"""Counting game cog.

Watches the configured counting channel; every message must be the next number
in sequence and no user may count twice in a row. The backend validates each
number atomically (and tracks current count + high score). On a wrong number the
chain optionally resets to 0.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/counting
       → { enabled, channel_id, count_emoji, reset_on_fail, current_count, high_score }
  POST /api/bot/guilds/{gid}/counting/count  body { user_id, number }
       → { accepted, current, high_score, expected, reset, reason, new_record }

Logging prefix: "[counting]".
"""

import time

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post


SETTINGS_TTL_SECONDS = 60


class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._cache = {}

    async def _settings(self, guild_id):
        key = str(guild_id)
        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "counting")
        if settings is not None:
            self._cache[key] = (settings, now)
        return settings

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        content = (message.content or "").strip()
        if not content:
            return
        first = content.split()[0]
        if not first.lstrip("+").isdigit():
            return

        settings = await self._settings(message.guild.id)
        if not settings or not settings.get("enabled"):
            return
        channel_id = settings.get("channel_id")
        if not channel_id or str(message.channel.id) != str(channel_id):
            return

        try:
            number = int(first)
        except (ValueError, TypeError):
            return

        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{message.guild.id}/counting/count",
            {"user_id": str(message.author.id), "number": number},
        )
        if not result:
            return

        if result.get("accepted"):
            emoji = settings.get("count_emoji") or "✅"
            try:
                await message.add_reaction(emoji)
            except Exception:
                try:
                    await message.add_reaction("✅")
                except Exception:
                    pass
            if result.get("new_record"):
                try:
                    await message.add_reaction("🏆")
                except Exception:
                    pass
            return

        reason = result.get("reason")
        if reason not in ("wrong_number", "double_count"):
            return
        try:
            await message.add_reaction("❌")
        except Exception:
            pass
        if result.get("reset"):
            reached = max((result.get("expected") or 1) - 1, 0)
            if reason == "double_count":
                txt = f"💥 {message.author.mention} you can't count twice in a row! The count is back to **1**."
            else:
                txt = f"💥 {message.author.mention} ruined it at **{reached}**! The next number was **{result.get('expected')}**. Back to **1**."
            try:
                await message.channel.send(txt)
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(Counting(bot))
