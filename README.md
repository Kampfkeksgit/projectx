# Discord Bot Dashboard

A complete system for managing Discord bot welcome and leave messages through a web dashboard. Includes a Discord bot, backend API, frontend dashboard, and SQLite database.

## Overview

This project provides a user-friendly way to configure and manage Discord bot responses to member events:
- **Welcome messages** when users join your Discord server
- **Leave messages** when users leave your Discord server
- **Real-time preview** of message templates
- **Multi-guild support** for managing multiple servers
- **Audit logging** of all configuration changes

## System Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system design, data flows, API endpoints, and deployment architecture.

## Project Structure

```
projectx/
├── bot/                          # Python Discord Bot
│   ├── main.py                  # Bot entry point
│   ├── config.py                # Configuration loader
│   └── cogs/
│       └── welcome_leave.py     # Event handlers and commands
├── backend/                      # Node.js Express API
│   ├── server.js                # Express server setup
│   ├── db.js                    # Database initialization
│   ├── migrations.js            # Database schema
│   ├── middleware/
│   │   └── auth.js              # Authentication & authorization
│   ├── routes/
│   │   ├── auth.js              # OAuth & token endpoints
│   │   ├── guilds.js            # Guild management endpoints
│   │   └── settings.js          # Settings CRUD endpoints
│   ├── utils/
│   │   └── dbHelper.js          # Database utilities
│   └── tests/
│       ├── db.test.js           # Database tests
│       └── verify.js            # Verification script
├── frontend/                     # Vue.js Dashboard
│   ├── src/
│   │   ├── App.vue              # Root component
│   │   ├── components/
│   │   │   ├── NavBar.vue       # Navigation bar
│   │   │   ├── GuildSelector.vue # Guild selection dropdown
│   │   │   └── LoadingPage.vue  # Loading indicator
│   │   ├── pages/
│   │   │   ├── Dashboard.vue    # Main dashboard
│   │   │   ├── Welcome.vue      # Welcome config page
│   │   │   ├── Leave.vue        # Leave config page
│   │   │   └── AuthCallback.vue # OAuth callback handler
│   │   ├── services/
│   │   │   └── api.js           # Axios API client
│   │   ├── router/
│   │   │   └── index.js         # Vue Router configuration
│   │   └── main.js              # Vue entry point
│   ├── vite.config.js
│   └── package.json
├── TEST_PLAN.md                 # Comprehensive testing checklist
├── VERIFICATION_CHECKLIST.md    # Implementation status
├── DEPLOYMENT_CHECKLIST.md      # Deployment preparation
├── ARCHITECTURE.md              # System architecture documentation
└── README.md                    # This file
```

## Prerequisites

- **Node.js** v18+ (for backend and frontend)
- **Python** 3.8+ (for bot)
- **npm** or **yarn** (for dependencies)
- **Discord Server** (for testing)
- **Discord Application** (OAuth credentials)

## Quick Start

### 1. Clone and Install

```bash
# Backend
cd X:\projectx\backend
npm install

# Frontend
cd X:\projectx\frontend
npm install

# Bot (virtual environment recommended)
cd X:\projectx\bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "OAuth2" → "General"
4. Note your **Client ID** and **Client Secret**
5. Add Redirect URI: `http://localhost:5173/auth/callback` (for development)
6. Go to "Bot"
7. Click "Add Bot"
8. Copy the **Bot Token**
9. Enable "Message Content Intent" under "Privileged Gateway Intents"

### 3. Environment Configuration

Create `.env` files in each directory:

**`X:\projectx\bot\.env`**
```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_client_id_here
DISCORD_CLIENT_SECRET=your_client_secret_here
BACKEND_URL=http://localhost:3000
DATABASE_URL=bot.db
```

**`X:\projectx\backend\.env`**
```env
PORT=3000
DISCORD_CLIENT_ID=your_client_id_here
DISCORD_CLIENT_SECRET=your_client_secret_here
DISCORD_REDIRECT_URI=http://localhost:5173/auth/callback
FRONTEND_URL=http://localhost:5173
DATABASE_URL=./bot.db
SESSION_SECRET=your_random_secret_here
NODE_ENV=development
```

**`X:\projectx\frontend\.env`**
```env
VITE_BACKEND_URL=http://localhost:3000/api
VITE_DISCORD_CLIENT_ID=your_client_id_here
VITE_DISCORD_REDIRECT_URI=http://localhost:5173/auth/callback
```

### 4. Add Bot to Test Server

1. Go to Discord Developer Portal → Your Application → OAuth2 → URL Generator
2. Select scopes: `bot`
3. Select permissions: `Send Messages`, `Read Messages/View Channels`
4. Copy the generated URL and open it
5. Select your test server and authorize

### 5. Start Services

**Terminal 1 - Backend:**
```bash
cd X:\projectx\backend
npm run dev
```

**Terminal 2 - Frontend:**
```bash
cd X:\projectx\frontend
npm run dev
```

**Terminal 3 - Bot:**
```bash
cd X:\projectx\bot
python main.py
```

### 6. Access Dashboard

Open your browser: `http://localhost:5173`

## Features

### Authentication
- Discord OAuth2 login
- JWT Bearer token authentication
- Automatic token refresh
- Secure logout

### Guild Management
- View all Discord servers you're admin/owner of
- Select guild for configuration
- Display guild icon and name
- Multi-guild support

### Welcome Message Configuration
- Enable/disable welcome messages
- Configure target channel
- Customize message template
- Real-time preview with placeholders:
  - `{user}` → @username
  - `{guild}` → server name
- Save and persist settings
- Reset to defaults

### Leave Message Configuration
- Enable/disable leave messages
- Configure target channel
- Customize message template
- Real-time preview with placeholders
- Save and persist settings

### Bot Features
- Automatic welcome message on member join
- Automatic leave message on member leave
- Admin command: `/welcome_test` to test messages
- Reads configuration from backend API
- Respects enabled/disabled settings

### Backend API
- RESTful API with Express
- SQLite database
- OAuth2 integration
- Audit logging of all changes
- CORS enabled for frontend
- Input validation and error handling

## Usage Guide

### Configuring Welcome Messages

1. Log in with Discord
2. Select your server from the guild dropdown
3. Click "Welcome Messages" in the dashboard
4. Toggle "Enable Welcome Messages" to ON
5. Enter the Channel ID where messages should be sent
6. Customize the message template (use `{user}` and `{guild}` placeholders)
7. See real-time preview below
8. Click "Save Settings"
9. You'll see a success message
10. When someone joins your server, the bot will send the message!

### Configuring Leave Messages

Follow the same steps as welcome messages on the "Leave Messages" tab.

### Finding Channel IDs

1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click on a channel and select "Copy Channel ID"
3. Paste into the Channel ID field in the dashboard

### Testing Welcome/Leave Messages

1. After configuring, use the bot command `/welcome_test` in a channel where the bot has permissions
2. The bot will send a preview of the welcome message
3. To test leave messages, configure a test user or have someone leave the server

## API Documentation

### Authentication Endpoints

```
POST /api/auth/callback
- Exchange Discord OAuth code for tokens
- Body: { code: "authorization_code" }
- Returns: { accessToken, refreshToken, user }

POST /api/auth/refresh
- Refresh expired access token
- Body: { refreshToken: "token" }
- Returns: { accessToken, expiresIn }
```

### Guild Endpoints

```
GET /api/guilds
- Get all guilds user is admin/owner of
- Auth: Bearer token
- Returns: [{ id, name, icon, isOwner, isAdmin }]

GET /api/guilds/:id
- Get specific guild details
- Auth: Bearer token
- Returns: { id, name, icon, isOwner, isAdmin }

GET /api/guilds/:id/full
- Get guild details with current settings
- Auth: Bearer token
- Returns: { ...guild, settings }
```

### Settings Endpoints

```
GET /api/guilds/:id/settings
- Get guild settings
- Auth: Bearer token
- Returns: { welcomeEnabled, welcomeChannelId, welcomeMessage, ... }

PUT /api/guilds/:id/settings
- Update all guild settings (complete replacement)
- Auth: Bearer token
- Body: { welcomeEnabled, welcomeChannelId, welcomeMessage, ... }
- Returns: { success: true, settings }

PATCH /api/guilds/:id/settings
- Update partial guild settings (merge)
- Auth: Bearer token
- Body: { welcomeEnabled: true } (only changed fields)
- Returns: { success: true, settings }

DELETE /api/guilds/:id/settings
- Reset settings to defaults
- Auth: Bearer token
- Returns: { success: true }
```

## Testing

### Automated Tests

```bash
# Backend tests
cd X:\projectx\backend
npm test

# Frontend tests (if implemented)
cd X:\projectx\frontend
npm test
```

### Manual Testing

See [TEST_PLAN.md](./TEST_PLAN.md) for comprehensive testing checklist with:
- Authentication flow testing
- Guild management testing
- Message configuration testing
- API integration testing
- Bot functionality testing
- Database integrity testing
- Error handling testing
- User experience testing

## Troubleshooting

### Bot Not Responding
- Verify bot token is correct in `.env`
- Check bot has "Message Content Intent" enabled
- Ensure bot has proper permissions in the server
- Check bot can read configured channel

### Settings Not Saving
- Check backend is running on port 3000
- Verify token is valid (check localStorage)
- Check browser console for API errors
- Check backend logs for errors

### Login Not Working
- Verify Discord credentials are correct
- Check OAuth redirect URI matches in both Discord app and backend
- Clear browser cache and localStorage
- Check backend logs

### Messages Not Sending
- Verify channel ID is correct
- Check bot has "Send Messages" permission in channel
- Enable Welcome/Leave messages (toggle ON)
- Check bot is running (`python main.py`)

### Database Errors
- Delete bot.db and restart backend to reinitialize
- Check file permissions in project directory
- Verify SQLite3 is installed

## Database Schema

See [ARCHITECTURE.md](./ARCHITECTURE.md) for complete database schema documentation.

Key tables:
- `users` - Discord users who logged in
- `guilds` - Discord servers
- `user_guilds` - User-guild relationships
- `guild_settings` - Per-guild configuration
- `audit_log` - All changes audit trail

## Deployment

See [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) for production deployment guide.

### Quick Deploy Steps

1. Set up production environment variables
2. Build frontend: `npm run build` in frontend directory
3. Serve built files with nginx or backend
4. Start backend with `npm start` (use PM2)
5. Start bot with `python main.py` (use PM2)
6. Set up HTTPS with Let's Encrypt
7. Configure domain DNS
8. Enable CORS for production domain
9. Set up monitoring and logging

## Production Considerations

- Use PostgreSQL instead of SQLite for multi-server deployments
- Set up Redis for session/token caching
- Use environment-based configuration
- Enable HTTPS/TLS (no HTTP in production)
- Set up rate limiting
- Configure CORS strictly
- Use PM2 or systemd for process management
- Set up automated backups
- Enable error tracking (Sentry, etc.)
- Set up uptime monitoring
- Use CDN for static assets

## Performance Tips

- Enable caching of guild list (localStorage)
- Batch API requests when possible
- Use indexes on database queries
- Enable gzip compression on backend
- Minify and bundle frontend assets
- Use lazy loading for routes
- Implement request debouncing

## Security Best Practices

- Never commit secrets to version control
- Use HTTPS in production (TLS 1.2+)
- Validate all input on backend
- Escape user input on frontend
- Use parameterized SQL queries
- Implement rate limiting
- Keep dependencies updated
- Run security audits regularly
- Use strong session secrets
- Rotate tokens periodically

## Contributing

1. Create a feature branch
2. Make changes
3. Test thoroughly (see TEST_PLAN.md)
4. Submit pull request

## Support

For issues or questions:
1. Check [TEST_PLAN.md](./TEST_PLAN.md) for testing steps
2. Check [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
3. Review logs in bot, backend, and browser console
4. Refer to Discord.py and Express.js documentation

## Logs

- **Backend**: Logs to console (can be redirected to file)
- **Bot**: Logs to console
- **Frontend**: Browser developer console (F12)

## License

[Add your license here]

## Version

1.0.0 - Initial Release

## Verification Status

See [VERIFICATION_CHECKLIST.md](./VERIFICATION_CHECKLIST.md) for implementation status.

All components implemented and ready for integration testing.
