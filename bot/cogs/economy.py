"""Economy cog (Premium: Pro).

A per-server currency: balance, daily, work, pay, leaderboard, shop and buy.
All balances and cooldowns live in the backend, which performs every mutation
inside a transaction.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/economy        → { enabled, currency_name, currency_symbol, ... }
  POST /api/bot/guilds/{gid}/economy/balance         body { user_id }
  POST /api/bot/guilds/{gid}/economy/daily           body { user_id }
  POST /api/bot/guilds/{gid}/economy/work            body { user_id }
  POST /api/bot/guilds/{gid}/economy/pay             body { user_id, target_id, amount }
  GET  /api/bot/guilds/{gid}/economy/leaderboard
  GET  /api/bot/guilds/{gid}/economy/shop            → { items }
  POST /api/bot/guilds/{gid}/economy/buy             body { user_id, item_id }

Logging prefix: "[economy]".
"""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post
from utils import general_config
from utils.bot_i18n import t, lang_for


ECONOMY_COLOR = 0xFACC15


def fmt_amount(amount, result):
    symbol = (result or {}).get("currency_symbol") or "🪙"
    name = (result or {}).get("currency_name") or "coins"
    return f"{symbol} **{amount}** {name}"


def fmt_duration(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY

    async def _enabled(self, guild_id):
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "economy")
        return bool(settings and settings.get("enabled")), settings

    @commands.command(name="balance", aliases=["bal"])
    @commands.guild_only()
    async def balance(self, ctx, member: discord.Member = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        target = member or ctx.author
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/balance", {"user_id": str(target.id)})
        if not result:
            await ctx.reply(t(lang, "eco.balanceFailed"), mention_author=False)
            return
        await ctx.reply(t(lang, "eco.balance", name=target.display_name, amount=fmt_amount(result.get("balance", 0), result)), mention_author=False)

    @app_commands.command(name="balance", description="Show your balance or another member's.")
    @app_commands.guild_only()
    @app_commands.describe(member="The member to check (defaults to you).")
    async def balance_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        target = member or interaction.user
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/balance", {"user_id": str(target.id)})
        if not result:
            await interaction.response.send_message(t(lang, "eco.balanceFailed"), ephemeral=True)
            return
        await interaction.response.send_message(
            t(lang, "eco.balance", name=target.display_name, amount=fmt_amount(result.get("balance", 0), result))
        )

    @commands.command(name="daily")
    @commands.guild_only()
    async def daily(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/daily", {"user_id": str(ctx.author.id)})
        if not result:
            await ctx.reply(t(lang, "eco.dailyFailed"), mention_author=False)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await ctx.reply(t(lang, "eco.dailyCooldown", time=fmt_duration(result.get("remaining"))), mention_author=False)
            return
        await ctx.reply(t(lang, "eco.dailyClaimed", amount=fmt_amount(result.get("amount", 0), result), balance=fmt_amount(result.get("balance", 0), result)), mention_author=False)

    @commands.command(name="work")
    @commands.guild_only()
    async def work(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/work", {"user_id": str(ctx.author.id)})
        if not result:
            await ctx.reply(t(lang, "eco.workFailed"), mention_author=False)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await ctx.reply(t(lang, "eco.workCooldown", time=fmt_duration(result.get("remaining"))), mention_author=False)
            return
        await ctx.reply(t(lang, "eco.worked", amount=fmt_amount(result.get("amount", 0), result), balance=fmt_amount(result.get("balance", 0), result)), mention_author=False)

    @commands.command(name="pay")
    @commands.guild_only()
    async def pay(self, ctx, member: discord.Member = None, amount: int = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if member is None or amount is None:
            await ctx.reply(t(lang, "eco.payUsage"), mention_author=False)
            return
        if amount <= 0:
            await ctx.reply(t(lang, "eco.payPositive"), mention_author=False)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/pay",
                                {"user_id": str(ctx.author.id), "target_id": str(member.id), "amount": amount})
        if not result:
            await ctx.reply(t(lang, "eco.transferFailed"), mention_author=False)
            return
        if not result.get("ok"):
            reason = result.get("reason")
            messages = {
                "insufficient": t(lang, "eco.payInsufficient"),
                "self": t(lang, "eco.paySelf"),
                "bad_amount": t(lang, "eco.payBadAmount"),
            }
            await ctx.reply(messages.get(reason, t(lang, "eco.transferFailed")), mention_author=False)
            return
        await ctx.reply(t(lang, "eco.paid", amount=fmt_amount(amount, result), target=member.mention, balance=fmt_amount(result.get("balance", 0), result)), mention_author=False)

    @commands.command(name="rich", aliases=["leaderboard", "baltop"])
    @commands.guild_only()
    async def rich(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/leaderboard?limit=10")
        entries = (data or {}).get("leaderboard") or []
        if not entries:
            await ctx.reply(t(lang, "eco.nobody"), mention_author=False)
            return
        lines = []
        for e in entries:
            member = ctx.guild.get_member(int(e["user_id"]))
            name = member.display_name if member else f"User {e['user_id']}"
            lines.append(f"**{e['rank']}.** {name} — {e['balance']}")
        color = await general_config.get_embed_color(self.backend_url, self.api_key, ctx.guild.id, fallback=ECONOMY_COLOR)
        embed = discord.Embed(title=t(lang, "eco.richTitle"), description="\n".join(lines), color=color)
        await ctx.send(embed=embed)

    @commands.command(name="shop")
    @commands.guild_only()
    async def shop(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/shop")
        items = (data or {}).get("items") or []
        if not items:
            await ctx.reply(t(lang, "eco.shopEmpty"), mention_author=False)
            return
        color = await general_config.get_embed_color(self.backend_url, self.api_key, ctx.guild.id, fallback=ECONOMY_COLOR)
        embed = discord.Embed(title=t(lang, "eco.shopTitle"), description=t(lang, "eco.shopHint"), color=color)
        for it in items[:25]:
            desc = (it.get("description") or "").strip()
            value = t(lang, "eco.shopPrice", price=it.get("price", 0))
            if desc:
                value = f"{desc}\n{value}"
            value += f"\n`!buy {it['id']}`"
            embed.add_field(name=it.get("name") or t(lang, "eco.itemFallback"), value=value, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    @commands.guild_only()
    async def buy(self, ctx, item_id: str = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if not item_id:
            await ctx.reply(t(lang, "eco.buyUsage"), mention_author=False)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/buy",
                                {"user_id": str(ctx.author.id), "item_id": item_id})
        if not result:
            await ctx.reply(t(lang, "eco.buyFailed"), mention_author=False)
            return
        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "insufficient":
                await ctx.reply(t(lang, "eco.buyInsufficient", price=result.get("price"), balance=result.get("balance")), mention_author=False)
            elif reason == "not_found":
                await ctx.reply(t(lang, "eco.buyNotFound"), mention_author=False)
            else:
                await ctx.reply(t(lang, "eco.buyFailed"), mention_author=False)
            return
        item = result.get("item") or {}
        role_id = result.get("role_id")
        if role_id:
            role = ctx.guild.get_role(int(role_id))
            if role:
                try:
                    await ctx.author.add_roles(role, reason="Shop purchase")
                except Exception as exc:
                    print(f"[economy] add role failed: {exc}")
        await ctx.reply(t(lang, "eco.bought", item=item.get("name"), balance=fmt_amount(result.get("balance", 0), result)), mention_author=False)

    # --- Slash variants (mirror the prefix commands; shown in the bot profile) ---

    @app_commands.command(name="daily", description="Claim your daily reward.")
    @app_commands.guild_only()
    async def daily_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/daily", {"user_id": str(interaction.user.id)})
        if not result:
            await interaction.response.send_message(t(lang, "eco.dailyFailed"), ephemeral=True)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await interaction.response.send_message(t(lang, "eco.dailyCooldown", time=fmt_duration(result.get("remaining"))), ephemeral=True)
            else:
                await interaction.response.send_message(t(lang, "eco.dailyFailed"), ephemeral=True)
            return
        await interaction.response.send_message(t(lang, "eco.dailyClaimed", amount=fmt_amount(result.get("amount", 0), result), balance=fmt_amount(result.get("balance", 0), result)))

    @app_commands.command(name="work", description="Work for some currency.")
    @app_commands.guild_only()
    async def work_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/work", {"user_id": str(interaction.user.id)})
        if not result:
            await interaction.response.send_message(t(lang, "eco.workFailed"), ephemeral=True)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await interaction.response.send_message(t(lang, "eco.workCooldown", time=fmt_duration(result.get("remaining"))), ephemeral=True)
            else:
                await interaction.response.send_message(t(lang, "eco.workFailed"), ephemeral=True)
            return
        await interaction.response.send_message(t(lang, "eco.worked", amount=fmt_amount(result.get("amount", 0), result), balance=fmt_amount(result.get("balance", 0), result)))

    @app_commands.command(name="pay", description="Transfer currency to another member.")
    @app_commands.guild_only()
    @app_commands.describe(member="Who to pay", amount="How much to transfer")
    async def pay_slash(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message(t(lang, "eco.payPositive"), ephemeral=True)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/pay",
                                {"user_id": str(interaction.user.id), "target_id": str(member.id), "amount": amount})
        if not result:
            await interaction.response.send_message(t(lang, "eco.transferFailed"), ephemeral=True)
            return
        if not result.get("ok"):
            reason = result.get("reason")
            messages = {
                "insufficient": t(lang, "eco.payInsufficient"),
                "self": t(lang, "eco.paySelf"),
                "bad_amount": t(lang, "eco.payBadAmount"),
            }
            await interaction.response.send_message(messages.get(reason, t(lang, "eco.transferFailed")), ephemeral=True)
            return
        await interaction.response.send_message(t(lang, "eco.paid", amount=fmt_amount(amount, result), target=member.mention, balance=fmt_amount(result.get("balance", 0), result)))

    @app_commands.command(name="rich", description="Show the balance leaderboard.")
    @app_commands.guild_only()
    async def rich_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/leaderboard?limit=10")
        entries = (data or {}).get("leaderboard") or []
        if not entries:
            await interaction.response.send_message(t(lang, "eco.nobody"), ephemeral=True)
            return
        lines = []
        for e in entries:
            member = interaction.guild.get_member(int(e["user_id"]))
            name = member.display_name if member else f"User {e['user_id']}"
            lines.append(f"**{e['rank']}.** {name} — {e['balance']}")
        color = await general_config.get_embed_color(self.backend_url, self.api_key, interaction.guild.id, fallback=ECONOMY_COLOR)
        embed = discord.Embed(title=t(lang, "eco.richTitle"), description="\n".join(lines), color=color)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="List the shop items you can buy.")
    @app_commands.guild_only()
    async def shop_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/shop")
        items = (data or {}).get("items") or []
        if not items:
            await interaction.response.send_message(t(lang, "eco.shopEmpty"), ephemeral=True)
            return
        color = await general_config.get_embed_color(self.backend_url, self.api_key, interaction.guild.id, fallback=ECONOMY_COLOR)
        embed = discord.Embed(title=t(lang, "eco.shopTitle"), description=t(lang, "eco.shopHint"), color=color)
        for it in items[:25]:
            desc = (it.get("description") or "").strip()
            value = t(lang, "eco.shopPrice", price=it.get("price", 0))
            if desc:
                value = f"{desc}\n{value}"
            value += f"\n`/buy {it['id']}`"
            embed.add_field(name=it.get("name") or t(lang, "eco.itemFallback"), value=value, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy a shop item by its ID.")
    @app_commands.guild_only()
    @app_commands.describe(item="The shop item ID (see /shop)")
    async def buy_slash(self, interaction: discord.Interaction, item: str):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/buy",
                                {"user_id": str(interaction.user.id), "item_id": item})
        if not result:
            await interaction.response.send_message(t(lang, "eco.buyFailed"), ephemeral=True)
            return
        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "insufficient":
                await interaction.response.send_message(t(lang, "eco.buyInsufficient", price=result.get("price"), balance=result.get("balance")), ephemeral=True)
            elif reason == "not_found":
                await interaction.response.send_message(t(lang, "eco.buyNotFound"), ephemeral=True)
            else:
                await interaction.response.send_message(t(lang, "eco.buyFailed"), ephemeral=True)
            return
        item_obj = result.get("item") or {}
        role_id = result.get("role_id")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role:
                try:
                    await interaction.user.add_roles(role, reason="Shop purchase")
                except Exception as exc:
                    print(f"[economy] add role failed: {exc}")
        await interaction.response.send_message(t(lang, "eco.bought", item=item_obj.get("name"), balance=fmt_amount(result.get("balance", 0), result)))


async def setup(bot):
    await bot.add_cog(Economy(bot))
