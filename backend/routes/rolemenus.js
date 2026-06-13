import express from 'express'
import {
  ROLE_MENU_TYPES,
  getRoleMenus,
  createRoleMenu,
  updateRoleMenu,
  deleteRoleMenu,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const menus = await getRoleMenus(req.params.guild_id)
    res.json({ success: true, menus })
  } catch (error) {
    console.error('Get role menus error:', error.message)
    res.status(500).json({ error: 'Failed to fetch role menus' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}
    if (body.menu_type !== undefined && !ROLE_MENU_TYPES.includes(body.menu_type)) {
      return res.status(400).json({ error: 'menu_type must be one of: ' + ROLE_MENU_TYPES.join(', ') })
    }
    const menu = await createRoleMenu(guildId, body)
    await logAuditAction(req.user.id, guildId, 'ROLEMENU_CREATE', { id: menu.id })
    res.json({ success: true, menu })
  } catch (error) {
    console.error('Create role menu error:', error.message)
    res.status(500).json({ error: 'Failed to create role menu' })
  }
})

router.put('/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}
    if (body.menu_type !== undefined && !ROLE_MENU_TYPES.includes(body.menu_type)) {
      return res.status(400).json({ error: 'menu_type must be one of: ' + ROLE_MENU_TYPES.join(', ') })
    }
    let menu
    try {
      menu = await updateRoleMenu(guildId, req.params.id, body)
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'Role menu not found' })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'ROLEMENU_UPDATE', { id: menu.id })
    res.json({ success: true, menu })
  } catch (error) {
    console.error('Update role menu error:', error.message)
    res.status(500).json({ error: 'Failed to update role menu' })
  }
})

router.delete('/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteRoleMenu(guildId, req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Role menu not found' })
    await logAuditAction(req.user.id, guildId, 'ROLEMENU_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete role menu error:', error.message)
    res.status(500).json({ error: 'Failed to delete role menu' })
  }
})

export default router
