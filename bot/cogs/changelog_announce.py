"""Changelog announcement cog — posts newly published changelog entries to a
Discord channel.

The system owner writes release notes in the admin dashboard and sets an
announcement channel (a channel in the HQ/support server). This cog polls the
backend for published-but-not-yet-announced entries and posts each as an embed,
then marks it announced so it is never posted twice. Existing entries are
backfilled to announced=1 by migration v48, so only *new* publishes are sent.

Backend contract (X-Bot-Token auth):
  GET /api/bot/changelog/due            → { channel_id, entries: [{ id, version,
                                            title, body, entry_date }] }
  PUT /api/bot/changelog/{id}/announced → mark posted

Logging prefix: "[changelog]".
"""

import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put

POLL_SECONDS = 60
BRAND_COLOR = 0x5865F2


class ChangelogAnnounce(commands.Cog):
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
            data = await bot_get(self.backend_url, self.api_key, "/api/bot/changelog/due")
        except Exception as exc:
            print(f"[changelog] poll error: {exc}")
            return

        data = data or {}
        channel_id = data.get("channel_id")
        entries = data.get("entries") or []
        if not channel_id or not entries:
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
        except (TypeError, ValueError):
            print(f"[changelog] invalid channel id {channel_id!r}")
            return
        if channel is None:
            # Bot can't see the channel this cycle — retry later, don't mark posted.
            return

        for entry in entries:
            await self._announce(channel, entry)
            await asyncio.sleep(1)  # gentle pacing between posts

    @poll_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    def _build_embed(self, entry):
        title = (entry.get("title") or "Update")[:256]
        body = (entry.get("body") or "")[:4096]
        version = (entry.get("version") or "").strip()
        embed = discord.Embed(title=title, description=body or None, color=discord.Color(BRAND_COLOR))
        embed.set_author(name=f"📢 Changelog · {version}" if version else "📢 Changelog")
        entry_date = entry.get("entry_date")
        try:
            if entry_date:
                embed.timestamp = datetime.fromtimestamp(int(entry_date), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
        return embed

    async def _announce(self, channel, entry):
        eid = entry.get("id")
        if not eid:
            return
        try:
            await channel.send(embed=self._build_embed(entry))
        except discord.Forbidden:
            print(f"[changelog] no permission to post in {channel.id}")
            return  # don't mark announced → retry once perms are fixed
        except Exception as exc:
            print(f"[changelog] post failed for {eid}: {exc}")
            return
        try:
            await bot_put(self.backend_url, self.api_key, f"/api/bot/changelog/{eid}/announced", {})
            print(f"[changelog] announced {eid}")
        except Exception as exc:
            # Posted but couldn't mark → it may re-post next cycle. Log loudly.
            print(f"[changelog] posted {eid} but failed to mark announced: {exc}")


async def setup(bot):
    await bot.add_cog(ChangelogAnnounce(bot))
