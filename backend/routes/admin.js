import express from 'express'
import {
  getAdminUsers,
  setUserBlocked,
  getAdminGuilds,
  setGuildBlocked,
  setGuildPremium,
  PREMIUM_TIERS,
  getUser,
  getGuild,
  logAuditAction,
  getAdminOverview,
  getAuditLogEntries,
  getAuditActions,
  getGuildInspect,
  getMaintenanceState,
  setMaintenanceState,
  getUsersForExport,
  getGuildsForExport,
  getBackup,
  createMarketplaceTemplate,
  getAdminMarketplaceTemplates,
  deleteMarketplaceTemplate,
  setMarketplaceTemplateStatus,
  getAllBackupJobs,
  retryBackupJob,
  getErrorLog,
  clearErrorLog,
  getMetricsSnapshots,
  getTopGuilds,
  getAnnouncementState,
  setAnnouncementState,
  ANNOUNCEMENT_LEVELS,
  createBroadcast,
  getRecentBroadcasts
} from '../db.js'
import { getBotHealth } from '../state/botStats.js'
import { requireSession, requireOwner, isOwner } from '../middleware/session.js'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
let BACKEND_VERSION = null
try { BACKEND_VERSION = require('../package.json').version || null } catch { BACKEND_VERSION = null }

const router = express.Router()

// Every route in this file is owner-only.
router.use(requireSession, requireOwner)

/**
 * GET /api/admin/users?search=&limit=&offset=
 * Owner-only paginated user list with block status.
 */
router.get('/users', async (req, res) => {
  try {
    const { search = '', limit = 50, offset = 0 } = req.query
    const result = await getAdminUsers({ search, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin list users error:', error.message)
    res.status(500).json({ error: 'Failed to list users' })
  }
})

/**
 * POST /api/admin/users/:user_id/block  Body: { blocked: bool, reason?: string }
 * Block or unblock a Discord user. The owner can never be blocked.
 */
router.post('/users/:user_id/block', async (req, res) => {
  try {
    const userId = req.params.user_id
    const blocked = !!req.body?.blocked
    const reason = req.body?.reason
    const until = blocked ? (req.body?.until ?? null) : null

    if (blocked && isOwner(userId)) {
      return res.status(400).json({ error: 'The system owner cannot be blocked' })
    }

    const existing = await getUser(userId)
    if (!existing) {
      return res.status(404).json({ error: 'User not found' })
    }

    await setUserBlocked(userId, blocked, reason, until)
    await logAuditAction(req.user.id, null, blocked ? 'ADMIN_BLOCK_USER' : 'ADMIN_UNBLOCK_USER', {
      target_user_id: userId,
      reason: blocked ? (reason || null) : null,
      until: blocked ? (until || null) : null
    })

    res.json({ success: true, user_id: userId, blocked })
  } catch (error) {
    console.error('Admin block user error:', error.message)
    res.status(500).json({ error: 'Failed to update user' })
  }
})

/**
 * GET /api/admin/guilds?search=&limit=&offset=
 * Owner-only guild list with block status + bot presence.
 */
router.get('/guilds', async (req, res) => {
  try {
    const { search = '', limit = 100, offset = 0 } = req.query
    const result = await getAdminGuilds({ search, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin list guilds error:', error.message)
    res.status(500).json({ error: 'Failed to list guilds' })
  }
})

/**
 * POST /api/admin/guilds/:guild_id/block  Body: { blocked: bool, reason?: string }
 * Block or unblock a guild. A blocked guild leaves the server picker, its
 * dashboard routes return 403, and the bot's per-guild endpoints stop serving it.
 */
router.post('/guilds/:guild_id/block', async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const blocked = !!req.body?.blocked
    const reason = req.body?.reason
    const until = blocked ? (req.body?.until ?? null) : null

    const existing = await getGuild(guildId)
    if (!existing) {
      return res.status(404).json({ error: 'Guild not found' })
    }

    await setGuildBlocked(guildId, blocked, reason, until)
    await logAuditAction(req.user.id, guildId, blocked ? 'ADMIN_BLOCK_GUILD' : 'ADMIN_UNBLOCK_GUILD', {
      reason: blocked ? (reason || null) : null,
      until: blocked ? (until || null) : null
    })

    res.json({ success: true, guild_id: guildId, blocked })
  } catch (error) {
    console.error('Admin block guild error:', error.message)
    res.status(500).json({ error: 'Failed to update guild' })
  }
})

/**
 * POST /api/admin/guilds/:guild_id/premium  Body: { tier, until?: unix-seconds }
 * Owner-only manual premium override (source = 'manual'). `tier` ∈ free|basic|pro.
 * Setting 'free' clears the premium entirely.
 */
router.post('/guilds/:guild_id/premium', async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const tier = req.body?.tier
    const until = req.body?.until ?? null

    if (!PREMIUM_TIERS.includes(tier)) {
      return res.status(400).json({ error: 'tier must be one of: ' + PREMIUM_TIERS.join(', ') })
    }

    const existing = await getGuild(guildId)
    if (!existing) {
      return res.status(404).json({ error: 'Guild not found' })
    }

    await setGuildPremium(guildId, { tier, source: 'manual', until })
    await logAuditAction(req.user.id, guildId, 'ADMIN_SET_PREMIUM', { tier, until: until || null })

    res.json({ success: true, guild_id: guildId, tier, until: tier === 'free' ? null : (until || null) })
  } catch (error) {
    console.error('Admin set premium error:', error.message)
    res.status(500).json({ error: 'Failed to update premium' })
  }
})

/**
 * GET /api/admin/overview
 * Aggregated system metrics for the admin overview dashboard.
 */
router.get('/overview', async (req, res) => {
  try {
    const overview = await getAdminOverview()
    res.json({ success: true, overview })
  } catch (error) {
    console.error('Admin overview error:', error.message)
    res.status(500).json({ error: 'Failed to load overview' })
  }
})

/**
 * GET /api/admin/audit?action=&target=&limit=&offset=
 * Paginated, filterable global audit-log feed (newest first).
 */
router.get('/audit', async (req, res) => {
  try {
    const { action = '', target = '', limit = 50, offset = 0 } = req.query
    const result = await getAuditLogEntries({ action, target, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin audit error:', error.message)
    res.status(500).json({ error: 'Failed to load audit log' })
  }
})

/**
 * GET /api/admin/audit/actions — distinct action names for the filter dropdown.
 */
router.get('/audit/actions', async (req, res) => {
  try {
    const actions = await getAuditActions()
    res.json({ success: true, actions })
  } catch (error) {
    console.error('Admin audit actions error:', error.message)
    res.status(500).json({ error: 'Failed to load audit actions' })
  }
})

/**
 * GET /api/admin/guilds/:guild_id/inspect
 * Read-only snapshot of a guild's module/premium/presence state (support tool).
 */
router.get('/guilds/:guild_id/inspect', async (req, res) => {
  try {
    const inspect = await getGuildInspect(req.params.guild_id)
    if (!inspect) return res.status(404).json({ error: 'Guild not found' })
    res.json({ success: true, inspect })
  } catch (error) {
    console.error('Admin inspect guild error:', error.message)
    res.status(500).json({ error: 'Failed to inspect guild' })
  }
})

/**
 * GET /api/admin/maintenance — current global maintenance state.
 * PUT /api/admin/maintenance  Body: { enabled, message? } — toggle it.
 */
router.get('/maintenance', async (req, res) => {
  try {
    const state = await getMaintenanceState()
    res.json({ success: true, ...state })
  } catch (error) {
    console.error('Admin get maintenance error:', error.message)
    res.status(500).json({ error: 'Failed to load maintenance state' })
  }
})

router.put('/maintenance', async (req, res) => {
  try {
    const enabled = !!req.body?.enabled
    const message = typeof req.body?.message === 'string' ? req.body.message : ''
    await setMaintenanceState({ enabled, message })
    await logAuditAction(req.user.id, null, 'ADMIN_MAINTENANCE', { enabled, message: message || null })
    res.json({ success: true, enabled, message })
  } catch (error) {
    console.error('Admin set maintenance error:', error.message)
    res.status(500).json({ error: 'Failed to update maintenance state' })
  }
})

/**
 * GET /api/admin/health — bot live status (from the botStats cache) + backend
 * process facts. For the Monitoring → Bot-Health panel.
 */
router.get('/health', async (req, res) => {
  try {
    res.json({
      success: true,
      bot: getBotHealth(),
      backend: {
        version: BACKEND_VERSION,
        node: process.version,
        uptime_seconds: Math.floor(process.uptime())
      }
    })
  } catch (error) {
    console.error('Admin health error:', error.message)
    res.status(500).json({ error: 'Failed to load health' })
  }
})

/**
 * GET /api/admin/errors?source=&level=&limit=&offset= — central error feed.
 * DELETE /api/admin/errors — clear the log.
 */
router.get('/errors', async (req, res) => {
  try {
    const { source = '', level = '', limit = 50, offset = 0 } = req.query
    const result = await getErrorLog({ source, level, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin errors error:', error.message)
    res.status(500).json({ error: 'Failed to load errors' })
  }
})

router.delete('/errors', async (req, res) => {
  try {
    const cleared = await clearErrorLog()
    await logAuditAction(req.user.id, null, 'ADMIN_CLEAR_ERRORS', { cleared })
    res.json({ success: true, cleared })
  } catch (error) {
    console.error('Admin clear errors error:', error.message)
    res.status(500).json({ error: 'Failed to clear errors' })
  }
})

/**
 * GET /api/admin/jobs?status=&limit=&offset= — backup job queue across all guilds.
 * POST /api/admin/jobs/:id/retry — requeue a failed job.
 */
router.get('/jobs', async (req, res) => {
  try {
    const { status = '', limit = 50, offset = 0 } = req.query
    const result = await getAllBackupJobs({ status, limit, offset })
    res.json({ success: true, ...result })
  } catch (error) {
    console.error('Admin jobs error:', error.message)
    res.status(500).json({ error: 'Failed to load jobs' })
  }
})

router.post('/jobs/:id/retry', async (req, res) => {
  try {
    const changes = await retryBackupJob(req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Job not found or not failed' })
    await logAuditAction(req.user.id, null, 'ADMIN_RETRY_JOB', { job_id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Admin retry job error:', error.message)
    res.status(500).json({ error: 'Failed to retry job' })
  }
})

/**
 * GET /api/admin/announcement — current global announcement banner.
 * PUT /api/admin/announcement  Body: { enabled, message?, level? } — set it.
 */
router.get('/announcement', async (req, res) => {
  try {
    const state = await getAnnouncementState()
    res.json({ success: true, ...state })
  } catch (error) {
    console.error('Admin get announcement error:', error.message)
    res.status(500).json({ error: 'Failed to load announcement' })
  }
})

router.put('/announcement', async (req, res) => {
  try {
    const enabled = !!req.body?.enabled
    const message = typeof req.body?.message === 'string' ? req.body.message : ''
    const level = ANNOUNCEMENT_LEVELS.includes(req.body?.level) ? req.body.level : 'info'
    await setAnnouncementState({ enabled, message, level })
    await logAuditAction(req.user.id, null, 'ADMIN_ANNOUNCEMENT', { enabled, level, message: message || null })
    res.json({ success: true, enabled, message, level })
  } catch (error) {
    console.error('Admin set announcement error:', error.message)
    res.status(500).json({ error: 'Failed to update announcement' })
  }
})

/**
 * POST /api/admin/broadcast  Body: { message } — enqueue a DM to all server owners.
 * GET  /api/admin/broadcasts — recent broadcasts + their status.
 */
router.post('/broadcast', async (req, res) => {
  try {
    const message = typeof req.body?.message === 'string' ? req.body.message.trim() : ''
    if (!message) return res.status(400).json({ error: 'message required' })
    const { id } = await createBroadcast(message, req.user.id)
    await logAuditAction(req.user.id, null, 'ADMIN_BROADCAST', { broadcast_id: id, message: message.slice(0, 200) })
    res.json({ success: true, id })
  } catch (error) {
    console.error('Admin broadcast error:', error.message)
    res.status(500).json({ error: 'Failed to enqueue broadcast' })
  }
})

router.get('/broadcasts', async (req, res) => {
  try {
    const broadcasts = await getRecentBroadcasts(20)
    res.json({ success: true, broadcasts })
  } catch (error) {
    console.error('Admin broadcasts list error:', error.message)
    res.status(500).json({ error: 'Failed to load broadcasts' })
  }
})

/**
 * GET /api/admin/metrics?days= — daily growth/adoption snapshots (Analytics).
 */
router.get('/metrics', async (req, res) => {
  try {
    const days = Number(req.query.days) || 30
    const snapshots = await getMetricsSnapshots(days)
    res.json({ success: true, snapshots })
  } catch (error) {
    console.error('Admin metrics error:', error.message)
    res.status(500).json({ error: 'Failed to load metrics' })
  }
})

/**
 * GET /api/admin/top-guilds?by=modules|activity — leaderboard for Analytics.
 */
router.get('/top-guilds', async (req, res) => {
  try {
    const by = req.query.by === 'activity' ? 'activity' : 'modules'
    const guilds = await getTopGuilds({ by, limit: 15 })
    res.json({ success: true, by, guilds })
  } catch (error) {
    console.error('Admin top-guilds error:', error.message)
    res.status(500).json({ error: 'Failed to load top guilds' })
  }
})

/**
 * GET /api/admin/users/export  +  /api/admin/guilds/export — CSV download.
 */
router.get('/users/export', async (req, res) => {
  try {
    const rows = await getUsersForExport()
    const csv = toCsv(
      ['discord_id', 'username', 'email', 'blocked', 'blocked_until', 'created_at'],
      rows.map((r) => [r.discord_id, r.username, r.email, r.blocked ? 1 : 0, r.blocked_until || '', r.created_at])
    )
    sendCsv(res, 'projectx-users.csv', csv)
  } catch (error) {
    console.error('Admin export users error:', error.message)
    res.status(500).json({ error: 'Failed to export users' })
  }
})

router.get('/guilds/export', async (req, res) => {
  try {
    const rows = await getGuildsForExport()
    const csv = toCsv(
      ['id', 'guild_name', 'bot_present', 'blocked', 'blocked_until', 'premium_tier', 'premium_source', 'premium_until', 'created_at'],
      rows.map((r) => [r.id, r.guild_name, r.bot_present ? 1 : 0, r.blocked ? 1 : 0, r.blocked_until || '', r.premium_tier || 'free', r.premium_source || '', r.premium_until || '', r.created_at])
    )
    sendCsv(res, 'projectx-guilds.csv', csv)
  } catch (error) {
    console.error('Admin export guilds error:', error.message)
    res.status(500).json({ error: 'Failed to export guilds' })
  }
})

function csvCell(value) {
  const s = value == null ? '' : String(value)
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function toCsv(header, rows) {
  const lines = [header.map(csvCell).join(',')]
  for (const row of rows) lines.push(row.map(csvCell).join(','))
  return lines.join('\r\n')
}

function sendCsv(res, filename, csv) {
  res.setHeader('Content-Type', 'text/csv; charset=utf-8')
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`)
  res.send('﻿' + csv) // BOM so Excel reads UTF-8 correctly
}

// ---------- Template Marketplace (owner-only) ----------

/**
 * POST /api/admin/marketplace/publish
 * Body: { source_guild_id, backup_id, name?, description?, category? }
 * Publish one of the owner's guild snapshots as a public marketplace template.
 */
router.post('/marketplace/publish', async (req, res) => {
  try {
    const { source_guild_id, backup_id, name, description, category } = req.body || {}
    if (!source_guild_id || !backup_id) return res.status(400).json({ error: 'source_guild_id and backup_id required' })
    const snapshot = await getBackup(source_guild_id, backup_id)
    if (!snapshot) return res.status(404).json({ error: 'Snapshot not found' })
    const tpl = await createMarketplaceTemplate(req.user.id, source_guild_id, {
      name, description, category,
      guild_name: snapshot.guild_name,
      guild_icon_url: snapshot.guild_icon_url,
      data: snapshot.data
    })
    await logAuditAction(req.user.id, source_guild_id, 'MARKETPLACE_PUBLISH', { template_id: tpl.id, name: tpl.name })
    res.json({ success: true, template: tpl })
  } catch (error) {
    console.error('Marketplace publish error:', error.message)
    res.status(500).json({ error: 'Failed to publish template' })
  }
})

/** GET /api/admin/marketplace — all templates (any status) for management. */
router.get('/marketplace', async (req, res) => {
  try {
    const templates = await getAdminMarketplaceTemplates()
    res.json({ success: true, templates })
  } catch (error) {
    console.error('Marketplace list error:', error.message)
    res.status(500).json({ error: 'Failed to list templates' })
  }
})

/** PUT /api/admin/marketplace/:id/status  Body: { status } */
router.put('/marketplace/:id/status', async (req, res) => {
  try {
    const changes = await setMarketplaceTemplateStatus(req.params.id, (req.body && req.body.status))
    if (changes === 0) return res.status(404).json({ error: 'Template not found' })
    await logAuditAction(req.user.id, null, 'MARKETPLACE_STATUS', { template_id: req.params.id, status: req.body?.status })
    res.json({ success: true })
  } catch (error) {
    console.error('Marketplace status error:', error.message)
    res.status(500).json({ error: 'Failed to update template' })
  }
})

/** DELETE /api/admin/marketplace/:id */
router.delete('/marketplace/:id', async (req, res) => {
  try {
    const changes = await deleteMarketplaceTemplate(req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'Template not found' })
    await logAuditAction(req.user.id, null, 'MARKETPLACE_DELETE', { template_id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Marketplace delete error:', error.message)
    res.status(500).json({ error: 'Failed to delete template' })
  }
})

export default router
