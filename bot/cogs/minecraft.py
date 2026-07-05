"""Minecraft server status cog.

Maintains ONE auto-updating live-status message per configured Minecraft server.
There are no online/offline transition alerts — just the single message that is
edited in place whenever the visible values (status / players / version / motd)
change, exactly like the role-menus "dirty" edit-in-place pattern.

Status is polled from the public mcsrvstat.us API (no key, no extra dependency —
just aiohttp). On any query failure the status is reported as "unknown" (never a
false "offline"). A single bad server never aborts the whole cycle and the loop
never crashes. Logging prefix: "[minecraft]".

Backend contract (X-Bot-Token auth, via utils.backend helpers):

  GET /api/bot/minecraft/servers
      → { "servers": [ server, … ] }  (all enabled servers across all guilds)
      Each `server`:
        { id, guild_id, name, address, edition ∈ {java|bedrock},
          channel_id, notify_mode ∈ {plain|embed},
          message_template (str, may be ''),
          embed { title, description, color('#RRGGBB'), thumbnail, image,
                  footer, show_timestamp(bool), author_name, author_icon_url },
          enabled, status ∈ {online|offline|unknown},
          players_online, players_max, motd, version,
          status_message_id (str|null), last_checked_at }

  PUT /api/bot/guilds/{guild_id}/minecraft/{server_id}/state
      body { status?, players_online?, players_max?, motd?, version?,
             status_message_id? }
      → persists state (only the given keys). last_checked_at + dirty-reset are
        handled server-side.
"""

import asyncio

import aiohttp
import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put
from utils import general_config
from utils.bot_i18n import t, lang_for


# Ampel colors for the default status embed (semantic — used instead of the
# guild accent color when the user didn't author their own embed).
COLOR_ONLINE = 0x43B581
COLOR_OFFLINE = 0xF04747
COLOR_UNKNOWN = 0x747F8D

MCSRVSTAT_JAVA = "https://api.mcsrvstat.us/3/{address}"
MCSRVSTAT_BEDROCK = "https://api.mcsrvstat.us/bedrock/3/{address}"
USER_AGENT = "projectx-bot/1.0 (Minecraft status)"

HTTP_URL_PREFIXES = ("http://", "https://")


def _looks_like_url(value):
    return bool(value) and str(value).lower().startswith(HTTP_URL_PREFIXES)


def _parse_color(value, fallback):
    """'#RRGGBB' → int; invalid → fallback (an int)."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return int(value[1:], 16)
        except ValueError:
            pass
    return fallback


class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # server_id -> last rendered snapshot tuple (status, players_online,
        # players_max, version, motd). Avoids editing the message when nothing
        # visible changed (Discord rate-limit friendly).
        self._rendered = {}
        self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    def _enabled(self):
        if not self.api_key:
            print("[minecraft] BOT_API_KEY missing — skip cycle")
            return False
        if not self.backend_url:
            print("[minecraft] BACKEND_URL missing — skip cycle")
            return False
        return True

    # ------------------------------------------------------------------ #
    # Loop
    # ------------------------------------------------------------------ #

    @tasks.loop(seconds=max(60, config.MINECRAFT_POLL_INTERVAL))
    async def poll_loop(self):
        try:
            await self._run_cycle()
        except Exception as exc:
            print(f"[minecraft] poll cycle fatal error: {exc}")

    @poll_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _run_cycle(self):
        if not self._enabled():
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/minecraft/servers")
        if not data:
            return
        servers = data.get("servers") or []
        for server in servers:
            if not server.get("enabled"):
                continue
            try:
                await self._process_server(server)
            except Exception as exc:
                print(f"[minecraft] server {server.get('id')}: error: {exc}")

    # ------------------------------------------------------------------ #
    # mcsrvstat.us query
    # ------------------------------------------------------------------ #

    async def _query_status(self, address, edition):
        """Return a normalized status dict, never raises.

        { status: 'online'|'offline'|'unknown',
          players_online: int, players_max: int,
          version: str, motd: str }
        On any error → status 'unknown' (NOT a false 'offline').
        """
        result = {
            "status": "unknown",
            "players_online": 0,
            "players_max": 0,
            "version": "",
            "motd": "",
        }
        if not address:
            return result
        tpl = MCSRVSTAT_BEDROCK if (edition or "").lower() == "bedrock" else MCSRVSTAT_JAVA
        url = tpl.format(address=address)
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        print(f"[minecraft] {address}: HTTP {resp.status}")
                        return result
                    payload = await resp.json()
        except Exception as exc:
            print(f"[minecraft] {address}: query failed: {exc}")
            return result

        if not isinstance(payload, dict):
            return result

        # mcsrvstat: 'online' bool present once the address resolved. If online
        # is explicitly False → server offline; otherwise (present) → online.
        online = payload.get("online")
        result["status"] = "online" if online else "offline"

        players = payload.get("players") or {}
        if isinstance(players, dict):
            try:
                result["players_online"] = int(players.get("online") or 0)
            except (TypeError, ValueError):
                result["players_online"] = 0
            try:
                result["players_max"] = int(players.get("max") or 0)
            except (TypeError, ValueError):
                result["players_max"] = 0

        version = payload.get("version")
        if isinstance(version, str):
            result["version"] = version
        elif version is not None:
            result["version"] = str(version)

        motd = payload.get("motd") or {}
        if isinstance(motd, dict):
            clean = motd.get("clean")
            if isinstance(clean, list):
                result["motd"] = "\n".join(str(line) for line in clean).strip()
            elif isinstance(clean, str):
                result["motd"] = clean.strip()
        return result

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _status_label(self, lang, status):
        if status == "online":
            return t(lang, "mc.online")
        if status == "offline":
            return t(lang, "mc.offline")
        return t(lang, "mc.unknown")

    def _apply_placeholders(self, template, *, lang, name, address, status_label,
                            players, players_max, version, motd):
        if template is None:
            return ""
        text = str(template)
        replacements = {
            "{status}": status_label,
            "{players}": str(players),
            "{max}": str(players_max),
            "{motd}": (motd or "").replace("\n", " ").strip(),
            "{version}": version or "",
            "{address}": address or "",
            "{name}": name or address or "",
        }
        for token, value in replacements.items():
            if token in text:
                text = text.replace(token, value)
        return text

    def _default_plain(self, lang, status, *, name, players, players_max):
        if status == "online":
            key = "mc.defaultOnline"
        elif status == "offline":
            key = "mc.defaultOffline"
        else:
            key = "mc.defaultUnknown"
        return t(lang, key, name=name, players=players, max=players_max)

    def _build_content(self, server, snap, lang):
        name = server.get("name") or server.get("address") or t(lang, "mc.defaultName")
        status = snap["status"]
        status_label = self._status_label(lang, status)
        template = server.get("message_template")
        if not template:
            return self._default_plain(
                lang, status, name=name,
                players=snap["players_online"], players_max=snap["players_max"],
            )
        return self._apply_placeholders(
            template, lang=lang, name=name, address=server.get("address"),
            status_label=status_label, players=snap["players_online"],
            players_max=snap["players_max"], version=snap["version"], motd=snap["motd"],
        )

    async def _build_embed(self, server, snap, lang):
        name = server.get("name") or server.get("address") or t(lang, "mc.defaultName")
        status = snap["status"]
        status_label = self._status_label(lang, status)
        cfg = server.get("embed")
        if not isinstance(cfg, dict):
            cfg = {}

        def ph(value):
            return self._apply_placeholders(
                value or "", lang=lang, name=name, address=server.get("address"),
                status_label=status_label, players=snap["players_online"],
                players_max=snap["players_max"], version=snap["version"], motd=snap["motd"],
            )

        has_user_content = bool(
            (cfg.get("title") or "").strip()
            or (cfg.get("description") or "").strip()
            or (cfg.get("author_name") or "").strip()
        )

        semantic = COLOR_UNKNOWN
        if status == "online":
            semantic = COLOR_ONLINE
        elif status == "offline":
            semantic = COLOR_OFFLINE

        if not has_user_content:
            # Sensible default status embed with the semantic ampel color.
            embed = discord.Embed(title=name, color=semantic)
            embed.add_field(name=t(lang, "mc.statusField"), value=status_label, inline=True)
            embed.add_field(
                name=t(lang, "mc.playersField"),
                value=f"{snap['players_online']}/{snap['players_max']}",
                inline=True,
            )
            if snap["version"]:
                embed.add_field(name=t(lang, "mc.versionField"), value=snap["version"], inline=True)
            if snap["motd"]:
                embed.description = snap["motd"]
            embed.timestamp = discord.utils.utcnow()
            return embed

        # User authored the embed → keep their design, only substitute placeholders
        # and use their configured color (fallback to the guild accent color).
        fallback_color = semantic
        try:
            gid = int(server.get("guild_id"))
            accent = await general_config.get_embed_color(
                self.backend_url, self.api_key, gid, fallback=semantic)
            fallback_color = accent.value
        except Exception:
            fallback_color = semantic

        embed = discord.Embed(
            title=ph(cfg.get("title", "")) or None,
            description=ph(cfg.get("description", "")) or None,
            color=_parse_color(cfg.get("color"), fallback_color),
        )
        thumb = cfg.get("thumbnail")
        if _looks_like_url(thumb):
            try:
                embed.set_thumbnail(url=str(thumb))
            except Exception:
                pass
        image = cfg.get("image")
        if _looks_like_url(image):
            try:
                embed.set_image(url=str(image))
            except Exception:
                pass
        footer = ph(cfg.get("footer", ""))
        if footer:
            embed.set_footer(text=footer[:2048])
        author_name = ph(cfg.get("author_name", ""))
        if author_name:
            icon = cfg.get("author_icon_url")
            try:
                if _looks_like_url(icon):
                    embed.set_author(name=author_name[:256], icon_url=str(icon))
                else:
                    embed.set_author(name=author_name[:256])
            except Exception:
                pass
        if cfg.get("show_timestamp"):
            embed.timestamp = discord.utils.utcnow()
        return embed

    # ------------------------------------------------------------------ #
    # Per-server processing (query + edit-in-place message)
    # ------------------------------------------------------------------ #

    async def _process_server(self, server):
        server_id = server.get("id")
        guild_id = server.get("guild_id")
        channel_id = server.get("channel_id")
        if not (server_id and guild_id and channel_id):
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
        except (TypeError, ValueError):
            print(f"[minecraft] invalid channel id {channel_id!r} for server {server_id}")
            return
        if channel is None:
            # Bot may not see the channel this cycle — skip quietly.
            return

        snap = await self._query_status(server.get("address"), server.get("edition"))

        # Compare against the last rendered snapshot to skip needless edits.
        current_key = (
            snap["status"], snap["players_online"], snap["players_max"],
            snap["version"], snap["motd"],
        )
        existing_id = server.get("status_message_id")
        cached = self._rendered.get(server_id)
        unchanged = cached is not None and cached == current_key

        lang = await lang_for(self.backend_url, self.api_key, guild_id)
        notify_mode = (server.get("notify_mode") or "plain").lower()

        embed = None
        content = None
        if notify_mode == "embed":
            embed = await self._build_embed(server, snap, lang)
        else:
            content = self._build_content(server, snap, lang)

        msg = None
        # Try to edit the existing message in place when it exists.
        if existing_id:
            try:
                existing = await channel.fetch_message(int(existing_id))
                # Only edit if visible values changed (or we've never rendered it).
                if not unchanged:
                    await existing.edit(content=content, embed=embed)
                msg = existing
            except (discord.NotFound, ValueError):
                msg = None  # message deleted → repost below
            except discord.Forbidden:
                print(f"[minecraft] no permission to edit message in {channel_id}")
                return
            except Exception as exc:
                print(f"[minecraft] edit failed for server {server_id}: {exc}")
                return

        if msg is None:
            try:
                msg = await channel.send(content=content, embed=embed)
            except discord.Forbidden:
                print(f"[minecraft] missing permission to post in channel {channel_id}")
                return
            except Exception as exc:
                print(f"[minecraft] post failed in channel {channel_id}: {exc}")
                return
            # Persist the new message id so we edit it next cycle.
            await self._put_state(guild_id, server_id, {"status_message_id": str(msg.id)})

        # Remember what we rendered so we don't re-edit unnecessarily.
        self._rendered[server_id] = current_key

        # Write the freshly polled values back to the backend so the dashboard
        # reflects them. Only send when they changed vs. what the backend knows.
        changes = {}
        if server.get("status") != snap["status"]:
            changes["status"] = snap["status"]
        if server.get("players_online") != snap["players_online"]:
            changes["players_online"] = snap["players_online"]
        if server.get("players_max") != snap["players_max"]:
            changes["players_max"] = snap["players_max"]
        if (server.get("version") or "") != snap["version"]:
            changes["version"] = snap["version"]
        if (server.get("motd") or "") != snap["motd"]:
            changes["motd"] = snap["motd"]
        if changes:
            await self._put_state(guild_id, server_id, changes)

    async def _put_state(self, guild_id, server_id, changes):
        if not changes:
            return
        path = f"/api/bot/guilds/{guild_id}/minecraft/{server_id}/state"
        await bot_put(self.backend_url, self.api_key, path, changes)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
