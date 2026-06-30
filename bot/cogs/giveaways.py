"""Giveaways cog (slash commands + dashboard creation + entry requirements).

Managers run `/giveaway start|reroll|end`; giveaways can also be created in the
dashboard (the bot posts those via a pending-poll loop). Members enter by clicking
a button — the bot checks the configured requirements (roles, account age, server
membership age, leveling level) before registering the entry. When the timer ends
the draw loop picks random winners.

Duration accepts e.g. 30s / 10m / 2h / 1d (a bare number = minutes).

Backend contract (X-Bot-Token auth):
  POST /api/bot/guilds/{gid}/giveaways      body { channel_id, prize, winners_count,
        ends_at, host_id?, description?, required_role_ids?, min_account_age_days?,
        min_member_days?, min_level? } → full giveaway (incl. id)
  PUT  /api/bot/guilds/{gid}/giveaways/{id}/message   body { message_id }
  POST /api/bot/guilds/{gid}/giveaways/{id}/entries   body { user_id } → { added }
  GET  /api/bot/guilds/{gid}/giveaways/{id}           → { giveaway }   (incl. requirements)
  GET  /api/bot/guilds/{gid}/giveaways/{id}/entries   → { user_ids }
  GET  /api/bot/guilds/{gid}/leveling/user/{uid}      → { level }
  PUT  /api/bot/guilds/{gid}/giveaways/{id}/end       (end early)
  GET  /api/bot/giveaways/pending                     → { giveaways }  (dashboard, unposted)
  GET  /api/bot/giveaways/due                         → { giveaways }
  PUT  /api/bot/giveaways/{id}/ended

Logging prefix: "[giveaway]".
"""

import re
import time
import random

import discord
from discord import app_commands
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


def _is_manager(interaction):
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and (perms.manage_guild or perms.administrator))


class Giveaways(commands.Cog):
    giveaway = app_commands.Group(
        name="giveaway",
        description="Create and manage giveaways.",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.draw_loop.start()
        self.post_loop.start()

    def cog_unload(self):
        self.draw_loop.cancel()
        self.post_loop.cancel()

    # ----- embed / requirement rendering -------------------------------------

    def _requirement_lines(self, gv, guild, lang):
        lines = []
        roles = gv.get("required_role_ids") or []
        if roles:
            names = []
            for rid in roles:
                role = guild.get_role(int(rid)) if str(rid).isdigit() else None
                names.append(role.mention if role else f"`{rid}`")
            lines.append(t(lang, "giveaway.reqRoleLine", roles=", ".join(names)))
        if int(gv.get("min_account_age_days") or 0) > 0:
            lines.append(t(lang, "giveaway.reqAccountLine", days=int(gv["min_account_age_days"])))
        if int(gv.get("min_member_days") or 0) > 0:
            lines.append(t(lang, "giveaway.reqMemberLine", days=int(gv["min_member_days"])))
        if int(gv.get("min_level") or 0) > 0:
            lines.append(t(lang, "giveaway.reqLevelLine", level=int(gv["min_level"])))
        return lines

    def _build_embed(self, gv, guild, ended=False, color=GIVEAWAY_COLOR, lang="en"):
        embed = discord.Embed(title=t(lang, "giveaway.title"), color=color)
        if gv.get("description"):
            embed.description = str(gv["description"])[:1000]
        embed.add_field(name=t(lang, "giveaway.prize"), value=str(gv.get("prize") or "—"), inline=False)
        embed.add_field(name=t(lang, "giveaway.winners"), value=str(gv.get("winners_count") or 1), inline=True)
        if ended:
            embed.add_field(name=t(lang, "giveaway.status"), value=t(lang, "giveaway.ended"), inline=True)
        else:
            embed.add_field(name=t(lang, "giveaway.ends"), value=f"<t:{int(gv.get('ends_at') or 0)}:R>", inline=True)
        req_lines = self._requirement_lines(gv, guild, lang) if guild else []
        if req_lines:
            embed.add_field(name=t(lang, "giveaway.requirements"), value="\n".join(req_lines), inline=False)
        if gv.get("host_id"):
            # Field (not footer) so the host mention stays clickable.
            embed.add_field(name=t(lang, "giveaway.hostLabel"), value=f"<@{gv['host_id']}>", inline=True)
        if not ended:
            embed.set_footer(text=t(lang, "giveaway.joinFooter"))
        return embed

    # ----- slash commands ----------------------------------------------------

    @giveaway.command(name="start", description="Start a giveaway.")
    @app_commands.describe(
        prize="What is being given away.",
        winners="How many winners (1-50).",
        duration="How long, e.g. 30s, 10m, 2h, 1d.",
        required_role="Only members with this role may enter.",
        min_account_age="Minimum Discord account age in days.",
        min_member_age="Minimum days as a member of this server.",
        min_level="Minimum leveling level required.",
        description="Optional extra text shown in the giveaway.",
    )
    async def start(self, interaction: discord.Interaction, prize: str, winners: int, duration: str,
                    required_role: discord.Role = None, min_account_age: int = 0,
                    min_member_age: int = 0, min_level: int = 0, description: str = None):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not _is_manager(interaction):
            await interaction.response.send_message(t(lang, "giveaway.adminOnly"), ephemeral=True)
            return
        seconds = parse_duration(duration)
        if seconds is None:
            await interaction.response.send_message(t(lang, "giveaway.invalidDuration"), ephemeral=True)
            return
        if winners < 1 or winners > 50:
            await interaction.response.send_message(t(lang, "giveaway.winnersRange"), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ends_at = int(time.time()) + seconds
        created = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{interaction.guild.id}/giveaways",
            {
                "channel_id": str(interaction.channel.id),
                "prize": prize[:256],
                "winners_count": winners,
                "ends_at": ends_at,
                "host_id": str(interaction.user.id),
                "description": (description or "")[:1000],
                "required_role_ids": [str(required_role.id)] if required_role else [],
                "min_account_age_days": max(0, int(min_account_age or 0)),
                "min_member_days": max(0, int(min_member_age or 0)),
                "min_level": max(0, int(min_level or 0)),
            },
        )
        if not created or not created.get("id"):
            await interaction.followup.send(t(lang, "giveaway.startFailed"), ephemeral=True)
            return
        gid = created["id"]
        color = await general_config.get_embed_color(self.backend_url, self.api_key, interaction.guild.id, fallback=GIVEAWAY_COLOR)
        embed = self._build_embed(created, interaction.guild, color=color, lang=lang)
        try:
            msg = await interaction.channel.send(embed=embed, view=build_enter_view(gid))
        except discord.Forbidden:
            await interaction.followup.send(t(lang, "giveaway.cantPost"), ephemeral=True)
            return
        await bot_put(self.backend_url, self.api_key,
                      f"/api/bot/guilds/{interaction.guild.id}/giveaways/{gid}/message",
                      {"message_id": str(msg.id)})
        await interaction.followup.send(t(lang, "giveaway.startedOk"), ephemeral=True)

    @giveaway.command(name="reroll", description="Draw a new winner for a giveaway.")
    @app_commands.describe(giveaway_id="The giveaway id (from the dashboard).")
    async def reroll(self, interaction: discord.Interaction, giveaway_id: str):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not _is_manager(interaction):
            await interaction.response.send_message(t(lang, "giveaway.adminOnly"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/giveaways/{giveaway_id}")
        gv = (data or {}).get("giveaway")
        if not gv:
            await interaction.followup.send(t(lang, "giveaway.notFound"), ephemeral=True)
            return
        ent = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/giveaways/{giveaway_id}/entries")
        user_ids = (ent or {}).get("user_ids") or []
        if not user_ids:
            await interaction.followup.send(t(lang, "giveaway.noEntries"), ephemeral=True)
            return
        winner = random.choice(user_ids)
        await interaction.channel.send(t(lang, "giveaway.reroll", prize=gv.get("prize"), winner=winner))
        await interaction.followup.send(t(lang, "giveaway.startedOk"), ephemeral=True)

    @giveaway.command(name="end", description="End a giveaway early and draw winners.")
    @app_commands.describe(giveaway_id="The giveaway id (from the dashboard).")
    async def end(self, interaction: discord.Interaction, giveaway_id: str):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not _is_manager(interaction):
            await interaction.response.send_message(t(lang, "giveaway.adminOnly"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        res = await bot_put(self.backend_url, self.api_key,
                            f"/api/bot/guilds/{interaction.guild.id}/giveaways/{giveaway_id}/end", {})
        if res and res.get("ended"):
            await interaction.followup.send(t(lang, "giveaway.endedOk"), ephemeral=True)
        else:
            await interaction.followup.send(t(lang, "giveaway.notFound"), ephemeral=True)

    # ----- entry button ------------------------------------------------------

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("ge:"):
            return
        gid = custom_id[3:]
        # Backend round-trips before answering — defer immediately (token expiry 10062).
        await interaction.response.defer(ephemeral=True)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)

        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/giveaways/{gid}")
        gv = (data or {}).get("giveaway")
        if not gv or gv.get("ended"):
            await interaction.followup.send(t(lang, "giveaway.notFound"), ephemeral=True)
            return

        member = interaction.guild.get_member(interaction.user.id) or interaction.user
        ok, msg = await self._check_requirements(member, gv, interaction.guild, lang)
        if not ok:
            await interaction.followup.send(msg, ephemeral=True)
            return

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

    async def _check_requirements(self, member, gv, guild, lang):
        """Return (ok, message). Roles/age checked locally, level via backend."""
        now = discord.utils.utcnow()
        roles = gv.get("required_role_ids") or []
        if roles:
            member_role_ids = {str(r.id) for r in getattr(member, "roles", [])}
            if not any(str(rid) in member_role_ids for rid in roles):
                names = []
                for rid in roles:
                    role = guild.get_role(int(rid)) if str(rid).isdigit() else None
                    names.append(role.mention if role else f"`{rid}`")
                return False, t(lang, "giveaway.reqFailRole", roles=", ".join(names))

        min_acc = int(gv.get("min_account_age_days") or 0)
        if min_acc > 0 and member.created_at:
            age_days = (now - member.created_at).days
            if age_days < min_acc:
                return False, t(lang, "giveaway.reqFailAccount", days=min_acc)

        min_mem = int(gv.get("min_member_days") or 0)
        joined = getattr(member, "joined_at", None)
        if min_mem > 0 and joined:
            mem_days = (now - joined).days
            if mem_days < min_mem:
                return False, t(lang, "giveaway.reqFailMember", days=min_mem)

        min_level = int(gv.get("min_level") or 0)
        if min_level > 0:
            lvl_data = await bot_get(self.backend_url, self.api_key,
                                     f"/api/bot/guilds/{guild.id}/leveling/user/{member.id}")
            level = int((lvl_data or {}).get("level") or 0)
            if level < min_level:
                return False, t(lang, "giveaway.reqFailLevel", level=min_level)

        return True, ""

    # ----- pending-post loop (dashboard-created giveaways) -------------------

    @tasks.loop(seconds=30)
    async def post_loop(self):
        await self._post_pending()

    @post_loop.before_loop
    async def _before_post_loop(self):
        await self.bot.wait_until_ready()

    async def _post_pending(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/giveaways/pending")
        if not data:
            return
        for gv in (data.get("giveaways") or []):
            try:
                await self._post_one(gv)
            except Exception as exc:
                print(f"[giveaway] post error for {gv.get('id')}: {exc}")

    async def _post_one(self, gv):
        guild = self.bot.get_guild(int(gv["guild_id"]))
        channel = guild.get_channel(int(gv["channel_id"])) if guild and gv.get("channel_id") else None
        if channel is None:
            return
        lang = await lang_for(self.backend_url, self.api_key, gv["guild_id"])
        color = await general_config.get_embed_color(self.backend_url, self.api_key, gv["guild_id"], fallback=GIVEAWAY_COLOR)
        embed = self._build_embed(gv, guild, color=color, lang=lang)
        try:
            msg = await channel.send(embed=embed, view=build_enter_view(gv["id"]))
        except discord.Forbidden:
            print(f"[giveaway] missing permission to post in {channel.id}")
            return
        await bot_put(self.backend_url, self.api_key,
                      f"/api/bot/guilds/{gv['guild_id']}/giveaways/{gv['id']}/message",
                      {"message_id": str(msg.id)})

    # ----- draw loop ---------------------------------------------------------

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
