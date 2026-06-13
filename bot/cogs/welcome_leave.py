"""Welcome/Leave cog: posts join/leave messages with optional rich embeds,
DM-on-join, auto-delete, and an expanded placeholder system.

Settings are fetched from the backend on every event via
GET /api/bot/guilds/:guild_id/settings (no envelope) — see
backend/routes/bot.js. The shape is documented in db.js
(WELCOME_LEAVE_DEFAULTS).
"""

import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings


DEFAULT_EMBED_COLOR = 0x5865F2
AVATAR_PLACEHOLDER = "{user.avatar}"


def resolve_placeholders(template, member, guild):
    """Replace placeholders in `template` using member/guild context.

    Supported tokens:
      {user}                → member.mention
      {user.name}           → member.display_name (or member.name fallback)
      {user.id}             → str(member.id)
      {user.tag}            → str(member)  (handles new username system)
      {user.avatar}         → str(member.display_avatar.url)
      {guild}               → guild.name
      {guild.id}            → str(guild.id)
      {guild.member_count}  → str(guild.member_count)
    """
    if template is None:
        return ""
    text = str(template)

    try:
        display_name = getattr(member, "display_name", None) or getattr(member, "name", "")
    except Exception:
        display_name = ""

    try:
        avatar_url = str(member.display_avatar.url) if getattr(member, "display_avatar", None) else ""
    except Exception:
        avatar_url = ""

    replacements = {
        "{user}": getattr(member, "mention", str(member)),
        "{user.name}": display_name,
        "{user.id}": str(getattr(member, "id", "")),
        "{user.tag}": str(member),
        "{user.avatar}": avatar_url,
        "{guild}": getattr(guild, "name", ""),
        "{guild.id}": str(getattr(guild, "id", "")),
        "{guild.member_count}": str(getattr(guild, "member_count", "") or ""),
    }

    for token, value in replacements.items():
        if token in text:
            text = text.replace(token, value)
    return text


def _resolve_url_field(raw, member, guild):
    """For embed image/thumbnail/author_icon_url fields:
    only resolve the literal `{user.avatar}` placeholder; otherwise
    return the URL untouched (or '' for empty/None).
    """
    if not raw:
        return ""
    s = str(raw)
    if s == AVATAR_PLACEHOLDER:
        try:
            return str(member.display_avatar.url) if getattr(member, "display_avatar", None) else ""
        except Exception:
            return ""
    return s


def _parse_color(color_str):
    """'#RRGGBB' → discord.Color; invalid → default brand purple."""
    try:
        if isinstance(color_str, str) and color_str.startswith("#") and len(color_str) == 7:
            return discord.Color(int(color_str[1:], 16))
    except (ValueError, TypeError):
        pass
    return discord.Color(DEFAULT_EMBED_COLOR)


def build_embed(embed_cfg, member, guild, test_marker=False):
    """Build a discord.Embed from the parsed embed config + placeholder context.

    Returns None if `embed_cfg` is falsy/empty.
    """
    if not embed_cfg or not isinstance(embed_cfg, dict):
        return None

    title = resolve_placeholders(embed_cfg.get("title", "") or "", member, guild)
    description = resolve_placeholders(embed_cfg.get("description", "") or "", member, guild)
    if test_marker:
        description = f"**[TEST]** {description}" if description else "**[TEST]**"
    footer = resolve_placeholders(embed_cfg.get("footer", "") or "", member, guild)
    author_name = resolve_placeholders(embed_cfg.get("author_name", "") or "", member, guild)

    embed = discord.Embed(
        title=title or None,
        description=description or None,
        color=_parse_color(embed_cfg.get("color")),
    )

    thumbnail = _resolve_url_field(embed_cfg.get("thumbnail"), member, guild)
    if thumbnail:
        try:
            embed.set_thumbnail(url=thumbnail)
        except Exception as exc:
            print(f"[welcome_leave] set_thumbnail failed: {exc}")

    image = _resolve_url_field(embed_cfg.get("image"), member, guild)
    if image:
        try:
            embed.set_image(url=image)
        except Exception as exc:
            print(f"[welcome_leave] set_image failed: {exc}")

    if footer:
        try:
            embed.set_footer(text=footer)
        except Exception as exc:
            print(f"[welcome_leave] set_footer failed: {exc}")

    if author_name:
        icon_url = _resolve_url_field(embed_cfg.get("author_icon_url"), member, guild)
        try:
            if icon_url:
                embed.set_author(name=author_name, icon_url=icon_url)
            else:
                embed.set_author(name=author_name)
        except Exception as exc:
            print(f"[welcome_leave] set_author failed: {exc}")

    if embed_cfg.get("show_timestamp"):
        embed.timestamp = datetime.now(timezone.utc)

    return embed


async def _schedule_delete(message, delay):
    """Delete `message` after `delay` seconds, swallowing any error."""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception as exc:
        print(f"[welcome_leave] auto-delete failed: {exc}")


class WelcomeLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = config.BACKEND_URL

    async def get_guild_settings(self, guild_id):
        """Fetch the full extended Welcome/Leave settings via the shared helper."""
        return await fetch_bot_settings(
            self.backend_url, config.BOT_API_KEY, guild_id, None
        )

    async def _send_welcome(self, settings, member, guild, *, test_marker=False):
        """Core send routine shared by on_member_join and /welcome_test.

        Returns the sent discord.Message, or None if nothing was sent / on error.
        """
        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            return None

        try:
            channel = self.bot.get_channel(int(channel_id))
        except (TypeError, ValueError):
            print(f"[welcome_leave] invalid channel id {channel_id!r} for guild {guild.id}")
            return None
        if channel is None:
            print(f"[welcome_leave] channel {channel_id} not found in guild {guild.id}")
            return None

        use_embed = bool(settings.get("welcome_use_embed"))
        ping_user = bool(settings.get("welcome_ping_user"))

        content = None
        embed = None

        if use_embed:
            embed = build_embed(
                settings.get("welcome_embed") or {},
                member,
                guild,
                test_marker=test_marker,
            )
            content = member.mention if ping_user else None
        else:
            raw = settings.get("welcome_message") or "Welcome {user}!"
            content = resolve_placeholders(raw, member, guild)
            if test_marker:
                content = f"**[TEST]** {content}"

        try:
            sent = await channel.send(content=content, embed=embed)
        except Exception as exc:
            print(f"[welcome_leave] failed to send welcome in {guild.id}: {exc}")
            return None

        # DM the new member (skipped for test mode is left to the caller — test
        # invokes _send_welcome directly without going through on_member_join).
        if not test_marker and settings.get("welcome_dm_enabled"):
            dm_template = settings.get("welcome_dm_message") or ""
            if dm_template:
                dm_text = resolve_placeholders(dm_template, member, guild)
                try:
                    await member.send(dm_text)
                except Exception as exc:
                    print(f"[welcome_leave] DM to {member} failed: {exc}")

        # Schedule auto-delete (don't block the listener).
        delete_after = settings.get("welcome_delete_after") or 0
        try:
            delete_after = int(delete_after)
        except (TypeError, ValueError):
            delete_after = 0
        if delete_after > 0:
            asyncio.create_task(_schedule_delete(sent, delete_after))

        return sent

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        try:
            settings = await self.get_guild_settings(guild.id)
            if not settings or not settings.get("welcome_enabled"):
                return
            await self._send_welcome(settings, member, guild)
        except Exception as exc:
            print(f"[welcome_leave] on_member_join error in {guild.id}: {exc}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        try:
            settings = await self.get_guild_settings(guild.id)
            if not settings or not settings.get("leave_enabled"):
                return

            channel_id = settings.get("leave_channel_id")
            if not channel_id:
                return

            try:
                channel = self.bot.get_channel(int(channel_id))
            except (TypeError, ValueError):
                print(f"[welcome_leave] invalid leave channel id {channel_id!r}")
                return
            if channel is None:
                print(f"[welcome_leave] leave channel {channel_id} not found in {guild.id}")
                return

            use_embed = bool(settings.get("leave_use_embed"))
            content = None
            embed = None

            if use_embed:
                embed = build_embed(
                    settings.get("leave_embed") or {},
                    member,
                    guild,
                )
            else:
                raw = settings.get("leave_message") or "{user} has left."
                content = resolve_placeholders(raw, member, guild)

            try:
                sent = await channel.send(content=content, embed=embed)
            except Exception as exc:
                print(f"[welcome_leave] failed to send leave in {guild.id}: {exc}")
                return

            delete_after = settings.get("leave_delete_after") or 0
            try:
                delete_after = int(delete_after)
            except (TypeError, ValueError):
                delete_after = 0
            if delete_after > 0:
                asyncio.create_task(_schedule_delete(sent, delete_after))
        except Exception as exc:
            print(f"[welcome_leave] on_member_remove error in {guild.id}: {exc}")

    @commands.command(name="welcome_test")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        """Post a preview welcome targeting the invoker (admin only)."""
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            if not settings:
                await ctx.send("No settings found. Please configure welcome/leave on the dashboard.")
                return
            if not settings.get("welcome_channel_id"):
                await ctx.send("No welcome channel configured.")
                return

            sent = await self._send_welcome(
                settings, ctx.author, ctx.guild, test_marker=True
            )
            if sent is None:
                await ctx.send("Failed to send test welcome (check channel/permissions).")
                return

            try:
                await ctx.send(f"Test welcome message sent to {sent.channel.mention}")
            except Exception:
                pass
        except Exception as exc:
            try:
                await ctx.send(f"Error: {exc}")
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))
