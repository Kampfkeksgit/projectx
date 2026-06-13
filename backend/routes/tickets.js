import express from 'express'
import {
  getTicketSettings, upsertTicketSettings, getGuildTickets,
  getTicketCategories, createTicketCategory, updateTicketCategory, deleteTicketCategory,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getTicketSettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get ticket settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch ticket settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertTicketSettings(guildId, req.body || {})
    const settings = await getTicketSettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_TICKET_SETTINGS', settings)
    res.json({ success: true, message: 'Ticket settings updated', settings })
  } catch (error) {
    console.error('Update ticket settings error:', error.message)
    res.status(500).json({ error: 'Failed to update ticket settings' })
  }
})

router.get('/list', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const tickets = await getGuildTickets(req.params.guild_id)
    res.json({ success: true, tickets })
  } catch (error) {
    console.error('Get tickets error:', error.message)
    res.status(500).json({ error: 'Failed to fetch tickets' })
  }
})

// ----- Ticket categories (ticket types) -----

router.get('/categories', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const categories = await getTicketCategories(req.params.guild_id)
    res.json({ success: true, categories })
  } catch (error) {
    console.error('Get ticket categories error:', error.message)
    res.status(500).json({ error: 'Failed to fetch ticket categories' })
  }
})

router.post('/categories', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const { id } = await createTicketCategory(guildId, req.body || {})
    const categories = await getTicketCategories(guildId)
    const category = categories.find((c) => c.id === id) || null
    await logAuditAction(req.user.id, guildId, 'TICKET_CATEGORY_CREATE', { id })
    res.json({ success: true, category })
  } catch (error) {
    console.error('Create ticket category error:', error.message)
    res.status(500).json({ error: 'Failed to create ticket category' })
  }
})

router.put('/categories/:cat_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await updateTicketCategory(guildId, req.params.cat_id, req.body || {})
    if (!changes) return res.status(404).json({ error: 'Category not found' })
    const categories = await getTicketCategories(guildId)
    const category = categories.find((c) => c.id === req.params.cat_id) || null
    await logAuditAction(req.user.id, guildId, 'TICKET_CATEGORY_UPDATE', { id: req.params.cat_id })
    res.json({ success: true, category })
  } catch (error) {
    console.error('Update ticket category error:', error.message)
    res.status(500).json({ error: 'Failed to update ticket category' })
  }
})

router.delete('/categories/:cat_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteTicketCategory(guildId, req.params.cat_id)
    if (!changes) return res.status(404).json({ error: 'Category not found' })
    await logAuditAction(req.user.id, guildId, 'TICKET_CATEGORY_DELETE', { id: req.params.cat_id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete ticket category error:', error.message)
    res.status(500).json({ error: 'Failed to delete ticket category' })
  }
})

export default router
