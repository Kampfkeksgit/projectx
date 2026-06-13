import express from 'express'
import {
  STATS_COUNTER_TYPES,
  getStatsSettings,
  upsertStatsSettings,
  getStatsCounters,
  createStatsCounter,
  updateStatsCounter,
  deleteStatsCounter,
  getStatsSnapshots,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

// GET /api/guilds/:id/stats → settings + counters
router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const [settings, counters] = await Promise.all([
      getStatsSettings(guildId),
      getStatsCounters(guildId)
    ])
    res.json({ success: true, settings, counters })
  } catch (error) {
    console.error('Get stats error:', error.message)
    res.status(500).json({ error: 'Failed to fetch stats settings' })
  }
})

// PUT /api/guilds/:id/stats → update module settings (enabled + interval)
router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertStatsSettings(guildId, req.body || {})
    const settings = await getStatsSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_STATS_SETTINGS', settings)
    res.json({ success: true, message: 'Stats settings updated', settings })
  } catch (error) {
    console.error('Update stats settings error:', error.message)
    res.status(500).json({ error: 'Failed to update stats settings' })
  }
})

// POST /api/guilds/:id/stats/counters → create a counter
router.post('/counters', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}
    if (body.type !== undefined && !STATS_COUNTER_TYPES.includes(body.type)) {
      return res.status(400).json({ error: 'type must be one of: ' + STATS_COUNTER_TYPES.join(', ') })
    }
    let counter
    try {
      counter = await createStatsCounter(guildId, body)
    } catch (err) {
      if (err && err.code === 'VALIDATION') {
        return res.status(400).json({ error: err.message })
      }
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'STATS_COUNTER_CREATE', {
      id: counter.id, type: counter.type, channel_id: counter.channel_id
    })
    res.json({ success: true, counter })
  } catch (error) {
    console.error('Create stats counter error:', error.message)
    res.status(500).json({ error: 'Failed to create stats counter' })
  }
})

// PUT /api/guilds/:id/stats/counters/:cid → update a counter
router.put('/counters/:cid', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const counterId = req.params.cid
    const body = req.body || {}
    if (body.type !== undefined && !STATS_COUNTER_TYPES.includes(body.type)) {
      return res.status(400).json({ error: 'type must be one of: ' + STATS_COUNTER_TYPES.join(', ') })
    }
    let counter
    try {
      counter = await updateStatsCounter(guildId, counterId, body)
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') {
        return res.status(404).json({ error: 'Stats counter not found' })
      }
      if (err && err.code === 'VALIDATION') {
        return res.status(400).json({ error: err.message })
      }
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'STATS_COUNTER_UPDATE', {
      id: counter.id, type: counter.type, enabled: counter.enabled
    })
    res.json({ success: true, counter })
  } catch (error) {
    console.error('Update stats counter error:', error.message)
    res.status(500).json({ error: 'Failed to update stats counter' })
  }
})

// DELETE /api/guilds/:id/stats/counters/:cid → delete a counter
router.delete('/counters/:cid', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const counterId = req.params.cid
    const changes = await deleteStatsCounter(guildId, counterId)
    if (changes === 0) {
      return res.status(404).json({ error: 'Stats counter not found' })
    }
    await logAuditAction(req.user.id, guildId, 'STATS_COUNTER_DELETE', { id: counterId })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete stats counter error:', error.message)
    res.status(500).json({ error: 'Failed to delete stats counter' })
  }
})

// GET /api/guilds/:id/stats/history?days=7 → snapshots for the graphs
router.get('/history', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let days = parseInt(req.query.days, 10)
    if (!Number.isFinite(days)) days = 7
    if (days < 1) days = 1
    if (days > 90) days = 90
    const sinceTs = Math.floor(Date.now() / 1000) - days * 86400
    const snapshots = await getStatsSnapshots(guildId, sinceTs)
    res.json({ success: true, snapshots, days })
  } catch (error) {
    console.error('Get stats history error:', error.message)
    res.status(500).json({ error: 'Failed to fetch stats history' })
  }
})

export default router
