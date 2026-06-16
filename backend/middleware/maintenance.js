import jwt from 'jsonwebtoken'
import { getMaintenanceState } from '../db.js'
import { isOwner, SESSION_COOKIE_NAME } from './session.js'

/**
 * Global maintenance gate. When the owner enables maintenance mode, all
 * dashboard WRITE requests (POST/PUT/PATCH/DELETE) are rejected with 503 —
 * except the system owner, who stays able to work. Reads (GET) always pass so
 * the dashboard can still render (with a banner) and the owner can investigate.
 *
 * Mount this BEFORE the cookie-protected guild routers. It decodes the session
 * JWT itself (no DB user lookup) purely to grant the owner an exemption.
 */

const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

// Tiny cache so we don't hit the DB on every write request. Maintenance toggles
// are rare; a few seconds of staleness is fine.
let cache = { value: null, at: 0 }
const TTL_MS = 5000

async function readState() {
  const now = Date.now()
  if (cache.value && now - cache.at < TTL_MS) return cache.value
  const value = await getMaintenanceState()
  cache = { value, at: now }
  return value
}

function requesterIsOwner(req) {
  try {
    const token = req.cookies?.[SESSION_COOKIE_NAME]
    if (!token) return false
    const payload = jwt.verify(token, process.env.SESSION_SECRET)
    return isOwner(payload?.uid)
  } catch {
    return false
  }
}

export async function maintenanceGate(req, res, next) {
  if (!WRITE_METHODS.has(req.method)) return next()
  try {
    const state = await readState()
    if (!state.enabled) return next()
    if (requesterIsOwner(req)) return next()
    return res.status(503).json({ error: 'maintenance', message: state.message || '' })
  } catch {
    // Fail open — never let a maintenance-check error take down writes.
    return next()
  }
}
