"""Moderation cog: anti-spam (rate limit), banned-words, anti-invite/link,
mass-mention & caps filters, native timeouts, warn-threshold escalation and a
role/channel whitelist.

Settings come from GET /api/bot/guilds/:id/settings/moderation (raw shape).
Warn escalation is persisted backend-side via
POST /api/bot/guilds/:id/moderation/warn.
"""

import collections
import re
import time
from datetime import timedelta

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post


SPAM_WINDOW_SECONDS = 10.0
# Only run the caps filter on messages with at least this many letters — short
# shouty words ("OK", "LOL") shouldn't trip it.
CAPS_MIN_LETTERS = 8

# Discord invite links (discord.gg/…, discord.com/invite/…, plus the short TLDs).
INVITE_RE = re.compile(
    r"(?:discord(?:app)?\.com/invite|discord\.(?:gg|io|me|li))/\S+",
    re.IGNORECASE,
)
# Any http(s) URL — used by the anti-link filter.
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = config.BACKEND_URL
        # Per-(guild_id, user_id) sliding window of message timestamps.
        self._spam_window = collections.defaultdict(collections.deque)

    async def get_settings(self, guild_id):
        return await fetch_bot_settings(
            self.backend_url, config.BOT_API_KEY, guild_id, "moderation"
        )

    # ------------------------------------------------------------------ #
    # Event
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot or message.guild is None:
                return

            settings = await self.get_settings(message.guild.id)
            if not settings or not settings.get("enabled"):
                return

            member = message.author

            # --- Whitelist: exempt roles bypass ALL moderation ---
            exempt = set(settings.get("exempt_role_ids") or [])
            if exempt and isinstance(member, discord.Member):
                if any(str(r.id) in exempt for r in member.roles):
                    return

            # --- Whitelist: ignored channels ---
            ignored = set(settings.get("ignored_channel_ids") or [])
            if str(message.channel.id) in ignored:
                return

            content = message.content or ""

            # --- Content filters (first match wins) ---
            violation = self._detect_violation(content, message, settings)
            if violation:
                reason, action = violation
                await self._safe_delete(message)
                await self._apply_action(member, action, settings, reason)
                await self._record_warn(message.guild, member, settings)
                return

            # --- Anti-spam (rate limit) — not part of warn escalation ---
            if settings.get("anti_spam_enabled"):
                await self._check_spam(message, settings)
        except Exception as exc:
            print(f"[moderation] on_message error: {exc}")

    def _detect_violation(self, content, message, settings):
        """Return (reason, action) for the first matching filter, else None."""
        content_lc = content.lower()

        banned_words = settings.get("banned_words") or []
        if banned_words and any(w and w in content_lc for w in banned_words):
            return ("banned word", settings.get("banned_word_action") or "delete")

        filter_action = settings.get("filter_action") or "delete"

        if settings.get("anti_invite") and INVITE_RE.search(content):
            return ("Discord invite link", filter_action)

        if settings.get("anti_link") and URL_RE.search(content):
            return ("external link", filter_action)

        if settings.get("anti_mention"):
            try:
                max_mentions = int(settings.get("max_mentions") or 5)
            except (TypeError, ValueError):
                max_mentions = 5
            mention_count = len(message.mentions) + len(message.role_mentions)
            if mention_count > max_mentions:
                return ("mass mention", filter_action)

        if settings.get("anti_caps") and self._is_excessive_caps(content, settings):
            return ("excessive caps", filter_action)

        return None

    def _is_excessive_caps(self, content, settings):
        letters = [c for c in content if c.isalpha()]
        if len(letters) < CAPS_MIN_LETTERS:
            return False
        try:
            threshold = int(settings.get("caps_percentage") or 70)
        except (TypeError, ValueError):
            threshold = 70
        uppercase = sum(1 for c in letters if c.isupper())
        return (uppercase / len(letters)) * 100 >= threshold

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    async def _apply_action(self, member, action, settings, reason):
        """Apply a per-message filter action. The offending message is already deleted."""
        guild = member.guild if isinstance(member, discord.Member) else None
        try:
            if action == "warn":
                await self._dm(member, f"Your message was removed: {reason}.")
            elif action == "mute":
                await self._apply_mute_role(member, settings, reason)
            elif action == "timeout":
                await self._apply_timeout(member, settings, reason)
            elif action == "kick":
                if isinstance(member, discord.Member):
                    try:
                        await member.kick(reason=f"Moderation: {reason}")
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        print(f"[moderation] kick failed: {exc}")
            # 'delete' → nothing extra (already deleted)
        except Exception as exc:
            print(f"[moderation] action handler error: {exc}")

    async def _apply_mute_role(self, member, settings, reason):
        mute_role_id = settings.get("mute_role_id")
        if not mute_role_id or not isinstance(member, discord.Member):
            return
        try:
            role = member.guild.get_role(int(mute_role_id))
            if role is not None:
                await member.add_roles(role, reason=f"Moderation: {reason}")
        except (ValueError, TypeError, discord.Forbidden, discord.HTTPException) as exc:
            print(f"[moderation] mute failed: {exc}")

    async def _apply_timeout(self, member, settings, reason):
        if not isinstance(member, discord.Member):
            return
        try:
            seconds = int(settings.get("timeout_duration") or 300)
        except (TypeError, ValueError):
            seconds = 300
        seconds = max(60, min(2419200, seconds))
        try:
            await member.timeout(timedelta(seconds=seconds), reason=f"Moderation: {reason}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[moderation] timeout failed: {exc}")

    # ------------------------------------------------------------------ #
    # Warn escalation
    # ------------------------------------------------------------------ #

    async def _record_warn(self, guild, member, settings):
        """Record a warning backend-side; escalate if the threshold is reached."""
        try:
            threshold = int(settings.get("warn_threshold") or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold <= 0:
            return  # escalation disabled — skip the backend round-trip

        result = await bot_post(
            self.backend_url,
            config.BOT_API_KEY,
            f"/api/bot/guilds/{guild.id}/moderation/warn",
            {"user_id": str(member.id)},
        )
        if not result or not result.get("threshold_reached"):
            return

        action = result.get("escalation_action") or "mute"
        await self._apply_escalation(member, action, result, settings)

    async def _apply_escalation(self, member, action, result, settings):
        if not isinstance(member, discord.Member):
            return
        reason = "Moderation: warn threshold reached"
        try:
            if action == "ban":
                await member.ban(reason=reason, delete_message_days=0)
            elif action == "kick":
                await member.kick(reason=reason)
            elif action == "timeout":
                seconds = int(result.get("timeout_duration") or settings.get("timeout_duration") or 300)
                seconds = max(60, min(2419200, seconds))
                await member.timeout(timedelta(seconds=seconds), reason=reason)
            else:  # mute
                await self._apply_mute_role(member, settings, "warn threshold reached")
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[moderation] escalation ({action}) failed: {exc}")

    # ------------------------------------------------------------------ #
    # Anti-spam
    # ------------------------------------------------------------------ #

    async def _check_spam(self, message: discord.Message, settings):
        try:
            limit = int(settings.get("max_messages_per_10s") or 5)
        except (TypeError, ValueError):
            limit = 5
        limit = max(1, min(100, limit))

        key = (message.guild.id, message.author.id)
        window = self._spam_window[key]
        now = time.monotonic()
        window.append(now)

        cutoff = now - SPAM_WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) > limit:
            await self._safe_delete(message)
            await self._dm(
                message.author,
                f"You are sending messages too quickly in {message.guild.name}. Please slow down.",
            )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _safe_delete(self, message: discord.Message):
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            print(f"[moderation] delete failed: {exc}")

    async def _dm(self, user, text):
        try:
            await user.send(text)
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(Moderation(bot))
