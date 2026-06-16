import express from 'express'
import {
  getApplicationForms,
  createApplicationForm,
  updateApplicationForm,
  deleteApplicationForm,
  getApplications,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

// ----- Forms -----
router.get('/forms', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const forms = await getApplicationForms(req.params.guild_id)
    res.json({ success: true, forms })
  } catch (error) {
    console.error('Get application forms error:', error.message)
    res.status(500).json({ error: 'Failed to fetch application forms' })
  }
})

router.post('/forms', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const form = await createApplicationForm(guildId, req.body || {})
    await logAuditAction(req.user.id, guildId, 'APPLICATION_FORM_CREATE', { id: form.id, name: form.name })
    res.json({ success: true, form })
  } catch (error) {
    console.error('Create application form error:', error.message)
    res.status(500).json({ error: 'Failed to create application form' })
  }
})

router.put('/forms/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let form
    try {
      form = await updateApplicationForm(guildId, req.params.id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'Form not found' })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'APPLICATION_FORM_UPDATE', { id: form.id })
    res.json({ success: true, form })
  } catch (error) {
    console.error('Update application form error:', error.message)
    res.status(500).json({ error: 'Failed to update application form' })
  }
})

router.delete('/forms/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteApplicationForm(guildId, req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Form not found' })
    await logAuditAction(req.user.id, guildId, 'APPLICATION_FORM_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete application form error:', error.message)
    res.status(500).json({ error: 'Failed to delete application form' })
  }
})

// ----- Submissions (read-only) -----
router.get('/submissions', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const status = ['pending', 'accepted', 'denied'].includes(req.query.status) ? req.query.status : undefined
    const submissions = await getApplications(req.params.guild_id, { status })
    res.json({ success: true, submissions })
  } catch (error) {
    console.error('Get application submissions error:', error.message)
    res.status(500).json({ error: 'Failed to fetch submissions' })
  }
})

export default router
