"""Per-guild general settings (language, timezone, default embed color).

Read from the backend's `GET /api/bot/guilds/:id/settings/general` endpoint and
cached in-memory with a short TTL. Used by cogs to tint their branded embeds
with the guild's chosen accent color (and to localize / time-format output).

The whole module is defensive: on any backend failure it returns the last cached
value or a safe default, so a missing/unreachable backend never breaks a cog.

Logging prefix: "[general]" (via utils.backend).
"""

import time

import discord

from utils.backend import bot_get

DEFAULT_COLOR = 0x5865F2
DEFAULT_LANGUAGE = "en"
DEFAULT_TIMEZONE = "UTC"
_TTL_SECONDS = 60
# guild_id (int) -> (settings_dict, fetched_at)
_CACHE = {}


def _defaults():
    return {
        "language": DEFAULT_LANGUAGE,
        "timezone": DEFAULT_TIMEZONE,
        "embed_color": "#5865F2",
        "dashboard_theme": "dark",
    }


async def get_settings(backend_url, api_key, guild_id):
    """Return the guild's general settings dict (cached, never raises)."""
    gid = int(guild_id)
    now = time.time()
    cached = _CACHE.get(gid)
    if cached and now - cached[1] < _TTL_SECONDS:
        return cached[0]
    data = await bot_get(backend_url, api_key, f"/api/bot/guilds/{gid}/settings/general")
    if isinstance(data, dict):
        settings = {
            "language": data.get("language") or DEFAULT_LANGUAGE,
            "timezone": data.get("timezone") or DEFAULT_TIMEZONE,
            "embed_color": data.get("embed_color") or "#5865F2",
            "dashboard_theme": data.get("dashboard_theme") or "dark",
        }
        _CACHE[gid] = (settings, now)
        return settings
    if cached:
        return cached[0]
    return _defaults()


def _hex_to_int(value, fallback=DEFAULT_COLOR):
    if isinstance(value, str):
        s = value.strip().lstrip("#")
        if len(s) == 6:
            try:
                return int(s, 16)
            except ValueError:
                pass
    return fallback


async def get_embed_color(backend_url, api_key, guild_id, fallback=DEFAULT_COLOR):
    """Return the guild's default embed color as a discord.Color (cached).

    `fallback` (an int like 0x5865F2) is used when the backend is unreachable or
    the stored value is invalid — pass the cog's previous hardcoded color so the
    look is unchanged when general settings can't be read.
    """
    settings = await get_settings(backend_url, api_key, guild_id)
    return discord.Color(_hex_to_int(settings.get("embed_color"), fallback))


async def get_language(backend_url, api_key, guild_id):
    settings = await get_settings(backend_url, api_key, guild_id)
    return settings.get("language") or DEFAULT_LANGUAGE


async def get_timezone(backend_url, api_key, guild_id):
    settings = await get_settings(backend_url, api_key, guild_id)
    return settings.get("timezone") or DEFAULT_TIMEZONE


def invalidate(guild_id=None):
    if guild_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(int(guild_id), None)
