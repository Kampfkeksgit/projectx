import express from 'express'
import {
  WELCOME_LEAVE_DEFAULTS,
  getGuildSettings,
  upsertGuildSettings,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

/**
 * Shape the raw `guild_settings` row (with parsed embed objects coming from
 * getGuildSettings) into the public response object: integers → booleans,
 * NULL channels stay NULL, embed objects pass through.
 */
function shapeSettings(row) {
  if (!row) return null
  return {
    guild_id: row.guild_id,
    welcome_enabled: !!row.welcome_enabled,
    welcome_channel_id: row.welcome_channel_id ?? null,
    welcome_message: row.welcome_message ?? WELCOME_LEAVE_DEFAULTS.welcome_message,
    leave_enabled: !!row.leave_enabled,
    leave_channel_id: row.leave_channel_id ?? null,
    leave_message: row.leave_message ?? WELCOME_LEAVE_DEFAULTS.leave_message,
    welcome_use_embed: !!row.welcome_use_embed,
    welcome_embed: row.welcome_embed ?? { ...WELCOME_LEAVE_DEFAULTS.welcome_embed },
    welcome_ping_user: !!row.welcome_ping_user,
    welcome_dm_enabled: !!row.welcome_dm_enabled,
    welcome_dm_message: row.welcome_dm_message ?? '',
    welcome_delete_after: row.welcome_delete_after ?? 0,
    leave_use_embed: !!row.leave_use_embed,
    leave_embed: row.leave_embed ?? { ...WELCOME_LEAVE_DEFAULTS.leave_embed },
    leave_delete_after: row.leave_delete_after ?? 0,
    created_at: row.created_at ?? null,
    updated_at: row.updated_at ?? null
  }
}

function defaultResponse(guildId) {
  return {
    guild_id: guildId,
    ...WELCOME_LEAVE_DEFAULTS,
    welcome_embed: { ...WELCOME_LEAVE_DEFAULTS.welcome_embed },
    leave_embed: { ...WELCOME_LEAVE_DEFAULTS.leave_embed },
    created_at: null,
    updated_at: null
  }
}

/**
 * Get guild settings
 * GET /api/guilds/:guild_id/settings
 * Returns the full extended Welcome/Leave shape, with defaults if no row exists.
 */
router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const settings = await getGuildSettings(guildId)

    if (!settings) {
      return res.json({
        success: true,
        settings: defaultResponse(guildId)
      })
    }

    res.json({
      success: true,
      settings: shapeSettings(settings)
    })
  } catch (error) {
    console.error('Get guild settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch settings' })
  }
})

/**
 * Update guild settings (full replacement)
 * PUT /api/guilds/:guild_id/settings
 * Accepts the full extended shape; missing fields fall back to defaults.
 */
router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    // db.upsertGuildSettings handles all coercion/clamping/truncation.
    await upsertGuildSettings(guildId, body)

    const saved = shapeSettings(await getGuildSettings(guildId))

    await logAuditAction(req.user.id, guildId, 'UPDATE_SETTINGS', saved)

    res.json({
      success: true,
      message: 'Settings updated successfully',
      settings: saved
    })
  } catch (error) {
    console.error('Update guild settings error:', error.message)
    res.status(500).json({ error: 'Failed to update settings' })
  }
})

/**
 * Patch guild settings (partial update)
 * PATCH /api/guilds/:guild_id/settings
 * Merges the partial body with the current row (or defaults) then upserts.
 */
router.patch('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const currentRow = await getGuildSettings(guildId)

    // Build a full shape: current row (or defaults) merged with provided keys.
    const base = currentRow
      ? shapeSettings(currentRow)
      : defaultResponse(guildId)

    const merged = { ...base }
    for (const key of Object.keys(req.body || {})) {
      merged[key] = req.body[key]
    }

    await upsertGuildSettings(guildId, merged)

    const saved = shapeSettings(await getGuildSettings(guildId))

    await logAuditAction(req.user.id, guildId, 'PATCH_SETTINGS', req.body)

    res.json({
      success: true,
      message: 'Settings updated',
      settings: saved
    })
  } catch (error) {
    console.error('Patch guild settings error:', error.message)
    res.status(500).json({ error: 'Failed to patch settings' })
  }
})

export default router
