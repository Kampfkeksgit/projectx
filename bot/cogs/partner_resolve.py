"""Partner-resolve cog.

The owner adds a partner (for the public /partners page) as either a Discord USER
(by id) or a partner GUILD (by invite link). The backend can't ask the bot
synchronously, so this cog polls for unresolved partners and resolves each:

  - kind='user'  → fetch_user(discord_id) → username + display name + avatar.
  - kind='guild' → fetch_invite(invite_url) → guild name + icon + member count
                   + guild id. Works even when the bot isn't a member of that
                   guild (that's the whole point of a partner server).

It fills name/avatar only when the admin left them empty (the backend guards
that), and sets resolved_name as the "resolved" marker so each partner resolves
once. Changing the id/invite in the dashboard clears the marker → re-resolve.

Backend contract (X-Bot-Token auth):
  GET /api/bot/partners/unresolved     → { partners: [{ id, kind, discord_id, invite_url }] }
  PUT /api/bot/partners/{id}/resolved  body { resolved_name, name, avatar_url, guild_id?, member_count? }

Logging prefix: "[partner]".
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put


RESOLVE_INTERVAL_MINUTES = 5


class PartnerResolve(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.resolve_loop.start()

    def cog_unload(self):
        self.resolve_loop.cancel()

    @tasks.loop(minutes=RESOLVE_INTERVAL_MINUTES)
    async def resolve_loop(self):
        await self._resolve()

    @resolve_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _resolve(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/partners/unresolved")
        for p in (data or {}).get("partners", []) or []:
            pid = p.get("id")
            kind = p.get("kind") or "user"
            if not pid:
                continue
            if kind == "guild":
                payload = await self._resolve_guild(p.get("invite_url") or "")
            else:
                payload = await self._resolve_user(str(p.get("discord_id") or ""))
            if payload is None:
                continue  # transient error → retry next loop
            await bot_put(
                self.backend_url, self.api_key,
                f"/api/bot/partners/{pid}/resolved", payload,
            )

    async def _resolve_user(self, discord_id):
        if not discord_id.isdigit():
            return None
        try:
            user = await self.bot.fetch_user(int(discord_id))
        except discord.NotFound:
            # Invalid id → still mark resolved so we don't retry forever.
            return {"resolved_name": "unknown", "name": "", "avatar_url": ""}
        except Exception as exc:
            print(f"[partner] user resolve failed for {discord_id}: {exc}")
            return None  # transient (rate limit etc.)
        return {
            "resolved_name": user.name,
            "name": getattr(user, "global_name", None) or user.name,
            "avatar_url": str(user.display_avatar.url),
        }

    async def _resolve_guild(self, invite_url):
        if not invite_url:
            return None
        try:
            invite = await self.bot.fetch_invite(invite_url, with_counts=True)
        except discord.NotFound:
            # Invalid / expired invite → mark resolved so we stop retrying.
            return {"resolved_name": "unknown", "name": "", "avatar_url": ""}
        except Exception as exc:
            print(f"[partner] guild resolve failed for {invite_url}: {exc}")
            return None  # transient
        guild = invite.guild
        if guild is None:
            return {"resolved_name": "unknown", "name": "", "avatar_url": ""}
        icon = str(guild.icon.url) if getattr(guild, "icon", None) else ""
        members = getattr(invite, "approximate_member_count", None) or 0
        return {
            "resolved_name": guild.name,
            "name": guild.name,
            "avatar_url": icon,
            "guild_id": str(guild.id),
            "member_count": int(members),
        }


async def setup(bot):
    await bot.add_cog(PartnerResolve(bot))
