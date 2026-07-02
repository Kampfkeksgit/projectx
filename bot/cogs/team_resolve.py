"""Team-resolve cog.

The owner can add a team member (for the public /team page) by just a Discord id.
The backend can't ask the bot synchronously, so this cog polls for unresolved
members, fetches the Discord user by id (`fetch_user`) and writes the username +
display name + avatar back. It fills name/avatar only when the admin left them
empty (the backend guards that), and sets `discord_username` as the resolved
marker so each member is resolved once.

Backend contract (X-Bot-Token auth):
  GET /api/bot/team/unresolved        → { members: [{ id, discord_id }] }
  PUT /api/bot/team/{id}/resolved     body { username, name, avatar_url }

Logging prefix: "[team]".
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put


RESOLVE_INTERVAL_MINUTES = 5


class TeamResolve(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.resolve_loop.start()

    def cog_unload(self):
        self.resolve_loop.cancel()

    @tasks.loop(minutes=RESOLVE_INTERVAL_MINUTES)
    async def resolve_loop(self):
        await self._resolve()

    @resolve_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _resolve(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/team/unresolved")
        for m in (data or {}).get("members", []) or []:
            mid = m.get("id")
            did = str(m.get("discord_id") or "")
            if not mid or not did.isdigit():
                continue
            username, name, avatar = "unknown", "", ""
            try:
                user = await self.bot.fetch_user(int(did))
                username = user.name
                name = getattr(user, "global_name", None) or user.name
                avatar = str(user.display_avatar.url)
            except discord.NotFound:
                # Invalid id → still mark resolved (username stays "unknown") so we
                # don't retry it forever; the admin sees the name wasn't filled.
                pass
            except Exception as exc:
                print(f"[team] resolve failed for {did}: {exc}")
                continue  # transient (rate limit etc.) → retry next loop
            await bot_put(
                self.backend_url, self.api_key,
                f"/api/bot/team/{mid}/resolved",
                {"username": username, "name": name, "avatar_url": avatar},
            )


async def setup(bot):
    await bot.add_cog(TeamResolve(bot))
