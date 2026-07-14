"""Server-Logs cog: posts embeds for configured events to log channels.

Log text is deliberately English (admin audit trail — see CLAUDE.md); only the
dashboard UI is translated. v50 adds per-category log channels, actor filters
(ignored roles/users/bots), an audit-log "who did it" executor lookup and seven
new event types (invites/threads/emojis/bulk-delete/boosts/automod/webhooks).
"""

from datetime import datetime, timezone

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings
from utils.ratelimit import safe_send


COLOR_GREEN = 0x2ECC71
COLOR_RED = 0xE74C3C
COLOR_AMBER = 0xF1C40F
COLOR_GREY = 0x95A5A6
COLOR_BLURPLE = 0x5865F2

# How far back (seconds) an audit-log entry may be to count as "this event".
AUDIT_WINDOW = 12

# Which per-category channel field an event routes to. Each falls back to the
# base log_channel_id when its category channel is unset.
CATEGORY_CHANNEL_KEY = {
    "member": "member_log_channel_id",
    "message": "message_log_channel_id",
    "voice": "voice_log_channel_id",
    "server": "server_log_channel_id",
}


def _truncate(s, limit=1024):
    if s is None:
        return "(empty)"
    s = str(s)
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


class ServerLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = config.BACKEND_URL

    async def get_settings(self, guild_id):
        return await fetch_bot_settings(
            self.backend_url, config.BOT_API_KEY, guild_id, "logs"
        )

    # ------------------------------------------------------------------ #
    # Channel resolution + filters
    # ------------------------------------------------------------------ #

    def _channel_id_for(self, settings, category):
        """Category channel if set, else the base log channel."""
        key = CATEGORY_CHANNEL_KEY.get(category)
        cid = settings.get(key) if key else None
        return cid or settings.get("log_channel_id")

    async def _resolve_log_channel(self, guild, settings, flag_key, category="member"):
        """Return the target channel if logging is enabled and the event flag is on."""
        if not settings or not settings.get("enabled"):
            return None
        if not settings.get(flag_key):
            return None
        channel_id = self._channel_id_for(settings, category)
        if not channel_id:
            return None
        try:
            return guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_ignored(settings, channel_id):
        """True if the channel is in log_ignored_channel_ids (skip message logging)."""
        ignored = set(settings.get("log_ignored_channel_ids") or [])
        return str(channel_id) in ignored

    @staticmethod
    def _is_actor_ignored(settings, user):
        """True if the event's actor should be filtered (ignored bot/user/role)."""
        if user is None:
            return False
        if settings.get("ignore_bots") and getattr(user, "bot", False):
            return True
        ignored_users = set(settings.get("ignored_user_ids") or [])
        if str(getattr(user, "id", "")) in ignored_users:
            return True
        ignored_roles = set(settings.get("ignored_role_ids") or [])
        if ignored_roles:
            member_roles = getattr(user, "roles", None)
            if member_roles:
                for role in member_roles:
                    if str(role.id) in ignored_roles:
                        return True
        return False

    async def _find_executor(self, guild, action, target_id=None):
        """Best-effort: who performed an action, via the audit log. None if unknown."""
        try:
            me = guild.me
            if me is None or not me.guild_permissions.view_audit_log:
                return None
            now = datetime.now(timezone.utc)
            async for entry in guild.audit_logs(limit=6, action=action):
                if (now - entry.created_at).total_seconds() > AUDIT_WINDOW:
                    break  # entries are newest-first; older than the window → stop
                if target_id is not None:
                    tid = getattr(entry.target, "id", None)
                    if tid is not None and int(tid) != int(target_id):
                        continue
                return entry.user
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            return None
        return None

    async def _maybe_executor(self, guild, settings, action, target_id=None):
        if not settings.get("show_executor"):
            return None
        return await self._find_executor(guild, action, target_id)

    @staticmethod
    def _apply_executor(embed, executor):
        if executor is not None:
            embed.add_field(
                name="Performed by",
                value=f"{executor.mention} (`{executor.id}`)",
                inline=False,
            )

    async def _post(self, channel, embed):
        try:
            # Paced through the per-channel rate-limit cache so bulk events
            # (e.g. a backup restore creating many channels/roles) don't flood
            # the log channel and trigger 429s.
            await safe_send(channel, embed=embed)
        except discord.Forbidden:
            print(f"[logs] missing permissions in #{channel}")
        except discord.HTTPException as exc:
            print(f"[logs] HTTP error: {exc}")

    # ------------------------------------------------------------------ #
    # Member events (member category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            settings = await self.get_settings(member.guild.id)
            channel = await self._resolve_log_channel(member.guild, settings, "log_joins", "member")
            if not channel:
                return
            if self._is_actor_ignored(settings, member):
                return
            created = int(member.created_at.timestamp())
            embed = discord.Embed(
                title="Member joined",
                description=f"{member.mention} joined the server.",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
            embed.add_field(name="Account created", value=f"<t:{created}:R>", inline=True)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_join error: {exc}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            settings = await self.get_settings(member.guild.id)
            channel = await self._resolve_log_channel(member.guild, settings, "log_leaves", "member")
            if not channel:
                return
            if self._is_actor_ignored(settings, member):
                return
            # Distinguish a kick from a voluntary leave via the audit log.
            executor = await self._maybe_executor(
                member.guild, settings, discord.AuditLogAction.kick, member.id
            )
            if executor is not None:
                embed = discord.Embed(
                    title="Member kicked",
                    description=f"{member} was kicked.",
                    color=COLOR_RED,
                    timestamp=datetime.now(timezone.utc),
                )
            else:
                embed = discord.Embed(
                    title="Member left",
                    description=f"{member} left the server.",
                    color=COLOR_RED,
                    timestamp=datetime.now(timezone.utc),
                )
            embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
            self._apply_executor(embed, executor)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_remove error: {exc}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        try:
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_member_bans", "member")
            if not channel:
                return
            if self._is_actor_ignored(settings, user):
                return
            executor = await self._maybe_executor(
                guild, settings, discord.AuditLogAction.ban, user.id
            )
            embed = discord.Embed(
                title="Member banned",
                description=f"{user} was banned.",
                color=COLOR_RED,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
            self._apply_executor(embed, executor)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_ban error: {exc}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user):
        try:
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_member_unbans", "member")
            if not channel:
                return
            executor = await self._maybe_executor(
                guild, settings, discord.AuditLogAction.unban, user.id
            )
            embed = discord.Embed(
                title="Member unbanned",
                description=f"{user} was unbanned.",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
            self._apply_executor(embed, executor)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_unban error: {exc}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            settings = await self.get_settings(after.guild.id)
            if not settings or not settings.get("enabled"):
                return
            if self._is_actor_ignored(settings, after):
                return

            # --- Boosts (own toggle + channel) ---
            if before.premium_since != after.premium_since:
                bchannel = await self._resolve_log_channel(after.guild, settings, "log_boosts", "member")
                if bchannel:
                    if after.premium_since is not None and before.premium_since is None:
                        embed = discord.Embed(
                            title="Server boosted",
                            description=f"{after.mention} started boosting the server. 🎉",
                            color=COLOR_BLURPLE,
                            timestamp=datetime.now(timezone.utc),
                        )
                    elif after.premium_since is None and before.premium_since is not None:
                        embed = discord.Embed(
                            title="Boost removed",
                            description=f"{after.mention} stopped boosting the server.",
                            color=COLOR_GREY,
                            timestamp=datetime.now(timezone.utc),
                        )
                    else:
                        embed = None
                    if embed is not None:
                        embed.add_field(name="User", value=f"{after} (`{after.id}`)", inline=False)
                        await self._post(bchannel, embed)

            # --- Role / nickname / timeout changes (member_updates toggle) ---
            channel = await self._resolve_log_channel(after.guild, settings, "log_member_updates", "member")
            if not channel:
                return

            before_roles = set(before.roles)
            after_roles = set(after.roles)
            added = [r for r in after_roles - before_roles]
            removed = [r for r in before_roles - after_roles]
            if added or removed:
                embed = discord.Embed(
                    title="Member roles updated",
                    color=COLOR_GREY,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)
                if added:
                    embed.add_field(name="Added", value=_truncate(", ".join(r.mention for r in added), 1024), inline=False)
                if removed:
                    embed.add_field(name="Removed", value=_truncate(", ".join(r.mention for r in removed), 1024), inline=False)
                executor = await self._maybe_executor(
                    after.guild, settings, discord.AuditLogAction.member_role_update, after.id
                )
                self._apply_executor(embed, executor)
                await self._post(channel, embed)

            if before.nick != after.nick:
                embed = discord.Embed(
                    title="Nickname changed",
                    color=COLOR_GREY,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)
                embed.add_field(name="Before", value=_truncate(before.nick or "(none)", 256), inline=True)
                embed.add_field(name="After", value=_truncate(after.nick or "(none)", 256), inline=True)
                await self._post(channel, embed)

            if before.timed_out_until != after.timed_out_until:
                if after.timed_out_until is not None:
                    embed = discord.Embed(
                        title="Member timed out",
                        description=f"Until <t:{int(after.timed_out_until.timestamp())}:F>",
                        color=COLOR_AMBER,
                        timestamp=datetime.now(timezone.utc),
                    )
                else:
                    embed = discord.Embed(
                        title="Member timeout removed",
                        color=COLOR_GREEN,
                        timestamp=datetime.now(timezone.utc),
                    )
                embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=False)
                executor = await self._maybe_executor(
                    after.guild, settings, discord.AuditLogAction.member_update, after.id
                )
                self._apply_executor(embed, executor)
                await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_update error: {exc}")

    # ------------------------------------------------------------------ #
    # Message events (message category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        try:
            if message.guild is None:
                return
            settings = await self.get_settings(message.guild.id)
            channel = await self._resolve_log_channel(
                message.guild, settings, "log_message_deletes", "message"
            )
            if not channel:
                return
            if self._is_ignored(settings, message.channel.id):
                return
            if self._is_actor_ignored(settings, message.author):
                return
            executor = await self._maybe_executor(
                message.guild, settings, discord.AuditLogAction.message_delete,
                getattr(message.author, "id", None),
            )
            embed = discord.Embed(
                title="Message deleted",
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Author",
                value=f"{message.author.mention} (`{message.author.id}`)",
                inline=True,
            )
            embed.add_field(
                name="Channel",
                value=getattr(message.channel, "mention", "#unknown"),
                inline=True,
            )
            embed.add_field(
                name="Content",
                value=_truncate(message.content or "(no text content)", 1024),
                inline=False,
            )
            self._apply_executor(embed, executor)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_message_delete error: {exc}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        try:
            if after.guild is None:
                return
            if (before.content or "") == (after.content or ""):
                return
            settings = await self.get_settings(after.guild.id)
            channel = await self._resolve_log_channel(
                after.guild, settings, "log_message_edits", "message"
            )
            if not channel:
                return
            if self._is_ignored(settings, after.channel.id):
                return
            if self._is_actor_ignored(settings, after.author):
                return
            embed = discord.Embed(
                title="Message edited",
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Author",
                value=f"{after.author.mention} (`{after.author.id}`)",
                inline=True,
            )
            embed.add_field(
                name="Channel",
                value=getattr(after.channel, "mention", "#unknown"),
                inline=True,
            )
            embed.add_field(name="Before", value=_truncate(before.content, 1024), inline=False)
            embed.add_field(name="After", value=_truncate(after.content, 1024), inline=False)
            if getattr(after, "jump_url", None):
                embed.add_field(name="Jump", value=f"[Go to message]({after.jump_url})", inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_message_edit error: {exc}")

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        try:
            if not messages:
                return
            first = messages[0]
            if first.guild is None:
                return
            settings = await self.get_settings(first.guild.id)
            channel = await self._resolve_log_channel(
                first.guild, settings, "log_bulk_delete", "message"
            )
            if not channel:
                return
            if self._is_ignored(settings, first.channel.id):
                return
            embed = discord.Embed(
                title="Bulk message delete",
                description=f"{len(messages)} messages were deleted.",
                color=COLOR_RED,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Channel",
                value=getattr(first.channel, "mention", "#unknown"),
                inline=True,
            )
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_bulk_message_delete error: {exc}")

    # ------------------------------------------------------------------ #
    # Channel events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._log_channel_event(channel.guild, "Channel created", channel, COLOR_GREEN,
                                      discord.AuditLogAction.channel_create)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self._log_channel_event(channel.guild, "Channel deleted", channel, COLOR_RED,
                                      discord.AuditLogAction.channel_delete)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        try:
            if before.name == after.name:
                return  # only log renames; ignore permission/topic churn
            settings = await self.get_settings(after.guild.id)
            log_channel = await self._resolve_log_channel(after.guild, settings, "log_channels", "server")
            if not log_channel:
                return
            executor = await self._maybe_executor(
                after.guild, settings, discord.AuditLogAction.channel_update, after.id
            )
            embed = discord.Embed(
                title="Channel renamed",
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Before", value=_truncate(before.name, 256), inline=True)
            embed.add_field(name="After", value=_truncate(after.name, 256), inline=True)
            self._apply_executor(embed, executor)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] on_guild_channel_update error: {exc}")

    async def _log_channel_event(self, guild, title, channel, color, action):
        try:
            settings = await self.get_settings(guild.id)
            log_channel = await self._resolve_log_channel(guild, settings, "log_channels", "server")
            if not log_channel:
                return
            executor = await self._maybe_executor(guild, settings, action, channel.id)
            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Channel", value=f"{getattr(channel, 'name', 'unknown')} (`{channel.id}`)", inline=False)
            self._apply_executor(embed, executor)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] channel event error: {exc}")

    # ------------------------------------------------------------------ #
    # Role events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self._log_role_event(role.guild, "Role created", role, COLOR_GREEN,
                                   discord.AuditLogAction.role_create)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self._log_role_event(role.guild, "Role deleted", role, COLOR_RED,
                                   discord.AuditLogAction.role_delete)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        try:
            if before.name == after.name:
                return
            settings = await self.get_settings(after.guild.id)
            log_channel = await self._resolve_log_channel(after.guild, settings, "log_roles", "server")
            if not log_channel:
                return
            executor = await self._maybe_executor(
                after.guild, settings, discord.AuditLogAction.role_update, after.id
            )
            embed = discord.Embed(
                title="Role renamed",
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Before", value=_truncate(before.name, 256), inline=True)
            embed.add_field(name="After", value=_truncate(after.name, 256), inline=True)
            self._apply_executor(embed, executor)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] on_guild_role_update error: {exc}")

    async def _log_role_event(self, guild, title, role, color, action):
        try:
            settings = await self.get_settings(guild.id)
            log_channel = await self._resolve_log_channel(guild, settings, "log_roles", "server")
            if not log_channel:
                return
            executor = await self._maybe_executor(guild, settings, action, role.id)
            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Role", value=f"{role.name} (`{role.id}`)", inline=False)
            self._apply_executor(embed, executor)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] role event error: {exc}")

    # ------------------------------------------------------------------ #
    # Invite events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        try:
            guild = invite.guild
            if guild is None:
                return
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_invites", "server")
            if not channel:
                return
            embed = discord.Embed(
                title="Invite created",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
            if invite.channel is not None:
                embed.add_field(name="Channel", value=getattr(invite.channel, "mention", str(invite.channel)), inline=True)
            if invite.inviter is not None:
                embed.add_field(name="Created by", value=f"{invite.inviter.mention} (`{invite.inviter.id}`)", inline=False)
            max_uses = invite.max_uses or 0
            embed.add_field(name="Max uses", value=str(max_uses) if max_uses else "∞", inline=True)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_invite_create error: {exc}")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        try:
            guild = invite.guild
            if guild is None:
                return
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_invites", "server")
            if not channel:
                return
            embed = discord.Embed(
                title="Invite deleted",
                color=COLOR_RED,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
            if invite.channel is not None:
                embed.add_field(name="Channel", value=getattr(invite.channel, "mention", str(invite.channel)), inline=True)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_invite_delete error: {exc}")

    # ------------------------------------------------------------------ #
    # Thread events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        await self._log_thread_event(thread, "Thread created", COLOR_GREEN)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        await self._log_thread_event(thread, "Thread deleted", COLOR_RED)

    async def _log_thread_event(self, thread, title, color):
        try:
            guild = thread.guild
            if guild is None:
                return
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_threads", "server")
            if not channel:
                return
            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Thread", value=f"{thread.name} (`{thread.id}`)", inline=False)
            if thread.parent is not None:
                embed.add_field(name="Parent", value=getattr(thread.parent, "mention", str(thread.parent)), inline=True)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] thread event error: {exc}")

    # ------------------------------------------------------------------ #
    # Emoji / sticker events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        await self._log_asset_update(guild, "Emojis updated", before, after)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild, before, after):
        await self._log_asset_update(guild, "Stickers updated", before, after)

    async def _log_asset_update(self, guild, title, before, after):
        try:
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_emojis", "server")
            if not channel:
                return
            before_ids = {e.id for e in before}
            after_ids = {e.id for e in after}
            added = [e for e in after if e.id not in before_ids]
            removed = [e for e in before if e.id not in after_ids]
            if not added and not removed:
                return
            embed = discord.Embed(
                title=title,
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            if added:
                embed.add_field(name="Added", value=_truncate(", ".join(f"`{e.name}`" for e in added), 1024), inline=False)
            if removed:
                embed.add_field(name="Removed", value=_truncate(", ".join(f"`{e.name}`" for e in removed), 1024), inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] asset update error: {exc}")

    # ------------------------------------------------------------------ #
    # Webhook events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        try:
            guild = channel.guild
            if guild is None:
                return
            settings = await self.get_settings(guild.id)
            log_channel = await self._resolve_log_channel(guild, settings, "log_webhooks", "server")
            if not log_channel:
                return
            executor = await self._maybe_executor(guild, settings, discord.AuditLogAction.webhook_update)
            embed = discord.Embed(
                title="Webhooks updated",
                color=COLOR_GREY,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Channel", value=getattr(channel, "mention", str(channel)), inline=True)
            self._apply_executor(embed, executor)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] on_webhooks_update error: {exc}")

    # ------------------------------------------------------------------ #
    # AutoMod events (server category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_automod_action(self, execution):
        try:
            guild = getattr(execution, "guild", None)
            if guild is None:
                gid = getattr(execution, "guild_id", None)
                guild = self.bot.get_guild(gid) if gid else None
            if guild is None:
                return
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_automod", "server")
            if not channel:
                return
            member = getattr(execution, "member", None)
            if member is not None and self._is_actor_ignored(settings, member):
                return
            embed = discord.Embed(
                title="AutoMod action",
                color=COLOR_RED,
                timestamp=datetime.now(timezone.utc),
            )
            user_id = getattr(execution, "user_id", None)
            if member is not None:
                embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            elif user_id:
                embed.add_field(name="User", value=f"`{user_id}`", inline=False)
            keyword = getattr(execution, "matched_keyword", None)
            if keyword:
                embed.add_field(name="Matched", value=_truncate(str(keyword), 256), inline=True)
            content = getattr(execution, "content", None)
            if content:
                embed.add_field(name="Content", value=_truncate(content, 1024), inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_automod_action error: {exc}")

    # ------------------------------------------------------------------ #
    # Voice activity (voice category)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            settings = await self.get_settings(member.guild.id)
            channel = await self._resolve_log_channel(member.guild, settings, "log_voice", "voice")
            if not channel:
                return
            if self._is_actor_ignored(settings, member):
                return

            if before.channel is None and after.channel is not None:
                title, color, detail = "Joined voice", COLOR_GREEN, after.channel.mention
            elif before.channel is not None and after.channel is None:
                title, color, detail = "Left voice", COLOR_RED, before.channel.mention
            elif before.channel != after.channel:
                title, color = "Moved voice", COLOR_AMBER
                detail = f"{before.channel.mention} → {after.channel.mention}"
            else:
                return  # mute/deafen/etc. — ignore

            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="Channel", value=detail, inline=True)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_voice_state_update error: {exc}")


async def setup(bot):
    await bot.add_cog(ServerLogs(bot))
