"""Per-guild command config (custom prefix + disabled built-in commands).

Read from the backend's `GET /api/bot/guilds/:id/commands` endpoint and cached
in-memory with a short TTL. Used by main.py's dynamic prefix resolver and the
global command gates (prefix + slash).
"""

import time

from utils.backend import bot_get

DEFAULT_PREFIX = "!"
_TTL_SECONDS = 60
# guild_id (int) -> (config_dict, fetched_at)
_CACHE = {}


async def get_config(backend_url, api_key, guild_id):
    """Return { 'prefix': str, 'disabled': [keys] } for a guild (cached).

    On any backend failure returns the last cached value if present, otherwise a
    safe default (prefix '!', nothing disabled) — the bot never breaks on a
    missing/unreachable backend.
    """
    gid = int(guild_id)
    now = time.time()
    cached = _CACHE.get(gid)
    if cached and now - cached[1] < _TTL_SECONDS:
        return cached[0]
    data = await bot_get(backend_url, api_key, f"/api/bot/guilds/{gid}/commands")
    if isinstance(data, dict):
        cfg = {
            "prefix": data.get("prefix") or DEFAULT_PREFIX,
            "disabled": set(data.get("disabled") or []),
        }
        _CACHE[gid] = (cfg, now)
        return cfg
    if cached:
        return cached[0]
    return {"prefix": DEFAULT_PREFIX, "disabled": set()}


async def get_prefix(backend_url, api_key, guild_id):
    cfg = await get_config(backend_url, api_key, guild_id)
    return cfg.get("prefix") or DEFAULT_PREFIX


async def is_disabled(backend_url, api_key, guild_id, command_name):
    cfg = await get_config(backend_url, api_key, guild_id)
    return command_name in cfg.get("disabled", set())


def invalidate(guild_id=None):
    if guild_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(int(guild_id), None)
