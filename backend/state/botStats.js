/**
 * In-memory bot stats — populated by the bot via PUT /api/bot/stats
 * and read by the public landing page via GET /api/public/stats.
 *
 * Reset to zeros if the bot is offline. The bot pings every 5 minutes
 * (see bot/cogs/presence.py), so the public endpoint considers data
 * older than ~15 minutes as stale and zeroes guild_count/user_count.
 */

const STALE_AFTER_MS = 15 * 60 * 1000

const state = {
  guild_count: 0,
  user_count: 0,
  started_at: null,   // unix seconds; when the bot connected to the gateway
  last_updated: 0     // unix ms; when we last received a stats ping
}

export function setBotStats({ guild_count, user_count, started_at }) {
  if (Number.isFinite(guild_count)) state.guild_count = Math.max(0, Math.floor(guild_count))
  if (Number.isFinite(user_count))  state.user_count  = Math.max(0, Math.floor(user_count))
  if (Number.isFinite(started_at) && started_at > 0) state.started_at = Math.floor(started_at)
  state.last_updated = Date.now()
}

export function getPublicStats() {
  const isStale = Date.now() - state.last_updated > STALE_AFTER_MS
  const nowSec = Math.floor(Date.now() / 1000)
  const uptime = !isStale && state.started_at ? Math.max(0, nowSec - state.started_at) : 0
  return {
    servers: isStale ? 0 : state.guild_count,
    users:   isStale ? 0 : state.user_count,
    uptime_seconds: uptime,
    online: !isStale
  }
}
