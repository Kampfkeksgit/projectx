import express from 'express'
import {
  SOCIAL_PLATFORMS,
  getSocialSubscriptions,
  createSocialSubscription,
  updateSocialSubscription,
  deleteSocialSubscription,
  logAuditAction
} from '../db.js'
import { requireGuildAccess } from '../middleware/auth.js'
import { requireSession } from '../middleware/session.js'

const router = express.Router({ mergeParams: true })

router.get('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const subscriptions = await getSocialSubscriptions(guildId)
    res.json({ success: true, subscriptions })
  } catch (error) {
    console.error('Get social subscriptions error:', error.message)
    res.status(500).json({ error: 'Failed to fetch social subscriptions' })
  }
})

router.post('/', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const body = req.body || {}

    if (body.platform !== undefined && !SOCIAL_PLATFORMS.includes(body.platform)) {
      return res.status(400).json({ error: 'platform must be one of: ' + SOCIAL_PLATFORMS.join(', ') })
    }

    let subscription
    try {
      subscription = await createSocialSubscription(guildId, body)
    } catch (err) {
      if (err && /UNIQUE constraint failed/i.test(err.message)) {
        return res.status(409).json({ error: 'This account is already tracked on this platform' })
      }
      if (err && err.code === 'VALIDATION') {
        return res.status(400).json({ error: err.message })
      }
      throw err
    }

    await logAuditAction(req.user.id, guildId, 'SOCIAL_CREATE', {
      id: subscription.id,
      platform: subscription.platform,
      account: subscription.account,
      channel_id: subscription.channel_id
    })

    res.json({ success: true, subscription })
  } catch (error) {
    console.error('Create social subscription error:', error.message)
    res.status(500).json({ error: 'Failed to create social subscription' })
  }
})

router.put('/:sub_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const subId = req.params.sub_id
    const body = req.body || {}

    if (body.platform !== undefined && !SOCIAL_PLATFORMS.includes(body.platform)) {
      return res.status(400).json({ error: 'platform must be one of: ' + SOCIAL_PLATFORMS.join(', ') })
    }

    let subscription
    try {
      subscription = await updateSocialSubscription(guildId, subId, body)
    } catch (err) {
      if (err && err.code === 'NOT_FOUND') {
        return res.status(404).json({ error: 'Social subscription not found' })
      }
      if (err && err.code === 'VALIDATION') {
        return res.status(400).json({ error: err.message })
      }
      if (err && /UNIQUE constraint failed/i.test(err.message)) {
        return res.status(409).json({ error: 'This account is already tracked on this platform' })
      }
      throw err
    }

    await logAuditAction(req.user.id, guildId, 'SOCIAL_UPDATE', {
      id: subscription.id,
      platform: subscription.platform,
      account: subscription.account,
      enabled: subscription.enabled
    })

    res.json({ success: true, subscription })
  } catch (error) {
    console.error('Update social subscription error:', error.message)
    res.status(500).json({ error: 'Failed to update social subscription' })
  }
})

router.delete('/:sub_id', requireSession, requireGuildAccess, async (req, res) => {
  try {
    const guildId = req.params.guild_id
    const subId = req.params.sub_id
    const changes = await deleteSocialSubscription(guildId, subId)
    if (changes === 0) {
      return res.status(404).json({ error: 'Social subscription not found' })
    }
    await logAuditAction(req.user.id, guildId, 'SOCIAL_DELETE', { id: subId })
    res.json({ success: true })
  } catch (error) {
    console.error('Delete social subscription error:', error.message)
    res.status(500).json({ error: 'Failed to delete social subscription' })
  }
})

export default router
