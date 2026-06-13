import express from 'express'
import {
  getCustomCommands,
  createCustomCommand,
  updateCustomCommand,
  deleteCustomCommand,
  BUILTIN_COMMANDS,
  getCommandSettings,
  setCommandEnabled,
  getCommandPrefix,
  setCommandPrefix,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

const MATCH_TYPES = ['exact', 'contains', 'starts_with']

// ----- Command manager (built-in commands catalog + prefix) -----
// Registered before the /:cmd_id routes so the literal paths win.

router.get('/catalog', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const [prefix, settings] = await Promise.all([getCommandPrefix(guildId), getCommandSettings(guildId)])
    res.json({ success: true, prefix, catalog: BUILTIN_COMMANDS, settings })
  } catch (error) {
    console.error('Get command catalog error:', error.message)
    res.status(500).json({ error: 'Failed to fetch command catalog' })
  }
})

router.put('/prefix', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const prefix = await setCommandPrefix(guildId, (req.body || {}).prefix)
    await logAuditAction(req.user.id, guildId, 'COMMAND_PREFIX_UPDATE', { prefix })
    res.json({ success: true, prefix })
  } catch (error) {
    console.error('Set command prefix error:', error.message)
    res.status(500).json({ error: 'Failed to update prefix' })
  }
})

router.put('/toggle/:key', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const enabled = Boolean((req.body || {}).enabled)
    try {
      await setCommandEnabled(guildId, req.params.key, enabled)
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') return res.status(404).json({ error: 'Unknown command' })
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'COMMAND_TOGGLE', { key: req.params.key, enabled })
    res.json({ success: true, key: req.params.key, enabled })
  } catch (error) {
    console.error('Toggle command error:', error.message)
    res.status(500).json({ error: 'Failed to toggle command' })
  }
})

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const commands = await getCustomCommands(guildId)
    res.json({ success: true, commands })
  } catch (error) {
    console.error('Get custom commands error:', error.message)
    res.status(500).json({ error: 'Failed to fetch custom commands' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    if (typeof body.trigger !== 'string' || body.trigger.trim().length === 0) {
      return res.status(400).json({ error: 'trigger required' })
    }
    if (typeof body.response !== 'string' || body.response.length === 0) {
      return res.status(400).json({ error: 'response required' })
    }
    if (body.match_type !== undefined && !MATCH_TYPES.includes(body.match_type)) {
      return res.status(400).json({ error: 'match_type must be one of: ' + MATCH_TYPES.join(', ') })
    }

    let command
    try {
      command = await createCustomCommand(guildId, {
        trigger: body.trigger,
        response: body.response,
        match_type: body.match_type,
        enabled: body.enabled !== undefined ? Boolean(body.enabled) : true
      })
    } catch (err) {
      if (err && /UNIQUE constraint failed/i.test(err.message)) {
        return res.status(409).json({ error: 'Trigger already exists' })
      }
      if (err && err.code === 'VALIDATION') {
        return res.status(400).json({ error: err.message })
      }
      throw err
    }

    await logAuditAction(req.user.id, guildId, 'CC_CREATE', {
      id: command.id,
      trigger: command.trigger,
      match_type: command.match_type,
      enabled: command.enabled
    })

    res.json({ success: true, command })
  } catch (error) {
    console.error('Create custom command error:', error.message)
    res.status(500).json({ error: 'Failed to create custom command' })
  }
})

router.put('/:cmd_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const cmdId = Number(req.params.cmd_id)
    if (!Number.isInteger(cmdId) || cmdId <= 0) {
      return res.status(400).json({ error: 'Invalid cmd_id' })
    }
    const body = req.body || {}
    if (body.match_type !== undefined && !MATCH_TYPES.includes(body.match_type)) {
      return res.status(400).json({ error: 'match_type must be one of: ' + MATCH_TYPES.join(', ') })
    }

    let command
    try {
      command = await updateCustomCommand(guildId, cmdId, body)
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') {
        return res.status(404).json({ error: 'Custom command not found' })
      }
      if (err && err.code === 'VALIDATION') {
        return res.status(400).json({ error: err.message })
      }
      if (err && /UNIQUE constraint failed/i.test(err.message)) {
        return res.status(409).json({ error: 'Trigger already exists' })
      }
      throw err
    }

    await logAuditAction(req.user.id, guildId, 'CC_UPDATE', {
      id: command.id,
      trigger: command.trigger,
      match_type: command.match_type,
      enabled: command.enabled
    })

    res.json({ success: true, command })
  } catch (error) {
    console.error('Update custom command error:', error.message)
    res.status(500).json({ error: 'Failed to update custom command' })
  }
})

router.delete('/:cmd_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const cmdId = Number(req.params.cmd_id)
    if (!Number.isInteger(cmdId) || cmdId <= 0) {
      return res.status(400).json({ error: 'Invalid cmd_id' })
    }
    const changes = await deleteCustomCommand(guildId, cmdId)
    if (changes === 0) {
      return res.status(404).json({ error: 'Custom command not found' })
    }
    await logAuditAction(req.user.id, guildId, 'CC_DELETE', { id: cmdId })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete custom command error:', error.message)
    res.status(500).json({ error: 'Failed to delete custom command' })
  }
})

export default router
