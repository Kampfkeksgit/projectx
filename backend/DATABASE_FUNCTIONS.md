# Database Function Reference

## Quick API Reference

### Guild Operations

#### `getGuild(guildId)`
Get a single guild by ID.
- **Parameters:** `guildId` (string)
- **Returns:** Promise<Guild|undefined>
- **Example:** `const guild = await getGuild('123456789012345678');`

#### `getAllGuilds()`
Get all enabled guilds.
- **Parameters:** none
- **Returns:** Promise<Guild[]>
- **Example:** `const guilds = await getAllGuilds();`

#### `createGuild(guildId, guildName, guildIconUrl)`
Create a new guild.
- **Parameters:** 
  - `guildId` (string) - Discord Guild ID
  - `guildName` (string) - Display name
  - `guildIconUrl` (string) - URL to guild icon
- **Returns:** Promise<number> - lastID
- **Example:** `await createGuild('123456789012345678', 'My Guild', 'https://...icon.png');`

#### `updateGuild(guildId, updates)`
Update guild information.
- **Parameters:**
  - `guildId` (string) - Guild ID
  - `updates` (object) - Fields to update {guild_name, guild_icon_url, enabled, etc.}
- **Returns:** Promise<number> - Number of changes
- **Example:** `await updateGuild('123456789012345678', { guild_name: 'New Name' });`

#### `deleteGuild(guildId)`
Delete a guild and all related data (cascade delete).
- **Parameters:** `guildId` (string)
- **Returns:** Promise<number> - Number of changes
- **Example:** `await deleteGuild('123456789012345678');`

---

### Guild Settings

#### `getGuildSettings(guildId)`
Get settings for a specific guild.
- **Parameters:** `guildId` (string)
- **Returns:** Promise<GuildSettings|undefined>
- **Example:** `const settings = await getGuildSettings('123456789012345678');`

#### `upsertGuildSettings(guildId, settings)`
Create or update guild settings.
- **Parameters:**
  - `guildId` (string) - Guild ID
  - `settings` (object) - Settings to upsert
    - `welcome_enabled` (boolean)
    - `welcome_channel_id` (string)
    - `welcome_message` (string) - Supports {user} placeholder
    - `leave_enabled` (boolean)
    - `leave_channel_id` (string)
    - `leave_message` (string) - Supports {user} placeholder
- **Returns:** Promise<number> - lastID
- **Example:** 
```javascript
await upsertGuildSettings('123456789012345678', {
  welcome_enabled: true,
  welcome_channel_id: '111111111111111111',
  welcome_message: 'Welcome {user}!'
});
```

---

### User Operations

#### `getUser(userId)`
Get a user by Discord ID.
- **Parameters:** `userId` (string) - Discord User ID
- **Returns:** Promise<User|undefined>
- **Example:** `const user = await getUser('987654321098765432');`

#### `upsertUser(userId, userData)`
Create or update a user.
- **Parameters:**
  - `userId` (string) - Discord User ID
  - `userData` (object) - User data:
    - `username` (string)
    - `email` (string)
    - `avatar_url` (string)
    - `access_token` (string)
    - `refresh_token` (string)
- **Returns:** Promise<number> - lastID
- **Example:**
```javascript
await upsertUser('987654321098765432', {
  username: 'TestUser',
  email: 'user@example.com',
  avatar_url: 'https://...avatar.png',
  access_token: 'token_123',
  refresh_token: 'refresh_456'
});
```

#### `deleteUser(userId)`
Delete a user and all related data.
- **Parameters:** `userId` (string) - Discord User ID
- **Returns:** Promise<number> - Number of changes
- **Example:** `await deleteUser('987654321098765432');`

---

### User-Guild Relationships

#### `getUserGuilds(userId)`
Get all guilds for a user with role information.
- **Parameters:** `userId` (string)
- **Returns:** Promise<Guild[]> - Guilds with owner/admin flags
- **Example:** `const guilds = await getUserGuilds('987654321098765432');`

#### `addUserToGuild(userId, guildId, owner, admin)`
Add or update a user in a guild.
- **Parameters:**
  - `userId` (string)
  - `guildId` (string)
  - `owner` (boolean) - Is guild owner
  - `admin` (boolean) - Is guild admin
- **Returns:** Promise<number> - lastID
- **Example:** `await addUserToGuild('987654321098765432', '123456789012345678', false, true);`

#### `removeUserFromGuild(userId, guildId)`
Remove a user from a guild.
- **Parameters:**
  - `userId` (string)
  - `guildId` (string)
- **Returns:** Promise<number> - Number of changes
- **Example:** `await removeUserFromGuild('987654321098765432', '123456789012345678');`

#### `userHasGuildAccess(userId, guildId)`
Check if user has access to a guild.
- **Parameters:**
  - `userId` (string)
  - `guildId` (string)
- **Returns:** Promise<boolean>
- **Example:** `const hasAccess = await userHasGuildAccess('987654321098765432', '123456789012345678');`

#### `userIsGuildAdmin(userId, guildId)`
Check if user is guild owner or admin.
- **Parameters:**
  - `userId` (string)
  - `guildId` (string)
- **Returns:** Promise<boolean>
- **Example:** `const isAdmin = await userIsGuildAdmin('987654321098765432', '123456789012345678');`

---

### Audit Logging

#### `logAuditAction(userId, guildId, action, changes)`
Log an action to the audit log.
- **Parameters:**
  - `userId` (string) - User who performed action (nullable)
  - `guildId` (string) - Affected guild (nullable)
  - `action` (string) - Action description
  - `changes` (object) - What changed (optional)
- **Returns:** Promise<number> - lastID
- **Example:**
```javascript
await logAuditAction('987654321098765432', '123456789012345678', 'update_settings', {
  welcome_message: 'old message',
  welcome_message_new: 'new message'
});
```

#### `getGuildAuditLog(guildId, limit)`
Get audit log entries for a guild.
- **Parameters:**
  - `guildId` (string)
  - `limit` (number) - Max entries (default: 100)
- **Returns:** Promise<AuditEntry[]>
- **Example:** `const logs = await getGuildAuditLog('123456789012345678', 50);`

---

### Database Utilities

#### `getDbStats()`
Get database statistics (row counts).
- **Parameters:** none
- **Returns:** Promise<{guilds, guild_settings, users, user_guilds, audit_log}>
- **Example:** `const stats = await getDbStats();`

#### `closeDb()`
Close database connection gracefully.
- **Parameters:** none
- **Returns:** Promise<void>
- **Example:** `await closeDb();`

---

## Helper Functions (dbHelper.js)

### Query Building

#### `buildUpdateQuery(table, fields, whereClause, whereValues)`
Build a dynamic UPDATE query.
- **Returns:** `{query: string, values: array}`

#### `buildInsertQuery(table, data)`
Build a dynamic INSERT query.
- **Returns:** `{query: string, values: array}`

#### `buildSelectQuery(table, columns, whereClause, whereValues, options)`
Build a dynamic SELECT query with pagination.
- **Options:** `{orderBy, limit, offset}`
- **Returns:** `{query: string, values: array}`

### Error Handling

#### `handleDbError(error, context, details)`
Parse and format database errors with context.
- **Returns:** `{message, code, originalError, context, details}`
- **Detects:** UNIQUE, FOREIGN KEY, NOT NULL, table errors

### Validators

#### `isValidGuildId(guildId)`
Validate Discord Guild ID format (15-21 digits).
- **Returns:** boolean

#### `isValidUserId(userId)`
Validate Discord User ID format (15-21 digits).
- **Returns:** boolean

#### `isValidChannelId(channelId)`
Validate Discord Channel ID format (15-21 digits).
- **Returns:** boolean

### Utilities

#### `formatTimestamp(date)`
Format date to ISO 8601 string.
- **Parameters:** date (optional, default: now)
- **Returns:** string (ISO format)

#### `safeJsonParse(jsonString, fallback)`
Parse JSON with fallback on error.
- **Parameters:**
  - jsonString (string)
  - fallback (any, default: null)
- **Returns:** parsed object or fallback

#### `sanitizeInput(input)`
Remove potentially harmful characters from input.
- **Returns:** sanitized string

#### `logQuery(query, values, executionTime)`
Log SQL query with parameters (redacted).
- **Parameters:**
  - query (string)
  - values (array, optional)
  - executionTime (number, optional)

---

## Database Schema

### Tables

1. **guilds**
   - `id` (TEXT, PRIMARY KEY)
   - `guild_name` (TEXT)
   - `guild_icon_url` (TEXT)
   - `enabled` (BOOLEAN)
   - `created_at` (DATETIME)
   - `updated_at` (DATETIME)

2. **guild_settings**
   - `id` (INTEGER, PRIMARY KEY)
   - `guild_id` (TEXT, UNIQUE, FK → guilds)
   - `welcome_enabled` (BOOLEAN)
   - `welcome_channel_id` (TEXT)
   - `welcome_message` (TEXT)
   - `leave_enabled` (BOOLEAN)
   - `leave_channel_id` (TEXT)
   - `leave_message` (TEXT)
   - `created_at` (DATETIME)
   - `updated_at` (DATETIME)

3. **users**
   - `discord_id` (TEXT, PRIMARY KEY)
   - `username` (TEXT)
   - `email` (TEXT)
   - `avatar_url` (TEXT)
   - `access_token` (TEXT)
   - `refresh_token` (TEXT)
   - `created_at` (DATETIME)
   - `updated_at` (DATETIME)

4. **user_guilds**
   - `id` (INTEGER, PRIMARY KEY)
   - `user_id` (TEXT, FK → users)
   - `guild_id` (TEXT, FK → guilds)
   - `owner` (BOOLEAN)
   - `admin` (BOOLEAN)
   - `created_at` (DATETIME)
   - Unique(user_id, guild_id)

5. **audit_log**
   - `id` (INTEGER, PRIMARY KEY)
   - `user_id` (TEXT, FK → users, nullable)
   - `guild_id` (TEXT, FK → guilds, nullable)
   - `action` (TEXT)
   - `changes` (TEXT, JSON)
   - `created_at` (DATETIME)

---

## Error Codes

| Code | Description |
|------|-------------|
| `UNIQUE_CONSTRAINT_VIOLATION` | Record already exists |
| `FOREIGN_KEY_CONSTRAINT_VIOLATION` | Referenced record missing |
| `NOT_NULL_CONSTRAINT_VIOLATION` | Required field missing |
| `TABLE_NOT_FOUND` | Table does not exist |
| `DB_ERROR` | Generic database error |

---

## Usage Pattern

```javascript
import * as db from './db.js';
import * as dbHelper from './utils/dbHelper.js';

try {
  // Validate input
  if (!dbHelper.isValidGuildId(guildId)) {
    throw new Error('Invalid guild ID');
  }

  // Perform operation
  const result = await db.getGuild(guildId);

  // Handle result
  if (result) {
    console.log('Found guild:', result);
  }
} catch (error) {
  // Handle error
  const handled = dbHelper.handleDbError(error, 'getGuild', {guildId});
  console.error(handled);
}
```

---

**Last Updated:** 2026-05-18  
**Status:** ✅ Production Ready
