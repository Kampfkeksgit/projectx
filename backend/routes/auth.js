import express from 'express'
import axios from 'axios'
import {
  upsertUser,
  addUserToGuild,
  getGuild,
  createGuild,
  getUser,
  updateUserTokens,
  removeUserGuildsNotIn,
  runInTransaction
} from '../db.js'
import {
  setSessionCookie,
  clearSessionCookie,
  requireSession,
  isOwner
} from '../middleware/session.js'

const router = express.Router()
const DISCORD_API = 'https://discord.com/api/v10'

/**
 * Compute the unix-seconds expiry from a Discord `expires_in` value.
 */
function expiresAt(expiresInSeconds) {
  if (typeof expiresInSeconds !== 'number' || !Number.isFinite(expiresInSeconds)) return null
  return Math.floor(Date.now() / 1000) + expiresInSeconds
}

/**
 * Compute avatar URL for a Discord user object.
 */
function avatarUrlFor(user) {
  return user.avatar
    ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png`
    : null
}

/**
 * Compute admin flag from Discord guild permissions string.
 * Discord returns `permissions` as a string. ADMINISTRATOR bit = 0x8.
 */
function isAdminFromPermissions(permissions) {
  try {
    return (BigInt(permissions || '0') & 0x8n) !== 0n
  } catch {
    return false
  }
}

/**
 * Reconcile guilds for the user against the freshly fetched Discord list.
 * - Ensures the guilds row exists for each.
 * - Upserts user_guilds row with owner/admin flags.
 * - Removes user_guilds rows for guilds the user is no longer in.
 */
async function reconcileUserGuilds(userId, guilds) {
  // One transaction for the entire reconcile — turns N×fsync into 1×fsync,
  // which keeps OAuth callback fast for users in many guilds.
  await runInTransaction(async () => {
    const fetchedIds = []
    for (const guild of guilds) {
      const existing = await getGuild(guild.id)
      if (!existing) {
        const guildIconUrl = guild.icon
          ? `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`
          : null
        await createGuild(guild.id, guild.name, guildIconUrl)
      }
      const admin = isAdminFromPermissions(guild.permissions)
      await addUserToGuild(userId, guild.id, !!guild.owner, admin)
      fetchedIds.push(guild.id)
    }
    await removeUserGuildsNotIn(userId, fetchedIds)
  })
}

/**
 * Refresh Discord tokens for a stored user, updating the DB.
 * Throws if refresh fails (caller should clear session and respond 401).
 */
async function refreshDiscordTokens(userId) {
  const dbUser = await getUser(userId)
  if (!dbUser || !dbUser.refresh_token) {
    throw new Error('No refresh token on file')
  }

  const tokenResponse = await axios.post(
    `${DISCORD_API}/oauth2/token`,
    new URLSearchParams({
      client_id: process.env.DISCORD_CLIENT_ID,
      client_secret: process.env.DISCORD_CLIENT_SECRET,
      grant_type: 'refresh_token',
      refresh_token: dbUser.refresh_token
    }),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  )

  const { access_token, refresh_token, expires_in } = tokenResponse.data
  const newRefresh = refresh_token || dbUser.refresh_token
  const tokenExpiresAt = expiresAt(expires_in)

  await updateUserTokens(userId, access_token, newRefresh, tokenExpiresAt)
  return { access_token, refresh_token: newRefresh, token_expires_at: tokenExpiresAt }
}

/**
 * OAuth callback endpoint
 * POST /api/auth/callback  Body: { code }
 *
 * Exchanges authorization code for Discord tokens, syncs user + guilds,
 * issues an HTTP-only session cookie, and returns a sanitized user payload.
 */
router.post('/callback', async (req, res) => {
  const t0 = Date.now()
  const mark = (label) => console.log(`[auth/callback] ${label} +${Date.now() - t0}ms`)
  try {
    const { code } = req.body

    if (!code) {
      return res.status(400).json({ error: 'No authorization code provided' })
    }

    // 1. Exchange OAuth code for tokens
    const tokenResponse = await axios.post(
      `${DISCORD_API}/oauth2/token`,
      new URLSearchParams({
        client_id: process.env.DISCORD_CLIENT_ID,
        client_secret: process.env.DISCORD_CLIENT_SECRET,
        grant_type: 'authorization_code',
        code,
        redirect_uri: process.env.DISCORD_REDIRECT_URI
      }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    )

    const { access_token, refresh_token, expires_in } = tokenResponse.data
    const tokenExpiresAt = expiresAt(expires_in)
    mark('token exchange done')

    // 2. Fetch user + guilds
    const [userResponse, guildsResponse] = await Promise.all([
      axios.get(`${DISCORD_API}/users/@me`, {
        headers: { Authorization: `Bearer ${access_token}` }
      }),
      axios.get(`${DISCORD_API}/users/@me/guilds`, {
        headers: { Authorization: `Bearer ${access_token}` }
      })
    ])

    const user = userResponse.data
    const guilds = guildsResponse.data
    const avatarUrl = avatarUrlFor(user)
    mark(`fetched user + ${guilds.length} guilds`)

    // 3. Upsert user (persists token_expires_at)
    await upsertUser(user.id, {
      username: user.username,
      email: user.email,
      avatar_url: avatarUrl,
      access_token,
      refresh_token,
      token_expires_at: tokenExpiresAt
    })
    mark('user upserted')

    // 4-5. Reconcile guild membership
    await reconcileUserGuilds(user.id, guilds)
    mark('reconcile done')

    // 5b. Refuse login for blocked users (owner is always exempt).
    const owner = isOwner(user.id)
    const stored = await getUser(user.id)
    if (stored?.blocked && !owner) {
      clearSessionCookie(res)
      return res.status(403).json({ error: 'Account is blocked', blocked: true })
    }

    // 6. Issue session cookie
    setSessionCookie(res, user.id)

    // 7. Sanitized response (no tokens)
    return res.json({
      success: true,
      user: {
        id: user.id,
        username: user.username,
        avatar_url: avatarUrl,
        email: user.email,
        is_owner: owner
      }
    })
  } catch (error) {
    console.error('OAuth callback error:', error.response?.data || error.message)
    res.status(500).json({ error: 'OAuth callback failed', details: error.message })
  }
})

/**
 * Get current authenticated user from session cookie.
 * GET /api/auth/me
 */
router.get('/me', async (req, res) => {
  try {
    // Manual cookie verification so we can return { authenticated: false } on failure
    // rather than the generic 401 body from requireSession.
    const token = req.cookies?.projectx_session
    if (!token) {
      return res.status(401).json({ authenticated: false })
    }

    // Use requireSession-style verification but return shape per contract.
    const { default: jwt } = await import('jsonwebtoken')
    let payload
    try {
      payload = jwt.verify(token, process.env.SESSION_SECRET || '')
    } catch {
      return res.status(401).json({ authenticated: false })
    }

    const dbUser = await getUser(payload.uid)
    if (!dbUser) {
      return res.status(401).json({ authenticated: false })
    }

    const owner = isOwner(dbUser.discord_id)

    // A blocked user's session is treated as unauthenticated — clear the cookie
    // so the frontend drops them back to guest.
    if (dbUser.blocked && !owner) {
      clearSessionCookie(res)
      return res.status(403).json({ authenticated: false, blocked: true })
    }

    return res.json({
      authenticated: true,
      user: {
        id: dbUser.discord_id,
        username: dbUser.username,
        email: dbUser.email,
        avatar_url: dbUser.avatar_url,
        is_owner: owner
      }
    })
  } catch (error) {
    console.error('Get /me error:', error.message)
    return res.status(401).json({ authenticated: false })
  }
})

/**
 * Logout — clears the session cookie.
 * POST /api/auth/logout
 */
router.post('/logout', (req, res) => {
  clearSessionCookie(res)
  return res.json({ success: true })
})

/**
 * Refresh the user's guild list using the stored Discord refresh token.
 * If the Discord refresh fails, clears the session and returns 401.
 * POST /api/auth/refresh-guilds
 */
router.post('/refresh-guilds', requireSession, async (req, res) => {
  const userId = req.user.id
  let tokens
  try {
    tokens = await refreshDiscordTokens(userId)
  } catch (error) {
    console.error('Discord token refresh failed:', error.response?.data || error.message)
    clearSessionCookie(res)
    return res.status(401).json({ error: 'Discord token refresh failed' })
  }

  try {
    const guildsResponse = await axios.get(`${DISCORD_API}/users/@me/guilds`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` }
    })
    await reconcileUserGuilds(userId, guildsResponse.data)
    return res.json({ success: true })
  } catch (error) {
    console.error('refresh-guilds error:', error.response?.data || error.message)
    return res.status(500).json({ error: 'Failed to refresh guilds' })
  }
})

export default router
