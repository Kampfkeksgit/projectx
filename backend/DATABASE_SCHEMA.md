# Discord Bot Dashboard - Database Schema

## Overview
SQLite database for managing multi-guild Discord bot dashboard with user authentication, guild settings, and audit logging.

**Database Location:** `./data/bot.db`

---

## Tables

### 1. **guilds**
Stores Discord guild information
```sql
CREATE TABLE guilds (
  id TEXT PRIMARY KEY,
  guild_name TEXT NOT NULL,
  guild_icon_url TEXT,
  enabled BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- `id`: Discord Guild ID (Snowflake)
- `guild_name`: Display name of the guild
- `guild_icon_url`: URL to guild icon
- `enabled`: Whether the guild is active in the dashboard
- `created_at`/`updated_at`: Timestamps

---

### 2. **guild_settings**
Configuration for each guild (welcome/leave messages, etc.)
```sql
CREATE TABLE guild_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id TEXT NOT NULL UNIQUE,
  welcome_enabled BOOLEAN DEFAULT 1,
  welcome_channel_id TEXT,
  welcome_message TEXT DEFAULT 'Welcome {user}!',
  leave_enabled BOOLEAN DEFAULT 1,
  leave_channel_id TEXT,
  leave_message TEXT DEFAULT '{user} has left.',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
);
```
- `id`: Auto-increment primary key
- `guild_id`: Reference to guild
- `welcome_enabled`: Enable/disable welcome messages
- `welcome_channel_id`: Channel for welcome messages
- `welcome_message`: Customizable welcome message template
- `leave_enabled`: Enable/disable leave messages
- `leave_channel_id`: Channel for leave messages
- `leave_message`: Customizable leave message template

**Note:** Templates support `{user}` placeholder

---

### 3. **users**
Discord user information and authentication tokens
```sql
CREATE TABLE users (
  discord_id TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  email TEXT,
  avatar_url TEXT,
  access_token TEXT,
  refresh_token TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- `discord_id`: Discord User ID (Snowflake)
- `username`: Discord username
- `email`: User email from OAuth
- `avatar_url`: URL to user avatar
- `access_token`: OAuth access token (for API calls)
- `refresh_token`: OAuth refresh token (for token renewal)

---

### 4. **user_guilds**
Maps users to guilds with role information (owner, admin)
```sql
CREATE TABLE user_guilds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  guild_id TEXT NOT NULL,
  owner BOOLEAN DEFAULT 0,
  admin BOOLEAN DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(discord_id) ON DELETE CASCADE,
  FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
  UNIQUE(user_id, guild_id)
);
```
- `id`: Auto-increment primary key
- `user_id`: Reference to user
- `guild_id`: Reference to guild
- `owner`: Whether user is guild owner
- `admin`: Whether user is guild admin
- Composite unique constraint prevents duplicate user-guild associations

---

### 5. **audit_log**
Tracks administrative actions for security and accountability
```sql
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,
  guild_id TEXT,
  action TEXT NOT NULL,
  changes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(discord_id) ON DELETE SET NULL,
  FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE SET NULL
);
```
- `id`: Auto-increment primary key
- `user_id`: User who performed the action (nullable)
- `guild_id`: Guild affected by the action (nullable)
- `action`: Description of action (e.g., "update_settings", "add_member")
- `changes`: JSON string of what changed (optional)

---

## Relationships

```
guilds (1) ──────── (M) guild_settings
  │
  └─ (1) ──────── (M) user_guilds ──────── (M) users
  │
  └─ (1) ──────── (M) audit_log
  
users (1) ──────── (M) user_guilds
users (1) ──────── (M) audit_log
```

---

## Helper Functions (from db.js)

### Guild Operations
- `getGuild(guildId)` - Get guild by ID
- `getAllGuilds()` - Get all enabled guilds
- `createGuild(guildId, guildName, guildIconUrl)` - Create new guild
- `updateGuild(guildId, updates)` - Update guild info
- `deleteGuild(guildId)` - Delete guild and cascade

### Guild Settings
- `getGuildSettings(guildId)` - Get settings for a guild
- `upsertGuildSettings(guildId, settings)` - Create or update settings

### User Operations
- `getUser(discordId)` - Get user by Discord ID
- `upsertUser(discordId, userData)` - Create or update user

### User-Guild Relationships
- `getUserGuilds(userId)` - Get all guilds for a user
- `addUserToGuild(userId, guildId, owner, admin)` - Add/update user in guild
- `userHasGuildAccess(userId, guildId)` - Check if user can access guild
- `userIsGuildAdmin(userId, guildId)` - Check if user is owner or admin

### Audit Operations
- `logAuditAction(userId, guildId, action, changes)` - Log an action
- `getGuildAuditLog(guildId, limit)` - Get audit log for guild

### Utilities
- `getDbStats()` - Get row counts for all tables

---

## Database Initialization

The database is automatically initialized on server startup via:

1. **server.js** - Calls initialization on startup
2. **db.js** - Creates all tables with proper schema
3. **migrations.js** - Handles schema versioning and migrations

---

## Foreign Key Constraints

All foreign keys use appropriate cascading rules:

- **ON DELETE CASCADE** - When referenced record is deleted, delete related records
  - Guild settings → guilds
  - User-guild associations → guilds & users
  
- **ON DELETE SET NULL** - When referenced record is deleted, set to NULL
  - Audit log → users & guilds (preserve history)

---

## File Locations

- **Database:** `./data/bot.db`
- **Schema Definition:** `./db.js` (initializeDatabase function)
- **Migrations:** `./migrations.js`
- **Helper Functions:** `./db.js` (exported functions)

---

## Usage Example

```javascript
import { 
  getGuild, 
  createGuild, 
  getGuildSettings,
  upsertGuildSettings,
  logAuditAction 
} from './db.js';

// Get a guild
const guild = await getGuild('123456789');

// Create a new guild
await createGuild('987654321', 'New Guild', 'https://...icon.png');

// Get and update settings
const settings = await getGuildSettings('123456789');
await upsertGuildSettings('123456789', {
  welcome_enabled: true,
  welcome_channel_id: '111111111',
  welcome_message: 'Welcome {user}! 👋'
});

// Log an action
await logAuditAction('user123', 'guild456', 'update_settings', {
  welcome_message: 'old message',
  welcome_message_new: 'new message'
});
```

---

## Notes

- All timestamps use ISO format (DATETIME DEFAULT CURRENT_TIMESTAMP)
- Boolean values stored as 0/1
- Foreign keys are enabled by default (PRAGMA foreign_keys = ON)
- Database file is auto-created in `./data/bot.db` if it doesn't exist
- Schema version tracking allows for future migrations

