"""Custom-Commands cog: matches incoming messages against a per-guild list of
configured triggers and posts a templated response on the first hit.

Backend contract:
  GET /api/bot/guilds/:guild_id/custom-commands
    → { commands: [{ id, trigger, response, match_type, enabled }] }
  (only enabled commands are returned)

Match types:
  exact       → lowered == trigger
  contains    → trigger in lowered
  starts_with → lowered.startswith(trigger)

Triggers are matched against the lowercased+stripped message content, so the
trigger should already be stored in lowercase by the dashboard.

The cache is rebuilt:
  - on_ready
  - on_guild_join
  - every 5 minutes via tasks.loop
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get
from cogs.welcome_leave import resolve_placeholders


REFRESH_INTERVAL_MINUTES = 5


class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # guild_id (int) -> list[dict] of commands
        self.cache = {}
        self.refresh_loop.start()

    def cog_unload(self):
        try:
            self.refresh_loop.cancel()
        except Exception:
            pass

    # ---------- cache management ----------

    def _enabled(self):
        if not self.api_key:
            return False
        if not self.backend_url:
            return False
        return True

    async def _refresh_guild(self, guild):
        if not self._enabled() or guild is None:
            return
        path = f"/api/bot/guilds/{guild.id}/custom-commands"
        data = await bot_get(self.backend_url, self.api_key, path)
        if data is None:
            return
        commands_list = []
        for c in data.get("commands") or []:
            trigger = c.get("trigger")
            response = c.get("response")
            if not trigger or response is None:
                continue
            if not c.get("enabled", True):
                # Backend should only return enabled commands but be defensive.
                continue
            commands_list.append({
                "id": c.get("id"),
                "trigger": str(trigger).lower().strip(),
                "response": str(response),
                "match_type": (c.get("match_type") or "exact").lower(),
            })
        self.cache[guild.id] = commands_list

    async def _refresh_all(self):
        if not self._enabled():
            return
        for guild in list(self.bot.guilds):
            try:
                await self._refresh_guild(guild)
            except Exception as exc:
                print(f"[custom_commands] refresh failed for {guild.id}: {exc}")

    # ---------- listeners ----------

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self._refresh_all()
        except Exception as exc:
            print(f"[custom_commands] on_ready refresh failed: {exc}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            await self._refresh_guild(guild)
        except Exception as exc:
            print(f"[custom_commands] on_guild_join refresh failed for {guild.id}: {exc}")

    @tasks.loop(minutes=REFRESH_INTERVAL_MINUTES)
    async def refresh_loop(self):
        try:
            await self._refresh_all()
        except Exception as exc:
            print(f"[custom_commands] periodic refresh failed: {exc}")

    @refresh_loop.before_loop
    async def _before_refresh(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.guild is None:
                return
            author = message.author
            if author is None or author.bot:
                return
            if self.bot.user and author.id == self.bot.user.id:
                return

            guild_commands = self.cache.get(message.guild.id)
            if not guild_commands:
                return

            lowered = (message.content or "").lower().strip()
            if not lowered:
                return

            matched = None
            for cmd in guild_commands:
                trigger = cmd["trigger"]
                if not trigger:
                    continue
                mt = cmd["match_type"]
                if mt == "exact":
                    if lowered == trigger:
                        matched = cmd
                        break
                elif mt == "contains":
                    if trigger in lowered:
                        matched = cmd
                        break
                elif mt == "starts_with":
                    if lowered.startswith(trigger):
                        matched = cmd
                        break
                else:
                    # Unknown match_type — be defensive, treat as exact.
                    if lowered == trigger:
                        matched = cmd
                        break

            if matched is None:
                return

            # Reuse welcome_leave's placeholder resolver — same token semantics.
            try:
                resolved = resolve_placeholders(matched["response"], author, message.guild)
            except Exception as exc:
                print(f"[custom_commands] placeholder error in {message.guild.id}: {exc}")
                resolved = matched["response"]

            if not resolved:
                return

            try:
                await message.channel.send(resolved)
            except discord.Forbidden:
                print(f"[custom_commands] missing send perms in {message.guild.id}")
            except discord.HTTPException as exc:
                print(f"[custom_commands] HTTP error in {message.guild.id}: {exc}")
        except Exception as exc:
            print(f"[custom_commands] on_message fatal error: {exc}")


async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
