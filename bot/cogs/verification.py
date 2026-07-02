"""Verification cog.

Posts a panel with a "Verify" button; clicking it grants the configured verified
role. Clicks are handled via on_interaction (custom_id "verify") so they keep
working across bot restarts without persistent-view registration.

Admins post/refresh the panel with the `/verifypanel` slash command.

Backend contract (X-Bot-Token auth):
  GET /api/bot/guilds/{gid}/settings/verification
      → { enabled, channel_id, verified_role_id, message, button_label, ... }
  PUT /api/bot/guilds/{gid}/verification/panel  body { message_id }

Logging prefix: "[verify]".
"""

import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_put
from utils import general_config
from utils.bot_i18n import t, lang_for


SETTINGS_TTL_SECONDS = 120
VERIFY_COLOR = 0x22C55E
VERIFY_CUSTOM_ID = "verify"


def build_panel_view(label):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.success,
        label=(label or "Verify")[:80],
        custom_id=VERIFY_CUSTOM_ID,
        emoji="✅",
    ))
    return view


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}

    async def _get_settings(self, guild_id, force=False):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if not force and cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "verification")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    @app_commands.command(name="verifypanel", description="Post or refresh the verification panel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def verifypanel(self, interaction: discord.Interaction):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        perms = getattr(interaction.user, "guild_permissions", None)
        if not (perms and (perms.manage_guild or perms.administrator)):
            await interaction.response.send_message(t(lang, "verify.adminOnly"), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        settings = await self._get_settings(interaction.guild.id, force=True)
        if not settings or not settings.get("enabled"):
            await interaction.followup.send(t(lang, "verify.disabled"), ephemeral=True)
            return
        if not settings.get("verified_role_id"):
            await interaction.followup.send(t(lang, "verify.noRole"), ephemeral=True)
            return

        channel_id = settings.get("channel_id")
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id else interaction.channel
        embed = discord.Embed(
            description=settings.get("message") or t(lang, "verify.defaultMessage"),
            color=await general_config.get_embed_color(self.backend_url, self.api_key, interaction.guild.id, fallback=VERIFY_COLOR),
        )
        embed.set_author(name=t(lang, "verify.author"))
        try:
            msg = await channel.send(embed=embed, view=build_panel_view(settings.get("button_label") or t(lang, "verify.button")))
        except discord.Forbidden:
            await interaction.followup.send(t(lang, "verify.cantPost"), ephemeral=True)
            return

        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{interaction.guild.id}/verification/panel",
            {"message_id": str(msg.id)},
        )
        await interaction.followup.send(t(lang, "verify.panelPosted", channel=channel.mention), ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        if (interaction.data or {}).get("custom_id") != VERIFY_CUSTOM_ID:
            return
        if interaction.guild is None:
            return

        # Settings-Lookup (HTTP) + add_roles vor der Antwort — sofort deferren,
        # sonst läuft der Interaction-Token ab (10062 Unknown interaction).
        await interaction.response.defer(ephemeral=True)

        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        settings = await self._get_settings(interaction.guild.id)
        if not settings or not settings.get("enabled"):
            await interaction.followup.send(t(lang, "verify.currentlyDisabled"), ephemeral=True)
            return
        role_id = settings.get("verified_role_id")
        role = interaction.guild.get_role(int(role_id)) if role_id else None
        if role is None:
            await interaction.followup.send(t(lang, "verify.roleGone"), ephemeral=True)
            return
        member = interaction.user
        if role in member.roles:
            await interaction.followup.send(t(lang, "verify.already"), ephemeral=True)
            return
        try:
            await member.add_roles(role, reason="Verification")
            await interaction.followup.send(t(lang, "verify.success"), ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(t(lang, "verify.forbidden"), ephemeral=True)
        except Exception as exc:
            print(f"[verify] add role failed in {interaction.guild.id}: {exc}")
            await interaction.followup.send(t(lang, "verify.error"), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Verification(bot))
