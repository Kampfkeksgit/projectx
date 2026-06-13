"""Social Notifications cog — polls YouTube / Twitch / Kick for tracked creators
and posts a Discord announcement when they go live or upload a new video.

Backend contract (all via utils.backend helpers, X-Bot-Token auth):

  GET /api/bot/social/subscriptions
      → { "subscriptions": [ sub, … ] }
      Each `sub`:
        { id, guild_id, platform, account, account_id, display_name,
          channel_id, notify_live (bool), notify_upload (bool),
          mention_role_id (str|null), message_template (str, may be ''),
          use_embed (bool),
          embed { title, description, color('#RRGGBB'), thumbnail, image,
                  footer, show_timestamp(bool), author_name, author_icon_url },
          enabled, last_video_id (str|null), last_live (bool), last_checked_at }
      platform ∈ youtube | twitch | kick | tiktok | instagram
      account  = normalized handle/login/channelId (no leading @)
      account_id = resolved platform id; null until the bot resolves + writes back

  PUT /api/bot/social/subscriptions/{id}/state
      body { account_id?, display_name?, last_video_id?, last_live? }
      → persists state. Send ONLY the keys that changed.
        last_checked_at is stamped server-side.

Design notes / limitations:
  - YouTube uploads use the public Atom RSS feed (0 API quota, no key needed).
    A YOUTUBE_API_KEY is only needed to (a) resolve a @handle → UC… channelId
    and (b) best-effort distinguish "live" vs "upload". Without a key the user
    must enter the raw UC… channel id, and every new feed entry is treated as
    an upload.
  - Twitch + Kick need their respective client_id/secret for an app token.
  - TikTok / Instagram have no free official API → stubbed (skipped) with a
    clear extension point.
  - Every network call is wrapped; a single bad subscription never aborts the
    whole cycle, and the loop never crashes. Logging prefix: "[social]".
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

import config


DEFAULT_EMBED_COLOR = 0x5865F2

# YouTube channelIds look like "UC" + 22 url-safe base64 chars.
YT_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{20,}$")
# A plausible http(s) URL (used to gate embed image/thumbnail/icon fields).
HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# Atom / YouTube XML namespaces used by the uploads feed.
YT_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "twitch": "Twitch",
    "kick": "Kick",
    "tiktok": "TikTok",
    "instagram": "Instagram",
}


def _platform_label(platform):
    return PLATFORM_LABELS.get((platform or "").lower(), (platform or "").capitalize())


def _looks_like_url(value):
    return bool(value) and bool(HTTP_URL_RE.match(str(value)))


def _parse_color(color_str):
    """'#RRGGBB' → int; invalid → default brand purple."""
    try:
        if isinstance(color_str, str) and color_str.startswith("#") and len(color_str) == 7:
            return int(color_str[1:], 16)
    except (ValueError, TypeError):
        pass
    return DEFAULT_EMBED_COLOR


class SocialNotify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY

        # Cached OAuth app tokens: { "value": str, "expires_at": float(unix) }.
        self._twitch_token = None
        self._kick_token = None

        self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    def _enabled(self):
        if not self.api_key:
            print("[social] BOT_API_KEY missing — skip cycle")
            return False
        if not self.backend_url:
            print("[social] BACKEND_URL missing — skip cycle")
            return False
        return True

    # ------------------------------------------------------------------ #
    # Loop
    # ------------------------------------------------------------------ #

    @tasks.loop(seconds=max(30, config.SOCIAL_POLL_INTERVAL))
    async def poll_loop(self):
        try:
            await self._run_cycle()
        except Exception as exc:
            print(f"[social] poll cycle fatal error: {exc}")

    @poll_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _run_cycle(self):
        if not self._enabled():
            return

        data = await self._bot_get("/api/bot/social/subscriptions")
        if not data:
            return
        subs = data.get("subscriptions") or []
        if not subs:
            return

        # Group enabled subs by platform.
        by_platform = {}
        for sub in subs:
            if not sub.get("enabled"):
                continue
            platform = (sub.get("platform") or "").lower()
            by_platform.setdefault(platform, []).append(sub)

        for platform, platform_subs in by_platform.items():
            try:
                if platform == "youtube":
                    await self._handle_youtube(platform_subs)
                elif platform == "twitch":
                    await self._handle_twitch(platform_subs)
                elif platform == "kick":
                    await self._handle_kick(platform_subs)
                elif platform in ("tiktok", "instagram"):
                    await self._handle_unsupported(platform, platform_subs)
                else:
                    print(f"[social] {platform}: unknown platform, skipped")
            except Exception as exc:
                print(f"[social] {platform}: handler error: {exc}")

    # ------------------------------------------------------------------ #
    # Backend helpers (thin wrappers so we keep the [social] log prefix)
    # ------------------------------------------------------------------ #

    async def _bot_get(self, path):
        from utils.backend import bot_get
        return await bot_get(self.backend_url, self.api_key, path)

    async def _put_state(self, sub_id, changes):
        """PUT only the changed state keys for a subscription."""
        if not changes:
            return
        from utils.backend import bot_put
        path = f"/api/bot/social/subscriptions/{sub_id}/state"
        await bot_put(self.backend_url, self.api_key, path, changes)

    # ------------------------------------------------------------------ #
    # Raw HTTP (for third-party APIs — backend helpers only target the backend)
    # ------------------------------------------------------------------ #

    async def _http_get_json(self, url, headers=None, params=None, timeout=10):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, params=params,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if 200 <= resp.status < 300:
                        try:
                            return resp.status, await resp.json()
                        except Exception:
                            return resp.status, None
                    body = await resp.text()
                    print(f"[social] GET {url}: HTTP {resp.status} — {body[:160]}")
                    return resp.status, None
        except Exception as exc:
            print(f"[social] GET {url} failed: {exc}")
            return None, None

    async def _http_get_text(self, url, headers=None, params=None, timeout=10):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, params=params,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if 200 <= resp.status < 300:
                        return resp.status, await resp.text()
                    print(f"[social] GET {url}: HTTP {resp.status}")
                    return resp.status, None
        except Exception as exc:
            print(f"[social] GET {url} failed: {exc}")
            return None, None

    async def _http_post_form_json(self, url, data, timeout=10):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=data,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if 200 <= resp.status < 300:
                        try:
                            return resp.status, await resp.json()
                        except Exception:
                            return resp.status, None
                    body = await resp.text()
                    print(f"[social] POST {url}: HTTP {resp.status} — {body[:160]}")
                    return resp.status, None
        except Exception as exc:
            print(f"[social] POST {url} failed: {exc}")
            return None, None

    # ------------------------------------------------------------------ #
    # YouTube
    # ------------------------------------------------------------------ #

    async def _handle_youtube(self, subs):
        key = config.YOUTUBE_API_KEY  # optional
        for sub in subs:
            try:
                await self._process_youtube_sub(sub, key)
            except Exception as exc:
                print(f"[social] youtube sub {sub.get('id')}: error: {exc}")

    async def _resolve_youtube_channel_id(self, account, key):
        """Resolve a handle/username → UC… channelId via the Data API.

        Returns the channelId string, or None if it can't be resolved.
        """
        handle = (account or "").lstrip("@").strip()
        if not handle:
            return None
        # Try forHandle first (modern @handles), then forUsername (legacy).
        for param in ("forHandle", "forUsername"):
            status, payload = await self._http_get_json(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", param: handle, "key": key},
            )
            if payload:
                items = payload.get("items") or []
                if items and items[0].get("id"):
                    return items[0]["id"]
        return None

    async def _process_youtube_sub(self, sub, key):
        account = sub.get("account") or ""
        channel_id = sub.get("account_id")

        # --- resolve channelId if missing ---
        if not channel_id:
            handle = account.lstrip("@").strip()
            if YT_CHANNEL_ID_RE.match(handle):
                channel_id = handle
            elif key:
                channel_id = await self._resolve_youtube_channel_id(account, key)
            else:
                print(
                    f"[social] youtube {account}: cannot resolve channelId without "
                    f"YOUTUBE_API_KEY (enter the UC… channel id instead)"
                )
                return
            if not channel_id:
                print(f"[social] youtube {account}: could not resolve channelId")
                return
            # Persist the resolved id so we never resolve again.
            await self._put_state(sub.get("id"), {"account_id": channel_id})
            sub["account_id"] = channel_id

        # --- fetch uploads feed (no key, 0 quota) ---
        status, text = await self._http_get_text(
            "https://www.youtube.com/feeds/videos.xml",
            params={"channel_id": channel_id},
        )
        if not text:
            return

        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            print(f"[social] youtube {account}: feed parse error: {exc}")
            return

        entries = root.findall("atom:entry", YT_NS)
        if not entries:
            return

        latest = entries[0]
        vid_el = latest.find("yt:videoId", YT_NS)
        title_el = latest.find("atom:title", YT_NS)
        video_id = vid_el.text if vid_el is not None else None
        title = title_el.text if title_el is not None else ""
        if not video_id:
            return

        last_video_id = sub.get("last_video_id")

        # First sight of this channel → seed last_video_id, do NOT announce backlog.
        if not last_video_id:
            await self._put_state(sub.get("id"), {"last_video_id": video_id})
            return

        # No change → nothing to do.
        if video_id == last_video_id:
            return

        # New entry detected.
        url = f"https://www.youtube.com/watch?v={video_id}"
        display_name = sub.get("display_name") or account

        # Best-effort live detection (only if key + notify_live).
        event_type = "video"
        if sub.get("notify_live") and key:
            try:
                if await self._youtube_is_live(video_id, key):
                    event_type = "live"
            except Exception as exc:
                print(f"[social] youtube {account}: live-check error: {exc}")
                event_type = "video"

        should_announce = (
            (event_type == "live" and sub.get("notify_live"))
            or (event_type == "video" and sub.get("notify_upload"))
        )
        if should_announce:
            await self._announce(sub, event_type=event_type, url=url, title=title or "",
                                 display_name=display_name)

        # Always advance last_video_id so we don't re-fire on the next cycle.
        await self._put_state(sub.get("id"), {"last_video_id": video_id})

    async def _youtube_is_live(self, video_id, key):
        """Return True if the given video is currently a live broadcast.

        Limitation: this is a best-effort single-video check. It does not catch
        livestreams that were scheduled but never produced a feed entry, and it
        costs API quota — hence it only runs when a key is configured AND the
        sub wants live notifications.
        """
        status, payload = await self._http_get_json(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet,liveStreamingDetails",
                "id": video_id,
                "key": key,
            },
        )
        if not payload:
            return False
        items = payload.get("items") or []
        if not items:
            return False
        snippet = items[0].get("snippet") or {}
        return snippet.get("liveBroadcastContent") == "live"

    # ------------------------------------------------------------------ #
    # Twitch
    # ------------------------------------------------------------------ #

    async def _twitch_get_token(self, force=False):
        """Return a cached/refreshed Twitch app access token, or None."""
        cid = config.TWITCH_CLIENT_ID
        secret = config.TWITCH_CLIENT_SECRET
        if not cid or not secret:
            return None
        now = time.time()
        if (not force and self._twitch_token
                and self._twitch_token.get("expires_at", 0) > now + 60):
            return self._twitch_token["value"]

        status, payload = await self._http_post_form_json(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": cid,
                "client_secret": secret,
                "grant_type": "client_credentials",
            },
        )
        if not payload or not payload.get("access_token"):
            print("[social] twitch: failed to obtain app token")
            return None
        expires_in = payload.get("expires_in") or 3600
        self._twitch_token = {
            "value": payload["access_token"],
            "expires_at": now + int(expires_in),
        }
        return self._twitch_token["value"]

    async def _handle_twitch(self, subs):
        if not config.TWITCH_CLIENT_ID or not config.TWITCH_CLIENT_SECRET:
            print("[social] twitch: skipped, TWITCH_CLIENT_ID/SECRET not set")
            return
        token = await self._twitch_get_token()
        if not token:
            return
        cid = config.TWITCH_CLIENT_ID
        headers = {"Client-Id": cid, "Authorization": f"Bearer {token}"}

        # Resolve any missing user_ids / display_names first.
        for sub in subs:
            try:
                if not sub.get("account_id"):
                    await self._twitch_resolve_user(sub, headers)
            except Exception as exc:
                print(f"[social] twitch resolve {sub.get('account')}: {exc}")

        # Batch the live check (up to 100 logins per request).
        logins = []
        for sub in subs:
            login = (sub.get("account") or "").lstrip("@").strip().lower()
            if login:
                logins.append(login)
        live_set = set()
        live_meta = {}  # login → { title, game_name, user_name }
        for chunk_start in range(0, len(logins), 100):
            chunk = logins[chunk_start:chunk_start + 100]
            params = [("user_login", l) for l in chunk]
            status, payload = await self._http_get_json(
                "https://api.twitch.tv/helix/streams",
                headers=headers, params=params,
            )
            if status == 401:
                # Token expired mid-cycle — refresh once and retry this chunk.
                token = await self._twitch_get_token(force=True)
                if not token:
                    return
                headers = {"Client-Id": cid, "Authorization": f"Bearer {token}"}
                status, payload = await self._http_get_json(
                    "https://api.twitch.tv/helix/streams",
                    headers=headers, params=params,
                )
            if not payload:
                continue
            for entry in payload.get("data") or []:
                login = (entry.get("user_login") or "").lower()
                if login:
                    live_set.add(login)
                    live_meta[login] = {
                        "title": entry.get("title") or "",
                        "game_name": entry.get("game_name") or "",
                        "user_name": entry.get("user_name") or "",
                    }

        for sub in subs:
            try:
                await self._process_twitch_sub(sub, live_set, live_meta)
            except Exception as exc:
                print(f"[social] twitch sub {sub.get('id')}: error: {exc}")

    async def _twitch_resolve_user(self, sub, headers):
        login = (sub.get("account") or "").lstrip("@").strip()
        if not login:
            return
        status, payload = await self._http_get_json(
            "https://api.twitch.tv/helix/users",
            headers=headers, params={"login": login},
        )
        if not payload:
            return
        data = payload.get("data") or []
        if not data:
            print(f"[social] twitch {login}: user not found")
            return
        user = data[0]
        changes = {}
        if user.get("id"):
            changes["account_id"] = str(user["id"])
            sub["account_id"] = str(user["id"])
        if user.get("display_name"):
            changes["display_name"] = user["display_name"]
            sub["display_name"] = user["display_name"]
        if changes:
            await self._put_state(sub.get("id"), changes)

    async def _process_twitch_sub(self, sub, live_set, live_meta):
        login = (sub.get("account") or "").lstrip("@").strip().lower()
        is_live = login in live_set
        was_live = bool(sub.get("last_live"))

        # offline → online transition.
        if is_live and not was_live and sub.get("notify_live"):
            meta = live_meta.get(login, {})
            url = f"https://www.twitch.tv/{login}"
            title = meta.get("title") or meta.get("game_name") or ""
            display_name = sub.get("display_name") or meta.get("user_name") or sub.get("account")
            await self._announce(sub, event_type="live", url=url, title=title,
                                 display_name=display_name)

        if is_live != was_live:
            await self._put_state(sub.get("id"), {"last_live": is_live})

    # ------------------------------------------------------------------ #
    # Kick
    # ------------------------------------------------------------------ #

    async def _kick_get_token(self, force=False):
        cid = config.KICK_CLIENT_ID
        secret = config.KICK_CLIENT_SECRET
        if not cid or not secret:
            return None
        now = time.time()
        if (not force and self._kick_token
                and self._kick_token.get("expires_at", 0) > now + 60):
            return self._kick_token["value"]

        status, payload = await self._http_post_form_json(
            "https://id.kick.com/oauth/token",
            data={
                "client_id": cid,
                "client_secret": secret,
                "grant_type": "client_credentials",
            },
        )
        if not payload or not payload.get("access_token"):
            print("[social] kick: failed to obtain app token")
            return None
        expires_in = payload.get("expires_in") or 3600
        self._kick_token = {
            "value": payload["access_token"],
            "expires_at": now + int(expires_in),
        }
        return self._kick_token["value"]

    async def _handle_kick(self, subs):
        if not config.KICK_CLIENT_ID or not config.KICK_CLIENT_SECRET:
            print("[social] kick: skipped, KICK_CLIENT_ID/SECRET not set")
            return
        token = await self._kick_get_token()
        if not token:
            return
        headers = {"Authorization": f"Bearer {token}"}

        for sub in subs:
            try:
                await self._process_kick_sub(sub, headers)
            except Exception as exc:
                print(f"[social] kick sub {sub.get('id')}: error: {exc}")

    @staticmethod
    def _kick_extract_channel(payload):
        """Kick's response shape varies; dig out the first channel-ish object.

        Returns a dict or None.
        """
        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        if isinstance(data, list):
            return data[0] if data else None
        if isinstance(data, dict):
            return data
        # Some endpoints return the channel object at the top level.
        return payload

    @staticmethod
    def _kick_is_live(channel):
        """Defensively detect a live state across the various shapes Kick uses."""
        if not isinstance(channel, dict):
            return False, {}
        # Common shapes: { livestream: {...}|null }, { is_live: bool },
        # { stream: { is_live: bool } }, { livestream: { is_live: bool } }.
        live = False
        stream_obj = {}
        ls = channel.get("livestream")
        if isinstance(ls, dict):
            stream_obj = ls
            live = bool(ls.get("is_live", True)) if "is_live" in ls else True
        elif ls is not None and ls is not False:
            live = bool(ls)
        if not live and channel.get("is_live"):
            live = True
        stream = channel.get("stream")
        if not live and isinstance(stream, dict):
            if stream.get("is_live"):
                live = True
                stream_obj = stream
        return live, stream_obj

    async def _process_kick_sub(self, sub, headers):
        slug = (sub.get("account") or "").lstrip("@").strip()
        if not slug:
            return
        status, payload = await self._http_get_json(
            "https://api.kick.com/public/v1/channels",
            headers=headers, params={"slug": slug},
        )
        if status == 401:
            token = await self._kick_get_token(force=True)
            if not token:
                return
            headers = {"Authorization": f"Bearer {token}"}
            status, payload = await self._http_get_json(
                "https://api.kick.com/public/v1/channels",
                headers=headers, params={"slug": slug},
            )
        if not payload:
            return

        channel = self._kick_extract_channel(payload)
        if channel is None:
            print(f"[social] kick {slug}: unexpected response shape, skipped")
            return

        # Best-effort display_name persistence.
        user_obj = channel.get("user") if isinstance(channel.get("user"), dict) else {}
        display_name = (
            channel.get("slug")
            or user_obj.get("username")
            or sub.get("display_name")
            or slug
        )
        if display_name and display_name != sub.get("display_name"):
            await self._put_state(sub.get("id"), {"display_name": display_name})
            sub["display_name"] = display_name

        try:
            is_live, stream_obj = self._kick_is_live(channel)
        except Exception as exc:
            print(f"[social] kick {slug}: live-parse error: {exc}")
            return

        was_live = bool(sub.get("last_live"))
        if is_live and not was_live and sub.get("notify_live"):
            url = f"https://kick.com/{slug}"
            title = ""
            if isinstance(stream_obj, dict):
                title = stream_obj.get("session_title") or stream_obj.get("title") or ""
            await self._announce(sub, event_type="live", url=url, title=title,
                                 display_name=sub.get("display_name") or slug)

        if is_live != was_live:
            await self._put_state(sub.get("id"), {"last_live": is_live})

    # ------------------------------------------------------------------ #
    # TikTok / Instagram — stub (no free official API)
    # ------------------------------------------------------------------ #

    async def _handle_unsupported(self, platform, subs):
        """Extension point for paid providers.

        There is no free official API for TikTok/Instagram live/upload
        detection. To support them later, implement a per-sub detection method
        here that returns events and call self._announce(...) + self._put_state(...)
        exactly like the other platforms. For now we log once and skip.
        """
        print(f"[social] {platform}: not supported (no free official API — see CLAUDE.md)")
        return

    # ------------------------------------------------------------------ #
    # Announcement rendering (shared)
    # ------------------------------------------------------------------ #

    def _apply_placeholders(self, template, *, display_name, platform, url, title, event_type):
        """Replace social-specific placeholders (case-sensitive).

          {creator}  → display_name
          {platform} → capitalized platform label
          {url}      → content/stream URL
          {title}    → video/stream title (or '')
          {type}     → 'live' or 'video'
        """
        if template is None:
            return ""
        text = str(template)
        replacements = {
            "{creator}": display_name or "",
            "{platform}": _platform_label(platform),
            "{url}": url or "",
            "{title}": title or "",
            "{type}": event_type or "",
        }
        for token, value in replacements.items():
            if token in text:
                text = text.replace(token, value)
        return text

    def _build_embed(self, sub, *, display_name, platform, url, title, event_type):
        cfg = sub.get("embed") or {}
        if not isinstance(cfg, dict):
            cfg = {}

        def ph(value):
            return self._apply_placeholders(
                value or "", display_name=display_name, platform=platform,
                url=url, title=title, event_type=event_type,
            )

        embed = discord.Embed(
            title=ph(cfg.get("title", "")) or None,
            description=ph(cfg.get("description", "")) or None,
            color=_parse_color(cfg.get("color")),
        )

        thumb = cfg.get("thumbnail")
        if _looks_like_url(thumb):
            try:
                embed.set_thumbnail(url=str(thumb))
            except Exception as exc:
                print(f"[social] set_thumbnail failed: {exc}")

        image = cfg.get("image")
        if _looks_like_url(image):
            try:
                embed.set_image(url=str(image))
            except Exception as exc:
                print(f"[social] set_image failed: {exc}")

        footer = ph(cfg.get("footer", ""))
        if footer:
            try:
                embed.set_footer(text=footer)
            except Exception as exc:
                print(f"[social] set_footer failed: {exc}")

        author_name = ph(cfg.get("author_name", ""))
        if author_name:
            icon = cfg.get("author_icon_url")
            try:
                if _looks_like_url(icon):
                    embed.set_author(name=author_name, icon_url=str(icon))
                else:
                    embed.set_author(name=author_name)
            except Exception as exc:
                print(f"[social] set_author failed: {exc}")

        if cfg.get("show_timestamp"):
            embed.timestamp = discord.utils.utcnow()

        # Always ensure the announcement carries the link. If neither the title
        # nor the description already contains the URL, append it as a field.
        if url:
            has_url = (embed.description and url in embed.description)
            if not has_url:
                if embed.description:
                    embed.description = f"{embed.description}\n\n{url}"
                else:
                    embed.add_field(name="Link", value=url, inline=False)

        return embed

    def _default_template(self, event_type):
        if event_type == "live":
            return "**{creator}** is now live on {platform}! {url}"
        return "**{creator}** posted a new video on {platform}: {url}"

    async def _announce(self, sub, *, event_type, url, title, display_name):
        """Post the announcement for a subscription. Defensive end-to-end."""
        platform = (sub.get("platform") or "").lower()
        channel_id = sub.get("channel_id")
        if not channel_id:
            print(f"[social] sub {sub.get('id')}: no channel_id, skip announce")
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
        except (TypeError, ValueError):
            print(f"[social] invalid channel id {channel_id!r} for sub {sub.get('id')}")
            return
        if channel is None:
            print(f"[social] channel {channel_id} not found for sub {sub.get('id')}")
            return

        template = sub.get("message_template")
        if not template:
            template = self._default_template(event_type)
        content = self._apply_placeholders(
            template, display_name=display_name, platform=platform,
            url=url, title=title, event_type=event_type,
        )

        # Prepend role mention if configured.
        allowed = discord.AllowedMentions.none()
        mention_role_id = sub.get("mention_role_id")
        if mention_role_id:
            content = f"<@&{mention_role_id}> {content}".strip()
            allowed = discord.AllowedMentions(roles=True)

        embed = None
        if sub.get("use_embed"):
            try:
                embed = self._build_embed(
                    sub, display_name=display_name, platform=platform,
                    url=url, title=title, event_type=event_type,
                )
            except Exception as exc:
                print(f"[social] embed build failed for sub {sub.get('id')}: {exc}")
                embed = None

        # When using an embed, the content still carries the (optional) role
        # mention — but if it's empty Discord rejects an empty content, so coerce.
        send_content = content if content else None

        try:
            await channel.send(content=send_content, embed=embed, allowed_mentions=allowed)
        except discord.Forbidden:
            print(f"[social] missing permissions to announce in channel {channel_id}")
        except discord.HTTPException as exc:
            print(f"[social] HTTP error announcing in channel {channel_id}: {exc}")
        except Exception as exc:
            print(f"[social] announce error in channel {channel_id}: {exc}")


async def setup(bot):
    await bot.add_cog(SocialNotify(bot))
