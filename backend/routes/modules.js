import express from 'express'
import {
  MODULE_DEFAULTS,
  MOD_ACTIONS,
  MOD_ESCALATION_ACTIONS,
  getAutoroleSettings,
  upsertAutoroleSettings,
  getLogSettings,
  upsertLogSettings,
  getModerationSettings,
  upsertModerationSettings,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

function withGuildDefaults(guildId, defaults) {
  return { guild_id: guildId, ...defaults, created_at: null, updated_at: null }
}

function sanitizeStringArray(value) {
  if (!Array.isArray(value)) return []
  return value.filter((v) => typeof v === 'string' && v.length > 0)
}

// ============================================================================
// Auto-Role
// ============================================================================

router.get('/autorole', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const row = await getAutoroleSettings(guildId)
    if (!row) {
      return res.json({
        success: true,
        settings: withGuildDefaults(guildId, MODULE_DEFAULTS.autorole)
      })
    }
    res.json({ success: true, settings: row })
  } catch (error) {
    console.error('Get autorole settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch autorole settings' })
  }
})

router.put('/autorole', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    const validated = {
      enabled: Boolean(body.enabled),
      role_ids: sanitizeStringArray(body.role_ids),
      apply_to_bots: Boolean(body.apply_to_bots)
    }

    await upsertAutoroleSettings(guildId, validated)
    await logAuditAction(req.user.id, guildId, 'UPDATE_AUTOROLE_SETTINGS', validated)

    res.json({
      success: true,
      message: 'Auto-role settings updated',
      settings: { guild_id: guildId, ...validated }
    })
  } catch (error) {
    console.error('Update autorole settings error:', error.message)
    res.status(500).json({ error: 'Failed to update autorole settings' })
  }
})

// ============================================================================
// Server-Logs
// ============================================================================

router.get('/logs', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const row = await getLogSettings(guildId)
    if (!row) {
      return res.json({
        success: true,
        settings: withGuildDefaults(guildId, MODULE_DEFAULTS.logs)
      })
    }
    res.json({ success: true, settings: row })
  } catch (error) {
    console.error('Get log settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch log settings' })
  }
})

router.put('/logs', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    const validated = {
      enabled: Boolean(body.enabled),
      log_channel_id: typeof body.log_channel_id === 'string' && body.log_channel_id.length > 0
        ? body.log_channel_id
        : null,
      log_joins: Boolean(body.log_joins),
      log_leaves: Boolean(body.log_leaves),
      log_message_edits: Boolean(body.log_message_edits),
      log_message_deletes: Boolean(body.log_message_deletes),
      log_member_bans: Boolean(body.log_member_bans),
      log_member_updates: Boolean(body.log_member_updates),
      log_member_unbans: Boolean(body.log_member_unbans),
      log_channels: Boolean(body.log_channels),
      log_roles: Boolean(body.log_roles),
      log_voice: Boolean(body.log_voice),
      log_ignored_channel_ids: sanitizeStringArray(body.log_ignored_channel_ids)
    }

    await upsertLogSettings(guildId, validated)
    await logAuditAction(req.user.id, guildId, 'UPDATE_LOG_SETTINGS', validated)

    res.json({
      success: true,
      message: 'Log settings updated',
      settings: { guild_id: guildId, ...validated }
    })
  } catch (error) {
    console.error('Update log settings error:', error.message)
    res.status(500).json({ error: 'Failed to update log settings' })
  }
})

// ============================================================================
// Moderation
// ============================================================================

router.get('/moderation', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const row = await getModerationSettings(guildId)
    if (!row) {
      return res.json({
        success: true,
        settings: withGuildDefaults(guildId, MODULE_DEFAULTS.moderation)
      })
    }
    res.json({ success: true, settings: row })
  } catch (error) {
    console.error('Get moderation settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch moderation settings' })
  }
})

router.put('/moderation', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    let rate = Number(body.max_messages_per_10s)
    if (!Number.isFinite(rate)) rate = 5
    rate = Math.max(1, Math.min(100, Math.trunc(rate)))

    const action = MOD_ACTIONS.includes(body.banned_word_action)
      ? body.banned_word_action
      : 'delete'
    const filterAction = MOD_ACTIONS.includes(body.filter_action)
      ? body.filter_action
      : 'delete'
    const escalation = MOD_ESCALATION_ACTIONS.includes(body.warn_escalation_action)
      ? body.warn_escalation_action
      : 'mute'

    const validated = {
      enabled: Boolean(body.enabled),
      anti_spam_enabled: Boolean(body.anti_spam_enabled),
      max_messages_per_10s: rate,
      banned_words: sanitizeStringArray(body.banned_words).map((w) => w.toLowerCase()),
      banned_word_action: action,
      mute_role_id: typeof body.mute_role_id === 'string' && body.mute_role_id.length > 0
        ? body.mute_role_id
        : null,
      anti_invite: Boolean(body.anti_invite),
      anti_link: Boolean(body.anti_link),
      filter_action: filterAction,
      anti_mention: Boolean(body.anti_mention),
      max_mentions: body.max_mentions,
      anti_caps: Boolean(body.anti_caps),
      caps_percentage: body.caps_percentage,
      timeout_duration: body.timeout_duration,
      warn_threshold: body.warn_threshold,
      warn_escalation_action: escalation,
      exempt_role_ids: sanitizeStringArray(body.exempt_role_ids),
      ignored_channel_ids: sanitizeStringArray(body.ignored_channel_ids)
    }

    await upsertModerationSettings(guildId, validated)
    await logAuditAction(req.user.id, guildId, 'UPDATE_MODERATION_SETTINGS', validated)

    // Re-read so the response reflects the clamped/validated numeric fields.
    const stored = await getModerationSettings(guildId)
    res.json({
      success: true,
      message: 'Moderation settings updated',
      settings: stored || { guild_id: guildId, ...validated }
    })
  } catch (error) {
    console.error('Update moderation settings error:', error.message)
    res.status(500).json({ error: 'Failed to update moderation settings' })
  }
})

export default router
