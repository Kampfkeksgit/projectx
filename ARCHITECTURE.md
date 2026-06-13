# Discord Bot Dashboard - System Architecture

## High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User's Web Browser                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Vue.js Dashboard Frontend (Port 5173)                       │  │
│  │  - Guild Selection                                           │  │
│  │  - Welcome Message Configuration                            │  │
│  │  - Leave Message Configuration                              │  │
│  │  - Real-time Message Preview                               │  │
│  └────────────────┬─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                     │
        HTTP/HTTPS API Requests (REST)
                     │
┌─────────────────────┴─────────────────────────────────────────────────┐
│         Node.js Express Backend API Server (Port 3000)                │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  API Routes                                                  │    │
│  │  - /api/health (Health Check)                               │    │
│  │  - /api/auth/* (OAuth2 Authentication)                      │    │
│  │  - /api/guilds (List User Guilds)                          │    │
│  │  - /api/guilds/:id (Get Guild Details)                     │    │
│  │  - /api/guilds/:id/settings (CRUD Settings)                │    │
│  ├──────────────────────────────────────────────────────────────┤    │
│  │  Middleware                                                  │    │
│  │  - Authentication (JWT Bearer Tokens)                       │    │
│  │  - Authorization (Guild Ownership/Admin Checks)             │    │
│  │  - CORS (Cross-Origin Resource Sharing)                    │    │
│  │  - Error Handling                                           │    │
│  ├──────────────────────────────────────────────────────────────┤    │
│  │  Services                                                    │    │
│  │  - Discord OAuth Token Exchange                             │    │
│  │  - Token Refresh Logic                                      │    │
│  │  - Discord API Integration (via axios)                      │    │
│  │  - Database Layer (SQLite3)                                 │    │
│  │  - Audit Logging                                            │    │
│  └────────────────┬──────────────────────────────┬──────────────┘    │
└─────────────────────┼──────────────────────────────┼────────────────┘
                      │                              │
          HTTP Requests             Database Operations
          to Discord API            (SQL Queries)
                      │                              │
    ┌─────────────────┘                ┌────────────┴──────────────┐
    │                                   │                           │
┌───┴──────────────────┐      ┌──────────┴──────────────┐    ┌──────┴──────────┐
│  Discord API         │      │  SQLite3 Database      │    │  Discord OAuth  │
│  - Guilds Info       │      │  - guilds table        │    │  - Token Mgmt   │
│  - User Info         │      │  - users table         │    │  - User Creds   │
│  - Guild Members     │      │  - guild_settings      │    │                 │
│                      │      │  - audit_log table     │    │                 │
└──────────────────────┘      └────────────────────────┘    └─────────────────┘
```

## Discord Bot Component

```
┌────────────────────────────────────────────────────────────────┐
│  Python Discord.py Bot (Background Process)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Event Handlers                                          │  │
│  │  - on_ready() - Bot initialization                      │  │
│  │  - on_member_join() - Welcome message logic             │  │
│  │  - on_member_remove() - Leave message logic             │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  Commands                                                │  │
│  │  - /welcome_test - Admin command to test messages       │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  Integration Layer                                       │  │
│  │  - Fetch guild settings from backend API                │  │
│  │  - Parse message templates ({user}, {guild})            │  │
│  │  - Send configured messages to Discord                  │  │
│  └─────────┬──────────────────────────┬────────────────────┘  │
└────────────┼──────────────────────────┼──────────────────────┘
             │                          │
        REST API Calls           Discord WebSocket
        to Backend                Connection
             │                          │
    ┌────────┴──┐            ┌──────────┴─────┐
    │            │            │                │
    │  Backend   │            │  Discord API   │
    │  (Fetch    │            │  - Guilds      │
    │  Settings) │            │  - Members     │
    │            │            │  - Messages    │
    └────────────┘            └────────────────┘
```

## Data Flow Diagrams

### 1. Authentication Flow

```
User (Browser)              Frontend                Backend                  Discord
    │                          │                       │                        │
    ├─ Click "Login" ────────→ │                       │                        │
    │                          │                       │                        │
    │                          ├─ Redirect to OAuth ──────────────────────────→ │
    │                          │  (/oauth/authorize)                            │
    │                          │                                                │
    │ ← Redirect to Callback ────────────────────────────────────────────────── │
    │   (with code)                                                             │
    │                          │                       │                        │
    │                          ├─ Send Code ──────────→ POST /api/auth/callback │
    │                          │                       │                        │
    │                          │                       ├─ Exchange Code ───────→ │
    │                          │                       │  (using Client ID/Secret)
    │                          │                       │                        │
    │                          │                       │ ← Access Token ─────── │
    │                          │                       │   Refresh Token        │
    │                          │ ← Return Tokens ───── │                        │
    │                          │                       │                        │
    │ ← Save tokens in localStorage                    │                        │
```

### 2. Guild Settings Update Flow

```
User (Browser)              Frontend                Backend                Database
    │                          │                       │                        │
    ├─ Fill Form ────────────→ │                       │                        │
    │ (Channel ID, Message)    │                       │                        │
    │                          │                       │                        │
    │                          ├─ PUT /api/guilds/:id/settings                  │
    │                          │ (with Bearer token)   │                        │
    │                          │                       ├─ Verify Token ────────→│
    │                          │                       │                        │
    │                          │                       │ ← Valid ──────────────│
    │                          │                       │                        │
    │                          │                       ├─ Update Settings ────→ │
    │                          │                       │ (SQL UPDATE)           │
    │                          │                       │                        │
    │                          │                       │ ← Success ────────────│
    │                          │                       │                        │
    │                          │ ← Success Response ─── │                        │
    │                          │                       │                        │
    │ ← Show Success Message ──                        │                        │
```

### 3. Member Join → Welcome Message Flow

```
New Member Joins               Discord Bot            Backend API            Database
    │                              │                       │                    │
    ├─ Join Event ──────────────→ │                       │                    │
    │                              │                       │                    │
    │                              ├─ Fetch Guild Settings                      │
    │                              ├─ REST Call ──────────→ GET /api/guilds/:id/settings
    │                              │                       │                    │
    │                              │                       ├─ Query Settings ─→ │
    │                              │                       │                    │
    │                              │                       │ ← Settings ──────│
    │                              │ ← Settings ─────────── │                    │
    │                              │                       │                    │
    │                              ├─ Check Enabled        │                    │
    │                              │                       │                    │
    │                              ├─ Parse Template       │                    │
    │                              │ ({user}, {guild})      │                    │
    │                              │                       │                    │
    │                              ├─ Send Message ───────→ Target Channel      │
    │                              │                       │                    │
    │ ← Welcome Message ←────────── │                       │                    │
```

## Database Schema

### Tables

```sql
-- Users who have logged in
CREATE TABLE users (
  id TEXT PRIMARY KEY,           -- Discord User ID
  username TEXT,
  email TEXT,
  avatar_url TEXT,
  last_login TIMESTAMP
);

-- Discord Guilds
CREATE TABLE guilds (
  id TEXT PRIMARY KEY,           -- Discord Guild ID
  name TEXT,
  owner_id TEXT,                 -- Discord User ID (guild owner)
  icon_url TEXT,
  created_at TIMESTAMP
);

-- User-Guild membership
CREATE TABLE user_guilds (
  user_id TEXT,
  guild_id TEXT,
  is_owner BOOLEAN,
  is_admin BOOLEAN,
  joined_at TIMESTAMP,
  PRIMARY KEY (user_id, guild_id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (guild_id) REFERENCES guilds(id)
);

-- Guild-specific settings
CREATE TABLE guild_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id TEXT NOT NULL,
  welcome_enabled BOOLEAN DEFAULT 1,
  welcome_channel_id TEXT,
  welcome_message TEXT DEFAULT 'Welcome {user} to {guild}!',
  leave_enabled BOOLEAN DEFAULT 1,
  leave_channel_id TEXT,
  leave_message TEXT DEFAULT '{user} has left {guild}',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (guild_id) REFERENCES guilds(id)
);

-- Audit log for all changes
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id TEXT,
  user_id TEXT,
  action TEXT,              -- 'update_settings', 'delete_settings', etc.
  changes TEXT,             -- JSON of what changed
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (guild_id) REFERENCES guilds(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## API Endpoints

### Authentication
- `POST /api/auth/callback` - OAuth code exchange
- `POST /api/auth/refresh` - Token refresh
- `GET /api/health` - Health check

### Guilds
- `GET /api/guilds` - List all user's guilds
- `GET /api/guilds/:id` - Get guild details
- `GET /api/guilds/:id/full` - Get guild details + settings

### Settings
- `GET /api/guilds/:id/settings` - Fetch guild settings
- `PUT /api/guilds/:id/settings` - Update guild settings (complete)
- `PATCH /api/guilds/:id/settings` - Update guild settings (partial)
- `DELETE /api/guilds/:id/settings` - Reset to defaults

## Frontend Architecture

### Pages/Components
- **App.vue** - Root component with navigation
- **NavBar.vue** - User authentication status, logout button
- **GuildSelector.vue** - Dropdown/list of user's guilds
- **LoadingPage.vue** - Loading spinner during API calls
- **Dashboard.vue** - Main guild dashboard
- **Welcome.vue** - Welcome message configuration page
- **Leave.vue** - Leave message configuration page
- **AuthCallback.vue** - OAuth redirect handler

### State Management
- localStorage for:
  - Bearer token
  - Refresh token
  - Current guild ID
  - User info

### API Integration
- Axios service with:
  - Bearer token auto-injection
  - 401 error interception
  - Automatic token refresh on 401
  - Base URL configuration from env

## Deployment Architecture

### Production Setup
```
┌─────────────────────────────────────────────────────┐
│  Production Server (e.g., AWS EC2, VPS, Railway)   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. Backend Service (PM2/systemd)                   │
│     - Express server on port 3000                   │
│     - Reverse proxy (nginx) on port 80/443         │
│     - Environment variables loaded                  │
│                                                     │
│  2. Bot Service (PM2/systemd)                       │
│     - Python discord.py process                     │
│     - Connects to Discord via WebSocket             │
│     - Reads settings from backend API               │
│                                                     │
│  3. Frontend (Static Files)                         │
│     - Vue build served by nginx                     │
│     - CDN optional for assets                       │
│                                                     │
│  4. Database                                        │
│     - SQLite3 in /data directory                    │
│     - Regular backups to S3/cloud storage           │
│     - Read-only replica for analytics               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Security Architecture

### Authentication
- Discord OAuth2 (industry standard)
- JWT Bearer tokens for API auth
- Token refresh tokens stored securely
- HTTPS only (TLS 1.2+)

### Authorization
- Guild ownership verification
- Admin/permissions check from Discord API
- Per-resource authorization on backend

### Data Protection
- Secrets stored in .env (never in version control)
- Input validation on all endpoints
- SQL injection prevention via parameterized queries
- XSS prevention via Vue's template escaping
- CORS restricted to frontend domain

## Performance Considerations

### Caching
- Guild list cached in frontend localStorage
- Discord API responses cached (1 hour TTL)
- Settings cached in memory on bot startup

### Rate Limiting
- Discord API: 50 requests per second
- Backend API: Consider rate limiting per IP
- Bot event handlers: Debounce multiple events

### Optimization
- Frontend code splitting by route
- Lazy loading of pages
- Lazy loading of guild selector
- API requests batched when possible
- Database queries indexed

## Error Handling Strategy

### Frontend
- 401: Redirect to login
- 403: Show permission denied message
- 4xx/5xx: Show user-friendly error message
- Network error: Show "Connection lost" message

### Backend
- Validation errors: 400 with details
- Auth errors: 401 Unauthorized
- Permission errors: 403 Forbidden
- Server errors: 500 with generic message (log details)

### Bot
- Discord API errors: Log and continue
- Settings fetch failure: Use cached settings
- Message send failure: Log and notify admin

## Monitoring & Logging

### What to Monitor
- Backend API response times
- Database query performance
- Bot event processing latency
- Discord API rate limit usage
- Error rates by endpoint
- User authentication success rate

### Logs
- Structured logs (JSON format)
- Separate logs: api.log, bot.log, error.log
- Log levels: DEBUG, INFO, WARN, ERROR
- Centralized logging (e.g., ELK, Datadog) optional

## Disaster Recovery

### Backup Strategy
- Daily automated database backups
- Backups stored off-server
- Backup retention: 30 days
- Test restore procedures monthly

### Failover
- Database replication optional for HA
- Multiple bot instances with load balancing
- Graceful degradation (read-only mode)

## Development vs Production

### Environment Differences
```
Development:
- VITE_BACKEND_URL=http://localhost:3000
- Discord OAuth redirect: http://localhost:3000
- Verbose logging
- Hot module reloading

Production:
- VITE_BACKEND_URL=https://api.example.com
- Discord OAuth redirect: https://api.example.com
- Structured logging
- Built/minified frontend
- NODE_ENV=production
- SSL/TLS enforced
```

## Technology Stack Summary

### Backend
- **Runtime**: Node.js v18+
- **Framework**: Express.js
- **Database**: SQLite3
- **HTTP Client**: Axios
- **Auth**: JWT Bearer tokens

### Frontend
- **Framework**: Vue.js 3
- **Build Tool**: Vite
- **Routing**: Vue Router
- **HTTP Client**: Axios

### Bot
- **Language**: Python 3.8+
- **Framework**: discord.py
- **HTTP**: requests, aiohttp
- **Config**: python-dotenv

### Infrastructure
- **Hosting**: Any (VPS, Heroku, Railway, AWS, etc.)
- **Database**: SQLite3 (can be upgraded to PostgreSQL)
- **Reverse Proxy**: nginx
- **Process Manager**: PM2 or systemd

## Future Enhancements

1. **Database Migration**: SQLite → PostgreSQL for scaling
2. **Caching Layer**: Redis for session/token caching
3. **Message Queue**: Bull/RabbitMQ for async tasks
4. **Analytics**: Event tracking and user analytics
5. **Multi-Bot**: Support multiple bots per dashboard
6. **Role-Based Access**: Fine-grained permissions
7. **Webhook Integration**: Custom integrations
8. **Mobile App**: React Native/Flutter companion
9. **Advanced Scheduling**: Scheduled messages, recurring events
10. **Audit Trail UI**: Visual audit log viewer
