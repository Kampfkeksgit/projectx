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
survive restarts. Admins post/refresh the panel with `!ticketpanel`.

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
import io
import time

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post, bot_put

SETTINGS_TTL_SECONDS = 120
TICKET_COLOR = 0x5865F2
DEFAULT_OPEN_ID = "__default__"

_BUTTON_STYLES = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}


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


def build_panel_view(settings):
    """Dropdown or buttons depending on panel_type + configured categories."""
    view = discord.ui.View(timeout=None)
    categories = [c for c in (settings.get("categories") or []) if c.get("enabled", True)]
    panel_type = settings.get("panel_type") or "dropdown"

    if not categories:
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=(settings.get("button_label") or "Open Ticket")[:80],
            custom_id="ticket_open",
            emoji="🎫",
        ))
        return view

    if panel_type == "buttons":
        for cat in categories[:25]:
            style = _BUTTON_STYLES.get(cat.get("button_style"), discord.ButtonStyle.primary)
            view.add_item(discord.ui.Button(
                style=style,
                label=(cat.get("label") or "Ticket")[:80],
                custom_id=f"ticketcat:{cat['id']}",
                emoji=parse_emoji(cat.get("emoji")),
            ))
        return view

    # dropdown
    options = []
    for cat in categories[:25]:
        options.append(discord.SelectOption(
            label=(cat.get("label") or "Ticket")[:100],
            value=str(cat["id"]),
            description=(cat.get("description") or "")[:100] or None,
            emoji=parse_emoji(cat.get("emoji")),
        ))
    view.add_item(discord.ui.Select(
        custom_id="ticket_select",
        placeholder="Select a ticket category…",
        min_values=1,
        max_values=1,
        options=options,
    ))
    return view


def build_control_view(settings):
    view = discord.ui.View(timeout=None)
    if settings.get("claim_enabled", True):
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.success, label="Claim", custom_id="ticket_claim", emoji="🙋"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Add user", custom_id="ticket_add", emoji="➕"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Remove user", custom_id="ticket_remove", emoji="➖"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label="Close", custom_id="ticket_close", emoji="🔒"))
    return view


def build_close_confirm_view():
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label="Close ticket", custom_id="ticket_closeyes", emoji="🔒"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", custom_id="ticket_closeno"))
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


def build_delete_view():
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label="Delete channel", custom_id="ticket_delete", emoji="🗑"))
    return view


def build_user_select_view(custom_id, placeholder):
    view = discord.ui.View(timeout=300)
    view.add_item(discord.ui.UserSelect(custom_id=custom_id, placeholder=placeholder, min_values=1, max_values=10))
    return view


class RatingModal(discord.ui.Modal):
    def __init__(self, cog, gid, ticket_id, rating, in_channel):
        super().__init__(title=f"Rate your support ({'⭐' * rating})")
        self.cog = cog
        self.gid = gid
        self.ticket_id = ticket_id
        self.rating = rating
        self.in_channel = in_channel
        self.comment = discord.ui.TextInput(
            label="Comment (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            placeholder="Tell us about your experience…",
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

    @commands.command(name="ticketpanel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def ticketpanel(self, ctx):
        settings = await self._get_settings(ctx.guild.id, force=True)
        if not settings or not settings.get("enabled"):
            await ctx.reply("Tickets are not enabled.", mention_author=False)
            return
        channel_id = settings.get("panel_channel_id")
        channel = ctx.guild.get_channel(int(channel_id)) if channel_id else ctx.channel
        embed = build_embed(
            settings.get("panel_embed"),
            guild=ctx.guild,
            fallback_desc=settings.get("panel_message") or "Click below to open a ticket.",
        )
        try:
            msg = await channel.send(embed=embed, view=build_panel_view(settings))
        except discord.Forbidden:
            await ctx.reply("I can't post in the ticket channel.", mention_author=False)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/panel", {"message_id": str(msg.id)})
        if channel.id != ctx.channel.id:
            await ctx.reply(f"🎫 Ticket panel posted in {channel.mention}.", mention_author=False)

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
            await interaction.response.edit_message(content="Close cancelled.", view=None)
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

        settings = await self._get_settings(guild.id)
        if not settings or not settings.get("enabled"):
            await interaction.followup.send("Tickets are disabled.", ephemeral=True)
            return

        if category_id in (None, "", DEFAULT_OPEN_ID):
            category = None
        else:
            category = self._find_category(settings, category_id)

        existing = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/tickets/open?user_id={interaction.user.id}")
        if existing and existing.get("ticket"):
            ch_id = existing["ticket"].get("channel_id")
            await interaction.followup.send(f"You already have an open ticket: <#{ch_id}>", ephemeral=True)
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
            await interaction.followup.send("I couldn't create the ticket channel (missing Manage Channels).", ephemeral=True)
            return
        except Exception as exc:
            print(f"[tickets] create channel failed in {guild.id}: {exc}")
            await interaction.followup.send("Something went wrong opening your ticket.", ephemeral=True)
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
            fallback_desc="A team member will be with you shortly.",
        )
        if welcome_text:
            embed.add_field(name="​", value=resolve_placeholders(welcome_text, user=interaction.user, guild=guild, number=number)[:1024], inline=False)
        if category:
            embed.add_field(name="Category", value=category.get("label", "—"), inline=True)
        if number:
            embed.add_field(name="Ticket", value=f"#{number}", inline=True)

        content_bits = [interaction.user.mention]
        if support_role is not None:
            content_bits.append(support_role.mention)
        if ping_role is not None and (not support_role or ping_role.id != support_role.id):
            content_bits.append(ping_role.mention)
        try:
            await channel.send(content=" ".join(content_bits), embed=embed, view=build_control_view(settings))
        except Exception as exc:
            print(f"[tickets] post in channel failed: {exc}")

        await self._log_event(guild, settings, discord.Embed(
            description=f"🎫 Ticket **#{number}** opened by {interaction.user.mention} in {channel.mention}"
                        + (f" · *{category.get('label')}*" if category else ""),
            color=TICKET_COLOR,
        ))
        await interaction.followup.send(f"🎫 Ticket opened: {channel.mention}", ephemeral=True)

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
        settings = await self._get_settings(interaction.guild.id)
        if not await self._is_staff(interaction, settings or {}):
            await interaction.followup.send("Only staff can claim tickets.", ephemeral=True)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/tickets/claim",
                      {"channel_id": str(interaction.channel.id), "user_id": str(interaction.user.id)})
        try:
            await interaction.channel.send(embed=discord.Embed(
                description=f"🙋 Ticket claimed by {interaction.user.mention}.",
                color=0x57F287,
            ))
        except Exception:
            pass
        await interaction.followup.send("You claimed this ticket.", ephemeral=True)

    # ----- Add / remove user -----

    async def _prompt_user_select(self, interaction, mode):
        settings = await self._get_settings(interaction.guild.id)
        if not await self._is_staff(interaction, settings or {}):
            await interaction.response.send_message("Only staff can manage ticket members.", ephemeral=True)
            return
        cid = f"ticket_addsel:{interaction.channel.id}" if mode == "add" else f"ticket_remsel:{interaction.channel.id}"
        placeholder = "Select users to add…" if mode == "add" else "Select users to remove…"
        content = "Who should be added to this ticket?" if mode == "add" else "Who should be removed from this ticket?"
        await interaction.response.send_message(content=content, view=build_user_select_view(cid, placeholder), ephemeral=True)

    async def _apply_user_select(self, interaction, mode, channel_id):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id.isdigit() else interaction.channel
        if channel is None:
            await interaction.followup.send("Ticket channel not found.", ephemeral=True)
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
            verb = "added to" if mode == "add" else "removed from"
            try:
                await channel.send(embed=discord.Embed(description=f"{'➕' if mode == 'add' else '➖'} {names} {verb} the ticket.", color=TICKET_COLOR))
            except Exception:
                pass
            await interaction.followup.send(f"{'Added' if mode == 'add' else 'Removed'}: {names}", ephemeral=True)
        else:
            await interaction.followup.send("No changes made.", ephemeral=True)

    # ----- Close -----

    async def _close_request(self, interaction):
        settings = await self._get_settings(interaction.guild.id)
        ticket = await self._ticket_for(interaction.guild.id, interaction.channel.id)
        is_owner = ticket and str(ticket.get("user_id")) == str(interaction.user.id)
        if not (await self._is_staff(interaction, settings or {}) or is_owner):
            await interaction.response.send_message("Only staff or the ticket owner can close this.", ephemeral=True)
            return
        if (settings or {}).get("close_confirm", True):
            await interaction.response.send_message("Are you sure you want to close this ticket?", view=build_close_confirm_view(), ephemeral=True)
        else:
            await self._do_close(interaction)

    async def _ticket_for(self, guild_id, channel_id):
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/tickets/by-channel?channel_id={channel_id}")
        return (data or {}).get("ticket")

    async def _do_close(self, interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        channel = interaction.channel
        settings = await self._get_settings(guild.id)
        ticket = await self._ticket_for(guild.id, channel.id)

        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/tickets/close",
                      {"channel_id": str(channel.id), "closed_by": str(interaction.user.id)})
        await self._maybe_transcript(channel, settings, interaction.user)
        await self._log_event(guild, settings, discord.Embed(
            description=f"🔒 Ticket {('#' + str(ticket.get('number'))) if ticket else ''} closed by {interaction.user.mention}",
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

        await interaction.followup.send("Ticket closed.", ephemeral=True)

        if rate_channel and ticket_id:
            # Keep the channel so the opener can rate; lock it down + offer staff delete.
            try:
                if opener_id:
                    opener = guild.get_member(int(opener_id))
                    if opener:
                        await channel.set_permissions(opener, view_channel=True, send_messages=False)
                await channel.send(
                    content=(f"<@{opener_id}> " if opener_id else "") + "How was our support? Tap a rating below:",
                    embed=discord.Embed(description="⭐ = poor · ⭐⭐⭐⭐⭐ = excellent", color=TICKET_COLOR),
                    view=build_rating_view(guild.id, ticket_id),
                )
                await channel.send("Staff can remove this channel once done:", view=build_delete_view())
            except Exception as exc:
                print(f"[tickets] post rating prompt failed: {exc}")
        else:
            await asyncio.sleep(5)
            try:
                await channel.delete(reason="Ticket closed")
            except Exception as exc:
                print(f"[tickets] delete channel failed: {exc}")

    async def _delete_channel(self, interaction):
        settings = await self._get_settings(interaction.guild.id)
        if not await self._is_staff(interaction, settings or {}):
            await interaction.response.send_message("Only staff can delete this channel.", ephemeral=True)
            return
        await interaction.response.send_message("Deleting channel…", ephemeral=True)
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
        await interaction.response.send_modal(RatingModal(self, gid, ticket_id, rating, in_channel))

    async def save_rating(self, interaction, gid, ticket_id, rating, comment, in_channel):
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{gid}/tickets/rating",
                      {"ticket_id": ticket_id, "rating": rating, "comment": comment})
        await interaction.response.send_message(f"Thanks for your rating: {'⭐' * rating}", ephemeral=True)

        # Post the rating into the configured log channel.
        settings = await self._get_settings(gid)
        guild = self.bot.get_guild(int(gid)) if str(gid).isdigit() else None
        if guild:
            embed = discord.Embed(
                title="⭐ Ticket rated",
                description=f"{'⭐' * rating} ({rating}/5) by {interaction.user.mention}",
                color=0xFEE75C,
            )
            if comment.strip():
                embed.add_field(name="Comment", value=comment.strip()[:1024], inline=False)
            await self._log_event(guild, settings, embed)

        if in_channel and interaction.channel:
            try:
                await interaction.channel.send("✅ Rating received — closing this channel shortly. Thank you!")
                await asyncio.sleep(4)
                await interaction.channel.delete(reason="Ticket rated & closed")
            except Exception as exc:
                print(f"[tickets] post-rating delete failed: {exc}")

    async def _send_dm_rating(self, guild, opener_id, ticket_id):
        try:
            member = guild.get_member(int(opener_id)) or await guild.fetch_member(int(opener_id))
            if member is None:
                return
            await member.send(
                content=f"Your ticket in **{guild.name}** was closed. How was our support?",
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
        try:
            lines = []
            async for m in channel.history(limit=1000, oldest_first=True):
                ts = m.created_at.strftime("%Y-%m-%d %H:%M")
                content = m.content or ""
                for att in m.attachments:
                    content += f" [attachment: {att.url}]"
                if not content and m.embeds:
                    content = "[embed]"
                lines.append(f"[{ts}] {m.author}: {content}")
            text = "\n".join(lines) or "(no messages)"
            buf = io.BytesIO(text.encode("utf-8"))
            file = discord.File(buf, filename=f"transcript-{channel.name}.txt")
            embed = discord.Embed(
                title="🎫 Ticket transcript",
                description=f"Channel: #{channel.name}\nClosed by: {closer.mention}\nMessages: {len(lines)}",
                color=TICKET_COLOR,
                timestamp=discord.utils.utcnow(),
            )
            await target.send(embed=embed, file=file)
        except discord.Forbidden:
            print(f"[tickets] missing permission to post transcript in {channel.guild.id}")
        except Exception as exc:
            print(f"[tickets] transcript failed in {channel.guild.id}: {exc}")

    # ----- Prefix commands (parallel to the buttons) -----

    @commands.command(name="claim")
    @commands.guild_only()
    async def claim_cmd(self, ctx):
        settings = await self._get_settings(ctx.guild.id)
        ticket = await self._ticket_for(ctx.guild.id, ctx.channel.id)
        if not ticket:
            return
        if not (ctx.author.guild_permissions.manage_channels or self._has_support_role(ctx.author, settings)):
            await ctx.reply("Only staff can claim tickets.", mention_author=False)
            return
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/claim",
                      {"channel_id": str(ctx.channel.id), "user_id": str(ctx.author.id)})
        await ctx.send(embed=discord.Embed(description=f"🙋 Ticket claimed by {ctx.author.mention}.", color=0x57F287))

    @commands.command(name="ticketadd")
    @commands.guild_only()
    async def ticketadd_cmd(self, ctx, member: discord.Member):
        if not await self._cmd_in_ticket(ctx):
            return
        try:
            await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, attach_files=True, reason="Ticket add user")
            await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/users", {"channel_id": str(ctx.channel.id), "add": [str(member.id)]})
            await ctx.send(embed=discord.Embed(description=f"➕ {member.mention} added to the ticket.", color=TICKET_COLOR))
        except discord.Forbidden:
            await ctx.reply("I couldn't change channel permissions.", mention_author=False)

    @commands.command(name="ticketremove")
    @commands.guild_only()
    async def ticketremove_cmd(self, ctx, member: discord.Member):
        if not await self._cmd_in_ticket(ctx):
            return
        try:
            await ctx.channel.set_permissions(member, overwrite=None, reason="Ticket remove user")
            await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/tickets/users", {"channel_id": str(ctx.channel.id), "remove": [str(member.id)]})
            await ctx.send(embed=discord.Embed(description=f"➖ {member.mention} removed from the ticket.", color=TICKET_COLOR))
        except discord.Forbidden:
            await ctx.reply("I couldn't change channel permissions.", mention_author=False)

    @commands.command(name="ticketclose")
    @commands.guild_only()
    async def ticketclose_cmd(self, ctx):
        settings = await self._get_settings(ctx.guild.id)
        ticket = await self._ticket_for(ctx.guild.id, ctx.channel.id)
        if not ticket:
            return
        is_owner = str(ticket.get("user_id")) == str(ctx.author.id)
        if not (ctx.author.guild_permissions.manage_channels or self._has_support_role(ctx.author, settings) or is_owner):
            await ctx.reply("Only staff or the ticket owner can close this.", mention_author=False)
            return
        await ctx.send("🔒 Closing this ticket in 5 seconds…")
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
            await ctx.reply("Only staff can manage ticket members.", mention_author=False)
            return False
        return True


async def setup(bot):
    await bot.add_cog(Tickets(bot))
