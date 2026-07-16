import express from 'express'
import { getBotProfile, upsertBotProfile, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getBotProfile(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get bot profile error:', error.message)
    res.status(500).json({ error: 'Failed to fetch bot profile' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const settings = await upsertBotProfile(guildId, req.body || {})
    await logAuditAction(req.user.id, guildId, 'UPDATE_BOT_PROFILE', {
      nickname: settings.nickname, avatar_url: settings.avatar_url
    })
    res.json({ success: true, message: 'Bot profile updated', settings })
  } catch (error) {
    console.error('Update bot profile error:', error.message)
    res.status(500).json({ error: 'Failed to update bot profile' })
  }
})

export default router
