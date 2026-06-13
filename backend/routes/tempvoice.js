import express from 'express'
import { getTempVoiceSettings, upsertTempVoiceSettings, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getTempVoiceSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get tempvoice settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch temp-voice settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertTempVoiceSettings(guildId, req.body || {})
    const settings = await getTempVoiceSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_TEMPVOICE_SETTINGS', settings)
    res.json({ success: true, message: 'Temp-voice settings updated', settings })
  } catch (error) {
    console.error('Update tempvoice settings error:', error.message)
    res.status(500).json({ error: 'Failed to update temp-voice settings' })
  }
})

export default router
