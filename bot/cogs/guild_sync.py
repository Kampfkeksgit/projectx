"""
Guild-sync cog — pushes the bot's per-guild channel + role lists to the backend.

The dashboard uses these (via `GET /api/guilds/:id/channels` and
`/api/guilds/:id/roles`) to populate channel/role-picker dropdowns instead of
making admins paste raw snowflakes into text fields.

Triggers:
  - on_ready                        → full sync of every guild (channels + roles)
  - on_guild_join                   → full sync of the new guild
  - on_guild_channel_create/update/delete  → re-sync the affected guild's channels
  - on_guild_role_create/update/delete     → re-sync the affected guild's roles
  - tasks.loop(minutes=15)          → safety-net full re-sync of every guild

All external calls are wrapped in try/except so a listener never crashes.
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_put


SYNC_INTERVAL_MINUTES = 15

# Discord ChannelType → backend enum. Anything not in this map is skipped
# (e.g. DMs, group DMs — they never appear on a guild anyway, but be defensive).
CHANNEL_TYPE_MAP = {
    discord.ChannelType.text: 'text',
    discord.ChannelType.voice: 'voice',
    discord.ChannelType.category: 'category',
    discord.ChannelType.news: 'announcement',
    discord.ChannelType.stage_voice: 'stage',
    discord.ChannelType.forum: 'forum',
    discord.ChannelType.public_thread: 'thread',
    discord.ChannelType.private_thread: 'thread',
    discord.ChannelType.news_thread: 'thread',
}


def _serialize_channel(channel):
    """Map a discord channel to the backend's expected shape, or None to skip."""
    mapped = CHANNEL_TYPE_MAP.get(getattr(channel, 'type', None))
    if mapped is None:
        return None
    name = getattr(channel, 'name', None)
    if not name:
        return None
    parent_id = getattr(channel, 'category_id', None)
    return {
        'id': str(channel.id),
        'name': name,
        'type': mapped,
        'parent_id': str(parent_id) if parent_id else None,
        'position': int(getattr(channel, 'position', 0) or 0),
    }


def _serialize_role(role):
    """Map a discord role to the backend's expected shape."""
    try:
        color_value = int(role.color.value) if role.color else 0
    except Exception:
        color_value = 0
    try:
        is_default = bool(role.is_default())
    except Exception:
        is_default = False
    return {
        'id': str(role.id),
        'name': role.name or '',
        'color': color_value,
        'position': int(getattr(role, 'position', 0) or 0),
        'managed': bool(getattr(role, 'managed', False)),
        'is_default': is_default,
    }


class GuildSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    # ---------- listeners ----------

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self._sync_all_guilds()
        except Exception as exc:
            print(f"[guild_sync] on_ready full sync failed: {exc}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            await self._sync_guild(guild)
        except Exception as exc:
            print(f"[guild_sync] on_guild_join sync failed for {guild.id}: {exc}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._safe_sync_channels(getattr(channel, 'guild', None))

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        await self._safe_sync_channels(getattr(after, 'guild', None))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self._safe_sync_channels(getattr(channel, 'guild', None))

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self._safe_sync_roles(getattr(role, 'guild', None))

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        await self._safe_sync_roles(getattr(after, 'guild', None))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self._safe_sync_roles(getattr(role, 'guild', None))

    @tasks.loop(minutes=SYNC_INTERVAL_MINUTES)
    async def sync_loop(self):
        try:
            await self._sync_all_guilds()
        except Exception as exc:
            print(f"[guild_sync] periodic sync failed: {exc}")

    @sync_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    # ---------- internal ----------

    def _enabled(self):
        if not self.api_key:
            print("[guild_sync] BOT_API_KEY missing — skip sync")
            return False
        if not self.backend_url:
            print("[guild_sync] BACKEND_URL missing — skip sync")
            return False
        return True

    async def _safe_sync_channels(self, guild):
        if guild is None:
            return
        try:
            await self._sync_channels(guild)
        except Exception as exc:
            print(f"[guild_sync] channel sync failed for {guild.id}: {exc}")

    async def _safe_sync_roles(self, guild):
        if guild is None:
            return
        try:
            await self._sync_roles(guild)
        except Exception as exc:
            print(f"[guild_sync] role sync failed for {guild.id}: {exc}")

    async def _sync_all_guilds(self):
        if not self._enabled():
            return
        for guild in list(self.bot.guilds):
            await self._sync_guild(guild)

    async def _sync_guild(self, guild):
        if not self._enabled():
            return
        await self._sync_channels(guild)
        await self._sync_roles(guild)

    def _guild_meta(self, guild):
        """Return name + icon URL so the backend can seed the guilds row if needed."""
        icon_url = ""
        try:
            if getattr(guild, "icon", None):
                icon_url = str(guild.icon.url)
        except Exception:
            icon_url = ""
        return {
            "guild_name": getattr(guild, "name", "") or "",
            "guild_icon_url": icon_url
        }

    async def _sync_channels(self, guild):
        if not self._enabled():
            return
        payload = []
        for ch in getattr(guild, 'channels', []) or []:
            item = _serialize_channel(ch)
            if item is not None:
                payload.append(item)
        path = f"/api/bot/guilds/{guild.id}/channels"
        body = {"channels": payload, **self._guild_meta(guild)}
        await bot_put(self.backend_url, self.api_key, path, body)

    async def _sync_roles(self, guild):
        if not self._enabled():
            return
        payload = [_serialize_role(r) for r in (getattr(guild, 'roles', []) or [])]
        path = f"/api/bot/guilds/{guild.id}/roles"
        body = {"roles": payload, **self._guild_meta(guild)}
        await bot_put(self.backend_url, self.api_key, path, body)


async def setup(bot):
    await bot.add_cog(GuildSync(bot))
