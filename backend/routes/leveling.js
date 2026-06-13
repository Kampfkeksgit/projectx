import express from 'express'
import {
  MODULE_DEFAULTS,
  getLevelingSettings,
  upsertLevelingSettings,
  getLevelingRewards,
  setLevelingRewards,
  getLeaderboard,
  countLeaderboardUsers,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'
import { requirePremiumModule } from '../middleware/premium.js'

// Mounted at /api/guilds/:guild_id — uses absolute sub-paths so the GET/PUT
// settings endpoints sit under /settings/leveling and the leaderboard sits
// under /leveling/leaderboard without needing two mount points.
const router = express.Router({ mergeParams: true })

const SNOWFLAKE_REGEX = /^\d{15,25}$/

function withGuildDefaults(guildId) {
  return {
    guild_id: guildId,
    ...MODULE_DEFAULTS.leveling,
    ignored_channel_ids: [...MODULE_DEFAULTS.leveling.ignored_channel_ids],
    rewards: [],
    updated_at: null
  }
}

router.get('/settings/leveling', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const [row, rewards] = await Promise.all([
      getLevelingSettings(guildId),
      getLevelingRewards(guildId)
    ])
    if (!row) {
      const defaults = withGuildDefaults(guildId)
      defaults.rewards = rewards
      return res.json({ success: true, settings: defaults })
    }
    res.json({ success: true, settings: { ...row, rewards } })
  } catch (error) {
    console.error('Get leveling settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leveling settings' })
  }
})

router.put('/settings/leveling', requireSession, requireGuildAccess, requirePremiumModule('leveling'), async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    const ignored = Array.isArray(body.ignored_channel_ids)
      ? body.ignored_channel_ids.filter((id) => typeof id === 'string' && SNOWFLAKE_REGEX.test(id))
      : []

    const validated = {
      enabled: Boolean(body.enabled),
      xp_per_message_min: body.xp_per_message_min,
      xp_per_message_max: body.xp_per_message_max,
      cooldown_seconds: body.cooldown_seconds,
      level_up_channel_id: typeof body.level_up_channel_id === 'string' && SNOWFLAKE_REGEX.test(body.level_up_channel_id)
        ? body.level_up_channel_id
        : null,
      level_up_message: typeof body.level_up_message === 'string'
        ? body.level_up_message
        : MODULE_DEFAULTS.leveling.level_up_message,
      ignored_channel_ids: ignored,
      stack_role_rewards: body.stack_role_rewards === undefined
        ? true
        : Boolean(body.stack_role_rewards)
    }

    await upsertLevelingSettings(guildId, validated)

    if (Array.isArray(body.rewards)) {
      const rewards = body.rewards
        .filter((r) => r && typeof r === 'object')
        .map((r) => ({ level: r.level, role_id: r.role_id }))
      await setLevelingRewards(guildId, rewards)
    }

    const [saved, rewards] = await Promise.all([
      getLevelingSettings(guildId),
      getLevelingRewards(guildId)
    ])

    await logAuditAction(req.user.id, guildId, 'UPDATE_LEVELING_SETTINGS', {
      ...validated,
      rewards
    })

    res.json({
      success: true,
      message: 'Leveling settings updated',
      settings: { ...(saved || withGuildDefaults(guildId)), rewards }
    })
  } catch (error) {
    console.error('Update leveling settings error:', error.message)
    res.status(500).json({ error: 'Failed to update leveling settings' })
  }
})

router.get('/leveling/leaderboard', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const limit = Math.max(1, Math.min(100, Number(req.query.limit) || 25))
    const offset = Math.max(0, Number(req.query.offset) || 0)
    const [leaderboard, total] = await Promise.all([
      getLeaderboard(guildId, limit, offset),
      countLeaderboardUsers(guildId)
    ])
    res.json({ success: true, leaderboard, total })
  } catch (error) {
    console.error('Get leveling leaderboard error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
})

export default router
