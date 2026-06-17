import express from 'express'
import { getGamesSettings, upsertGamesSettings, getGameLeaderboard, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getGamesSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get games settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch games settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const settings = await upsertGamesSettings(guildId, req.body || {})
    await logAuditAction(req.user.id, guildId, 'UPDATE_GAMES_SETTINGS', settings)
    res.json({ success: true, message: 'Games settings updated', settings })
  } catch (error) {
    console.error('Update games settings error:', error.message)
    res.status(500).json({ error: 'Failed to update games settings' })
  }
})

router.get('/leaderboard', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const leaderboard = await getGameLeaderboard(req.params.guild_id, req.query.game, Number(req.query.limit) || 25)
    res.json({ success: true, leaderboard })
  } catch (error) {
    console.error('Get game leaderboard error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
})

export default router
