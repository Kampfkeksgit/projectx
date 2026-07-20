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
  getLegalInfo,
  setLegalInfo,
  getUsersForExport,
  getGuildsForExport,
  getBackup,
  createMarketplaceTemplate,
  getAdminMarketplaceTemplates,
  getMarketplaceTemplate,
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
  getRecentBroadcasts,
  createPremiumCode,
  getTeamMembers,
  createTeamMember,
  updateTeamMember,
  deleteTeamMember,
  getPartners,
  createPartner,
  updatePartner,
  deletePartner,
  getChangelogEntries,
  createChangelogEntry,
  updateChangelogEntry,
  deleteChangelogEntry,
  getChangelogChannel,
  setChangelogChannel,
  getPremiumCodes,
  deletePremiumCode,
  getRevenue
} from '../db.js'
import { getBotHealth } from '../state/botStats.js'
import { requireSession, requireOwner, requireAdmin, isOwner } from '../middleware/session.js'
import {
  adminCan,
  getAdminStaff,
  upsertAdminStaff,
  removeAdminStaff,
  ADMIN_PERM_TABS
} from '../db.js'
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
// Prefer an APP_VERSION injected at deploy (e.g. git short SHA) so the panel
// reflects the actual build; fall back to package.json.
let BACKEND_VERSION = process.env.APP_VERSION || null
if (!BACKEND_VERSION) {
  try { BACKEND_VERSION = require('../package.json').version || null } catch { BACKEND_VERSION = null }
}

const router = express.Router()

// Admin access = env owner OR a configured staff member (admin_staff row).
// requireAdmin resolves the effective access map onto req.adminAccess.
router.use(requireSession, requireAdmin)

// Per-tab permission policy. First match wins; unmapped routes fail closed for
// staff (owner is always allowed). Each rule: [METHOD, pathRegex, tab, level].
// NOTE: when adding a new admin route, add a rule here too (or staff get 403).
const PERM_RULES = [
  ['GET',    /^\/overview$/,                  'overview',    'view'],
  ['GET',    /^\/metrics$/,                   'analytics',   'view'],
  ['GET',    /^\/top-guilds$/,                'analytics',   'view'],
  ['GET',    /^\/revenue$/,                   'premium',     'view'],
  ['GET',    /^\/premium-codes$/,             'premium',     'view'],
  ['POST',   /^\/premium-codes$/,             'premium',     'manage'],
  ['DELETE', /^\/premium-codes\/[^/]+$/,      'premium',     'manage'],
  ['GET',    /^\/health$/,                    'health',      'view'],
  ['GET',    /^\/users$/,                     'users',       'view'],
  ['GET',    /^\/users\/export$/,             'users',       'view'],
  ['POST',   /^\/users\/[^/]+\/block$/,       'users',       'manage'],
  ['GET',    /^\/guilds$/,                    'guilds',      'view'],
  ['GET',    /^\/guilds\/export$/,            'guilds',      'view'],
  ['GET',    /^\/guilds\/[^/]+\/inspect$/,    'guilds',      'view'],
  ['POST',   /^\/guilds\/[^/]+\/block$/,      'guilds',      'manage'],
  ['POST',   /^\/guilds\/[^/]+\/premium$/,    'guilds',      'manage'],
  ['GET',    /^\/audit$/,                     'audit',       'view'],
  ['GET',    /^\/audit\/actions$/,            'audit',       'view'],
  ['GET',    /^\/jobs$/,                      'jobs',        'view'],
  ['POST',   /^\/jobs\/[^/]+\/retry$/,        'jobs',        'manage'],
  ['GET',    /^\/errors$/,                    'errors',      'view'],
  ['DELETE', /^\/errors$/,                    'errors',      'manage'],
  ['GET',    /^\/marketplace$/,               'marketplace', 'view'],
  ['GET',    /^\/marketplace\/[^/]+\/export$/,'marketplace', 'view'],
  ['POST',   /^\/marketplace\/publish$/,      'marketplace', 'manage'],
  ['POST',   /^\/marketplace\/upload$/,       'marketplace', 'manage'],
  ['PUT',    /^\/marketplace\/[^/]+\/status$/,'marketplace', 'manage'],
  ['DELETE', /^\/marketplace\/[^/]+$/,        'marketplace', 'manage'],
  ['GET',    /^\/team$/,                      'team',        'view'],
  ['POST',   /^\/team$/,                      'team',        'manage'],
  ['PUT',    /^\/team\/[^/]+$/,               'team',        'manage'],
  ['DELETE', /^\/team\/[^/]+$/,               'team',        'manage'],
  ['GET',    /^\/partners$/,                  'partners',    'view'],
  ['POST',   /^\/partners$/,                  'partners',    'manage'],
  ['PUT',    /^\/partners\/[^/]+$/,           'partners',    'manage'],
  ['DELETE', /^\/partners\/[^/]+$/,           'partners',    'manage'],
  ['GET',    /^\/changelog$/,                 'changelog',   'view'],
  ['PUT',    /^\/changelog\/channel$/,        'changelog',   'manage'],
  ['POST',   /^\/changelog$/,                 'changelog',   'manage'],
  ['PUT',    /^\/changelog\/[^/]+$/,          'changelog',   'manage'],
  ['DELETE', /^\/changelog\/[^/]+$/,          'changelog',   'manage'],
  ['GET',    /^\/maintenance$/,               'system',      'view'],
  ['PUT',    /^\/maintenance$/,               'system',      'manage'],
  ['GET',    /^\/announcement$/,              'system',      'view'],
  ['PUT',    /^\/announcement$/,              'system',      'manage'],
  ['GET',    /^\/legal$/,                     'system',      'view'],
  ['PUT',    /^\/legal$/,                     'system',      'manage'],
  ['POST',   /^\/broadcast$/,                 'system',      'manage'],
  ['GET',    /^\/broadcasts$/,                'system',      'view']
]

router.use((req, res, next) => {
  // Path relative to /api/admin, regardless of how Express reports req.path.
  let p = req.path || '/'
  if (req.baseUrl && p.startsWith(req.baseUrl)) p = p.slice(req.baseUrl.length) || '/'

  // Own access info — available to any admin.
  if (p === '/access') return next()
  // Staff management is owner-only.
  if (p === '/staff' || p.startsWith('/staff/')) {
    if (!req.user?.is_owner) return res.status(403).json({ error: 'Owner access required' })
    return next()
  }

  const rule = PERM_RULES.find(([m, re]) => m === req.method && re.test(p))
  if (!rule) {
    // Unmapped route: owner still allowed, staff denied (fail closed).
    if (req.user?.is_owner) return next()
    return res.status(403).json({ error: 'forbidden' })
  }
  const [, , tab, level] = rule
  if (!adminCan(req.adminAccess, tab, level)) {
    return res.status(403).json({ error: 'permission_required', tab, required: level })
  }
  next()
})

// ----- Own admin access (any admin) + staff management (owner-only) -----

// The current user's effective admin access (drives tab visibility + gating).
router.get('/access', async (req, res) => {
  res.json({
    success: true,
    is_owner: !!req.adminAccess?.is_owner,
    is_staff: !!req.adminAccess?.is_staff,
    permissions: req.adminAccess?.permissions || {},
    tabs: ADMIN_PERM_TABS
  })
})

router.get('/staff', async (req, res) => {
  try {
    res.json({ success: true, staff: await getAdminStaff(), tabs: ADMIN_PERM_TABS })
  } catch (error) {
    console.error('Admin get staff error:', error.message)
    res.status(500).json({ error: 'Failed to fetch staff' })
  }
})

router.post('/staff', async (req, res) => {
  try {
    const body = req.body || {}
    const userId = String(body.user_id || '').trim()
    if (isOwner(userId)) return res.status(400).json({ error: 'is_owner' })
    let member
    try {
      member = await upsertAdminStaff(userId, { permissions: body.permissions, note: body.note, addedBy: req.user.id })
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'invalid_user' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_STAFF_UPSERT', { user_id: userId })
    res.json({ success: true, member })
  } catch (error) {
    console.error('Admin upsert staff error:', error.message)
    res.status(500).json({ error: 'Failed to save staff' })
  }
})

router.delete('/staff/:user_id', async (req, res) => {
  try {
    const changes = await removeAdminStaff(req.params.user_id)
    if (changes === 0) return res.status(404).json({ error: 'not_found' })
    await logAuditAction(req.user.id, null, 'ADMIN_STAFF_REMOVE', { user_id: req.params.user_id })
    res.json({ success: true })
  } catch (error) {
    console.error('Admin remove staff error:', error.message)
    res.status(500).json({ error: 'Failed to remove staff' })
  }
})

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
    const { search = '', limit = 100, offset = 0, present = '' } = req.query
    const result = await getAdminGuilds({ search, limit, offset, present })
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
 * GET /api/admin/legal — operator / legal contact info (Impressum + Datenschutz).
 * PUT /api/admin/legal Body: { name, street, postal_code, city, country, email, phone }
 * Editable owner PII; the public legal pages substitute it into the text.
 */
router.get('/legal', async (req, res) => {
  try {
    const info = await getLegalInfo()
    res.json({ success: true, info })
  } catch (error) {
    console.error('Admin get legal error:', error.message)
    res.status(500).json({ error: 'Failed to load legal info' })
  }
})

router.put('/legal', async (req, res) => {
  try {
    const body = req.body || {}
    await setLegalInfo(body)
    const info = await getLegalInfo()
    await logAuditAction(req.user.id, null, 'ADMIN_LEGAL', { name: info.name || null, city: info.city || null })
    res.json({ success: true, info })
  } catch (error) {
    console.error('Admin set legal error:', error.message)
    res.status(500).json({ error: 'Failed to update legal info' })
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
 * Premium codes (Owner admin → Premium).
 *   POST   /api/admin/premium-codes  Body: { tier, duration_days?, max_uses?, expires_at? }
 *   GET    /api/admin/premium-codes
 *   DELETE /api/admin/premium-codes/:code
 */
router.post('/premium-codes', async (req, res) => {
  try {
    const { tier, duration_days, max_uses, expires_at, code: customCode } = req.body || {}
    if (!PREMIUM_TIERS.includes(tier) || tier === 'free') {
      return res.status(400).json({ error: 'tier must be basic or pro' })
    }
    let code
    try {
      code = await createPremiumCode({
        tier,
        duration_days: Number(duration_days),
        max_uses: Number(max_uses),
        expires_at: expires_at ? Number(expires_at) : null,
        createdBy: req.user.id,
        code: customCode
      })
    } catch (err) {
      if (err && err.code === 'DUPLICATE') return res.status(409).json({ error: 'code_exists' })
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'invalid_code' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_PREMIUM_CODE_CREATE', { code: code.code, tier: code.tier, duration_days: code.duration_days, max_uses: code.max_uses })
    res.json({ success: true, code })
  } catch (error) {
    console.error('Admin create premium code error:', error.message)
    res.status(500).json({ error: 'Failed to create code' })
  }
})

router.get('/premium-codes', async (req, res) => {
  try {
    const codes = await getPremiumCodes()
    res.json({ success: true, codes })
  } catch (error) {
    console.error('Admin list premium codes error:', error.message)
    res.status(500).json({ error: 'Failed to load codes' })
  }
})

router.delete('/premium-codes/:code', async (req, res) => {
  try {
    const changes = await deletePremiumCode(req.params.code)
    if (changes === 0) return res.status(404).json({ error: 'Code not found' })
    await logAuditAction(req.user.id, null, 'ADMIN_PREMIUM_CODE_DELETE', { code: req.params.code })
    res.json({ success: true })
  } catch (error) {
    console.error('Admin delete premium code error:', error.message)
    res.status(500).json({ error: 'Failed to delete code' })
  }
})

// ----- Team / credits management (owner) -----

router.get('/team', async (req, res) => {
  try {
    res.json({ success: true, members: await getTeamMembers() })
  } catch (error) {
    console.error('Admin get team error:', error.message)
    res.status(500).json({ error: 'Failed to fetch team' })
  }
})

router.post('/team', async (req, res) => {
  try {
    let member
    try {
      member = await createTeamMember(req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'name_required' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_TEAM_CREATE', { id: member.id, name: member.name })
    res.json({ success: true, member })
  } catch (error) {
    console.error('Admin create team member error:', error.message)
    res.status(500).json({ error: 'Failed to create team member' })
  }
})

router.put('/team/:id', async (req, res) => {
  try {
    let member
    try {
      member = await updateTeamMember(req.params.id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'not_found' })
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'name_required' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_TEAM_UPDATE', { id: member.id })
    res.json({ success: true, member })
  } catch (error) {
    console.error('Admin update team member error:', error.message)
    res.status(500).json({ error: 'Failed to update team member' })
  }
})

router.delete('/team/:id', async (req, res) => {
  try {
    const changes = await deleteTeamMember(req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'not_found' })
    await logAuditAction(req.user.id, null, 'ADMIN_TEAM_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Admin delete team member error:', error.message)
    res.status(500).json({ error: 'Failed to delete team member' })
  }
})

// ----- Partners management (owner) -----

router.get('/partners', async (req, res) => {
  try {
    res.json({ success: true, partners: await getPartners() })
  } catch (error) {
    console.error('Admin get partners error:', error.message)
    res.status(500).json({ error: 'Failed to fetch partners' })
  }
})

router.post('/partners', async (req, res) => {
  try {
    let partner
    try {
      partner = await createPartner(req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'partner_invalid' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_PARTNER_CREATE', { id: partner.id, kind: partner.kind })
    res.json({ success: true, partner })
  } catch (error) {
    console.error('Admin create partner error:', error.message)
    res.status(500).json({ error: 'Failed to create partner' })
  }
})

router.put('/partners/:id', async (req, res) => {
  try {
    let partner
    try {
      partner = await updatePartner(req.params.id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'not_found' })
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'partner_invalid' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_PARTNER_UPDATE', { id: partner.id })
    res.json({ success: true, partner })
  } catch (error) {
    console.error('Admin update partner error:', error.message)
    res.status(500).json({ error: 'Failed to update partner' })
  }
})

router.delete('/partners/:id', async (req, res) => {
  try {
    const changes = await deletePartner(req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'not_found' })
    await logAuditAction(req.user.id, null, 'ADMIN_PARTNER_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Admin delete partner error:', error.message)
    res.status(500).json({ error: 'Failed to delete partner' })
  }
})

// ----- Changelog publisher (owner-only) -----

router.get('/changelog', async (req, res) => {
  try {
    const [entries, channel_id] = await Promise.all([getChangelogEntries(), getChangelogChannel()])
    res.json({ success: true, entries, channel_id: channel_id || '' })
  } catch (error) {
    console.error('Admin get changelog error:', error.message)
    res.status(500).json({ error: 'Failed to fetch changelog' })
  }
})

// Registered BEFORE '/changelog/:id' so 'channel' isn't captured as an id.
router.put('/changelog/channel', async (req, res) => {
  try {
    await setChangelogChannel(req.body?.channel_id)
    const channel_id = await getChangelogChannel()
    await logAuditAction(req.user.id, null, 'ADMIN_CHANGELOG_CHANNEL', { channel_id: channel_id || '' })
    res.json({ success: true, channel_id: channel_id || '' })
  } catch (error) {
    console.error('Admin set changelog channel error:', error.message)
    res.status(500).json({ error: 'Failed to set changelog channel' })
  }
})

router.post('/changelog', async (req, res) => {
  try {
    let entry
    try {
      entry = await createChangelogEntry(req.body || {})
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'title_required' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_CHANGELOG_CREATE', { id: entry.id, version: entry.version, published: entry.published })
    res.json({ success: true, entry })
  } catch (error) {
    console.error('Admin create changelog error:', error.message)
    res.status(500).json({ error: 'Failed to create changelog entry' })
  }
})

router.put('/changelog/:id', async (req, res) => {
  try {
    let entry
    try {
      entry = await updateChangelogEntry(req.params.id, req.body || {})
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'not_found' })
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: 'title_required' })
      throw err
    }
    await logAuditAction(req.user.id, null, 'ADMIN_CHANGELOG_UPDATE', { id: entry.id, published: entry.published })
    res.json({ success: true, entry })
  } catch (error) {
    console.error('Admin update changelog error:', error.message)
    res.status(500).json({ error: 'Failed to update changelog entry' })
  }
})

router.delete('/changelog/:id', async (req, res) => {
  try {
    const changes = await deleteChangelogEntry(req.params.id)
    if (changes === 0) return res.status(404).json({ error: 'not_found' })
    await logAuditAction(req.user.id, null, 'ADMIN_CHANGELOG_DELETE', { id: req.params.id })
    res.json({ success: true })
  } catch (error) {
    console.error('Admin delete changelog error:', error.message)
    res.status(500).json({ error: 'Failed to delete changelog entry' })
  }
})

/** GET /api/admin/revenue — estimated MRR from active premium (Analytics/Premium). */
router.get('/revenue', async (req, res) => {
  try {
    const revenue = await getRevenue()
    res.json({ success: true, revenue })
  } catch (error) {
    console.error('Admin revenue error:', error.message)
    res.status(500).json({ error: 'Failed to load revenue' })
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

/**
 * POST /api/admin/marketplace/upload
 * Body: { name?, description?, category?, guild_name?, guild_icon_url?, data }
 * Upload a template directly (no source guild needed). `data` is a snapshot blob
 * { server, roles, channels } — either raw, or wrapped in a previously exported
 * file ({ ..., data: {...} }). The template appears in the marketplace at once.
 */
router.post('/marketplace/upload', async (req, res) => {
  try {
    const body = req.body || {}
    // Accept both a raw snapshot blob and a full exported file (which nests it under `data`).
    const raw = (body.data && typeof body.data === 'object' && (body.data.data || body.data)) || body.data
    let data = raw
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch { data = null }
    }
    if (!data || typeof data !== 'object' || (!Array.isArray(data.roles) && !Array.isArray(data.channels))) {
      return res.status(400).json({ error: 'invalid_template', message: 'data must contain a roles and/or channels array' })
    }
    if ((data.roles || []).length === 0 && (data.channels || []).length === 0) {
      return res.status(400).json({ error: 'empty_template', message: 'template has no roles or channels' })
    }
    // Fall back to the snapshot's own server name / the export's guild_name for display.
    const guildName = body.guild_name || (body.data && body.data.guild_name) || (data.server && data.server.name) || null
    const guildIcon = body.guild_icon_url || (body.data && body.data.guild_icon_url) || (data.server && data.server.icon_url) || null
    const tpl = await createMarketplaceTemplate(req.user.id, null, {
      name: body.name || (body.data && body.data.name),
      description: body.description || (body.data && body.data.description),
      category: body.category || (body.data && body.data.category),
      guild_name: guildName,
      guild_icon_url: guildIcon,
      data
    })
    await logAuditAction(req.user.id, null, 'MARKETPLACE_UPLOAD', { template_id: tpl.id, name: tpl.name })
    res.json({ success: true, template: tpl })
  } catch (error) {
    console.error('Marketplace upload error:', error.message)
    res.status(500).json({ error: 'Failed to upload template' })
  }
})

/**
 * GET /api/admin/marketplace/:id/export
 * Download a template (incl. its full data blob) as a re-importable JSON file.
 */
router.get('/marketplace/:id/export', async (req, res) => {
  try {
    const tpl = await getMarketplaceTemplate(req.params.id)
    if (!tpl) return res.status(404).json({ error: 'Template not found' })
    const exported = {
      format_version: 1,
      name: tpl.name,
      description: tpl.description,
      category: tpl.category,
      guild_name: tpl.guild_name,
      guild_icon_url: tpl.guild_icon_url,
      channels_count: tpl.channels_count,
      roles_count: tpl.roles_count,
      data: tpl.data
    }
    await logAuditAction(req.user.id, null, 'MARKETPLACE_EXPORT', { template_id: tpl.id })
    const slug = String(tpl.name || 'template').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'template'
    res.setHeader('Content-Type', 'application/json; charset=utf-8')
    res.setHeader('Content-Disposition', `attachment; filename="template-${slug}.json"`)
    res.send(JSON.stringify(exported, null, 2))
  } catch (error) {
    console.error('Marketplace export error:', error.message)
    res.status(500).json({ error: 'Failed to export template' })
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
