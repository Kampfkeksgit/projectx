"""Birthday cog.

Members set their birthday with `!birthday DD.MM[.YYYY]`. Once a day the bot
announces everyone whose birthday is today and (optionally) gives them a
birthday role for the day, removing it again the next day.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/birthdays/today        → { birthdays: [{ guild_id, user_id, year,
                                            announce_channel_id, message_template, birthday_role_id }] }
  GET  /api/bot/birthdays/role-guilds  → { guilds: [{ guild_id, birthday_role_id }] }
  POST /api/bot/guilds/{gid}/birthdays body { user_id, day, month, year? }

Logging prefix: "[birthday]".
"""

import re

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_post
from utils.bot_i18n import t, lang_for


BIRTHDAY_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?$")
BIRTHDAY_COLOR = 0xF472B6


class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._last_run_date = None  # (year, month, day) of the last daily run
        self.daily_loop.start()

    def cog_unload(self):
        self.daily_loop.cancel()

    @tasks.loop(minutes=30)
    async def daily_loop(self):
        await self._run_daily()

    @daily_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _run_daily(self):
        if not self.api_key or not self.backend_url:
            return
        # discord.utils.utcnow keeps us off the forbidden bare datetime.now().
        today = discord.utils.utcnow().date()
        key = (today.year, today.month, today.day)
        if self._last_run_date == key:
            return

        data = await bot_get(self.backend_url, self.api_key, "/api/bot/birthdays/today")
        if data is None:
            return  # don't stamp the date on failure → retry next tick
        birthdays = data.get("birthdays") or []

        # Group today's celebrants per guild for the role sweep.
        today_by_guild = {}
        for row in birthdays:
            today_by_guild.setdefault(str(row.get("guild_id")), set()).add(str(row.get("user_id")))

        # Announce + assign role.
        for row in birthdays:
            await self._celebrate(row)

        # Remove the birthday role from yesterday's holders.
        await self._sweep_roles(today_by_guild)

        self._last_run_date = key

    async def _celebrate(self, row):
        guild = self.bot.get_guild(int(row["guild_id"]))
        if guild is None:
            return
        member = guild.get_member(int(row["user_id"]))
        if member is None:
            return

        channel_id = row.get("announce_channel_id")
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if channel is not None:
            template = row.get("message_template") or "🎉 Happy Birthday {user}!"
            text = template.replace("{user}", member.mention).replace("{name}", member.display_name)
            try:
                await channel.send(text)
            except Exception as exc:
                print(f"[birthday] announce failed in {guild.id}: {exc}")

        role_id = row.get("birthday_role_id")
        if role_id:
            role = guild.get_role(int(role_id))
            if role is not None and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Birthday")
                except Exception as exc:
                    print(f"[birthday] add role failed in {guild.id}: {exc}")

    async def _sweep_roles(self, today_by_guild):
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/birthdays/role-guilds")
        if not data:
            return
        for row in (data.get("guilds") or []):
            guild = self.bot.get_guild(int(row["guild_id"]))
            if guild is None:
                continue
            role = guild.get_role(int(row["birthday_role_id"]))
            if role is None:
                continue
            celebrants = today_by_guild.get(str(guild.id), set())
            for member in list(role.members):
                if str(member.id) not in celebrants:
                    try:
                        await member.remove_roles(role, reason="Birthday over")
                    except Exception as exc:
                        print(f"[birthday] remove role failed in {guild.id}: {exc}")

    @commands.command(name="birthday", aliases=["setbirthday", "bday"])
    @commands.guild_only()
    async def birthday(self, ctx, date: str = None):
        lang = await lang_for(self.backend_url, self.api_key, ctx.guild.id)
        if not date:
            await ctx.reply(t(lang, "bday.usage"), mention_author=False)
            return
        m = BIRTHDAY_RE.match(date.strip())
        if not m:
            await ctx.reply(t(lang, "bday.badFormat"), mention_author=False)
            return
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else None
        if not (1 <= month <= 12 and 1 <= day <= 31):
            await ctx.reply(t(lang, "bday.badDate"), mention_author=False)
            return

        body = {"user_id": str(ctx.author.id), "day": day, "month": month}
        if year:
            body["year"] = year if year > 100 else 2000 + year
        result = await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{ctx.guild.id}/birthdays", body,
        )
        if result is None:
            await ctx.reply(t(lang, "bday.saveFailed"), mention_author=False)
            return
        await ctx.reply(t(lang, "bday.saved", date=f"{day:02d}.{month:02d}"), mention_author=False)


async def setup(bot):
    await bot.add_cog(Birthday(bot))
