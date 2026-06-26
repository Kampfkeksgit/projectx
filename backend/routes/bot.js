import express from 'express'
import {
  MODULE_DEFAULTS,
  WELCOME_LEAVE_DEFAULTS,
  getGuildSettings,
  getAutoroleSettings,
  getLogSettings,
  getModerationSettings,
  syncBotPresence,
  replaceGuildChannels,
  replaceGuildRoles,
  getReactionRoleMessages,
  getLevelingSettings,
  getLevelingRewards,
  grantXp,
  getCustomCommands,
  getCommandConfigForBot,
  getAllEnabledSocialSubscriptions,
  updateSocialSubscriptionState,
  addModerationWarning,
  getAllEnabledStatsConfigs,
  setStatsCounterChannel,
  setStatsCategory,
  insertStatsSnapshot,
  getTempVoiceSettings,
  addTempVoiceChannel,
  removeTempVoiceChannel,
  getAllTempVoiceChannels,
  getStarboardSettings,
  getStarboardEntry,
  upsertStarboardEntry,
  deleteStarboardEntry,
  getSuggestionSettings,
  getGeneralSettings,
  getBirthdaySettings,
  setBirthday,
  getTodaysBirthdays,
  getBirthdayRoleGuilds,
  getAntiRaidSettings,
  getDueScheduledMessages,
  markScheduledRan,
  getVerificationSettings,
  setVerificationPanelMessage,
  getPendingRoleMenus,
  setRoleMenuMessage,
  getRoleMenuByMessage,
  getGiveawayById,
  getTicketSettings,
  getTicketConfig,
  setTicketPanelMessage,
  createTicket,
  getOpenTicketForUser,
  getTicketByChannel,
  closeTicketByChannel,
  claimTicket,
  setTicketRating,
  updateTicketExtraUsers,
  createGiveaway,
  setGiveawayMessage,
  addGiveawayEntry,
  getGiveawayEntries,
  getDueGiveaways,
  markGiveawayEnded,
  isGuildBlocked,
  getGuild,
  effectiveTier,
  moduleUnlocked,
  syncSkuEntitlements,
  getCountingSettings,
  recordCount,
  createPoll,
  setPollMessage,
  getPoll,
  votePoll,
  getDuePolls,
  markPollEnded,
  getInviteSettings,
  replaceGuildInvites,
  getGuildInvitesCache,
  recordMemberInvite,
  getEnabledApplicationForms,
  getApplicationForm,
  setApplicationPanelMessage,
  createApplication,
  reviewApplication,
  getEconomySettings,
  getEconomyBalance,
  economyDaily,
  economyWork,
  economyPay,
  getEconomyLeaderboard,
  getEconomyShop,
  economyBuy,
  getGamesSettings,
  recordGameScore,
  getGameLeaderboard,
  getDueBackupJobs,
  updateBackupJob,
  createBackup
} from '../db.js'
import { requireBotToken } from '../middleware/session.js'
import { setBotStats } from '../state/botStats.js'

const router = express.Router()

/**
 * Guard every per-guild bot endpoint: if the system owner has blocked this
 * guild, return 403 so the bot's helpers (fetch_bot_settings / bot_get etc.)
 * treat it as a failure and skip — making the bot go inert in blocked guilds.
 * The guild-spanning poller endpoints (social/stats/scheduled/…) already filter
 * blocked guilds at the DB layer.
 */
router.use('/guilds/:guild_id', requireBotToken, async (req, res, next) => {
  try {
    if (await isGuildBlocked(req.params.guild_id)) {
      return res.status(403).json({ error: 'Guild is blocked', blocked: true })
    }
    // Premium gate for per-guild module endpoints that aren't covered by the
    // bulk-query tier filters. When the guild's tier is below the module, return
    // a "disabled" shape so the bot treats the premium feature as off (this is
    // what makes a lapsed/downgraded guild stop getting the feature at runtime).
    const gate = PREMIUM_BOT_GATES.find((g) => g.test.test(req.path))
    if (gate) {
      const guild = await getGuild(req.params.guild_id)
      if (!moduleUnlocked(effectiveTier(guild), gate.module)) {
        return res.json(gate.disabled)
      }
    }
    next()
  } catch (error) {
    console.error('Bot guild-block guard error:', error.message)
    res.status(500).json({ error: 'Failed to check guild status' })
  }
})

/**
 * Per-guild premium bot endpoints (path suffix → module + the "off" shape to
 * return when locked). Bulk poller endpoints (social/stats/scheduled/birthday/
 * rolemenus/giveaways) are filtered at the DB layer instead.
 */
const PREMIUM_BOT_GATES = [
  { test: /\/settings\/leveling$/, module: 'leveling', disabled: { enabled: false } },
  { test: /\/leveling\/xp$/, module: 'leveling', disabled: { granted: false } },
  { test: /\/settings\/tempvoice$/, module: 'tempvoice', disabled: { enabled: false } },
  { test: /\/settings\/starboard$/, module: 'starboard', disabled: { enabled: false } },
  { test: /\/settings\/antiraid$/, module: 'antiraid', disabled: { enabled: false } },
  { test: /\/settings\/tickets$/, module: 'tickets', disabled: { enabled: false, categories: [] } },
  { test: /\/settings\/invitetracking$/, module: 'invitetracking', disabled: { enabled: false } },
  { test: /\/settings\/applications$/, module: 'applications', disabled: { forms: [] } },
  { test: /\/settings\/economy$/, module: 'economy', disabled: { enabled: false } },
  { test: /\/settings\/games$/, module: 'games', disabled: { games_channel_id: null, tictactoe_enabled: false, rps_enabled: false, trivia_enabled: false, connect4_enabled: false, hangman_enabled: false, poker_enabled: false } }
]

/**
 * Bot-only: bulk-sync Discord SKU entitlements → premium tiers.
 *   PUT /api/bot/premium   Body: { entitlements: [{ guild_id, tier, until? }] }
 * Sets sku-sourced premium for entitled guilds and downgrades guilds whose SKU
 * premium lapsed. Manual (owner-set) premium is untouched. Called by the bot's
 * premium_sync cog. Not under the /guilds guard (it spans all guilds).
 */
router.put('/premium', requireBotToken, async (req, res) => {
  try {
    const result = await syncSkuEntitlements(req.body?.entitlements)
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Bot premium sync error:', error.message)
    res.status(500).json({ error: 'Failed to sync premium' })
  }
})

/**
 * Bot-only: push current bot stats (guild count, total user count, start time).
 *   PUT /api/bot/stats
 *   Headers: X-Bot-Token: <BOT_API_KEY>
 *   Body:    { guild_count: number, user_count: number, started_at: number (unix seconds) }
 *
 * The public landing-page endpoint /api/public/stats reads this in-memory cache.
 * If the bot stops pinging for > 15 min, the public endpoint treats the data as stale.
 */
router.put('/stats', requireBotToken, (req, res) => {
  try {
    const { guild_count, user_count, started_at } = req.body || {}
    setBotStats({
      guild_count: Number(guild_count),
      user_count: Number(user_count),
      started_at: Number(started_at)
    })
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot stats update error:', error.message)
    res.status(500).json({ error: 'Failed to update stats' })
  }
})

/**
 * Bot-only: fetch the welcome/leave settings for a guild.
 *
 *   GET /api/bot/guilds/:guild_id/settings
 *   Headers: X-Bot-Token: <BOT_API_KEY>
 *
 * Returns the raw top-level settings shape the bot consumes (NOT wrapped in
 * a `{ success, settings }` envelope — see bot/cogs/welcome_leave.py).
 * Falls back to default values if the guild has no row.
 */
router.get('/guilds/:guild_id/settings', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const settings = await getGuildSettings(guildId)

    if (!settings) {
      return res.json({
        ...WELCOME_LEAVE_DEFAULTS,
        welcome_embed: { ...WELCOME_LEAVE_DEFAULTS.welcome_embed },
        leave_embed: { ...WELCOME_LEAVE_DEFAULTS.leave_embed }
      })
    }

    return res.json({
      welcome_enabled: !!settings.welcome_enabled,
      welcome_channel_id: settings.welcome_channel_id ?? null,
      welcome_message: settings.welcome_message ?? WELCOME_LEAVE_DEFAULTS.welcome_message,
      leave_enabled: !!settings.leave_enabled,
      leave_channel_id: settings.leave_channel_id ?? null,
      leave_message: settings.leave_message ?? WELCOME_LEAVE_DEFAULTS.leave_message,
      welcome_use_embed: !!settings.welcome_use_embed,
      welcome_embed: settings.welcome_embed ?? { ...WELCOME_LEAVE_DEFAULTS.welcome_embed },
      welcome_ping_user: !!settings.welcome_ping_user,
      welcome_dm_enabled: !!settings.welcome_dm_enabled,
      welcome_dm_message: settings.welcome_dm_message ?? '',
      welcome_delete_after: settings.welcome_delete_after ?? 0,
      leave_use_embed: !!settings.leave_use_embed,
      leave_embed: settings.leave_embed ?? { ...WELCOME_LEAVE_DEFAULTS.leave_embed },
      leave_delete_after: settings.leave_delete_after ?? 0
    })
  } catch (error) {
    console.error('Bot get guild settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch settings' })
  }
})

/**
 * Bot-only: fetch auto-role settings (raw shape).
 *   GET /api/bot/guilds/:guild_id/settings/autorole
 */
router.get('/guilds/:guild_id/settings/autorole', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const row = await getAutoroleSettings(guildId)
    if (!row) {
      return res.json({ ...MODULE_DEFAULTS.autorole })
    }
    return res.json({
      enabled: !!row.enabled,
      role_ids: Array.isArray(row.role_ids) ? row.role_ids : [],
      apply_to_bots: !!row.apply_to_bots
    })
  } catch (error) {
    console.error('Bot get autorole settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch autorole settings' })
  }
})

/**
 * Bot-only: fetch server-log settings (raw shape).
 *   GET /api/bot/guilds/:guild_id/settings/logs
 */
router.get('/guilds/:guild_id/settings/logs', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const row = await getLogSettings(guildId)
    if (!row) {
      return res.json({ ...MODULE_DEFAULTS.logs })
    }
    return res.json({
      enabled: !!row.enabled,
      log_channel_id: row.log_channel_id ?? null,
      log_joins: !!row.log_joins,
      log_leaves: !!row.log_leaves,
      log_message_edits: !!row.log_message_edits,
      log_message_deletes: !!row.log_message_deletes,
      log_member_bans: !!row.log_member_bans,
      log_member_updates: !!row.log_member_updates,
      log_member_unbans: !!row.log_member_unbans,
      log_channels: !!row.log_channels,
      log_roles: !!row.log_roles,
      log_voice: !!row.log_voice,
      log_ignored_channel_ids: Array.isArray(row.log_ignored_channel_ids) ? row.log_ignored_channel_ids : []
    })
  } catch (error) {
    console.error('Bot get log settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch log settings' })
  }
})

/**
 * Bot-only: fetch moderation settings (raw shape).
 *   GET /api/bot/guilds/:guild_id/settings/moderation
 */
router.get('/guilds/:guild_id/settings/moderation', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const row = await getModerationSettings(guildId)
    if (!row) {
      return res.json({ ...MODULE_DEFAULTS.moderation })
    }
    return res.json({
      enabled: !!row.enabled,
      anti_spam_enabled: !!row.anti_spam_enabled,
      max_messages_per_10s: row.max_messages_per_10s ?? 5,
      banned_words: Array.isArray(row.banned_words) ? row.banned_words : [],
      banned_word_action: row.banned_word_action ?? 'delete',
      mute_role_id: row.mute_role_id ?? null,
      anti_invite: !!row.anti_invite,
      anti_link: !!row.anti_link,
      filter_action: row.filter_action ?? 'delete',
      anti_mention: !!row.anti_mention,
      max_mentions: row.max_mentions ?? 5,
      anti_caps: !!row.anti_caps,
      caps_percentage: row.caps_percentage ?? 70,
      timeout_duration: row.timeout_duration ?? 300,
      warn_threshold: row.warn_threshold ?? 0,
      warn_escalation_action: row.warn_escalation_action ?? 'mute',
      exempt_role_ids: Array.isArray(row.exempt_role_ids) ? row.exempt_role_ids : [],
      ignored_channel_ids: Array.isArray(row.ignored_channel_ids) ? row.ignored_channel_ids : []
    })
  } catch (error) {
    console.error('Bot get moderation settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch moderation settings' })
  }
})

/**
 * Bot-only: record a moderation warning + evaluate escalation threshold.
 *   POST /api/bot/guilds/:guild_id/moderation/warn
 *   Body: { user_id }
 * → { count, total, threshold, threshold_reached, escalation_action, timeout_duration }
 */
router.post('/guilds/:guild_id/moderation/warn', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    const userId = req.body?.user_id
    if (typeof userId !== 'string' || !SNOWFLAKE_REGEX.test(userId)) {
      return res.status(400).json({ error: 'user_id must be a Discord snowflake' })
    }
    const result = await addModerationWarning(guildId, userId, Math.floor(Date.now() / 1000))
    return res.json(result)
  } catch (error) {
    console.error('Bot moderation warn error:', error.message)
    res.status(500).json({ error: 'Failed to record warning' })
  }
})

/**
 * Bot-only: sync the bot's current guild membership.
 *
 *   PUT /api/bot/presence
 *   Headers: X-Bot-Token: <BOT_API_KEY>
 *   Body:    { guild_ids: string[] }
 *
 * Sets `bot_present = 1` for every guild in the list, `0` for the rest.
 * Called by the bot on_ready, on_guild_join, on_guild_remove, and a 5min loop.
 */
router.put('/presence', requireBotToken, async (req, res) => {
  try {
    const ids = Array.isArray(req.body?.guild_ids) ? req.body.guild_ids : null
    if (!ids) {
      return res.status(400).json({ error: 'guild_ids must be an array' })
    }
    // Defensive: only accept snowflake-shaped strings
    const safeIds = ids.filter((id) => typeof id === 'string' && /^\d{15,25}$/.test(id))
    const result = await syncBotPresence(safeIds)
    return res.json({ success: true, ...result, received: safeIds.length })
  } catch (error) {
    console.error('Bot presence sync error:', error.stack || error.message)
    res.status(500).json({ error: 'Failed to sync presence', details: error.message })
  }
})

const SNOWFLAKE_REGEX = /^\d{15,25}$/

/**
 * Bot-only: replace the full channel list for a guild.
 *
 *   PUT /api/bot/guilds/:guild_id/channels
 *   Headers: X-Bot-Token: <BOT_API_KEY>
 *   Body:    { channels: [{ id, name, type, parent_id, position }] }
 *
 * Drops items without an id/name or with a non-snowflake id, then runs a
 * full DELETE + bulk INSERT in one transaction (see replaceGuildChannels).
 */
router.put('/guilds/:guild_id/channels', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }

    const raw = Array.isArray(req.body?.channels) ? req.body.channels : null
    if (!raw) {
      return res.status(400).json({ error: 'channels must be an array' })
    }

    const channels = raw.filter((c) => (
      c
      && typeof c.id === 'string' && SNOWFLAKE_REGEX.test(c.id)
      && typeof c.name === 'string' && c.name.length > 0
    ))

    const guildMeta = (req.body?.guild_name || req.body?.guild_icon_url)
      ? { name: req.body.guild_name, icon_url: req.body.guild_icon_url }
      : null

    const count = await replaceGuildChannels(guildId, channels, guildMeta)
    return res.json({ success: true, count })
  } catch (error) {
    console.error('Bot replace channels error:', error.stack || error.message)
    res.status(500).json({ error: 'Failed to replace channels' })
  }
})

/**
 * Bot-only: replace the full role list for a guild.
 *
 *   PUT /api/bot/guilds/:guild_id/roles
 *   Headers: X-Bot-Token: <BOT_API_KEY>
 *   Body:    { roles: [{ id, name, color, position, managed, is_default }] }
 *
 * Same DELETE + bulk INSERT pattern as channels. @everyone is expected to be
 * included with `is_default: true` so the dashboard read path can filter it.
 */
router.put('/guilds/:guild_id/roles', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }

    const raw = Array.isArray(req.body?.roles) ? req.body.roles : null
    if (!raw) {
      return res.status(400).json({ error: 'roles must be an array' })
    }

    const roles = raw.filter((r) => (
      r
      && typeof r.id === 'string' && SNOWFLAKE_REGEX.test(r.id)
      && typeof r.name === 'string' && r.name.length > 0
    ))

    const guildMeta = (req.body?.guild_name || req.body?.guild_icon_url)
      ? { name: req.body.guild_name, icon_url: req.body.guild_icon_url }
      : null

    const count = await replaceGuildRoles(guildId, roles, guildMeta)
    return res.json({ success: true, count })
  } catch (error) {
    console.error('Bot replace roles error:', error.stack || error.message)
    res.status(500).json({ error: 'Failed to replace roles' })
  }
})

/**
 * Bot-only: list reaction-role messages (with mappings) for a guild.
 *   GET /api/bot/guilds/:guild_id/reaction-roles
 */
router.get('/guilds/:guild_id/reaction-roles', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    const messages = await getReactionRoleMessages(guildId)
    return res.json({ messages })
  } catch (error) {
    console.error('Bot get reaction roles error:', error.message)
    res.status(500).json({ error: 'Failed to fetch reaction roles' })
  }
})

/**
 * Bot-only: fetch leveling settings (raw shape, no rewards inline).
 *   GET /api/bot/guilds/:guild_id/settings/leveling
 */
router.get('/guilds/:guild_id/settings/leveling', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    const row = await getLevelingSettings(guildId)
    if (!row) {
      return res.json({
        ...MODULE_DEFAULTS.leveling,
        ignored_channel_ids: [...MODULE_DEFAULTS.leveling.ignored_channel_ids]
      })
    }
    return res.json({
      enabled: !!row.enabled,
      xp_per_message_min: row.xp_per_message_min,
      xp_per_message_max: row.xp_per_message_max,
      cooldown_seconds: row.cooldown_seconds,
      level_up_channel_id: row.level_up_channel_id ?? null,
      level_up_message: row.level_up_message,
      ignored_channel_ids: Array.isArray(row.ignored_channel_ids) ? row.ignored_channel_ids : [],
      stack_role_rewards: !!row.stack_role_rewards
    })
  } catch (error) {
    console.error('Bot get leveling settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leveling settings' })
  }
})

/**
 * Bot-only: fetch the level → role-reward map for a guild.
 *   GET /api/bot/guilds/:guild_id/leveling/rewards
 */
router.get('/guilds/:guild_id/leveling/rewards', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    const rewards = await getLevelingRewards(guildId)
    return res.json({ rewards })
  } catch (error) {
    console.error('Bot get leveling rewards error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leveling rewards' })
  }
})

/**
 * Bot-only: grant XP to a user. Atomic; returns the full payload the bot
 * needs to render a level-up announcement + assign role rewards.
 *
 *   POST /api/bot/guilds/:guild_id/leveling/xp
 *   Body: { user_id, channel_id }
 */
router.post('/guilds/:guild_id/leveling/xp', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    const userId = req.body?.user_id
    const channelId = req.body?.channel_id
    if (typeof userId !== 'string' || !SNOWFLAKE_REGEX.test(userId)) {
      return res.status(400).json({ error: 'user_id must be a Discord snowflake' })
    }
    if (typeof channelId !== 'string' || !SNOWFLAKE_REGEX.test(channelId)) {
      return res.status(400).json({ error: 'channel_id must be a Discord snowflake' })
    }

    const result = await grantXp(guildId, userId, Math.floor(Date.now() / 1000))

    if (!result.granted) {
      return res.json({ granted: false })
    }

    // Channel-level opt-out: if this channel is in the ignored list, the bot
    // still got XP recorded — but we tell the bot not to grant or announce.
    // (Spec: "If leveling is disabled or the channel is in ignored_channel_ids,
    //  returns { granted: false }").
    if (Array.isArray(result.ignored_channel_ids) && result.ignored_channel_ids.includes(channelId)) {
      return res.json({ granted: false })
    }

    return res.json({
      granted: true,
      leveled_up: !!result.leveled_up,
      xp_gained: result.xp_gained,
      total_xp: result.total_xp,
      new_level: result.new_level,
      role_rewards: Array.isArray(result.role_rewards) ? result.role_rewards : [],
      announce_channel_id: result.level_up_channel_id ?? null,
      announce_message_template: result.level_up_message_template ?? null
    })
  } catch (error) {
    console.error('Bot grant XP error:', error.message)
    res.status(500).json({ error: 'Failed to grant XP' })
  }
})

/**
 * Bot-only: list ENABLED custom commands for a guild (raw shape, no envelope).
 *   GET /api/bot/guilds/:guild_id/custom-commands
 */
router.get('/guilds/:guild_id/custom-commands', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    const all = await getCustomCommands(guildId)
    const commands = all
      .filter((c) => c.enabled)
      .map((c) => ({
        id: c.id,
        trigger: c.trigger,
        response: c.response,
        match_type: c.match_type,
        enabled: !!c.enabled
      }))
    return res.json({ commands })
  } catch (error) {
    console.error('Bot get custom commands error:', error.message)
    res.status(500).json({ error: 'Failed to fetch custom commands' })
  }
})

// Bot-only: per-guild command config — custom prefix + disabled command keys.
// Read by the bot to resolve the prefix and gate built-in commands per guild.
router.get('/guilds/:guild_id/commands', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }
    return res.json(await getCommandConfigForBot(guildId))
  } catch (error) {
    console.error('Bot get command config error:', error.message)
    res.status(500).json({ error: 'Failed to fetch command config' })
  }
})

/**
 * Bot-only: list ALL enabled social subscriptions across every guild.
 * The social-notify poller reads this once per cycle. Includes the
 * bot-maintained polling state (last_video_id / last_live / account_id).
 *   GET /api/bot/social/subscriptions
 */
router.get('/social/subscriptions', requireBotToken, async (req, res) => {
  try {
    const subscriptions = await getAllEnabledSocialSubscriptions()
    return res.json({ subscriptions })
  } catch (error) {
    console.error('Bot get social subscriptions error:', error.message)
    res.status(500).json({ error: 'Failed to fetch social subscriptions' })
  }
})

/**
 * Bot-only: persist polling state for a subscription after a check.
 *   PUT /api/bot/social/subscriptions/:sub_id/state
 *   Body: { account_id?, display_name?, last_video_id?, last_live? }
 * Only the keys present in the body are written; last_checked_at is always
 * stamped server-side.
 */
router.put('/social/subscriptions/:sub_id/state', requireBotToken, async (req, res) => {
  try {
    const subId = req.params.sub_id
    const body = req.body || {}
    const changes = await updateSocialSubscriptionState(subId, {
      account_id: body.account_id,
      display_name: body.display_name,
      last_video_id: body.last_video_id,
      last_live: body.last_live
    }, Math.floor(Date.now() / 1000))
    if (changes === 0) {
      return res.status(404).json({ error: 'Subscription not found' })
    }
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot update social state error:', error.message)
    res.status(500).json({ error: 'Failed to update social state' })
  }
})

/**
 * Bot-only: every guild with the stats module enabled, with its update interval
 * and its enabled counters. The stats cog reads this once per poll cycle.
 *   GET /api/bot/stats/configs
 */
router.get('/stats/configs', requireBotToken, async (req, res) => {
  try {
    const configs = await getAllEnabledStatsConfigs()
    return res.json({ configs })
  } catch (error) {
    console.error('Bot get stats configs error:', error.message)
    res.status(500).json({ error: 'Failed to fetch stats configs' })
  }
})

/**
 * Bot-only: store the channel_id the bot auto-created for a stats counter, so
 * future cycles rename it in place instead of creating another channel.
 *   PUT /api/bot/guilds/:guild_id/stats/counters/:counter_id/channel
 *   Body: { channel_id }
 */
router.put('/guilds/:guild_id/stats/counters/:counter_id/channel', requireBotToken, async (req, res) => {
  try {
    const { guild_id, counter_id } = req.params
    const channelId = (req.body || {}).channel_id
    const changes = await setStatsCounterChannel(guild_id, counter_id, channelId)
    if (changes === 0) {
      return res.status(404).json({ error: 'Stats counter not found' })
    }
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set stats counter channel error:', error.message)
    res.status(500).json({ error: 'Failed to set stats counter channel' })
  }
})

/**
 * Bot-only: store the category_id the bot auto-created for a guild's stats
 * channels, so future cycles reuse it instead of creating another category.
 *   PUT /api/bot/guilds/:guild_id/stats/category
 *   Body: { category_id }
 */
router.put('/guilds/:guild_id/stats/category', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const categoryId = (req.body || {}).category_id
    const changes = await setStatsCategory(guildId, categoryId)
    if (changes === 0) {
      return res.status(404).json({ error: 'Stats settings not found' })
    }
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set stats category error:', error.message)
    res.status(500).json({ error: 'Failed to set stats category' })
  }
})

/**
 * Bot-only: record a stats snapshot (powers the dashboard history graphs).
 *   POST /api/bot/guilds/:guild_id/stats/snapshot
 *   Body: { members, humans, bots, online, offline, boosters }
 */
router.post('/guilds/:guild_id/stats/snapshot', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const b = req.body || {}
    await insertStatsSnapshot(guildId, {
      members: b.members, humans: b.humans, bots: b.bots,
      online: b.online, offline: b.offline, boosters: b.boosters
    }, Math.floor(Date.now() / 1000))
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot insert stats snapshot error:', error.message)
    res.status(500).json({ error: 'Failed to insert stats snapshot' })
  }
})

// ----- Batch 1 modules (v12): Temp-Voice / Starboard / Suggestions -----

// Temp-Voice: raw settings for a guild.
router.get('/guilds/:guild_id/settings/tempvoice', requireBotToken, async (req, res) => {
  try {
    const settings = await getTempVoiceSettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get tempvoice settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch temp-voice settings' })
  }
})

// Temp-Voice: track a freshly-created temp channel.
router.post('/guilds/:guild_id/tempvoice/channels', requireBotToken, async (req, res) => {
  try {
    const { channel_id, owner_id } = req.body || {}
    if (!channel_id) return res.status(400).json({ error: 'channel_id required' })
    await addTempVoiceChannel(req.params.guild_id, channel_id, owner_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot add tempvoice channel error:', error.message)
    res.status(500).json({ error: 'Failed to track temp-voice channel' })
  }
})

// Temp-Voice: untrack a temp channel (after deletion).
router.delete('/guilds/:guild_id/tempvoice/channels/:channel_id', requireBotToken, async (req, res) => {
  try {
    await removeTempVoiceChannel(req.params.channel_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot remove tempvoice channel error:', error.message)
    res.status(500).json({ error: 'Failed to untrack temp-voice channel' })
  }
})

// Temp-Voice: all tracked temp channels across guilds (for startup cleanup).
router.get('/tempvoice/channels', requireBotToken, async (req, res) => {
  try {
    const channels = await getAllTempVoiceChannels()
    return res.json({ channels })
  } catch (error) {
    console.error('Bot get tempvoice channels error:', error.message)
    res.status(500).json({ error: 'Failed to fetch temp-voice channels' })
  }
})

// Starboard: raw settings for a guild.
router.get('/guilds/:guild_id/settings/starboard', requireBotToken, async (req, res) => {
  try {
    const settings = await getStarboardSettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get starboard settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch starboard settings' })
  }
})

// Starboard: read the entry for a source message (or null).
router.get('/guilds/:guild_id/starboard/entries/:message_id', requireBotToken, async (req, res) => {
  try {
    const entry = await getStarboardEntry(req.params.guild_id, req.params.message_id)
    return res.json({ entry })
  } catch (error) {
    console.error('Bot get starboard entry error:', error.message)
    res.status(500).json({ error: 'Failed to fetch starboard entry' })
  }
})

// Starboard: upsert the entry (count + posted star message id).
router.put('/guilds/:guild_id/starboard/entries/:message_id', requireBotToken, async (req, res) => {
  try {
    const b = req.body || {}
    await upsertStarboardEntry(req.params.guild_id, req.params.message_id, {
      channel_id: b.channel_id,
      star_message_id: b.star_message_id,
      count: b.count
    })
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot upsert starboard entry error:', error.message)
    res.status(500).json({ error: 'Failed to upsert starboard entry' })
  }
})

// Starboard: delete the entry (dropped below threshold / unstarred).
router.delete('/guilds/:guild_id/starboard/entries/:message_id', requireBotToken, async (req, res) => {
  try {
    await deleteStarboardEntry(req.params.guild_id, req.params.message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot delete starboard entry error:', error.message)
    res.status(500).json({ error: 'Failed to delete starboard entry' })
  }
})

// Suggestions: raw settings for a guild.
router.get('/guilds/:guild_id/settings/suggestions', requireBotToken, async (req, res) => {
  try {
    const settings = await getSuggestionSettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get suggestion settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch suggestion settings' })
  }
})

// General dashboard settings (v36) — raw object, no envelope.
router.get('/guilds/:guild_id/settings/general', requireBotToken, async (req, res) => {
  try {
    const settings = await getGeneralSettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get general settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch general settings' })
  }
})

// ----- Batch 2 modules (v13): Birthday / Scheduled / Anti-Raid -----

// Birthday: raw settings.
router.get('/guilds/:guild_id/settings/birthday', requireBotToken, async (req, res) => {
  try {
    const settings = await getBirthdaySettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get birthday settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch birthday settings' })
  }
})

// Birthday: set a member's birthday (from the bot command).
router.post('/guilds/:guild_id/birthdays', requireBotToken, async (req, res) => {
  try {
    const { user_id, day, month, year } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    let result
    try {
      result = await setBirthday(req.params.guild_id, user_id, { day, month, year })
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    return res.json({ success: true, birthday: result })
  } catch (error) {
    console.error('Bot set birthday error:', error.message)
    res.status(500).json({ error: 'Failed to set birthday' })
  }
})

// Birthday: everyone whose birthday is today (server computes the date).
router.get('/birthdays/today', requireBotToken, async (req, res) => {
  try {
    const now = new Date()
    const birthdays = await getTodaysBirthdays(now.getMonth() + 1, now.getDate())
    return res.json({ birthdays })
  } catch (error) {
    console.error('Bot get today birthdays error:', error.message)
    res.status(500).json({ error: 'Failed to fetch birthdays' })
  }
})

// Birthday: enabled guilds with a birthday role (for the daily role sweep).
router.get('/birthdays/role-guilds', requireBotToken, async (req, res) => {
  try {
    const guilds = await getBirthdayRoleGuilds()
    return res.json({ guilds })
  } catch (error) {
    console.error('Bot get birthday role guilds error:', error.message)
    res.status(500).json({ error: 'Failed to fetch birthday role guilds' })
  }
})

// Anti-Raid: raw settings.
router.get('/guilds/:guild_id/settings/antiraid', requireBotToken, async (req, res) => {
  try {
    const settings = await getAntiRaidSettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get antiraid settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch anti-raid settings' })
  }
})

// Scheduled: messages that are due now (across all guilds).
router.get('/scheduled/due', requireBotToken, async (req, res) => {
  try {
    const messages = await getDueScheduledMessages(Math.floor(Date.now() / 1000))
    return res.json({ messages })
  } catch (error) {
    console.error('Bot get due scheduled error:', error.message)
    res.status(500).json({ error: 'Failed to fetch due scheduled messages' })
  }
})

// Scheduled: mark a message as run (advance interval / disable once).
router.put('/scheduled/:id/ran', requireBotToken, async (req, res) => {
  try {
    await markScheduledRan(req.params.id, Math.floor(Date.now() / 1000))
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot mark scheduled ran error:', error.message)
    res.status(500).json({ error: 'Failed to mark scheduled message run' })
  }
})

// ----- Server Backup & Restore (v32) -----

// Backup: jobs that are due now (across all guilds). Restore jobs include `.data`.
router.get('/backup/jobs/due', requireBotToken, async (req, res) => {
  try {
    const jobs = await getDueBackupJobs()
    return res.json({ jobs })
  } catch (error) {
    console.error('Bot get due backup jobs error:', error.message)
    res.status(500).json({ error: 'Failed to fetch due backup jobs' })
  }
})

// Backup: update a job's status / result.
router.put('/backup/jobs/:job_id', requireBotToken, async (req, res) => {
  try {
    const { status, backup_id, message } = req.body || {}
    await updateBackupJob(req.params.job_id, { status, backup_id, message })
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot update backup job error:', error.message)
    res.status(500).json({ error: 'Failed to update backup job' })
  }
})

// Backup: store a snapshot created by the bot.
router.post('/guilds/:guild_id/backups', requireBotToken, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    if (!SNOWFLAKE_REGEX.test(guildId)) {
      return res.status(400).json({ error: 'Invalid guild_id' })
    }

    const { name, guild_name, guild_icon_url, data } = req.body || {}
    const snapshot = await createBackup(guildId, { name, guild_name, guild_icon_url, data })
    return res.json({ id: snapshot.id })
  } catch (error) {
    console.error('Bot create backup error:', error.stack || error.message)
    res.status(500).json({ error: 'Failed to create backup' })
  }
})

// ----- Batch 3 Part A (v14): Verification / Role-Menus -----

// Verification: raw settings.
router.get('/guilds/:guild_id/settings/verification', requireBotToken, async (req, res) => {
  try {
    const settings = await getVerificationSettings(req.params.guild_id)
    return res.json(settings)
  } catch (error) {
    console.error('Bot get verification settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch verification settings' })
  }
})

// Verification: store the posted panel message id.
router.put('/guilds/:guild_id/verification/panel', requireBotToken, async (req, res) => {
  try {
    await setVerificationPanelMessage(req.params.guild_id, (req.body || {}).message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set verification panel error:', error.message)
    res.status(500).json({ error: 'Failed to set verification panel' })
  }
})

// Role-Menus: menus configured but not yet posted (bot posts them).
router.get('/rolemenus/pending', requireBotToken, async (req, res) => {
  try {
    const menus = await getPendingRoleMenus()
    return res.json({ menus })
  } catch (error) {
    console.error('Bot get pending role menus error:', error.message)
    res.status(500).json({ error: 'Failed to fetch pending role menus' })
  }
})

// Role-Menus: a menu by its posted message id (for exclusive-select handling).
router.get('/guilds/:guild_id/rolemenus/by-message/:message_id', requireBotToken, async (req, res) => {
  try {
    const menu = await getRoleMenuByMessage(req.params.guild_id, req.params.message_id)
    return res.json({ menu })
  } catch (error) {
    console.error('Bot get role menu by message error:', error.message)
    res.status(500).json({ error: 'Failed to fetch role menu' })
  }
})

// Role-Menus: store the posted message id for a menu.
router.put('/guilds/:guild_id/rolemenus/:menu_id/message', requireBotToken, async (req, res) => {
  try {
    const b = req.body || {}
    await setRoleMenuMessage(req.params.guild_id, req.params.menu_id, b.channel_id, b.message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set role menu message error:', error.message)
    res.status(500).json({ error: 'Failed to set role menu message' })
  }
})

// ----- Batch 3 Part B (v15): Tickets / Giveaways -----

// Tickets: raw settings + enabled categories (full bot config).
router.get('/guilds/:guild_id/settings/tickets', requireBotToken, async (req, res) => {
  try {
    return res.json(await getTicketConfig(req.params.guild_id))
  } catch (error) {
    console.error('Bot get ticket settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch ticket settings' })
  }
})

// Tickets: ticket row for a channel (claim/rating/add-remove flows).
router.get('/guilds/:guild_id/tickets/by-channel', requireBotToken, async (req, res) => {
  try {
    const ticket = await getTicketByChannel(req.params.guild_id, req.query.channel_id)
    return res.json({ ticket })
  } catch (error) {
    console.error('Bot get ticket by channel error:', error.message)
    res.status(500).json({ error: 'Failed to fetch ticket' })
  }
})

// Tickets: store the posted panel message id.
router.put('/guilds/:guild_id/tickets/panel', requireBotToken, async (req, res) => {
  try {
    await setTicketPanelMessage(req.params.guild_id, (req.body || {}).message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set ticket panel error:', error.message)
    res.status(500).json({ error: 'Failed to set ticket panel' })
  }
})

// Tickets: existing open ticket for a user (dedupe).
router.get('/guilds/:guild_id/tickets/open', requireBotToken, async (req, res) => {
  try {
    const ticket = await getOpenTicketForUser(req.params.guild_id, req.query.user_id)
    return res.json({ ticket })
  } catch (error) {
    console.error('Bot get open ticket error:', error.message)
    res.status(500).json({ error: 'Failed to fetch open ticket' })
  }
})

// Tickets: record a newly-opened ticket channel (returns assigned number).
router.post('/guilds/:guild_id/tickets', requireBotToken, async (req, res) => {
  try {
    const { channel_id, user_id, ticket_category_id } = req.body || {}
    if (!channel_id || !user_id) return res.status(400).json({ error: 'channel_id and user_id required' })
    const result = await createTicket(req.params.guild_id, channel_id, user_id, ticket_category_id || null)
    return res.json({ success: true, ...result })
  } catch (error) {
    console.error('Bot create ticket error:', error.message)
    res.status(500).json({ error: 'Failed to create ticket' })
  }
})

// Tickets: mark the ticket for a channel closed (with who closed it).
router.put('/guilds/:guild_id/tickets/close', requireBotToken, async (req, res) => {
  try {
    const { channel_id, closed_by } = req.body || {}
    await closeTicketByChannel(req.params.guild_id, channel_id, closed_by || null)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot close ticket error:', error.message)
    res.status(500).json({ error: 'Failed to close ticket' })
  }
})

// Tickets: claim a ticket (assign a staff handler).
router.put('/guilds/:guild_id/tickets/claim', requireBotToken, async (req, res) => {
  try {
    const { channel_id, user_id } = req.body || {}
    await claimTicket(req.params.guild_id, channel_id, user_id || null)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot claim ticket error:', error.message)
    res.status(500).json({ error: 'Failed to claim ticket' })
  }
})

// Tickets: store the opener's rating (by ticket id, so it works from a DM).
router.put('/guilds/:guild_id/tickets/rating', requireBotToken, async (req, res) => {
  try {
    const { ticket_id, rating, comment } = req.body || {}
    if (!ticket_id) return res.status(400).json({ error: 'ticket_id required' })
    await setTicketRating(req.params.guild_id, ticket_id, rating, comment || null)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot rate ticket error:', error.message)
    res.status(500).json({ error: 'Failed to rate ticket' })
  }
})

// Tickets: add/remove users manually granted access to a ticket channel.
router.put('/guilds/:guild_id/tickets/users', requireBotToken, async (req, res) => {
  try {
    const { channel_id, add, remove } = req.body || {}
    if (!channel_id) return res.status(400).json({ error: 'channel_id required' })
    const extra_user_ids = await updateTicketExtraUsers(req.params.guild_id, channel_id, { add: add || [], remove: remove || [] })
    return res.json({ success: true, extra_user_ids })
  } catch (error) {
    console.error('Bot ticket users error:', error.message)
    res.status(500).json({ error: 'Failed to update ticket users' })
  }
})

// Giveaways: create (from !gstart). Returns the new id.
router.post('/guilds/:guild_id/giveaways', requireBotToken, async (req, res) => {
  try {
    let result
    try {
      result = await createGiveaway(req.params.guild_id, req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    return res.json({ success: true, ...result })
  } catch (error) {
    console.error('Bot create giveaway error:', error.message)
    res.status(500).json({ error: 'Failed to create giveaway' })
  }
})

// Giveaways: store the posted message id.
router.put('/guilds/:guild_id/giveaways/:gid/message', requireBotToken, async (req, res) => {
  try {
    await setGiveawayMessage(req.params.guild_id, req.params.gid, (req.body || {}).message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set giveaway message error:', error.message)
    res.status(500).json({ error: 'Failed to set giveaway message' })
  }
})

// Giveaways: add an entry (button click).
router.post('/guilds/:guild_id/giveaways/:gid/entries', requireBotToken, async (req, res) => {
  try {
    const changes = await addGiveawayEntry(req.params.gid, (req.body || {}).user_id)
    return res.json({ success: true, added: changes > 0 })
  } catch (error) {
    console.error('Bot add giveaway entry error:', error.message)
    res.status(500).json({ error: 'Failed to add giveaway entry' })
  }
})

// Giveaways: a single giveaway (for reroll).
router.get('/guilds/:guild_id/giveaways/:gid', requireBotToken, async (req, res) => {
  try {
    const giveaway = await getGiveawayById(req.params.guild_id, req.params.gid)
    return res.json({ giveaway })
  } catch (error) {
    console.error('Bot get giveaway error:', error.message)
    res.status(500).json({ error: 'Failed to fetch giveaway' })
  }
})

// Giveaways: entrants for a giveaway.
router.get('/guilds/:guild_id/giveaways/:gid/entries', requireBotToken, async (req, res) => {
  try {
    const user_ids = await getGiveawayEntries(req.params.gid)
    return res.json({ user_ids })
  } catch (error) {
    console.error('Bot get giveaway entries error:', error.message)
    res.status(500).json({ error: 'Failed to fetch giveaway entries' })
  }
})

// Giveaways: due to draw (ended time passed, not yet drawn).
router.get('/giveaways/due', requireBotToken, async (req, res) => {
  try {
    const giveaways = await getDueGiveaways(Math.floor(Date.now() / 1000))
    return res.json({ giveaways })
  } catch (error) {
    console.error('Bot get due giveaways error:', error.message)
    res.status(500).json({ error: 'Failed to fetch due giveaways' })
  }
})

// Giveaways: mark drawn/ended.
router.put('/giveaways/:gid/ended', requireBotToken, async (req, res) => {
  try {
    await markGiveawayEnded(req.params.gid)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot mark giveaway ended error:', error.message)
    res.status(500).json({ error: 'Failed to mark giveaway ended' })
  }
})

// ===== New modules (v23-v27): Counting / Polls / Invite-Tracking / Applications / Economy =====

// ----- Counting (free) -----
router.get('/guilds/:guild_id/settings/counting', requireBotToken, async (req, res) => {
  try {
    return res.json(await getCountingSettings(req.params.guild_id))
  } catch (error) {
    console.error('Bot get counting settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch counting settings' })
  }
})

router.post('/guilds/:guild_id/counting/count', requireBotToken, async (req, res) => {
  try {
    const { user_id, number } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    const result = await recordCount(req.params.guild_id, user_id, number)
    return res.json(result)
  } catch (error) {
    console.error('Bot record count error:', error.message)
    res.status(500).json({ error: 'Failed to record count' })
  }
})

// ----- Polls (free) -----
router.post('/guilds/:guild_id/polls', requireBotToken, async (req, res) => {
  try {
    let poll
    try {
      poll = await createPoll(req.params.guild_id, req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    return res.json(poll)
  } catch (error) {
    console.error('Bot create poll error:', error.message)
    res.status(500).json({ error: 'Failed to create poll' })
  }
})

router.put('/guilds/:guild_id/polls/:pid/message', requireBotToken, async (req, res) => {
  try {
    await setPollMessage(req.params.guild_id, req.params.pid, (req.body || {}).message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set poll message error:', error.message)
    res.status(500).json({ error: 'Failed to set poll message' })
  }
})

router.get('/guilds/:guild_id/polls/:pid', requireBotToken, async (req, res) => {
  try {
    const poll = await getPoll(req.params.guild_id, req.params.pid)
    return res.json({ poll })
  } catch (error) {
    console.error('Bot get poll error:', error.message)
    res.status(500).json({ error: 'Failed to fetch poll' })
  }
})

router.post('/guilds/:guild_id/polls/:pid/vote', requireBotToken, async (req, res) => {
  try {
    const { user_id, option_index } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    const result = await votePoll(req.params.guild_id, req.params.pid, user_id, option_index)
    return res.json(result)
  } catch (error) {
    console.error('Bot vote poll error:', error.message)
    res.status(500).json({ error: 'Failed to register vote' })
  }
})

router.get('/polls/due', requireBotToken, async (req, res) => {
  try {
    const polls = await getDuePolls(Math.floor(Date.now() / 1000))
    return res.json({ polls })
  } catch (error) {
    console.error('Bot get due polls error:', error.message)
    res.status(500).json({ error: 'Failed to fetch due polls' })
  }
})

router.put('/polls/:pid/ended', requireBotToken, async (req, res) => {
  try {
    await markPollEnded(req.params.pid)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot mark poll ended error:', error.message)
    res.status(500).json({ error: 'Failed to mark poll ended' })
  }
})

// ----- Invite tracking (basic) -----
router.get('/guilds/:guild_id/settings/invitetracking', requireBotToken, async (req, res) => {
  try {
    return res.json(await getInviteSettings(req.params.guild_id))
  } catch (error) {
    console.error('Bot get invite settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch invite settings' })
  }
})

router.get('/guilds/:guild_id/invites', requireBotToken, async (req, res) => {
  try {
    const invites = await getGuildInvitesCache(req.params.guild_id)
    return res.json({ invites })
  } catch (error) {
    console.error('Bot get invites cache error:', error.message)
    res.status(500).json({ error: 'Failed to fetch invites' })
  }
})

router.put('/guilds/:guild_id/invites', requireBotToken, async (req, res) => {
  try {
    const result = await replaceGuildInvites(req.params.guild_id, (req.body || {}).invites)
    return res.json({ success: true, ...result })
  } catch (error) {
    console.error('Bot replace invites error:', error.message)
    res.status(500).json({ error: 'Failed to sync invites' })
  }
})

router.post('/guilds/:guild_id/invites/join', requireBotToken, async (req, res) => {
  try {
    const { user_id, inviter_id, code } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    const result = await recordMemberInvite(req.params.guild_id, { user_id, inviter_id, code })
    return res.json({ success: true, ...result })
  } catch (error) {
    console.error('Bot record member invite error:', error.message)
    res.status(500).json({ error: 'Failed to record invite' })
  }
})

// ----- Applications (pro) -----
router.get('/guilds/:guild_id/settings/applications', requireBotToken, async (req, res) => {
  try {
    const forms = await getEnabledApplicationForms(req.params.guild_id)
    return res.json({ forms })
  } catch (error) {
    console.error('Bot get application forms error:', error.message)
    res.status(500).json({ error: 'Failed to fetch application forms' })
  }
})

router.get('/guilds/:guild_id/applications/forms/:fid', requireBotToken, async (req, res) => {
  try {
    const form = await getApplicationForm(req.params.guild_id, req.params.fid)
    return res.json({ form })
  } catch (error) {
    console.error('Bot get application form error:', error.message)
    res.status(500).json({ error: 'Failed to fetch application form' })
  }
})

router.put('/guilds/:guild_id/applications/forms/:fid/panel', requireBotToken, async (req, res) => {
  try {
    const b = req.body || {}
    await setApplicationPanelMessage(req.params.guild_id, req.params.fid, b.channel_id, b.message_id)
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot set application panel error:', error.message)
    res.status(500).json({ error: 'Failed to set application panel' })
  }
})

router.post('/guilds/:guild_id/applications', requireBotToken, async (req, res) => {
  try {
    let result
    try {
      result = await createApplication(req.params.guild_id, req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    return res.json({ success: true, ...result })
  } catch (error) {
    console.error('Bot create application error:', error.message)
    res.status(500).json({ error: 'Failed to submit application' })
  }
})

router.put('/guilds/:guild_id/applications/:appid/review', requireBotToken, async (req, res) => {
  try {
    const b = req.body || {}
    const changes = await reviewApplication(req.params.guild_id, req.params.appid, { status: b.status, reviewer_id: b.reviewer_id })
    return res.json({ success: changes > 0 })
  } catch (error) {
    console.error('Bot review application error:', error.message)
    res.status(500).json({ error: 'Failed to review application' })
  }
})

// ----- Economy (pro) -----
router.get('/guilds/:guild_id/settings/economy', requireBotToken, async (req, res) => {
  try {
    return res.json(await getEconomySettings(req.params.guild_id))
  } catch (error) {
    console.error('Bot get economy settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch economy settings' })
  }
})

router.post('/guilds/:guild_id/economy/balance', requireBotToken, async (req, res) => {
  try {
    const { user_id } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    return res.json(await getEconomyBalance(req.params.guild_id, user_id))
  } catch (error) {
    console.error('Bot economy balance error:', error.message)
    res.status(500).json({ error: 'Failed to fetch balance' })
  }
})

router.post('/guilds/:guild_id/economy/daily', requireBotToken, async (req, res) => {
  try {
    const { user_id } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    return res.json(await economyDaily(req.params.guild_id, user_id, Math.floor(Date.now() / 1000)))
  } catch (error) {
    console.error('Bot economy daily error:', error.message)
    res.status(500).json({ error: 'Failed to claim daily' })
  }
})

router.post('/guilds/:guild_id/economy/work', requireBotToken, async (req, res) => {
  try {
    const { user_id } = req.body || {}
    if (!user_id) return res.status(400).json({ error: 'user_id required' })
    return res.json(await economyWork(req.params.guild_id, user_id, Math.floor(Date.now() / 1000)))
  } catch (error) {
    console.error('Bot economy work error:', error.message)
    res.status(500).json({ error: 'Failed to work' })
  }
})

router.post('/guilds/:guild_id/economy/pay', requireBotToken, async (req, res) => {
  try {
    const { user_id, target_id, amount } = req.body || {}
    if (!user_id || !target_id) return res.status(400).json({ error: 'user_id and target_id required' })
    return res.json(await economyPay(req.params.guild_id, user_id, target_id, amount))
  } catch (error) {
    console.error('Bot economy pay error:', error.message)
    res.status(500).json({ error: 'Failed to pay' })
  }
})

router.get('/guilds/:guild_id/economy/leaderboard', requireBotToken, async (req, res) => {
  try {
    const leaderboard = await getEconomyLeaderboard(req.params.guild_id, Number(req.query.limit) || 10)
    return res.json({ leaderboard })
  } catch (error) {
    console.error('Bot economy leaderboard error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
})

router.get('/guilds/:guild_id/economy/shop', requireBotToken, async (req, res) => {
  try {
    const items = await getEconomyShop(req.params.guild_id, true)
    return res.json({ items })
  } catch (error) {
    console.error('Bot economy shop error:', error.message)
    res.status(500).json({ error: 'Failed to fetch shop' })
  }
})

router.post('/guilds/:guild_id/economy/buy', requireBotToken, async (req, res) => {
  try {
    const { user_id, item_id } = req.body || {}
    if (!user_id || !item_id) return res.status(400).json({ error: 'user_id and item_id required' })
    return res.json(await economyBuy(req.params.guild_id, user_id, item_id))
  } catch (error) {
    console.error('Bot economy buy error:', error.message)
    res.status(500).json({ error: 'Failed to buy item' })
  }
})

// ----- Games category (v28) -----
router.get('/guilds/:guild_id/settings/games', requireBotToken, async (req, res) => {
  try {
    return res.json(await getGamesSettings(req.params.guild_id))
  } catch (error) {
    console.error('Bot get games settings error:', error.message)
    res.status(500).json({ error: 'Failed to fetch games settings' })
  }
})

router.post('/guilds/:guild_id/games/score', requireBotToken, async (req, res) => {
  try {
    const { user_id, game, win } = req.body || {}
    if (!user_id || !game) return res.status(400).json({ error: 'user_id and game required' })
    try {
      await recordGameScore(req.params.guild_id, user_id, game, !!win)
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    return res.json({ success: true })
  } catch (error) {
    console.error('Bot record game score error:', error.message)
    res.status(500).json({ error: 'Failed to record score' })
  }
})

router.get('/guilds/:guild_id/games/leaderboard', requireBotToken, async (req, res) => {
  try {
    const leaderboard = await getGameLeaderboard(req.params.guild_id, req.query.game, Number(req.query.limit) || 10)
    return res.json({ leaderboard })
  } catch (error) {
    console.error('Bot get game leaderboard error:', error.message)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
})

export default router
