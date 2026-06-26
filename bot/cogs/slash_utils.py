"""Slash-Utility-Commands cog.

A handful of always-useful slash commands. These register on the bot's command
tree; main.py syncs the tree once on startup.

  /ping        — latency check
  /userinfo    — info about a member
  /serverinfo  — info about the server
  /avatar      — show a member's avatar

Logging prefix: "[slash]".
"""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import general_config
from utils.bot_i18n import t, lang_for


class SlashUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY

    async def _lang(self, interaction):
        if interaction.guild is None:
            return "en"
        return await lang_for(self.backend_url, self.api_key, interaction.guild.id)

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        lang = await self._lang(interaction)
        await interaction.response.send_message(t(lang, "slash.pong", ms=latency_ms), ephemeral=True)

    @app_commands.command(name="userinfo", description="Show information about a member.")
    @app_commands.describe(member="The member to inspect (defaults to you).")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        lang = await self._lang(interaction)
        embed = discord.Embed(color=member.color, timestamp=discord.utils.utcnow())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name=t(lang, "slash.fieldId"), value=str(member.id), inline=True)
        embed.add_field(name=t(lang, "slash.fieldNickname"), value=member.nick or "—", inline=True)
        embed.add_field(name=t(lang, "slash.fieldBot"), value=t(lang, "slash.yes") if member.bot else t(lang, "slash.no"), inline=True)
        embed.add_field(name=t(lang, "slash.fieldCreated"), value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        if member.joined_at:
            embed.add_field(name=t(lang, "slash.fieldJoined"), value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(name=t(lang, "slash.fieldRolesCount", count=len(roles)), value=" ".join(roles[:15]) or "—", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Show information about this server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(t("en", "slash.serverOnly"), ephemeral=True)
            return
        lang = await self._lang(interaction)
        color = await general_config.get_embed_color(self.backend_url, self.api_key, guild.id, fallback=0x5865F2)
        embed = discord.Embed(title=guild.name, color=color, timestamp=discord.utils.utcnow())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name=t(lang, "slash.fieldId"), value=str(guild.id), inline=True)
        embed.add_field(name=t(lang, "slash.fieldOwner"), value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name=t(lang, "slash.fieldMembers"), value=str(guild.member_count), inline=True)
        embed.add_field(name=t(lang, "slash.fieldChannels"), value=str(len(guild.channels)), inline=True)
        embed.add_field(name=t(lang, "slash.fieldRoles"), value=str(len(guild.roles)), inline=True)
        embed.add_field(name=t(lang, "slash.fieldBoosts"), value=str(guild.premium_subscription_count or 0), inline=True)
        embed.add_field(name=t(lang, "slash.fieldCreated"), value=discord.utils.format_dt(guild.created_at, "R"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="avatar", description="Show a member's avatar.")
    @app_commands.describe(member="The member (defaults to you).")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        lang = await self._lang(interaction)
        embed = discord.Embed(title=t(lang, "slash.avatarTitle", name=member.display_name), color=member.color)
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SlashUtils(bot))
