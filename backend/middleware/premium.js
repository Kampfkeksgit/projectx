import { getGuild, effectiveTier, moduleUnlocked, MODULE_TIERS } from '../db.js'

/**
 * Gate a premium module's WRITE operations behind the guild's tier.
 *
 * Reads (GET/HEAD/OPTIONS) pass through so the dashboard can still render the
 * config page with a "Premium required" lock + upsell. Mutations (PUT/POST/
 * DELETE/PATCH) return 403 `premium_required` when the guild's effective tier
 * is below the module's required tier (single source: MODULE_TIERS in db.js).
 *
 * Mount BEFORE the module's router, e.g.:
 *   app.use('/api/guilds/:guild_id/social', requirePremiumModule('social'), socialRoutes)
 */
export function requirePremiumModule(moduleKey) {
  return async (req, res, next) => {
    if (req.method === 'GET' || req.method === 'HEAD' || req.method === 'OPTIONS') return next()
    try {
      const guild = await getGuild(req.params.guild_id)
      const tier = effectiveTier(guild)
      if (moduleUnlocked(tier, moduleKey)) return next()
      return res.status(403).json({
        error: 'premium_required',
        module: moduleKey,
        required_tier: MODULE_TIERS[moduleKey] || 'free',
        current_tier: tier
      })
    } catch (err) {
      console.error('Premium gate error:', err.message)
      return res.status(500).json({ error: 'Premium check failed' })
    }
  }
}

export default requirePremiumModule
