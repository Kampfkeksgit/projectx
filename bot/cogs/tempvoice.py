"""Temp-Voice (Join-to-Create) cog.

When a member joins the configured "hub" voice channel, the bot creates a fresh
temporary voice channel (in the configured category), moves the member into it,
and deletes the channel automatically once it becomes empty.

Backend contract (X-Bot-Token auth):
  GET    /api/bot/guilds/{gid}/settings/tempvoice
         → { enabled, hub_channel_id, category_id, name_template, user_limit }
  POST   /api/bot/guilds/{gid}/tempvoice/channels   body { channel_id, owner_id }
  DELETE /api/bot/guilds/{gid}/tempvoice/channels/{channel_id}
  GET    /api/bot/tempvoice/channels                → { channels: [...] }  (startup cleanup)

Requires permissions: Manage Channels + Move Members. Logging prefix: "[tempvoice]".
"""

import time

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post, bot_delete


SETTINGS_TTL_SECONDS = 300


class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # guild_id (str) -> (settings dict, fetched_at)
        self._settings_cache = {}
        # channel ids (int) the bot manages and should clean up when empty.
        self._temp_channels = set()

    async def _get_settings(self, guild_id):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "tempvoice")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    @commands.Cog.listener()
    async def on_ready(self):
        # Load tracked channels and prune any that are gone or already empty.
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/tempvoice/channels")
        if not data:
            return
        for row in (data.get("channels") or []):
            try:
                cid = int(row.get("channel_id"))
            except (TypeError, ValueError):
                continue
            channel = self.bot.get_channel(cid)
            if channel is None:
                await self._untrack(row.get("guild_id"), cid)
            elif len(channel.members) == 0:
                await self._delete_channel(channel)
            else:
                self._temp_channels.add(cid)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild

        # Joined (or moved into) a channel → maybe spawn a temp channel.
        if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
            settings = await self._get_settings(guild.id)
            if settings and settings.get("enabled") and after.channel.id not in self._temp_channels:
                hub_id = settings.get("hub_channel_id")
                if hub_id and str(after.channel.id) == str(hub_id):
                    await self._spawn(member, settings)

        # Left a channel → if it's a now-empty temp channel, delete it.
        if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
            if before.channel.id in self._temp_channels and len(before.channel.members) == 0:
                await self._delete_channel(before.channel)

    async def _spawn(self, member, settings):
        guild = member.guild
        name = (settings.get("name_template") or "🔊 {user}").replace("{user}", member.display_name)[:100]

        category = None
        cat_id = settings.get("category_id")
        if cat_id:
            ch = guild.get_channel(int(cat_id))
            if isinstance(ch, discord.CategoryChannel):
                category = ch
        # Fall back to the hub's own category if none configured.
        if category is None and member.voice and member.voice.channel:
            category = member.voice.channel.category

        user_limit = settings.get("user_limit") or 0

        try:
            channel = await guild.create_voice_channel(
                name,
                category=category,
                user_limit=user_limit if user_limit else None,
                reason="Temp-Voice: join-to-create",
            )
        except discord.Forbidden:
            print(f"[tempvoice] missing Manage Channels permission in {guild.id}")
            return
        except Exception as exc:
            print(f"[tempvoice] create channel failed in {guild.id}: {exc}")
            return

        self._temp_channels.add(channel.id)
        await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild.id}/tempvoice/channels",
            {"channel_id": str(channel.id), "owner_id": str(member.id)},
        )

        try:
            await member.move_to(channel, reason="Temp-Voice")
        except discord.Forbidden:
            print(f"[tempvoice] missing Move Members permission in {guild.id}")
        except Exception as exc:
            print(f"[tempvoice] move member failed in {guild.id}: {exc}")

    async def _delete_channel(self, channel):
        self._temp_channels.discard(channel.id)
        guild_id = channel.guild.id
        try:
            await channel.delete(reason="Temp-Voice: empty")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print(f"[tempvoice] missing permission to delete channel in {guild_id}")
        except Exception as exc:
            print(f"[tempvoice] delete channel failed in {guild_id}: {exc}")
        await self._untrack(guild_id, channel.id)

    async def _untrack(self, guild_id, channel_id):
        self._temp_channels.discard(int(channel_id))
        await bot_delete(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild_id}/tempvoice/channels/{channel_id}",
        )


async def setup(bot):
    await bot.add_cog(TempVoice(bot))
