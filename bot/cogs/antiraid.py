"""Anti-Raid cog.

Two protections, both event-driven on member join:
  - Account-age gate: members whose account is younger than the configured
    minimum are actioned (alert / kick / ban).
  - Join-rate burst detection: if more than N members join within S seconds, the
    burst is treated as a raid and actioned.

Backend contract (X-Bot-Token auth):
  GET /api/bot/guilds/{gid}/settings/antiraid
      → { enabled, join_rate_count, join_rate_seconds, action, account_age_days, alert_channel_id }

Logging prefix: "[antiraid]".
"""

import time
from collections import deque, defaultdict

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings


SETTINGS_TTL_SECONDS = 120
RAID_COOLDOWN_SECONDS = 30
ALERT_COLOR = 0xEF4444


class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}                       # guild_id (str) -> (settings, fetched_at)
        self._joins = defaultdict(lambda: deque())      # guild_id (int) -> deque[(ts, member)]
        self._raid_until = {}                           # guild_id (int) -> cooldown expiry ts

    async def _get_settings(self, guild_id):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "antiraid")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        settings = await self._get_settings(member.guild.id)
        if not settings or not settings.get("enabled"):
            return

        action = settings.get("action") or "alert"

        # 1) Account-age gate.
        min_days = int(settings.get("account_age_days") or 0)
        if min_days > 0:
            age_days = (discord.utils.utcnow() - member.created_at).days
            if age_days < min_days:
                await self._act_on_member(member, action, f"account only {age_days}d old (min {min_days}d)")
                await self._alert(member.guild, settings,
                                  f"🚨 {member} blocked — account age {age_days}d below minimum {min_days}d.")
                return

        # 2) Join-rate burst detection.
        count = int(settings.get("join_rate_count") or 5)
        window = int(settings.get("join_rate_seconds") or 10)
        now = time.time()
        q = self._joins[member.guild.id]
        q.append((now, member))
        while q and now - q[0][0] > window:
            q.popleft()

        if len(q) >= count and now >= self._raid_until.get(member.guild.id, 0):
            self._raid_until[member.guild.id] = now + RAID_COOLDOWN_SECONDS
            burst = [m for _, m in q]
            await self._alert(member.guild, settings,
                              f"🚨 Possible raid: {len(burst)} joins in {window}s. Action: **{action}**.")
            if action in ("kick", "ban"):
                for m in burst:
                    await self._act_on_member(m, action, "raid burst")

    async def _act_on_member(self, member, action, reason):
        try:
            if action == "kick":
                await member.kick(reason=f"Anti-Raid: {reason}")
            elif action == "ban":
                await member.ban(reason=f"Anti-Raid: {reason}", delete_message_days=1)
        except discord.Forbidden:
            print(f"[antiraid] missing permission to {action} in {member.guild.id}")
        except Exception as exc:
            print(f"[antiraid] {action} failed in {member.guild.id}: {exc}")

    async def _alert(self, guild, settings, text):
        channel_id = settings.get("alert_channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            return
        try:
            embed = discord.Embed(description=text, color=ALERT_COLOR, timestamp=discord.utils.utcnow())
            embed.set_author(name="Anti-Raid")
            await channel.send(embed=embed)
        except Exception as exc:
            print(f"[antiraid] alert failed in {guild.id}: {exc}")


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
