"""Trivia quiz cog.

Members start a trivia round with `!trivia`. The bot posts a general-knowledge
question with four labelled answer buttons (A–D). The first player to click the
correct answer wins; their win is scored via the backend. After 25 seconds the
answer auto-reveals if nobody solved it.

Clicks are handled via on_interaction (custom_id "trv:<token>:<idx>") so the
buttons keep working without persistent-view registration. Sessions live only in
memory (a round is short-lived), keyed by a short random token.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/games
       → { games_channel_id, trivia_enabled, ... } or None
  POST /api/bot/guilds/{gid}/games/score
       body { user_id, game: "trivia", win: true }

Logging prefix: "[trivia]".
"""

import time
import uuid
import random
import asyncio

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post


SETTINGS_TTL_SECONDS = 60
TRIVIA_COLOR = 0x6366F1
REVEAL_AFTER_SECONDS = 25
OPTION_LABELS = ["A", "B", "C", "D"]


QUESTIONS = [
    {"q": "What is the largest planet in our solar system?",
     "options": ["Earth", "Jupiter", "Saturn", "Neptune"], "answer": 1},
    {"q": "Which gas do plants primarily absorb from the atmosphere?",
     "options": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"], "answer": 2},
    {"q": "How many continents are there on Earth?",
     "options": ["5", "6", "7", "8"], "answer": 2},
    {"q": "What is the capital city of Japan?",
     "options": ["Seoul", "Beijing", "Bangkok", "Tokyo"], "answer": 3},
    {"q": "Which animal is known as the 'King of the Jungle'?",
     "options": ["Tiger", "Lion", "Elephant", "Bear"], "answer": 1},
    {"q": "What is the chemical symbol for water?",
     "options": ["H2O", "CO2", "O2", "NaCl"], "answer": 0},
    {"q": "How many sides does a hexagon have?",
     "options": ["5", "6", "7", "8"], "answer": 1},
    {"q": "Which planet is known as the Red Planet?",
     "options": ["Venus", "Mars", "Mercury", "Jupiter"], "answer": 1},
    {"q": "What is the tallest mountain in the world?",
     "options": ["K2", "Mount Kilimanjaro", "Mount Everest", "Denali"], "answer": 2},
    {"q": "Which ocean is the largest?",
     "options": ["Atlantic", "Indian", "Arctic", "Pacific"], "answer": 3},
    {"q": "How many colors are there in a rainbow?",
     "options": ["5", "6", "7", "9"], "answer": 2},
    {"q": "What is the fastest land animal?",
     "options": ["Cheetah", "Lion", "Horse", "Greyhound"], "answer": 0},
    {"q": "Which language has the most native speakers worldwide?",
     "options": ["English", "Hindi", "Mandarin Chinese", "Spanish"], "answer": 2},
    {"q": "What is the smallest prime number?",
     "options": ["0", "1", "2", "3"], "answer": 2},
    {"q": "Which instrument has 88 keys?",
     "options": ["Guitar", "Piano", "Violin", "Flute"], "answer": 1},
    {"q": "What is the freezing point of water in degrees Celsius?",
     "options": ["0", "32", "100", "-10"], "answer": 0},
    {"q": "Which country is home to the kangaroo?",
     "options": ["South Africa", "Brazil", "Australia", "India"], "answer": 2},
    {"q": "How many legs does a spider have?",
     "options": ["6", "8", "10", "12"], "answer": 1},
    {"q": "What is the main ingredient in guacamole?",
     "options": ["Tomato", "Avocado", "Pepper", "Onion"], "answer": 1},
    {"q": "Which planet is closest to the Sun?",
     "options": ["Venus", "Earth", "Mercury", "Mars"], "answer": 2},
]


def build_question_view(token, count):
    view = discord.ui.View(timeout=None)
    for idx in range(min(count, 4)):
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=OPTION_LABELS[idx],
            custom_id=f"trv:{token}:{idx}",
        ))
    return view


class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}
        # token -> { "answer": int, "answered": set(), "solved": bool, "message": Message, "guild_id": int }
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

    @commands.command(name="trivia")
    @commands.guild_only()
    async def trivia(self, ctx):
        try:
            settings = await self._get_settings(ctx.guild.id, force=True)
            if not settings or not settings.get("trivia_enabled"):
                await ctx.reply("Trivia is not enabled on this server.", mention_author=False)
                return

            games_channel_id = settings.get("games_channel_id")
            if games_channel_id and str(games_channel_id) != str(ctx.channel.id):
                channel = ctx.guild.get_channel(int(games_channel_id))
                where = channel.mention if channel else "the configured games channel"
                await ctx.reply(f"Please use trivia in {where}.", mention_author=False)
                return

            question = random.choice(QUESTIONS)
            options = question["options"]
            answer = int(question["answer"])

            token = uuid.uuid4().hex[:8]
            embed = discord.Embed(
                title="🧠 Trivia Time!",
                description=question["q"],
                color=TRIVIA_COLOR,
            )
            for i, opt in enumerate(options[:4]):
                embed.add_field(name=f"{OPTION_LABELS[i]}", value=str(opt), inline=False)
            embed.set_footer(text=f"First correct answer wins • {REVEAL_AFTER_SECONDS}s")

            try:
                msg = await ctx.send(embed=embed, view=build_question_view(token, len(options)))
            except discord.Forbidden:
                await ctx.reply("I can't post in this channel.", mention_author=False)
                return

            self._sessions[token] = {
                "answer": answer,
                "answered": set(),
                "solved": False,
                "message": msg,
                "guild_id": ctx.guild.id,
                "options": list(options[:4]),
            }
            asyncio.create_task(self._auto_reveal(token))
        except Exception as exc:
            print(f"[trivia] start failed in {getattr(ctx.guild, 'id', '?')}: {exc}")
            try:
                await ctx.reply("Couldn't start trivia right now.", mention_author=False)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        try:
            if interaction.type != discord.InteractionType.component or interaction.guild is None:
                return
            custom_id = (interaction.data or {}).get("custom_id") or ""
            if not custom_id.startswith("trv:"):
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                return
            token = parts[1]
            try:
                idx = int(parts[2])
            except ValueError:
                return

            session = self._sessions.get(token)
            if not session:
                await interaction.response.send_message("This question has expired.", ephemeral=True)
                return

            uid = interaction.user.id
            if uid in session["answered"]:
                await interaction.response.send_message("You already answered.", ephemeral=True)
                return
            session["answered"].add(uid)

            if idx == session["answer"]:
                await self._handle_win(interaction, token, session)
            else:
                await interaction.response.send_message("❌ Not quite!", ephemeral=True)
        except Exception as exc:
            print(f"[trivia] interaction error: {exc}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Something went wrong.", ephemeral=True)
            except Exception:
                pass

    async def _handle_win(self, interaction, token, session):
        # Mark solved + remove the session up front so the auto-reveal can't fire.
        session["solved"] = True
        self._sessions.pop(token, None)

        await interaction.response.defer()

        message = session.get("message")
        answer = session["answer"]
        options = session.get("options") or []
        correct_text = options[answer] if answer < len(options) else "?"

        embed = discord.Embed(
            title="🧠 Trivia — Solved!",
            description=f"The correct answer was **{OPTION_LABELS[answer]}. {correct_text}**\n\n🎉 {interaction.user.mention} got it!",
            color=TRIVIA_COLOR,
        )
        try:
            if message is not None:
                await message.edit(embed=embed, view=self._disabled_view(message))
        except Exception as exc:
            print(f"[trivia] win edit failed: {exc}")

        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{session['guild_id']}/games/score",
                {"user_id": str(interaction.user.id), "game": "trivia", "win": True},
            )
        except Exception as exc:
            print(f"[trivia] score failed: {exc}")

    async def _auto_reveal(self, token):
        try:
            await asyncio.sleep(REVEAL_AFTER_SECONDS)
            session = self._sessions.get(token)
            if not session or session.get("solved"):
                return
            # Claim the session so a late click can't double-fire.
            self._sessions.pop(token, None)

            message = session.get("message")
            answer = session["answer"]
            options = session.get("options") or []
            correct_text = options[answer] if answer < len(options) else "?"

            embed = discord.Embed(
                title="🧠 Trivia — Time's up!",
                description=f"Time's up! The answer was **{OPTION_LABELS[answer]}. {correct_text}**",
                color=TRIVIA_COLOR,
            )
            if message is not None:
                await message.edit(embed=embed, view=self._disabled_view(message))
        except Exception as exc:
            print(f"[trivia] auto-reveal failed: {exc}")

    @staticmethod
    def _disabled_view(message):
        view = discord.ui.View(timeout=None)
        try:
            existing = discord.ui.View.from_message(message)
            for child in existing.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    view.add_item(child)
        except Exception:
            pass
        return view


async def setup(bot):
    await bot.add_cog(Trivia(bot))
