"""Hangman cog.

Members run `!hangman` to start a guessing game in a channel. Players then type
single letters as messages to guess the hidden word. The first solver wins; the
bot scores the solver via the backend.

This cog uses an on_message listener for letter guesses (NOT buttons). It never
calls bot.process_commands — main.py / the command framework handles that.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/games
      → { games_channel_id, hangman_enabled, ... }
  POST /api/bot/guilds/{gid}/games/score
      body { user_id, game, win }

Logging prefix: "[hangman]".
"""

import random

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post


HANGMAN_COLOR = 0x5865F2
WIN_COLOR = 0x22C55E
LOSE_COLOR = 0xEF4444
MAX_ATTEMPTS = 6

# Family-friendly words, lowercase, letters only, 4–10 chars.
WORDS = [
    "apple", "banana", "orange", "grape", "lemon",
    "garden", "flower", "forest", "river", "mountain",
    "rocket", "planet", "comet", "galaxy", "meteor",
    "guitar", "violin", "piano", "drum", "trumpet",
    "castle", "bridge", "tower", "island", "harbor",
    "dragon", "wizard", "knight", "puzzle", "treasure",
    "rainbow", "thunder", "breeze", "sunset", "winter",
    "pencil", "marble", "candle", "basket", "blanket",
]


def mask_word(word, guessed):
    """Return the word with un-guessed letters shown as underscores, e.g. '_ a _ _'."""
    return " ".join(letter if letter in guessed else "_" for letter in word)


def is_solved(word, guessed):
    return all(letter in guessed for letter in word)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # channel.id -> { word, guessed:set, wrong:set, attempts_left:int, message }
        self._games = {}

    def _build_embed(self, game, title="Hangman", color=HANGMAN_COLOR, footer=None):
        embed = discord.Embed(title=title, color=color)
        embed.add_field(
            name="Word",
            value=f"`{mask_word(game['word'], game['guessed'])}`",
            inline=False,
        )
        wrong = game["wrong"]
        embed.add_field(
            name="Wrong letters",
            value=", ".join(sorted(wrong)) if wrong else "—",
            inline=True,
        )
        embed.add_field(
            name="Attempts left",
            value=str(game["attempts_left"]),
            inline=True,
        )
        embed.set_footer(text=footer or "Type a single letter to guess.")
        return embed

    @commands.command(name="hangman")
    @commands.guild_only()
    async def hangman(self, ctx):
        if ctx.channel.id in self._games:
            await ctx.reply("A game is already running here.", mention_author=False)
            return

        settings = await fetch_bot_settings(self.backend_url, self.api_key, ctx.guild.id, "games")
        if not settings or not settings.get("hangman_enabled"):
            await ctx.reply("Hangman is not enabled on this server.", mention_author=False)
            return

        games_channel_id = settings.get("games_channel_id")
        if games_channel_id and str(ctx.channel.id) != str(games_channel_id):
            channel = ctx.guild.get_channel(int(games_channel_id)) if str(games_channel_id).isdigit() else None
            where = channel.mention if channel else "the configured games channel"
            await ctx.reply(f"Hangman can only be played in {where}.", mention_author=False)
            return

        word = random.choice(WORDS)
        game = {
            "word": word,
            "guessed": set(),
            "wrong": set(),
            "attempts_left": MAX_ATTEMPTS,
            "message": None,
        }
        self._games[ctx.channel.id] = game

        try:
            game["message"] = await ctx.send(embed=self._build_embed(game))
        except Exception as exc:
            print(f"[hangman] failed to post game in {ctx.channel.id}: {exc}")
            self._games.pop(ctx.channel.id, None)

    async def _refresh_embed(self, channel, game, **kwargs):
        """Edit the stored message if possible; fall back to posting a new one."""
        embed = self._build_embed(game, **kwargs)
        msg = game.get("message")
        if msg is not None:
            try:
                await msg.edit(embed=embed)
                return
            except Exception:
                pass
        try:
            game["message"] = await channel.send(embed=embed)
        except Exception as exc:
            print(f"[hangman] failed to refresh embed in {getattr(channel, 'id', '?')}: {exc}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.guild is None:
            return

        game = self._games.get(message.channel.id)
        if game is None:
            return

        content = message.content.strip()
        if len(content) != 1 or not content.isalpha() or not content.isascii():
            return

        letter = content.lower()

        if letter in game["guessed"] or letter in game["wrong"]:
            try:
                await message.add_reaction("♻️")
            except Exception:
                pass
            return

        if letter in game["word"]:
            game["guessed"].add(letter)
            if is_solved(game["word"], game["guessed"]):
                word = game["word"]
                # Win: clean up first so a re-trigger can't double-score.
                self._games.pop(message.channel.id, None)
                await self._refresh_embed(
                    message.channel, game,
                    title="🎉 Solved!", color=WIN_COLOR,
                    footer=f"{message.author} guessed it.",
                )
                try:
                    await message.channel.send(
                        f"🎉 {message.author.mention} solved it: **{word.upper()}**"
                    )
                except Exception as exc:
                    print(f"[hangman] win announce failed: {exc}")
                await self._score_solver(message.guild.id, message.author.id)
            else:
                await self._refresh_embed(message.channel, game, footer="Correct! Keep going.")
            return

        # Wrong letter.
        game["wrong"].add(letter)
        game["attempts_left"] -= 1
        if game["attempts_left"] <= 0:
            word = game["word"]
            self._games.pop(message.channel.id, None)
            try:
                await message.channel.send(
                    f"💀 Out of attempts! The word was **{word.upper()}**"
                )
            except Exception as exc:
                print(f"[hangman] lose announce failed: {exc}")
            return

        await self._refresh_embed(message.channel, game, footer="Wrong letter!")

    async def _score_solver(self, guild_id, uid):
        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{guild_id}/games/score",
                {"user_id": str(uid), "game": "hangman", "win": True},
            )
        except Exception as exc:
            print(f"[hangman] score failed for {uid} in {guild_id}: {exc}")


async def setup(bot):
    await bot.add_cog(Hangman(bot))
