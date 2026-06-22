import express from 'express'
import {
  getBackups,
  getBackup,
  deleteBackup,
  createBackupJob,
  getActiveBackupJobs,
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
