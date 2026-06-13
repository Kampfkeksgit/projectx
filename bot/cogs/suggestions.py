"""Suggestions cog.

Members run `!suggest <text>`; the bot posts the suggestion as an embed in the
configured suggestions channel with up/down vote reactions.

Backend contract (X-Bot-Token auth):
  GET /api/bot/guilds/{gid}/settings/suggestions
      → { enabled, suggest_channel_id, upvote_emoji, downvote_emoji }

Logging prefix: "[suggestions]".
"""

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings


SUGGEST_COLOR = 0x5865F2


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY

    @commands.command(name="suggest")
    @commands.guild_only()
    async def suggest(self, ctx, *, text: str = None):
        if not text or not text.strip():
            await ctx.reply("Usage: `!suggest <your suggestion>`", mention_author=False)
            return

        settings = await fetch_bot_settings(self.backend_url, self.api_key, ctx.guild.id, "suggestions")
        if not settings or not settings.get("enabled"):
            await ctx.reply("Suggestions are not enabled on this server.", mention_author=False)
            return

        channel_id = settings.get("suggest_channel_id")
        channel = ctx.guild.get_channel(int(channel_id)) if channel_id else None
        if channel is None:
            await ctx.reply("The suggestions channel is not configured.", mention_author=False)
            return

        embed = discord.Embed(
            description=text.strip()[:4000],
            color=SUGGEST_COLOR,
            timestamp=ctx.message.created_at,
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Suggestion • {ctx.author}")

        try:
            msg = await channel.send(embed=embed)
        except discord.Forbidden:
            await ctx.reply("I can't post in the suggestions channel.", mention_author=False)
            return
        except Exception as exc:
            print(f"[suggestions] post failed: {exc}")
            await ctx.reply("Something went wrong posting your suggestion.", mention_author=False)
            return

        for emoji in (settings.get("upvote_emoji") or "👍", settings.get("downvote_emoji") or "👎"):
            try:
                await msg.add_reaction(emoji)
            except Exception as exc:
                print(f"[suggestions] add_reaction failed: {exc}")

        # Tidy up the command message; confirm to the author.
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(f"{ctx.author.mention} ✅ your suggestion was posted in {channel.mention}.", delete_after=8)


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
