import { reactive, ref } from 'vue'
import api from '../services/api.js'

/**
 * Per-guild cache for Discord channels and roles.
 *
 * The store is a singleton keyed by guildId: calling useGuildResources('g1')
 * twice returns the same reactive object, so two selectors on the same page
 * (e.g. ChannelSelector + RoleSelector) share one network request.
 *
 * Behaviour:
 *  - loadChannels / loadRoles are idempotent. Calling them a second time while
 *    fresh data is already in cache is a no-op.
 *  - Stale-while-revalidate: if the cached data is older than STALE_MS, the
 *    next call returns the cached array immediately AND kicks off a
 *    background refetch.
 *  - Pass `force: true` to bypass the cache (used by the "Refresh" button).
 */

const STALE_MS = 5 * 60 * 1000 // 5 minutes
const cacheMap = new Map()

function createStore(guildId) {
  const state = reactive({
    guildId,
    channels: ref([]),
    roles: ref([]),
    channelsLoading: ref(false),
    rolesLoading: ref(false),
    channelsError: ref(null),
    rolesError: ref(null),
    channelsFetchedAt: 0,
    rolesFetchedAt: 0
  })

  // We track in-flight promises so concurrent callers reuse the same request.
  let channelsInFlight = null
  let rolesInFlight = null

  async function fetchChannels() {
    state.channelsLoading = true
    state.channelsError = null
    try {
      const { data } = await api.get(`/guilds/${guildId}/channels`)
      if (data?.success) {
        state.channels = Array.isArray(data.channels) ? data.channels : []
      } else {
        state.channels = []
      }
      state.channelsFetchedAt = Date.now()
      return state.channels
    } catch (err) {
      state.channelsError = err
      // Don't clobber any data we already had on transient errors.
      if (!state.channelsFetchedAt) state.channels = []
      throw err
    } finally {
      state.channelsLoading = false
    }
  }

  async function fetchRoles() {
    state.rolesLoading = true
    state.rolesError = null
    try {
      const { data } = await api.get(`/guilds/${guildId}/roles`, {
        params: { include_default: 0, include_managed: 1 }
      })
      if (data?.success) {
        state.roles = Array.isArray(data.roles) ? data.roles : []
      } else {
        state.roles = []
      }
      state.rolesFetchedAt = Date.now()
      return state.roles
    } catch (err) {
      state.rolesError = err
      if (!state.rolesFetchedAt) state.roles = []
      throw err
    } finally {
      state.rolesLoading = false
    }
  }

  async function loadChannels(force = false) {
    if (!guildId) return []
    const age = Date.now() - state.channelsFetchedAt
    const isFresh = state.channelsFetchedAt > 0 && age < STALE_MS

    if (force) {
      if (!channelsInFlight) {
        channelsInFlight = fetchChannels().finally(() => { channelsInFlight = null })
      }
      return channelsInFlight
    }

    if (isFresh) return state.channels

    if (state.channelsFetchedAt > 0) {
      // Stale-while-revalidate: kick off a background refresh, return cache now.
      if (!channelsInFlight) {
        channelsInFlight = fetchChannels()
          .catch(() => { /* keep stale cache visible */ })
          .finally(() => { channelsInFlight = null })
      }
      return state.channels
    }

    // First fetch: actually wait.
    if (!channelsInFlight) {
      channelsInFlight = fetchChannels().finally(() => { channelsInFlight = null })
    }
    try {
      await channelsInFlight
    } catch {
      // surfaced via state.channelsError
    }
    return state.channels
  }

  async function loadRoles(force = false) {
    if (!guildId) return []
    const age = Date.now() - state.rolesFetchedAt
    const isFresh = state.rolesFetchedAt > 0 && age < STALE_MS

    if (force) {
      if (!rolesInFlight) {
        rolesInFlight = fetchRoles().finally(() => { rolesInFlight = null })
      }
      return rolesInFlight
    }

    if (isFresh) return state.roles

    if (state.rolesFetchedAt > 0) {
      if (!rolesInFlight) {
        rolesInFlight = fetchRoles()
          .catch(() => { /* keep stale cache visible */ })
          .finally(() => { rolesInFlight = null })
      }
      return state.roles
    }

    if (!rolesInFlight) {
      rolesInFlight = fetchRoles().finally(() => { rolesInFlight = null })
    }
    try {
      await rolesInFlight
    } catch {
      // surfaced via state.rolesError
    }
    return state.roles
  }

  return {
    state,
    loadChannels,
    loadRoles
  }
}

export function useGuildResources(guildId) {
  if (!guildId) {
    // Return an inert store for callers that haven't resolved a guildId yet.
    // We deliberately do NOT cache this so the real store is created later.
    return createStore('')
  }
  let store = cacheMap.get(guildId)
  if (!store) {
    store = createStore(guildId)
    cacheMap.set(guildId, store)
  }
  return store
}

export default useGuildResources
