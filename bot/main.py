import traceback

import discord
from discord.ext import commands
import config
from utils.command_config import get_prefix as cc_get_prefix, is_disabled as cc_is_disabled, DEFAULT_PREFIX

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for member join/leave events
intents.guilds = True
# Required by the Stats cog to count online/offline members. This is a
# PRIVILEGED intent — it must also be enabled in the Discord Developer Portal
# (Bot → Privileged Gateway Intents → Presence Intent). Without it every member
# reads as offline and the online counter stays 0.
intents.presences = True


async def _resolve_prefix(bot, message):
    """Per-guild prefix from the command-manager config (cached). Falls back to
    '!' for DMs / backend errors. The bot mention always works too."""
    base = DEFAULT_PREFIX
    if message.guild is not None:
        try:
            base = await cc_get_prefix(config.BACKEND_URL, config.BOT_API_KEY, message.guild.id)
        except Exception:
            base = DEFAULT_PREFIX
    return commands.when_mentioned_or(base)(bot, message)


bot = commands.Bot(command_prefix=_resolve_prefix, intents=intents)


@bot.check
async def _command_gate(ctx):
    """Global gate: block built-in prefix commands disabled for this guild."""
    if ctx.guild is None or ctx.command is None:
        return True
    try:
        if await cc_is_disabled(config.BACKEND_URL, config.BOT_API_KEY, ctx.guild.id, ctx.command.qualified_name):
            return False  # raises CheckFailure → swallowed in on_command_error
    except Exception:
        return True
    return True


async def _tree_gate(interaction):
    """Global gate for slash commands disabled for this guild."""
    if interaction.guild is None or interaction.command is None:
        return True
    try:
        if await cc_is_disabled(config.BACKEND_URL, config.BOT_API_KEY, interaction.guild.id, interaction.command.qualified_name):
            try:
                await interaction.response.send_message("This command is disabled on this server.", ephemeral=True)
            except Exception:
                pass
            return False
    except Exception:
        return True
    return True


bot.tree.interaction_check = _tree_gate


@bot.event
async def on_command_error(ctx, error):
    # Disabled commands / missing permissions / unknown commands: stay silent.
    if isinstance(error, (commands.CheckFailure, commands.CommandNotFound)):
        return
    # Preserve visibility for genuine errors (matches the previous default).
    traceback.print_exception(type(error), error, error.__traceback__)

@bot.event
async def setup_hook():
    # Runs exactly once at startup (before the gateway connects). Loading cogs
    # here — instead of in on_ready, which re-fires on every reconnect / session
    # invalidation — avoids "Extension already loaded" errors.
    try:
        await bot.load_extension('cogs.welcome_leave')
        print('✅​ Welcome/Leave cog loaded')
    except Exception as e:
        print(f'❌ Failed to load cog: {e}')
    try:
        await bot.load_extension('cogs.autorole')
        print('✅​ Auto-Role cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Auto-Role cog: {e}')
    try:
        await bot.load_extension('cogs.logs')
        print('✅​ Server-Logs cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Server-Logs cog: {e}')
    try:
        await bot.load_extension('cogs.moderation')
        print('✅​ Moderation cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Moderation cog: {e}')
    try:
        await bot.load_extension('cogs.presence')
        print('✅​ Presence cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Presence cog: {e}')
    try:
        await bot.load_extension('cogs.guild_sync')
        print('✅​ Guild-Sync cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Guild-Sync cog: {e}')
    try:
        await bot.load_extension('cogs.reaction_roles')
        print('✅​ Reaction-Roles cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Reaction-Roles cog: {e}')
    try:
        await bot.load_extension('cogs.leveling')
        print('✅​ Leveling cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Leveling cog: {e}')
    try:
        await bot.load_extension('cogs.custom_commands')
        print('✅​ Custom-Commands cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Custom-Commands cog: {e}')
    try:
        await bot.load_extension('cogs.social_notify')
        print('✅​ Social-Notify cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Social-Notify cog: {e}')
    try:
        await bot.load_extension('cogs.stats')
        print('✅​ Stats cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Stats cog: {e}')
    try:
        await bot.load_extension('cogs.tempvoice')
        print('✅​ Temp-Voice cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Temp-Voice cog: {e}')
    try:
        await bot.load_extension('cogs.starboard')
        print('✅​ Starboard cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Starboard cog: {e}')
    try:
        await bot.load_extension('cogs.suggestions')
        print('✅​ Suggestions cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Suggestions cog: {e}')
    try:
        await bot.load_extension('cogs.birthday')
        print('✅​ Birthday cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Birthday cog: {e}')
    try:
        await bot.load_extension('cogs.scheduler')
        print('✅​ Scheduler cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Scheduler cog: {e}')
    try:
        await bot.load_extension('cogs.antiraid')
        print('✅​ Anti-Raid cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Anti-Raid cog: {e}')
    try:
        await bot.load_extension('cogs.slash_utils')
        print('✅​ Slash-Utils cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Slash-Utils cog: {e}')
    try:
        await bot.load_extension('cogs.verification')
        print('✅​ Verification cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Verification cog: {e}')
    try:
        await bot.load_extension('cogs.rolemenus')
        print('✅​ Role-Menus cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Role-Menus cog: {e}')
    try:
        await bot.load_extension('cogs.tickets')
        print('✅​ Tickets cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Tickets cog: {e}')
    try:
        await bot.load_extension('cogs.giveaways')
        print('✅​ Giveaways cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Giveaways cog: {e}')
    try:
        await bot.load_extension('cogs.premium_sync')
        print('✅​ Premium sync cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Premium sync cog: {e}')
    try:
        await bot.load_extension('cogs.counting')
        print('✅​ Counting cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Counting cog: {e}')
    try:
        await bot.load_extension('cogs.polls')
        print('✅​ Polls cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Polls cog: {e}')
    try:
        await bot.load_extension('cogs.invitetracking')
        print('✅​ Invite-Tracking cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Invite-Tracking cog: {e}')
    try:
        await bot.load_extension('cogs.applications')
        print('✅​ Applications cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Applications cog: {e}')
    try:
        await bot.load_extension('cogs.economy')
        print('✅​ Economy cog loaded')
    except Exception as e:
        print(f'❌ Failed to load Economy cog: {e}')
    for _game in ('tictactoe', 'rps', 'trivia', 'connect4', 'hangman', 'poker'):
        try:
            await bot.load_extension(f'cogs.{_game}')
            print(f'✅​ Game cog loaded: {_game}')
        except Exception as e:
            print(f'❌ Failed to load game cog {_game}: {e}')

    # Sync application (slash) commands. setup_hook runs once, so no guard needed.
    try:
        synced = await bot.tree.sync()
        print(f'✅​ Synced {len(synced)} application commands')
    except Exception as e:
        print(f'❌ Failed to sync application commands: {e}')


@bot.event
async def on_ready():
    # Fires on every (re)connect — keep it side-effect-free besides logging.
    print(f'ℹ️ {bot.user} has connected to Discord!')
    print(f'🆔 Bot ID: {bot.user.id}')


if __name__ == '__main__':
    bot.run(config.DISCORD_TOKEN)
