import express from 'express'
import { getPublicStats } from '../state/botStats.js'
import { PLAN_CATALOG } from '../db.js'

const router = express.Router()

/**
 * Public stats — no auth. Used by the landing page.
 *
 *   GET /api/public/stats
 *   Returns: { servers, users, uptime_seconds, online }
 *
 * Numbers come from an in-memory cache populated by the bot via
 * PUT /api/bot/stats (called every 5min from bot/cogs/presence.py).
 * If the bot hasn't pinged in > 15min, the values are zeroed and `online: false`.
 */
router.get('/stats', (req, res) => {
  res.set('Cache-Control', 'public, max-age=30')
  res.json(getPublicStats())
})

/**
 * Public plan/pricing catalog — no auth. Drives the landing page pricing section
 * and the module tier badges so they stay in sync with MODULE_TIERS in db.js.
 *
 *   GET /api/public/plans
 *   Returns: { currency, tiers: [{ key, price_monthly }], modules: [{ key, tier }] }
 */
router.get('/plans', (req, res) => {
  res.set('Cache-Control', 'public, max-age=300')
  res.json(PLAN_CATALOG)
})

export default router
