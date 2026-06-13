import express from 'express'
import { getGuildGiveaways, deleteGiveaway, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const giveaways = await getGuildGiveaways(req.params.guild_id)
    res.json({ success: true, giveaways })
  } catch (error) {
    console.error('Get giveaways error:', error.message)
    res.status(500).json({ error: 'Failed to fetch giveaways' })
  }
})

router.delete('/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteGiveaway(guildId, req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Giveaway not found' })
    await logAuditAction(req.user.id, guildId, 'GIVEAWAY_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete giveaway error:', error.message)
    res.status(500).json({ error: 'Failed to delete giveaway' })
  }
})

export default router
