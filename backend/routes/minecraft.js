import express from 'express'
import {
  getMinecraftServers,
  createMinecraftServer,
  updateMinecraftServer,
  deleteMinecraftServer,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const servers = await getMinecraftServers(req.params.guild_id)
    res.json({ success: true, servers })
  } catch (error) {
    console.error('Get minecraft servers error:', error.message)
    res.status(500).json({ error: 'Failed to fetch minecraft servers' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let server
    try {
      server = await createMinecraftServer(guildId, req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'MINECRAFT_CREATE', {
      id: server.id, address: server.address, edition: server.edition, channel_id: server.channel_id
    })
    res.json({ success: true, server })
  } catch (error) {
    console.error('Create minecraft server error:', error.message)
    res.status(500).json({ error: 'Failed to create minecraft server' })
  }
})

router.put('/:server_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let server
    try {
      server = await updateMinecraftServer(guildId, req.params.server_id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'Minecraft server not found' })
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'MINECRAFT_UPDATE', {
      id: server.id, address: server.address, enabled: server.enabled
    })
    res.json({ success: true, server })
  } catch (error) {
    console.error('Update minecraft server error:', error.message)
    res.status(500).json({ error: 'Failed to update minecraft server' })
  }
})

router.delete('/:server_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteMinecraftServer(guildId, req.params.server_id)
    if (changes === 0) return res.status(404).json({ error: 'Minecraft server not found' })
    await logAuditAction(req.user.id, guildId, 'MINECRAFT_DELETE', { id: req.params.server_id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete minecraft server error:', error.message)
    res.status(500).json({ error: 'Failed to delete minecraft server' })
  }
})

export default router
