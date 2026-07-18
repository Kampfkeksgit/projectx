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

import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_get, bot_post
from utils import general_config, command_config
from utils.bot_i18n import t, lang_for


ECONOMY_COLOR = 0xFACC15

# Settings cache TTL for the passive-earn listeners (avoid hammering the backend).
_SETTINGS_TTL_SECONDS = 60

# Sentinel returned by the shared helpers for a `disabled` reason:
# → prefix stays silent, slash replies ephemerally with `eco.disabled`
# (mirrors the module-not-enabled behaviour of the existing commands).
_SILENT = object()


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


def _common_error(lang, result):
    """Map a shared not-ok reason to a reply.

    Returns `_SILENT` for a `disabled` reason (silent for prefix / ephemeral
    `eco.disabled` for slash), a translated string for `command_disabled` /
    `cooldown`, or `None` when the reason is command-specific (caller handles it).
    """
    reason = (result or {}).get("reason")
    if reason == "disabled":
        return _SILENT
    if reason == "command_disabled":
        return t(lang, "eco.commandDisabled")
    if reason == "cooldown":
        return t(lang, "eco.cooldown", time=fmt_duration((result or {}).get("remaining")))
    return None


def _parse_amount_all(raw):
    """Parse an optional amount arg where `all`/empty/0 means all.

    Returns (amount:int, valid:bool). `amount <= 0` signals "all" to the backend.
    """
    if raw is None:
        return 0, True
    s = str(raw).strip().lower()
    if s in ("", "all"):
        return 0, True
    try:
        return int(s), True
    except ValueError:
        return 0, False


def _norm_side(choice):
    c = (choice or "heads").strip().lower()
    return c if c in ("heads", "tails") else "heads"


def _daily_message(lang, result):
    """Build the (multi-line) daily reply incl. optional streak + interest notes."""
    parts = [t(lang, "eco.dailyClaimed",
               amount=fmt_amount(result.get("amount", 0), result),
               balance=fmt_amount(result.get("balance", 0), result))]
    if (result.get("streak_bonus") or 0) > 0:
        parts.append(t(lang, "eco.streakBonus",
                       streak=result.get("streak"), bonus=result.get("streak_bonus")))
    if (result.get("interest") or 0) > 0:
        parts.append(t(lang, "eco.interestGained", interest=result.get("interest")))
    return "\n".join(parts)


def _balance_message(lang, name, result):
    if result.get("bank_enabled"):
        return t(lang, "eco.balanceFull", name=name,
                 wallet=fmt_amount(result.get("balance", 0), result),
                 bank=fmt_amount(result.get("bank", 0), result))
    return t(lang, "eco.balance", name=name,
             amount=fmt_amount(result.get("balance", 0), result))


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # (guild_id, user_id) -> voice session start (unix seconds)
        self._voice_since = {}
        # guild_id -> (settings_dict_or_None, fetched_at) — for the passive listeners
        self._settings_cache = {}

    async def _enabled(self, guild_id):
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "economy")
        return bool(settings and settings.get("enabled")), settings

    async def _prefix(self, guild_id):
        """Resolve the guild's command prefix (for `{p}` in usage strings)."""
        try:
            return await command_config.get_prefix(self.backend_url, self.api_key, guild_id)
        except Exception:
            return command_config.DEFAULT_PREFIX

    async def _cached_settings(self, guild_id):
        """Economy settings for a guild, cached ~60s (used by the earn listeners)."""
        now = time.time()
        cached = self._settings_cache.get(guild_id)
        if cached and now - cached[1] < _SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "economy")
        self._settings_cache[guild_id] = (settings, now)
        return settings

    # --- Shared action helpers (used by both the prefix + slash wrappers) ---
    # Each returns (text, ephemeral): text may be a string (send it), `_SILENT`
    # (disabled → silent for prefix / eco.disabled for slash), or None (nothing).

    async def _weekly(self, guild_id, author, lang):
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/weekly",
                                {"user_id": str(author.id), "role_ids": [str(r.id) for r in author.roles]})
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        return t(lang, "eco.weeklyClaimed",
                 amount=fmt_amount(result.get("amount", 0), result),
                 balance=fmt_amount(result.get("balance", 0), result)), False

    async def _beg(self, guild_id, author, lang):
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/beg",
                                {"user_id": str(author.id), "role_ids": [str(r.id) for r in author.roles]})
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        if result.get("success"):
            return t(lang, "eco.begSuccess",
                     amount=fmt_amount(result.get("amount", 0), result),
                     balance=fmt_amount(result.get("balance", 0), result)), False
        return t(lang, "eco.begFail"), False

    async def _crime(self, guild_id, author, lang):
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/crime",
                                {"user_id": str(author.id), "role_ids": [str(r.id) for r in author.roles]})
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        if result.get("success"):
            return t(lang, "eco.crimeSuccess",
                     amount=fmt_amount(result.get("amount", 0), result),
                     balance=fmt_amount(result.get("balance", 0), result)), False
        return t(lang, "eco.crimeFail",
                 fine=fmt_amount(result.get("fine", 0), result),
                 balance=fmt_amount(result.get("balance", 0), result)), False

    async def _gather(self, guild_id, author, lang, kind):
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/gather",
                                {"user_id": str(author.id), "kind": kind, "role_ids": [str(r.id) for r in author.roles]})
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        key = "eco.fishCaught" if kind == "fish" else "eco.mined"
        return t(lang, key,
                 amount=fmt_amount(result.get("amount", 0), result),
                 balance=fmt_amount(result.get("balance", 0), result)), False

    async def _rob(self, guild_id, author, target, lang):
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/rob",
                                {"user_id": str(author.id), "target_id": str(target.id)})
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "self":
                return t(lang, "eco.robSelf"), True
            if reason == "target_poor":
                return t(lang, "eco.robTargetPoor"), True
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        if result.get("success"):
            return t(lang, "eco.robSuccess", target=target.mention,
                     amount=fmt_amount(result.get("stolen", 0), result),
                     balance=fmt_amount(result.get("balance", 0), result)), False
        return t(lang, "eco.robFail",
                 fine=fmt_amount(result.get("fine", 0), result),
                 balance=fmt_amount(result.get("balance", 0), result)), False

    async def _bank(self, guild_id, author, lang, direction, amount):
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/bank",
                                {"user_id": str(author.id), "dir": direction, "amount": amount})
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "command_disabled":
                return t(lang, "eco.bankDisabled"), True
            if reason == "bank_full":
                return t(lang, "eco.bankFull"), True
            if reason == "insufficient":
                return t(lang, "eco.bankInsufficient"), True
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        key = "eco.deposited" if direction == "deposit" else "eco.withdrew"
        return t(lang, key,
                 amount=fmt_amount(result.get("amount", 0), result),
                 balance=fmt_amount(result.get("balance", 0), result),
                 bank=fmt_amount(result.get("bank", 0), result)), False

    async def _gamble(self, guild_id, author, lang, game, bet, choice=None):
        body = {"user_id": str(author.id), "game": game, "bet": bet}
        if choice is not None:
            body["choice"] = choice
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild_id}/economy/gamble", body)
        if not result:
            return t(lang, "eco.transferFailed"), True
        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "command_disabled":
                return t(lang, "eco.gambleDisabled"), True
            if reason == "bad_amount":
                return t(lang, "eco.betBadAmount"), True
            if reason == "below_min":
                return t(lang, "eco.betTooLow", min=result.get("min_bet")), True
            if reason == "above_max":
                return t(lang, "eco.betTooHigh", max=result.get("max_bet")), True
            if reason == "insufficient":
                return t(lang, "eco.betInsufficient"), True
            common = _common_error(lang, result)
            return (common if common is not None else t(lang, "eco.transferFailed")), True
        win = bool(result.get("win"))
        payout = fmt_amount(result.get("payout", 0), result)
        balance = fmt_amount(result.get("balance", 0), result)
        bet_fmt = fmt_amount(result.get("bet", bet), result)
        if game == "coinflip":
            key = "eco.coinflipWin" if win else "eco.coinflipLose"
            return t(lang, key, result=result.get("result"), payout=payout, bet=bet_fmt, balance=balance), False
        if game == "dice":
            key = "eco.diceWin" if win else "eco.diceLose"
            return t(lang, key, roll=result.get("roll"), payout=payout, bet=bet_fmt, balance=balance), False
        reels = " ".join(str(r) for r in (result.get("reels") or []))
        key = "eco.slotsWin" if win else "eco.slotsLose"
        return t(lang, key, reels=reels, payout=payout, bet=bet_fmt, balance=balance), False

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
        await ctx.reply(_balance_message(lang, target.display_name, result), mention_author=False)

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
        await interaction.response.send_message(_balance_message(lang, target.display_name, result))

    @commands.command(name="daily")
    @commands.guild_only()
    async def daily(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/daily",
                                {"user_id": str(ctx.author.id), "role_ids": [str(r.id) for r in ctx.author.roles]})
        if not result:
            await ctx.reply(t(lang, "eco.dailyFailed"), mention_author=False)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await ctx.reply(t(lang, "eco.dailyCooldown", time=fmt_duration(result.get("remaining"))), mention_author=False)
            return
        await ctx.reply(_daily_message(lang, result), mention_author=False)

    @commands.command(name="work")
    @commands.guild_only()
    async def work(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{ctx.guild.id}/economy/work",
                                {"user_id": str(ctx.author.id), "role_ids": [str(r.id) for r in ctx.author.roles]})
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

    # --- New prefix commands (each mirrored by a slash command below) ---

    @commands.command(name="weekly")
    @commands.guild_only()
    async def weekly(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        text, _eph = await self._weekly(ctx.guild.id, ctx.author, lang)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="beg")
    @commands.guild_only()
    async def beg(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        text, _eph = await self._beg(ctx.guild.id, ctx.author, lang)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="crime")
    @commands.guild_only()
    async def crime(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        text, _eph = await self._crime(ctx.guild.id, ctx.author, lang)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="fish")
    @commands.guild_only()
    async def fish(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        text, _eph = await self._gather(ctx.guild.id, ctx.author, lang, "fish")
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="mine")
    @commands.guild_only()
    async def mine(self, ctx):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        text, _eph = await self._gather(ctx.guild.id, ctx.author, lang, "mine")
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="rob")
    @commands.guild_only()
    async def rob(self, ctx, member: discord.Member = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if member is None:
            p = await self._prefix(ctx.guild.id)
            await ctx.reply(t(lang, "eco.robUsage", p=p), mention_author=False)
            return
        if member.bot:
            await ctx.reply(t(lang, "eco.robBot"), mention_author=False)
            return
        text, _eph = await self._rob(ctx.guild.id, ctx.author, member, lang)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="deposit")
    @commands.guild_only()
    async def deposit(self, ctx, amount: str = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        parsed, valid = _parse_amount_all(amount)
        if not valid:
            p = await self._prefix(ctx.guild.id)
            await ctx.reply(t(lang, "eco.depositUsage", p=p), mention_author=False)
            return
        text, _eph = await self._bank(ctx.guild.id, ctx.author, lang, "deposit", parsed)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="withdraw")
    @commands.guild_only()
    async def withdraw(self, ctx, amount: str = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        parsed, valid = _parse_amount_all(amount)
        if not valid:
            p = await self._prefix(ctx.guild.id)
            await ctx.reply(t(lang, "eco.withdrawUsage", p=p), mention_author=False)
            return
        text, _eph = await self._bank(ctx.guild.id, ctx.author, lang, "withdraw", parsed)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="coinflip")
    @commands.guild_only()
    async def coinflip(self, ctx, bet: int = None, choice: str = "heads"):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if bet is None:
            p = await self._prefix(ctx.guild.id)
            await ctx.reply(t(lang, "eco.betUsage", p=p, cmd="coinflip"), mention_author=False)
            return
        text, _eph = await self._gamble(ctx.guild.id, ctx.author, lang, "coinflip", bet, _norm_side(choice))
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="dice")
    @commands.guild_only()
    async def dice(self, ctx, bet: int = None, choice: int = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if bet is None or choice is None or not (1 <= choice <= 6):
            p = await self._prefix(ctx.guild.id)
            await ctx.reply(t(lang, "eco.diceUsage", p=p), mention_author=False)
            return
        text, _eph = await self._gamble(ctx.guild.id, ctx.author, lang, "dice", bet, choice)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    @commands.command(name="slots")
    @commands.guild_only()
    async def slots(self, ctx, bet: int = None):
        ok, _ = await self._enabled(ctx.guild.id)
        if not ok:
            return
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if bet is None:
            p = await self._prefix(ctx.guild.id)
            await ctx.reply(t(lang, "eco.betUsage", p=p, cmd="slots"), mention_author=False)
            return
        text, _eph = await self._gamble(ctx.guild.id, ctx.author, lang, "slots", bet)
        if text is _SILENT:
            return
        if text:
            await ctx.reply(text, mention_author=False)

    # --- Slash variants (mirror the prefix commands; shown in the bot profile) ---

    @app_commands.command(name="daily", description="Claim your daily reward.")
    @app_commands.guild_only()
    async def daily_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/daily",
                                {"user_id": str(interaction.user.id), "role_ids": [str(r.id) for r in interaction.user.roles]})
        if not result:
            await interaction.response.send_message(t(lang, "eco.dailyFailed"), ephemeral=True)
            return
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await interaction.response.send_message(t(lang, "eco.dailyCooldown", time=fmt_duration(result.get("remaining"))), ephemeral=True)
            else:
                await interaction.response.send_message(t(lang, "eco.dailyFailed"), ephemeral=True)
            return
        await interaction.response.send_message(_daily_message(lang, result))

    @app_commands.command(name="work", description="Work for some currency.")
    @app_commands.guild_only()
    async def work_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        result = await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{interaction.guild.id}/economy/work",
                                {"user_id": str(interaction.user.id), "role_ids": [str(r.id) for r in interaction.user.roles]})
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

    # --- New slash commands (mirror the new prefix commands above) ---

    async def _slash_reply(self, interaction, lang, text, ephemeral):
        """Send a shared-helper result: `_SILENT` → ephemeral eco.disabled, else send."""
        if text is _SILENT:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        if text is None:
            text, ephemeral = t(lang, "eco.transferFailed"), True
        await interaction.response.send_message(text, ephemeral=ephemeral)

    @app_commands.command(name="weekly", description="Claim your weekly reward.")
    @app_commands.guild_only()
    async def weekly_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._weekly(interaction.guild.id, interaction.user, lang)
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="beg", description="Beg for some spare change.")
    @app_commands.guild_only()
    async def beg_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._beg(interaction.guild.id, interaction.user, lang)
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="crime", description="Commit a crime for a risky payout.")
    @app_commands.guild_only()
    async def crime_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._crime(interaction.guild.id, interaction.user, lang)
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="fish", description="Go fishing for some currency.")
    @app_commands.guild_only()
    async def fish_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._gather(interaction.guild.id, interaction.user, lang, "fish")
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="mine", description="Mine some ore for currency.")
    @app_commands.guild_only()
    async def mine_slash(self, interaction: discord.Interaction):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._gather(interaction.guild.id, interaction.user, lang, "mine")
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="rob", description="Attempt to rob another member.")
    @app_commands.guild_only()
    @app_commands.describe(member="Who to rob")
    async def rob_slash(self, interaction: discord.Interaction, member: discord.Member):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(t(lang, "eco.robBot"), ephemeral=True)
            return
        text, eph = await self._rob(interaction.guild.id, interaction.user, member, lang)
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="deposit", description="Deposit currency into your bank.")
    @app_commands.guild_only()
    @app_commands.describe(amount="How much to deposit (leave empty or 0 for all)")
    async def deposit_slash(self, interaction: discord.Interaction, amount: int = None):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._bank(interaction.guild.id, interaction.user, lang, "deposit", amount if amount is not None else 0)
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="withdraw", description="Withdraw currency from your bank.")
    @app_commands.guild_only()
    @app_commands.describe(amount="How much to withdraw (leave empty or 0 for all)")
    async def withdraw_slash(self, interaction: discord.Interaction, amount: int = None):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._bank(interaction.guild.id, interaction.user, lang, "withdraw", amount if amount is not None else 0)
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="coinflip", description="Bet on a coin flip.")
    @app_commands.guild_only()
    @app_commands.describe(bet="How much to bet", choice="heads or tails (default heads)")
    async def coinflip_slash(self, interaction: discord.Interaction, bet: int, choice: str = "heads"):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._gamble(interaction.guild.id, interaction.user, lang, "coinflip", bet, _norm_side(choice))
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="dice", description="Bet on a dice roll (1-6).")
    @app_commands.guild_only()
    @app_commands.describe(bet="How much to bet", choice="Your guess (1-6)")
    async def dice_slash(self, interaction: discord.Interaction, bet: int, choice: app_commands.Range[int, 1, 6]):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._gamble(interaction.guild.id, interaction.user, lang, "dice", bet, int(choice))
        await self._slash_reply(interaction, lang, text, eph)

    @app_commands.command(name="slots", description="Spin the slot machine.")
    @app_commands.guild_only()
    @app_commands.describe(bet="How much to bet")
    async def slots_slash(self, interaction: discord.Interaction, bet: int):
        ok, _ = await self._enabled(interaction.guild.id)
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not ok:
            await interaction.response.send_message(t(lang, "eco.disabled"), ephemeral=True)
            return
        text, eph = await self._gamble(interaction.guild.id, interaction.user, lang, "slots", bet)
        await self._slash_reply(interaction, lang, text, eph)

    # --- Passive earning listeners ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or message.webhook_id is not None:
            return
        try:
            settings = await self._cached_settings(message.guild.id)
            if not settings or not settings.get("enabled") or not settings.get("chat_earn_enabled"):
                return
            role_ids = [str(r.id) for r in getattr(message.author, "roles", [])]
            await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{message.guild.id}/economy/earn",
                           {"user_id": str(message.author.id), "source": "chat", "role_ids": role_ids})
        except Exception as exc:
            print(f"[economy] chat earn failed: {exc}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or member.guild is None:
            return
        try:
            guild = member.guild
            key = (guild.id, member.id)
            now = discord.utils.utcnow().timestamp()
            afk_id = guild.afk_channel.id if guild.afk_channel else None

            def _active(channel):
                return channel is not None and channel.id != afk_id

            was_active = _active(before.channel)
            now_active = _active(after.channel)
            moved = (before.channel is not None and after.channel is not None
                     and before.channel.id != after.channel.id)

            # A voice session ended when the member left an active channel
            # (disconnected, moved elsewhere, or moved into the AFK channel).
            if was_active and (after.channel is None or moved):
                since = self._voice_since.pop(key, None)
                if since is not None:
                    minutes = int((now - since) // 60)
                    if minutes >= 1:
                        settings = await self._cached_settings(guild.id)
                        if settings and settings.get("enabled") and settings.get("voice_earn_enabled"):
                            role_ids = [str(r.id) for r in member.roles]
                            await bot_post(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/economy/earn",
                                           {"user_id": str(member.id), "source": "voice",
                                            "minutes": minutes, "role_ids": role_ids})

            # (Re)start the timer when the member is now in an active channel
            # (fresh join or moved into a new active channel); clear it otherwise.
            if now_active:
                if not was_active or moved:
                    self._voice_since[key] = now
            else:
                self._voice_since.pop(key, None)
        except Exception as exc:
            print(f"[economy] voice earn failed: {exc}")


async def setup(bot):
    await bot.add_cog(Economy(bot))
