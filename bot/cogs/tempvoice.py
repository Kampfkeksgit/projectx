"""Temp-Voice (Join-to-Create) cog.

When a member joins the configured "hub" voice channel, the bot creates a fresh
temporary voice channel (in the configured category), moves the member into it,
and deletes the channel automatically once it becomes empty.

If the control panel is enabled, an interactive panel (lock/unlock, hide/show,
user limit, rename, invite/permit user, kick user, claim) is posted when the
channel is created. The destination is configurable:
  - voice   → the temp channel's own text chat
  - dm      → a DM to the owner (and to the new owner after an ownership transfer)
  - channel → a fixed text channel

Only the channel owner can use the panel (Claim is the exception: anyone in the
channel can claim it once the owner has left).

Backend contract (X-Bot-Token auth):
  GET    /api/bot/guilds/{gid}/settings/tempvoice
         → { enabled, hub_channel_id, category_id, name_template, user_limit,
             panel_enabled, panel_destination, panel_channel_id }
  POST   /api/bot/guilds/{gid}/tempvoice/channels   body { channel_id, owner_id }
  DELETE /api/bot/guilds/{gid}/tempvoice/channels/{channel_id}
  GET    /api/bot/tempvoice/channels                → { channels: [...] }  (startup cleanup)

Requires permissions: Manage Channels + Move Members. Logging prefix: "[tempvoice]".
"""

import time

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post, bot_delete
from utils import general_config
from utils.bot_i18n import t, lang_for


SETTINGS_TTL_SECONDS = 300
PANEL_COLOR = 0x5865F2


# ----- Panel UI builders -----

def build_panel_view(channel_id, lang="en"):
    """Control panel buttons. Handled in on_interaction (custom_id tv:<action>:<cid>),
    so they keep working across bot restarts."""
    cid = str(channel_id)
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="🔒", label=t(lang, "tv.lock"), custom_id=f"tv:lock:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="🔓", label=t(lang, "tv.unlock"), custom_id=f"tv:unlock:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="🙈", label=t(lang, "tv.hide"), custom_id=f"tv:hide:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="👁️", label=t(lang, "tv.show"), custom_id=f"tv:show:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="🔢", label=t(lang, "tv.limit"), custom_id=f"tv:limit:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, emoji="✏️", label=t(lang, "tv.rename"), custom_id=f"tv:rename:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.success, emoji="➕", label=t(lang, "tv.invite"), custom_id=f"tv:invite:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, emoji="➖", label=t(lang, "tv.kick"), custom_id=f"tv:kick:{cid}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, emoji="👑", label=t(lang, "tv.claim"), custom_id=f"tv:claim:{cid}"))
    return view


def build_user_select_view(custom_id, placeholder):
    view = discord.ui.View(timeout=300)
    view.add_item(discord.ui.UserSelect(custom_id=custom_id, placeholder=placeholder, min_values=1, max_values=10))
    return view


def build_panel_embed(channel, owner, color=PANEL_COLOR, lang="en"):
    e = discord.Embed(
        title=t(lang, "tv.panelTitle"),
        description=t(lang, "tv.panelDesc", name=channel.name),
        color=color,
    )
    if owner is not None:
        e.add_field(name=t(lang, "tv.ownerField"), value=owner.mention, inline=True)
    e.set_footer(text=t(lang, "tv.panelFooter"))
    return e


class LimitModal(discord.ui.Modal):
    def __init__(self, channel, lang="en"):
        super().__init__(title=t(lang, "tv.limitTitle"))
        self.channel = channel
        self.lang = lang
        self.value = discord.ui.TextInput(
            label=t(lang, "tv.limitLabel"),
            placeholder=t(lang, "tv.limitPlaceholder"),
            required=True,
            max_length=2,
        )
        self.add_item(self.value)

    async def on_submit(self, interaction):
        raw = str(self.value.value or "").strip()
        if not raw.isdigit():
            await interaction.response.send_message(t(self.lang, "tv.limitBadInput"), ephemeral=True)
            return
        limit = max(0, min(99, int(raw)))
        try:
            await self.channel.edit(user_limit=limit, reason="Temp-Voice panel")
            value = t(self.lang, "tv.unlimited") if limit == 0 else limit
            await interaction.response.send_message(t(self.lang, "tv.limitSet", value=value), ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(t(self.lang, "tv.limitFailed", error=str(exc)[:80]), ephemeral=True)


class RenameModal(discord.ui.Modal):
    def __init__(self, channel, lang="en"):
        super().__init__(title=t(lang, "tv.renameTitle"))
        self.channel = channel
        self.lang = lang
        self.value = discord.ui.TextInput(
            label=t(lang, "tv.renameLabel"),
            default=channel.name,
            required=True,
            max_length=100,
        )
        self.add_item(self.value)

    async def on_submit(self, interaction):
        name = str(self.value.value or "").strip()[:100]
        if not name:
            await interaction.response.send_message(t(self.lang, "tv.renameEmpty"), ephemeral=True)
            return
        try:
            await self.channel.edit(name=name, reason="Temp-Voice panel")
            await interaction.response.send_message(t(self.lang, "tv.renamed", name=name), ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(t(self.lang, "tv.renameFailed", error=str(exc)[:80]), ephemeral=True)


class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # guild_id (str) -> (settings dict, fetched_at)
        self._settings_cache = {}
        # channel ids (int) the bot manages and should clean up when empty.
        self._temp_channels = set()
        # channel id (int) -> owner id (int)
        self._owners = {}

    async def _get_settings(self, guild_id):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "tempvoice")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    @commands.Cog.listener()
    async def on_ready(self):
        # Load tracked channels and prune any that are gone or already empty.
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/tempvoice/channels")
        if not data:
            return
        for row in (data.get("channels") or []):
            try:
                cid = int(row.get("channel_id"))
            except (TypeError, ValueError):
                continue
            channel = self.bot.get_channel(cid)
            if channel is None:
                await self._untrack(row.get("guild_id"), cid)
            elif len(channel.members) == 0:
                await self._delete_channel(channel)
            else:
                self._temp_channels.add(cid)
                if row.get("owner_id"):
                    try:
                        self._owners[cid] = int(row.get("owner_id"))
                    except (TypeError, ValueError):
                        pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild

        # Joined (or moved into) a channel → maybe spawn a temp channel.
        if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
            settings = await self._get_settings(guild.id)
            if settings and settings.get("enabled") and after.channel.id not in self._temp_channels:
                hub_id = settings.get("hub_channel_id")
                if hub_id and str(after.channel.id) == str(hub_id):
                    await self._spawn(member, settings)

        # Left a channel → delete if now-empty, else transfer ownership if the owner left.
        if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
            if before.channel.id in self._temp_channels:
                if len(before.channel.members) == 0:
                    await self._delete_channel(before.channel)
                elif self._owners.get(before.channel.id) == member.id:
                    await self._transfer_owner(before.channel)

    async def _spawn(self, member, settings):
        guild = member.guild
        name = (settings.get("name_template") or "🔊 {user}").replace("{user}", member.display_name)[:100]

        category = None
        cat_id = settings.get("category_id")
        if cat_id:
            ch = guild.get_channel(int(cat_id))
            if isinstance(ch, discord.CategoryChannel):
                category = ch
        # Fall back to the hub's own category if none configured.
        if category is None and member.voice and member.voice.channel:
            category = member.voice.channel.category

        user_limit = settings.get("user_limit") or 0

        try:
            channel = await guild.create_voice_channel(
                name,
                category=category,
                user_limit=user_limit if user_limit else None,
                reason="Temp-Voice: join-to-create",
            )
        except discord.Forbidden:
            print(f"[tempvoice] missing Manage Channels permission in {guild.id}")
            return
        except Exception as exc:
            print(f"[tempvoice] create channel failed in {guild.id}: {exc}")
            return

        self._temp_channels.add(channel.id)
        self._owners[channel.id] = member.id
        await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild.id}/tempvoice/channels",
            {"channel_id": str(channel.id), "owner_id": str(member.id)},
        )

        try:
            await member.move_to(channel, reason="Temp-Voice")
        except discord.Forbidden:
            print(f"[tempvoice] missing Move Members permission in {guild.id}")
        except Exception as exc:
            print(f"[tempvoice] move member failed in {guild.id}: {exc}")

        if settings.get("panel_enabled"):
            await self._send_panel(channel, member, settings)

    async def _send_panel(self, channel, owner, settings):
        dest = settings.get("panel_destination") or "voice"
        color = await general_config.get_embed_color(self.backend_url, self.api_key, channel.guild.id, fallback=PANEL_COLOR)
        lang = await lang_for(self.backend_url, self.api_key, channel.guild.id)
        embed = build_panel_embed(channel, owner, color=color, lang=lang)
        view = build_panel_view(channel.id, lang=lang)
        try:
            if dest == "dm":
                await owner.send(embed=embed, view=view)
            elif dest == "channel":
                target = None
                cid = settings.get("panel_channel_id")
                if cid:
                    target = channel.guild.get_channel(int(cid))
                if target is not None:
                    await target.send(content=owner.mention, embed=embed, view=view)
                else:
                    await channel.send(embed=embed, view=view)  # fallback to voice chat
            else:  # voice text chat
                await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            print(f"[tempvoice] missing permission to post control panel in {channel.guild.id}")
        except Exception as exc:
            print(f"[tempvoice] send panel failed in {channel.guild.id}: {exc}")

    async def _transfer_owner(self, channel):
        """Owner left but members remain → hand ownership to the first member."""
        members = [m for m in channel.members if not m.bot]
        if not members:
            return
        new_owner = members[0]
        self._owners[channel.id] = new_owner.id
        await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{channel.guild.id}/tempvoice/channels",
            {"channel_id": str(channel.id), "owner_id": str(new_owner.id)},
        )
        settings = await self._get_settings(channel.guild.id) or {}
        if settings.get("panel_enabled"):
            try:
                # The voice/channel panels keep working (owner is re-checked live);
                # for DM mode the new owner needs their own copy.
                if (settings.get("panel_destination") or "voice") == "dm":
                    await self._send_panel(channel, new_owner, settings)
                else:
                    notice_color = await general_config.get_embed_color(self.backend_url, self.api_key, channel.guild.id, fallback=PANEL_COLOR)
                    notice_lang = await lang_for(self.backend_url, self.api_key, channel.guild.id)
                    await channel.send(
                        content=new_owner.mention,
                        embed=discord.Embed(description=t(notice_lang, "tv.newOwner", user=new_owner.mention), color=notice_color),
                    )
            except Exception as exc:
                print(f"[tempvoice] owner-transfer notice failed: {exc}")

    # ----- Panel interactions -----

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("tv:"):
            return
        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        _, action, ch_id = parts
        if not ch_id.isdigit():
            return
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild_id) if interaction.guild_id else "en"
        channel = self.bot.get_channel(int(ch_id))
        if not isinstance(channel, discord.VoiceChannel):
            await self._respond(interaction, t(lang, "tv.noChannel"))
            return
        try:
            await self._handle_action(interaction, action, channel, lang)
        except Exception as exc:
            print(f"[tempvoice] panel action '{action}' failed: {exc}")
            await self._respond(interaction, t(lang, "tv.somethingWrong"))

    async def _respond(self, interaction, message):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            pass

    def _is_owner(self, interaction, channel):
        return self._owners.get(channel.id) == interaction.user.id

    async def _set_overwrite(self, channel, target, **perms):
        ow = channel.overwrites_for(target)
        for key, value in perms.items():
            setattr(ow, key, value)
        await channel.set_permissions(target, overwrite=ow, reason="Temp-Voice panel")

    async def _handle_action(self, interaction, action, channel, lang="en"):
        guild = channel.guild
        everyone = guild.default_role

        # Claim: anyone in the channel may take ownership once the current owner is gone.
        if action == "claim":
            owner_id = self._owners.get(channel.id)
            owner_present = any(m.id == owner_id for m in channel.members)
            if owner_present:
                await self._respond(interaction, t(lang, "tv.claimOwnerHere"))
                return
            if interaction.user not in channel.members:
                await self._respond(interaction, t(lang, "tv.claimMustBeIn"))
                return
            self._owners[channel.id] = interaction.user.id
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{guild.id}/tempvoice/channels",
                {"channel_id": str(channel.id), "owner_id": str(interaction.user.id)},
            )
            await self._respond(interaction, t(lang, "tv.claimed"))
            return

        # All other actions are owner-only.
        if not self._is_owner(interaction, channel):
            await self._respond(interaction, t(lang, "tv.ownerOnly"))
            return

        if action == "lock":
            await self._set_overwrite(channel, everyone, connect=False)
            await self._respond(interaction, t(lang, "tv.locked"))
        elif action == "unlock":
            await self._set_overwrite(channel, everyone, connect=None)
            await self._respond(interaction, t(lang, "tv.unlocked"))
        elif action == "hide":
            await self._set_overwrite(channel, everyone, view_channel=False)
            await self._respond(interaction, t(lang, "tv.hidden"))
        elif action == "show":
            await self._set_overwrite(channel, everyone, view_channel=None)
            await self._respond(interaction, t(lang, "tv.shown"))
        elif action == "limit":
            await interaction.response.send_modal(LimitModal(channel, lang=lang))
        elif action == "rename":
            await interaction.response.send_modal(RenameModal(channel, lang=lang))
        elif action == "invite":
            await interaction.response.send_message(
                t(lang, "tv.inviteSelect"),
                view=build_user_select_view(f"tv:invitesel:{channel.id}", t(lang, "tv.inviteSelPlaceholder")),
                ephemeral=True,
            )
        elif action == "kick":
            await interaction.response.send_message(
                t(lang, "tv.kickSelect"),
                view=build_user_select_view(f"tv:kicksel:{channel.id}", t(lang, "tv.kickSelPlaceholder")),
                ephemeral=True,
            )
        elif action == "invitesel":
            await self._apply_invite(interaction, channel)
        elif action == "kicksel":
            await self._apply_kick(interaction, channel)

    async def _apply_invite(self, interaction, channel):
        await interaction.response.defer(ephemeral=True)
        guild = channel.guild
        ids = (interaction.data or {}).get("values") or []
        done = []
        for uid in ids:
            member = guild.get_member(int(uid)) if uid.isdigit() else None
            if member is None:
                continue
            try:
                await self._set_overwrite(channel, member, connect=True, view_channel=True)
                done.append(member)
            except Exception as exc:
                print(f"[tempvoice] invite failed: {exc}")
        lang = await lang_for(self.backend_url, self.api_key, guild.id)
        if done:
            names = ", ".join(m.mention for m in done)
            await interaction.followup.send(t(lang, "tv.invited", names=names), ephemeral=True)
        else:
            await interaction.followup.send(t(lang, "tv.noChanges"), ephemeral=True)

    async def _apply_kick(self, interaction, channel):
        await interaction.response.defer(ephemeral=True)
        guild = channel.guild
        ids = (interaction.data or {}).get("values") or []
        done = []
        for uid in ids:
            member = guild.get_member(int(uid)) if uid.isdigit() else None
            if member is None or member.id == interaction.user.id:
                continue
            try:
                await self._set_overwrite(channel, member, connect=False)
                if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
                    await member.move_to(None, reason="Temp-Voice: kicked from channel")
                done.append(member)
            except Exception as exc:
                print(f"[tempvoice] kick failed: {exc}")
        lang = await lang_for(self.backend_url, self.api_key, guild.id)
        if done:
            names = ", ".join(m.mention for m in done)
            await interaction.followup.send(t(lang, "tv.removed", names=names), ephemeral=True)
        else:
            await interaction.followup.send(t(lang, "tv.noChanges"), ephemeral=True)

    async def _delete_channel(self, channel):
        self._temp_channels.discard(channel.id)
        self._owners.pop(channel.id, None)
        guild_id = channel.guild.id
        try:
            await channel.delete(reason="Temp-Voice: empty")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print(f"[tempvoice] missing permission to delete channel in {guild_id}")
        except Exception as exc:
            print(f"[tempvoice] delete channel failed in {guild_id}: {exc}")
        await self._untrack(guild_id, channel.id)

    async def _untrack(self, guild_id, channel_id):
        self._temp_channels.discard(int(channel_id))
        self._owners.pop(int(channel_id), None)
        await bot_delete(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild_id}/tempvoice/channels/{channel_id}",
        )


async def setup(bot):
    await bot.add_cog(TempVoice(bot))
