"""Rock-Paper-Scissors cog.

`!rps [@opponent]` starts a game. Without an opponent the author plays against
the bot (instant resolve). With an opponent both human players must each pick a
move via the buttons; once both have chosen the result is revealed.

Moves are picked via buttons (custom_id "rps:<token>:<choice>") handled in
on_interaction so they keep working across restarts. Sessions live in memory
keyed by an 8-char token; an expired/unknown token replies ephemerally.

Settings are read from the "games" module:
  GET /api/bot/guilds/{gid}/settings/games
      → { games_channel_id, rps_enabled, ... } or None

Scoring (humans only, never the bot):
  POST /api/bot/guilds/{gid}/games/score
      body { user_id, game: "rps", win: <bool> }

Logging prefix: "[rps]".
"""

import time
import uuid
import random

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post


SETTINGS_TTL_SECONDS = 60
RPS_COLOR = 0x6366F1

CHOICES = ("rock", "paper", "scissors")
EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
LABEL = {"rock": "Rock", "paper": "Paper", "scissors": "Scissors"}
# What each move beats.
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


def pretty(choice):
    return f"{EMOJI.get(choice, '')} {LABEL.get(choice, str(choice))}".strip()


def resolve(a, b):
    """Return 1 if `a` beats `b`, -1 if `b` beats `a`, 0 on a tie."""
    if a == b:
        return 0
    return 1 if BEATS.get(a) == b else -1


def build_view(token, disabled=False):
    view = discord.ui.View(timeout=None)
    for choice in CHOICES:
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=LABEL[choice],
            emoji=EMOJI[choice],
            custom_id=f"rps:{token}:{choice}",
            disabled=disabled,
        ))
    return view


class RPS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}
        # token -> session dict
        self._sessions = {}

    async def _get_settings(self, guild_id, force=False):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if not force and cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "games")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    async def _score(self, guild_id, user_id, win):
        """Record a result for a single human player. Never call for the bot."""
        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{guild_id}/games/score",
                {"user_id": str(user_id), "game": "rps", "win": bool(win)},
            )
        except Exception as exc:
            print(f"[rps] score failed in {guild_id} for {user_id}: {exc}")

    @commands.command(name="rps")
    @commands.guild_only()
    async def rps(self, ctx, opponent: discord.Member = None):
        settings = await self._get_settings(ctx.guild.id, force=True)
        if not settings or not settings.get("rps_enabled"):
            await ctx.reply("Rock-Paper-Scissors is not enabled here.", mention_author=False)
            return

        games_channel_id = settings.get("games_channel_id")
        if games_channel_id and str(games_channel_id) != str(ctx.channel.id):
            channel = ctx.guild.get_channel(int(games_channel_id)) if str(games_channel_id).isdigit() else None
            where = channel.mention if channel else "the configured games channel"
            await ctx.reply(f"Please play games in {where}.", mention_author=False)
            return

        # vs opponent
        if opponent is not None:
            if opponent.bot:
                await ctx.reply("You can't challenge a bot. Use `!rps` to play against me.", mention_author=False)
                return
            if opponent.id == ctx.author.id:
                await ctx.reply("You can't challenge yourself.", mention_author=False)
                return
            await self._start_pvp(ctx, opponent)
            return

        # vs bot
        await self._start_vs_bot(ctx)

    async def _start_vs_bot(self, ctx):
        token = uuid.uuid4().hex[:8]
        self._sessions[token] = {
            "mode": "bot",
            "guild_id": ctx.guild.id,
            "author_id": ctx.author.id,
            "created": time.time(),
        }
        embed = discord.Embed(
            title="🪨 📄 ✂️ Rock-Paper-Scissors",
            description=f"{ctx.author.mention}, make your move!",
            color=RPS_COLOR,
        )
        try:
            await ctx.send(embed=embed, view=build_view(token))
        except discord.Forbidden:
            self._sessions.pop(token, None)
            await ctx.reply("I can't post in this channel.", mention_author=False)

    async def _start_pvp(self, ctx, opponent):
        token = uuid.uuid4().hex[:8]
        self._sessions[token] = {
            "mode": "pvp",
            "guild_id": ctx.guild.id,
            "p1_id": ctx.author.id,
            "p2_id": opponent.id,
            "p1_choice": None,
            "p2_choice": None,
            "created": time.time(),
        }
        embed = discord.Embed(
            title="🪨 📄 ✂️ Rock-Paper-Scissors",
            description=(
                f"{ctx.author.mention} vs {opponent.mention}\n\n"
                "Both players, pick your move with the buttons below."
            ),
            color=RPS_COLOR,
        )
        try:
            await ctx.send(embed=embed, view=build_view(token))
        except discord.Forbidden:
            self._sessions.pop(token, None)
            await ctx.reply("I can't post in this channel.", mention_author=False)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("rps:"):
            return

        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        _, token, choice = parts
        if choice not in CHOICES:
            return

        session = self._sessions.get(token)
        if session is None:
            try:
                await interaction.response.send_message("This game has expired.", ephemeral=True)
            except Exception:
                pass
            return

        try:
            if session.get("mode") == "bot":
                await self._handle_vs_bot(interaction, token, session, choice)
            else:
                await self._handle_pvp(interaction, token, session, choice)
        except Exception as exc:
            print(f"[rps] interaction error in {interaction.guild.id}: {exc}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Something went wrong with that game.", ephemeral=True)
                else:
                    await interaction.response.send_message("Something went wrong with that game.", ephemeral=True)
            except Exception:
                pass

    async def _handle_vs_bot(self, interaction, token, session, choice):
        if interaction.user.id != session["author_id"]:
            await interaction.response.send_message("This game isn't yours. Start your own with `!rps`.", ephemeral=True)
            return

        # Consume the session up front so a double-click can't resolve twice.
        self._sessions.pop(token, None)

        bot_choice = random.choice(CHOICES)
        outcome = resolve(choice, bot_choice)  # 1 player wins, -1 bot wins, 0 tie

        if outcome == 1:
            result = f"🎉 {interaction.user.mention} wins!"
            win = True
        elif outcome == -1:
            result = f"🤖 I win this time, {interaction.user.mention}!"
            win = False
        else:
            result = "🤝 It's a tie!"
            win = False

        embed = discord.Embed(title="🪨 📄 ✂️ Rock-Paper-Scissors", color=RPS_COLOR)
        embed.add_field(name=str(interaction.user.display_name), value=pretty(choice), inline=True)
        embed.add_field(name="Me", value=pretty(bot_choice), inline=True)
        embed.add_field(name="Result", value=result, inline=False)

        await interaction.response.edit_message(embed=embed, view=build_view(token, disabled=True))
        await self._score(session["guild_id"], session["author_id"], win)

    async def _handle_pvp(self, interaction, token, session, choice):
        uid = interaction.user.id
        if uid == session["p1_id"]:
            slot = "p1_choice"
        elif uid == session["p2_id"]:
            slot = "p2_choice"
        else:
            await interaction.response.send_message("You're not part of this match.", ephemeral=True)
            return

        if session.get(slot) is not None:
            await interaction.response.send_message(
                f"You already chose {pretty(session[slot])}.", ephemeral=True
            )
            return

        session[slot] = choice
        await interaction.response.send_message(f"You chose {pretty(choice)}. Waiting for the result…", ephemeral=True)

        # Resolve only once both players have picked.
        if session.get("p1_choice") is None or session.get("p2_choice") is None:
            return

        # Consume the session so a race can't resolve twice.
        if self._sessions.pop(token, None) is None:
            return

        p1_id = session["p1_id"]
        p2_id = session["p2_id"]
        p1_choice = session["p1_choice"]
        p2_choice = session["p2_choice"]
        guild = interaction.guild
        guild_id = session["guild_id"]

        outcome = resolve(p1_choice, p2_choice)  # 1 p1 wins, -1 p2 wins, 0 tie

        m1 = guild.get_member(p1_id)
        m2 = guild.get_member(p2_id)
        name1 = m1.display_name if m1 else f"User {p1_id}"
        name2 = m2.display_name if m2 else f"User {p2_id}"
        mention1 = m1.mention if m1 else f"<@{p1_id}>"
        mention2 = m2.mention if m2 else f"<@{p2_id}>"

        if outcome == 1:
            result = f"🎉 {mention1} wins!"
        elif outcome == -1:
            result = f"🎉 {mention2} wins!"
        else:
            result = "🤝 It's a tie!"

        embed = discord.Embed(title="🪨 📄 ✂️ Rock-Paper-Scissors", color=RPS_COLOR)
        embed.add_field(name=name1, value=pretty(p1_choice), inline=True)
        embed.add_field(name=name2, value=pretty(p2_choice), inline=True)
        embed.add_field(name="Result", value=result, inline=False)

        try:
            await interaction.message.edit(embed=embed, view=build_view(token, disabled=True))
        except Exception as exc:
            print(f"[rps] could not edit pvp message in {guild_id}: {exc}")

        # Score both humans: winner True, loser False, tie both False.
        await self._score(guild_id, p1_id, outcome == 1)
        await self._score(guild_id, p2_id, outcome == -1)


async def setup(bot):
    await bot.add_cog(RPS(bot))
