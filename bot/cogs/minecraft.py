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
import time

import aiohttp
import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put
from utils import general_config
from utils.bot_i18n import t, lang_for
from utils.rich_message import is_components_v2, build_layout_view


# Ampel colors for the default status embed (semantic — used instead of the
# guild accent color when the user didn't author their own embed).
COLOR_ONLINE = 0x43B581
COLOR_OFFLINE = 0xF04747
COLOR_UNKNOWN = 0x747F8D

MCSRVSTAT_JAVA = "https://api.mcsrvstat.us/3/{address}"
MCSRVSTAT_BEDROCK = "https://api.mcsrvstat.us/bedrock/3/{address}"
USER_AGENT = "projectx-bot/1.0 (Minecraft status)"

STATUS_EMOJI = {"online": "🟢", "offline": "🔴", "unknown": "⚫"}
# Discord rate-limits channel renames to ~2 / 10 min per channel. Only rename
# when the name changed AND at least this many seconds passed since the last one.
NAME_RENAME_COOLDOWN = 330

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
        # server_id -> last channel name we set; channel_id -> monotonic time of
        # the last rename (rate-limit guard for the status-as-channel-name feature).
        self._name_rendered = {}
        self._name_renamed_at = {}
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
                            players, players_max, version, motd, ping=-1, status=None):
        if template is None:
            return ""
        text = str(template)
        ping_str = f"{ping}ms" if isinstance(ping, int) and ping >= 0 else ""
        replacements = {
            "{status}": status_label,
            "{players}": str(players),
            "{max}": str(players_max),
            "{motd}": (motd or "").replace("\n", " ").strip(),
            "{version}": version or "",
            "{address}": address or "",
            "{name}": name or address or "",
            "{ping}": ping_str,
            "{emoji}": STATUS_EMOJI.get(status or "unknown", "⚫"),
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
            ping=snap.get("ping", -1), status=status,
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
                ping=snap.get("ping", -1), status=status,
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

    def _build_v2_view(self, server, snap, lang):
        """Build a Components V2 LayoutView for the status message.

        Returns None if the config has no renderable blocks (caller falls back
        to the default status embed so the message is never empty).
        """
        name = server.get("name") or server.get("address") or t(lang, "mc.defaultName")
        status_label = self._status_label(lang, snap["status"])
        cfg = server.get("embed") if isinstance(server.get("embed"), dict) else {}

        def ph(value):
            return self._apply_placeholders(
                value or "", lang=lang, name=name, address=server.get("address"),
                status_label=status_label, players=snap["players_online"],
                players_max=snap["players_max"], version=snap["version"], motd=snap["motd"],
            )

        return build_layout_view(
            cfg,
            resolve_text=ph,
            resolve_url=lambda s: str(s) if _looks_like_url(s) else "",
        )

    # ------------------------------------------------------------------ #
    # Per-server processing (query + edit-in-place message)
    # ------------------------------------------------------------------ #

    async def _measure_ping(self, address, edition):
        """Best-effort latency in ms via a TCP connect to the server (no MC
        handshake). Java only; Bedrock is UDP → -1. -1 on any failure (SRV-only
        setups, firewalled, offline). Never raises."""
        if not address or (edition or "").lower() == "bedrock":
            return -1
        host, port = address, 25565
        if ":" in address:
            h, _, p = address.rpartition(":")
            if h and p.isdigit():
                host, port = h, int(p)
        writer = None
        try:
            start = time.monotonic()
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            return max(0, int((time.monotonic() - start) * 1000))
        except Exception:
            return -1
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

    def _name_for(self, server, snap, lang):
        """Render the status-as-channel-name string from the server's template
        (falls back to a sensible default). Capped at Discord's 100 chars."""
        name = server.get("name") or server.get("address") or t(lang, "mc.defaultName")
        status = snap["status"]
        template = server.get("name_template") or "{emoji} {name}: {players}/{max}"
        rendered = self._apply_placeholders(
            template, lang=lang, name=name, address=server.get("address"),
            status_label=self._status_label(lang, status), players=snap["players_online"],
            players_max=snap["players_max"], version=snap["version"], motd=snap["motd"],
            ping=snap.get("ping", -1), status=status,
        )
        # Collapse whitespace + trim dangling separators (e.g. from an empty {ping}).
        rendered = " ".join(rendered.split()).strip(" ·-|")
        return rendered[:100] or (name[:100])

    async def _update_name_channel(self, server, snap, lang):
        """Rename the configured channel to reflect the live status. Rate-limit
        aware: only renames on change AND after a cooldown (Discord ~2/10min)."""
        chan_id = server.get("name_channel_id")
        if not chan_id:
            return
        try:
            channel = self.bot.get_channel(int(chan_id))
        except (TypeError, ValueError):
            return
        if channel is None:
            return

        new_name = self._name_for(server, snap, lang)
        server_id = server.get("id")
        if self._name_rendered.get(server_id) == new_name:
            return  # unchanged since we last set it
        last = self._name_renamed_at.get(str(chan_id), 0.0)
        if time.monotonic() - last < NAME_RENAME_COOLDOWN:
            return  # too soon — wait to avoid Discord's rename rate limit
        try:
            await channel.edit(name=new_name)
            self._name_rendered[server_id] = new_name
            self._name_renamed_at[str(chan_id)] = time.monotonic()
        except discord.Forbidden:
            print(f"[minecraft] no permission to rename channel {chan_id}")
        except Exception as exc:
            print(f"[minecraft] rename failed for channel {chan_id}: {exc}")

    async def _process_server(self, server):
        server_id = server.get("id")
        guild_id = server.get("guild_id")
        channel_id = server.get("channel_id")
        name_channel_id = server.get("name_channel_id")
        # Need at least one destination: a status-message channel or a name channel.
        if not (server_id and guild_id and server.get("address")):
            return
        if not (channel_id or name_channel_id):
            return

        snap = await self._query_status(server.get("address"), server.get("edition"))
        snap["ping"] = await self._measure_ping(server.get("address"), server.get("edition"))

        lang = await lang_for(self.backend_url, self.api_key, guild_id)

        # Status message (only if a message channel is configured + visible).
        if channel_id:
            await self._update_status_message(server, snap, lang, channel_id)

        # Status as channel name (only if a name channel is configured).
        await self._update_name_channel(server, snap, lang)

        # Persist the freshly polled values so the dashboard reflects them.
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
        if snap.get("ping", -1) != (server.get("ping_ms") if server.get("ping_ms") is not None else -1):
            changes["ping_ms"] = snap.get("ping", -1)
        if changes:
            await self._put_state(guild_id, server_id, changes)

    async def _update_status_message(self, server, snap, lang, channel_id):
        """Post/edit-in-place the status message in the configured channel."""
        server_id = server.get("id")
        guild_id = server.get("guild_id")
        try:
            channel = self.bot.get_channel(int(channel_id))
        except (TypeError, ValueError):
            print(f"[minecraft] invalid channel id {channel_id!r} for server {server_id}")
            return
        if channel is None:
            return  # bot can't see it this cycle

        current_key = (
            snap["status"], snap["players_online"], snap["players_max"],
            snap["version"], snap["motd"],
        )
        existing_id = server.get("status_message_id")
        cached = self._rendered.get(server_id)
        unchanged = cached is not None and cached == current_key

        notify_mode = (server.get("notify_mode") or "plain").lower()
        embed = None
        content = None
        view = None
        if notify_mode == "embed":
            cfg = server.get("embed") if isinstance(server.get("embed"), dict) else {}
            if is_components_v2(cfg):
                view = self._build_v2_view(server, snap, lang)
            if view is None:
                embed = await self._build_embed(server, snap, lang)
        else:
            content = self._build_content(server, snap, lang)
        want_v2 = view is not None

        async def _send_new():
            if want_v2:
                return await channel.send(view=view)
            return await channel.send(content=content, embed=embed)

        msg = None
        if existing_id:
            try:
                existing = await channel.fetch_message(int(existing_id))
                existing_is_v2 = bool(existing.flags.components_v2)
                if want_v2 != existing_is_v2:
                    try:
                        await existing.delete()
                    except Exception:
                        pass
                    msg = None
                elif not unchanged:
                    if want_v2:
                        await existing.edit(view=view)
                    else:
                        await existing.edit(content=content, embed=embed)
                    msg = existing
                else:
                    msg = existing
            except (discord.NotFound, ValueError):
                msg = None
            except discord.Forbidden:
                print(f"[minecraft] no permission to edit message in {channel_id}")
                return
            except Exception as exc:
                print(f"[minecraft] edit failed for server {server_id}: {exc}")
                return

        if msg is None:
            try:
                msg = await _send_new()
            except discord.Forbidden:
                print(f"[minecraft] missing permission to post in channel {channel_id}")
                return
            except Exception as exc:
                print(f"[minecraft] post failed in channel {channel_id}: {exc}")
                return
            await self._put_state(guild_id, server_id, {"status_message_id": str(msg.id)})

        self._rendered[server_id] = current_key

    async def _put_state(self, guild_id, server_id, changes):
        if not changes:
            return
        path = f"/api/bot/guilds/{guild_id}/minecraft/{server_id}/state"
        await bot_put(self.backend_url, self.api_key, path, changes)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
