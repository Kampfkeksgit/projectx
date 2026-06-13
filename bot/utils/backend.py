"""Shared helper for bot cogs to talk to the backend's /api/bot/* endpoints."""

import aiohttp


DEFAULT_PUT_TIMEOUT_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 10


async def fetch_bot_settings(backend_url, api_key, guild_id, module):
    """GET {backend_url}/api/bot/guilds/{guild_id}/settings[/{module}] with X-Bot-Token.

    Args:
        backend_url: Base URL of the backend, e.g. 'http://localhost:3000'.
        api_key: Shared secret matching the backend's BOT_API_KEY.
        guild_id: Discord guild ID (int or str).
        module: One of 'autorole' | 'logs' | 'moderation' (or any future
            bot-internal module slug). Pass None or '' to hit the top-level
            Welcome/Leave endpoint at /api/bot/guilds/{guild_id}/settings.

    Returns:
        Parsed JSON dict on success, or None on any failure (network error,
        non-200 status, timeout, JSON decode error). Caller should handle None
        gracefully (typically: silently skip the event).
    """
    headers = {"X-Bot-Token": api_key or ""}
    base = f"{backend_url}/api/bot/guilds/{guild_id}/settings"
    url = f"{base}/{module}" if module else base
    label = module or "welcome_leave"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                print(f"[bot/backend] {label} settings: HTTP {resp.status}")
    except Exception as exc:
        print(f"[bot/backend] failed to fetch {label} settings for {guild_id}: {exc}")
    return None


async def bot_put(backend_url, api_key, path, json_body, timeout=DEFAULT_PUT_TIMEOUT_SECONDS):
    """PUT {backend_url}{path} with X-Bot-Token + JSON body.

    Args:
        backend_url: Base URL of the backend, e.g. 'http://localhost:3000'.
        api_key: Shared secret matching the backend's BOT_API_KEY.
        path: Backend path starting with '/' (e.g. '/api/bot/guilds/123/channels').
        json_body: dict to send as JSON.
        timeout: Total request timeout in seconds (default 10).

    Returns:
        Parsed JSON dict on success, or None on any failure (network error,
        non-2xx status, timeout, JSON decode error). Caller logs/handles None.
    """
    if not backend_url:
        print("[bot/backend] PUT skipped: BACKEND_URL missing")
        return None
    if not api_key:
        print("[bot/backend] PUT skipped: BOT_API_KEY missing")
        return None

    url = f"{backend_url.rstrip('/')}{path}"
    headers = {"X-Bot-Token": api_key}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(
                url,
                json=json_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if 200 <= resp.status < 300:
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
                body = await resp.text()
                print(f"[bot/backend] PUT {path}: HTTP {resp.status} — {body[:200]}")
    except Exception as exc:
        print(f"[bot/backend] PUT {path} failed: {exc}")
    return None


async def bot_post(backend_url, api_key, path, json_body, timeout=DEFAULT_TIMEOUT_SECONDS):
    """POST {backend_url}{path} with X-Bot-Token + JSON body.

    Args:
        backend_url: Base URL of the backend, e.g. 'http://localhost:3000'.
        api_key: Shared secret matching the backend's BOT_API_KEY.
        path: Backend path starting with '/' (e.g. '/api/bot/guilds/123/leveling/xp').
        json_body: dict to send as JSON.
        timeout: Total request timeout in seconds (default 10).

    Returns:
        Parsed JSON dict on success, or None on any failure (network error,
        non-2xx status, timeout, JSON decode error). Caller logs/handles None.
    """
    if not backend_url:
        print("[bot/backend] POST skipped: BACKEND_URL missing")
        return None
    if not api_key:
        print("[bot/backend] POST skipped: BOT_API_KEY missing")
        return None

    url = f"{backend_url.rstrip('/')}{path}"
    headers = {"X-Bot-Token": api_key}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=json_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if 200 <= resp.status < 300:
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
                body = await resp.text()
                print(f"[bot/backend] POST {path}: HTTP {resp.status} — {body[:200]}")
    except Exception as exc:
        print(f"[bot/backend] POST {path} failed: {exc}")
    return None


async def bot_delete(backend_url, api_key, path, timeout=DEFAULT_TIMEOUT_SECONDS):
    """DELETE {backend_url}{path} with X-Bot-Token.

    Returns parsed JSON dict (or {}) on success, or None on any failure.
    """
    if not backend_url:
        print("[bot/backend] DELETE skipped: BACKEND_URL missing")
        return None
    if not api_key:
        print("[bot/backend] DELETE skipped: BOT_API_KEY missing")
        return None

    url = f"{backend_url.rstrip('/')}{path}"
    headers = {"X-Bot-Token": api_key}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if 200 <= resp.status < 300:
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
                body = await resp.text()
                print(f"[bot/backend] DELETE {path}: HTTP {resp.status} — {body[:200]}")
    except Exception as exc:
        print(f"[bot/backend] DELETE {path} failed: {exc}")
    return None


async def bot_get(backend_url, api_key, path, timeout=DEFAULT_TIMEOUT_SECONDS):
    """GET {backend_url}{path} with X-Bot-Token.

    Args:
        backend_url: Base URL of the backend, e.g. 'http://localhost:3000'.
        api_key: Shared secret matching the backend's BOT_API_KEY.
        path: Backend path starting with '/' (e.g. '/api/bot/guilds/123/reaction-roles').
        timeout: Total request timeout in seconds (default 10).

    Returns:
        Parsed JSON dict on success, or None on any failure (network error,
        non-2xx status, timeout, JSON decode error). Caller logs/handles None.
    """
    if not backend_url:
        print("[bot/backend] GET skipped: BACKEND_URL missing")
        return None
    if not api_key:
        print("[bot/backend] GET skipped: BOT_API_KEY missing")
        return None

    url = f"{backend_url.rstrip('/')}{path}"
    headers = {"X-Bot-Token": api_key}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if 200 <= resp.status < 300:
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
                body = await resp.text()
                print(f"[bot/backend] GET {path}: HTTP {resp.status} — {body[:200]}")
    except Exception as exc:
        print(f"[bot/backend] GET {path} failed: {exc}")
    return None
