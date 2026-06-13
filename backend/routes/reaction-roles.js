import express from 'express'
import {
  getReactionRoleMessages,
  createReactionRoleMessage,
  updateReactionRoleMessage,
  deleteReactionRoleMessage,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

const SNOWFLAKE_REGEX = /^\d{15,25}$/
const MAX_MAPPINGS = 25
const MAX_NAME_LEN = 100

/**
 * Validate the incoming reaction-role body. Returns an array of human-readable
 * error strings (empty array = valid).
 */
function validateBody(body) {
  const errors = []
  if (!body || typeof body !== 'object') {
    errors.push('Body must be an object')
    return errors
  }
  if (!SNOWFLAKE_REGEX.test(body.channel_id || '')) {
    errors.push('channel_id must be a Discord snowflake')
  }
  if (!SNOWFLAKE_REGEX.test(body.message_id || '')) {
    errors.push('message_id must be a Discord snowflake')
  }
  if (body.name !== undefined && body.name !== null && typeof body.name !== 'string') {
    errors.push('name must be a string')
  }

  const mappings = Array.isArray(body.mappings) ? body.mappings : null
  if (!mappings || mappings.length === 0) {
    errors.push('mappings must be a non-empty array')
  } else if (mappings.length > MAX_MAPPINGS) {
    errors.push(`mappings limited to ${MAX_MAPPINGS} entries`)
  } else {
    for (const [i, m] of mappings.entries()) {
      if (!m || typeof m !== 'object') {
        errors.push(`mapping[${i}] must be an object`)
        continue
      }
      if (typeof m.emoji !== 'string' || m.emoji.trim().length === 0) {
        errors.push(`mapping[${i}].emoji must be a non-empty string`)
      }
      if (!SNOWFLAKE_REGEX.test(m.role_id || '')) {
        errors.push(`mapping[${i}].role_id must be a Discord snowflake`)
      }
    }
  }
  return errors
}

function shapeBody(body) {
  return {
    channel_id: String(body.channel_id),
    message_id: String(body.message_id),
    name: typeof body.name === 'string' ? body.name.slice(0, MAX_NAME_LEN) : null,
    exclusive: Boolean(body.exclusive),
    mappings: body.mappings.map((m) => ({
      emoji: String(m.emoji).trim(),
      role_id: String(m.role_id)
    }))
  }
}

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const messages = await getReactionRoleMessages(guildId)
    res.json({ success: true, messages })
  } catch (error) {
    console.error('Get reaction roles error:', error.message)
    res.status(500).json({ error: 'Failed to fetch reaction roles' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}
    const errors = validateBody(body)
    if (errors.length > 0) {
      return res.status(400).json({ error: 'Validation failed', details: errors })
    }
    const shaped = shapeBody(body)
    const created = await createReactionRoleMessage(guildId, shaped)
    await logAuditAction(req.user.id, guildId, 'RR_CREATE', {
      id: created.id,
      channel_id: created.channel_id,
      message_id: created.message_id,
      mappings: created.mappings
    })
    res.json({ success: true, message: created })
  } catch (error) {
    if (error && /UNIQUE constraint failed/i.test(error.message)) {
      return res.status(409).json({ error: 'A reaction role already exists for this message' })
    }
    console.error('Create reaction role error:', error.message)
    res.status(500).json({ error: 'Failed to create reaction role' })
  }
})

router.put('/:rr_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const rrId = req.params.rr_id
    if (typeof rrId !== 'string' || rrId.length === 0) {
      return res.status(400).json({ error: 'Invalid rr_id' })
    }
    const body = req.body || {}
    const errors = validateBody(body)
    if (errors.length > 0) {
      return res.status(400).json({ error: 'Validation failed', details: errors })
    }
    const shaped = shapeBody(body)
    let updated
    try {
      updated = await updateReactionRoleMessage(guildId, rrId, shaped)
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') {
        return res.status(404).json({ error: 'Reaction role not found' })
      }
      throw err
    }
    await logAuditAction(req.user.id, guildId, 'RR_UPDATE', {
      id: updated.id,
      channel_id: updated.channel_id,
      message_id: updated.message_id,
      mappings: updated.mappings
    })
    res.json({ success: true, message: updated })
  } catch (error) {
    if (error && /UNIQUE constraint failed/i.test(error.message)) {
      return res.status(409).json({ error: 'A reaction role already exists for this message' })
    }
    console.error('Update reaction role error:', error.message)
    res.status(500).json({ error: 'Failed to update reaction role' })
  }
})

router.delete('/:rr_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const rrId = req.params.rr_id
    const changes = await deleteReactionRoleMessage(guildId, rrId)
    if (changes === 0) {
      return res.status(404).json({ error: 'Reaction role not found' })
    }
    await logAuditAction(req.user.id, guildId, 'RR_DELETE', { id: rrId })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete reaction role error:', error.message)
    res.status(500).json({ error: 'Failed to delete reaction role' })
  }
})

export default router
