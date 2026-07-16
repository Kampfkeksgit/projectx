"""Per-guild bot profile cog.

Lets an admin set the bot's NICKNAME and AVATAR just for one guild (Discord
supports server-specific bot profiles via PATCH /guilds/{id}/members/@me, exposed
in discord.py as ``guild.me.edit(nick=..., avatar=...)``).

The dashboard writes the desired nickname/avatar to the backend and marks the row
dirty. This cog polls the changed profiles, applies them and writes back a status
code so the dashboard can show success / a clear error.

Backend contract (X-Bot-Token auth):
  GET /api/bot/botprofile/pending              → { profiles: [{ guild_id, nickname, avatar_url }] }
  PUT /api/bot/guilds/{id}/botprofile/applied  body { status: 'ok'|'error', status_message }

status_message is a short CODE (the dashboard translates it):
  nick_forbidden, avatar_forbidden, avatar_download_failed, avatar_too_large,
  avatar_rate_limited, not_in_guild, error

Nickname: empty resets to the default bot name. Avatar: empty resets to the global
avatar. The bot needs the "Change Nickname" permission for the nickname part.

Logging prefix: "[botprofile]".
"""

import aiohttp
import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put


# Discord's avatar upload limit is ~10 MB; stay a bit under to be safe.
MAX_AVATAR_BYTES = 10 * 1024 * 1024


class BotProfile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.apply_loop.start()

    def cog_unload(self):
        self.apply_loop.cancel()

    @tasks.loop(seconds=config.BOT_PROFILE_POLL_INTERVAL)
    async def apply_loop(self):
        await self._apply()

    @apply_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _apply(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/botprofile/pending")
        for p in (data or {}).get("profiles", []) or []:
            gid = str(p.get("guild_id") or "")
            if not gid.isdigit():
                continue
            guild = self.bot.get_guild(int(gid))
            if guild is None:
                # Bot isn't in this guild (yet) — leave it dirty and retry later.
                continue
            errors = await self._apply_one(guild, p.get("nickname") or "", p.get("avatar_url") or "")
            status = "error" if errors else "ok"
            await bot_put(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{gid}/botprofile/applied",
                {"status": status, "status_message": ",".join(errors)[:300]},
            )

    async def _apply_one(self, guild, nickname, avatar_url):
        """Apply nick + avatar to the bot's own member in this guild. Returns error codes."""
        errors = []
        me = guild.me
        if me is None:
            return ["not_in_guild"]

        # --- Nickname (empty → reset to default) ---
        try:
            await me.edit(nick=(nickname or None))
        except discord.Forbidden:
            errors.append("nick_forbidden")
        except discord.HTTPException as exc:
            print(f"[botprofile] nick edit failed in {guild.id}: {exc}")
            errors.append("error")

        # --- Avatar (empty → reset to global) ---
        try:
            if avatar_url:
                img = await self._download(avatar_url)
                if img == "too_large":
                    errors.append("avatar_too_large")
                elif img is None:
                    errors.append("avatar_download_failed")
                else:
                    await me.edit(avatar=img)
            else:
                await me.edit(avatar=None)
        except discord.Forbidden:
            errors.append("avatar_forbidden")
        except discord.HTTPException as exc:
            # 429 = rate limited (avatar changes are heavily throttled by Discord).
            if getattr(exc, "status", None) == 429:
                errors.append("avatar_rate_limited")
            else:
                print(f"[botprofile] avatar edit failed in {guild.id}: {exc}")
                errors.append("error")
        return errors

    async def _download(self, url):
        """Download an image. Returns bytes, 'too_large', or None on failure."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    ctype = (resp.headers.get("Content-Type") or "").lower()
                    if not ctype.startswith("image/"):
                        return None
                    clen = resp.headers.get("Content-Length")
                    if clen and int(clen) > MAX_AVATAR_BYTES:
                        return "too_large"
                    data = await resp.content.read(MAX_AVATAR_BYTES + 1)
                    if len(data) > MAX_AVATAR_BYTES:
                        return "too_large"
                    return data
        except Exception as exc:
            print(f"[botprofile] download failed for {url}: {exc}")
            return None


async def setup(bot):
    await bot.add_cog(BotProfile(bot))
