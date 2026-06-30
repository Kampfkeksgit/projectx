import express from 'express'
import {
  getMusicSettings, upsertMusicSettings,
  getMusicState, enqueueMusicCommand,
  logAuditAction, MUSIC_COMMAND_ACTIONS
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

// ----- Settings -----
router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getMusicSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get music settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch music settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const settings = await upsertMusicSettings(guildId, req.body || {})
    await logAuditAction(req.user.id, guildId, 'UPDATE_MUSIC_SETTINGS', req.body || {})
    res.json({ success: true, message: 'Music settings updated', settings })
  } catch (error) {
    console.error('Update music settings error:', error.message)
    res.status(500).json({ error: 'Failed to update music settings' })
  }
})

// ----- Live state (read-only snapshot the bot pushes) -----
router.get('/state', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const state = await getMusicState(req.params.guild_id)
    res.json({ success: true, state })
  } catch (error) {
    console.error('Get music state error:', error.message)
    res.status(500).json({ error: 'Failed to fetch music state' })
  }
})

// ----- Control: queue a command the bot will execute -----
router.post('/control', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const { action, payload } = req.body || {}
    if (!MUSIC_COMMAND_ACTIONS.includes(action)) {
      return res.status(400).json({ error: 'invalid_action', actions: MUSIC_COMMAND_ACTIONS })
    }
    const cmd = await enqueueMusicCommand(req.params.guild_id, action, payload)
    res.json({ success: true, command: cmd })
  } catch (error) {
    if (error && error.code === 'VALIDATION') return res.status(400).json({ error: error.message })
    console.error('Music control error:', error.message)
    res.status(500).json({ error: 'Failed to queue music command' })
  }
})

export default router
