import express from 'express'
import cors from 'cors'
import cookieParser from 'cookie-parser'
import dotenv from 'dotenv'
import { initializeSchemaVersion, checkAndApplyMigrations } from './migrations.js'
import { whenDbReady } from './db.js'
import authRoutes from './routes/auth.js'
import guildRoutes from './routes/guilds.js'
import settingsRoutes from './routes/settings.js'
import modulesRoutes from './routes/modules.js'
import resourcesRoutes from './routes/resources.js'
import reactionRolesRoutes from './routes/reaction-roles.js'
import levelingRoutes from './routes/leveling.js'
import customCommandsRoutes from './routes/custom-commands.js'
import socialRoutes from './routes/social.js'
import statsRoutes from './routes/stats.js'
import tempvoiceRoutes from './routes/tempvoice.js'
import starboardRoutes from './routes/starboard.js'
import suggestionsRoutes from './routes/suggestions.js'
import birthdayRoutes from './routes/birthday.js'
import scheduledRoutes from './routes/scheduled.js'
import antiraidRoutes from './routes/antiraid.js'
import verificationRoutes from './routes/verification.js'
import roleMenusRoutes from './routes/rolemenus.js'
import ticketsRoutes from './routes/tickets.js'
import giveawaysRoutes from './routes/giveaways.js'
import countingRoutes from './routes/counting.js'
import pollsRoutes from './routes/polls.js'
import inviteTrackingRoutes from './routes/invitetracking.js'
import applicationsRoutes from './routes/applications.js'
import economyRoutes from './routes/economy.js'
import gamesRoutes from './routes/games.js'
import backupRoutes from './routes/backup.js'
import publicRoutes from './routes/public.js'
import adminRoutes from './routes/admin.js'
import premiumRoutes from './routes/premium.js'
import botRoutes from './routes/bot.js'
import { requirePremiumModule } from './middleware/premium.js'
import { maintenanceGate } from './middleware/maintenance.js'

dotenv.config()

// Warn loudly if critical secrets are missing — but DO NOT crash; devs may
// not have them set yet, and individual routes guard themselves.
if (!process.env.SESSION_SECRET) {
  console.warn('⚠️  SESSION_SECRET is not set — session cookies cannot be signed/verified.')
}
if (!process.env.BOT_API_KEY) {
  console.warn('⚠️  BOT_API_KEY is not set — /api/bot routes will reject all requests with 500.')
}

const app = express()
const PORT = process.env.PORT || 3000

app.use(cors({
  origin: process.env.FRONTEND_URL,
  credentials: true
}))
app.use(express.json())
app.use(cookieParser())

// Initialize database on startup
let dbReady = false

// Wait until every table is created, THEN ensure the schema_version table and
// run migrations exactly once, sequentially. This ordering avoids the fresh-DB
// race that crashed startup with "no such table: users".
whenDbReady
  .then(() => initializeSchemaVersion())
  .then(() => checkAndApplyMigrations())
  .then(() => {
    dbReady = true
    console.log('✅​ Database ready')
  })
  .catch((err) => {
    console.error('Failed to initialize database:', err)
    process.exit(1)
  })

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Backend is running',
    database: dbReady ? 'ready' : 'initializing'
  })
})

// Middleware to check database readiness
app.use((req, res, next) => {
  if (!dbReady && req.path !== '/api/health') {
    return res.status(503).json({ error: 'Database not ready' })
  }
  next()
})

// Routes
app.use('/api/auth', authRoutes)
// Global maintenance gate: blocks non-owner dashboard writes when enabled.
// Applied to all guild routers (reads pass through); admin/auth/bot are exempt.
app.use('/api/guilds', maintenanceGate)
app.use('/api/guilds', guildRoutes)
app.use('/api/guilds/:guild_id/settings', settingsRoutes)
app.use('/api/guilds/:guild_id/settings', modulesRoutes)
app.use('/api/guilds/:guild_id/premium', premiumRoutes)
// Premium module routers are write-gated by tier (reads pass through so the
// dashboard can render the lock/upsell). Free modules carry no gate.
// (Leveling is gated inside its own router — it shares the bare /:guild_id mount
//  with resources, so a prefix-level gate would wrongly block sibling modules.)
app.use('/api/guilds/:guild_id', levelingRoutes)
app.use('/api/guilds/:guild_id/reaction-roles', reactionRolesRoutes)
app.use('/api/guilds/:guild_id/custom-commands', customCommandsRoutes)
app.use('/api/guilds/:guild_id/social', requirePremiumModule('social'), socialRoutes)
app.use('/api/guilds/:guild_id/stats', requirePremiumModule('stats'), statsRoutes)
app.use('/api/guilds/:guild_id/tempvoice', requirePremiumModule('tempvoice'), tempvoiceRoutes)
app.use('/api/guilds/:guild_id/starboard', requirePremiumModule('starboard'), starboardRoutes)
app.use('/api/guilds/:guild_id/suggestions', suggestionsRoutes)
app.use('/api/guilds/:guild_id/birthday', requirePremiumModule('birthday'), birthdayRoutes)
app.use('/api/guilds/:guild_id/scheduled', requirePremiumModule('scheduled'), scheduledRoutes)
app.use('/api/guilds/:guild_id/antiraid', requirePremiumModule('antiraid'), antiraidRoutes)
app.use('/api/guilds/:guild_id/verification', verificationRoutes)
app.use('/api/guilds/:guild_id/rolemenus', requirePremiumModule('rolemenus'), roleMenusRoutes)
app.use('/api/guilds/:guild_id/tickets', requirePremiumModule('tickets'), ticketsRoutes)
app.use('/api/guilds/:guild_id/giveaways', requirePremiumModule('giveaways'), giveawaysRoutes)
app.use('/api/guilds/:guild_id/counting', countingRoutes)
app.use('/api/guilds/:guild_id/polls', pollsRoutes)
app.use('/api/guilds/:guild_id/invitetracking', requirePremiumModule('invitetracking'), inviteTrackingRoutes)
app.use('/api/guilds/:guild_id/applications', requirePremiumModule('applications'), applicationsRoutes)
app.use('/api/guilds/:guild_id/economy', requirePremiumModule('economy'), economyRoutes)
app.use('/api/guilds/:guild_id/games', requirePremiumModule('games'), gamesRoutes)
app.use('/api/guilds/:guild_id/backups', requirePremiumModule('backup'), backupRoutes)
app.use('/api/guilds/:guild_id', resourcesRoutes)
app.use('/api/public', publicRoutes)
app.use('/api/admin', adminRoutes)
app.use('/api/bot', botRoutes)

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err)
  res.status(500).json({ error: 'Internal server error', message: err.message })
})

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found' })
})

// Explicit '0.0.0.0' so the server binds to IPv4 — without this, Node bindet auf
// Windows oft nur auf '::' (IPv6-Wildcard), und Clients, die `localhost` zu
// 127.0.0.1 auflösen (z. B. Python aiohttp im Bot), bekommen Connection-Refused.
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Backend server running on http://localhost:${PORT}`)
})
