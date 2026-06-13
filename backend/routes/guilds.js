import express from 'express'
import { getUserManageableGuilds, getGuild, getGuildSettings, logAuditAction } from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router()

/**
 * Get manageable guilds for the authenticated user.
 * Returns only guilds where the user is Owner OR has Administrator —
 * Member-only memberships werden bewusst ausgeblendet, da sie das Dashboard
 * ohnehin nicht konfigurieren dürften.
 * GET /api/guilds
 * Cookie: projectx_session
 * Returns: { success: true, guilds: [...] }
 */
router.get('/', requireSession, async (req, res) => {
  try {
    const userId = req.user.id
    const guilds = await getUserManageableGuilds(userId)

    res.json({
      success: true,
      guilds: guilds || []
    })
  } catch (error) {
    console.error('Get user guilds error:', error.message)
    res.status(500).json({ error: 'Failed to fetch guilds' })
  }
})

/**
 * Get specific guild details
 * GET /api/guilds/:guild_id
 * Headers: Authorization: Bearer {access_token}
 * Returns: { success: true, guild: {...} }
 */
router.get('/:guild_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guild = await getGuild(req.params.guild_id)
    
    if (!guild) {
      return res.status(404).json({ error: 'Guild not found' })
    }
    
    res.json({
      success: true,
      guild
    })
  } catch (error) {
    console.error('Get guild error:', error.message)
    res.status(500).json({ error: 'Failed to fetch guild' })
  }
})

/**
 * Get guild with combined settings
 * GET /api/guilds/:guild_id/full
 * Headers: Authorization: Bearer {access_token}
 * Returns: { success: true, guild: {...}, settings: {...} }
 */
router.get('/:guild_id/full', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const guild = await getGuild(guildId)
    
    if (!guild) {
      return res.status(404).json({ error: 'Guild not found' })
    }
    
    const settings = await getGuildSettings(guildId)
    
    res.json({
      success: true,
      guild,
      settings: settings || {
        guild_id: guildId,
        welcome_enabled: true,
        welcome_channel_id: null,
        welcome_message: 'Welcome {user}!',
        leave_enabled: true,
        leave_channel_id: null,
        leave_message: '{user} has left.'
      }
    })
  } catch (error) {
    console.error('Get guild with settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch guild details' })
  }
})

export default router
