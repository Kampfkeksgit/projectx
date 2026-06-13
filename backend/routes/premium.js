import express from 'express'
import { getGuild, effectiveTier, moduleUnlockMap, MODULE_TIERS } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

/**
 * GET /api/guilds/:guild_id/premium
 * The guild's current tier + a moduleKey→unlocked map for the dashboard to
 * render locks. Cookie-protected (owner/admin via requireGuildAccess).
 */
router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guild = await getGuild(req.params.guild_id)
    const tier = effectiveTier(guild)
    res.json({
      success: true,
      tier,
      source: guild?.premium_source || null,
      until: guild?.premium_until || null,
      module_tiers: MODULE_TIERS,
      modules: moduleUnlockMap(tier)
    })
  } catch (error) {
    console.error('Get premium error:', error.message)
    res.status(500).json({ error: 'Failed to fetch premium status' })
  }
})

export default router
