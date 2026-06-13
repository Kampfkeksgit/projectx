import axios from 'axios'

const configuredBackendUrl = (import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000').replace(/\/+$/, '')
const API_BASE_URL = configuredBackendUrl.endsWith('/api')
  ? configuredBackendUrl
  : `${configuredBackendUrl}/api`

const api = axios.create({
  baseURL: API_BASE_URL,
  // OAuth-Callback ist die einzige langsame Route (Discord Token-Exchange
  // + /users/@me + /users/@me/guilds + DB-Reconcile in einer Transaktion).
  // Bei Usern mit vielen Guilds kann das auf langsamen Verbindungen >15s dauern.
  timeout: 45000,
  withCredentials: true
})

// On 401: clear auth state and bounce to landing.
// Avoid bouncing the 401 from /auth/me itself (that's expected for guests).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const url = error?.config?.url || ''

    if (status === 401 && !url.includes('/auth/me') && !url.includes('/auth/callback')) {
      // Notify listeners (auth store registers one) without an import cycle
      try {
        window.dispatchEvent(new CustomEvent('projectx:unauthorized'))
      } catch (e) {
        // ignore
      }
      if (window.location.pathname !== '/') {
        window.location.href = '/'
      }
    }
    return Promise.reject(error)
  }
)

export default api
export { API_BASE_URL }
