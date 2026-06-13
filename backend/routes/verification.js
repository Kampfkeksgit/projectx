import express from 'express'
import { getVerificationSettings, upsertVerificationSettings, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getVerificationSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get verification settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch verification settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertVerificationSettings(guildId, req.body || {})
    const settings = await getVerificationSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_VERIFICATION_SETTINGS', settings)
    res.json({ success: true, message: 'Verification settings updated', settings })
  } catch (error) {
    console.error('Update verification settings error:', error.message)
    res.status(500).json({ error: 'Failed to update verification settings' })
  }
})

export default router
