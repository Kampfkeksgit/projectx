import { reactive } from 'vue'
import api from '../services/api.js'

/**
 * Per-guild premium state (singleton). Loaded once per guild by DashboardLayout
 * and read by the Sidebar, Overview cards and each premium module page to render
 * locks/upsell. The backend remains the source of truth for enforcement.
 */
const cache = reactive({
  guildId: null,
  tier: 'free',
  source: null,
  until: null,
  modules: {},       // moduleKey → bool (unlocked)
  moduleTiers: {},   // moduleKey → required tier
  loading: false,
  loaded: false
})

export const TIER_RANK = { free: 0, basic: 1, pro: 2 }

async function load(guildId, { force = false } = {}) {
  if (!guildId) return cache
  if (!force && cache.guildId === guildId && cache.loaded) return cache
  if (cache.guildId !== guildId) {
    // switching guilds — reset to safe defaults until the new data lands
    cache.tier = 'free'
    cache.source = null
    cache.until = null
    cache.modules = {}
    cache.moduleTiers = {}
    cache.loaded = false
  }
  cache.guildId = guildId
  cache.loading = true
  try {
    const { data } = await api.get(`/guilds/${guildId}/premium`)
    if (data?.success) {
      cache.tier = data.tier || 'free'
      cache.source = data.source || null
      cache.until = data.until || null
      cache.modules = data.modules || {}
      cache.moduleTiers = data.module_tiers || {}
      cache.loaded = true
    }
  } catch {
    // Leave defaults; unknown modules are treated as unlocked so the UI never
    // hard-locks a page just because this request failed.
  } finally {
    cache.loading = false
  }
  return cache
}

/** Is a module (dashboard route segment) unlocked for the current guild tier? */
function isUnlocked(moduleKey) {
  if (!cache.loaded) return true            // optimistic until loaded
  if (!(moduleKey in cache.modules)) return true  // unknown = free
  return !!cache.modules[moduleKey]
}

/** Required tier for a module ('free' | 'basic' | 'pro'). */
function tierOf(moduleKey) {
  return cache.moduleTiers[moduleKey] || 'free'
}

export function usePremium() {
  return { cache, load, isUnlocked, tierOf }
}

export default usePremium
