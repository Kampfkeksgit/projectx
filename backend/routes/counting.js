import express from 'express'
import { getCountingSettings, upsertCountingSettings, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getCountingSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get counting settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch counting settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertCountingSettings(guildId, req.body || {})
    const settings = await getCountingSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_COUNTING_SETTINGS', settings)
    res.json({ success: true, message: 'Counting settings updated', settings })
  } catch (error) {
    console.error('Update counting settings error:', error.message)
    res.status(500).json({ error: 'Failed to update counting settings' })
  }
})

export default router
