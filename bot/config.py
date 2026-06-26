import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:3000')
DATABASE_URL = os.getenv('DATABASE_URL', 'bot.db')
# Bot version string, surfaced in the Owner admin → Monitoring → Bot-Health panel.
BOT_VERSION = os.getenv('BOT_VERSION', '1.0.0')
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

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN not set in .env file")
if not DISCORD_CLIENT_ID:
    raise ValueError("DISCORD_CLIENT_ID not set in .env file")
if not BOT_API_KEY:
    print("WARNING: BOT_API_KEY not set in .env — backend bot API calls will fail with 401.")
