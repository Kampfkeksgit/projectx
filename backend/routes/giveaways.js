import express from 'express'
import { getGuildGiveaways, createGiveaway, deleteGiveaway, logAuditAction } from '../db.js'
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

// Dashboard create: stores a pending giveaway (no message_id); the bot posts it.
// Duration comes as seconds; ends_at is computed server-side.
router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const b = req.body || {}
    const duration = Math.floor(Number(b.duration_seconds))
    if (!Number.isFinite(duration) || duration < 30 || duration > 30 * 86400) {
      return res.status(400).json({ error: 'invalid_duration', message: 'duration_seconds must be 30..2592000' })
    }
    const endsAt = Math.floor(Date.now() / 1000) + duration
    let created
    try {
      created = await createGiveaway(guildId, {
        channel_id: b.channel_id,
        prize: b.prize,
        winners_count: b.winners_count,
        ends_at: endsAt,
        host_id: req.user.id,
        description: b.description,
        required_role_ids: b.required_role_ids,
        min_account_age_days: b.min_account_age_days,
        min_member_days: b.min_member_days,
        min_level: b.min_level
      })
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'GIVEAWAY_CREATE', { id: created.id, prize: created.prize })
    res.json({ success: true, giveaway: created })
  } catch (error) {
    console.error('Create giveaway error:', error.message)
    res.status(500).json({ error: 'Failed to create giveaway' })
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
