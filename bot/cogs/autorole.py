"""Auto-Role cog: assigns configured roles to new members on join."""

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = config.BACKEND_URL

    async def get_settings(self, guild_id):
        return await fetch_bot_settings(
            self.backend_url, config.BOT_API_KEY, guild_id, "autorole"
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        try:
            settings = await self.get_settings(guild.id)
            if not settings or not settings.get("enabled"):
                return

            if member.bot and not settings.get("apply_to_bots"):
                return

            role_ids = settings.get("role_ids") or []
            if not role_ids:
                return

            roles_to_add = []
            for rid in role_ids:
                try:
                    role = guild.get_role(int(rid))
                    if role is not None:
                        roles_to_add.append(role)
                except (TypeError, ValueError):
                    print(f"[autorole] invalid role id {rid!r} for guild {guild.id}")

            if not roles_to_add:
                return

            try:
                await member.add_roles(*roles_to_add, reason="Auto-Role")
                print(
                    f"[autorole] applied {len(roles_to_add)} role(s) to "
                    f"{member} in {guild.name}"
                )
            except discord.Forbidden:
                print(f"[autorole] missing permissions in {guild.name}")
            except discord.HTTPException as exc:
                print(f"[autorole] HTTP error in {guild.name}: {exc}")
        except Exception as exc:
            print(f"[autorole] unexpected error in {guild.id}: {exc}")


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
