import express from 'express'
import {
  getBackups,
  getBackup,
  deleteBackup,
  createBackupJob,
  getActiveBackupJobs,
  getUserManageableGuilds,
  userIsGuildAdmin,
  RESTORE_MODES,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const snapshots = await getBackups(guildId)
    const jobs = await getActiveBackupJobs(guildId)
    res.json({ success: true, snapshots, jobs })
  } catch (error) {
    console.error('Get backups error:', error.message)
    res.status(500).json({ error: 'Failed to fetch backups' })
  }
})

// Templates: snapshots from the user's OTHER manageable servers, to apply here.
// Registered before GET /:backup_id so "/templates" isn't captured as an id.
router.get('/templates', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const targetId = req.params.guild_id
    const guilds = await getUserManageableGuilds(req.user.id)
    const sources = []
    for (const g of guilds) {
      if (g.id === targetId || g.blocked) continue
      const snapshots = await getBackups(g.id)
      if (snapshots.length) {
        sources.push({ guild_id: g.id, guild_name: g.guild_name, guild_icon_url: g.guild_icon_url, snapshots })
      }
    }
    res.json({ success: true, sources })
  } catch (error) {
    console.error('Get backup templates error:', error.message)
    res.status(500).json({ error: 'Failed to fetch templates' })
  }
})

// Apply a snapshot from another server (template) to this server. Requires the
// user to be admin/owner of BOTH the source and the target guild. The bot's
// restore matches roles by name (creating missing ones) and skips member-target
// overwrites that don't exist here, so a cross-server apply works unchanged.
router.post('/apply-template', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const targetId = req.params.guild_id
    const sourceGuildId = req.body && req.body.source_guild_id
    const backupId = req.body && req.body.backup_id
    let mode = (req.body && req.body.mode) || 'missing'
    if (!RESTORE_MODES.includes(mode)) mode = 'missing'

    if (!sourceGuildId || !backupId) return res.status(400).json({ error: 'source_guild_id and backup_id required' })
    if (sourceGuildId === targetId) return res.status(400).json({ error: 'Use restore for the same server' })

    const hasSource = await userIsGuildAdmin(req.user.id, sourceGuildId)
    if (!hasSource) return res.status(403).json({ error: 'No access to source server' })

    const snapshot = await getBackup(sourceGuildId, backupId)
    if (!snapshot) return res.status(404).json({ error: 'Snapshot not found' })

    let job
    try {
      job = await createBackupJob(targetId, { type: 'restore', backup_id: backupId, mode })
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, targetId, 'BACKUP_APPLY_TEMPLATE', { source_guild_id: sourceGuildId, backup_id: backupId, mode })
    res.json({ success: true, job })
  } catch (error) {
    console.error('Apply backup template error:', error.message)
    res.status(500).json({ error: 'Failed to apply template' })
  }
})

// Full snapshot incl. data blob — used by the dashboard preview before restoring.
router.get('/:backup_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const snapshot = await getBackup(guildId, req.params.backup_id)
    if (!snapshot) return res.status(404).json({ error: 'Snapshot not found' })
    res.json({ success: true, snapshot })
  } catch (error) {
    console.error('Get backup detail error:', error.message)
    res.status(500).json({ error: 'Failed to fetch backup' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    let job
    try {
      job = await createBackupJob(guildId, { type: 'snapshot' })
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'BACKUP_SNAPSHOT_REQUEST', { job_id: job.id })
    res.json({ success: true, job })
  } catch (error) {
    console.error('Create backup snapshot error:', error.message)
    res.status(500).json({ error: 'Failed to request backup snapshot' })
  }
})

router.post('/:backup_id/restore', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const backupId = req.params.backup_id
    const snapshot = await getBackup(guildId, backupId)
    if (!snapshot) return res.status(404).json({ error: 'Snapshot not found' })

    let mode = (req.body && req.body.mode) || 'missing'
    if (!RESTORE_MODES.includes(mode)) mode = 'missing'

    let job
    try {
      job = await createBackupJob(guildId, { type: 'restore', backup_id: backupId, mode })
    } catch (err) {
      if (err && err.code === 'VALIDATION') return res.status(400).json({ error: err.message })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'BACKUP_RESTORE_REQUEST', { backup_id: backupId, mode })
    res.json({ success: true, job })
  } catch (error) {
    console.error('Create backup restore error:', error.message)
    res.status(500).json({ error: 'Failed to request backup restore' })
  }
})

router.delete('/:backup_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const changes = await deleteBackup(guildId, req.params.backup_id)
    if (changes === 0) return res.status(404).json({ error: 'Snapshot not found' })
    await logAuditAction(req.user.id, guildId, 'BACKUP_DELETE', { backup_id: req.params.backup_id })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete backup error:', error.message)
    res.status(500).json({ error: 'Failed to delete backup' })
  }
})

export default router
