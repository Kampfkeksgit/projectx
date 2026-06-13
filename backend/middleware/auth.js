/**
 * Guild-access authorization middleware.
 *
 * Note: The legacy `verifyToken` middleware (which re-hit Discord on every
 * request) has been removed. Use `requireSession` from `./session.js` to
 * authenticate the user via the HTTP-only session cookie, then chain
 * `requireGuildAccess` to gate per-guild access.
 */

/**
 * Verify the user can MANAGE a specific guild (Owner OR Administrator).
 * Must be called after a middleware that sets `req.user.id` (e.g. requireSession).
 *
 * Note: pure Member-Memberships gelten hier bewusst nicht als Access. Die
 * Guild-Liste filtert dasselbe Kriterium (siehe getUserManageableGuilds),
 * deshalb ist das hier die Defense-in-Depth zum Listen-Filter.
 */
export const requireGuildAccess = async (req, res, next) => {
  try {
    const userId = req.user?.id
    const guildId = req.params.guild_id

    if (!userId || !guildId) {
      return res.status(400).json({ error: 'Missing user or guild ID' })
    }

    // Import db here to avoid circular dependencies
    const { userIsGuildAdmin, isGuildBlocked } = await import('../db.js')

    // A guild blocked by the system owner cannot be configured by anyone.
    if (await isGuildBlocked(guildId)) {
      return res.status(403).json({ error: 'This server is blocked', blocked: true })
    }

    const canManage = await userIsGuildAdmin(userId, guildId)

    if (!canManage) {
      return res.status(403).json({ error: 'Insufficient permissions for this guild' })
    }

    next()
  } catch (error) {
    console.error('Guild access verification error:', error.message)
    res.status(500).json({ error: 'Failed to verify guild access' })
  }
}
