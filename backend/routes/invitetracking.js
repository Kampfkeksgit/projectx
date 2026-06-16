import express from 'express'
import { getInviteSettings, upsertInviteSettings, getInviteLeaderboard, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getInviteSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get invite settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch invite settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertInviteSettings(guildId, req.body || {})
    const settings = await getInviteSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_INVITETRACKING_SETTINGS', settings)
    res.json({ success: true, message: 'Invite tracking settings updated', settings })
  } catch (error) {
    console.error('Update invite settings error:', error.message)
    res.status(500).json({ error: 'Failed to update invite settings' })
  }
})

router.get('/leaderboard', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const leaderboard = await getInviteLeaderboard(req.params.guild_id, Number(req.query.limit) || 25)
    res.json({ success: true, leaderboard })
  } catch (error) {
    console.error('Get invite leaderboard error:', error.message)
    res.status(500).json({ error: 'Failed to fetch invite leaderboard' })
  }
})

export default router
