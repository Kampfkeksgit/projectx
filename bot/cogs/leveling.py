"""Leveling/XP cog: forwards every message to the backend, which decides whether
to grant XP and emits a level-up payload when the user crosses a threshold.

Backend contract:
  POST /api/bot/guilds/:guild_id/leveling/xp
       body: { "user_id": str, "channel_id": str }
       → {
           granted: bool,
           leveled_up: bool,
           xp_gained: int,
           total_xp: int,
           new_level: int,
           role_rewards: [str],          # roles the user should NOW have
           previous_role_rewards: [str], # OPTIONAL — roles to remove if non-stacking
           announce_channel_id: str|None,
           announce_message_template: str|None,
         }

The backend is the source of truth for cooldowns, ignored channels, and the
"enabled" toggle — if it returns `granted: false` the bot does nothing.

`previous_role_rewards` is an OPTIONAL field. Per the task brief it's not part
of the formal contract yet — if present, we remove those roles before adding
new ones; if absent we treat it as an empty list and only add. That's good
enough for the first iteration; the cog will Just Work once the backend
starts emitting the field.
"""

import discord
from discord.ext import commands

import config
from utils.backend import bot_post


def _apply_levelup_placeholders(template, *, member, guild, level):
    """Same placeholder semantics as cogs.welcome_leave for level-up messages.

    Tokens:
      {user}           → member.mention
      {user.mention}   → member.mention
      {user.name}      → display_name (or .name fallback)
      {level}          → str(level)
      {guild}          → guild.name
    """
    if template is None:
        return ""
    text = str(template)
    try:
        display_name = getattr(member, "display_name", None) or getattr(member, "name", "")
    except Exception:
        display_name = ""

    replacements = {
        "{user.mention}": getattr(member, "mention", str(member)),
        "{user}": getattr(member, "mention", str(member)),
        "{user.name}": display_name,
        "{level}": str(level),
        "{guild}": getattr(guild, "name", ""),
    }
    for token, value in replacements.items():
        if token in text:
            text = text.replace(token, value)
    return text


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY

    def _enabled(self):
        if not self.api_key:
            return False
        if not self.backend_url:
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if not self._enabled():
                return
            if message.guild is None:
                return
            author = message.author
            if author is None or author.bot:
                return
            # Skip slash-command interaction echo messages — they're application
            # messages with no real "human" intent.
            if getattr(message, "interaction", None) is not None:
                return

            path = f"/api/bot/guilds/{message.guild.id}/leveling/xp"
            body = {
                "user_id": str(author.id),
                "channel_id": str(message.channel.id),
            }
            data = await bot_post(self.backend_url, self.api_key, path, body)
            if not data:
                return
            if not data.get("granted"):
                return

            leveled_up = bool(data.get("leveled_up"))
            new_level = data.get("new_level")
            role_rewards = data.get("role_rewards") or []
            previous_role_rewards = data.get("previous_role_rewards") or []

            if not leveled_up:
                return

            guild = message.guild
            member = author if isinstance(author, discord.Member) else guild.get_member(author.id)
            if member is None:
                try:
                    member = await guild.fetch_member(author.id)
                except Exception as exc:
                    print(f"[leveling] fetch_member failed in {guild.id}: {exc}")
                    member = None

            # ---------- announcement ----------
            template = data.get("announce_message_template")
            if template:
                text = _apply_levelup_placeholders(
                    template, member=member or author, guild=guild, level=new_level
                )
                announce_channel = None
                announce_id = _coerce_int(data.get("announce_channel_id"))
                if announce_id is not None:
                    announce_channel = self.bot.get_channel(announce_id)
                if announce_channel is None:
                    announce_channel = message.channel
                if announce_channel is not None and text:
                    try:
                        await announce_channel.send(text)
                    except discord.Forbidden:
                        print(f"[leveling] missing permissions to announce in {guild.id}")
                    except discord.HTTPException as exc:
                        print(f"[leveling] HTTP error sending announcement in {guild.id}: {exc}")
                    except Exception as exc:
                        print(f"[leveling] announcement error in {guild.id}: {exc}")

            # ---------- role rewards ----------
            if member is not None:
                # Remove previous-tier reward roles first (non-stacking mode).
                # Backend is responsible for telling us which to strip; if it
                # doesn't, we simply add the new ones — that's the documented
                # acceptable first-iteration behaviour.
                roles_to_remove = []
                for rid in previous_role_rewards:
                    parsed = _coerce_int(rid)
                    if parsed is None:
                        continue
                    role = guild.get_role(parsed)
                    if role is not None and role in member.roles:
                        roles_to_remove.append(role)
                if roles_to_remove:
                    try:
                        await member.remove_roles(*roles_to_remove, reason="Leveling: previous reward")
                    except discord.Forbidden:
                        print(f"[leveling] missing perms to remove old reward roles in {guild.id}")
                    except discord.HTTPException as exc:
                        print(f"[leveling] HTTP error removing old reward roles: {exc}")
                    except Exception as exc:
                        print(f"[leveling] remove-previous error: {exc}")

                roles_to_add = []
                for rid in role_rewards:
                    parsed = _coerce_int(rid)
                    if parsed is None:
                        continue
                    role = guild.get_role(parsed)
                    if role is not None and role not in member.roles:
                        roles_to_add.append(role)
                if roles_to_add:
                    try:
                        await member.add_roles(*roles_to_add, reason=f"Leveling: reached level {new_level}")
                    except discord.Forbidden:
                        print(f"[leveling] missing perms to add reward roles in {guild.id}")
                    except discord.HTTPException as exc:
                        print(f"[leveling] HTTP error adding reward roles: {exc}")
                    except Exception as exc:
                        print(f"[leveling] add-reward error: {exc}")
        except Exception as exc:
            # Absolute belt-and-braces — an on_message listener that ever
            # raises will spam the entire event loop with the same error,
            # one per message bot-wide.
            print(f"[leveling] on_message fatal error: {exc}")


async def setup(bot):
    await bot.add_cog(Leveling(bot))
