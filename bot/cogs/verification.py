"""Verification cog.

Posts a panel with a "Verify" button; clicking it grants the configured verified
role. Clicks are handled via on_interaction (custom_id "verify") so they keep
working across bot restarts without persistent-view registration.

Admins post/refresh the panel with `!verifypanel`.

Backend contract (X-Bot-Token auth):
  GET /api/bot/guilds/{gid}/settings/verification
      → { enabled, channel_id, verified_role_id, message, button_label, ... }
  PUT /api/bot/guilds/{gid}/verification/panel  body { message_id }

Logging prefix: "[verify]".
"""

import time

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_put


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

    @commands.command(name="verifypanel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def verifypanel(self, ctx):
        settings = await self._get_settings(ctx.guild.id, force=True)
        if not settings or not settings.get("enabled"):
            await ctx.reply("Verification is not enabled.", mention_author=False)
            return
        if not settings.get("verified_role_id"):
            await ctx.reply("No verified role is configured.", mention_author=False)
            return

        channel_id = settings.get("channel_id")
        channel = ctx.guild.get_channel(int(channel_id)) if channel_id else ctx.channel
        embed = discord.Embed(
            description=settings.get("message") or "Click the button below to verify.",
            color=VERIFY_COLOR,
        )
        embed.set_author(name="Verification")
        try:
            msg = await channel.send(embed=embed, view=build_panel_view(settings.get("button_label")))
        except discord.Forbidden:
            await ctx.reply("I can't post in the verification channel.", mention_author=False)
            return

        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{ctx.guild.id}/verification/panel",
            {"message_id": str(msg.id)},
        )
        if channel.id != ctx.channel.id:
            await ctx.reply(f"✅ Verification panel posted in {channel.mention}.", mention_author=False)

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

        settings = await self._get_settings(interaction.guild.id)
        if not settings or not settings.get("enabled"):
            await interaction.followup.send("Verification is currently disabled.", ephemeral=True)
            return
        role_id = settings.get("verified_role_id")
        role = interaction.guild.get_role(int(role_id)) if role_id else None
        if role is None:
            await interaction.followup.send("The verified role no longer exists.", ephemeral=True)
            return
        member = interaction.user
        if role in member.roles:
            await interaction.followup.send("You're already verified. ✅", ephemeral=True)
            return
        try:
            await member.add_roles(role, reason="Verification")
            await interaction.followup.send("✅ You're verified — welcome!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I couldn't assign the role (missing permission / role too high).", ephemeral=True)
        except Exception as exc:
            print(f"[verify] add role failed in {interaction.guild.id}: {exc}")
            await interaction.followup.send("Something went wrong. Try again later.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Verification(bot))
