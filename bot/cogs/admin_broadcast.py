"""Owner-Broadcast cog — DMs a queued broadcast to every server owner.

The system owner enqueues a broadcast from the admin dashboard. This cog polls
the backend queue, claims the oldest pending broadcast (status=sending so a
restart / second instance can't double-send), DMs the message to each UNIQUE
guild owner, then reports done with the sent/total counts.

Backend contract (X-Bot-Token auth):
  GET /api/bot/broadcasts/due       → { broadcast: { id, message } | null }
  PUT /api/bot/broadcasts/{id}      body { status, sent_count?, total? }

Logging prefix: "[broadcast]".
"""

import asyncio

from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put

POLL_SECONDS = 30


class AdminBroadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll_loop(self):
        if not self.api_key or not self.backend_url:
            return
        try:
            data = await bot_get(self.backend_url, self.api_key, "/api/bot/broadcasts/due")
        except Exception as exc:
            print(f"[broadcast] poll error: {exc}")
            return
        bc = (data or {}).get("broadcast")
        if bc and bc.get("id"):
            await self._run(bc)

    @poll_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def _run(self, bc):
        bid = bc["id"]
        message = (bc.get("message") or "")[:2000]
        # Claim it immediately so a restart / second instance won't re-send.
        await bot_put(self.backend_url, self.api_key, f"/api/bot/broadcasts/{bid}", {"status": "sending"})

        owner_ids = {g.owner_id for g in self.bot.guilds if g.owner_id}
        total = len(owner_ids)
        sent = 0
        for oid in owner_ids:
            try:
                user = self.bot.get_user(oid) or await self.bot.fetch_user(oid)
                if user is not None:
                    await user.send(message)
                    sent += 1
            except Exception as exc:
                print(f"[broadcast] DM to {oid} failed: {exc}")
            await asyncio.sleep(1)  # gentle rate-limit between DMs

        await bot_put(
            self.backend_url, self.api_key, f"/api/bot/broadcasts/{bid}",
            {"status": "done", "sent_count": sent, "total": total},
        )
        print(f"[broadcast] {bid}: delivered {sent}/{total}")


async def setup(bot):
    await bot.add_cog(AdminBroadcast(bot))
