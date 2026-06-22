"""Server Backup & Restore cog.

Polls the backend for due backup jobs and either captures a full snapshot of a
guild (roles + channels + overwrites + server style) or restores one onto a
live guild.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/backup/jobs/due
       → { jobs: [ { id, guild_id, type, status, backup_id, mode, message, data? } ] }
       For type=='restore', `data` is the snapshot object. For type=='snapshot',
       no data is sent.
  PUT  /api/bot/backup/jobs/{job_id}   body { status, backup_id?, message? }
       status ∈ pending|running|done|failed
  POST /api/bot/guilds/{guild_id}/backups   body { name, guild_name, guild_icon_url, data }
       → { id }

Snapshot data shape (produced by snapshot jobs, consumed by restore jobs — kept
symmetric):
  {
    "server":   { name, icon_url, verification_level },
    "roles":    [ { id, name, color, position, hoist, mentionable,
                    permissions(str int), managed, is_default } ],
    "channels": [ { id, name, type, parent_id, position, topic, nsfw, slowmode,
                    bitrate, user_limit,
                    overwrites: [ { target_id, target_type, allow(str int), deny(str int) } ] } ]
  }

GOTCHAS (see inline comments too):
  - The bot can only manage roles/channels strictly BELOW its own top role.
  - Channel type is immutable: mirror never changes a type, it only creates via
    the missing-create path (and deletes channels absent from the snapshot).
  - Overwrite role-ids MUST be remapped via role_map after role recreation.
  - Mirror deletions ONLY for channels absent from the snapshot — never delete a
    channel that exists in the snapshot.
  - Discord rate-limits bulk channel creation → the asyncio.sleep() calls pace it.

Logging prefix: "[backup]".
"""

import asyncio

import aiohttp
import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put, bot_post


POLL_SECONDS = 20

# Discord ChannelType → snapshot type string. Threads/DMs etc. are skipped.
_CHANNEL_TYPE_TO_STR = {
    discord.ChannelType.category: "category",
    discord.ChannelType.text: "text",
    discord.ChannelType.voice: "voice",
    discord.ChannelType.news: "announcement",
    discord.ChannelType.stage_voice: "stage",
    discord.ChannelType.forum: "forum",
}


def _safe_msg(text):
    """Truncate a status message to a backend-friendly length."""
    return (text or "")[:1800]


class ServerBackup(commands.Cog):
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

    # ---------- poll loop ----------

    async def _run(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/backup/jobs/due")
        if not data:
            return
        for job in (data.get("jobs") or []):
            # One bad job must never crash the loop.
            try:
                await self._handle_job(job)
            except Exception as exc:
                print(f"[backup] job {job.get('id')} crashed: {exc}")
                await self._mark(job, "failed", message=str(exc)[:1500])

    async def _handle_job(self, job):
        job_id = job.get("id")
        guild = self.bot.get_guild(int(job["guild_id"]))
        if guild is None:
            await self._mark(job, "failed", message="Bot not in guild")
            return

        # Immediately claim the job so it isn't picked up twice.
        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/backup/jobs/{job_id}", {"status": "running"},
        )

        jtype = job.get("type")
        try:
            if jtype == "snapshot":
                backup_id, message = await self._do_snapshot(guild)
                await self._mark(job, "done", backup_id=backup_id, message=message)
            elif jtype == "restore":
                message = await self._do_restore(guild, job)
                await self._mark(job, "done", message=message)
            else:
                await self._mark(job, "failed", message=f"Unknown job type: {jtype}")
        except Exception as exc:
            await self._mark(job, "failed", message=str(exc)[:1500])

    async def _mark(self, job, status, backup_id=None, message=None):
        body = {"status": status}
        if backup_id is not None:
            body["backup_id"] = backup_id
        if message is not None:
            body["message"] = _safe_msg(message)
        try:
            await bot_put(
                self.backend_url, self.api_key,
                f"/api/bot/backup/jobs/{job.get('id')}", body,
            )
        except Exception as exc:
            print(f"[backup] failed to mark job {job.get('id')} as {status}: {exc}")

    # ---------- snapshot ----------

    async def _do_snapshot(self, guild):
        roles = [self._serialize_role(r) for r in guild.roles]

        channels = []
        for ch in guild.channels:
            item = self._serialize_channel(ch)
            if item is not None:
                channels.append(item)

        icon_url = None
        try:
            if guild.icon:
                icon_url = str(guild.icon.url)
        except Exception:
            icon_url = None

        try:
            verification_level = int(guild.verification_level.value)
        except Exception:
            verification_level = 0

        data = {
            "server": {
                "name": guild.name,
                "icon_url": icon_url,
                "verification_level": verification_level,
            },
            "roles": roles,
            "channels": channels,
        }

        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild.id}/backups",
            {
                "name": None,  # let the backend auto-name
                "guild_name": guild.name,
                "guild_icon_url": icon_url,
                "data": data,
            },
        )
        backup_id = result.get("id") if isinstance(result, dict) else None
        message = f"Snapshot saved: {len(channels)} channels, {len(roles)} roles"
        return backup_id, message

    def _serialize_role(self, role):
        try:
            color = int(role.color.value)
        except Exception:
            color = 0
        try:
            perms = str(role.permissions.value)
        except Exception:
            perms = "0"
        try:
            is_default = bool(role.is_default())
        except Exception:
            is_default = False
        return {
            "id": str(role.id),
            "name": role.name or "",
            "color": color,
            "position": int(getattr(role, "position", 0) or 0),
            "hoist": bool(getattr(role, "hoist", False)),
            "mentionable": bool(getattr(role, "mentionable", False)),
            "permissions": perms,
            "managed": bool(getattr(role, "managed", False)),
            "is_default": is_default,
        }

    def _serialize_channel(self, channel):
        ctype = _CHANNEL_TYPE_TO_STR.get(getattr(channel, "type", None))
        if ctype is None:
            return None  # threads/DMs etc. — skip

        parent_id = getattr(channel, "category_id", None)

        # topic only exists on text/news/forum channels.
        topic = None
        if ctype in ("text", "announcement", "forum"):
            topic = getattr(channel, "topic", None)

        # bitrate / user_limit only on voice/stage channels.
        bitrate = None
        user_limit = None
        if ctype in ("voice", "stage"):
            bitrate = getattr(channel, "bitrate", None)
            user_limit = getattr(channel, "user_limit", None)

        overwrites = []
        try:
            for target, overwrite in channel.overwrites.items():
                try:
                    allow, deny = overwrite.pair()
                    target_type = "role" if isinstance(target, discord.Role) else "member"
                    overwrites.append({
                        "target_id": str(target.id),
                        "target_type": target_type,
                        "allow": str(allow.value),
                        "deny": str(deny.value),
                    })
                except Exception:
                    continue  # one bad overwrite never drops the channel
        except Exception:
            overwrites = []

        return {
            "id": str(channel.id),
            "name": getattr(channel, "name", "") or "",
            "type": ctype,
            "parent_id": str(parent_id) if parent_id else None,
            "position": int(getattr(channel, "position", 0) or 0),
            "topic": topic,
            "nsfw": bool(getattr(channel, "nsfw", False)),
            "slowmode": int(getattr(channel, "slowmode_delay", 0) or 0),
            "bitrate": int(bitrate) if bitrate is not None else None,
            "user_limit": int(user_limit) if user_limit is not None else None,
            "overwrites": overwrites,
        }

    # ---------- restore ----------

    async def _do_restore(self, guild, job):
        data = job.get("data")
        if not data or not isinstance(data, dict):
            raise Exception("Snapshot data missing")

        mode = job.get("mode") or "missing"
        notes = []

        # 1) Roles → build old_id -> live discord.Role map.
        role_map = await self._restore_roles(guild, data.get("roles") or [], notes)

        # 2) Categories first (so channels can attach), then non-category channels.
        await self._restore_channels(guild, data.get("channels") or [], role_map, mode, notes)

        # 3) Server style (name + icon).
        await self._restore_server_style(guild, data.get("server") or {}, notes)

        if not notes:
            notes.append("Restore complete (no changes needed).")
        return _safe_msg(" | ".join(notes))

    async def _restore_roles(self, guild, snapshot_roles, notes):
        """Returns old_role_id(str) -> discord.Role. Creates missing roles below
        the bot's top role; maps existing ones by exact name."""
        role_map = {}
        my_top = guild.me.top_role.position

        # Existing live roles by name (non-managed, usable as targets).
        live_by_name = {}
        for r in guild.roles:
            if not r.managed and not r.is_default():
                live_by_name.setdefault(r.name, r)

        created = 0
        for sr in snapshot_roles:
            old_id = str(sr.get("id"))
            if sr.get("is_default"):
                # @everyone — map its old id to the live default role.
                role_map[old_id] = guild.default_role
                continue

            if sr.get("managed"):
                # Managed (integration/bot) roles can't be created — skip mapping.
                existing = live_by_name.get(sr.get("name"))
                if existing is not None:
                    role_map[old_id] = existing
                else:
                    notes.append(f"Skipped managed role '{sr.get('name')}' (cannot recreate)")
                continue

            existing = live_by_name.get(sr.get("name"))
            if existing is not None:
                role_map[old_id] = existing
                continue

            # The bot can only manage roles strictly below its own top role.
            if int(sr.get("position", 0) or 0) >= my_top:
                notes.append(f"Skipped role '{sr.get('name')}' (above bot's top role)")
                continue

            try:
                perms = discord.Permissions(int(sr.get("permissions", 0) or 0))
            except Exception:
                perms = discord.Permissions.none()
            try:
                colour = discord.Colour(int(sr.get("color", 0) or 0))
            except Exception:
                colour = discord.Colour.default()

            try:
                new_role = await guild.create_role(
                    name=sr.get("name") or "role",
                    colour=colour,
                    permissions=perms,
                    hoist=bool(sr.get("hoist", False)),
                    mentionable=bool(sr.get("mentionable", False)),
                    reason="Backup restore",
                )
                role_map[old_id] = new_role
                created += 1
                await asyncio.sleep(0.3)  # pace role creation (rate limits)
            except discord.Forbidden:
                notes.append(f"No permission to create role '{sr.get('name')}'")
            except Exception as exc:
                notes.append(f"Role '{sr.get('name')}' failed: {str(exc)[:80]}")

        if created:
            notes.append(f"Created {created} role(s)")
        return role_map

    def _build_overwrites(self, guild, snapshot_overwrites, role_map):
        """Build a {target_obj: PermissionOverwrite} dict from snapshot overwrites.
        Role targets are remapped via role_map; members resolved live. Unresolved
        targets are skipped."""
        result = {}
        for ow in (snapshot_overwrites or []):
            try:
                old_id = str(ow.get("target_id"))
                if ow.get("target_type") == "role":
                    target = role_map.get(old_id)  # remapped after recreation
                else:
                    target = guild.get_member(int(old_id))
                if target is None:
                    continue  # unmapped role / member not present → skip
                allow = discord.Permissions(int(ow.get("allow", 0) or 0))
                deny = discord.Permissions(int(ow.get("deny", 0) or 0))
                result[target] = discord.PermissionOverwrite.from_pair(allow, deny)
            except Exception:
                continue
        return result

    async def _restore_channels(self, guild, snapshot_channels, role_map, mode, notes):
        categories = [c for c in snapshot_channels if c.get("type") == "category"]
        non_categories = [c for c in snapshot_channels if c.get("type") != "category"]
        categories.sort(key=lambda c: int(c.get("position", 0) or 0))
        non_categories.sort(key=lambda c: int(c.get("position", 0) or 0))

        # Existing live channels keyed by (name, type) for "missing"/"mirror" matching.
        live_by_name_type = {}
        for ch in guild.channels:
            ctype = _CHANNEL_TYPE_TO_STR.get(getattr(ch, "type", None))
            if ctype is None:
                continue
            live_by_name_type[(ch.name, ctype)] = ch

        # Track snapshot keys so mirror knows which live channels to keep.
        snapshot_keys = set()
        # old category id -> live category object (so children attach correctly).
        cat_map = {}

        created = 0

        # --- categories ---
        for c in categories:
            key = (c.get("name"), "category")
            snapshot_keys.add(key)
            existing = live_by_name_type.get(key)
            if existing is not None:
                cat_map[str(c.get("id"))] = existing
                if mode == "mirror":
                    await self._maybe_edit_channel(existing, c, None, notes)
                continue
            # create category
            try:
                overwrites = self._build_overwrites(guild, c.get("overwrites"), role_map)
                new_cat = await guild.create_category(
                    c.get("name") or "category",
                    overwrites=overwrites,
                    position=int(c.get("position", 0) or 0),
                    reason="Backup restore",
                )
                cat_map[str(c.get("id"))] = new_cat
                created += 1
                await asyncio.sleep(0.5)  # pace bulk channel creation (rate limits)
            except discord.Forbidden:
                notes.append(f"No permission to create category '{c.get('name')}'")
            except Exception as exc:
                notes.append(f"Category '{c.get('name')}' failed: {str(exc)[:80]}")

        # --- non-category channels ---
        for c in non_categories:
            ctype = c.get("type")
            key = (c.get("name"), ctype)
            snapshot_keys.add(key)
            parent = cat_map.get(str(c.get("parent_id"))) if c.get("parent_id") else None

            existing = live_by_name_type.get(key)
            if existing is not None:
                if mode == "mirror":
                    await self._maybe_edit_channel(existing, c, parent, notes)
                continue

            try:
                overwrites = self._build_overwrites(guild, c.get("overwrites"), role_map)
                await self._create_channel(guild, c, parent, overwrites, notes)
                created += 1
                await asyncio.sleep(0.5)  # pace bulk channel creation (rate limits)
            except discord.Forbidden:
                notes.append(f"No permission to create channel '{c.get('name')}'")
            except Exception as exc:
                notes.append(f"Channel '{c.get('name')}' failed: {str(exc)[:80]}")

        if created:
            notes.append(f"Created {created} channel(s)/category(ies)")

        # --- mirror: delete live channels NOT in the snapshot ---
        if mode == "mirror":
            deleted = 0
            for (name, ctype), ch in list(live_by_name_type.items()):
                if (name, ctype) in snapshot_keys:
                    continue  # NEVER delete a channel that exists in the snapshot
                try:
                    await ch.delete(reason="Backup mirror restore")
                    deleted += 1
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    notes.append(f"Could not delete '{name}': {str(exc)[:60]}")
            if deleted:
                notes.append(f"Mirror removed {deleted} channel(s) not in snapshot")

    async def _create_channel(self, guild, c, parent, overwrites, notes):
        """Create a single channel of the snapshot's type. Channel type is
        immutable, so we create the exact type here."""
        ctype = c.get("type")
        name = c.get("name") or "channel"

        if ctype in ("text", "announcement"):
            await guild.create_text_channel(
                name,
                category=parent,
                topic=c.get("topic") or None,
                nsfw=bool(c.get("nsfw", False)),
                slowmode_delay=int(c.get("slowmode", 0) or 0),
                overwrites=overwrites,
                reason="Backup restore",
            )
            if ctype == "announcement":
                # We create a plain text channel; can't always convert to news.
                notes.append(f"'{name}' created as text (announcement type best-effort)")
        elif ctype == "voice":
            await guild.create_voice_channel(
                name,
                category=parent,
                bitrate=int(c.get("bitrate")) if c.get("bitrate") else None,
                user_limit=int(c.get("user_limit")) if c.get("user_limit") else None,
                overwrites=overwrites,
                reason="Backup restore",
            )
        elif ctype == "stage":
            # Stage channels may not be supported on every guild — best effort.
            try:
                await guild.create_stage_channel(
                    name, category=parent, overwrites=overwrites, reason="Backup restore",
                )
            except Exception as exc:
                notes.append(f"Stage channel '{name}' not restored: {str(exc)[:60]}")
        elif ctype == "forum":
            try:
                await guild.create_forum(
                    name, category=parent, overwrites=overwrites, reason="Backup restore",
                )
            except Exception as exc:
                notes.append(f"Forum channel '{name}' not restored: {str(exc)[:60]}")
        else:
            notes.append(f"Unknown channel type '{ctype}' for '{name}' — skipped")

    async def _maybe_edit_channel(self, channel, c, parent, notes):
        """Mirror best-effort: align an existing channel's name/topic/position/parent
        to the snapshot. Channel TYPE is never changed (immutable)."""
        kwargs = {}
        if getattr(channel, "name", None) != c.get("name"):
            kwargs["name"] = c.get("name")
        snap_topic = c.get("topic")
        if c.get("type") in ("text", "announcement", "forum") and getattr(channel, "topic", None) != snap_topic:
            kwargs["topic"] = snap_topic or None
        snap_pos = int(c.get("position", 0) or 0)
        if int(getattr(channel, "position", 0) or 0) != snap_pos:
            kwargs["position"] = snap_pos
        # Only adjust parent for non-categories.
        if c.get("type") != "category" and parent is not None and getattr(channel, "category_id", None) != parent.id:
            kwargs["category"] = parent

        if not kwargs:
            return
        try:
            await channel.edit(reason="Backup mirror restore", **kwargs)
            await asyncio.sleep(0.3)
        except Exception as exc:
            notes.append(f"Could not edit '{c.get('name')}': {str(exc)[:60]}")

    async def _restore_server_style(self, guild, server, notes):
        if not guild.me.guild_permissions.manage_guild:
            notes.append("Server style not restored (missing Manage Server permission)")
            return

        # Name.
        new_name = server.get("name")
        if new_name and new_name != guild.name:
            try:
                await guild.edit(name=new_name, reason="Backup restore")
            except Exception as exc:
                notes.append(f"Could not set server name: {str(exc)[:60]}")

        # Icon — optional, best effort (fetch bytes then set).
        icon_url = server.get("icon_url")
        if icon_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(icon_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            icon_bytes = await resp.read()
                            await guild.edit(icon=icon_bytes, reason="Backup restore")
                        else:
                            notes.append("icon not restored (download failed)")
            except Exception as exc:
                notes.append(f"icon not restored ({str(exc)[:50]})")
        else:
            notes.append("icon not restored (none in snapshot)")


async def setup(bot):
    await bot.add_cog(ServerBackup(bot))
