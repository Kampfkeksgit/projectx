import express from 'express'
import { getAntiRaidSettings, upsertAntiRaidSettings, ANTIRAID_ACTIONS, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getAntiRaidSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get antiraid settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch anti-raid settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}
    if (body.action !== undefined && !ANTIRAID_ACTIONS.includes(body.action)) {
      return res.status(400).json({ error: 'action must be one of: ' + ANTIRAID_ACTIONS.join(', ') })
    }
    await upsertAntiRaidSettings(guildId, body)
    const settings = await getAntiRaidSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_ANTIRAID_SETTINGS', settings)
    res.json({ success: true, message: 'Anti-raid settings updated', settings })
  } catch (error) {
    console.error('Update antiraid settings error:', error.message)
    res.status(500).json({ error: 'Failed to update anti-raid settings' })
  }
})

export default router
