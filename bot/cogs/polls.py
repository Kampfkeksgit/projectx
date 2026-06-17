"""Polls cog.

Admins/members create a poll with `!poll Question | Option A | Option B | ...`
(2–10 options). Members vote via buttons; the embed shows a live tally. Optional
timed polls are closed by the backend-driven loop.

Backend contract (X-Bot-Token auth):
  POST /api/bot/guilds/{gid}/polls                body { channel_id, question, options, multi, ends_at } → { id, ... }
  PUT  /api/bot/guilds/{gid}/polls/{pid}/message  body { message_id }
  POST /api/bot/guilds/{gid}/polls/{pid}/vote     body { user_id, option_index } → { ok, counts, options, question, multi }
  GET  /api/bot/polls/due                         → { polls }
  PUT  /api/bot/polls/{pid}/ended

Logging prefix: "[polls]".
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_post, bot_put


POLL_COLOR = 0x5865F2
BAR_LEN = 12
OPTION_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def build_poll_embed(question, options, counts, multi, ended=False):
    counts = counts or [0] * len(options)
    total = sum(counts) or 0
    embed = discord.Embed(
        title=("📊 " + (question or "Poll"))[:256],
        color=POLL_COLOR,
    )
    lines = []
    for i, opt in enumerate(options):
        c = counts[i] if i < len(counts) else 0
        pct = (c / total * 100) if total else 0
        filled = int(round(pct / 100 * BAR_LEN))
        bar = "█" * filled + "░" * (BAR_LEN - filled)
        emoji = OPTION_EMOJI[i] if i < len(OPTION_EMOJI) else "•"
        lines.append(f"{emoji} **{opt}**\n`{bar}` {c} ({pct:.0f}%)")
    embed.description = "\n\n".join(lines)
    foot = f"{total} vote(s)" + (" • multiple choice" if multi else " • single choice")
    embed.set_footer(text=foot + (" • Closed" if ended else ""))
    return embed


def build_poll_view(poll_id, options):
    view = discord.ui.View(timeout=None)
    for i, opt in enumerate(options):
        emoji = OPTION_EMOJI[i] if i < len(OPTION_EMOJI) else None
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=str(opt)[:80],
            emoji=emoji,
            custom_id=f"pv:{poll_id}:{i}",
        ))
    return view


class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.close_loop.start()

    def cog_unload(self):
        self.close_loop.cancel()

    @commands.command(name="poll")
    @commands.guild_only()
    async def poll(self, ctx, *, text: str = None):
        if not text or "|" not in text:
            await ctx.reply("Usage: `!poll Question | Option A | Option B | ...` (2–10 options)", mention_author=False)
            return
        parts = [p.strip() for p in text.split("|")]
        question = parts[0]
        options = [p for p in parts[1:] if p][:10]
        if not question or len(options) < 2:
            await ctx.reply("A poll needs a question and at least 2 options.", mention_author=False)
            return

        created = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{ctx.guild.id}/polls",
            {"channel_id": str(ctx.channel.id), "question": question, "options": options, "multi": False, "ends_at": 0},
        )
        if not created or not created.get("id"):
            await ctx.reply("Couldn't create the poll right now.", mention_author=False)
            return
        pid = created["id"]
        embed = build_poll_embed(question, options, [0] * len(options), False)
        try:
            msg = await ctx.send(embed=embed, view=build_poll_view(pid, options))
        except discord.Forbidden:
            await ctx.reply("I can't post in this channel.", mention_author=False)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/polls/{pid}/message", {"message_id": str(msg.id)})
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("pv:"):
            return
        try:
            _, pid, idx = custom_id.split(":", 2)
            option_index = int(idx)
        except (ValueError, IndexError):
            return
        await interaction.response.defer(ephemeral=True)
        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{interaction.guild.id}/polls/{pid}/vote",
            {"user_id": str(interaction.user.id), "option_index": option_index},
        )
        if not result or not result.get("ok"):
            reason = (result or {}).get("reason")
            msg = "This poll is closed." if reason == "closed" else "Couldn't register your vote."
            await interaction.followup.send(msg, ephemeral=True)
            return
        options = result.get("options") or []
        embed = build_poll_embed(result.get("question"), options, result.get("counts"), result.get("multi"))
        try:
            await interaction.message.edit(embed=embed, view=build_poll_view(pid, options))
        except Exception as exc:
            print(f"[polls] edit failed: {exc}")
        await interaction.followup.send("✅ Your vote was counted.", ephemeral=True)

    @tasks.loop(seconds=30)
    async def close_loop(self):
        await self._close_due()

    @close_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _close_due(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/polls/due")
        if not data:
            return
        for poll in (data.get("polls") or []):
            try:
                await self._close_one(poll)
            except Exception as exc:
                print(f"[polls] close error for {poll.get('id')}: {exc}")
            await bot_put(self.backend_url, self.api_key, f"/api/bot/polls/{poll['id']}/ended", {})

    async def _close_one(self, poll):
        guild = self.bot.get_guild(int(poll["guild_id"]))
        channel = guild.get_channel(int(poll["channel_id"])) if guild and poll.get("channel_id") else None
        if channel is None:
            return
        options = poll.get("options") or []
        counts = poll.get("counts") or [0] * len(options)
        embed = build_poll_embed(poll.get("question"), options, counts, poll.get("multi"), ended=True)
        if poll.get("message_id"):
            try:
                msg = await channel.fetch_message(int(poll["message_id"]))
                await msg.edit(embed=embed, view=None)
            except Exception:
                pass
        if options and sum(counts):
            top = max(range(len(options)), key=lambda i: counts[i] if i < len(counts) else 0)
            await channel.send(f"📊 Poll ended — **{options[top]}** wins with {counts[top]} vote(s)!")


async def setup(bot):
    await bot.add_cog(Polls(bot))
