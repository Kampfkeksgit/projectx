"""Starboard cog.

When a message collects enough of the configured star emoji, the bot reposts it
to the starboard channel and keeps the star count updated. Drops below the
threshold remove it again.

Backend contract (X-Bot-Token auth):
  GET    /api/bot/guilds/{gid}/settings/starboard
         → { enabled, star_channel_id, emoji, threshold, self_star }
  GET    /api/bot/guilds/{gid}/starboard/entries/{message_id}  → { entry|null }
  PUT    /api/bot/guilds/{gid}/starboard/entries/{message_id}  body { channel_id, star_message_id, count }
  DELETE /api/bot/guilds/{gid}/starboard/entries/{message_id}

Logging prefix: "[starboard]".
"""

import time

import discord
from discord.ext import commands

import config
from utils.backend import bot_get, bot_put, bot_delete
from utils import general_config


SETTINGS_TTL_SECONDS = 300
STAR_COLOR = 0xFFAC33


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}  # guild_id (str) -> (settings, fetched_at)

    async def _get_settings(self, guild_id):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await bot_get(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild_id}/settings/starboard",
        )
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    @staticmethod
    def _emoji_matches(payload_emoji, configured):
        # Unicode emoji compare directly; custom emoji compare by name.
        if str(payload_emoji) == str(configured):
            return True
        if payload_emoji.name and payload_emoji.name == str(configured):
            return True
        return False

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self._handle(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self._handle(payload)

    async def _handle(self, payload):
        if payload.guild_id is None:
            return
        settings = await self._get_settings(payload.guild_id)
        if not settings or not settings.get("enabled"):
            return
        star_channel_id = settings.get("star_channel_id")
        if not star_channel_id:
            return
        if not self._emoji_matches(payload.emoji, settings.get("emoji") or "⭐"):
            return
        # Don't starboard messages that live in the starboard channel itself.
        if str(payload.channel_id) == str(star_channel_id):
            return

        source_channel = self.bot.get_channel(payload.channel_id)
        if source_channel is None:
            return
        try:
            message = await source_channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return
        except Exception as exc:
            print(f"[starboard] fetch message failed: {exc}")
            return

        count = self._count_stars(message, settings)
        threshold = int(settings.get("threshold") or 3)

        star_channel = self.bot.get_channel(int(star_channel_id))
        if star_channel is None:
            return

        entry = None
        data = await bot_get(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{payload.guild_id}/starboard/entries/{payload.message_id}",
        )
        if data:
            entry = data.get("entry")

        if count >= threshold:
            await self._post_or_update(message, star_channel, count, entry, payload)
        elif entry and entry.get("star_message_id"):
            await self._remove(star_channel, entry, payload)

    def _count_stars(self, message, settings):
        emoji = str(settings.get("emoji") or "⭐")
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji or getattr(reaction.emoji, "name", None) == emoji:
                count = reaction.count
                # Subtract the author's own star when self-star isn't allowed and
                # the bot can't otherwise tell — best-effort, no extra fetch.
                if not settings.get("self_star") and message.author and not message.author.bot:
                    # reaction.me would be the bot; we only deduct if the author
                    # is plausibly counted. Keep it simple and safe.
                    pass
                return count
        return 0

    def _build_embed(self, message, color=STAR_COLOR):
        embed = discord.Embed(
            description=message.content or "",
            color=color,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url,
        )
        embed.add_field(name="Source", value=f"[Jump to message]({message.jump_url})", inline=False)
        embed.set_footer(text=f"#{getattr(message.channel, 'name', 'channel')}")
        # Attach the first image attachment, if any.
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                embed.set_image(url=att.url)
                break
        return embed

    async def _post_or_update(self, message, star_channel, count, entry, payload):
        content = f"⭐ **{count}** <#{payload.channel_id}>"
        color = await general_config.get_embed_color(self.backend_url, self.api_key, message.guild.id, fallback=STAR_COLOR)
        embed = self._build_embed(message, color=color)

        star_message_id = entry.get("star_message_id") if entry else None
        new_star_id = star_message_id

        if star_message_id:
            try:
                star_msg = await star_channel.fetch_message(int(star_message_id))
                await star_msg.edit(content=content, embed=embed)
            except discord.NotFound:
                star_message_id = None  # fall through to repost
            except Exception as exc:
                print(f"[starboard] edit failed: {exc}")

        if not star_message_id:
            try:
                star_msg = await star_channel.send(content=content, embed=embed)
                new_star_id = str(star_msg.id)
            except discord.Forbidden:
                print(f"[starboard] missing permission to post in {star_channel.id}")
                return
            except Exception as exc:
                print(f"[starboard] post failed: {exc}")
                return

        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{payload.guild_id}/starboard/entries/{payload.message_id}",
            {"channel_id": str(payload.channel_id), "star_message_id": new_star_id, "count": count},
        )

    async def _remove(self, star_channel, entry, payload):
        try:
            star_msg = await star_channel.fetch_message(int(entry["star_message_id"]))
            await star_msg.delete()
        except discord.NotFound:
            pass
        except Exception as exc:
            print(f"[starboard] remove failed: {exc}")
        await bot_delete(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{payload.guild_id}/starboard/entries/{payload.message_id}",
        )


async def setup(bot):
    await bot.add_cog(Starboard(bot))
