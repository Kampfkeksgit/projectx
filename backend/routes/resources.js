import express from 'express'
import { getGuildChannels, getGuildRoles } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

/**
 * List all channels the bot has synced for a guild. Used by the dashboard to
 * render channel-picker dropdowns instead of raw-ID inputs.
 *
 *   GET /api/guilds/:guild_id/channels
 *   Cookie: projectx_session
 *
 * Returns `{ success: true, channels: [...] }`. If the bot has never synced
 * (chicken/egg on a fresh bot), returns an empty array — never 404 — so the
 * frontend can render an "empty" state gracefully.
 */
router.get('/channels', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const rows = await getGuildChannels(guildId)
    const channels = rows.map((row) => ({
      id: row.id,
      name: row.name,
      type: row.type,
      parent_id: row.parent_id ?? null,
      position: row.position ?? 0
    }))
    res.json({ success: true, channels })
  } catch (error) {
    console.error('Get guild channels error:', error.message)
    res.status(500).json({ error: 'Failed to fetch channels' })
  }
})

/**
 * List all roles the bot has synced for a guild.
 *
 *   GET /api/guilds/:guild_id/roles?include_default=0&include_managed=1
 *   Cookie: projectx_session
 *
 * Defaults: include_default=0 (drop @everyone), include_managed=1 (keep
 * integration-managed roles). Returns `{ success: true, roles: [...] }` and
 * falls back to `[]` if the bot has never synced.
 */
router.get('/roles', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const includeDefault = String(req.query.include_default ?? '0') === '1'
    const includeManaged = String(req.query.include_managed ?? '1') === '1'
    const rows = await getGuildRoles(guildId, { includeDefault, includeManaged })
    const roles = rows.map((row) => ({
      id: row.id,
      name: row.name,
      color: row.color ?? 0,
      position: row.position ?? 0,
      managed: !!row.managed,
      is_default: !!row.is_default
    }))
    res.json({ success: true, roles })
  } catch (error) {
    console.error('Get guild roles error:', error.message)
    res.status(500).json({ error: 'Failed to fetch roles' })
  }
})

export default router
