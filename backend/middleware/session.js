import jwt from 'jsonwebtoken'
import crypto from 'crypto'
import { getUser, isUserBlocked } from '../db.js'

const COOKIE_NAME = 'projectx_session'
const SEVEN_DAYS_SECONDS = 60 * 60 * 24 * 7
const SEVEN_DAYS_MS = SEVEN_DAYS_SECONDS * 1000

function getSessionSecret() {
  const secret = process.env.SESSION_SECRET
  if (!secret) {
    // In production, this should never happen — server logs a loud warning at startup.
    throw new Error('SESSION_SECRET is not set')
  }
  return secret
}

function cookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: SEVEN_DAYS_MS
  }
}

/**
 * Parse the OWNER_DISCORD_ID env var into a Set of allowed owner IDs.
 * Supports a single ID or a comma-separated list.
 */
function getOwnerIds() {
  const raw = process.env.OWNER_DISCORD_ID || ''
  return new Set(
    raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  )
}

/**
 * True if the given Discord user ID is configured as a system owner.
 * The owner is exempt from user-blocking and is the only one allowed into
 * the /api/admin/* routes.
 */
export function isOwner(uid) {
  if (!uid) return false
  return getOwnerIds().has(String(uid))
}

/**
 * Sign a session JWT for the given Discord user ID.
 */
export function signSession(uid) {
  return jwt.sign({ uid: String(uid) }, getSessionSecret(), {
    expiresIn: SEVEN_DAYS_SECONDS
  })
}

/**
 * Set the HTTP-only session cookie on the response.
 */
export function setSessionCookie(res, uid) {
  const token = signSession(uid)
  res.cookie(COOKIE_NAME, token, cookieOptions())
  return token
}

/**
 * Clear the session cookie.
 */
export function clearSessionCookie(res) {
  const opts = cookieOptions()
  // Match attributes used to set the cookie; omit maxAge so the cookie expires immediately.
  res.clearCookie(COOKIE_NAME, {
    httpOnly: opts.httpOnly,
    secure: opts.secure,
    sameSite: opts.sameSite,
    path: opts.path
  })
}

/**
 * Express middleware: require a valid session cookie and attach req.user (from DB).
 */
export async function requireSession(req, res, next) {
  try {
    const token = req.cookies?.[COOKIE_NAME]
    if (!token) {
      return res.status(401).json({ error: 'Not authenticated' })
    }

    let payload
    try {
      payload = jwt.verify(token, getSessionSecret())
    } catch (err) {
      return res.status(401).json({ error: 'Not authenticated' })
    }

    const uid = payload?.uid
    if (!uid) {
      return res.status(401).json({ error: 'Not authenticated' })
    }

    const dbUser = await getUser(uid)
    if (!dbUser) {
      return res.status(401).json({ error: 'Not authenticated' })
    }

    const owner = isOwner(dbUser.discord_id)

    // Blocked users are locked out of every cookie-protected route. The owner
    // can never be blocked (defense-in-depth: setUserBlocked also refuses).
    if (dbUser.blocked && !owner) {
      return res.status(403).json({ error: 'Account is blocked', blocked: true })
    }

    req.user = {
      id: dbUser.discord_id,
      username: dbUser.username,
      email: dbUser.email,
      avatar_url: dbUser.avatar_url,
      is_owner: owner
    }
    next()
  } catch (error) {
    console.error('requireSession error:', error.message)
    return res.status(401).json({ error: 'Not authenticated' })
  }
}

/**
 * Express middleware: require the authenticated user to be a system owner.
 * Must run AFTER requireSession (which sets req.user.is_owner).
 */
export function requireOwner(req, res, next) {
  if (!req.user?.is_owner) {
    return res.status(403).json({ error: 'Owner access required' })
  }
  next()
}

/**
 * Express middleware: require the X-Bot-Token header to match BOT_API_KEY.
 * Uses constant-time comparison via crypto.timingSafeEqual.
 */
export function requireBotToken(req, res, next) {
  const expected = process.env.BOT_API_KEY
  if (!expected) {
    console.error('[bot-auth] BOT_API_KEY is not set; rejecting bot request')
    return res.status(500).json({ error: 'Bot auth not configured' })
  }

  const provided = req.headers['x-bot-token']
  if (typeof provided !== 'string' || provided.length === 0) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const a = Buffer.from(provided, 'utf8')
  const b = Buffer.from(expected, 'utf8')
  if (a.length !== b.length) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  let ok
  try {
    ok = crypto.timingSafeEqual(a, b)
  } catch {
    ok = false
  }

  if (!ok) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  next()
}

export const SESSION_COOKIE_NAME = COOKIE_NAME
