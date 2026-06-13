"""Scheduled Announcements cog.

Posts configured messages on a schedule — either once at a set time or on a
recurring interval. The backend computes the next run; the bot just polls for
due messages, posts them, and reports back.

Backend contract (X-Bot-Token auth):
  GET /api/bot/scheduled/due     → { messages: [{ id, guild_id, channel_id, content, ... }] }
  PUT /api/bot/scheduled/{id}/ran  → advance interval / disable once

Logging prefix: "[scheduler]".
"""

from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put


POLL_SECONDS = 30


class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_loop(self):
        await self._run()

    @poll_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _run(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/scheduled/due")
        if not data:
            return
        for msg in (data.get("messages") or []):
            try:
                await self._post(msg)
            except Exception as exc:
                print(f"[scheduler] post error for {msg.get('id')}: {exc}")

    async def _post(self, msg):
        guild = self.bot.get_guild(int(msg["guild_id"]))
        channel = guild.get_channel(int(msg["channel_id"])) if guild else None
        content = (msg.get("content") or "").strip()

        posted = False
        if channel is not None and content:
            text = content.replace("{guild}", guild.name)
            try:
                await channel.send(text[:2000])
                posted = True
            except Exception as exc:
                print(f"[scheduler] send failed for {msg.get('id')}: {exc}")

        # Always advance/disable so a broken entry doesn't fire forever.
        _ = posted
        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/scheduled/{msg['id']}/ran", {},
        )


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
