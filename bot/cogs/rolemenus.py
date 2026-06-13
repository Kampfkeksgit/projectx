"""Role Menus cog (buttons / select).

Self-assignable roles via buttons or a dropdown. Menus are configured in the
dashboard; this cog posts any unposted menu to its channel and handles clicks via
on_interaction (custom_id "rr:<role_id>" for buttons, "rrselect" for the select),
so they keep working across restarts without persistent-view registration.

Backend contract (X-Bot-Token auth):
  GET /api/bot/rolemenus/pending → { menus: [{ id, guild_id, channel_id, name,
                                       menu_type, use_embed, embed,
                                       options: [{ role_id, label, emoji }] }] }
  PUT /api/bot/guilds/{gid}/rolemenus/{id}/message  body { channel_id, message_id }

Logging prefix: "[rolemenus]".
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put


POLL_SECONDS = 60
MENU_COLOR = 0xA78BFA


def _parse_color(value, fallback=MENU_COLOR):
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return int(value[1:], 16)
        except ValueError:
            return fallback
    return fallback


def _resolve(text, guild):
    if not text:
        return ""
    return str(text).replace("{guild}", guild.name if guild else "")


def build_custom_embed(cfg, guild):
    """Build a discord.Embed from the dashboard embed config (use_embed mode)."""
    cfg = cfg or {}
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
    return embed


def parse_emoji(value):
    if not value:
        return None
    try:
        if value.startswith("<") and ":" in value:
            return discord.PartialEmoji.from_str(value)
        return value
    except Exception:
        return None


def build_menu_view(menu):
    options = menu.get("options") or []
    view = discord.ui.View(timeout=None)
    if menu.get("menu_type") == "select":
        select_options = []
        for o in options[:25]:
            select_options.append(discord.SelectOption(
                label=(o.get("label") or "Role")[:100],
                value=str(o.get("role_id")),
                emoji=parse_emoji(o.get("emoji")),
            ))
        if select_options:
            exclusive = bool(menu.get("exclusive"))
            view.add_item(discord.ui.Select(
                custom_id="rrselect",
                placeholder="Pick a role…" if exclusive else "Pick your roles…",
                min_values=0,
                max_values=1 if exclusive else len(select_options),
                options=select_options,
            ))
    else:
        for o in options[:25]:
            view.add_item(discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=(o.get("label") or "Role")[:80],
                custom_id=f"rr:{o.get('role_id')}",
                emoji=parse_emoji(o.get("emoji")),
            ))
    return view


class RoleMenus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.post_loop.start()

    def cog_unload(self):
        self.post_loop.cancel()

    @tasks.loop(seconds=POLL_SECONDS)
    async def post_loop(self):
        await self._post_pending()

    @post_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _post_pending(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/rolemenus/pending")
        if not data:
            return
        for menu in (data.get("menus") or []):
            try:
                await self._post_menu(menu)
            except Exception as exc:
                print(f"[rolemenus] post error for {menu.get('id')}: {exc}")

    async def _post_menu(self, menu):
        guild = self.bot.get_guild(int(menu["guild_id"]))
        if guild is None:
            return
        channel = guild.get_channel(int(menu["channel_id"])) if menu.get("channel_id") else None
        if channel is None or not (menu.get("options") or []):
            return

        if menu.get("use_embed"):
            embed = build_custom_embed(menu.get("embed"), guild)
            # Empty custom embed → still show something meaningful.
            if not (embed.title or embed.description or embed.fields or embed.author.name):
                embed.title = menu.get("name") or "Role Menu"
                embed.description = "Pick a role below."
        else:
            lines = []
            for o in menu["options"]:
                emoji = o.get("emoji") or ""
                lines.append(f"{emoji} {o.get('label') or ''}".strip())
            embed = discord.Embed(
                title=menu.get("name") or "Role Menu",
                description="\n".join(lines) or "Pick a role below.",
                color=MENU_COLOR,
            )
        try:
            msg = await channel.send(embed=embed, view=build_menu_view(menu))
        except discord.Forbidden:
            print(f"[rolemenus] missing permission to post in {channel.id}")
            return

        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild.id}/rolemenus/{menu['id']}/message",
            {"channel_id": str(channel.id), "message_id": str(msg.id)},
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""

        # Rollen-Ops (ggf. mehrere add/remove + ein Backend-Lookup) dauern leicht
        # >3s — sofort deferren, sonst läuft der Interaction-Token ab (10062).
        if custom_id.startswith("rr:"):
            await interaction.response.defer(ephemeral=True)
            await self._toggle(interaction, [custom_id[3:]])
        elif custom_id == "rrselect":
            await interaction.response.defer(ephemeral=True)
            values = (interaction.data or {}).get("values") or []
            await self._handle_select(interaction, values)

    async def _handle_select(self, interaction, values):
        # Exclusive menus: the selection IS the member's role set among the
        # menu's roles (picking one removes the others). Look up the menu by the
        # message the select lives on.
        menu = None
        msg = interaction.message
        if msg is not None:
            data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/rolemenus/by-message/{msg.id}")
            menu = (data or {}).get("menu")

        if not (menu and menu.get("exclusive")):
            await self._toggle(interaction, values)
            return

        member = interaction.guild.get_member(interaction.user.id) or interaction.user
        selected = set(str(v) for v in values)
        added, removed, failed = [], [], False
        for opt in (menu.get("options") or []):
            rid = str(opt.get("role_id"))
            role = interaction.guild.get_role(int(rid)) if rid.isdigit() else None
            if role is None:
                continue
            try:
                if rid in selected and role not in member.roles:
                    await member.add_roles(role, reason="Role menu (exclusive)")
                    added.append(role.name)
                elif rid not in selected and role in member.roles:
                    await member.remove_roles(role, reason="Role menu (exclusive)")
                    removed.append(role.name)
            except discord.Forbidden:
                failed = True
            except Exception as exc:
                print(f"[rolemenus] exclusive toggle failed in {interaction.guild.id}: {exc}")
                failed = True

        parts = []
        if added:
            parts.append("➕ " + ", ".join(added))
        if removed:
            parts.append("➖ " + ", ".join(removed))
        if failed and not parts:
            msg_text = "I couldn't change your roles (missing permission / role too high)."
        elif not parts:
            msg_text = "No changes."
        else:
            msg_text = " · ".join(parts)
        await interaction.followup.send(msg_text, ephemeral=True)

    async def _toggle(self, interaction, role_ids):
        member = interaction.user
        added, removed, failed = [], [], False
        for rid in role_ids:
            if not rid or not rid.isdigit():
                continue
            role = interaction.guild.get_role(int(rid))
            if role is None:
                continue
            try:
                if role in member.roles:
                    await member.remove_roles(role, reason="Role menu")
                    removed.append(role.name)
                else:
                    await member.add_roles(role, reason="Role menu")
                    added.append(role.name)
            except discord.Forbidden:
                failed = True
            except Exception as exc:
                print(f"[rolemenus] toggle failed in {interaction.guild.id}: {exc}")
                failed = True

        parts = []
        if added:
            parts.append("➕ " + ", ".join(added))
        if removed:
            parts.append("➖ " + ", ".join(removed))
        if failed and not parts:
            msg = "I couldn't change your roles (missing permission / role too high)."
        elif not parts:
            msg = "No changes."
        else:
            msg = " · ".join(parts)
        await interaction.followup.send(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(RoleMenus(bot))
