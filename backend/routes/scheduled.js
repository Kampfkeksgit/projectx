import express from 'express'
import {
  getScheduledMessages,
  createScheduledMessage,
  updateScheduledMessage,
  deleteScheduledMessage,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const messages = await getScheduledMessages(req.params.guild_id)
    res.json({ success: true, messages })
  } catch (error) {
    console.error('Get scheduled messages error:', error.message)
    res.status(500).json({ error: 'Failed to fetch scheduled messages' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let message
    try {
      message = await createScheduledMessage(guildId, req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'SCHEDULED_CREATE', { id: message.id, channel_id: message.channel_id })
    res.json({ success: true, message })
  } catch (error) {
    console.error('Create scheduled message error:', error.message)
    res.status(500).json({ error: 'Failed to create scheduled message' })
  }
})

router.put('/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let message
    try {
      message = await updateScheduledMessage(guildId, req.params.id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'Scheduled message not found' })
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'SCHEDULED_UPDATE', { id: message.id, enabled: message.enabled })
    res.json({ success: true, message })
  } catch (error) {
    console.error('Update scheduled message error:', error.message)
    res.status(500).json({ error: 'Failed to update scheduled message' })
  }
})

router.delete('/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteScheduledMessage(guildId, req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Scheduled message not found' })
    await logAuditAction(req.user.id, guildId, 'SCHEDULED_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete scheduled message error:', error.message)
    res.status(500).json({ error: 'Failed to delete scheduled message' })
  }
})

export default router
