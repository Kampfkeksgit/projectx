import express from 'express'
import {
  getEconomySettings,
  upsertEconomySettings,
  getEconomyShop,
  createShopItem,
  updateShopItem,
  deleteShopItem,
  getEconomyLeaderboard,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

// ----- Settings -----
router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const settings = await getEconomySettings(req.params.guild_id)
    res.json({ success: true, settings })
  } catch (error) {
    console.error('Get economy settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch economy settings' })
  }
})

router.put('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    await upsertEconomySettings(guildId, req.body || {})
    const settings = await getEconomySettings(guildId)
    await logAuditAction(req.user.id, guildId, 'UPDATE_ECONOMY_SETTINGS', settings)
    res.json({ success: true, message: 'Economy settings updated', settings })
  } catch (error) {
    console.error('Update economy settings error:', error.message)
    res.status(500).json({ error: 'Failed to update economy settings' })
  }
})

// ----- Shop -----
router.get('/shop', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const items = await getEconomyShop(req.params.guild_id)
    res.json({ success: true, items })
  } catch (error) {
    console.error('Get economy shop error:', error.message)
    res.status(500).json({ error: 'Failed to fetch shop' })
  }
})

router.post('/shop', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const item = await createShopItem(guildId, req.body || {})
    await logAuditAction(req.user.id, guildId, 'ECONOMY_SHOP_CREATE', { id: item.id, name: item.name })
    res.json({ success: true, item })
  } catch (error) {
    console.error('Create shop item error:', error.message)
    res.status(500).json({ error: 'Failed to create shop item' })
  }
})

router.put('/shop/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let item
    try {
      item = await updateShopItem(guildId, req.params.id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'Item not found' })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'ECONOMY_SHOP_UPDATE', { id: item.id })
    res.json({ success: true, item })
  } catch (error) {
    console.error('Update shop item error:', error.message)
    res.status(500).json({ error: 'Failed to update shop item' })
  }
})

router.delete('/shop/:id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteShopItem(guildId, req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Item not found' })
    await logAuditAction(req.user.id, guildId, 'ECONOMY_SHOP_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete shop item error:', error.message)
    res.status(500).json({ error: 'Failed to delete shop item' })
  }
})

// ----- Leaderboard (read-only) -----
router.get('/leaderboard', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const leaderboard = await getEconomyLeaderboard(req.params.guild_id, Number(req.query.limit) || 25)
    res.json({ success: true, leaderboard })
  } catch (error) {
    console.error('Get economy leaderboard error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
})

export default router
