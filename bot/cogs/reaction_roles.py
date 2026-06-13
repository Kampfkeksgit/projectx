"""Reaction-Roles cog: assigns/removes roles when users react to configured messages.

Backend contract:
  GET /api/bot/guilds/:guild_id/reaction-roles
    → { messages: [
          { id, channel_id, message_id, name, exclusive,
            mappings: [{ emoji, role_id }] }
        ] }

The `emoji` value in a mapping can be either:
  * a unicode emoji (e.g. "🎉") — matched against payload.emoji.name
  * a custom emoji string "<:name:id>" or "<a:name:id>" — only the numeric id
    is significant. We extract it via regex and match against str(payload.emoji.id).

Cache shape (in-memory):
  self.cache[(guild_id:int, message_id:int)] = {
      "exclusive": bool,
      "mappings":  { emoji_key:str -> role_id:int },
  }

The cache is rebuilt:
  - on_ready
  - on_guild_join
  - every 10 minutes via tasks.loop
"""

import re

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get


REFRESH_INTERVAL_MINUTES = 10

# Matches "<:name:1234567890>" or "<a:name:1234567890>" and captures the id.
CUSTOM_EMOJI_RE = re.compile(r"^<a?:[^:]+:(\d+)>$")


def _emoji_key_from_config(raw):
    """Normalize the backend's stored `emoji` field to a cache key.

    Returns None if the value is empty/garbage.
    For custom emojis we use the numeric id (as a string). For unicode emojis
    we use the literal string.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = CUSTOM_EMOJI_RE.match(s)
    if m:
        return m.group(1)
    return s


def _emoji_key_from_payload(payload):
    """Build the lookup key for a raw reaction event.

    discord.py populates payload.emoji.id for custom emojis (and .name is the
    emoji name) and payload.emoji.id=None for unicode (with .name = the actual
    unicode character).
    """
    try:
        emoji = payload.emoji
    except AttributeError:
        return None
    if emoji is None:
        return None
    if getattr(emoji, "id", None):
        return str(emoji.id)
    return getattr(emoji, "name", None)


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # Keyed by (guild_id, message_id)
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
        """Replace the cache entries for a single guild."""
        if not self._enabled() or guild is None:
            return
        path = f"/api/bot/guilds/{guild.id}/reaction-roles"
        data = await bot_get(self.backend_url, self.api_key, path)
        if data is None:
            return

        # Drop any existing cache entries for this guild — we're about to
        # rebuild them from scratch.
        for key in list(self.cache.keys()):
            if key[0] == guild.id:
                del self.cache[key]

        messages = data.get("messages") or []
        for m in messages:
            try:
                message_id = int(m.get("message_id"))
            except (TypeError, ValueError):
                continue
            mappings = {}
            for entry in m.get("mappings") or []:
                key = _emoji_key_from_config(entry.get("emoji"))
                role_id_raw = entry.get("role_id")
                if not key or role_id_raw is None:
                    continue
                try:
                    mappings[key] = int(role_id_raw)
                except (TypeError, ValueError):
                    continue
            self.cache[(guild.id, message_id)] = {
                "exclusive": bool(m.get("exclusive")),
                "mappings": mappings,
            }

    async def _refresh_all(self):
        if not self._enabled():
            return
        for guild in list(self.bot.guilds):
            try:
                await self._refresh_guild(guild)
            except Exception as exc:
                print(f"[reaction_roles] refresh failed for {guild.id}: {exc}")

    # ---------- listeners ----------

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self._refresh_all()
        except Exception as exc:
            print(f"[reaction_roles] on_ready refresh failed: {exc}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            await self._refresh_guild(guild)
        except Exception as exc:
            print(f"[reaction_roles] on_guild_join refresh failed for {guild.id}: {exc}")

    @tasks.loop(minutes=REFRESH_INTERVAL_MINUTES)
    async def refresh_loop(self):
        try:
            await self._refresh_all()
        except Exception as exc:
            print(f"[reaction_roles] periodic refresh failed: {exc}")

    @refresh_loop.before_loop
    async def _before_refresh(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            if payload.guild_id is None:
                return
            if self.bot.user and payload.user_id == self.bot.user.id:
                return

            entry = self.cache.get((payload.guild_id, payload.message_id))
            if not entry:
                return

            key = _emoji_key_from_payload(payload)
            if not key:
                return

            mappings = entry.get("mappings") or {}
            role_id = mappings.get(key)
            if role_id is None:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if guild is None:
                return

            role = guild.get_role(role_id)
            if role is None:
                return

            member = payload.member or guild.get_member(payload.user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(payload.user_id)
                except Exception as exc:
                    print(f"[reaction_roles] fetch_member failed: {exc}")
                    return
            if member is None or member.bot:
                return

            try:
                await member.add_roles(role, reason="Reaction-Roles")
            except discord.Forbidden:
                print(f"[reaction_roles] missing permissions to add role {role.id} in {guild.id}")
                return
            except discord.HTTPException as exc:
                print(f"[reaction_roles] HTTP error adding role in {guild.id}: {exc}")
                return

            # If the mapping set is exclusive, strip every OTHER mapped role
            # from this member so they only ever hold one of the set.
            if entry.get("exclusive"):
                other_role_ids = {rid for k, rid in mappings.items() if k != key}
                roles_to_remove = []
                for rid in other_role_ids:
                    r = guild.get_role(rid)
                    if r is not None and r in member.roles:
                        roles_to_remove.append(r)
                if roles_to_remove:
                    try:
                        await member.remove_roles(
                            *roles_to_remove, reason="Reaction-Roles exclusive"
                        )
                    except discord.Forbidden:
                        print(
                            f"[reaction_roles] missing perms to enforce exclusivity in {guild.id}"
                        )
                    except discord.HTTPException as exc:
                        print(f"[reaction_roles] HTTP error enforcing exclusivity: {exc}")
        except Exception as exc:
            print(f"[reaction_roles] on_raw_reaction_add error: {exc}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        try:
            if payload.guild_id is None:
                return
            if self.bot.user and payload.user_id == self.bot.user.id:
                return

            entry = self.cache.get((payload.guild_id, payload.message_id))
            if not entry:
                return

            # In exclusive mode the role might have just been swapped via a
            # different reaction — don't tear it back off again.
            if entry.get("exclusive"):
                return

            key = _emoji_key_from_payload(payload)
            if not key:
                return

            role_id = (entry.get("mappings") or {}).get(key)
            if role_id is None:
                return

            guild = self.bot.get_guild(payload.guild_id)
            if guild is None:
                return

            role = guild.get_role(role_id)
            if role is None:
                return

            member = guild.get_member(payload.user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(payload.user_id)
                except Exception as exc:
                    print(f"[reaction_roles] fetch_member (remove) failed: {exc}")
                    return
            if member is None or member.bot:
                return

            try:
                await member.remove_roles(role, reason="Reaction-Roles remove")
            except discord.Forbidden:
                print(f"[reaction_roles] missing permissions to remove role {role.id} in {guild.id}")
            except discord.HTTPException as exc:
                print(f"[reaction_roles] HTTP error removing role in {guild.id}: {exc}")
        except Exception as exc:
            print(f"[reaction_roles] on_raw_reaction_remove error: {exc}")


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
