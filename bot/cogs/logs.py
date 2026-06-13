"""Server-Logs cog: posts embeds for configured events to a log channel."""

from datetime import datetime, timezone

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings


COLOR_GREEN = 0x2ECC71
COLOR_RED = 0xE74C3C
COLOR_AMBER = 0xF1C40F
COLOR_GREY = 0x95A5A6


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

    async def _resolve_log_channel(self, guild, settings, flag_key):
        """Return the log channel if enabled and the specific event flag is on, else None."""
        if not settings or not settings.get("enabled"):
            return None
        if not settings.get(flag_key):
            return None
        channel_id = settings.get("log_channel_id")
        if not channel_id:
            return None
        try:
            return guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_ignored(settings, channel_id):
        """True if the given channel is in log_ignored_channel_ids (no message logging)."""
        ignored = set(settings.get("log_ignored_channel_ids") or [])
        return str(channel_id) in ignored

    async def _post(self, channel, embed):
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"[logs] missing permissions in #{channel}")
        except discord.HTTPException as exc:
            print(f"[logs] HTTP error: {exc}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            settings = await self.get_settings(member.guild.id)
            channel = await self._resolve_log_channel(member.guild, settings, "log_joins")
            if not channel:
                return
            embed = discord.Embed(
                title="Member joined",
                description=f"{member.mention} joined the server.",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_join error: {exc}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            settings = await self.get_settings(member.guild.id)
            channel = await self._resolve_log_channel(member.guild, settings, "log_leaves")
            if not channel:
                return
            embed = discord.Embed(
                title="Member left",
                description=f"{member} left the server.",
                color=COLOR_RED,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_remove error: {exc}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        try:
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_member_bans")
            if not channel:
                return
            embed = discord.Embed(
                title="Member banned",
                description=f"{user} was banned.",
                color=COLOR_RED,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_ban error: {exc}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        try:
            if message.guild is None or message.author.bot:
                return
            settings = await self.get_settings(message.guild.id)
            channel = await self._resolve_log_channel(
                message.guild, settings, "log_message_deletes"
            )
            if not channel:
                return
            if self._is_ignored(settings, message.channel.id):
                return
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
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_message_delete error: {exc}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        try:
            if after.guild is None or after.author.bot:
                return
            if (before.content or "") == (after.content or ""):
                return
            settings = await self.get_settings(after.guild.id)
            channel = await self._resolve_log_channel(
                after.guild, settings, "log_message_edits"
            )
            if not channel:
                return
            if self._is_ignored(settings, after.channel.id):
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
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_message_edit error: {exc}")

    # ------------------------------------------------------------------ #
    # Member updates: role changes, nickname, timeout (log_member_updates)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            settings = await self.get_settings(after.guild.id)
            channel = await self._resolve_log_channel(after.guild, settings, "log_member_updates")
            if not channel:
                return

            # Role changes
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
                await self._post(channel, embed)

            # Nickname change
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

            # Timeout applied / removed
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
                await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_update error: {exc}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user):
        try:
            settings = await self.get_settings(guild.id)
            channel = await self._resolve_log_channel(guild, settings, "log_member_unbans")
            if not channel:
                return
            embed = discord.Embed(
                title="Member unbanned",
                description=f"{user} was unbanned.",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
            await self._post(channel, embed)
        except Exception as exc:
            print(f"[logs] on_member_unban error: {exc}")

    # ------------------------------------------------------------------ #
    # Channel events (log_channels)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._log_channel_event(channel.guild, "Channel created", channel, COLOR_GREEN)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self._log_channel_event(channel.guild, "Channel deleted", channel, COLOR_RED)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        try:
            if before.name == after.name:
                return  # only log renames; ignore permission/topic churn
            settings = await self.get_settings(after.guild.id)
            log_channel = await self._resolve_log_channel(after.guild, settings, "log_channels")
            if not log_channel:
                return
            embed = discord.Embed(
                title="Channel renamed",
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Before", value=_truncate(before.name, 256), inline=True)
            embed.add_field(name="After", value=_truncate(after.name, 256), inline=True)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] on_guild_channel_update error: {exc}")

    async def _log_channel_event(self, guild, title, channel, color):
        try:
            settings = await self.get_settings(guild.id)
            log_channel = await self._resolve_log_channel(guild, settings, "log_channels")
            if not log_channel:
                return
            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Channel", value=f"{getattr(channel, 'name', 'unknown')} (`{channel.id}`)", inline=False)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] channel event error: {exc}")

    # ------------------------------------------------------------------ #
    # Role events (log_roles)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self._log_role_event(role.guild, "Role created", role, COLOR_GREEN)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self._log_role_event(role.guild, "Role deleted", role, COLOR_RED)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        try:
            if before.name == after.name:
                return
            settings = await self.get_settings(after.guild.id)
            log_channel = await self._resolve_log_channel(after.guild, settings, "log_roles")
            if not log_channel:
                return
            embed = discord.Embed(
                title="Role renamed",
                color=COLOR_AMBER,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Before", value=_truncate(before.name, 256), inline=True)
            embed.add_field(name="After", value=_truncate(after.name, 256), inline=True)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] on_guild_role_update error: {exc}")

    async def _log_role_event(self, guild, title, role, color):
        try:
            settings = await self.get_settings(guild.id)
            log_channel = await self._resolve_log_channel(guild, settings, "log_roles")
            if not log_channel:
                return
            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Role", value=f"{role.name} (`{role.id}`)", inline=False)
            await self._post(log_channel, embed)
        except Exception as exc:
            print(f"[logs] role event error: {exc}")

    # ------------------------------------------------------------------ #
    # Voice activity (log_voice)
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            if member.bot:
                return
            settings = await self.get_settings(member.guild.id)
            channel = await self._resolve_log_channel(member.guild, settings, "log_voice")
            if not channel:
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
