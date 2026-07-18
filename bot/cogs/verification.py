"""Verification cog.

Posts a panel with a "Verify" button; clicking it grants the configured verified
role. Clicks are handled via on_interaction (custom_id "verify") so they keep
working across bot restarts without persistent-view registration.

The panel auto-posts to the configured channel when verification is enabled (role
+ channel set) and auto-updates in place whenever the settings/embed are edited in
the dashboard (dirty flag → 60s poll loop, like rolemenus). `/verifypanel` is a
manual (re)post. The panel can be a plain message or a fully designed embed.

Backend contract (X-Bot-Token auth):
  GET /api/bot/guilds/{gid}/settings/verification
      → { enabled, channel_id, verified_role_id, message, button_label, use_embed, embed, ... }
  GET /api/bot/verification/pending  → { panels: [{ guild_id, channel_id, panel_message_id,
                                          message, button_label, use_embed, embed }] }
  PUT /api/bot/guilds/{gid}/verification/panel  body { message_id }  (clears dirty)

Logging prefix: "[verify]".
"""

import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.backend import fetch_bot_settings, bot_get, bot_put
from utils import general_config
from utils.bot_i18n import t, lang_for
from utils.rich_message import is_components_v2, build_layout_view


SETTINGS_TTL_SECONDS = 120
POLL_SECONDS = 60
VERIFY_COLOR = 0x22C55E
VERIFY_CUSTOM_ID = "verify"


def _resolve(text, guild):
    if not text:
        return ""
    return str(text).replace("{guild}", guild.name if guild else "")


def _parse_color(value, fallback=VERIFY_COLOR):
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return int(value[1:], 16)
        except ValueError:
            return fallback
    return fallback


def build_verify_button(label):
    return discord.ui.Button(
        style=discord.ButtonStyle.success,
        label=(label or "Verify")[:80],
        custom_id=VERIFY_CUSTOM_ID,
        emoji="✅",
    )


def build_panel_view(label):
    view = discord.ui.View(timeout=None)
    view.add_item(build_verify_button(label))
    return view


def build_panel_layout(settings, guild, lang):
    """Components V2 variant: accent container (from embed blocks) + verify button."""
    label = settings.get("button_label") or t(lang, "verify.button")
    return build_layout_view(
        settings.get("embed") or {},
        resolve_text=lambda s: _resolve(s, guild),
        resolve_url=lambda s: str(s) if str(s or "").startswith("http") else "",
        action_items=[build_verify_button(label)],
    )


def build_panel_embed(settings, guild, lang, plain_color):
    """Plain-message embed, or a fully designed embed when use_embed is set."""
    if settings.get("use_embed"):
        cfg = settings.get("embed") or {}
        embed = discord.Embed(
            title=_resolve(cfg.get("title"), guild) or None,
            description=_resolve(cfg.get("description"), guild) or None,
            color=_parse_color(cfg.get("color")),
        )
        author_name = _resolve(cfg.get("author_name"), guild)
        if author_name:
            icon = cfg.get("author_icon_url") or None
            if icon and not str(icon).startswith("http"):
                icon = None
            embed.set_author(name=author_name[:256], icon_url=icon)
        thumb = cfg.get("thumbnail")
        if thumb and str(thumb).startswith("http"):
            embed.set_thumbnail(url=thumb)
        image = cfg.get("image")
        if image and str(image).startswith("http"):
            embed.set_image(url=image)
        footer = _resolve(cfg.get("footer"), guild)
        if footer:
            embed.set_footer(text=footer[:2048])
        if cfg.get("show_timestamp"):
            embed.timestamp = discord.utils.utcnow()
        if not (embed.title or embed.description or embed.fields or embed.author.name):
            embed.title = t(lang, "verify.author")
            embed.description = t(lang, "verify.defaultMessage")
        return embed

    embed = discord.Embed(
        description=settings.get("message") or t(lang, "verify.defaultMessage"),
        color=plain_color,
    )
    embed.set_author(name=t(lang, "verify.author"))
    return embed


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}
        self.post_loop.start()

    def cog_unload(self):
        self.post_loop.cancel()

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

    async def _render_panel(self, guild, settings, target_channel=None, force_new=False):
        """Post or edit-in-place the verify panel. Returns the message or None.
        Editing an existing panel keeps it in sync with dashboard changes."""
        ch_id = settings.get("channel_id")
        channel = target_channel or (guild.get_channel(int(ch_id)) if ch_id else None)
        if channel is None:
            return None
        lang = await lang_for(self.backend_url, self.api_key, guild.id)
        plain_color = await general_config.get_embed_color(self.backend_url, self.api_key, guild.id, fallback=VERIFY_COLOR)
        cfg = settings.get("embed") or {}
        want_v2 = bool(settings.get("use_embed")) and is_components_v2(cfg)

        embed = None
        view = None
        if want_v2:
            view = build_panel_layout(settings, guild, lang)
            if view is None:
                want_v2 = False  # nothing renderable → classic fallback
        if not want_v2:
            embed = build_panel_embed(settings, guild, lang, plain_color)
            view = build_panel_view(settings.get("button_label") or t(lang, "verify.button"))

        msg = None
        existing_id = settings.get("panel_message_id")
        if existing_id and not force_new:
            try:
                existing = await channel.fetch_message(int(existing_id))
                if bool(existing.flags.components_v2) != want_v2:
                    # Format switched across the Components V2 boundary → repost.
                    try:
                        await existing.delete()
                    except Exception:
                        pass
                    msg = None
                else:
                    if want_v2:
                        await existing.edit(view=view)
                    else:
                        await existing.edit(embed=embed, view=view)
                    msg = existing
            except (discord.NotFound, discord.Forbidden, ValueError):
                msg = None  # gone / wrong channel → repost below
            except Exception as exc:
                print(f"[verify] edit failed in {guild.id}: {exc}")
                return None
        if msg is None:
            try:
                if want_v2:
                    msg = await channel.send(view=view)
                else:
                    msg = await channel.send(embed=embed, view=view)
            except discord.Forbidden:
                print(f"[verify] missing permission to post in {channel.id}")
                return None

        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild.id}/verification/panel",
            {"message_id": str(msg.id)},
        )
        return msg

    # ----- auto-update loop -------------------------------------------------

    @tasks.loop(seconds=POLL_SECONDS)
    async def post_loop(self):
        await self._post_pending()

    @post_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _post_pending(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/verification/pending")
        if not data:
            return
        for panel in (data.get("panels") or []):
            try:
                guild = self.bot.get_guild(int(panel["guild_id"]))
                if guild is not None:
                    await self._render_panel(guild, panel)
            except Exception as exc:
                print(f"[verify] pending post error for {panel.get('guild_id')}: {exc}")

    # ----- slash command ----------------------------------------------------

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
        msg = await self._render_panel(interaction.guild, settings, target_channel=channel)
        if msg is None:
            await interaction.followup.send(t(lang, "verify.cantPost"), ephemeral=True)
            return
        await interaction.followup.send(t(lang, "verify.panelPosted", channel=channel.mention), ephemeral=True)

    # ----- verify button ----------------------------------------------------

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
        # Optional: a role to strip on verify (e.g. an "Unverified" gate role).
        remove_id = settings.get("remove_role_id")
        remove_role = interaction.guild.get_role(int(remove_id)) if remove_id else None
        member = interaction.user
        has_verified = role in member.roles
        has_remove = remove_role is not None and remove_role in member.roles
        # Already fully verified (has the role, nothing left to strip) → no-op.
        if has_verified and not has_remove:
            await interaction.followup.send(t(lang, "verify.already"), ephemeral=True)
            return
        try:
            if not has_verified:
                await member.add_roles(role, reason="Verification")
            if has_remove:
                await member.remove_roles(remove_role, reason="Verification (remove gate role)")
            await interaction.followup.send(t(lang, "verify.success"), ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(t(lang, "verify.forbidden"), ephemeral=True)
        except Exception as exc:
            print(f"[verify] role update failed in {interaction.guild.id}: {exc}")
            await interaction.followup.send(t(lang, "verify.error"), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Verification(bot))
