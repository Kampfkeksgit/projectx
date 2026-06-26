import express from 'express'
import { getGeneralSettings, upsertGeneralSettings, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getGeneralSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get general settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch general settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertGeneralSettings(guildId, req.body || {})
    const settings = await getGeneralSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_GENERAL_SETTINGS', settings)
    res.json({ success: true, message: 'General settings updated', settings })
  } catch (error) {
    console.error('Update general settings error:', error.message)
    res.status(500).json({ error: 'Failed to update general settings' })
  }
})

export default router
