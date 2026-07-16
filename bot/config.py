import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:3000')
DATABASE_URL = os.getenv('DATABASE_URL', 'bot.db')
# Bot version string, surfaced in the Owner admin → Monitoring → Bot-Health panel.
# Prefers BOT_VERSION, then a shared APP_VERSION (e.g. a git short SHA injected at
# deploy time) so the panel reflects the actual build without manual bumping.
BOT_VERSION = os.getenv('BOT_VERSION') or os.getenv('APP_VERSION') or '1.0.0'
# Shared secret used to authenticate to backend /api/bot/* endpoints.
# Must match BOT_API_KEY in the backend's .env.
BOT_API_KEY = os.getenv('BOT_API_KEY')

# --- Social Notifications (YouTube / Twitch / Kick / …) ---
# All optional: the social_notify cog degrades gracefully and skips any
# platform whose credentials are absent. Do NOT raise if these are unset.
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
KICK_CLIENT_ID = os.getenv('KICK_CLIENT_ID')
KICK_CLIENT_SECRET = os.getenv('KICK_CLIENT_SECRET')
SOCIAL_POLL_INTERVAL = int(os.getenv('SOCIAL_POLL_INTERVAL', '180'))

# --- Minecraft server status ---
# The minecraft cog maintains one auto-updating live-status message per server
# (via the public mcsrvstat.us API — no key/dependency needed). Poll interval in
# seconds; a hard minimum of 60 is enforced in the cog to be nice to the API.
MINECRAFT_POLL_INTERVAL = int(os.getenv('MINECRAFT_POLL_INTERVAL', '120'))

# --- Premium / SKU monetization (all optional) ---
# Maps Discord Premium-App-Subscription SKU IDs to the bot's tiers. The
# premium_sync cog reads the application's entitlements via the Discord API and
# pushes the resulting per-guild tier to the backend. If no SKU IDs are set the
# cog stays inert — owner-set (manual) premium in the dashboard still works.
# APPLICATION_ID defaults to DISCORD_CLIENT_ID (they're the same for a bot app).
APPLICATION_ID = os.getenv('APPLICATION_ID') or DISCORD_CLIENT_ID
SKU_BASIC_ID = os.getenv('SKU_BASIC_ID')
SKU_PRO_ID = os.getenv('SKU_PRO_ID')
PREMIUM_POLL_INTERVAL = int(os.getenv('PREMIUM_POLL_INTERVAL', '300'))

# --- Per-guild bot profile (nickname + avatar) ---
# How often the bot_profile cog polls for changed per-guild profiles (seconds).
BOT_PROFILE_POLL_INTERVAL = max(int(os.getenv('BOT_PROFILE_POLL_INTERVAL', '60')), 30)

# --- Native Discord AutoMod sync ---
# How often the automod_sync cog reconciles native AutoMod rules for guilds whose
# moderation config changed (seconds). Earns the "Uses AutoMod" badge.
AUTOMOD_POLL_INTERVAL = max(int(os.getenv('AUTOMOD_POLL_INTERVAL', '90')), 60)

# --- Music module / Lavalink (Pro) ---
# The music cog connects to a Lavalink audio server via wavelink. If LAVALINK_HOST
# is unset the cog stays inert (no node connection, no playback) — the rest of the
# bot is unaffected. YouTube is intentionally NOT enabled on the Lavalink side.
LAVALINK_HOST = os.getenv('LAVALINK_HOST')                       # e.g. "lavalink" (docker) or "localhost"
LAVALINK_PORT = int(os.getenv('LAVALINK_PORT', '2333'))
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
LAVALINK_SECURE = os.getenv('LAVALINK_SECURE', 'false').lower() in ('1', 'true', 'yes')
MUSIC_POLL_INTERVAL = int(os.getenv('MUSIC_POLL_INTERVAL', '4'))  # dashboard control-command poll (seconds)

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN not set in .env file")
if not DISCORD_CLIENT_ID:
    raise ValueError("DISCORD_CLIENT_ID not set in .env file")
if not BOT_API_KEY:
    print("WARNING: BOT_API_KEY not set in .env — backend bot API calls will fail with 401.")
