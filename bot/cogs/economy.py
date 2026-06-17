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
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post


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
        target = member or ctx.author
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/balance", {"user_id": str(target.id)})
        if not result:
            await ctx.reply("Couldn't fetch the balance right now.", mention_author=False)
            return
        await ctx.reply(f"💰 {target.display_name} has {fmt_amount(result.get('balance', 0), result)}.", mention_author=False)

    @commands.command(name="daily")
    @commands.guild_only()
    async def daily(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/daily", {"user_id": str(ctx.author.id)})
        if not result:
            await ctx.reply("Couldn't claim your daily right now.", mention_author=False)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await ctx.reply(f"⏳ You already claimed your daily. Come back in **{fmt_duration(result.get('remaining'))}**.", mention_author=False)
            return
        await ctx.reply(f"🎁 You claimed {fmt_amount(result.get('amount', 0), result)}! New balance: {fmt_amount(result.get('balance', 0), result)}.", mention_author=False)

    @commands.command(name="work")
    @commands.guild_only()
    async def work(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/work", {"user_id": str(ctx.author.id)})
        if not result:
            await ctx.reply("Couldn't work right now.", mention_author=False)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await ctx.reply(f"⏳ You're tired. You can work again in **{fmt_duration(result.get('remaining'))}**.", mention_author=False)
            return
        await ctx.reply(f"🛠️ You worked and earned {fmt_amount(result.get('amount', 0), result)}! Balance: {fmt_amount(result.get('balance', 0), result)}.", mention_author=False)

    @commands.command(name="pay")
    @commands.guild_only()
    async def pay(self, ctx, member: discord.Member = None, amount: int = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        if member is None or amount is None:
            await ctx.reply("Usage: `!pay @user <amount>`", mention_author=False)
            return
        if amount <= 0:
            await ctx.reply("Amount must be positive.", mention_author=False)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/pay",
                                {"user_id": str(ctx.author.id), "target_id": str(member.id), "amount": amount})
        if not result:
            await ctx.reply("Couldn't complete the transfer.", mention_author=False)
            return
        if not result.get("ok"):
            reason = result.get("reason")
            messages = {
                "insufficient": "You don't have enough balance.",
                "self": "You can't pay yourself.",
                "bad_amount": "Invalid amount.",
            }
            await ctx.reply(messages.get(reason, "Couldn't complete the transfer."), mention_author=False)
            return
        await ctx.reply(f"✅ You sent {fmt_amount(amount, result)} to {member.mention}. Your balance: {fmt_amount(result.get('balance', 0), result)}.", mention_author=False)

    @commands.command(name="rich", aliases=["leaderboard", "baltop"])
    @commands.guild_only()
    async def rich(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/leaderboard?limit=10")
        entries = (data or {}).get("leaderboard") or []
        if not entries:
            await ctx.reply("Nobody has any balance yet.", mention_author=False)
            return
        lines = []
        for e in entries:
            member = ctx.guild.get_member(int(e["user_id"]))
            name = member.display_name if member else f"User {e['user_id']}"
            lines.append(f"**{e['rank']}.** {name} — {e['balance']}")
        embed = discord.Embed(title="💰 Richest members", description="\n".join(lines), color=ECONOMY_COLOR)
        await ctx.send(embed=embed)

    @commands.command(name="shop")
    @commands.guild_only()
    async def shop(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        data = await bot_get(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/shop")
        items = (data or {}).get("items") or []
        if not items:
            await ctx.reply("The shop is empty.", mention_author=False)
            return
        embed = discord.Embed(title="🛒 Shop", description="Buy with `!buy <id>`", color=ECONOMY_COLOR)
        for it in items[:25]:
            desc = (it.get("description") or "").strip()
            value = f"Price: **{it.get('price', 0)}**"
            if desc:
                value = f"{desc}\n{value}"
            value += f"\n`!buy {it['id']}`"
            embed.add_field(name=it.get("name") or "Item", value=value, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    @commands.guild_only()
    async def buy(self, ctx, item_id: str = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        if not item_id:
            await ctx.reply("Usage: `!buy <item_id>` (find the id with `!shop`)", mention_author=False)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/buy",
                                {"user_id": str(ctx.author.id), "item_id": item_id})
        if not result:
            await ctx.reply("Couldn't complete the purchase.", mention_author=False)
            return
        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "insufficient":
                await ctx.reply(f"You need **{result.get('price')}** but only have **{result.get('balance')}**.", mention_author=False)
            elif reason == "not_found":
                await ctx.reply("That item doesn't exist.", mention_author=False)
            else:
                await ctx.reply("Couldn't complete the purchase.", mention_author=False)
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
        await ctx.reply(f"✅ You bought **{item.get('name')}**! Balance: {fmt_amount(result.get('balance', 0), result)}.", mention_author=False)


async def setup(bot):
    await bot.add_cog(Economy(bot))
