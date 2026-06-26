import express from 'express'
import { getGuild, effectiveTier, moduleUnlockMap, MODULE_TIERS, redeemPremiumCode, logAuditAction } from '../db.js'
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

/**
 * POST /api/guilds/:guild_id/premium/redeem  Body: { code }
 * Redeem a promo/trial code → time-limited premium for this guild.
 * 400 { error: 'invalid_code', reason } on a bad/expired/exhausted code.
 */
router.post('/redeem', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const code = typeof req.body?.code === 'string' ? req.body.code : ''
    const result = await redeemPremiumCode(code, guildId)
    await logAuditAction(req.user.id, guildId, 'PREMIUM_CODE_REDEEM', { tier: result.tier, until: result.until })
    res.json({ success: true, ...result })
  } catch (error) {
    if (error.code === 'REDEEM') {
      return res.status(400).json({ error: 'invalid_code', reason: error.reason })
    }
    console.error('Redeem premium code error:', error.message)
    res.status(500).json({ error: 'Failed to redeem code' })
  }
})

export default router
