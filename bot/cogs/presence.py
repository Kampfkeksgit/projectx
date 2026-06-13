"""
Presence cog — syncs the bot's current guild membership to the backend.

The frontend uses the resulting `guilds.bot_present` flag to decide whether to
show "Configure" (bot is in the guild) or "Invite" (bot is missing). We sync:
  - on_ready (initial)
  - on_guild_join / on_guild_remove (event-driven)
  - every 5 minutes (fallback in case events are missed)
"""

import time
import aiohttp
from discord.ext import commands, tasks
import config


SYNC_INTERVAL_MINUTES = 5
REQUEST_TIMEOUT_SECONDS = 10


class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # Captured the first time on_ready fires; used as the public uptime baseline.
        self.started_at = None
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # Set the uptime baseline the first time we connect (don't reset on reconnects).
        if self.started_at is None:
            self.started_at = int(time.time())
        # First sync after the bot is ready and `bot.guilds` is populated.
        await self._sync()
        await self._push_stats()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self._sync()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self._sync()

    @tasks.loop(minutes=SYNC_INTERVAL_MINUTES)
    async def sync_loop(self):
        await self._sync()
        await self._push_stats()

    @sync_loop.before_loop
    async def _before_loop(self):
        # Don't fire the loop until the bot is connected.
        await self.bot.wait_until_ready()

    async def _sync(self):
        if not self.api_key:
            print("[presence] BOT_API_KEY missing — skip sync")
            return
        if not self.backend_url:
            print("[presence] BACKEND_URL missing — skip sync")
            return

        guild_ids = [str(g.id) for g in self.bot.guilds]
        url = f"{self.backend_url}/api/bot/presence"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    json={"guild_ids": guild_ids},
                    headers={"X-Bot-Token": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        print(f"[presence] sync failed: HTTP {resp.status} — {body[:200]}")
                    else:
                        # Quiet on success; uncomment for debugging
                        # print(f"[presence] synced {len(guild_ids)} guilds")
                        pass
        except Exception as e:
            print(f"[presence] sync error: {e}")

    async def _push_stats(self):
        """Push aggregate stats (guild count, user count, uptime baseline) to the
        backend so the public landing page can display them. Best-effort."""
        if not self.api_key or not self.backend_url:
            return

        guild_count = len(self.bot.guilds)
        # Sum guild member_count; guard against None values.
        user_count = sum((g.member_count or 0) for g in self.bot.guilds)
        url = f"{self.backend_url}/api/bot/stats"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    json={
                        "guild_count": guild_count,
                        "user_count": user_count,
                        "started_at": self.started_at or int(time.time())
                    },
                    headers={"X-Bot-Token": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        print(f"[presence] stats push failed: HTTP {resp.status} — {body[:200]}")
        except Exception as e:
            print(f"[presence] stats push error: {e}")


async def setup(bot):
    await bot.add_cog(Presence(bot))
