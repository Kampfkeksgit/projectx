"""Giveaways cog.

Admins start a giveaway with `!gstart <duration> <winners> <prize>`. Members
enter by clicking a button; when the timer ends the bot draws random winners.

Duration accepts e.g. 30s / 10m / 2h / 1d (a bare number = minutes).

Backend contract (X-Bot-Token auth):
  POST /api/bot/guilds/{gid}/giveaways          body { channel_id, prize, winners_count, ends_at } → { id }
  PUT  /api/bot/guilds/{gid}/giveaways/{id}/message  body { message_id }
  POST /api/bot/guilds/{gid}/giveaways/{id}/entries  body { user_id }
  GET  /api/bot/guilds/{gid}/giveaways/{id}/entries  → { user_ids }
  GET  /api/bot/giveaways/due                        → { giveaways }
  PUT  /api/bot/giveaways/{id}/ended

Logging prefix: "[giveaway]".
"""

import re
import time
import random

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_post, bot_put
from utils import general_config
from utils.bot_i18n import t, lang_for


GIVEAWAY_COLOR = 0xF59E0B
DURATION_RE = re.compile(r"^(\d+)([smhd]?)$", re.IGNORECASE)
DURATION_MULT = {"s": 1, "m": 60, "h": 3600, "d": 86400, "": 60}


def parse_duration(text):
    m = DURATION_RE.match((text or "").strip())
    if not m:
        return None
    value = int(m.group(1))
    unit = (m.group(2) or "").lower()
    seconds = value * DURATION_MULT.get(unit, 60)
    if seconds < 10 or seconds > 30 * 86400:
        return None
    return seconds


def build_enter_view(giveaway_id):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="Enter",
        custom_id=f"ge:{giveaway_id}",
        emoji="🎉",
    ))
    return view


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.draw_loop.start()

    def cog_unload(self):
        self.draw_loop.cancel()

    @commands.command(name="gstart")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def gstart(self, ctx, duration: str = None, winners: int = None, *, prize: str = None):
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if not duration or winners is None or not prize:
            await ctx.reply(t(lang, "giveaway.usage"), mention_author=False)
            return
        seconds = parse_duration(duration)
        if seconds is None:
            await ctx.reply(t(lang, "giveaway.invalidDuration"), mention_author=False)
            return
        if winners < 1 or winners > 50:
            await ctx.reply(t(lang, "giveaway.winnersRange"), mention_author=False)
            return

        ends_at = int(time.time()) + seconds
        created = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{ctx.guild.id}/giveaways",
            {"channel_id": str(ctx.channel.id), "prize": prize[:256], "winners_count": winners, "ends_at": ends_at},
        )
        if not created or not created.get("id"):
            await ctx.reply(t(lang, "giveaway.startFailed"), mention_author=False)
            return
        gid = created["id"]

        color = await general_config.get_embed_color(self.backend_url, self.api_key, ctx.guild.id, fallback=GIVEAWAY_COLOR)
        embed = self._build_embed(prize, winners, ends_at, color=color, lang=lang)
        try:
            msg = await ctx.send(embed=embed, view=build_enter_view(gid))
        except discord.Forbidden:
            await ctx.reply(t(lang, "giveaway.cantPost"), mention_author=False)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/giveaways/{gid}/message", {"message_id": str(msg.id)})

    def _build_embed(self, prize, winners, ends_at, ended=False, color=GIVEAWAY_COLOR, lang="en"):
        embed = discord.Embed(title=t(lang, "giveaway.title"), color=color)
        embed.add_field(name=t(lang, "giveaway.prize"), value=str(prize), inline=False)
        embed.add_field(name=t(lang, "giveaway.winners"), value=str(winners), inline=True)
        if ended:
            embed.add_field(name=t(lang, "giveaway.status"), value=t(lang, "giveaway.ended"), inline=True)
        else:
            embed.add_field(name=t(lang, "giveaway.ends"), value=f"<t:{ends_at}:R>", inline=True)
            embed.set_footer(text=t(lang, "giveaway.joinFooter"))
        return embed

    @commands.command(name="greroll")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def greroll(self, ctx, giveaway_id: str = None):
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if not giveaway_id:
            await ctx.reply(t(lang, "giveaway.rerollUsage"), mention_author=False)
            return
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/giveaways/{giveaway_id}")
        gv = (data or {}).get("giveaway")
        if not gv:
            await ctx.reply(t(lang, "giveaway.notFound"), mention_author=False)
            return
        ent = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/giveaways/{giveaway_id}/entries")
        user_ids = (ent or {}).get("user_ids") or []
        if not user_ids:
            await ctx.reply(t(lang, "giveaway.noEntries"), mention_author=False)
            return
        winner = random.choice(user_ids)
        await ctx.send(t(lang, "giveaway.reroll", prize=gv.get("prize"), winner=winner))

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("ge:"):
            return
        gid = custom_id[3:]
        # Backend-Call vor der Antwort — sofort deferren, sonst riskiert ein
        # langsamer Round-Trip den abgelaufenen Interaction-Token (10062).
        await interaction.response.defer(ephemeral=True)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{interaction.guild.id}/giveaways/{gid}/entries",
            {"user_id": str(interaction.user.id)},
        )
        if result and result.get("added"):
            await interaction.followup.send(t(lang, "giveaway.entered"), ephemeral=True)
        elif result is not None:
            await interaction.followup.send(t(lang, "giveaway.alreadyEntered"), ephemeral=True)
        else:
            await interaction.followup.send(t(lang, "giveaway.entryFailed"), ephemeral=True)

    @tasks.loop(seconds=30)
    async def draw_loop(self):
        await self._draw_due()

    @draw_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _draw_due(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/giveaways/due")
        if not data:
            return
        for g in (data.get("giveaways") or []):
            try:
                await self._draw_one(g)
            except Exception as exc:
                print(f"[giveaway] draw error for {g.get('id')}: {exc}")
            # Always mark ended so a broken giveaway doesn't loop forever.
            await bot_put(self.backend_url, self.api_key, f"/api/bot/giveaways/{g['id']}/ended", {})

    async def _draw_one(self, g):
        guild = self.bot.get_guild(int(g["guild_id"]))
        channel = guild.get_channel(int(g["channel_id"])) if guild and g.get("channel_id") else None
        if channel is None:
            return
        ent = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{g['guild_id']}/giveaways/{g['id']}/entries")
        user_ids = (ent or {}).get("user_ids") or []

        lang = await lang_for(self.backend_url, self.api_key, g["guild_id"])
        if not user_ids:
            await channel.send(t(lang, "giveaway.noWinner", prize=g.get("prize")))
            return

        count = min(int(g.get("winners_count") or 1), len(user_ids))
        winners = random.sample(user_ids, count)
        mentions = ", ".join(f"<@{uid}>" for uid in winners)
        await channel.send(t(lang, "giveaway.won", mentions=mentions, prize=g.get("prize")))


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
