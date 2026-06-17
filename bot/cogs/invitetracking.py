"""Invite-tracking cog (Premium: Basic).

Caches each guild's invite use-counts and, on member join, diffs them to attribute
the join to whichever invite code grew — then announces it and records the join so
the dashboard can show an invite leaderboard.

Requires the MANAGE_GUILD permission to read invites (gracefully no-ops without it).

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/invitetracking → { enabled, log_channel_id, message_template }
  GET  /api/bot/guilds/{gid}/invites                  → { invites: [{ code, inviter_id, uses }] }
  PUT  /api/bot/guilds/{gid}/invites                  body { invites: [...] }
  POST /api/bot/guilds/{gid}/invites/join             body { user_id, inviter_id, code } → { inviter_invites }

Logging prefix: "[invites]".
"""

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_put, bot_post


class InviteTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # guild_id(str) -> { code: uses }
        self._cache = {}

    async def _snapshot(self, guild):
        """Fetch current invite uses for a guild; returns { code: uses } or None."""
        try:
            invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            return None
        snap = {}
        payload = []
        for inv in invites:
            snap[inv.code] = inv.uses or 0
            payload.append({"code": inv.code, "inviter_id": str(inv.inviter.id) if inv.inviter else None, "uses": inv.uses or 0})
        # Persist the snapshot so detection survives restarts.
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/invites", {"invites": payload})
        return snap

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            settings = await fetch_bot_settings(self.backend_url, self.api_key, guild.id, "invitetracking")
            if not settings or not settings.get("enabled"):
                continue
            snap = await self._snapshot(guild)
            if snap is not None:
                self._cache[str(guild.id)] = snap

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild is None:
            return
        cache = self._cache.setdefault(str(invite.guild.id), {})
        cache[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild is None:
            return
        self._cache.get(str(invite.guild.id), {}).pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild.id, "invitetracking")
        if not settings or not settings.get("enabled"):
            return

        before = self._cache.get(str(guild.id), {})
        used_code = None
        inviter_id = None
        try:
            current = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            current = None

        if current is not None:
            now_map = {}
            for inv in current:
                now_map[inv.code] = inv.uses or 0
                if (inv.uses or 0) > before.get(inv.code, 0) and used_code is None:
                    used_code = inv.code
                    inviter_id = str(inv.inviter.id) if inv.inviter else None
            self._cache[str(guild.id)] = now_map

        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild.id}/invites/join",
            {"user_id": str(member.id), "inviter_id": inviter_id, "code": used_code},
        )
        invites_total = (result or {}).get("inviter_invites", 0)

        channel_id = settings.get("log_channel_id")
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if channel is None:
            return
        inviter_txt = f"<@{inviter_id}>" if inviter_id else "an unknown source"
        template = settings.get("message_template") or "👋 {user} joined — invited by {inviter} (now {invites} invites)"
        text = (template
                .replace("{user}", member.mention)
                .replace("{inviter}", inviter_txt)
                .replace("{invites}", str(invites_total))
                .replace("{code}", used_code or "—"))
        try:
            await channel.send(text[:2000])
        except Exception as exc:
            print(f"[invites] announce failed in {guild.id}: {exc}")


async def setup(bot):
    await bot.add_cog(InviteTracking(bot))
