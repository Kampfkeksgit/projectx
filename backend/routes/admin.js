import express from 'express'
import {
  getAdminUsers,
  setUserBlocked,
  getAdminGuilds,
  setGuildBlocked,
  setGuildPremium,
  PREMIUM_TIERS,
  getUser,
  getGuild,
  logAuditAction
} from '../db.js'
import { requireSession, requireOwner, isOwner } from '../middleware/session.js'

const router = express.Router()

// Every route in this file is owner-only.
router.use(requireSession, requireOwner)

/**
 * GET /api/admin/users?search=&limit=&offset=
 * Owner-only paginated user list with block status.
 */
router.get('/users', async (req, res) => {
  try {
    const { search = '', limit = 50, offset = 0 } = req.query
    const result = await getAdminUsers({ search, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin list users error:', error.message)
    res.status(500).json({ error: 'Failed to list users' })
  }
})

/**
 * POST /api/admin/users/:user_id/block  Body: { blocked: bool, reason?: string }
 * Block or unblock a Discord user. The owner can never be blocked.
 */
router.post('/users/:user_id/block', async (req, res) => {
  try {
    const userId = req.params.user_id
    const blocked = !!req.body?.blocked
    const reason = req.body?.reason

    if (blocked && isOwner(userId)) {
      return res.status(400).json({ error: 'The system owner cannot be blocked' })
    }

    const existing = await getUser(userId)
    if (!existing) {
      return res.status(404).json({ error: 'User not found' })
    }

    await setUserBlocked(userId, blocked, reason)
    await logAuditAction(req.user.id, null, blocked ? 'ADMIN_BLOCK_USER' : 'ADMIN_UNBLOCK_USER', {
      target_user_id: userId,
      reason: blocked ? (reason || null) : null
    })

    res.json({ success: true, user_id: userId, blocked })
  } catch (error) {
    console.error('Admin block user error:', error.message)
    res.status(500).json({ error: 'Failed to update user' })
  }
})

/**
 * GET /api/admin/guilds?search=&limit=&offset=
 * Owner-only guild list with block status + bot presence.
 */
router.get('/guilds', async (req, res) => {
  try {
    const { search = '', limit = 100, offset = 0 } = req.query
    const result = await getAdminGuilds({ search, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin list guilds error:', error.message)
    res.status(500).json({ error: 'Failed to list guilds' })
  }
})

/**
 * POST /api/admin/guilds/:guild_id/block  Body: { blocked: bool, reason?: string }
 * Block or unblock a guild. A blocked guild leaves the server picker, its
 * dashboard routes return 403, and the bot's per-guild endpoints stop serving it.
 */
router.post('/guilds/:guild_id/block', async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const blocked = !!req.body?.blocked
    const reason = req.body?.reason

    const existing = await getGuild(guildId)
    if (!existing) {
      return res.status(404).json({ error: 'Guild not found' })
    }

    await setGuildBlocked(guildId, blocked, reason)
    await logAuditAction(req.user.id, guildId, blocked ? 'ADMIN_BLOCK_GUILD' : 'ADMIN_UNBLOCK_GUILD', {
      reason: blocked ? (reason || null) : null
    })

    res.json({ success: true, guild_id: guildId, blocked })
  } catch (error) {
    console.error('Admin block guild error:', error.message)
    res.status(500).json({ error: 'Failed to update guild' })
  }
})

/**
 * POST /api/admin/guilds/:guild_id/premium  Body: { tier, until?: unix-seconds }
 * Owner-only manual premium override (source = 'manual'). `tier` ∈ free|basic|pro.
 * Setting 'free' clears the premium entirely.
 */
router.post('/guilds/:guild_id/premium', async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const tier = req.body?.tier
    const until = req.body?.until ?? null

    if (!PREMIUM_TIERS.includes(tier)) {
      return res.status(400).json({ error: 'tier must be one of: ' + PREMIUM_TIERS.join(', ') })
    }

    const existing = await getGuild(guildId)
    if (!existing) {
      return res.status(404).json({ error: 'Guild not found' })
    }

    await setGuildPremium(guildId, { tier, source: 'manual', until })
    await logAuditAction(req.user.id, guildId, 'ADMIN_SET_PREMIUM', { tier, until: until || null })

    res.json({ success: true, guild_id: guildId, tier, until: tier === 'free' ? null : (until || null) })
  } catch (error) {
    console.error('Admin set premium error:', error.message)
    res.status(500).json({ error: 'Failed to update premium' })
  }
})

export default router
