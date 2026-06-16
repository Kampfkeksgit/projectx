import express from 'express'
import { getGuildPolls, deletePoll, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const polls = await getGuildPolls(req.params.guild_id)
    res.json({ success: true, polls })
  } catch (error) {
    console.error('Get polls error:', error.message)
    res.status(500).json({ error: 'Failed to fetch polls' })
  }
})

router.delete('/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deletePoll(guildId, req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Poll not found' })
    await logAuditAction(req.user.id, guildId, 'POLL_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete poll error:', error.message)
    res.status(500).json({ error: 'Failed to delete poll' })
  }
})

export default router
