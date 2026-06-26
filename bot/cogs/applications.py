"""Applications cog (Premium: Pro).

Admins post a panel with `!applypanel`; each enabled form is a button. Clicking it
opens a modal (up to 5 questions). Submissions are posted to the form's review
channel with Accept/Deny buttons; accepting grants the configured role and DMs the
applicant.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/applications        → { forms: [...] }
  GET  /api/bot/guilds/{gid}/applications/forms/{fid}     → { form }
  POST /api/bot/guilds/{gid}/applications                 body { form_id, user_id, answers } → { id }
  PUT  /api/bot/guilds/{gid}/applications/{appid}/review  body { status, reviewer_id }

Logging prefix: "[applications]".
"""

import discord
from discord.ext import commands

import config
from utils.backend import bot_get, bot_post, bot_put
from utils import general_config
from utils.bot_i18n import t, lang_for


APP_COLOR = 0x6366F1
ACCEPT_COLOR = 0x22C55E
DENY_COLOR = 0xEF4444


class ApplicationModal(discord.ui.Modal):
    def __init__(self, cog, form):
        super().__init__(title=(form.get("name") or "Application")[:45])
        self.cog = cog
        self.form = form
        self._fields = []
        for i, q in enumerate((form.get("questions") or [])[:5]):
            field = discord.ui.TextInput(
                label=str(q)[:45],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1024,
            )
            self.add_item(field)
            self._fields.append((str(q), field))

    async def on_submit(self, interaction):
        await self.cog.handle_submit(interaction, self.form, self._fields)


def build_review_view(app_id, form_id, applicant_id, lang="en"):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.success, label=t(lang, "app.accept"), emoji="✅", custom_id=f"appok:{app_id}:{form_id}:{applicant_id}"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label=t(lang, "app.deny"), emoji="✖️", custom_id=f"appno:{app_id}:{applicant_id}"))
    return view


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY

    @commands.command(name="applypanel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def applypanel(self, ctx):
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/settings/applications")
        forms = (data or {}).get("forms") or []
        if not forms:
            await ctx.reply(t(lang, "app.noForms"), mention_author=False)
            return
        embed = discord.Embed(
            title=t(lang, "app.panelTitle"),
            description=t(lang, "app.panelDesc"),
            color=await general_config.get_embed_color(self.backend_url, self.api_key, ctx.guild.id, fallback=APP_COLOR),
        )
        view = discord.ui.View(timeout=None)
        for form in forms[:5]:
            embed.add_field(name=form.get("name") or t(lang, "app.formFallback"), value=(form.get("description") or "—")[:1024], inline=False)
            view.add_item(discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label=(form.get("button_label") or form.get("name") or t(lang, "app.applyButton"))[:80],
                custom_id=f"app:{form['id']}",
            ))
        try:
            await ctx.send(embed=embed, view=view)
        except discord.Forbidden:
            await ctx.reply(t(lang, "app.cantPost"), mention_author=False)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if custom_id.startswith("app:"):
            await self._open_form(interaction, custom_id[4:])
        elif custom_id.startswith("appok:"):
            await self._review(interaction, custom_id, accepted=True)
        elif custom_id.startswith("appno:"):
            await self._review(interaction, custom_id, accepted=False)

    async def _open_form(self, interaction, form_id):
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/applications/forms/{form_id}")
        form = (data or {}).get("form")
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not form or not form.get("enabled"):
            await interaction.response.send_message(t(lang, "app.noLongerAvailable"), ephemeral=True)
            return
        if not form.get("questions"):
            await interaction.response.send_message(t(lang, "app.noQuestions"), ephemeral=True)
            return
        await interaction.response.send_modal(ApplicationModal(self, form))

    async def handle_submit(self, interaction, form, fields):
        await interaction.response.defer(ephemeral=True)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        answers = [{"q": q, "a": str(field.value)} for q, field in fields]
        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{interaction.guild.id}/applications",
            {"form_id": form["id"], "user_id": str(interaction.user.id), "answers": answers},
        )
        if not result or not result.get("id"):
            await interaction.followup.send(t(lang, "app.submitFailed"), ephemeral=True)
            return
        app_id = result["id"]

        review_channel_id = form.get("review_channel_id")
        channel = interaction.guild.get_channel(int(review_channel_id)) if review_channel_id else None
        if channel is not None:
            embed = discord.Embed(
                title=t(lang, "app.reviewTitle", form=form.get("name") or t(lang, "app.formFallback")),
                color=await general_config.get_embed_color(self.backend_url, self.api_key, interaction.guild.id, fallback=APP_COLOR),
                timestamp=interaction.created_at,
            )
            embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
            embed.add_field(name=t(lang, "app.applicant"), value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            for a in answers:
                embed.add_field(name=a["q"][:256], value=(a["a"] or "—")[:1024], inline=False)
            try:
                await channel.send(embed=embed, view=build_review_view(app_id, form["id"], interaction.user.id, lang=lang))
            except Exception as exc:
                print(f"[applications] post review failed: {exc}")
        await interaction.followup.send(t(lang, "app.submitted"), ephemeral=True)

    async def _review(self, interaction, custom_id, accepted):
        # Only staff who can manage roles may review.
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        perms = interaction.user.guild_permissions
        if not (perms.administrator or perms.manage_roles):
            await interaction.response.send_message(t(lang, "app.noPermission"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        parts = custom_id.split(":")
        app_id = parts[1]
        if accepted:
            form_id = parts[2] if len(parts) > 2 else None
            applicant_id = parts[3] if len(parts) > 3 else None
        else:
            form_id = None
            applicant_id = parts[2] if len(parts) > 2 else None

        await bot_put(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{interaction.guild.id}/applications/{app_id}/review",
            {"status": "accepted" if accepted else "denied", "reviewer_id": str(interaction.user.id)},
        )

        member = interaction.guild.get_member(int(applicant_id)) if applicant_id else None
        if accepted and form_id:
            data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/applications/forms/{form_id}")
            form = (data or {}).get("form") or {}
            role_id = form.get("accepted_role_id")
            role = interaction.guild.get_role(int(role_id)) if role_id else None
            if role and member:
                try:
                    await member.add_roles(role, reason="Application accepted")
                except Exception as exc:
                    print(f"[applications] add role failed: {exc}")

        # Notify the applicant.
        if member:
            try:
                msg = t(lang, "app.dmAccepted") if accepted else t(lang, "app.dmDeclined")
                await member.send(t(lang, "app.dmWithGuild", msg=msg, guild=interaction.guild.name))
            except Exception:
                pass

        # Update the review message.
        try:
            embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
            embed.color = ACCEPT_COLOR if accepted else DENY_COLOR
            footer = t(lang, "app.footerAccepted", user=interaction.user) if accepted else t(lang, "app.footerDenied", user=interaction.user)
            embed.set_footer(text=footer)
            await interaction.message.edit(embed=embed, view=None)
        except Exception:
            pass
        await interaction.followup.send(t(lang, "app.reviewedAccepted") if accepted else t(lang, "app.reviewedDenied"), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Applications(bot))
