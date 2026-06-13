import { reactive } from 'vue'
import api from '../services/api.js'

/**
 * Auth state — plain reactive singleton.
 *
 * status:
 *   'unknown'        — initial, /auth/me request not finished
 *   'authenticating' — handling /auth/callback (OAuth code exchange)
 *   'authenticated'  — session cookie valid
 *   'guest'          — no session
 */
const state = reactive({
  user: null,
  status: 'unknown'
})

let mePromise = null

async function fetchMe(force = false) {
  if (mePromise && !force) return mePromise

  mePromise = (async () => {
    try {
      const { data } = await api.get('/auth/me')
      if (data?.authenticated && data.user) {
        state.user = data.user
        state.status = 'authenticated'
      } else {
        state.user = null
        state.status = 'guest'
      }
    } catch (err) {
      state.user = null
      state.status = 'guest'
    } finally {
      // allow subsequent refetches
      setTimeout(() => { mePromise = null }, 0)
    }
  })()

  return mePromise
}

function loginWithDiscord() {
  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID
  const redirectUri = import.meta.env.VITE_DISCORD_REDIRECT_URI
  const scope = ['identify', 'email', 'guilds'].join(' ')

  const params = new URLSearchParams({
    client_id: clientId || '',
    redirect_uri: redirectUri || '',
    response_type: 'code',
    scope,
    prompt: 'consent'
  })

  window.location.href = `https://discord.com/api/oauth2/authorize?${params.toString()}`
}

async function logout(router) {
  // Optimistic local clear
  state.user = null
  state.status = 'guest'
  try {
    await api.post('/auth/logout')
  } catch (e) {
    // even if logout fails server-side, local state is cleared
  }
  if (router) {
    router.push('/')
  } else if (window.location.pathname !== '/') {
    window.location.href = '/'
  }
}

// Global 401 listener — set state to guest immediately when API signals it.
if (typeof window !== 'undefined') {
  window.addEventListener('projectx:unauthorized', () => {
    state.user = null
    state.status = 'guest'
  })
}

async function waitUntilResolved() {
  if (state.status !== 'unknown') return
  // If a request is in flight, wait for it; otherwise kick one off.
  if (mePromise) {
    await mePromise
  } else {
    await fetchMe()
  }
}

export function useAuth() {
  return {
    state,
    fetchMe,
    loginWithDiscord,
    logout,
    waitUntilResolved
  }
}

export default useAuth
