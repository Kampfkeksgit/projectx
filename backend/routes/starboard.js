import express from 'express'
import { getStarboardSettings, upsertStarboardSettings, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getStarboardSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get starboard settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch starboard settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertStarboardSettings(guildId, req.body || {})
    const settings = await getStarboardSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_STARBOARD_SETTINGS', settings)
    res.json({ success: true, message: 'Starboard settings updated', settings })
  } catch (error) {
    console.error('Update starboard settings error:', error.message)
    res.status(500).json({ error: 'Failed to update starboard settings' })
  }
})

export default router
