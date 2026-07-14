"""Tickets cog.

A configurable support-ticket system:
  - Panel with either a category dropdown or per-category buttons (or a single
    "Open Ticket" button when no categories are configured). The panel is an
    embed designed in the dashboard.
  - Each ticket is a private channel (opener + support role). Inside it staff get
    a control bar: Claim, Add user, Remove user, Close.
  - Optional close-confirmation, transcript export, and a 1–5 star rating from the
    opener (in the channel and/or via DM).

Component interactions are handled via on_interaction (custom_ids below) so they
survive restarts. Admins post/refresh the panel with the `/ticketpanel` slash command.

custom_id scheme:
  ticket_open                         single default open button
  ticketcat:<category_id>             per-category open button
  ticket_select                       category dropdown (values = category id)
  ticket_claim / ticket_add / ticket_remove / ticket_close   control bar
  ticket_closeyes / ticket_closeno    close confirmation
  ticket_addsel:<channel_id> / ticket_remsel:<channel_id>    user select menus
  ticket_delete                       staff: delete a closed/kept channel
  ticketrate:<gid>:<ticket_id>:<n>    rating star (n = 1..5)

Requires Manage Channels. Logging prefix: "[tickets]".
"""

import asyncio
import html
import io
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post, bot_put
from utils.bot_i18n import t, lang_for
from utils.rich_message import is_components_v2, build_layout_view

SETTINGS_TTL_SECONDS = 120
TICKET_COLOR = 0x5865F2
DEFAULT_OPEN_ID = "__default__"

_BUTTON_STYLES = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}

# Inline CSS for the HTML ticket transcript (Discord-like dark theme). Kept as a
# plain string (no f-string) so the CSS braces don't need escaping.
_TRANSCRIPT_STYLE = """<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; background:#313338; color:#dbdee1; font-family:'gg sans','Segoe UI',Roboto,Helvetica,Arial,sans-serif; font-size:15px; line-height:1.45; }
.wrap { max-width:900px; margin:0 auto; padding:24px 16px 64px; }
header.tx { border-bottom:1px solid #3f4147; padding-bottom:16px; margin-bottom:12px; }
header.tx h1 { font-size:1.3rem; margin:0 0 6px; color:#f2f3f5; }
header.tx .sub { color:#949ba4; font-size:.85rem; }
.msg { display:flex; gap:14px; padding:7px 6px; border-radius:6px; }
.msg:hover { background:#2e3035; }
.avatar { width:40px; height:40px; border-radius:50%; flex-shrink:0; object-fit:cover; background:#5865f2; }
.avatar--ph { background:linear-gradient(135deg,#5865f2,#a78bfa); }
.body { min-width:0; flex:1; }
.meta { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; margin-bottom:2px; }
.author { color:#f2f3f5; font-weight:600; }
.handle, .ts { color:#949ba4; font-size:.72rem; }
.content { color:#dbdee1; word-wrap:break-word; overflow-wrap:anywhere; }
.muted { color:#949ba4; font-style:italic; }
.att-img img { max-width:340px; max-height:300px; border-radius:6px; margin-top:6px; display:block; }
.att-file { display:inline-block; margin-top:6px; color:#00a8fc; text-decoration:none; }
.att-file:hover { text-decoration:underline; }
a { color:#00a8fc; }
.empty { color:#949ba4; padding:32px; text-align:center; }
footer.tx { margin-top:24px; color:#6d7178; font-size:.72rem; text-align:center; }
</style>"""


def parse_emoji(raw):
    """Accept a unicode emoji or a custom '<:name:id>' string for buttons/options."""
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    if raw.startswith("<") and ":" in raw:
        try:
            return discord.PartialEmoji.from_str(raw)
        except Exception:
            return None
    return raw


def _color_int(value, fallback=TICKET_COLOR):
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return int(value[1:], 16)
        except ValueError:
            return fallback
    return fallback


def resolve_placeholders(text, *, user=None, guild=None, number=None, category=None):
    if not text:
        return text
    out = str(text)
    if user is not None:
        out = (out
               .replace("{user}", user.mention)
               .replace("{user.name}", user.display_name)
               .replace("{user.tag}", str(user))
               .replace("{user.id}", str(user.id)))
    if guild is not None:
        out = (out
               .replace("{guild}", guild.name)
               .replace("{guild.name}", guild.name)
               .replace("{guild.member_count}", str(guild.member_count or 0)))
    if number is not None:
        out = out.replace("{number}", str(number))
    if category is not None:
        out = out.replace("{category}", str(category))
    return out


def _avatar_or_url(value, user):
    if not value:
        return None
    value = str(value)
    if value == "{user.avatar}":
        return user.display_avatar.url if user else None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return None


def build_embed(cfg, *, user=None, guild=None, number=None, category=None, fallback_desc=None):
    """Build a discord.Embed from a dashboard embed config dict."""
    cfg = cfg or {}
    color = _color_int(cfg.get("color"))
    title = resolve_placeholders(cfg.get("title") or "", user=user, guild=guild, number=number, category=category)
    desc = resolve_placeholders(cfg.get("description") or "", user=user, guild=guild, number=number, category=category)
    if not desc and fallback_desc:
        desc = fallback_desc
    embed = discord.Embed(color=color)
    if title:
        embed.title = title[:256]
    if desc:
        embed.description = desc[:4096]
    thumb = _avatar_or_url(cfg.get("thumbnail"), user)
    if thumb:
        embed.set_thumbnail(url=thumb)
    image = _avatar_or_url(cfg.get("image"), user)
    if image:
        embed.set_image(url=image)
    footer = resolve_placeholders(cfg.get("footer") or "", user=user, guild=guild, number=number, category=category)
    if footer:
        embed.set_footer(text=footer[:2048])
    author_name = resolve_placeholders(cfg.get("author_name") or "", user=user, guild=guild, number=number, category=category)
    if author_name:
        icon = _avatar_or_url(cfg.get("author_icon_url"), user)
        embed.set_author(name=author_name[:256], icon_url=icon)
    if cfg.get("show_timestamp"):
        embed.timestamp = discord.utils.utcnow()
    return embed


def build_panel_items(settings, lang="en"):
    """The panel's interactive items (single button / category buttons / select)."""
    categories = [c for c in (settings.get("categories") or []) if c.get("enabled", True)]
    panel_type = settings.get("panel_type") or "dropdown"
    items = []

    if not categories:
        items.append(discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=(settings.get("button_label") or t(lang, "ticket.openButton"))[:80],
            custom_id="ticket_open",
            emoji="🎫",
        ))
        return items

    if panel_type == "buttons":
        for cat in categories[:25]:
            style = _BUTTON_STYLES.get(cat.get("button_style"), discord.ButtonStyle.primary)
            items.append(discord.ui.Button(
                style=style,
                label=(cat.get("label") or t(lang, "ticket.ticketFallback"))[:80],
                custom_id=f"ticketcat:{cat['id']}",
                emoji=parse_emoji(cat.get("emoji")),
            ))
        return items

    # dropdown
    options = []
    for cat in categories[:25]:
        options.append(discord.SelectOption(
            label=(cat.get("label") or t(lang, "ticket.ticketFallback"))[:100],
            value=str(cat["id"]),
            description=(cat.get("description") or "")[:100] or None,
            emoji=parse_emoji(cat.get("emoji")),
        ))
    items.append(discord.ui.Select(
        custom_id="ticket_select",
        placeholder=t(lang, "ticket.selectPlaceholder"),
        min_values=1,
        max_values=1,
        options=options,
    ))
    return items


def build_panel_view(settings, lang="en"):
    """Dropdown or buttons depending on panel_type + configured categories."""
    view = discord.ui.View(timeout=None)
    for it in build_panel_items(settings, lang):
        view.add_item(it)
    return view


def build_panel_layout(settings, guild, lang="en"):
    """Components V2 variant of the panel: accent container + panel items."""
    return build_layout_view(
        settings.get("panel_embed") or {},
        resolve_text=lambda s: resolve_placeholders(s or "", guild=guild),
        resolve_url=lambda s: _avatar_or_url(s, None) or "",
        action_items=build_panel_items(settings, lang),
    )


def build_control_items(settings, lang="en"):
    items = []
    if settings.get("claim_enabled", True):
        items.append(discord.ui.Button(style=discord.ButtonStyle.success, label=t(lang, "ticket.claim"), custom_id="ticket_claim", emoji="🙋"))
    items.append(discord.ui.Button(style=discord.ButtonStyle.secondary, label=t(lang, "ticket.addUser"), custom_id="ticket_add", emoji="➕"))
    items.append(discord.ui.Button(style=discord.ButtonStyle.secondary, label=t(lang, "ticket.removeUser"), custom_id="ticket_remove", emoji="➖"))
    items.append(discord.ui.Button(style=discord.ButtonStyle.danger, label=t(lang, "ticket.close"), custom_id="ticket_close", emoji="🔒"))
    return items


def build_control_view(settings, lang="en"):
    view = discord.ui.View(timeout=None)
    for it in build_control_items(settings, lang):
        view.add_item(it)
    return view


def build_welcome_layout(settings, guild, lang, *, user, number, category, extra_top=None):
    """Components V2 variant of the ticket welcome message: accent container
    (from welcome_embed blocks, with placeholders) + control buttons."""
    cat_label = (category or {}).get("label") if isinstance(category, dict) else category
    return build_layout_view(
        settings.get("welcome_embed") or {},
        resolve_text=lambda s: resolve_placeholders(
            s or "", user=user, guild=guild, number=number, category=cat_label),
        resolve_url=lambda s: _avatar_or_url(s, user) or "",
        action_items=build_control_items(settings, lang),
        extra_top=extra_top,
    )


def build_close_confirm_view(lang="en"):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label=t(lang, "ticket.closeTicket"), custom_id="ticket_closeyes", emoji="🔒"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label=t(lang, "ticket.cancel"), custom_id="ticket_closeno"))
    return view


def build_rating_view(gid, ticket_id):
    view = discord.ui.View(timeout=None)
    for n in range(1, 6):
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="⭐" * n,
            custom_id=f"ticketrate:{gid}:{ticket_id}:{n}",
        ))
    return view


def build_delete_view(lang="en"):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label=t(lang, "ticket.deleteChannel"), custom_id="ticket_delete", emoji="🗑"))
    return view


def build_user_select_view(custom_id, placeholder):
    view = discord.ui.View(timeout=300)
    view.add_item(discord.ui.UserSelect(custom_id=custom_id, placeholder=placeholder, min_values=1, max_values=10))
    return view


class RatingModal(discord.ui.Modal):
    def __init__(self, cog, gid, ticket_id, rating, in_channel, lang="en"):
        super().__init__(title=t(lang, "ticket.rateModalTitle", stars="⭐" * rating))
        self.cog = cog
        self.gid = gid
        self.ticket_id = ticket_id
        self.rating = rating
        self.in_channel = in_channel
        self.comment = discord.ui.TextInput(
            label=t(lang, "ticket.commentLabel"),
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            placeholder=t(lang, "ticket.commentPlaceholder"),
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction):
        await self.cog.save_rating(interaction, self.gid, self.ticket_id, self.rating, str(self.comment.value or ""), self.in_channel)


class Tickets(commands.Cog):
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
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "tickets")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    def _find_category(self, settings, category_id):
        for cat in (settings.get("categories") or []):
            if str(cat.get("id")) == str(category_id):
                return cat
        return None

    # ----- Panel command -----

    @app_commands.command(name="ticketpanel", description="Post or refresh the ticket panel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        perms = getattr(interaction.user, "guild_permissions", None)
        if not (perms and perms.administrator):
            await interaction.response.send_message(t(lang, "ticket.adminOnly"), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        settings = await self._get_settings(interaction.guild.id, force=True)
        if not settings or not settings.get("enabled"):
            await interaction.followup.send(t(lang, "ticket.notEnabled"), ephemeral=True)
            return
        channel_id = settings.get("panel_channel_id")
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id else interaction.channel
        panel_cfg = settings.get("panel_embed") or {}
        view = None
        if is_components_v2(panel_cfg):
            view = build_panel_layout(settings, interaction.guild, lang=lang)
        try:
            if view is not None:
                msg = await channel.send(view=view)
            else:
                embed = build_embed(
                    panel_cfg,
                    guild=interaction.guild,
                    fallback_desc=settings.get("panel_message") or t(lang, "ticket.fallbackPanelDesc"),
                )
                msg = await channel.send(embed=embed, view=build_panel_view(settings, lang=lang))
        except discord.Forbidden:
            await interaction.followup.send(t(lang, "ticket.cantPostPanel"), ephemeral=True)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/tickets/panel", {"message_id": str(msg.id)})
        await interaction.followup.send(t(lang, "ticket.panelPosted", channel=channel.mention), ephemeral=True)

    # ----- Interaction dispatch -----

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""

        if custom_id == "ticket_open":
            await self._open(interaction, None)
        elif custom_id.startswith("ticketcat:"):
            await self._open(interaction, custom_id.split(":", 1)[1])
        elif custom_id == "ticket_select":
            values = (interaction.data or {}).get("values") or []
            await self._open(interaction, values[0] if values else None)
        elif custom_id == "ticket_claim":
            await self._claim(interaction)
        elif custom_id == "ticket_add":
            await self._prompt_user_select(interaction, "add")
        elif custom_id == "ticket_remove":
            await self._prompt_user_select(interaction, "remove")
        elif custom_id.startswith("ticket_addsel:"):
            await self._apply_user_select(interaction, "add", custom_id.split(":", 1)[1])
        elif custom_id.startswith("ticket_remsel:"):
            await self._apply_user_select(interaction, "remove", custom_id.split(":", 1)[1])
        elif custom_id == "ticket_close":
            await self._close_request(interaction)
        elif custom_id == "ticket_closeyes":
            await self._do_close(interaction)
        elif custom_id == "ticket_closeno":
            lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id) if interaction.guild else "en"
            await interaction.response.edit_message(content=t(lang, "ticket.closeCancelled"), view=None)
        elif custom_id == "ticket_delete":
            await self._delete_channel(interaction)
        elif custom_id.startswith("ticketrate:"):
            await self._rate_click(interaction, custom_id)

    # ----- Open -----

    async def _open(self, interaction, category_id):
        guild = interaction.guild
        if guild is None:
            return
        await interaction.response.defer(ephemeral=True)

        lang = await lang_for(self.backend_url, self.api_key, guild.id)
        settings = await self._get_settings(guild.id)
        if not settings or not settings.get("enabled"):
            await interaction.followup.send(t(lang, "ticket.disabled"), ephemeral=True)
            return

        if category_id in (None, "", DEFAULT_OPEN_ID):
            category = None
        else:
            category = self._find_category(settings, category_id)

        existing = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/tickets/open?user_id={interaction.user.id}")
        if existing and existing.get("ticket"):
            ch_id = existing["ticket"].get("channel_id")
            await interaction.followup.send(t(lang, "ticket.alreadyOpen", channel=ch_id), ephemeral=True)
            return

        # Resolve category-channel / support-role with per-category override.
        cat_chan_id = (category or {}).get("category_id") or settings.get("category_id")
        discord_category = None
        if cat_chan_id:
            c = guild.get_channel(int(cat_chan_id))
            if isinstance(c, discord.CategoryChannel):
                discord_category = c

        support_role = None
        role_id = (category or {}).get("support_role_id") or settings.get("support_role_id")
        if role_id:
            support_role = guild.get_role(int(role_id))

        ping_role = None
        ping_id = (category or {}).get("ping_role_id") or settings.get("ping_role_id")
        if ping_id:
            ping_role = guild.get_role(int(ping_id))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if support_role is not None:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        base_name = resolve_placeholders(
            settings.get("naming_template") or "ticket-{user}",
            user=interaction.user,
            category=(category or {}).get("label", ""),
        ).replace("{number}", "")
        try:
            channel = await guild.create_text_channel(
                base_name[:90] or "ticket",
                category=discord_category,
                overwrites=overwrites,
                reason=f"Ticket for {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(t(lang, "ticket.createForbidden"), ephemeral=True)
            return
        except Exception as exc:
            print(f"[tickets] create channel failed in {guild.id}: {exc}")
            await interaction.followup.send(t(lang, "ticket.createFailed"), ephemeral=True)
            return

        created = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/tickets", {
            "channel_id": str(channel.id),
            "user_id": str(interaction.user.id),
            "ticket_category_id": (category or {}).get("id"),
        })
        number = (created or {}).get("number")

        # Rename with the assigned number if the template asks for it.
        template = settings.get("naming_template") or "ticket-{user}"
        if number and "{number}" in template:
            try:
                new_name = resolve_placeholders(
                    template, user=interaction.user, number=number, category=(category or {}).get("label", "")
                )
                await channel.edit(name=new_name[:90])
            except Exception:
                pass

        welcome_text = (category or {}).get("welcome_message") or None
        embed = build_embed(
            settings.get("welcome_embed"),
            user=interaction.user,
            guild=guild,
            number=number,
            category=(category or {}).get("label"),
            fallback_desc=t(lang, "ticket.welcomeFallback"),
        )
        if welcome_text:
            embed.add_field(name="​", value=resolve_placeholders(welcome_text, user=interaction.user, guild=guild, number=number)[:1024], inline=False)
        if category:
            embed.add_field(name=t(lang, "ticket.fieldCategory"), value=category.get("label", "—"), inline=True)
        if number:
            embed.add_field(name=t(lang, "ticket.fieldTicket"), value=f"#{number}", inline=True)

        content_bits = [interaction.user.mention]
        if support_role is not None:
            content_bits.append(support_role.mention)
        if ping_role is not None and (not support_role or ping_role.id != support_role.id):
            content_bits.append(ping_role.mention)
        try:
            welcome_cfg = settings.get("welcome_embed") or {}
            if is_components_v2(welcome_cfg):
                # V2: mentions become a top text block (content isn't allowed next
                # to a V2 view); allow the pings through explicitly.
                view = build_welcome_layout(
                    settings, guild, lang, user=interaction.user, number=number,
                    category=category, extra_top=" ".join(content_bits),
                )
                if view is not None:
                    await channel.send(
                        view=view,
                        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                    )
                else:
                    await channel.send(content=" ".join(content_bits), embed=embed, view=build_control_view(settings, lang=lang))
            else:
                await channel.send(content=" ".join(content_bits), embed=embed, view=build_control_view(settings, lang=lang))
        except Exception as exc:
            print(f"[tickets] post in channel failed: {exc}")

        log_desc = t(lang, "ticket.logOpened", number=number, user=interaction.user.mention, channel=channel.mention)
        if category:
            log_desc += t(lang, "ticket.logCategorySuffix", category=category.get("label"))
        await self._log_event(guild, settings, discord.Embed(description=log_desc, color=TICKET_COLOR))
        await interaction.followup.send(t(lang, "ticket.opened", channel=channel.mention), ephemeral=True)

    # ----- Claim -----

    async def _is_staff(self, interaction, settings):
        perms = interaction.channel.permissions_for(interaction.user) if interaction.channel else None
        if perms and perms.manage_channels:
            return True
        role_id = settings.get("support_role_id")
        if role_id and isinstance(interaction.user, discord.Member):
            if any(str(r.id) == str(role_id) for r in interaction.user.roles):
                return True
        return False

    async def _claim(self, interaction):
        await interaction.response.defer(ephemeral=True)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        settings = await self._get_settings(interaction.guild.id)
        if not await self._is_staff(interaction, settings or {}):
            await interaction.followup.send(t(lang, "ticket.onlyStaffClaim"), ephemeral=True)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/tickets/claim",
                      {"channel_id": str(interaction.channel.id), "user_id": str(interaction.user.id)})
        try:
            await interaction.channel.send(embed=discord.Embed(
                description=t(lang, "ticket.claimedBy", user=interaction.user.mention),
                color=0x57F287,
            ))
        except Exception:
            pass
        await interaction.followup.send(t(lang, "ticket.youClaimed"), ephemeral=True)

    # ----- Add / remove user -----

    async def _prompt_user_select(self, interaction, mode):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        settings = await self._get_settings(interaction.guild.id)
        if not await self._is_staff(interaction, settings or {}):
            await interaction.response.send_message(t(lang, "ticket.onlyStaffMembers"), ephemeral=True)
            return
        cid = f"ticket_addsel:{interaction.channel.id}" if mode == "add" else f"ticket_remsel:{interaction.channel.id}"
        placeholder = t(lang, "ticket.selectAdd") if mode == "add" else t(lang, "ticket.selectRemove")
        content = t(lang, "ticket.whoAdd") if mode == "add" else t(lang, "ticket.whoRemove")
        await interaction.response.send_message(content=content, view=build_user_select_view(cid, placeholder), ephemeral=True)

    async def _apply_user_select(self, interaction, mode, channel_id):
        await interaction.response.defer(ephemeral=True)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id.isdigit() else interaction.channel
        if channel is None:
            await interaction.followup.send(t(lang, "ticket.channelNotFound"), ephemeral=True)
            return
        user_ids = (interaction.data or {}).get("values") or []
        changed = []
        for uid in user_ids:
            member = interaction.guild.get_member(int(uid)) if uid.isdigit() else None
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(int(uid))
                except Exception:
                    member = None
            if member is None:
                continue
            try:
                if mode == "add":
                    await channel.set_permissions(member, view_channel=True, send_messages=True, attach_files=True, reason="Ticket add user")
                else:
                    await channel.set_permissions(member, overwrite=None, reason="Ticket remove user")
                changed.append(member)
            except Exception as exc:
                print(f"[tickets] {mode} user failed: {exc}")
        if changed:
            await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/tickets/users", {
                "channel_id": str(channel.id),
                ("add" if mode == "add" else "remove"): [str(m.id) for m in changed],
            })
            names = ", ".join(m.mention for m in changed)
            desc = t(lang, "ticket.membersAdded", names=names) if mode == "add" else t(lang, "ticket.membersRemoved", names=names)
            try:
                await channel.send(embed=discord.Embed(description=desc, color=TICKET_COLOR))
            except Exception:
                pass
            result_msg = t(lang, "ticket.resultAdded", names=names) if mode == "add" else t(lang, "ticket.resultRemoved", names=names)
            await interaction.followup.send(result_msg, ephemeral=True)
        else:
            await interaction.followup.send(t(lang, "ticket.noChanges"), ephemeral=True)

    # ----- Close -----

    async def _close_request(self, interaction):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        settings = await self._get_settings(interaction.guild.id)
        ticket = await self._ticket_for(interaction.guild.id, interaction.channel.id)
        is_owner = ticket and str(ticket.get("user_id")) == str(interaction.user.id)
        if not (await self._is_staff(interaction, settings or {}) or is_owner):
            await interaction.response.send_message(t(lang, "ticket.onlyStaffOrOwner"), ephemeral=True)
            return
        if (settings or {}).get("close_confirm", True):
            await interaction.response.send_message(t(lang, "ticket.confirmClose"), view=build_close_confirm_view(lang=lang), ephemeral=True)
        else:
            await self._do_close(interaction)

    async def _ticket_for(self, guild_id, channel_id):
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/tickets/by-channel?channel_id={channel_id}")
        return (data or {}).get("ticket")

    async def _do_close(self, interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        channel = interaction.channel
        lang = await lang_for(self.backend_url, self.api_key, guild.id)
        settings = await self._get_settings(guild.id)
        ticket = await self._ticket_for(guild.id, channel.id)

        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/tickets/close",
                      {"channel_id": str(channel.id), "closed_by": str(interaction.user.id)})
        await self._maybe_transcript(channel, settings, interaction.user)
        await self._log_event(guild, settings, discord.Embed(
            description=t(lang, "ticket.logClosed",
                          number=("#" + str(ticket.get("number"))) if ticket else "",
                          user=interaction.user.mention),
            color=0xED4245,
        ))

        rating_enabled = bool((settings or {}).get("rating_enabled"))
        rating_mode = (settings or {}).get("rating_mode") or "channel"
        rate_channel = rating_enabled and rating_mode in ("channel", "both")
        rate_dm = rating_enabled and rating_mode in ("dm", "both")
        ticket_id = (ticket or {}).get("id")
        opener_id = (ticket or {}).get("user_id")

        if rate_dm and ticket_id and opener_id:
            await self._send_dm_rating(guild, opener_id, ticket_id)

        await interaction.followup.send(t(lang, "ticket.closed"), ephemeral=True)

        if rate_channel and ticket_id:
            # Keep the channel so the opener can rate; lock it down + offer staff delete.
            try:
                if opener_id:
                    opener = guild.get_member(int(opener_id))
                    if opener:
                        await channel.set_permissions(opener, view_channel=True, send_messages=False)
                await channel.send(
                    content=(f"<@{opener_id}> " if opener_id else "") + t(lang, "ticket.ratePrompt"),
                    embed=discord.Embed(description=t(lang, "ticket.rateLegend"), color=TICKET_COLOR),
                    view=build_rating_view(guild.id, ticket_id),
                )
                await channel.send(t(lang, "ticket.staffRemoveHint"), view=build_delete_view(lang=lang))
            except Exception as exc:
                print(f"[tickets] post rating prompt failed: {exc}")
        else:
            await asyncio.sleep(5)
            try:
                await channel.delete(reason="Ticket closed")
            except Exception as exc:
                print(f"[tickets] delete channel failed: {exc}")

    async def _delete_channel(self, interaction):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        settings = await self._get_settings(interaction.guild.id)
        if not await self._is_staff(interaction, settings or {}):
            await interaction.response.send_message(t(lang, "ticket.onlyStaffDelete"), ephemeral=True)
            return
        await interaction.response.send_message(t(lang, "ticket.deleting"), ephemeral=True)
        try:
            await interaction.channel.delete(reason="Ticket channel removed by staff")
        except Exception as exc:
            print(f"[tickets] staff delete failed: {exc}")

    # ----- Rating -----

    async def _rate_click(self, interaction, custom_id):
        # custom_id = ticketrate:<gid>:<ticket_id>:<n>
        parts = custom_id.split(":")
        if len(parts) != 4:
            return
        _, gid, ticket_id, n = parts
        try:
            rating = max(1, min(5, int(n)))
        except ValueError:
            return
        in_channel = interaction.guild is not None
        lang = await lang_for(self.backend_url, self.api_key, gid)
        await interaction.response.send_modal(RatingModal(self, gid, ticket_id, rating, in_channel, lang=lang))

    async def save_rating(self, interaction, gid, ticket_id, rating, comment, in_channel):
        lang = await lang_for(self.backend_url, self.api_key, gid)
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{gid}/tickets/rating",
                      {"ticket_id": ticket_id, "rating": rating, "comment": comment})
        await interaction.response.send_message(t(lang, "ticket.thanksRating", stars="⭐" * rating), ephemeral=True)

        # Post the rating into the configured log channel.
        settings = await self._get_settings(gid)
        guild = self.bot.get_guild(int(gid)) if str(gid).isdigit() else None
        if guild:
            embed = discord.Embed(
                title=t(lang, "ticket.ratedTitle"),
                description=t(lang, "ticket.ratedDesc", stars="⭐" * rating, rating=rating, user=interaction.user.mention),
                color=0xFEE75C,
            )
            if comment.strip():
                embed.add_field(name=t(lang, "ticket.commentField"), value=comment.strip()[:1024], inline=False)
            await self._log_event(guild, settings, embed)

        if in_channel and interaction.channel:
            try:
                await interaction.channel.send(t(lang, "ticket.ratingReceived"))
                await asyncio.sleep(4)
                await interaction.channel.delete(reason="Ticket rated & closed")
            except Exception as exc:
                print(f"[tickets] post-rating delete failed: {exc}")

    async def _send_dm_rating(self, guild, opener_id, ticket_id):
        try:
            member = guild.get_member(int(opener_id)) or await guild.fetch_member(int(opener_id))
            if member is None:
                return
            lang = await lang_for(self.backend_url, self.api_key, guild.id)
            await member.send(
                content=t(lang, "ticket.dmRating", guild=guild.name),
                view=build_rating_view(guild.id, ticket_id),
            )
        except Exception as exc:
            print(f"[tickets] DM rating failed: {exc}")

    # ----- Helpers -----

    async def _log_event(self, guild, settings, embed):
        chan_id = (settings or {}).get("log_channel_id") or (settings or {}).get("transcript_channel_id")
        if not chan_id:
            return
        target = guild.get_channel(int(chan_id))
        if target is None:
            return
        try:
            await target.send(embed=embed)
        except Exception:
            pass

    async def _maybe_transcript(self, channel, settings, closer):
        chan_id = (settings or {}).get("transcript_channel_id")
        if not chan_id:
            return
        target = channel.guild.get_channel(int(chan_id))
        if target is None:
            return
        lang = await lang_for(self.backend_url, self.api_key, channel.guild.id)
        try:
            messages = []
            async for m in channel.history(limit=1000, oldest_first=True):
                messages.append(m)
            doc = self._render_transcript_html(channel, messages, closer)
            buf = io.BytesIO(doc.encode("utf-8"))
            # Safe filename (channel names can contain non-ascii / odd chars).
            safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in channel.name)[:60] or "ticket"
            file = discord.File(buf, filename=f"transcript-{safe}.html")
            embed = discord.Embed(
                title=t(lang, "ticket.transcriptTitle"),
                description=t(lang, "ticket.transcriptDesc", channel=channel.name, closer=closer.mention, count=len(messages)),
                color=TICKET_COLOR,
                timestamp=discord.utils.utcnow(),
            )
            await target.send(embed=embed, file=file)
        except discord.Forbidden:
            print(f"[tickets] missing permission to post transcript in {channel.guild.id}")
        except Exception as exc:
            print(f"[tickets] transcript failed in {channel.guild.id}: {exc}")

    def _render_transcript_html(self, channel, messages, closer):
        """Build a self-contained, Discord-styled HTML transcript. Every piece of
        user content is HTML-escaped — the file is opened in a browser, so raw
        content would otherwise allow HTML/script injection."""
        esc = html.escape
        gname = esc(channel.guild.name if channel.guild else "")
        cname = esc(channel.name)
        closer_name = esc(str(closer))
        count = len(messages)

        rows = []
        for m in messages:
            ts = m.created_at.strftime("%d.%m.%Y %H:%M")
            author = esc(getattr(m.author, "display_name", None) or str(m.author))
            handle = esc(str(m.author))
            try:
                avatar = esc(str(m.author.display_avatar.url), quote=True)
            except Exception:
                avatar = ""
            content = esc(m.content or "").replace("\n", "<br>")
            atts = ""
            for att in m.attachments:
                url = esc(att.url, quote=True)
                fn = esc(att.filename)
                ct = att.content_type or ""
                is_img = ct.startswith("image/") or att.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp"))
                if is_img:
                    atts += f'<a class="att-img" href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{fn}" loading="lazy"></a>'
                else:
                    atts += f'<a class="att-file" href="{url}" target="_blank" rel="noopener">\U0001F4CE {fn}</a>'
            if not content and not atts and m.embeds:
                content = '<span class="muted">[embed]</span>'
            avatar_html = (f'<img class="avatar" src="{avatar}" alt="" loading="lazy">'
                           if avatar else '<div class="avatar avatar--ph"></div>')
            rows.append(
                f'<div class="msg">{avatar_html}<div class="body">'
                f'<div class="meta"><span class="author">{author}</span>'
                f'<span class="handle">{handle}</span><span class="ts">{ts}</span></div>'
                f'<div class="content">{content}{atts}</div></div></div>'
            )
        body = "\n".join(rows) or '<div class="empty">Keine Nachrichten.</div>'

        return (
            '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Transkript · #{cname}</title>'
            + _TRANSCRIPT_STYLE +
            '</head><body><div class="wrap">'
            f'<header class="tx"><h1># {cname}</h1>'
            f'<div class="sub">{gname} · {count} Nachrichten · geschlossen von {closer_name}</div></header>'
            + body +
            '<footer class="tx">Transkript erstellt von ProjectX</footer>'
            '</div></body></html>'
        )

    # ----- Prefix commands (parallel to the buttons) -----

    @commands.command(name="claim")
    @commands.guild_only()
    async def claim_cmd(self, ctx):
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        settings = await self._get_settings(ctx.guild.id)
        ticket = await self._ticket_for(ctx.guild.id, ctx.channel.id)
        if not ticket:
            return
        if not (ctx.author.guild_permissions.manage_channels or self._has_support_role(ctx.author, settings)):
            await ctx.reply(t(lang, "ticket.onlyStaffClaim"), mention_author=False)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/claim",
                      {"channel_id": str(ctx.channel.id), "user_id": str(ctx.author.id)})
        await ctx.send(embed=discord.Embed(description=t(lang, "ticket.claimedBy", user=ctx.author.mention), color=0x57F287))

    @commands.command(name="ticketadd")
    @commands.guild_only()
    async def ticketadd_cmd(self, ctx, member: discord.Member):
        if not await self._cmd_in_ticket(ctx):
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        try:
            await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, attach_files=True, reason="Ticket add user")
            await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/users", {"channel_id": str(ctx.channel.id), "add": [str(member.id)]})
            await ctx.send(embed=discord.Embed(description=t(lang, "ticket.membersAdded", names=member.mention), color=TICKET_COLOR))
        except discord.Forbidden:
            await ctx.reply(t(lang, "ticket.permChangeFailed"), mention_author=False)

    @commands.command(name="ticketremove")
    @commands.guild_only()
    async def ticketremove_cmd(self, ctx, member: discord.Member):
        if not await self._cmd_in_ticket(ctx):
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        try:
            await ctx.channel.set_permissions(member, overwrite=None, reason="Ticket remove user")
            await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/users", {"channel_id": str(ctx.channel.id), "remove": [str(member.id)]})
            await ctx.send(embed=discord.Embed(description=t(lang, "ticket.membersRemoved", names=member.mention), color=TICKET_COLOR))
        except discord.Forbidden:
            await ctx.reply(t(lang, "ticket.permChangeFailed"), mention_author=False)

    @commands.command(name="ticketclose")
    @commands.guild_only()
    async def ticketclose_cmd(self, ctx):
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        settings = await self._get_settings(ctx.guild.id)
        ticket = await self._ticket_for(ctx.guild.id, ctx.channel.id)
        if not ticket:
            return
        is_owner = str(ticket.get("user_id")) == str(ctx.author.id)
        if not (ctx.author.guild_permissions.manage_channels or self._has_support_role(ctx.author, settings) or is_owner):
            await ctx.reply(t(lang, "ticket.onlyStaffOrOwner"), mention_author=False)
            return
        await ctx.send(t(lang, "ticket.closingIn5"))
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/close", {"channel_id": str(ctx.channel.id), "closed_by": str(ctx.author.id)})
        await self._maybe_transcript(ctx.channel, settings, ctx.author)
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason="Ticket closed")
        except Exception as exc:
            print(f"[tickets] delete channel failed: {exc}")

    def _has_support_role(self, member, settings):
        role_id = (settings or {}).get("support_role_id")
        if not role_id or not isinstance(member, discord.Member):
            return False
        return any(str(r.id) == str(role_id) for r in member.roles)

    async def _cmd_in_ticket(self, ctx):
        settings = await self._get_settings(ctx.guild.id)
        ticket = await self._ticket_for(ctx.guild.id, ctx.channel.id)
        if not ticket:
            return False
        if not (ctx.author.guild_permissions.manage_channels or self._has_support_role(ctx.author, settings)):
            lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
            await ctx.reply(t(lang, "ticket.onlyStaffMembers"), mention_author=False)
            return False
        return True


async def setup(bot):
    await bot.add_cog(Tickets(bot))
