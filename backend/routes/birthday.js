import express from 'express'
import {
  getBirthdaySettings,
  upsertBirthdaySettings,
  getGuildBirthdays,
  removeBirthday,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getBirthdaySettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get birthday settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch birthday settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertBirthdaySettings(guildId, req.body || {})
    const settings = await getBirthdaySettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_BIRTHDAY_SETTINGS', settings)
    res.json({ success: true, message: 'Birthday settings updated', settings })
  } catch (error) {
    console.error('Update birthday settings error:', error.message)
    res.status(500).json({ error: 'Failed to update birthday settings' })
  }
})

router.get('/list', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const birthdays = await getGuildBirthdays(req.params.guild_id)
    res.json({ success: true, birthdays })
  } catch (error) {
    console.error('Get birthdays error:', error.message)
    res.status(500).json({ error: 'Failed to fetch birthdays' })
  }
})

router.delete('/list/:user_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await removeBirthday(guildId, req.params.user_id)
    if (changes === 0) return res.status(404).json({ error: 'Birthday not found' })
    await logAuditAction(req.user.id, guildId, 'BIRTHDAY_DELETE', { user_id: req.params.user_id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete birthday error:', error.message)
    res.status(500).json({ error: 'Failed to delete birthday' })
  }
})

export default router
