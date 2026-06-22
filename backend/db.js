import sqlite3 from 'sqlite3';
import path from 'path';
import fs from 'fs';
import { randomUUID } from 'node:crypto';

const dbPath = process.env.DATABASE_URL || './data/bot.db';

// Ensure data directory exists
const dataDir = path.dirname(dbPath);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

// Resolves once initializeDatabase() has created every table. server.js awaits
// this BEFORE running migrations, so a fresh DB never ALTERs a not-yet-created
// table (root cause of "SQLITE_ERROR: no such table: users" on first boot).
let resolveDbReady;
export const whenDbReady = new Promise((resolve) => { resolveDbReady = resolve; });

export const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err);
  } else {
    console.log('Connected to SQLite database at:', dbPath);
    initializeDatabase();
  }
});

function initializeDatabase() {
  db.serialize(() => {
    // Enable foreign keys
    db.run('PRAGMA foreign_keys = ON');
    // NOTE: WAL is deliberately NOT used. The project lives on the X: drive,
    // which is a non-standard volume (network / virtual / OneDrive-style mount —
    // it has no Win32_LogicalDisk entry and breaks file watchers, see CLAUDE.md).
    // WAL relies on a memory-mapped `-shm` file + special file locking that such
    // filesystems don't support, which surfaces as a hard `SQLITE_IOERR: disk I/O
    // error` on every read/write once the WAL can't be checkpointed. TRUNCATE is
    // a rollback journal using only plain file I/O, so it works everywhere.
    // Combined with the runInTransaction queue, bulk writes stay fast enough.
    db.run('PRAGMA journal_mode = TRUNCATE');
    db.run('PRAGMA synchronous = NORMAL');
    // Wait (instead of erroring) if the single connection is briefly busy.
    db.run('PRAGMA busy_timeout = 5000');

    // Create guilds table
    db.run(`
      CREATE TABLE IF NOT EXISTS guilds (
        id TEXT PRIMARY KEY,
        guild_name TEXT NOT NULL,
        guild_icon_url TEXT,
        enabled BOOLEAN DEFAULT 1,
        bot_present BOOLEAN DEFAULT 0,
        premium_tier TEXT DEFAULT 'free',
        premium_source TEXT,
        premium_until INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `, (err) => {
      if (err) console.error('Error creating guilds table:', err);
      else console.log('✓ Guilds table initialized');
    });

    // Defensive ALTER for legacy DBs created before bot_present existed.
    db.run('ALTER TABLE guilds ADD COLUMN bot_present BOOLEAN DEFAULT 0', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) {
        console.error('Warning: could not ensure guilds.bot_present column:', err.message);
      }
    });

    // Defensive ALTERs for the V21 premium-tier columns (guilds).
    db.run("ALTER TABLE guilds ADD COLUMN premium_tier TEXT DEFAULT 'free'", (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guilds.premium_tier:', err.message);
    });
    db.run('ALTER TABLE guilds ADD COLUMN premium_source TEXT', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guilds.premium_source:', err.message);
    });
    db.run('ALTER TABLE guilds ADD COLUMN premium_until INTEGER', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guilds.premium_until:', err.message);
    });

    // Defensive ALTERs for the V17 owner-block flags (guilds) + V22 temp-ban expiry.
    const guildBlockAlters = [
      'ALTER TABLE guilds ADD COLUMN blocked BOOLEAN DEFAULT 0',
      'ALTER TABLE guilds ADD COLUMN blocked_reason TEXT',
      'ALTER TABLE guilds ADD COLUMN blocked_at INTEGER',
      'ALTER TABLE guilds ADD COLUMN blocked_until INTEGER'
    ];
    for (const stmt of guildBlockAlters) {
      db.run(stmt, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) {
          console.error('Warning: could not ensure guilds block column:', err.message);
        }
      });
    }

    // Defensive ALTER for the V19 command-manager prefix.
    db.run("ALTER TABLE guilds ADD COLUMN command_prefix TEXT DEFAULT '!'", (err) => {
      if (err && !/duplicate column name/i.test(err.message)) {
        console.error('Warning: could not ensure guilds.command_prefix column:', err.message);
      }
    });

    // V19 command-manager per-command enable/disable overrides.
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_command_settings (
        guild_id    TEXT NOT NULL,
        command_key TEXT NOT NULL,
        enabled     BOOLEAN DEFAULT 1,
        PRIMARY KEY (guild_id, command_key),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_command_settings table:', err);
    });

    // Create guild_settings table
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL UNIQUE,
        welcome_enabled BOOLEAN DEFAULT 1,
        welcome_channel_id TEXT,
        welcome_message TEXT DEFAULT 'Welcome {user}!',
        leave_enabled BOOLEAN DEFAULT 1,
        leave_channel_id TEXT,
        leave_message TEXT DEFAULT '{user} has left.',
        welcome_use_embed BOOLEAN DEFAULT 0,
        welcome_embed TEXT,
        welcome_ping_user BOOLEAN DEFAULT 0,
        welcome_dm_enabled BOOLEAN DEFAULT 0,
        welcome_dm_message TEXT,
        welcome_delete_after INTEGER DEFAULT 0,
        leave_use_embed BOOLEAN DEFAULT 0,
        leave_embed TEXT,
        leave_delete_after INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_settings table:', err);
      else console.log('✓ Guild settings table initialized');
    });

    // Defensive ALTERs for legacy DBs created before the V5 embed/DM/delete
    // columns existed. The proper migration is in migrations.js (v5); these
    // are no-ops for fresh DBs because the columns are already in the CREATE
    // TABLE above.
    const welcomeLeaveAlters = [
      'ALTER TABLE guild_settings ADD COLUMN welcome_use_embed BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_settings ADD COLUMN welcome_embed TEXT',
      'ALTER TABLE guild_settings ADD COLUMN welcome_ping_user BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_settings ADD COLUMN welcome_dm_enabled BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_settings ADD COLUMN welcome_dm_message TEXT',
      'ALTER TABLE guild_settings ADD COLUMN welcome_delete_after INTEGER DEFAULT 0',
      'ALTER TABLE guild_settings ADD COLUMN leave_use_embed BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_settings ADD COLUMN leave_embed TEXT',
      'ALTER TABLE guild_settings ADD COLUMN leave_delete_after INTEGER DEFAULT 0'
    ];
    for (const stmt of welcomeLeaveAlters) {
      db.run(stmt, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) {
          console.error('Warning: could not ensure guild_settings column:', err.message);
        }
      });
    }

    // Create users table
    db.run(`
      CREATE TABLE IF NOT EXISTS users (
        discord_id TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        email TEXT,
        avatar_url TEXT,
        access_token TEXT,
        refresh_token TEXT,
        token_expires_at INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `, (err) => {
      if (err) console.error('Error creating users table:', err);
      else console.log('✓ Users table initialized');
    });

    // Defensive ALTER for legacy DBs created before the token_expires_at column existed.
    // The proper migration lives in migrations.js (v2); this is a no-op for fresh DBs
    // because the column is already in the CREATE TABLE above.
    db.run('ALTER TABLE users ADD COLUMN token_expires_at INTEGER', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) {
        console.error('Warning: could not ensure users.token_expires_at column:', err.message);
      }
    });

    // Defensive ALTERs for the V17 owner-block flags (users) + V22 temp-ban expiry.
    const userBlockAlters = [
      'ALTER TABLE users ADD COLUMN blocked BOOLEAN DEFAULT 0',
      'ALTER TABLE users ADD COLUMN blocked_reason TEXT',
      'ALTER TABLE users ADD COLUMN blocked_at INTEGER',
      'ALTER TABLE users ADD COLUMN blocked_until INTEGER'
    ];
    for (const stmt of userBlockAlters) {
      db.run(stmt, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) {
          console.error('Warning: could not ensure users block column:', err.message);
        }
      });
    }

    // Create user_guilds table
    db.run(`
      CREATE TABLE IF NOT EXISTS user_guilds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        guild_id TEXT NOT NULL,
        owner BOOLEAN DEFAULT 0,
        admin BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(discord_id) ON DELETE CASCADE,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
        UNIQUE(user_id, guild_id)
      )
    `, (err) => {
      if (err) console.error('Error creating user_guilds table:', err);
      else console.log('✓ User guilds table initialized');
    });

    // Create guild_autorole_settings table (v3)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_autorole_settings (
        guild_id TEXT PRIMARY KEY,
        enabled BOOLEAN DEFAULT 0,
        role_ids TEXT DEFAULT '[]',
        apply_to_bots BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_autorole_settings table:', err);
      else console.log('✓ Guild autorole settings table initialized');
    });

    // Create guild_log_settings table (v3, extended v9)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_log_settings (
        guild_id TEXT PRIMARY KEY,
        enabled BOOLEAN DEFAULT 0,
        log_channel_id TEXT,
        log_joins BOOLEAN DEFAULT 1,
        log_leaves BOOLEAN DEFAULT 1,
        log_message_edits BOOLEAN DEFAULT 0,
        log_message_deletes BOOLEAN DEFAULT 0,
        log_member_bans BOOLEAN DEFAULT 1,
        log_member_updates BOOLEAN DEFAULT 0,
        log_member_unbans BOOLEAN DEFAULT 0,
        log_channels BOOLEAN DEFAULT 0,
        log_roles BOOLEAN DEFAULT 0,
        log_voice BOOLEAN DEFAULT 0,
        log_ignored_channel_ids TEXT DEFAULT '[]',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_log_settings table:', err);
      else console.log('✓ Guild log settings table initialized');
    });

    // Defensive ALTERs for legacy log rows created before v9 columns.
    const logAlters = [
      'ALTER TABLE guild_log_settings ADD COLUMN log_member_updates BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_log_settings ADD COLUMN log_member_unbans BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_log_settings ADD COLUMN log_channels BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_log_settings ADD COLUMN log_roles BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_log_settings ADD COLUMN log_voice BOOLEAN DEFAULT 0',
      "ALTER TABLE guild_log_settings ADD COLUMN log_ignored_channel_ids TEXT DEFAULT '[]'"
    ];
    for (const stmt of logAlters) {
      db.run(stmt, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) {
          console.error('Warning: could not ensure guild_log_settings column:', err.message);
        }
      });
    }

    // Create guild_moderation_settings table (v3, extended v9)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_moderation_settings (
        guild_id TEXT PRIMARY KEY,
        enabled BOOLEAN DEFAULT 0,
        anti_spam_enabled BOOLEAN DEFAULT 0,
        max_messages_per_10s INTEGER DEFAULT 5,
        banned_words TEXT DEFAULT '[]',
        banned_word_action TEXT DEFAULT 'delete',
        mute_role_id TEXT,
        anti_invite BOOLEAN DEFAULT 0,
        anti_link BOOLEAN DEFAULT 0,
        filter_action TEXT DEFAULT 'delete',
        anti_mention BOOLEAN DEFAULT 0,
        max_mentions INTEGER DEFAULT 5,
        anti_caps BOOLEAN DEFAULT 0,
        caps_percentage INTEGER DEFAULT 70,
        timeout_duration INTEGER DEFAULT 300,
        warn_threshold INTEGER DEFAULT 0,
        warn_escalation_action TEXT DEFAULT 'mute',
        exempt_role_ids TEXT DEFAULT '[]',
        ignored_channel_ids TEXT DEFAULT '[]',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_moderation_settings table:', err);
      else console.log('✓ Guild moderation settings table initialized');
    });

    // Defensive ALTERs for legacy moderation rows created before v9 columns.
    const moderationAlters = [
      'ALTER TABLE guild_moderation_settings ADD COLUMN anti_invite BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_moderation_settings ADD COLUMN anti_link BOOLEAN DEFAULT 0',
      "ALTER TABLE guild_moderation_settings ADD COLUMN filter_action TEXT DEFAULT 'delete'",
      'ALTER TABLE guild_moderation_settings ADD COLUMN anti_mention BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_moderation_settings ADD COLUMN max_mentions INTEGER DEFAULT 5',
      'ALTER TABLE guild_moderation_settings ADD COLUMN anti_caps BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_moderation_settings ADD COLUMN caps_percentage INTEGER DEFAULT 70',
      'ALTER TABLE guild_moderation_settings ADD COLUMN timeout_duration INTEGER DEFAULT 300',
      'ALTER TABLE guild_moderation_settings ADD COLUMN warn_threshold INTEGER DEFAULT 0',
      "ALTER TABLE guild_moderation_settings ADD COLUMN warn_escalation_action TEXT DEFAULT 'mute'",
      "ALTER TABLE guild_moderation_settings ADD COLUMN exempt_role_ids TEXT DEFAULT '[]'",
      "ALTER TABLE guild_moderation_settings ADD COLUMN ignored_channel_ids TEXT DEFAULT '[]'"
    ];
    for (const stmt of moderationAlters) {
      db.run(stmt, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) {
          console.error('Warning: could not ensure guild_moderation_settings column:', err.message);
        }
      });
    }

    // Create guild_moderation_warnings table (v9) — persistent warn counter for escalation.
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_moderation_warnings (
        guild_id    TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        count       INTEGER DEFAULT 0,
        total       INTEGER DEFAULT 0,
        updated_at  INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_moderation_warnings table:', err);
      else console.log('✓ Guild moderation warnings table initialized');
    });

    // Create guild_channels table (v6)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_channels (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        name        TEXT NOT NULL,
        type        TEXT NOT NULL,
        parent_id   TEXT,
        position    INTEGER DEFAULT 0,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_channels table:', err);
      else console.log('✓ Guild channels table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_guild_channels_guild ON guild_channels(guild_id)',
      (err) => {
        if (err) console.error('Error creating idx_guild_channels_guild:', err);
      }
    );

    // Create guild_roles table (v6)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_roles (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        name        TEXT NOT NULL,
        color       INTEGER DEFAULT 0,
        position    INTEGER DEFAULT 0,
        managed     BOOLEAN DEFAULT 0,
        is_default  BOOLEAN DEFAULT 0,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_roles table:', err);
      else console.log('✓ Guild roles table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_guild_roles_guild ON guild_roles(guild_id)',
      (err) => {
        if (err) console.error('Error creating idx_guild_roles_guild:', err);
      }
    );

    // Create guild_reaction_role_messages table (v7)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_reaction_role_messages (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        channel_id  TEXT NOT NULL,
        message_id  TEXT NOT NULL,
        name        TEXT,
        exclusive   BOOLEAN DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
        UNIQUE(guild_id, message_id)
      )
    `, (err) => {
      if (err) console.error('Error creating guild_reaction_role_messages table:', err);
      else console.log('✓ Guild reaction-role messages table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_rr_guild ON guild_reaction_role_messages(guild_id)',
      (err) => {
        if (err) console.error('Error creating idx_rr_guild:', err);
      }
    );

    // Create guild_reaction_role_mappings table (v7)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_reaction_role_mappings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        rr_message_id TEXT NOT NULL,
        emoji         TEXT NOT NULL,
        role_id       TEXT NOT NULL,
        FOREIGN KEY (rr_message_id) REFERENCES guild_reaction_role_messages(id) ON DELETE CASCADE,
        UNIQUE(rr_message_id, emoji)
      )
    `, (err) => {
      if (err) console.error('Error creating guild_reaction_role_mappings table:', err);
      else console.log('✓ Guild reaction-role mappings table initialized');
    });

    // Create guild_leveling_settings table (v7)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_leveling_settings (
        guild_id              TEXT PRIMARY KEY,
        enabled               BOOLEAN DEFAULT 0,
        xp_per_message_min    INTEGER DEFAULT 10,
        xp_per_message_max    INTEGER DEFAULT 25,
        cooldown_seconds      INTEGER DEFAULT 60,
        level_up_channel_id   TEXT,
        level_up_message      TEXT DEFAULT '🎉 GG {user}, you just reached level **{level}**!',
        ignored_channel_ids   TEXT DEFAULT '[]',
        stack_role_rewards    BOOLEAN DEFAULT 1,
        updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_leveling_settings table:', err);
      else console.log('✓ Guild leveling settings table initialized');
    });

    // Create guild_leveling_users table (v7)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_leveling_users (
        guild_id    TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        xp          INTEGER DEFAULT 0,
        level       INTEGER DEFAULT 0,
        messages    INTEGER DEFAULT 0,
        last_xp_at  INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_leveling_users table:', err);
      else console.log('✓ Guild leveling users table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_lvl_users_guild_xp ON guild_leveling_users(guild_id, xp DESC)',
      (err) => {
        if (err) console.error('Error creating idx_lvl_users_guild_xp:', err);
      }
    );

    // Create guild_leveling_rewards table (v7)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_leveling_rewards (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id  TEXT NOT NULL,
        level     INTEGER NOT NULL,
        role_id   TEXT NOT NULL,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
        UNIQUE(guild_id, level, role_id)
      )
    `, (err) => {
      if (err) console.error('Error creating guild_leveling_rewards table:', err);
      else console.log('✓ Guild leveling rewards table initialized');
    });

    // Create guild_custom_commands table (v7)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_custom_commands (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id    TEXT NOT NULL,
        trigger     TEXT NOT NULL,
        response    TEXT NOT NULL,
        match_type  TEXT DEFAULT 'exact',
        enabled     BOOLEAN DEFAULT 1,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
        UNIQUE(guild_id, trigger)
      )
    `, (err) => {
      if (err) console.error('Error creating guild_custom_commands table:', err);
      else console.log('✓ Guild custom commands table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_cc_guild ON guild_custom_commands(guild_id)',
      (err) => {
        if (err) console.error('Error creating idx_cc_guild:', err);
      }
    );

    // Create guild_social_subscriptions table (v8)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_social_subscriptions (
        id               TEXT PRIMARY KEY,
        guild_id         TEXT NOT NULL,
        platform         TEXT NOT NULL,
        account          TEXT NOT NULL,
        account_id       TEXT,
        display_name     TEXT,
        channel_id       TEXT NOT NULL,
        notify_live      BOOLEAN DEFAULT 1,
        notify_upload    BOOLEAN DEFAULT 1,
        mention_role_id  TEXT,
        message_template TEXT,
        use_embed        BOOLEAN DEFAULT 0,
        embed            TEXT,
        enabled          BOOLEAN DEFAULT 1,
        last_video_id    TEXT,
        last_live        BOOLEAN DEFAULT 0,
        last_checked_at  INTEGER DEFAULT 0,
        created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
        UNIQUE(guild_id, platform, account)
      )
    `, (err) => {
      if (err) console.error('Error creating guild_social_subscriptions table:', err);
      else console.log('✓ Guild social subscriptions table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_social_subs_guild ON guild_social_subscriptions(guild_id)',
      (err) => {
        if (err) console.error('Error creating idx_social_subs_guild:', err);
      }
    );

    // Create guild_stats_settings table (v10, category columns v11)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_stats_settings (
        guild_id        TEXT PRIMARY KEY,
        enabled         BOOLEAN DEFAULT 0,
        update_interval INTEGER DEFAULT 10,
        category_id     TEXT,
        auto_category   BOOLEAN DEFAULT 0,
        category_name   TEXT DEFAULT '📊 Statistics',
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_stats_settings table:', err);
      else console.log('✓ Guild stats settings table initialized');
    });

    // Defensive ALTERs for legacy v10 stats-settings rows created before the v11
    // category columns existed.
    const statsSettingsAlters = [
      'ALTER TABLE guild_stats_settings ADD COLUMN category_id TEXT',
      'ALTER TABLE guild_stats_settings ADD COLUMN auto_category BOOLEAN DEFAULT 0',
      "ALTER TABLE guild_stats_settings ADD COLUMN category_name TEXT DEFAULT '📊 Statistics'"
    ];
    for (const stmt of statsSettingsAlters) {
      db.run(stmt, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) {
          console.error('Warning: could not ensure guild_stats_settings column:', err.message);
        }
      });
    }

    // Create guild_stats_counters table (v10)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_stats_counters (
        id            TEXT PRIMARY KEY,
        guild_id      TEXT NOT NULL,
        type          TEXT NOT NULL,
        channel_id    TEXT,
        channel_kind  TEXT DEFAULT 'voice',
        name_template TEXT,
        auto_create   BOOLEAN DEFAULT 0,
        position      INTEGER DEFAULT 0,
        enabled       BOOLEAN DEFAULT 1,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_stats_counters table:', err);
      else console.log('✓ Guild stats counters table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_stats_counters_guild ON guild_stats_counters(guild_id)',
      (err) => {
        if (err) console.error('Error creating idx_stats_counters_guild:', err);
      }
    );

    // Create guild_stats_snapshots table (v10)
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_stats_snapshots (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id  TEXT NOT NULL,
        ts        INTEGER NOT NULL,
        members   INTEGER DEFAULT 0,
        humans    INTEGER DEFAULT 0,
        bots      INTEGER DEFAULT 0,
        online    INTEGER DEFAULT 0,
        offline   INTEGER DEFAULT 0,
        boosters  INTEGER DEFAULT 0,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_stats_snapshots table:', err);
      else console.log('✓ Guild stats snapshots table initialized');
    });
    db.run(
      'CREATE INDEX IF NOT EXISTS idx_stats_snap_guild_ts ON guild_stats_snapshots(guild_id, ts)',
      (err) => {
        if (err) console.error('Error creating idx_stats_snap_guild_ts:', err);
      }
    );

    // ----- Batch 1 modules (v12): Temp-Voice / Starboard / Suggestions -----

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_tempvoice_settings (
        guild_id       TEXT PRIMARY KEY,
        enabled        BOOLEAN DEFAULT 0,
        hub_channel_id TEXT,
        category_id    TEXT,
        name_template  TEXT DEFAULT '🔊 {user}',
        user_limit     INTEGER DEFAULT 0,
        updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_tempvoice_settings table:', err);
      else console.log('✓ Guild tempvoice settings table initialized');
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_tempvoice_channels (
        channel_id  TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        owner_id    TEXT,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_tempvoice_channels table:', err);
      else console.log('✓ Guild tempvoice channels table initialized');
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_tempvoice_channels_guild ON guild_tempvoice_channels(guild_id)', (err) => {
      if (err) console.error('Error creating idx_tempvoice_channels_guild:', err);
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_starboard_settings (
        guild_id        TEXT PRIMARY KEY,
        enabled         BOOLEAN DEFAULT 0,
        star_channel_id TEXT,
        emoji           TEXT DEFAULT '⭐',
        threshold       INTEGER DEFAULT 3,
        self_star       BOOLEAN DEFAULT 0,
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_starboard_settings table:', err);
      else console.log('✓ Guild starboard settings table initialized');
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_starboard_entries (
        guild_id        TEXT NOT NULL,
        message_id      TEXT NOT NULL,
        channel_id      TEXT,
        star_message_id TEXT,
        count           INTEGER DEFAULT 0,
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (guild_id, message_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_starboard_entries table:', err);
      else console.log('✓ Guild starboard entries table initialized');
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_suggestion_settings (
        guild_id           TEXT PRIMARY KEY,
        enabled            BOOLEAN DEFAULT 0,
        suggest_channel_id TEXT,
        upvote_emoji       TEXT DEFAULT '👍',
        downvote_emoji     TEXT DEFAULT '👎',
        updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_suggestion_settings table:', err);
      else console.log('✓ Guild suggestion settings table initialized');
    });

    // ----- Batch 2 modules (v13): Birthday / Scheduled / Anti-Raid -----

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_birthday_settings (
        guild_id            TEXT PRIMARY KEY,
        enabled             BOOLEAN DEFAULT 0,
        announce_channel_id TEXT,
        message_template    TEXT DEFAULT '🎉 Happy Birthday {user}!',
        birthday_role_id    TEXT,
        updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_birthday_settings table:', err);
      else console.log('✓ Guild birthday settings table initialized');
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_birthdays (
        guild_id    TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        month       INTEGER NOT NULL,
        day         INTEGER NOT NULL,
        year        INTEGER,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_birthdays table:', err);
      else console.log('✓ Guild birthdays table initialized');
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_birthdays_md ON guild_birthdays(month, day)', (err) => {
      if (err) console.error('Error creating idx_birthdays_md:', err);
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_scheduled_messages (
        id               TEXT PRIMARY KEY,
        guild_id         TEXT NOT NULL,
        channel_id       TEXT NOT NULL,
        content          TEXT,
        schedule_type    TEXT DEFAULT 'once',
        run_at           INTEGER DEFAULT 0,
        interval_seconds INTEGER DEFAULT 0,
        enabled          BOOLEAN DEFAULT 1,
        last_run         INTEGER DEFAULT 0,
        created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_scheduled_messages table:', err);
      else console.log('✓ Guild scheduled messages table initialized');
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_scheduled_guild ON guild_scheduled_messages(guild_id)', (err) => {
      if (err) console.error('Error creating idx_scheduled_guild:', err);
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_antiraid_settings (
        guild_id          TEXT PRIMARY KEY,
        enabled           BOOLEAN DEFAULT 0,
        join_rate_count   INTEGER DEFAULT 5,
        join_rate_seconds INTEGER DEFAULT 10,
        action            TEXT DEFAULT 'alert',
        account_age_days  INTEGER DEFAULT 0,
        alert_channel_id  TEXT,
        updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_antiraid_settings table:', err);
      else console.log('✓ Guild antiraid settings table initialized');
    });

    // ----- Batch 3 Part A (v14): Verification / Role-Menus -----

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_verification_settings (
        guild_id         TEXT PRIMARY KEY,
        enabled          BOOLEAN DEFAULT 0,
        channel_id       TEXT,
        verified_role_id TEXT,
        message          TEXT DEFAULT 'Click the button below to verify and unlock the server.',
        button_label     TEXT DEFAULT 'Verify',
        panel_message_id TEXT,
        updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_verification_settings table:', err);
      else console.log('✓ Guild verification settings table initialized');
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_role_menus (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        channel_id  TEXT,
        message_id  TEXT,
        name        TEXT,
        menu_type   TEXT DEFAULT 'buttons',
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_role_menus table:', err);
      else console.log('✓ Guild role menus table initialized');
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_role_menus_guild ON guild_role_menus(guild_id)', (err) => {
      if (err) console.error('Error creating idx_role_menus_guild:', err);
    });
    db.run('ALTER TABLE guild_role_menus ADD COLUMN exclusive BOOLEAN DEFAULT 0', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_role_menus.exclusive:', err.message);
    });
    db.run('ALTER TABLE guild_role_menus ADD COLUMN use_embed BOOLEAN DEFAULT 0', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_role_menus.use_embed:', err.message);
    });
    db.run('ALTER TABLE guild_role_menus ADD COLUMN embed TEXT', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_role_menus.embed:', err.message);
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_role_menu_options (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        menu_id   TEXT NOT NULL,
        role_id   TEXT NOT NULL,
        label     TEXT,
        emoji     TEXT,
        FOREIGN KEY (menu_id) REFERENCES guild_role_menus(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_role_menu_options table:', err);
      else console.log('✓ Guild role menu options table initialized');
    });

    // ----- Batch 3 Part B (v15): Tickets / Giveaways -----

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_ticket_settings (
        guild_id         TEXT PRIMARY KEY,
        enabled          BOOLEAN DEFAULT 0,
        panel_channel_id TEXT,
        category_id      TEXT,
        support_role_id  TEXT,
        panel_message    TEXT DEFAULT 'Need help? Click below to open a ticket.',
        button_label     TEXT DEFAULT 'Open Ticket',
        panel_message_id TEXT,
        updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_ticket_settings table:', err);
      else console.log('✓ Guild ticket settings table initialized');
    });
    // v16 + v18 ticket-settings columns (idempotent).
    [
      'ALTER TABLE guild_ticket_settings ADD COLUMN transcript_channel_id TEXT',
      "ALTER TABLE guild_ticket_settings ADD COLUMN panel_type TEXT DEFAULT 'dropdown'",
      'ALTER TABLE guild_ticket_settings ADD COLUMN panel_embed TEXT',
      'ALTER TABLE guild_ticket_settings ADD COLUMN welcome_embed TEXT',
      'ALTER TABLE guild_ticket_settings ADD COLUMN ping_role_id TEXT',
      "ALTER TABLE guild_ticket_settings ADD COLUMN naming_template TEXT DEFAULT 'ticket-{user}'",
      'ALTER TABLE guild_ticket_settings ADD COLUMN claim_enabled BOOLEAN DEFAULT 1',
      'ALTER TABLE guild_ticket_settings ADD COLUMN close_confirm BOOLEAN DEFAULT 1',
      'ALTER TABLE guild_ticket_settings ADD COLUMN rating_enabled BOOLEAN DEFAULT 0',
      "ALTER TABLE guild_ticket_settings ADD COLUMN rating_mode TEXT DEFAULT 'channel'",
      'ALTER TABLE guild_ticket_settings ADD COLUMN log_channel_id TEXT'
    ].forEach((stmt) => db.run(stmt, (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_ticket_settings ALTER:', err.message);
    }));

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_ticket_categories (
        id              TEXT PRIMARY KEY,
        guild_id        TEXT NOT NULL,
        label           TEXT,
        emoji           TEXT,
        description     TEXT,
        category_id     TEXT,
        support_role_id TEXT,
        ping_role_id    TEXT,
        welcome_message TEXT,
        button_style    TEXT DEFAULT 'primary',
        position        INTEGER DEFAULT 0,
        enabled         BOOLEAN DEFAULT 1,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_ticket_categories table:', err);
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_ticket_categories_guild ON guild_ticket_categories(guild_id)', () => {});

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_tickets (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        channel_id  TEXT,
        user_id     TEXT,
        status      TEXT DEFAULT 'open',
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_tickets table:', err);
      else console.log('✓ Guild tickets table initialized');
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_tickets_guild ON guild_tickets(guild_id)', (err) => {
      if (err) console.error('Error creating idx_tickets_guild:', err);
    });
    // v18 per-ticket state columns (idempotent).
    [
      'ALTER TABLE guild_tickets ADD COLUMN ticket_category_id TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN number INTEGER DEFAULT 0',
      'ALTER TABLE guild_tickets ADD COLUMN claimed_by TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN rating INTEGER',
      'ALTER TABLE guild_tickets ADD COLUMN rating_comment TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN closed_by TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN closed_at DATETIME',
      "ALTER TABLE guild_tickets ADD COLUMN extra_user_ids TEXT DEFAULT '[]'"
    ].forEach((stmt) => db.run(stmt, (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_tickets ALTER:', err.message);
    }));

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_giveaways (
        id            TEXT PRIMARY KEY,
        guild_id      TEXT NOT NULL,
        channel_id    TEXT,
        message_id    TEXT,
        prize         TEXT,
        winners_count INTEGER DEFAULT 1,
        ends_at       INTEGER DEFAULT 0,
        ended         BOOLEAN DEFAULT 0,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_giveaways table:', err);
      else console.log('✓ Guild giveaways table initialized');
    });
    db.run('CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON guild_giveaways(guild_id)', (err) => {
      if (err) console.error('Error creating idx_giveaways_guild:', err);
    });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_giveaway_entries (
        giveaway_id TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        PRIMARY KEY (giveaway_id, user_id),
        FOREIGN KEY (giveaway_id) REFERENCES guild_giveaways(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating guild_giveaway_entries table:', err);
      else console.log('✓ Guild giveaway entries table initialized');
    });

    // ----- New modules (v23-v27): Counting / Polls / Invite-Tracking / Applications / Economy -----

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_counting_settings (
        guild_id      TEXT PRIMARY KEY,
        enabled       BOOLEAN DEFAULT 0,
        channel_id    TEXT,
        current_count INTEGER DEFAULT 0,
        last_user_id  TEXT,
        high_score    INTEGER DEFAULT 0,
        reset_on_fail BOOLEAN DEFAULT 1,
        count_emoji   TEXT DEFAULT '✅',
        updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_counting_settings table:', err); });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_polls (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        channel_id  TEXT,
        message_id  TEXT,
        question    TEXT,
        options     TEXT DEFAULT '[]',
        multi       BOOLEAN DEFAULT 0,
        ends_at     INTEGER DEFAULT 0,
        ended       BOOLEAN DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_polls table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_polls_guild ON guild_polls(guild_id)', () => {});
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_poll_votes (
        poll_id      TEXT NOT NULL,
        user_id      TEXT NOT NULL,
        option_index INTEGER NOT NULL,
        PRIMARY KEY (poll_id, user_id, option_index),
        FOREIGN KEY (poll_id) REFERENCES guild_polls(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_poll_votes table:', err); });

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_invite_settings (
        guild_id         TEXT PRIMARY KEY,
        enabled          BOOLEAN DEFAULT 0,
        log_channel_id   TEXT,
        message_template TEXT DEFAULT '👋 {user} joined — invited by {inviter} (now {invites} invites)',
        updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_invite_settings table:', err); });
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_invites (
        guild_id    TEXT NOT NULL,
        code        TEXT NOT NULL,
        inviter_id  TEXT,
        uses        INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, code),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_invites table:', err); });
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_member_invites (
        guild_id    TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        inviter_id  TEXT,
        code        TEXT,
        joined_at   INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_member_invites table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_member_invites_inviter ON guild_member_invites(guild_id, inviter_id)', () => {});

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_application_forms (
        id               TEXT PRIMARY KEY,
        guild_id         TEXT NOT NULL,
        name             TEXT,
        description      TEXT,
        questions        TEXT DEFAULT '[]',
        review_channel_id TEXT,
        accepted_role_id TEXT,
        panel_channel_id TEXT,
        panel_message_id TEXT,
        button_label     TEXT DEFAULT 'Apply',
        position         INTEGER DEFAULT 0,
        enabled          BOOLEAN DEFAULT 1,
        created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_application_forms table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_application_forms_guild ON guild_application_forms(guild_id)', () => {});
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_applications (
        id          TEXT PRIMARY KEY,
        form_id     TEXT NOT NULL,
        guild_id    TEXT NOT NULL,
        user_id     TEXT,
        answers     TEXT DEFAULT '[]',
        status      TEXT DEFAULT 'pending',
        reviewer_id TEXT,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_applications table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_applications_guild ON guild_applications(guild_id)', () => {});

    db.run(`
      CREATE TABLE IF NOT EXISTS guild_economy_settings (
        guild_id        TEXT PRIMARY KEY,
        enabled         BOOLEAN DEFAULT 0,
        currency_name   TEXT DEFAULT 'coins',
        currency_symbol TEXT DEFAULT '🪙',
        start_balance   INTEGER DEFAULT 0,
        daily_amount    INTEGER DEFAULT 200,
        work_min        INTEGER DEFAULT 50,
        work_max        INTEGER DEFAULT 250,
        work_cooldown   INTEGER DEFAULT 3600,
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_economy_settings table:', err); });
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_economy_users (
        guild_id    TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        balance     INTEGER DEFAULT 0,
        last_daily  INTEGER DEFAULT 0,
        last_work   INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_economy_users table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_economy_users_balance ON guild_economy_users(guild_id, balance DESC)', () => {});
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_economy_shop (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        name        TEXT,
        description TEXT,
        price       INTEGER DEFAULT 0,
        role_id     TEXT,
        position    INTEGER DEFAULT 0,
        enabled     BOOLEAN DEFAULT 1,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_economy_shop table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_economy_shop_guild ON guild_economy_shop(guild_id)', () => {});

    // ----- Games category (v28): shared settings + scores -----
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_games_settings (
        guild_id          TEXT PRIMARY KEY,
        games_channel_id  TEXT,
        tictactoe_enabled BOOLEAN DEFAULT 0,
        rps_enabled       BOOLEAN DEFAULT 0,
        trivia_enabled    BOOLEAN DEFAULT 0,
        connect4_enabled  BOOLEAN DEFAULT 0,
        hangman_enabled   BOOLEAN DEFAULT 0,
        poker_enabled     BOOLEAN DEFAULT 0,
        poker_table_theme TEXT DEFAULT 'classic',
        games_language    TEXT DEFAULT 'en',
        updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_games_settings table:', err); });
    db.run('ALTER TABLE guild_games_settings ADD COLUMN poker_enabled BOOLEAN DEFAULT 0', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_games_settings.poker_enabled:', err.message);
    });
    db.run("ALTER TABLE guild_games_settings ADD COLUMN poker_table_theme TEXT DEFAULT 'classic'", (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_games_settings.poker_table_theme:', err.message);
    });
    db.run("ALTER TABLE guild_games_settings ADD COLUMN games_language TEXT DEFAULT 'en'", (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_games_settings.games_language:', err.message);
    });
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_game_scores (
        guild_id TEXT NOT NULL,
        user_id  TEXT NOT NULL,
        game     TEXT NOT NULL,
        wins     INTEGER DEFAULT 0,
        plays    INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id, game),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_game_scores table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_game_scores_lb ON guild_game_scores(guild_id, game, wins DESC)', () => {});

    // ----- Server Backup & Restore (v32): snapshots + async job queue -----
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_backups (
        id             TEXT PRIMARY KEY,
        guild_id       TEXT NOT NULL,
        name           TEXT,
        guild_name     TEXT,
        guild_icon_url TEXT,
        channels_count INTEGER DEFAULT 0,
        roles_count    INTEGER DEFAULT 0,
        data           TEXT,
        created_at     INTEGER DEFAULT 0,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_backups table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_backups_guild ON guild_backups(guild_id)', () => {});
    db.run(`
      CREATE TABLE IF NOT EXISTS guild_backup_jobs (
        id          TEXT PRIMARY KEY,
        guild_id    TEXT NOT NULL,
        type        TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'pending',
        backup_id   TEXT,
        mode        TEXT,
        message     TEXT,
        created_at  INTEGER DEFAULT 0,
        updated_at  INTEGER DEFAULT 0,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
      )
    `, (err) => { if (err) console.error('Error creating guild_backup_jobs table:', err); });
    db.run('CREATE INDEX IF NOT EXISTS idx_backup_jobs_status ON guild_backup_jobs(status)', () => {});
    db.run('ALTER TABLE guild_backup_jobs ADD COLUMN parts TEXT', (err) => {
      if (err && !/duplicate column name/i.test(err.message)) console.error('Warning: guild_backup_jobs.parts:', err.message);
    });

    // Create audit_log table
    db.run(`
      CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id TEXT,
        action TEXT NOT NULL,
        changes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(discord_id) ON DELETE SET NULL,
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE SET NULL
      )
    `, (err) => {
      if (err) console.error('Error creating audit_log table:', err);
      else console.log('✓ Audit log table initialized');
    });

    // V22 system settings (key/value) — backs the global maintenance mode.
    db.run(`
      CREATE TABLE IF NOT EXISTS system_settings (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `, (err) => {
      if (err) console.error('Error creating system_settings table:', err);
      else console.log('✓ System settings table initialized');
    });

    console.log('Database schema initialization complete');
    // Final serialized statement: its callback runs after every CREATE above,
    // so this is the safe point to signal "all tables exist".
    db.run('SELECT 1', () => resolveDbReady());
  });
}

// Helper functions for common queries

/**
 * Get a guild by ID
 */
export function getGuild(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guilds WHERE id = ?', [guildId], (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
}

// ============================================================
// Premium tiers / module gating (Schema v21)
// ============================================================

/** Ordered tiers. Index = rank (free=0 < basic=1 < pro=2). */
export const PREMIUM_TIERS = ['free', 'basic', 'pro'];

export function tierRank(tier) {
  const i = PREMIUM_TIERS.indexOf(tier);
  return i < 0 ? 0 : i;
}

/**
 * Module key = dashboard route segment → minimum tier required to use it.
 * Free: core onboarding + moderation. Basic: engagement. Pro: advanced/heavy.
 * Single source of truth for both the dashboard locks and the bot-side gates.
 */
export const MODULE_TIERS = {
  welcome: 'free', leave: 'free', autorole: 'free', logs: 'free',
  moderation: 'free', 'reaction-roles': 'free', verification: 'free',
  suggestions: 'free', 'custom-commands': 'free',
  counting: 'free', polls: 'free',
  leveling: 'basic', starboard: 'basic', tempvoice: 'basic',
  birthday: 'basic', rolemenus: 'basic', antiraid: 'basic',
  invitetracking: 'basic',
  games: 'basic', tictactoe: 'basic', rps: 'basic', trivia: 'basic', connect4: 'basic', hangman: 'basic', poker: 'basic',
  social: 'pro', stats: 'pro', tickets: 'pro', giveaways: 'pro', scheduled: 'pro',
  applications: 'pro', economy: 'pro', backup: 'pro'
};

/** Marketing/pricing catalog surfaced on the public landing page. */
export const PLAN_CATALOG = {
  currency: 'EUR',
  tiers: [
    { key: 'free', price_monthly: 0 },
    { key: 'basic', price_monthly: 2.99 },
    { key: 'pro', price_monthly: 5.99 }
  ],
  modules: Object.entries(MODULE_TIERS).map(([key, tier]) => ({ key, tier }))
};

function premiumNowSeconds() { return Math.floor(Date.now() / 1000); }

/** Effective tier for a guilds row, honoring premium_until expiry. */
export function effectiveTier(row) {
  if (!row) return 'free';
  const tier = PREMIUM_TIERS.includes(row.premium_tier) ? row.premium_tier : 'free';
  const until = row.premium_until ? Number(row.premium_until) : 0;
  if (until && until > 0 && until <= premiumNowSeconds()) return 'free';
  return tier;
}

export function moduleUnlocked(tier, moduleKey) {
  const need = MODULE_TIERS[moduleKey] || 'free';
  return tierRank(tier) >= tierRank(need);
}

/** moduleKey → bool unlock map for a given effective tier. */
export function moduleUnlockMap(tier) {
  const out = {};
  for (const key of Object.keys(MODULE_TIERS)) out[key] = moduleUnlocked(tier, key);
  return out;
}

/** Read a guild's raw premium fields (null if guild unknown). */
export function getGuildPremium(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT premium_tier, premium_source, premium_until FROM guilds WHERE id = ?', [guildId], (err, row) => {
      if (err) reject(err);
      else resolve(row || null);
    });
  });
}

/** Owner/SKU: set a guild's premium tier. source ∈ {manual|sku}; until = unix s or null. */
export function setGuildPremium(guildId, { tier, source = 'manual', until = null } = {}) {
  return new Promise((resolve, reject) => {
    const t = PREMIUM_TIERS.includes(tier) ? tier : 'free';
    const src = t === 'free' ? null : (source === 'sku' ? 'sku' : 'manual');
    const u = t === 'free' ? null : (until && Number(until) > 0 ? Math.floor(Number(until)) : null);
    db.run(
      'UPDATE guilds SET premium_tier = ?, premium_source = ?, premium_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
      [t, src, u, guildId],
      function (err) { if (err) reject(err); else resolve(this.changes); }
    );
  });
}

/**
 * SQL fragment: `<column>` belongs to a guild whose EFFECTIVE tier (expiry-aware)
 * is at least `minTier`. Used to make premium loop-cog features inert server-side
 * the moment a guild's tier lapses (e.g. SKU expired, owner downgraded).
 */
export function tierFilterSql(minTier, column = 'guild_id') {
  const r = tierRank(minTier);
  return `${column} IN (SELECT id FROM guilds WHERE (CASE WHEN (premium_until IS NULL OR premium_until = 0 OR premium_until > strftime('%s','now')) THEN (CASE premium_tier WHEN 'pro' THEN 2 WHEN 'basic' THEN 1 ELSE 0 END) ELSE 0 END) >= ${r})`;
}

/**
 * Bot: bulk-sync Discord SKU entitlements. Sets sku-sourced tiers for the listed
 * guilds and DOWNGRADES any guild whose premium previously came from 'sku' but is
 * no longer entitled. Manual (owner-set) premium is never touched.
 *   entitlements: [{ guild_id, tier, until? }]
 */
export function syncSkuEntitlements(entitlements) {
  return runInTransaction(async () => {
    const list = Array.isArray(entitlements) ? entitlements : [];
    const keep = new Set();
    for (const e of list) {
      if (!e || !isSnowflake(e.guild_id)) continue;
      const tier = PREMIUM_TIERS.includes(e.tier) ? e.tier : 'free';
      if (tier === 'free') continue;
      keep.add(e.guild_id);
      const until = e.until && Number(e.until) > 0 ? Math.floor(Number(e.until)) : null;
      await new Promise((resolve, reject) => {
        db.run(
          "UPDATE guilds SET premium_tier = ?, premium_source = 'sku', premium_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
          [tier, until, e.guild_id],
          (err) => (err ? reject(err) : resolve())
        );
      });
    }
    const skuGuilds = await new Promise((resolve, reject) => {
      db.all("SELECT id FROM guilds WHERE premium_source = 'sku'", [], (err, rows) => (err ? reject(err) : resolve(rows || [])));
    });
    let downgraded = 0;
    for (const g of skuGuilds) {
      if (keep.has(g.id)) continue;
      downgraded++;
      await new Promise((resolve, reject) => {
        db.run(
          "UPDATE guilds SET premium_tier = 'free', premium_source = NULL, premium_until = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
          [g.id],
          (err) => (err ? reject(err) : resolve())
        );
      });
    }
    return { synced: keep.size, downgraded };
  });
}

/**
 * Get all guilds
 */
export function getAllGuilds() {
  return new Promise((resolve, reject) => {
    db.all('SELECT * FROM guilds WHERE enabled = 1 ORDER BY created_at DESC', (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

/**
 * Create a new guild
 */
export function createGuild(guildId, guildName, guildIconUrl) {
  return new Promise((resolve, reject) => {
    db.run(
      'INSERT INTO guilds (id, guild_name, guild_icon_url) VALUES (?, ?, ?)',
      [guildId, guildName, guildIconUrl],
      function(err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

/**
 * INSERT-or-UPDATE a guilds row. Used by the bot's channel/role/presence sync
 * so the guilds table never lags behind the bot's view of the world (and so
 * the FK on guild_channels/guild_roles is satisfied even if no dashboard user
 * has logged into that guild yet).
 *
 * Updates name / icon only when non-empty values are passed — so a later
 * OAuth-reconcile with real data won't be overwritten by a bot ping that
 * happened to omit them.
 */
export function upsertGuildRow(guildId, guildName, guildIconUrl) {
  return new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO guilds (id, guild_name, guild_icon_url)
       VALUES (?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         guild_name = COALESCE(NULLIF(excluded.guild_name, ''), guild_name),
         guild_icon_url = COALESCE(NULLIF(excluded.guild_icon_url, ''), guild_icon_url),
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, guildName || guildId, guildIconUrl || null],
      function(err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Update guild information
 */
export function updateGuild(guildId, updates) {
  return new Promise((resolve, reject) => {
    const fields = [];
    const values = [];
    
    for (const [key, value] of Object.entries(updates)) {
      fields.push(`${key} = ?`);
      values.push(value);
    }
    
    fields.push('updated_at = CURRENT_TIMESTAMP');
    values.push(guildId);
    
    const query = `UPDATE guilds SET ${fields.join(', ')} WHERE id = ?`;
    
    db.run(query, values, function(err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

// ----- Welcome/Leave embed helpers -----

const DEFAULT_EMBED_COLOR = '#5865F2';

const DEFAULT_EMBED = {
  title: '',
  description: '',
  color: DEFAULT_EMBED_COLOR,
  thumbnail: '',
  image: '',
  footer: '',
  show_timestamp: false,
  author_name: '',
  author_icon_url: ''
};

const EMBED_CAPS = {
  title: 256,
  description: 4096,
  footer: 2048,
  author_name: 256
};

const COLOR_REGEX = /^#[0-9A-Fa-f]{6}$/;
const URL_REGEX = /^https?:\/\//i;
const AVATAR_PLACEHOLDER = '{user.avatar}';

function truncate(value, max) {
  if (value == null) return '';
  const str = String(value);
  return str.length > max ? str.substring(0, max) : str;
}

function sanitizeColor(value) {
  if (typeof value === 'string' && COLOR_REGEX.test(value)) return value;
  return DEFAULT_EMBED_COLOR;
}

function sanitizeUrlLike(value) {
  if (value == null) return '';
  const str = String(value);
  if (str === '') return '';
  if (str === AVATAR_PLACEHOLDER) return AVATAR_PLACEHOLDER;
  if (URL_REGEX.test(str)) return str;
  return '';
}

function sanitizeEmbed(input) {
  const source = (input && typeof input === 'object') ? input : {};
  return {
    title: truncate(source.title ?? '', EMBED_CAPS.title),
    description: truncate(source.description ?? '', EMBED_CAPS.description),
    color: sanitizeColor(source.color),
    thumbnail: sanitizeUrlLike(source.thumbnail),
    image: sanitizeUrlLike(source.image),
    footer: truncate(source.footer ?? '', EMBED_CAPS.footer),
    show_timestamp: !!source.show_timestamp,
    author_name: truncate(source.author_name ?? '', EMBED_CAPS.author_name),
    author_icon_url: sanitizeUrlLike(source.author_icon_url)
  };
}

function parseEmbedColumn(raw) {
  if (raw == null || raw === '') return { ...DEFAULT_EMBED };
  if (typeof raw === 'object') return sanitizeEmbed(raw);
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') return sanitizeEmbed(parsed);
    } catch {
      // fall through to default
    }
  }
  return { ...DEFAULT_EMBED };
}

function clampDeleteAfter(value) {
  let n = Number(value);
  if (!Number.isFinite(n)) n = 0;
  n = Math.trunc(n);
  if (n < 0) n = 0;
  if (n > 600) n = 600;
  return n;
}

export const WELCOME_LEAVE_DEFAULTS = {
  welcome_enabled: true,
  welcome_channel_id: null,
  welcome_message: 'Welcome {user}!',
  leave_enabled: true,
  leave_channel_id: null,
  leave_message: '{user} has left.',
  welcome_use_embed: false,
  welcome_embed: { ...DEFAULT_EMBED },
  welcome_ping_user: false,
  welcome_dm_enabled: false,
  welcome_dm_message: '',
  welcome_delete_after: 0,
  leave_use_embed: false,
  leave_embed: { ...DEFAULT_EMBED },
  leave_delete_after: 0
};

/**
 * Get guild settings — returns the row with embed columns parsed into objects.
 * Booleans and integers stay as their stored SQLite forms (0/1) so the existing
 * tests that assert on `welcome_enabled === 1` keep passing; the bot/route
 * layers convert them to JS booleans when shaping the public response.
 */
export function getGuildSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve(row);
      row.welcome_embed = parseEmbedColumn(row.welcome_embed);
      row.leave_embed = parseEmbedColumn(row.leave_embed);
      resolve(row);
    });
  });
}

/**
 * Create or update guild settings.
 *
 * Accepts the full extended Welcome/Leave shape (legacy callers passing only
 * the original 6 fields still work — missing new fields fall back to the
 * existing row's values, or to WELCOME_LEAVE_DEFAULTS for fresh rows).
 *
 *  - Booleans coerced to 0/1.
 *  - Strings truncated to per-field caps.
 *  - color validated; invalid → '#5865F2'.
 *  - URL-ish embed fields accept '', '{user.avatar}', or http(s) URLs.
 *  - *_delete_after clamped to [0, 600].
 *  - welcome_dm_message truncated to 2000 chars.
 *  - embed objects JSON-stringified before storage.
 */
export function upsertGuildSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_settings WHERE guild_id = ?', [guildId], (selErr, existing) => {
      if (selErr) return reject(selErr);

      const base = existing
        ? {
            welcome_enabled: !!existing.welcome_enabled,
            welcome_channel_id: existing.welcome_channel_id ?? null,
            welcome_message: existing.welcome_message ?? WELCOME_LEAVE_DEFAULTS.welcome_message,
            leave_enabled: !!existing.leave_enabled,
            leave_channel_id: existing.leave_channel_id ?? null,
            leave_message: existing.leave_message ?? WELCOME_LEAVE_DEFAULTS.leave_message,
            welcome_use_embed: !!existing.welcome_use_embed,
            welcome_embed: parseEmbedColumn(existing.welcome_embed),
            welcome_ping_user: !!existing.welcome_ping_user,
            welcome_dm_enabled: !!existing.welcome_dm_enabled,
            welcome_dm_message: existing.welcome_dm_message ?? '',
            welcome_delete_after: existing.welcome_delete_after ?? 0,
            leave_use_embed: !!existing.leave_use_embed,
            leave_embed: parseEmbedColumn(existing.leave_embed),
            leave_delete_after: existing.leave_delete_after ?? 0
          }
        : { ...WELCOME_LEAVE_DEFAULTS };

      const pick = (key) => (settings[key] !== undefined ? settings[key] : base[key]);

      const welcomeEnabled = pick('welcome_enabled') ? 1 : 0;
      const welcomeChannelId = pick('welcome_channel_id') || null;
      const welcomeMessage = truncate(pick('welcome_message') || WELCOME_LEAVE_DEFAULTS.welcome_message, 1000);
      const leaveEnabled = pick('leave_enabled') ? 1 : 0;
      const leaveChannelId = pick('leave_channel_id') || null;
      const leaveMessage = truncate(pick('leave_message') || WELCOME_LEAVE_DEFAULTS.leave_message, 1000);

      const welcomeUseEmbed = pick('welcome_use_embed') ? 1 : 0;
      const welcomeEmbed = sanitizeEmbed(pick('welcome_embed'));
      const welcomePingUser = pick('welcome_ping_user') ? 1 : 0;
      const welcomeDmEnabled = pick('welcome_dm_enabled') ? 1 : 0;
      const welcomeDmMessage = truncate(pick('welcome_dm_message') || '', 2000);
      const welcomeDeleteAfter = clampDeleteAfter(pick('welcome_delete_after'));

      const leaveUseEmbed = pick('leave_use_embed') ? 1 : 0;
      const leaveEmbed = sanitizeEmbed(pick('leave_embed'));
      const leaveDeleteAfter = clampDeleteAfter(pick('leave_delete_after'));

      db.run(
        `INSERT INTO guild_settings (
           guild_id,
           welcome_enabled, welcome_channel_id, welcome_message,
           leave_enabled, leave_channel_id, leave_message,
           welcome_use_embed, welcome_embed, welcome_ping_user,
           welcome_dm_enabled, welcome_dm_message, welcome_delete_after,
           leave_use_embed, leave_embed, leave_delete_after
         )
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(guild_id) DO UPDATE SET
           welcome_enabled = excluded.welcome_enabled,
           welcome_channel_id = excluded.welcome_channel_id,
           welcome_message = excluded.welcome_message,
           leave_enabled = excluded.leave_enabled,
           leave_channel_id = excluded.leave_channel_id,
           leave_message = excluded.leave_message,
           welcome_use_embed = excluded.welcome_use_embed,
           welcome_embed = excluded.welcome_embed,
           welcome_ping_user = excluded.welcome_ping_user,
           welcome_dm_enabled = excluded.welcome_dm_enabled,
           welcome_dm_message = excluded.welcome_dm_message,
           welcome_delete_after = excluded.welcome_delete_after,
           leave_use_embed = excluded.leave_use_embed,
           leave_embed = excluded.leave_embed,
           leave_delete_after = excluded.leave_delete_after,
           updated_at = CURRENT_TIMESTAMP`,
        [
          guildId,
          welcomeEnabled, welcomeChannelId, welcomeMessage,
          leaveEnabled, leaveChannelId, leaveMessage,
          welcomeUseEmbed, JSON.stringify(welcomeEmbed), welcomePingUser,
          welcomeDmEnabled, welcomeDmMessage, welcomeDeleteAfter,
          leaveUseEmbed, JSON.stringify(leaveEmbed), leaveDeleteAfter
        ],
        function (err) {
          if (err) reject(err);
          else resolve(this.lastID);
        }
      );
    });
  });
}

/**
 * Get a user by Discord ID
 */
export function getUser(discordId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM users WHERE discord_id = ?', [discordId], (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
}

/**
 * Create or update a user
 */
export function upsertUser(discordId, userData) {
  return new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO users (discord_id, username, email, avatar_url, access_token, refresh_token, token_expires_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(discord_id) DO UPDATE SET
       username = excluded.username,
       email = excluded.email,
       avatar_url = excluded.avatar_url,
       access_token = excluded.access_token,
       refresh_token = excluded.refresh_token,
       token_expires_at = excluded.token_expires_at,
       updated_at = CURRENT_TIMESTAMP`,
      [
        discordId,
        userData.username,
        userData.email,
        userData.avatar_url,
        userData.access_token,
        userData.refresh_token,
        userData.token_expires_at ?? null
      ],
      function(err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

/**
 * Update only the Discord OAuth tokens (and expiry) for a user.
 */
export function updateUserTokens(discordId, accessToken, refreshToken, tokenExpiresAt) {
  return new Promise((resolve, reject) => {
    db.run(
      `UPDATE users
       SET access_token = ?,
           refresh_token = ?,
           token_expires_at = ?,
           updated_at = CURRENT_TIMESTAMP
       WHERE discord_id = ?`,
      [accessToken, refreshToken, tokenExpiresAt ?? null, discordId],
      function(err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Get user guilds with roles (alle Memberships)
 */
export function getUserGuilds(userId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT g.*, ug.owner, ug.admin FROM user_guilds ug
       JOIN guilds g ON ug.guild_id = g.id
       WHERE ug.user_id = ? AND g.enabled = 1
       ORDER BY g.guild_name ASC`,
      [userId],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

/**
 * Get only guilds the user can actually manage (Owner OR Admin).
 * Used for the dashboard guild selector — Member-only Guilds werden ausgeblendet.
 */
export function getUserManageableGuilds(userId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT g.*, ug.owner, ug.admin FROM user_guilds ug
       JOIN guilds g ON ug.guild_id = g.id
       WHERE ug.user_id = ?
         AND g.enabled = 1
         AND (ug.owner = 1 OR ug.admin = 1)
       ORDER BY g.guild_name ASC`,
      [userId],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

/**
 * Add user to a guild
 */
export function addUserToGuild(userId, guildId, owner = false, admin = false) {
  return new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO user_guilds (user_id, guild_id, owner, admin)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(user_id, guild_id) DO UPDATE SET
       owner = excluded.owner,
       admin = excluded.admin`,
      [userId, guildId, owner ? 1 : 0, admin ? 1 : 0],
      function(err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

/**
 * Check if user has access to a guild
 */
export function userHasGuildAccess(userId, guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM user_guilds WHERE user_id = ? AND guild_id = ?',
      [userId, guildId],
      (err, row) => {
        if (err) reject(err);
        else resolve(!!row);
      }
    );
  });
}

/**
 * Check if user is guild owner or admin
 */
export function userIsGuildAdmin(userId, guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM user_guilds WHERE user_id = ? AND guild_id = ? AND (owner = 1 OR admin = 1)',
      [userId, guildId],
      (err, row) => {
        if (err) reject(err);
        else resolve(!!row);
      }
    );
  });
}

/**
 * Log an action to audit log
 */
export function logAuditAction(userId, guildId, action, changes = null) {
  return new Promise((resolve, reject) => {
    db.run(
      'INSERT INTO audit_log (user_id, guild_id, action, changes) VALUES (?, ?, ?, ?)',
      [userId, guildId, action, changes ? JSON.stringify(changes) : null],
      function(err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

/**
 * Get audit log for a guild
 */
export function getGuildAuditLog(guildId, limit = 100) {
  return new Promise((resolve, reject) => {
    db.all(
      'SELECT * FROM audit_log WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?',
      [guildId, limit],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

// ===== Owner-only admin moderation (block users / guilds) =====

/**
 * True if the given Discord user is currently blocked by the system owner.
 * Used by requireSession and the OAuth callback to lock blocked users out.
 */
export function isUserBlocked(discordId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT blocked, blocked_until FROM users WHERE discord_id = ?', [discordId], (err, row) => {
      if (err) reject(err);
      else resolve(isEffectivelyBlocked(row));
    });
  });
}

/**
 * True if the given guild is currently blocked by the system owner.
 * Used to gate dashboard guild routes and the bot's per-guild endpoints.
 */
export function isGuildBlocked(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT blocked, blocked_until FROM guilds WHERE id = ?', [guildId], (err, row) => {
      if (err) reject(err);
      else resolve(isEffectivelyBlocked(row));
    });
  });
}

/**
 * A row is effectively blocked when `blocked = 1` AND either it's a permanent
 * block (`blocked_until` is null) or the expiry is still in the future. An
 * elapsed temp-ban auto-expires here — no background sweeper needed.
 */
function isEffectivelyBlocked(row) {
  if (!row || !row.blocked) return false;
  if (!row.blocked_until) return true;
  return row.blocked_until > Math.floor(Date.now() / 1000);
}

/**
 * Owner admin: paginated user list with block status. Never returns tokens.
 * `search` matches username or discord_id (case-insensitive, prefix/substring).
 */
export function getAdminUsers({ search = '', limit = 50, offset = 0 } = {}) {
  return new Promise((resolve, reject) => {
    const lim = Math.min(Math.max(parseInt(limit, 10) || 50, 1), 200);
    const off = Math.max(parseInt(offset, 10) || 0, 0);
    const term = `%${String(search || '').trim()}%`;
    const where = search ? 'WHERE username LIKE ? OR discord_id LIKE ?' : '';
    const whereParams = search ? [term, term] : [];
    db.get(`SELECT COUNT(*) AS total FROM users ${where}`, whereParams, (cErr, cRow) => {
      if (cErr) return reject(cErr);
      db.all(
        `SELECT discord_id, username, email, avatar_url, blocked, blocked_reason, blocked_at, blocked_until, created_at
         FROM users ${where}
         ORDER BY blocked DESC, username COLLATE NOCASE ASC
         LIMIT ? OFFSET ?`,
        [...whereParams, lim, off],
        (err, rows) => {
          if (err) return reject(err);
          const users = (rows || []).map((r) => ({
            discord_id: r.discord_id,
            username: r.username,
            email: r.email,
            avatar_url: r.avatar_url,
            blocked: isEffectivelyBlocked(r),
            blocked_reason: r.blocked_reason || null,
            blocked_at: r.blocked_at || null,
            blocked_until: r.blocked_until || null,
            created_at: r.created_at
          }));
          resolve({ users, total: cRow?.total || 0 });
        }
      );
    });
  });
}

/**
 * Owner admin: set/clear the blocked flag on a user.
 * Returns the number of affected rows (0 if the user does not exist).
 */
export function setUserBlocked(discordId, blocked, reason = null, until = null) {
  return new Promise((resolve, reject) => {
    const isBlocked = blocked ? 1 : 0;
    const at = isBlocked ? Math.floor(Date.now() / 1000) : null;
    const cleanReason = isBlocked ? (reason ? String(reason).slice(0, 500) : null) : null;
    const cleanUntil = isBlocked ? sanitizeBlockUntil(until) : null;
    db.run(
      'UPDATE users SET blocked = ?, blocked_reason = ?, blocked_at = ?, blocked_until = ?, updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?',
      [isBlocked, cleanReason, at, cleanUntil, discordId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Coerce a temp-ban expiry into a future unix-seconds timestamp, or null for a
 * permanent block. Past/invalid values collapse to null (= permanent).
 */
function sanitizeBlockUntil(until) {
  const n = parseInt(until, 10);
  if (!Number.isFinite(n) || n <= 0) return null;
  const now = Math.floor(Date.now() / 1000);
  return n > now ? n : null;
}

/**
 * Owner admin: guild list with block status + bot presence.
 * `search` matches guild_name or id.
 */
export function getAdminGuilds({ search = '', limit = 100, offset = 0 } = {}) {
  return new Promise((resolve, reject) => {
    const lim = Math.min(Math.max(parseInt(limit, 10) || 100, 1), 500);
    const off = Math.max(parseInt(offset, 10) || 0, 0);
    const term = `%${String(search || '').trim()}%`;
    const where = search ? 'WHERE guild_name LIKE ? OR id LIKE ?' : '';
    const whereParams = search ? [term, term] : [];
    db.get(`SELECT COUNT(*) AS total FROM guilds ${where}`, whereParams, (cErr, cRow) => {
      if (cErr) return reject(cErr);
      db.all(
        `SELECT id, guild_name, guild_icon_url, bot_present, blocked, blocked_reason, blocked_at, blocked_until, premium_tier, premium_source, premium_until, created_at
         FROM guilds ${where}
         ORDER BY blocked DESC, guild_name COLLATE NOCASE ASC
         LIMIT ? OFFSET ?`,
        [...whereParams, lim, off],
        (err, rows) => {
          if (err) return reject(err);
          const guilds = (rows || []).map((r) => ({
            id: r.id,
            guild_name: r.guild_name,
            guild_icon_url: r.guild_icon_url,
            bot_present: !!r.bot_present,
            blocked: isEffectivelyBlocked(r),
            blocked_reason: r.blocked_reason || null,
            blocked_at: r.blocked_at || null,
            blocked_until: r.blocked_until || null,
            premium_tier: PREMIUM_TIERS.includes(r.premium_tier) ? r.premium_tier : 'free',
            premium_source: r.premium_source || null,
            premium_until: r.premium_until || null,
            premium_effective: effectiveTier(r),
            created_at: r.created_at
          }));
          resolve({ guilds, total: cRow?.total || 0 });
        }
      );
    });
  });
}

/**
 * Owner admin: set/clear the blocked flag on a guild.
 * Returns the number of affected rows (0 if the guild does not exist).
 */
export function setGuildBlocked(guildId, blocked, reason = null, until = null) {
  return new Promise((resolve, reject) => {
    const isBlocked = blocked ? 1 : 0;
    const at = isBlocked ? Math.floor(Date.now() / 1000) : null;
    const cleanReason = isBlocked ? (reason ? String(reason).slice(0, 500) : null) : null;
    const cleanUntil = isBlocked ? sanitizeBlockUntil(until) : null;
    db.run(
      'UPDATE guilds SET blocked = ?, blocked_reason = ?, blocked_at = ?, blocked_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
      [isBlocked, cleanReason, at, cleanUntil, guildId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Admin v2: overview, audit viewer, guild inspector, system settings =====

/**
 * Per-module metadata for the overview adoption counts and the guild inspector.
 * `flag` modules have an `enabled` column on their settings table; `count`
 * modules are "active" when at least one configured row exists (optionally
 * narrowed by `where`). Keys mirror the dashboard route segments / MODULE_TIERS.
 */
const FLAG_MODULE_TABLES = [
  { key: 'autorole', table: 'guild_autorole_settings' },
  { key: 'logs', table: 'guild_log_settings' },
  { key: 'moderation', table: 'guild_moderation_settings' },
  { key: 'leveling', table: 'guild_leveling_settings' },
  { key: 'stats', table: 'guild_stats_settings' },
  { key: 'tempvoice', table: 'guild_tempvoice_settings' },
  { key: 'starboard', table: 'guild_starboard_settings' },
  { key: 'suggestions', table: 'guild_suggestion_settings' },
  { key: 'birthday', table: 'guild_birthday_settings' },
  { key: 'antiraid', table: 'guild_antiraid_settings' },
  { key: 'verification', table: 'guild_verification_settings' },
  { key: 'tickets', table: 'guild_ticket_settings' },
  { key: 'counting', table: 'guild_counting_settings' },
  { key: 'invitetracking', table: 'guild_invite_settings' },
  { key: 'economy', table: 'guild_economy_settings' }
];

const COUNT_MODULE_TABLES = [
  { key: 'reaction-roles', table: 'guild_reaction_role_messages' },
  { key: 'custom-commands', table: 'guild_custom_commands' },
  { key: 'social', table: 'guild_social_subscriptions', where: 'enabled = 1' },
  { key: 'scheduled', table: 'guild_scheduled_messages', where: 'enabled = 1' },
  { key: 'rolemenus', table: 'guild_role_menus' },
  { key: 'giveaways', table: 'guild_giveaways', where: 'ended = 0' },
  { key: 'polls', table: 'guild_polls', where: 'ended = 0' },
  { key: 'applications', table: 'guild_application_forms', where: 'enabled = 1' }
];

function dbGet(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => (err ? reject(err) : resolve(row)));
  });
}

function dbAll(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => (err ? reject(err) : resolve(rows || [])));
  });
}

/**
 * Owner admin: aggregated system metrics for the overview dashboard.
 * Premium counts are expiry-aware (an elapsed `premium_until` counts as free).
 */
export async function getAdminOverview() {
  const now = Math.floor(Date.now() / 1000);
  const activePremium = `premium_tier IS NOT NULL AND premium_tier != 'free' AND (premium_until IS NULL OR premium_until > ${now})`;

  const [userTotals, guildTotals, premium, expiring] = await Promise.all([
    dbGet('SELECT COUNT(*) AS total, SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) AS blocked FROM users'),
    dbGet('SELECT COUNT(*) AS total, SUM(CASE WHEN bot_present = 1 THEN 1 ELSE 0 END) AS present, SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) AS blocked FROM guilds'),
    dbGet(`SELECT
        SUM(CASE WHEN premium_tier = 'basic' AND (premium_until IS NULL OR premium_until > ${now}) THEN 1 ELSE 0 END) AS basic,
        SUM(CASE WHEN premium_tier = 'pro' AND (premium_until IS NULL OR premium_until > ${now}) THEN 1 ELSE 0 END) AS pro
      FROM guilds`),
    dbAll(`SELECT id, guild_name, guild_icon_url, premium_tier, premium_until
      FROM guilds
      WHERE ${activePremium} AND premium_until IS NOT NULL AND premium_until <= ${now + 7 * 86400}
      ORDER BY premium_until ASC LIMIT 20`)
  ]);

  // Module adoption — count of guilds with each module active.
  const adoption = {};
  await Promise.all([
    ...FLAG_MODULE_TABLES.map(async (m) => {
      const row = await dbGet(`SELECT COUNT(*) AS n FROM ${m.table} WHERE enabled = 1`);
      adoption[m.key] = row?.n || 0;
    }),
    ...COUNT_MODULE_TABLES.map(async (m) => {
      const w = m.where ? ` WHERE ${m.where}` : '';
      const row = await dbGet(`SELECT COUNT(DISTINCT guild_id) AS n FROM ${m.table}${w}`);
      adoption[m.key] = row?.n || 0;
    }),
    (async () => {
      const w = await dbGet('SELECT COUNT(*) AS n FROM guild_settings WHERE welcome_enabled = 1');
      adoption['welcome'] = w?.n || 0;
      const l = await dbGet('SELECT COUNT(*) AS n FROM guild_settings WHERE leave_enabled = 1');
      adoption['leave'] = l?.n || 0;
    })()
  ]);

  const recentAudit = await dbGet(`SELECT COUNT(*) AS n FROM audit_log WHERE created_at >= datetime('now', '-1 day')`);

  const totalUsers = userTotals?.total || 0;
  const totalGuilds = guildTotals?.total || 0;
  const basic = premium?.basic || 0;
  const pro = premium?.pro || 0;

  return {
    users: { total: totalUsers, blocked: userTotals?.blocked || 0 },
    guilds: {
      total: totalGuilds,
      bot_present: guildTotals?.present || 0,
      bot_absent: totalGuilds - (guildTotals?.present || 0),
      blocked: guildTotals?.blocked || 0
    },
    premium: { free: Math.max(totalGuilds - basic - pro, 0), basic, pro },
    premium_expiring: expiring.map((r) => ({
      id: r.id,
      guild_name: r.guild_name,
      guild_icon_url: r.guild_icon_url,
      premium_tier: r.premium_tier,
      premium_until: r.premium_until
    })),
    module_adoption: adoption,
    audit_last_24h: recentAudit?.n || 0
  };
}

/**
 * Owner admin: paginated, filterable global audit-log feed (newest first).
 * Joins the actor's username + guild name for display. `action` is an exact
 * match; `target` matches actor id, guild id, or guild name.
 */
export function getAuditLogEntries({ action = '', target = '', limit = 50, offset = 0 } = {}) {
  return new Promise((resolve, reject) => {
    const lim = Math.min(Math.max(parseInt(limit, 10) || 50, 1), 200);
    const off = Math.max(parseInt(offset, 10) || 0, 0);
    const clauses = [];
    const params = [];
    if (action) { clauses.push('a.action = ?'); params.push(String(action)); }
    if (target) {
      const term = `%${String(target).trim()}%`;
      clauses.push('(a.user_id LIKE ? OR a.guild_id LIKE ? OR g.guild_name LIKE ?)');
      params.push(term, term, term);
    }
    const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const base = `FROM audit_log a
      LEFT JOIN users u ON u.discord_id = a.user_id
      LEFT JOIN guilds g ON g.id = a.guild_id
      ${where}`;
    db.get(`SELECT COUNT(*) AS total ${base}`, params, (cErr, cRow) => {
      if (cErr) return reject(cErr);
      db.all(
        `SELECT a.id, a.user_id, a.guild_id, a.action, a.changes, a.created_at,
                u.username AS actor_username, g.guild_name
         ${base}
         ORDER BY a.id DESC
         LIMIT ? OFFSET ?`,
        [...params, lim, off],
        (err, rows) => {
          if (err) return reject(err);
          const entries = (rows || []).map((r) => {
            let changes = null;
            try { changes = r.changes ? JSON.parse(r.changes) : null; } catch { changes = r.changes; }
            return {
              id: r.id,
              action: r.action,
              user_id: r.user_id || null,
              actor_username: r.actor_username || null,
              guild_id: r.guild_id || null,
              guild_name: r.guild_name || null,
              changes,
              created_at: r.created_at
            };
          });
          resolve({ entries, total: cRow?.total || 0 });
        }
      );
    });
  });
}

/**
 * Distinct list of audit-log action names (for the viewer's filter dropdown).
 */
export function getAuditActions() {
  return new Promise((resolve, reject) => {
    db.all('SELECT DISTINCT action FROM audit_log ORDER BY action ASC', [], (err, rows) => {
      if (err) reject(err);
      else resolve((rows || []).map((r) => r.action));
    });
  });
}

/**
 * Owner admin: read-only snapshot of which modules a guild has active, plus its
 * premium + presence + block state. Powers the support-focused guild inspector.
 */
export async function getGuildInspect(guildId) {
  const guild = await dbGet(
    `SELECT id, guild_name, guild_icon_url, bot_present, blocked, blocked_reason, blocked_at, blocked_until,
            premium_tier, premium_source, premium_until, created_at
     FROM guilds WHERE id = ?`, [guildId]);
  if (!guild) return null;

  const modules = [];
  await Promise.all([
    ...FLAG_MODULE_TABLES.map(async (m) => {
      const row = await dbGet(`SELECT enabled FROM ${m.table} WHERE guild_id = ?`, [guildId]);
      modules.push({ key: m.key, kind: 'flag', enabled: !!(row && row.enabled), configured: !!row });
    }),
    ...COUNT_MODULE_TABLES.map(async (m) => {
      const w = m.where ? ` AND ${m.where}` : '';
      const row = await dbGet(`SELECT COUNT(*) AS n FROM ${m.table} WHERE guild_id = ?${w}`, [guildId]);
      const n = row?.n || 0;
      modules.push({ key: m.key, kind: 'count', enabled: n > 0, count: n, configured: n > 0 });
    }),
    (async () => {
      const row = await dbGet('SELECT welcome_enabled, leave_enabled FROM guild_settings WHERE guild_id = ?', [guildId]);
      modules.push({ key: 'welcome', kind: 'flag', enabled: !!(row && row.welcome_enabled), configured: !!row });
      modules.push({ key: 'leave', kind: 'flag', enabled: !!(row && row.leave_enabled), configured: !!row });
    })()
  ]);

  modules.sort((a, b) => a.key.localeCompare(b.key));

  const memberCount = await dbGet('SELECT COUNT(*) AS n FROM user_guilds WHERE guild_id = ?', [guildId]);

  return {
    id: guild.id,
    guild_name: guild.guild_name,
    guild_icon_url: guild.guild_icon_url,
    bot_present: !!guild.bot_present,
    blocked: isEffectivelyBlocked(guild),
    blocked_reason: guild.blocked_reason || null,
    blocked_until: guild.blocked_until || null,
    premium_tier: PREMIUM_TIERS.includes(guild.premium_tier) ? guild.premium_tier : 'free',
    premium_source: guild.premium_source || null,
    premium_until: guild.premium_until || null,
    premium_effective: effectiveTier(guild),
    dashboard_members: memberCount?.n || 0,
    created_at: guild.created_at,
    modules
  };
}

// ----- System settings (maintenance mode) -----

export function getSystemSetting(key) {
  return new Promise((resolve, reject) => {
    db.get('SELECT value FROM system_settings WHERE key = ?', [key], (err, row) => {
      if (err) reject(err);
      else resolve(row ? row.value : null);
    });
  });
}

export function setSystemSetting(key, value) {
  return new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
       ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP`,
      [key, value == null ? null : String(value)],
      function (err) { if (err) reject(err); else resolve(this.changes); }
    );
  });
}

/**
 * Global maintenance state. When `enabled`, non-owner dashboard writes are
 * rejected with 503 and a banner is shown across the app.
 */
export async function getMaintenanceState() {
  const raw = await getSystemSetting('maintenance');
  if (!raw) return { enabled: false, message: '' };
  try {
    const parsed = JSON.parse(raw);
    return { enabled: !!parsed.enabled, message: typeof parsed.message === 'string' ? parsed.message : '' };
  } catch {
    return { enabled: false, message: '' };
  }
}

export function setMaintenanceState({ enabled, message = '' }) {
  const payload = JSON.stringify({ enabled: !!enabled, message: String(message || '').slice(0, 500) });
  return setSystemSetting('maintenance', payload);
}

// ----- CSV export (owner-only) -----

export function getUsersForExport() {
  return dbAll(
    `SELECT discord_id, username, email, blocked, blocked_until, created_at
     FROM users ORDER BY created_at ASC`
  );
}

export function getGuildsForExport() {
  return dbAll(
    `SELECT id, guild_name, bot_present, blocked, blocked_until, premium_tier, premium_source, premium_until, created_at
     FROM guilds ORDER BY created_at ASC`
  );
}

/**
 * Replace the bot-presence state for every guild in one transaction.
 * Sets `bot_present = 1` for guilds whose id is in `presentGuildIds`,
 * and `bot_present = 0` for all other guilds.
 *
 * Guilds the bot is in but which don't exist in the `guilds` table are silently
 * ignored — those guilds appear in the dashboard only after a dashboard user
 * (who is admin/owner there) logs in and triggers the OAuth reconcile path.
 */
export function syncBotPresence(presentGuildIds) {
  const ids = Array.isArray(presentGuildIds) ? presentGuildIds : [];

  // Routed through runInTransaction so it shares the single transaction queue
  // and can't collide with concurrent channel/role syncs ("cannot start a
  // transaction within a transaction").
  return runInTransaction(() => new Promise((resolve, reject) => {
    if (ids.length === 0) {
      db.run('UPDATE guilds SET bot_present = 0', function(err) {
        if (err) return reject(err);
        resolve({ present: 0, absent: this.changes });
      });
      return;
    }

    const placeholders = ids.map(() => '?').join(',');
    db.run(
      `UPDATE guilds SET bot_present = 1 WHERE id IN (${placeholders})`,
      ids,
      function(err) {
        if (err) return reject(err);
        const presentChanges = this.changes;
        db.run(
          `UPDATE guilds SET bot_present = 0 WHERE id NOT IN (${placeholders})`,
          ids,
          function(err2) {
            if (err2) return reject(err2);
            resolve({ present: presentChanges, absent: this.changes });
          }
        );
      }
    );
  }));
}

/**
 * Delete a guild and all related data
 */
export function deleteGuild(guildId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guilds WHERE id = ?', [guildId], function(err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/**
 * Delete a user and all related data
 */
export function deleteUser(discordId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM users WHERE discord_id = ?', [discordId], function(err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/**
 * Remove user from a guild
 */
export function removeUserFromGuild(userId, guildId) {
  return new Promise((resolve, reject) => {
    db.run(
      'DELETE FROM user_guilds WHERE user_id = ? AND guild_id = ?',
      [userId, guildId],
      function(err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Remove all user_guilds rows for a user whose guild_id is NOT in keepGuildIds.
 * If keepGuildIds is empty, deletes every user_guilds row for the user.
 */
export function removeUserGuildsNotIn(userId, keepGuildIds) {
  return new Promise((resolve, reject) => {
    const ids = Array.isArray(keepGuildIds) ? keepGuildIds : [];

    if (ids.length === 0) {
      db.run(
        'DELETE FROM user_guilds WHERE user_id = ?',
        [userId],
        function(err) {
          if (err) reject(err);
          else resolve(this.changes);
        }
      );
      return;
    }

    const placeholders = ids.map(() => '?').join(', ');
    const query = `DELETE FROM user_guilds WHERE user_id = ? AND guild_id NOT IN (${placeholders})`;
    db.run(query, [userId, ...ids], function(err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/**
 * Serialize all transactions onto the single shared sqlite3 connection.
 * sqlite3 keeps one connection, and a transaction is NOT nestable — if two
 * `BEGIN IMMEDIATE` blocks interleave (e.g. the bot fires presence-sync,
 * channel-sync and role-sync concurrently on startup) the second one throws
 * "cannot start a transaction within a transaction". This promise chain makes
 * every transaction wait for the previous one to COMMIT/ROLLBACK first.
 */
let _txChain = Promise.resolve();

function _runTxNow(work) {
  return new Promise((resolve, reject) => {
    db.run('BEGIN IMMEDIATE TRANSACTION', (beginErr) => {
      if (beginErr) return reject(beginErr);
      Promise.resolve()
        .then(() => work())
        .then((result) => {
          db.run('COMMIT', (commitErr) => {
            if (commitErr) reject(commitErr);
            else resolve(result);
          });
        })
        .catch((workErr) => {
          db.run('ROLLBACK', () => reject(workErr));
        });
    });
  });
}

/**
 * Run a body of async DB work inside a single BEGIN/COMMIT.
 * On any thrown error inside `work`, ROLLBACKs and rejects with that error.
 * Transactions are queued (see `_txChain`) so they never overlap on the shared
 * connection.
 *
 * Why: serial awaits across many INSERTs are slow because each becomes its own
 * transaction with an fsync. Wrapping in one transaction gives one fsync at COMMIT.
 */
export function runInTransaction(work) {
  const result = _txChain.then(() => _runTxNow(work));
  // Keep the queue alive regardless of this transaction's outcome.
  _txChain = result.then(() => undefined, () => undefined);
  return result;
}

/**
 * Get database statistics
 */
export function getDbStats() {
  return new Promise((resolve, reject) => {
    const stats = {};
    const tables = ['guilds', 'guild_settings', 'users', 'user_guilds', 'audit_log'];
    let completed = 0;

    tables.forEach((table) => {
      db.get(`SELECT COUNT(*) as count FROM ${table}`, (err, row) => {
        if (err) {
          reject(err);
        } else {
          stats[table] = row?.count || 0;
          completed++;
          if (completed === tables.length) {
            resolve(stats);
          }
        }
      });
    });
  });
}

// ===== Module: Auto-Role =====

const AUTOROLE_DEFAULTS = {
  enabled: false,
  role_ids: [],
  apply_to_bots: false
};

function parseStringArray(raw, fallback = []) {
  if (raw == null) return fallback;
  if (Array.isArray(raw)) {
    return raw.filter((item) => typeof item === 'string');
  }
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.filter((item) => typeof item === 'string');
      }
    } catch {
      // fall through
    }
  }
  return fallback;
}

/**
 * Get auto-role settings for a guild.
 * Returns the row with `role_ids` parsed into an array, or null if no row exists.
 */
export function getAutoroleSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_autorole_settings WHERE guild_id = ?',
      [guildId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        resolve({
          guild_id: row.guild_id,
          enabled: !!row.enabled,
          role_ids: parseStringArray(row.role_ids, []),
          apply_to_bots: !!row.apply_to_bots,
          created_at: row.created_at,
          updated_at: row.updated_at
        });
      }
    );
  });
}

/**
 * Upsert auto-role settings.
 * Coerces booleans to 0/1 and JSON-stringifies the role_ids array
 * (only string items are persisted).
 */
export function upsertAutoroleSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const roleIds = parseStringArray(settings.role_ids, []);
    const enabled = settings.enabled ? 1 : 0;
    const applyToBots = settings.apply_to_bots ? 1 : 0;

    db.run(
      `INSERT INTO guild_autorole_settings (guild_id, enabled, role_ids, apply_to_bots)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
       enabled = excluded.enabled,
       role_ids = excluded.role_ids,
       apply_to_bots = excluded.apply_to_bots,
       updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, JSON.stringify(roleIds), applyToBots],
      function (err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

// ===== Module: Server-Logs =====

const LOG_DEFAULTS = {
  enabled: false,
  log_channel_id: null,
  log_joins: true,
  log_leaves: true,
  log_message_edits: false,
  log_message_deletes: false,
  log_member_bans: true,
  log_member_updates: false,
  log_member_unbans: false,
  log_channels: false,
  log_roles: false,
  log_voice: false,
  log_ignored_channel_ids: []
};

/**
 * Get log settings for a guild. Returns the row or null.
 */
export function getLogSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_log_settings WHERE guild_id = ?',
      [guildId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        resolve({
          guild_id: row.guild_id,
          enabled: !!row.enabled,
          log_channel_id: row.log_channel_id ?? null,
          log_joins: !!row.log_joins,
          log_leaves: !!row.log_leaves,
          log_message_edits: !!row.log_message_edits,
          log_message_deletes: !!row.log_message_deletes,
          log_member_bans: !!row.log_member_bans,
          log_member_updates: !!row.log_member_updates,
          log_member_unbans: !!row.log_member_unbans,
          log_channels: !!row.log_channels,
          log_roles: !!row.log_roles,
          log_voice: !!row.log_voice,
          log_ignored_channel_ids: parseStringArray(row.log_ignored_channel_ids, []),
          created_at: row.created_at,
          updated_at: row.updated_at
        });
      }
    );
  });
}

/**
 * Upsert log settings. Coerces booleans to 0/1, JSON-stringifies the
 * ignored-channels array (snowflake strings only).
 */
export function upsertLogSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const channelId = typeof settings.log_channel_id === 'string' && settings.log_channel_id.length > 0
      ? settings.log_channel_id
      : null;
    const joins = settings.log_joins ? 1 : 0;
    const leaves = settings.log_leaves ? 1 : 0;
    const edits = settings.log_message_edits ? 1 : 0;
    const deletes = settings.log_message_deletes ? 1 : 0;
    const bans = settings.log_member_bans ? 1 : 0;
    const memberUpdates = settings.log_member_updates ? 1 : 0;
    const unbans = settings.log_member_unbans ? 1 : 0;
    const channels = settings.log_channels ? 1 : 0;
    const roles = settings.log_roles ? 1 : 0;
    const voice = settings.log_voice ? 1 : 0;
    const ignored = parseStringArray(settings.log_ignored_channel_ids, [])
      .filter((id) => isSnowflake(id));

    db.run(
      `INSERT INTO guild_log_settings
        (guild_id, enabled, log_channel_id, log_joins, log_leaves,
         log_message_edits, log_message_deletes, log_member_bans,
         log_member_updates, log_member_unbans, log_channels, log_roles,
         log_voice, log_ignored_channel_ids)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
       enabled = excluded.enabled,
       log_channel_id = excluded.log_channel_id,
       log_joins = excluded.log_joins,
       log_leaves = excluded.log_leaves,
       log_message_edits = excluded.log_message_edits,
       log_message_deletes = excluded.log_message_deletes,
       log_member_bans = excluded.log_member_bans,
       log_member_updates = excluded.log_member_updates,
       log_member_unbans = excluded.log_member_unbans,
       log_channels = excluded.log_channels,
       log_roles = excluded.log_roles,
       log_voice = excluded.log_voice,
       log_ignored_channel_ids = excluded.log_ignored_channel_ids,
       updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, channelId, joins, leaves, edits, deletes, bans,
       memberUpdates, unbans, channels, roles, voice, JSON.stringify(ignored)],
      function (err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

// ===== Module: Moderation =====

const MODERATION_DEFAULTS = {
  enabled: false,
  anti_spam_enabled: false,
  max_messages_per_10s: 5,
  banned_words: [],
  banned_word_action: 'delete',
  mute_role_id: null,
  anti_invite: false,
  anti_link: false,
  filter_action: 'delete',
  anti_mention: false,
  max_mentions: 5,
  anti_caps: false,
  caps_percentage: 70,
  timeout_duration: 300,
  warn_threshold: 0,
  warn_escalation_action: 'mute',
  exempt_role_ids: [],
  ignored_channel_ids: []
};

// Per-message filter actions (banned words / invite / link / mention / caps).
export const MOD_ACTIONS = ['delete', 'warn', 'mute', 'kick', 'timeout'];
// Action taken once the warn threshold is reached.
export const MOD_ESCALATION_ACTIONS = ['mute', 'kick', 'ban', 'timeout'];
// Discord native timeouts cap at 28 days.
const TIMEOUT_MAX_SECONDS = 2419200;

/**
 * Get moderation settings for a guild. Returns row (with array columns parsed)
 * or null.
 */
export function getModerationSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_moderation_settings WHERE guild_id = ?',
      [guildId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        resolve({
          guild_id: row.guild_id,
          enabled: !!row.enabled,
          anti_spam_enabled: !!row.anti_spam_enabled,
          max_messages_per_10s: row.max_messages_per_10s ?? 5,
          banned_words: parseStringArray(row.banned_words, []),
          banned_word_action: MOD_ACTIONS.includes(row.banned_word_action)
            ? row.banned_word_action
            : 'delete',
          mute_role_id: row.mute_role_id ?? null,
          anti_invite: !!row.anti_invite,
          anti_link: !!row.anti_link,
          filter_action: MOD_ACTIONS.includes(row.filter_action) ? row.filter_action : 'delete',
          anti_mention: !!row.anti_mention,
          max_mentions: row.max_mentions ?? 5,
          anti_caps: !!row.anti_caps,
          caps_percentage: row.caps_percentage ?? 70,
          timeout_duration: row.timeout_duration ?? 300,
          warn_threshold: row.warn_threshold ?? 0,
          warn_escalation_action: MOD_ESCALATION_ACTIONS.includes(row.warn_escalation_action)
            ? row.warn_escalation_action
            : 'mute',
          exempt_role_ids: parseStringArray(row.exempt_role_ids, []),
          ignored_channel_ids: parseStringArray(row.ignored_channel_ids, []),
          created_at: row.created_at,
          updated_at: row.updated_at
        });
      }
    );
  });
}

/**
 * Upsert moderation settings.
 *  - JSON-stringifies the banned_words array (lowercased, strings only) and the
 *    exempt_role_ids / ignored_channel_ids arrays (snowflakes only).
 *  - Coerces booleans to 0/1.
 *  - Bounds-checks: max_messages_per_10s [1,100], max_mentions [1,50],
 *    caps_percentage [50,100], timeout_duration [60, 2419200], warn_threshold [0,20].
 *  - Validates action enums (fallback to safe defaults).
 */
export function upsertModerationSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const antiSpam = settings.anti_spam_enabled ? 1 : 0;

    const rate = clampInt(settings.max_messages_per_10s, 5, 1, 100);
    const words = parseStringArray(settings.banned_words, [])
      .map((w) => String(w).toLowerCase());
    const action = MOD_ACTIONS.includes(settings.banned_word_action)
      ? settings.banned_word_action
      : 'delete';
    const muteRoleId = typeof settings.mute_role_id === 'string' && settings.mute_role_id.length > 0
      ? settings.mute_role_id
      : null;

    const antiInvite = settings.anti_invite ? 1 : 0;
    const antiLink = settings.anti_link ? 1 : 0;
    const filterAction = MOD_ACTIONS.includes(settings.filter_action) ? settings.filter_action : 'delete';
    const antiMention = settings.anti_mention ? 1 : 0;
    const maxMentions = clampInt(settings.max_mentions, 5, 1, 50);
    const antiCaps = settings.anti_caps ? 1 : 0;
    const capsPct = clampInt(settings.caps_percentage, 70, 50, 100);
    const timeoutDur = clampInt(settings.timeout_duration, 300, 60, TIMEOUT_MAX_SECONDS);
    const warnThreshold = clampInt(settings.warn_threshold, 0, 0, 20);
    const escalation = MOD_ESCALATION_ACTIONS.includes(settings.warn_escalation_action)
      ? settings.warn_escalation_action
      : 'mute';
    const exemptRoles = parseStringArray(settings.exempt_role_ids, []).filter((id) => isSnowflake(id));
    const ignoredChannels = parseStringArray(settings.ignored_channel_ids, []).filter((id) => isSnowflake(id));

    db.run(
      `INSERT INTO guild_moderation_settings
        (guild_id, enabled, anti_spam_enabled, max_messages_per_10s,
         banned_words, banned_word_action, mute_role_id,
         anti_invite, anti_link, filter_action, anti_mention, max_mentions,
         anti_caps, caps_percentage, timeout_duration, warn_threshold,
         warn_escalation_action, exempt_role_ids, ignored_channel_ids)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
       enabled = excluded.enabled,
       anti_spam_enabled = excluded.anti_spam_enabled,
       max_messages_per_10s = excluded.max_messages_per_10s,
       banned_words = excluded.banned_words,
       banned_word_action = excluded.banned_word_action,
       mute_role_id = excluded.mute_role_id,
       anti_invite = excluded.anti_invite,
       anti_link = excluded.anti_link,
       filter_action = excluded.filter_action,
       anti_mention = excluded.anti_mention,
       max_mentions = excluded.max_mentions,
       anti_caps = excluded.anti_caps,
       caps_percentage = excluded.caps_percentage,
       timeout_duration = excluded.timeout_duration,
       warn_threshold = excluded.warn_threshold,
       warn_escalation_action = excluded.warn_escalation_action,
       exempt_role_ids = excluded.exempt_role_ids,
       ignored_channel_ids = excluded.ignored_channel_ids,
       updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, antiSpam, rate, JSON.stringify(words), action, muteRoleId,
       antiInvite, antiLink, filterAction, antiMention, maxMentions,
       antiCaps, capsPct, timeoutDur, warnThreshold, escalation,
       JSON.stringify(exemptRoles), JSON.stringify(ignoredChannels)],
      function (err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

/**
 * Record a moderation warning for a user and evaluate the escalation threshold.
 * Runs in a transaction so concurrent violations can't double-count.
 *
 * Returns { count, total, threshold, threshold_reached, escalation_action,
 *           timeout_duration }. When the threshold is reached the running
 * `count` resets to 0 (lifetime `total` keeps climbing) and threshold_reached
 * is true so the bot applies the escalation action.
 * If warn_threshold <= 0 the escalation is disabled (threshold_reached false).
 */
export function addModerationWarning(guildId, userId, now) {
  const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);
  return runInTransaction(() => new Promise((resolve, reject) => {
    db.get(
      'SELECT warn_threshold, warn_escalation_action, timeout_duration FROM guild_moderation_settings WHERE guild_id = ?',
      [guildId],
      (sErr, sRow) => {
        if (sErr) return reject(sErr);
        const threshold = clampInt(sRow?.warn_threshold, 0, 0, 20);
        const escalation = MOD_ESCALATION_ACTIONS.includes(sRow?.warn_escalation_action)
          ? sRow.warn_escalation_action
          : 'mute';
        const timeoutDur = clampInt(sRow?.timeout_duration, 300, 60, TIMEOUT_MAX_SECONDS);

        db.get(
          'SELECT count, total FROM guild_moderation_warnings WHERE guild_id = ? AND user_id = ?',
          [guildId, userId],
          (uErr, uRow) => {
            if (uErr) return reject(uErr);
            const prevCount = uRow?.count || 0;
            const prevTotal = uRow?.total || 0;
            const newCount = prevCount + 1;
            const newTotal = prevTotal + 1;
            const reached = threshold > 0 && newCount >= threshold;
            const storedCount = reached ? 0 : newCount;

            db.run(
              `INSERT INTO guild_moderation_warnings (guild_id, user_id, count, total, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET
                 count = excluded.count,
                 total = excluded.total,
                 updated_at = excluded.updated_at`,
              [guildId, userId, storedCount, newTotal, ts],
              (wErr) => {
                if (wErr) return reject(wErr);
                resolve({
                  count: reached ? threshold : newCount,
                  total: newTotal,
                  threshold,
                  threshold_reached: reached,
                  escalation_action: escalation,
                  timeout_duration: timeoutDur
                });
              }
            );
          }
        );
      }
    );
  }));
}

// ===== Guild Resources: Channels / Roles =====

const CHANNEL_TYPES = new Set([
  'text', 'voice', 'category', 'announcement', 'forum', 'stage', 'thread'
]);

function clampInt32(value, fallback = 0) {
  let n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  n = Math.trunc(n);
  if (n > 2147483647) n = 2147483647;
  if (n < -2147483648) n = -2147483648;
  return n;
}

function clampColor(value) {
  let n = Number(value);
  if (!Number.isFinite(n)) n = 0;
  n = Math.trunc(n);
  if (n < 0) n = 0;
  if (n > 0xFFFFFF) n = 0xFFFFFF;
  return n;
}

/**
 * Get all synced channels for a guild.
 * Sorted so categories come first, then channels grouped under their parent
 * category, then by position/name. Defaults to [] if nothing has been synced.
 */
export function getGuildChannels(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT id, guild_id, name, type, parent_id, position, updated_at
       FROM guild_channels
       WHERE guild_id = ?
       ORDER BY (parent_id IS NULL) DESC, parent_id ASC, position ASC, name ASC`,
      [guildId],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

/**
 * Get all synced roles for a guild, sorted by Discord position DESC (top role first).
 *
 * Options:
 *   - includeDefault (default false): include the @everyone role.
 *   - includeManaged (default true): include integration-managed roles
 *     (Twitch sub roles, bot-integration roles, …).
 */
export function getGuildRoles(guildId, { includeDefault = false, includeManaged = true } = {}) {
  return new Promise((resolve, reject) => {
    const clauses = ['guild_id = ?'];
    const params = [guildId];
    if (!includeDefault) clauses.push('is_default = 0');
    if (!includeManaged) clauses.push('managed = 0');

    const sql = `SELECT id, guild_id, name, color, position, managed, is_default, updated_at
       FROM guild_roles
       WHERE ${clauses.join(' AND ')}
       ORDER BY position DESC, name ASC`;

    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

/**
 * Replace the full channel list for a guild in one transaction.
 * Validates type against the allowed enum (fallback to 'text'), clamps position
 * to a safe 32-bit int. Items without a string id or name are dropped by callers.
 *
 * `guildMeta` (optional, `{ name, icon_url }`) lets the caller seed the guilds
 * table on the fly — required when the bot syncs a guild no dashboard user has
 * logged into yet (otherwise the FK on guild_channels.guild_id fails).
 */
export function replaceGuildChannels(guildId, channels, guildMeta = null) {
  const list = Array.isArray(channels) ? channels : [];
  return runInTransaction(() => new Promise((resolve, reject) => {
    const ensureGuild = (cb) => {
      if (!guildMeta) return cb();
      db.run(
        `INSERT INTO guilds (id, guild_name, guild_icon_url)
         VALUES (?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           guild_name = COALESCE(NULLIF(excluded.guild_name, ''), guild_name),
           guild_icon_url = COALESCE(NULLIF(excluded.guild_icon_url, ''), guild_icon_url),
           updated_at = CURRENT_TIMESTAMP`,
        [guildId, guildMeta.name || guildId, guildMeta.icon_url || null],
        (err) => err ? reject(err) : cb()
      );
    };

    ensureGuild(() => db.run(
      'DELETE FROM guild_channels WHERE guild_id = ?',
      [guildId],
      function (delErr) {
        if (delErr) return reject(delErr);

        if (list.length === 0) return resolve(0);

        const stmt = db.prepare(
          `INSERT INTO guild_channels
             (id, guild_id, name, type, parent_id, position, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(id) DO UPDATE SET
             guild_id = excluded.guild_id,
             name = excluded.name,
             type = excluded.type,
             parent_id = excluded.parent_id,
             position = excluded.position,
             updated_at = CURRENT_TIMESTAMP`
        );

        let pending = list.length;
        let inserted = 0;
        let failed = false;

        for (const item of list) {
          if (!item || typeof item.id !== 'string' || typeof item.name !== 'string') {
            pending--;
            if (pending === 0 && !failed) {
              stmt.finalize((finErr) => finErr ? reject(finErr) : resolve(inserted));
            }
            continue;
          }
          const type = CHANNEL_TYPES.has(item.type) ? item.type : 'text';
          const parentId = item.parent_id ? String(item.parent_id) : null;
          const position = clampInt32(item.position, 0);

          stmt.run(
            [item.id, guildId, item.name, type, parentId, position],
            (runErr) => {
              if (failed) return;
              if (runErr) {
                failed = true;
                stmt.finalize(() => reject(runErr));
                return;
              }
              inserted++;
              pending--;
              if (pending === 0) {
                stmt.finalize((finErr) => finErr ? reject(finErr) : resolve(inserted));
              }
            }
          );
        }
      }
    ));
  }));
}

/**
 * Replace the full role list for a guild in one transaction.
 * Validates color (integer, clamped to [0, 0xFFFFFF]), clamps position to safe
 * 32-bit int. Coerces managed/is_default to 0/1.
 *
 * `guildMeta` (optional, `{ name, icon_url }`) seeds the guilds row up-front,
 * same reason as in replaceGuildChannels — keeps the FK constraint happy when
 * the bot syncs before any dashboard user has logged in.
 */
export function replaceGuildRoles(guildId, roles, guildMeta = null) {
  const list = Array.isArray(roles) ? roles : [];
  return runInTransaction(() => new Promise((resolve, reject) => {
    const ensureGuild = (cb) => {
      if (!guildMeta) return cb();
      db.run(
        `INSERT INTO guilds (id, guild_name, guild_icon_url)
         VALUES (?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           guild_name = COALESCE(NULLIF(excluded.guild_name, ''), guild_name),
           guild_icon_url = COALESCE(NULLIF(excluded.guild_icon_url, ''), guild_icon_url),
           updated_at = CURRENT_TIMESTAMP`,
        [guildId, guildMeta.name || guildId, guildMeta.icon_url || null],
        (err) => err ? reject(err) : cb()
      );
    };

    ensureGuild(() => db.run(
      'DELETE FROM guild_roles WHERE guild_id = ?',
      [guildId],
      function (delErr) {
        if (delErr) return reject(delErr);

        if (list.length === 0) return resolve(0);

        const stmt = db.prepare(
          `INSERT INTO guild_roles
             (id, guild_id, name, color, position, managed, is_default, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(id) DO UPDATE SET
             guild_id = excluded.guild_id,
             name = excluded.name,
             color = excluded.color,
             position = excluded.position,
             managed = excluded.managed,
             is_default = excluded.is_default,
             updated_at = CURRENT_TIMESTAMP`
        );

        let pending = list.length;
        let inserted = 0;
        let failed = false;

        for (const item of list) {
          if (!item || typeof item.id !== 'string' || typeof item.name !== 'string') {
            pending--;
            if (pending === 0 && !failed) {
              stmt.finalize((finErr) => finErr ? reject(finErr) : resolve(inserted));
            }
            continue;
          }
          const color = clampColor(item.color);
          const position = clampInt32(item.position, 0);
          const managed = item.managed ? 1 : 0;
          const isDefault = item.is_default ? 1 : 0;

          stmt.run(
            [item.id, guildId, item.name, color, position, managed, isDefault],
            (runErr) => {
              if (failed) return;
              if (runErr) {
                failed = true;
                stmt.finalize(() => reject(runErr));
                return;
              }
              inserted++;
              pending--;
              if (pending === 0) {
                stmt.finalize((finErr) => finErr ? reject(finErr) : resolve(inserted));
              }
            }
          );
        }
      }
    ));
  }));
}

// ===== Module: Reaction Roles =====

const SNOWFLAKE_REGEX = /^\d{15,25}$/;

function isSnowflake(value) {
  return typeof value === 'string' && SNOWFLAKE_REGEX.test(value);
}

function shapeReactionRoleRow(row, mappings) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    channel_id: row.channel_id,
    message_id: row.message_id,
    name: row.name ?? null,
    exclusive: !!row.exclusive,
    created_at: row.created_at ?? null,
    updated_at: row.updated_at ?? null,
    mappings: Array.isArray(mappings) ? mappings : []
  };
}

/**
 * Internal: read a single reaction-role message + its mappings.
 * Returns null if no message row exists.
 */
function readReactionRoleMessage(guildId, rrId) {
  return new Promise((resolve, reject) => {
    db.get(
      `SELECT * FROM guild_reaction_role_messages
       WHERE guild_id = ? AND id = ?`,
      [guildId, rrId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        db.all(
          `SELECT emoji, role_id FROM guild_reaction_role_mappings
           WHERE rr_message_id = ?
           ORDER BY id ASC`,
          [rrId],
          (mErr, mRows) => {
            if (mErr) return reject(mErr);
            resolve(shapeReactionRoleRow(row, mRows || []));
          }
        );
      }
    );
  });
}

/**
 * Get all reaction-role messages for a guild with their mappings joined inline.
 */
export function getReactionRoleMessages(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM guild_reaction_role_messages
       WHERE guild_id = ?
       ORDER BY created_at ASC`,
      [guildId],
      (err, msgs) => {
        if (err) return reject(err);
        if (!msgs || msgs.length === 0) return resolve([]);

        const ids = msgs.map((m) => m.id);
        const placeholders = ids.map(() => '?').join(',');
        db.all(
          `SELECT rr_message_id, emoji, role_id
           FROM guild_reaction_role_mappings
           WHERE rr_message_id IN (${placeholders})
           ORDER BY id ASC`,
          ids,
          (mErr, mRows) => {
            if (mErr) return reject(mErr);
            const byMsg = new Map();
            for (const r of mRows || []) {
              if (!byMsg.has(r.rr_message_id)) byMsg.set(r.rr_message_id, []);
              byMsg.get(r.rr_message_id).push({ emoji: r.emoji, role_id: r.role_id });
            }
            resolve(msgs.map((m) => shapeReactionRoleRow(m, byMsg.get(m.id) || [])));
          }
        );
      }
    );
  });
}

function sanitizeReactionRoleMappings(mappings) {
  if (!Array.isArray(mappings)) return [];
  const out = [];
  const seen = new Set();
  for (const m of mappings) {
    if (!m || typeof m !== 'object') continue;
    const emoji = typeof m.emoji === 'string' ? m.emoji.trim() : '';
    const roleId = typeof m.role_id === 'string' ? m.role_id : '';
    if (!emoji) continue;
    if (!isSnowflake(roleId)) continue;
    if (seen.has(emoji)) continue;
    seen.add(emoji);
    out.push({ emoji, role_id: roleId });
  }
  return out;
}

/**
 * Create a new reaction-role message + its mappings in one transaction.
 * Generates a server-side UUID for the row id.
 */
export function createReactionRoleMessage(guildId, payload) {
  const channelId = payload?.channel_id;
  const messageId = payload?.message_id;
  if (!isSnowflake(channelId)) {
    return Promise.reject(new Error('Invalid channel_id'));
  }
  if (!isSnowflake(messageId)) {
    return Promise.reject(new Error('Invalid message_id'));
  }
  const mappings = sanitizeReactionRoleMappings(payload?.mappings);
  if (mappings.length === 0) {
    return Promise.reject(new Error('At least one mapping required'));
  }
  const name = typeof payload?.name === 'string' ? payload.name.slice(0, 100) : null;
  const exclusive = payload?.exclusive ? 1 : 0;
  const id = randomUUID();

  return runInTransaction(() => new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO guild_reaction_role_messages
         (id, guild_id, channel_id, message_id, name, exclusive)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [id, guildId, channelId, messageId, name, exclusive],
      (insErr) => {
        if (insErr) return reject(insErr);

        const stmt = db.prepare(
          `INSERT INTO guild_reaction_role_mappings
             (rr_message_id, emoji, role_id)
           VALUES (?, ?, ?)`
        );

        let pending = mappings.length;
        let failed = false;
        for (const m of mappings) {
          stmt.run([id, m.emoji, m.role_id], (runErr) => {
            if (failed) return;
            if (runErr) {
              failed = true;
              stmt.finalize(() => reject(runErr));
              return;
            }
            pending--;
            if (pending === 0) {
              stmt.finalize((finErr) => {
                if (finErr) return reject(finErr);
                resolve(id);
              });
            }
          });
        }
      }
    );
  })).then(() => readReactionRoleMessage(guildId, id));
}

/**
 * Update an existing reaction-role message; replaces mappings wholesale
 * (delete + bulk insert) inside one transaction.
 */
export function updateReactionRoleMessage(guildId, rrId, payload) {
  const channelId = payload?.channel_id;
  const messageId = payload?.message_id;
  if (!isSnowflake(channelId)) {
    return Promise.reject(new Error('Invalid channel_id'));
  }
  if (!isSnowflake(messageId)) {
    return Promise.reject(new Error('Invalid message_id'));
  }
  const mappings = sanitizeReactionRoleMappings(payload?.mappings);
  if (mappings.length === 0) {
    return Promise.reject(new Error('At least one mapping required'));
  }
  const name = typeof payload?.name === 'string' ? payload.name.slice(0, 100) : null;
  const exclusive = payload?.exclusive ? 1 : 0;

  return runInTransaction(() => new Promise((resolve, reject) => {
    db.run(
      `UPDATE guild_reaction_role_messages
         SET channel_id = ?, message_id = ?, name = ?, exclusive = ?,
             updated_at = CURRENT_TIMESTAMP
       WHERE guild_id = ? AND id = ?`,
      [channelId, messageId, name, exclusive, guildId, rrId],
      function (updErr) {
        if (updErr) return reject(updErr);
        if (this.changes === 0) {
          return reject(Object.assign(new Error('Reaction role message not found'), { code: 'NOT_FOUND' }));
        }

        db.run(
          `DELETE FROM guild_reaction_role_mappings WHERE rr_message_id = ?`,
          [rrId],
          (delErr) => {
            if (delErr) return reject(delErr);

            const stmt = db.prepare(
              `INSERT INTO guild_reaction_role_mappings
                 (rr_message_id, emoji, role_id)
               VALUES (?, ?, ?)`
            );
            let pending = mappings.length;
            let failed = false;
            for (const m of mappings) {
              stmt.run([rrId, m.emoji, m.role_id], (runErr) => {
                if (failed) return;
                if (runErr) {
                  failed = true;
                  stmt.finalize(() => reject(runErr));
                  return;
                }
                pending--;
                if (pending === 0) {
                  stmt.finalize((finErr) => finErr ? reject(finErr) : resolve(rrId));
                }
              });
            }
          }
        );
      }
    );
  })).then(() => readReactionRoleMessage(guildId, rrId));
}

/**
 * Delete a reaction-role message (mappings cascade via FK ON DELETE CASCADE).
 */
export function deleteReactionRoleMessage(guildId, rrId) {
  return new Promise((resolve, reject) => {
    db.run(
      `DELETE FROM guild_reaction_role_messages WHERE guild_id = ? AND id = ?`,
      [guildId, rrId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Look up a reaction-role message by its Discord message snowflake.
 * Used by the bot when a reaction add/remove event fires.
 */
export function findReactionRoleByMessage(guildId, messageId) {
  return new Promise((resolve, reject) => {
    db.get(
      `SELECT * FROM guild_reaction_role_messages
       WHERE guild_id = ? AND message_id = ?`,
      [guildId, messageId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        db.all(
          `SELECT emoji, role_id FROM guild_reaction_role_mappings
           WHERE rr_message_id = ?
           ORDER BY id ASC`,
          [row.id],
          (mErr, mRows) => {
            if (mErr) return reject(mErr);
            resolve(shapeReactionRoleRow(row, mRows || []));
          }
        );
      }
    );
  });
}

// ===== Module: Leveling / XP =====

const LEVELING_DEFAULTS = {
  enabled: false,
  xp_per_message_min: 10,
  xp_per_message_max: 25,
  cooldown_seconds: 60,
  level_up_channel_id: null,
  level_up_message: '🎉 GG {user}, you just reached level **{level}**!',
  ignored_channel_ids: [],
  stack_role_rewards: true
};

/**
 * XP required to REACH the given level, cumulatively from level 0.
 * Standard MEE6-style curve: sum_{i=0..n-1} of 5*i^2 + 50*i + 100.
 */
export function totalXpForLevel(n) {
  let total = 0;
  const target = Math.max(0, Math.floor(Number(n) || 0));
  for (let i = 0; i < target; i++) total += 5 * i * i + 50 * i + 100;
  return total;
}

/**
 * Derive the highest reachable level for a given total XP.
 */
export function levelFromXp(xp) {
  const v = Math.max(0, Math.floor(Number(xp) || 0));
  let lvl = 0;
  while (totalXpForLevel(lvl + 1) <= v) lvl++;
  return lvl;
}

/**
 * XP needed to reach the level above `currentLevel`.
 */
export function xpForNextLevel(currentLevel) {
  return totalXpForLevel(Math.max(0, Math.floor(Number(currentLevel) || 0)) + 1);
}

function clampInt(value, fallback, lo, hi) {
  let n = Number(value);
  if (!Number.isFinite(n)) n = fallback;
  n = Math.trunc(n);
  if (n < lo) n = lo;
  if (n > hi) n = hi;
  return n;
}

function shapeLevelingSettingsRow(row) {
  if (!row) return null;
  return {
    guild_id: row.guild_id,
    enabled: !!row.enabled,
    xp_per_message_min: row.xp_per_message_min ?? LEVELING_DEFAULTS.xp_per_message_min,
    xp_per_message_max: row.xp_per_message_max ?? LEVELING_DEFAULTS.xp_per_message_max,
    cooldown_seconds: row.cooldown_seconds ?? LEVELING_DEFAULTS.cooldown_seconds,
    level_up_channel_id: row.level_up_channel_id ?? null,
    level_up_message: row.level_up_message ?? LEVELING_DEFAULTS.level_up_message,
    ignored_channel_ids: parseStringArray(row.ignored_channel_ids, []),
    stack_role_rewards: !!row.stack_role_rewards,
    updated_at: row.updated_at ?? null
  };
}

/**
 * Get leveling settings for a guild. Returns the parsed row or null if no row exists.
 */
export function getLevelingSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_leveling_settings WHERE guild_id = ?',
      [guildId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        resolve(shapeLevelingSettingsRow(row));
      }
    );
  });
}

/**
 * Upsert leveling settings. Coerces / clamps:
 *   - xp_per_message_min/max: [1, 500] integers; max raised to min if smaller.
 *   - cooldown_seconds: [0, 600] integer.
 *   - ignored_channel_ids: snowflake-shaped strings only.
 *   - booleans → 0/1.
 *   - level_up_message: truncated to 1000 chars.
 */
export function upsertLevelingSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings?.enabled ? 1 : 0;
    let xpMin = clampInt(settings?.xp_per_message_min, LEVELING_DEFAULTS.xp_per_message_min, 1, 500);
    let xpMax = clampInt(settings?.xp_per_message_max, LEVELING_DEFAULTS.xp_per_message_max, 1, 500);
    if (xpMax < xpMin) xpMax = xpMin;
    const cooldown = clampInt(settings?.cooldown_seconds, LEVELING_DEFAULTS.cooldown_seconds, 0, 600);

    const channelId = isSnowflake(settings?.level_up_channel_id) ? settings.level_up_channel_id : null;
    const message = truncate(
      settings?.level_up_message || LEVELING_DEFAULTS.level_up_message,
      1000
    );
    const ignored = parseStringArray(settings?.ignored_channel_ids, [])
      .filter((id) => isSnowflake(id));
    const stack = settings?.stack_role_rewards ? 1 : 0;

    db.run(
      `INSERT INTO guild_leveling_settings
         (guild_id, enabled, xp_per_message_min, xp_per_message_max, cooldown_seconds,
          level_up_channel_id, level_up_message, ignored_channel_ids, stack_role_rewards)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         xp_per_message_min = excluded.xp_per_message_min,
         xp_per_message_max = excluded.xp_per_message_max,
         cooldown_seconds = excluded.cooldown_seconds,
         level_up_channel_id = excluded.level_up_channel_id,
         level_up_message = excluded.level_up_message,
         ignored_channel_ids = excluded.ignored_channel_ids,
         stack_role_rewards = excluded.stack_role_rewards,
         updated_at = CURRENT_TIMESTAMP`,
      [
        guildId, enabled, xpMin, xpMax, cooldown,
        channelId, message, JSON.stringify(ignored), stack
      ],
      function (err) {
        if (err) reject(err);
        else resolve(this.lastID);
      }
    );
  });
}

/**
 * Get role rewards for a guild, sorted by level ASC.
 */
export function getLevelingRewards(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT id, level, role_id FROM guild_leveling_rewards
       WHERE guild_id = ?
       ORDER BY level ASC, id ASC`,
      [guildId],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

/**
 * Replace all role rewards for a guild in one transaction.
 * Drops entries with non-snowflake role_ids or non-positive levels.
 */
export function setLevelingRewards(guildId, rewards) {
  const list = Array.isArray(rewards) ? rewards : [];
  const sane = [];
  const seen = new Set();
  for (const r of list) {
    if (!r || typeof r !== 'object') continue;
    const level = clampInt(r.level, 0, 0, 1000);
    const roleId = typeof r.role_id === 'string' ? r.role_id : '';
    if (level < 1) continue;
    if (!isSnowflake(roleId)) continue;
    const key = `${level}:${roleId}`;
    if (seen.has(key)) continue;
    seen.add(key);
    sane.push({ level, role_id: roleId });
  }

  return runInTransaction(() => new Promise((resolve, reject) => {
    db.run(
      'DELETE FROM guild_leveling_rewards WHERE guild_id = ?',
      [guildId],
      (delErr) => {
        if (delErr) return reject(delErr);
        if (sane.length === 0) return resolve(0);

        const stmt = db.prepare(
          `INSERT INTO guild_leveling_rewards (guild_id, level, role_id)
           VALUES (?, ?, ?)`
        );
        let pending = sane.length;
        let inserted = 0;
        let failed = false;
        for (const r of sane) {
          stmt.run([guildId, r.level, r.role_id], (runErr) => {
            if (failed) return;
            if (runErr) {
              failed = true;
              stmt.finalize(() => reject(runErr));
              return;
            }
            inserted++;
            pending--;
            if (pending === 0) {
              stmt.finalize((finErr) => finErr ? reject(finErr) : resolve(inserted));
            }
          });
        }
      }
    );
  }));
}

/**
 * Get a single user's XP row. Returns a zeroed shape if no row exists.
 */
export function getLevelingUser(guildId, userId) {
  return new Promise((resolve, reject) => {
    db.get(
      `SELECT guild_id, user_id, xp, level, messages, last_xp_at
       FROM guild_leveling_users
       WHERE guild_id = ? AND user_id = ?`,
      [guildId, userId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) {
          return resolve({
            guild_id: guildId,
            user_id: userId,
            xp: 0,
            level: 0,
            messages: 0,
            last_xp_at: 0
          });
        }
        resolve(row);
      }
    );
  });
}

function randomInt(min, max) {
  const lo = Math.ceil(min);
  const hi = Math.floor(max);
  if (hi <= lo) return lo;
  return lo + Math.floor(Math.random() * (hi - lo + 1));
}

/**
 * Award XP to a user. Core of the leveling module.
 *  - Reads settings + user row inside a single transaction so concurrent
 *    messages from the same user can't double-grant during cooldown.
 *  - Returns { granted: false } if cooldown hasn't elapsed.
 *  - Returns the full payload the bot needs to announce a level-up + apply
 *    role rewards.
 */
export function grantXp(guildId, userId, now) {
  const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);

  return runInTransaction(() => new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_leveling_settings WHERE guild_id = ?',
      [guildId],
      (sErr, sRow) => {
        if (sErr) return reject(sErr);

        const settings = sRow ? shapeLevelingSettingsRow(sRow) : { ...LEVELING_DEFAULTS, guild_id: guildId };

        if (!settings.enabled) {
          return resolve({ granted: false, reason: 'disabled' });
        }

        db.get(
          `SELECT xp, level, messages, last_xp_at
           FROM guild_leveling_users
           WHERE guild_id = ? AND user_id = ?`,
          [guildId, userId],
          (uErr, uRow) => {
            if (uErr) return reject(uErr);

            const current = uRow || { xp: 0, level: 0, messages: 0, last_xp_at: 0 };
            const elapsed = ts - (current.last_xp_at || 0);
            if (elapsed < settings.cooldown_seconds) {
              return resolve({ granted: false, reason: 'cooldown' });
            }

            const granted = randomInt(settings.xp_per_message_min, settings.xp_per_message_max);
            const newXp = (current.xp || 0) + granted;
            const oldLevel = current.level || 0;
            const newLevel = levelFromXp(newXp);
            const newMessages = (current.messages || 0) + 1;

            db.run(
              `INSERT INTO guild_leveling_users
                 (guild_id, user_id, xp, level, messages, last_xp_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET
                 xp = excluded.xp,
                 level = excluded.level,
                 messages = excluded.messages,
                 last_xp_at = excluded.last_xp_at`,
              [guildId, userId, newXp, newLevel, newMessages, ts],
              (upErr) => {
                if (upErr) return reject(upErr);

                const leveledUp = newLevel > oldLevel;

                const finish = (roleRewards) => {
                  resolve({
                    granted: true,
                    xp_gained: granted,
                    total_xp: newXp,
                    old_level: oldLevel,
                    new_level: newLevel,
                    messages: newMessages,
                    leveled_up: leveledUp,
                    role_rewards: roleRewards,
                    level_up_channel_id: settings.level_up_channel_id,
                    level_up_message_template: settings.level_up_message,
                    ignored_channel_ids: settings.ignored_channel_ids
                  });
                };

                if (!leveledUp) return finish([]);

                db.all(
                  `SELECT level, role_id FROM guild_leveling_rewards
                   WHERE guild_id = ? AND level > ? AND level <= ?
                   ORDER BY level ASC, id ASC`,
                  [guildId, oldLevel, newLevel],
                  (rErr, rRows) => {
                    if (rErr) return reject(rErr);
                    const list = rRows || [];
                    if (!settings.stack_role_rewards) {
                      // Keep only the highest-level reward role; if multiple roles
                      // share that top level we keep the first one.
                      if (list.length === 0) return finish([]);
                      let topLevel = -1;
                      for (const r of list) if (r.level > topLevel) topLevel = r.level;
                      const top = list.find((r) => r.level === topLevel);
                      return finish(top ? [top.role_id] : []);
                    }
                    finish(list.map((r) => r.role_id));
                  }
                );
              }
            );
          }
        );
      }
    );
  }));
}

/**
 * Top N users by XP for the guild. Rank is 1-based across the absolute
 * leaderboard, so callers can paginate without re-ranking.
 */
export function getLeaderboard(guildId, limit = 25, offset = 0) {
  const lim = clampInt(limit, 25, 1, 100);
  const off = clampInt(offset, 0, 0, 1000000);
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT user_id, xp, level, messages
       FROM guild_leveling_users
       WHERE guild_id = ?
       ORDER BY xp DESC, user_id ASC
       LIMIT ? OFFSET ?`,
      [guildId, lim, off],
      (err, rows) => {
        if (err) return reject(err);
        const out = (rows || []).map((r, i) => ({
          user_id: r.user_id,
          xp: r.xp || 0,
          level: r.level || 0,
          messages: r.messages || 0,
          rank: off + i + 1
        }));
        resolve(out);
      }
    );
  });
}

/**
 * Count of users with any XP > 0 (used for leaderboard totals).
 */
export function countLeaderboardUsers(guildId) {
  return new Promise((resolve, reject) => {
    db.get(
      `SELECT COUNT(*) AS n FROM guild_leveling_users
       WHERE guild_id = ? AND xp > 0`,
      [guildId],
      (err, row) => {
        if (err) reject(err);
        else resolve(row?.n || 0);
      }
    );
  });
}

// ===== Module: Custom Commands =====

const CC_MATCH_TYPES = ['exact', 'contains', 'starts_with'];
const CC_TRIGGER_MAX = 50;
const CC_RESPONSE_MAX = 2000;

function shapeCustomCommandRow(row) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    trigger: row.trigger,
    response: row.response,
    match_type: CC_MATCH_TYPES.includes(row.match_type) ? row.match_type : 'exact',
    enabled: !!row.enabled,
    created_at: row.created_at ?? null,
    updated_at: row.updated_at ?? null
  };
}

/**
 * Get all custom commands for a guild, sorted oldest-first.
 */
export function getCustomCommands(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM guild_custom_commands
       WHERE guild_id = ?
       ORDER BY created_at ASC, id ASC`,
      [guildId],
      (err, rows) => {
        if (err) return reject(err);
        resolve((rows || []).map(shapeCustomCommandRow));
      }
    );
  });
}

/**
 * Create a custom command. Lowercases the trigger, truncates to caps,
 * validates the match_type enum. Throws on UNIQUE violation; route catches it.
 */
export function createCustomCommand(guildId, payload) {
  return new Promise((resolve, reject) => {
    const triggerRaw = typeof payload?.trigger === 'string' ? payload.trigger.trim().toLowerCase() : '';
    if (triggerRaw.length === 0) {
      return reject(Object.assign(new Error('Trigger required'), { code: 'VALIDATION' }));
    }
    const trigger = triggerRaw.slice(0, CC_TRIGGER_MAX);
    const responseRaw = typeof payload?.response === 'string' ? payload.response : '';
    if (responseRaw.length === 0) {
      return reject(Object.assign(new Error('Response required'), { code: 'VALIDATION' }));
    }
    const response = responseRaw.slice(0, CC_RESPONSE_MAX);
    const matchType = CC_MATCH_TYPES.includes(payload?.match_type) ? payload.match_type : 'exact';
    const enabled = payload?.enabled === false ? 0 : 1;

    db.run(
      `INSERT INTO guild_custom_commands (guild_id, trigger, response, match_type, enabled)
       VALUES (?, ?, ?, ?, ?)`,
      [guildId, trigger, response, matchType, enabled],
      function (err) {
        if (err) return reject(err);
        const id = this.lastID;
        db.get(
          `SELECT * FROM guild_custom_commands WHERE id = ?`,
          [id],
          (gErr, row) => {
            if (gErr) reject(gErr);
            else resolve(shapeCustomCommandRow(row));
          }
        );
      }
    );
  });
}

/**
 * Patch a custom command. Only known keys are applied; everything is sanitized.
 */
export function updateCustomCommand(guildId, cmdId, patch) {
  return new Promise((resolve, reject) => {
    db.get(
      `SELECT * FROM guild_custom_commands WHERE guild_id = ? AND id = ?`,
      [guildId, cmdId],
      (gErr, row) => {
        if (gErr) return reject(gErr);
        if (!row) {
          return reject(Object.assign(new Error('Custom command not found'), { code: 'NOT_FOUND' }));
        }

        let trigger = row.trigger;
        if (patch?.trigger !== undefined) {
          const t = typeof patch.trigger === 'string' ? patch.trigger.trim().toLowerCase() : '';
          if (t.length === 0) {
            return reject(Object.assign(new Error('Trigger required'), { code: 'VALIDATION' }));
          }
          trigger = t.slice(0, CC_TRIGGER_MAX);
        }

        let response = row.response;
        if (patch?.response !== undefined) {
          const r = typeof patch.response === 'string' ? patch.response : '';
          if (r.length === 0) {
            return reject(Object.assign(new Error('Response required'), { code: 'VALIDATION' }));
          }
          response = r.slice(0, CC_RESPONSE_MAX);
        }

        let matchType = row.match_type;
        if (patch?.match_type !== undefined) {
          matchType = CC_MATCH_TYPES.includes(patch.match_type) ? patch.match_type : matchType;
        }

        let enabled = row.enabled ? 1 : 0;
        if (patch?.enabled !== undefined) {
          enabled = patch.enabled ? 1 : 0;
        }

        db.run(
          `UPDATE guild_custom_commands
             SET trigger = ?, response = ?, match_type = ?, enabled = ?,
                 updated_at = CURRENT_TIMESTAMP
           WHERE guild_id = ? AND id = ?`,
          [trigger, response, matchType, enabled, guildId, cmdId],
          function (upErr) {
            if (upErr) return reject(upErr);
            db.get(
              `SELECT * FROM guild_custom_commands WHERE id = ?`,
              [cmdId],
              (g2Err, updated) => {
                if (g2Err) reject(g2Err);
                else resolve(shapeCustomCommandRow(updated));
              }
            );
          }
        );
      }
    );
  });
}

/**
 * Delete a custom command. Returns the number of deleted rows.
 */
export function deleteCustomCommand(guildId, cmdId) {
  return new Promise((resolve, reject) => {
    db.run(
      `DELETE FROM guild_custom_commands WHERE guild_id = ? AND id = ?`,
      [guildId, cmdId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Command Manager (built-in command catalog + per-guild config) =====

// Single source of truth for the bot's built-in commands. `key` MUST match the
// command's qualified name in the cogs so the bot's disabled-set lines up.
export const BUILTIN_COMMANDS = [
  { key: 'welcome_test', name: 'welcome_test', type: 'prefix', module: 'welcome', usage: '{p}welcome_test', description: 'Send a test welcome message (admin).' },
  { key: 'birthday', name: 'birthday', type: 'prefix', module: 'birthday', usage: '{p}birthday DD.MM[.YYYY]', description: 'Save your birthday.' },
  { key: 'suggest', name: 'suggest', type: 'prefix', module: 'suggestions', usage: '{p}suggest <text>', description: 'Submit a suggestion.' },
  { key: 'verifypanel', name: 'verifypanel', type: 'prefix', module: 'verification', usage: '{p}verifypanel', description: 'Post the verification panel (admin).' },
  { key: 'ticketpanel', name: 'ticketpanel', type: 'prefix', module: 'tickets', usage: '{p}ticketpanel', description: 'Post the ticket panel (admin).' },
  { key: 'claim', name: 'claim', type: 'prefix', module: 'tickets', usage: '{p}claim', description: 'Claim the current ticket (staff).' },
  { key: 'ticketadd', name: 'ticketadd', type: 'prefix', module: 'tickets', usage: '{p}ticketadd @user', description: 'Add a user to the current ticket (staff).' },
  { key: 'ticketremove', name: 'ticketremove', type: 'prefix', module: 'tickets', usage: '{p}ticketremove @user', description: 'Remove a user from the current ticket (staff).' },
  { key: 'ticketclose', name: 'ticketclose', type: 'prefix', module: 'tickets', usage: '{p}ticketclose', description: 'Close the current ticket (staff/owner).' },
  { key: 'gstart', name: 'gstart', type: 'prefix', module: 'giveaways', usage: '{p}gstart <duration> <winners> <prize>', description: 'Start a giveaway (admin).' },
  { key: 'greroll', name: 'greroll', type: 'prefix', module: 'giveaways', usage: '{p}greroll <giveaway_id>', description: 'Reroll a giveaway winner (admin).' },
  { key: 'poll', name: 'poll', type: 'prefix', module: 'polls', usage: '{p}poll <question> | <A> | <B> | …', description: 'Start a button poll.' },
  { key: 'applypanel', name: 'applypanel', type: 'prefix', module: 'applications', usage: '{p}applypanel', description: 'Post the application panel (admin).' },
  { key: 'balance', name: 'balance', type: 'prefix', module: 'economy', usage: '{p}balance [member]', description: 'Show a balance.' },
  { key: 'daily', name: 'daily', type: 'prefix', module: 'economy', usage: '{p}daily', description: 'Claim the daily reward.' },
  { key: 'work', name: 'work', type: 'prefix', module: 'economy', usage: '{p}work', description: 'Work for currency.' },
  { key: 'pay', name: 'pay', type: 'prefix', module: 'economy', usage: '{p}pay @user <amount>', description: 'Transfer currency to a member.' },
  { key: 'rich', name: 'rich', type: 'prefix', module: 'economy', usage: '{p}rich', description: 'Show the balance leaderboard.' },
  { key: 'shop', name: 'shop', type: 'prefix', module: 'economy', usage: '{p}shop', description: 'List shop items.' },
  { key: 'buy', name: 'buy', type: 'prefix', module: 'economy', usage: '{p}buy <item>', description: 'Buy a shop item.' },
  { key: 'ttt', name: 'ttt', type: 'prefix', module: 'games', usage: '{p}ttt @opponent', description: 'Start a Tic-Tac-Toe match.' },
  { key: 'rps', name: 'rps', type: 'prefix', module: 'games', usage: '{p}rps [@opponent]', description: 'Play Rock-Paper-Scissors.' },
  { key: 'trivia', name: 'trivia', type: 'prefix', module: 'games', usage: '{p}trivia', description: 'Start a trivia question.' },
  { key: 'connect4', name: 'connect4', type: 'prefix', module: 'games', usage: '{p}connect4 @opponent', description: 'Start a Connect Four match.' },
  { key: 'hangman', name: 'hangman', type: 'prefix', module: 'games', usage: '{p}hangman', description: 'Start a Hangman game.' },
  { key: 'poker', name: 'poker', type: 'prefix', module: 'games', usage: '{p}poker', description: 'Open a Texas Hold’em table.' },
  { key: 'ping', name: 'ping', type: 'slash', module: 'utility', usage: '/ping', description: "Check the bot's latency." },
  { key: 'userinfo', name: 'userinfo', type: 'slash', module: 'utility', usage: '/userinfo [member]', description: 'Show information about a member.' },
  { key: 'serverinfo', name: 'serverinfo', type: 'slash', module: 'utility', usage: '/serverinfo', description: 'Show information about this server.' },
  { key: 'avatar', name: 'avatar', type: 'slash', module: 'utility', usage: '/avatar [member]', description: "Show a member's avatar." }
];

const BUILTIN_COMMAND_KEYS = new Set(BUILTIN_COMMANDS.map((c) => c.key));
const DEFAULT_COMMAND_PREFIX = '!';

export function sanitizeCommandPrefix(value) {
  if (typeof value !== 'string') return DEFAULT_COMMAND_PREFIX;
  const trimmed = value.trim();
  // 1–5 chars, no whitespace inside. Falls back to '!' on anything invalid.
  if (trimmed.length < 1 || trimmed.length > 5 || /\s/.test(trimmed)) return DEFAULT_COMMAND_PREFIX;
  return trimmed;
}

export function getCommandPrefix(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT command_prefix FROM guilds WHERE id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      resolve(row && row.command_prefix ? row.command_prefix : DEFAULT_COMMAND_PREFIX);
    });
  });
}

export function setCommandPrefix(guildId, prefix) {
  return new Promise((resolve, reject) => {
    const clean = sanitizeCommandPrefix(prefix);
    db.run('UPDATE guilds SET command_prefix = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', [clean, guildId], function (err) {
      if (err) reject(err);
      else resolve(clean);
    });
  });
}

/** Map of { command_key: boolean } for every command the guild has toggled. */
export function getCommandSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT command_key, enabled FROM guild_command_settings WHERE guild_id = ?', [guildId], (err, rows) => {
      if (err) return reject(err);
      const out = {};
      for (const r of rows || []) out[r.command_key] = !!r.enabled;
      resolve(out);
    });
  });
}

export function setCommandEnabled(guildId, key, enabled) {
  return new Promise((resolve, reject) => {
    if (!BUILTIN_COMMAND_KEYS.has(key)) {
      const e = new Error('Unknown command');
      e.code = 'NOT_FOUND';
      return reject(e);
    }
    db.run(
      `INSERT INTO guild_command_settings (guild_id, command_key, enabled)
       VALUES (?, ?, ?)
       ON CONFLICT(guild_id, command_key) DO UPDATE SET enabled = excluded.enabled`,
      [guildId, key, enabled ? 1 : 0],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot: { prefix, disabled: [keys] } in one shot. */
export async function getCommandConfigForBot(guildId) {
  const prefix = await getCommandPrefix(guildId);
  const settings = await getCommandSettings(guildId);
  const disabled = Object.keys(settings).filter((k) => settings[k] === false);
  return { prefix, disabled };
}

// ===== Module: Social Notifications =====

export const SOCIAL_PLATFORMS = ['youtube', 'twitch', 'kick', 'tiktok', 'instagram'];
const SOCIAL_ACCOUNT_MAX = 100;
const SOCIAL_MESSAGE_MAX = 1000;
// Platforms whose account identifiers are case-insensitive and canonically
// lowercase — safe to lowercase for de-duplication. YouTube channel IDs (UC…)
// and TikTok/Instagram handles are kept as entered (just '@'/whitespace stripped).
const SOCIAL_LOWERCASE_PLATFORMS = new Set(['twitch', 'kick']);

export const SOCIAL_DEFAULTS = {
  platform: 'youtube',
  account: '',
  channel_id: null,
  notify_live: true,
  notify_upload: true,
  mention_role_id: null,
  message_template: '',
  use_embed: false,
  embed: { ...DEFAULT_EMBED },
  enabled: true
};

/**
 * Normalize a user-entered account handle: trim, strip a leading '@', and
 * lowercase for case-insensitive platforms (Twitch/Kick). Returns '' for junk.
 */
function normalizeSocialAccount(platform, account) {
  if (typeof account !== 'string') return '';
  let a = account.trim();
  if (a.startsWith('@')) a = a.slice(1);
  a = a.trim();
  if (SOCIAL_LOWERCASE_PLATFORMS.has(platform)) a = a.toLowerCase();
  return a.slice(0, SOCIAL_ACCOUNT_MAX);
}

function shapeSocialRow(row) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    platform: SOCIAL_PLATFORMS.includes(row.platform) ? row.platform : 'youtube',
    account: row.account,
    account_id: row.account_id ?? null,
    display_name: row.display_name ?? null,
    channel_id: row.channel_id,
    notify_live: !!row.notify_live,
    notify_upload: !!row.notify_upload,
    mention_role_id: row.mention_role_id ?? null,
    message_template: row.message_template ?? '',
    use_embed: !!row.use_embed,
    embed: parseEmbedColumn(row.embed),
    enabled: !!row.enabled,
    last_video_id: row.last_video_id ?? null,
    last_live: !!row.last_live,
    last_checked_at: row.last_checked_at ?? 0,
    created_at: row.created_at ?? null,
    updated_at: row.updated_at ?? null
  };
}

/**
 * Get all social subscriptions for a guild (newest first), with embed parsed
 * and booleans coerced.
 */
export function getSocialSubscriptions(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM guild_social_subscriptions
       WHERE guild_id = ?
       ORDER BY created_at ASC, id ASC`,
      [guildId],
      (err, rows) => {
        if (err) return reject(err);
        resolve((rows || []).map(shapeSocialRow));
      }
    );
  });
}

/**
 * Get every ENABLED subscription across all guilds — the bot's social-notify
 * poller reads this once per cycle. Includes the bot-maintained polling state
 * (last_video_id / last_live) so the bot can detect transitions.
 */
export function getAllEnabledSocialSubscriptions() {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM guild_social_subscriptions
       WHERE enabled = 1
         AND guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1)
         AND ${tierFilterSql('pro')}
       ORDER BY platform ASC, id ASC`,
      [],
      (err, rows) => {
        if (err) return reject(err);
        resolve((rows || []).map(shapeSocialRow));
      }
    );
  });
}

/**
 * Validate + coerce a create/update payload into the column values.
 * Throws an Error with code 'VALIDATION' on bad input.
 */
function buildSocialValues(payload, base) {
  const pick = (key) => (payload[key] !== undefined ? payload[key] : base[key]);

  const platform = pick('platform');
  if (!SOCIAL_PLATFORMS.includes(platform)) {
    throw Object.assign(new Error('platform must be one of: ' + SOCIAL_PLATFORMS.join(', ')), { code: 'VALIDATION' });
  }

  const account = normalizeSocialAccount(platform, pick('account'));
  if (account.length === 0) {
    throw Object.assign(new Error('account required'), { code: 'VALIDATION' });
  }

  const channelId = pick('channel_id');
  if (!isSnowflake(channelId)) {
    throw Object.assign(new Error('channel_id must be a Discord snowflake'), { code: 'VALIDATION' });
  }

  const mentionRoleId = isSnowflake(pick('mention_role_id')) ? pick('mention_role_id') : null;
  const messageTemplate = truncate(pick('message_template') || '', SOCIAL_MESSAGE_MAX);
  const embed = sanitizeEmbed(pick('embed'));

  return {
    platform,
    account,
    channel_id: channelId,
    notify_live: pick('notify_live') ? 1 : 0,
    notify_upload: pick('notify_upload') ? 1 : 0,
    mention_role_id: mentionRoleId,
    message_template: messageTemplate,
    use_embed: pick('use_embed') ? 1 : 0,
    embed: JSON.stringify(embed),
    enabled: pick('enabled') ? 1 : 0
  };
}

/**
 * Create a social subscription. Generates a server-side UUID. Throws on a
 * UNIQUE(guild_id, platform, account) violation (route maps it to 409).
 */
export function createSocialSubscription(guildId, payload) {
  return new Promise((resolve, reject) => {
    let v;
    try {
      v = buildSocialValues(payload || {}, SOCIAL_DEFAULTS);
    } catch (err) {
      return reject(err);
    }
    const id = randomUUID();

    db.run(
      `INSERT INTO guild_social_subscriptions
         (id, guild_id, platform, account, channel_id, notify_live, notify_upload,
          mention_role_id, message_template, use_embed, embed, enabled)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        id, guildId, v.platform, v.account, v.channel_id, v.notify_live, v.notify_upload,
        v.mention_role_id, v.message_template, v.use_embed, v.embed, v.enabled
      ],
      function (err) {
        if (err) return reject(err);
        db.get(
          `SELECT * FROM guild_social_subscriptions WHERE id = ?`,
          [id],
          (gErr, row) => {
            if (gErr) reject(gErr);
            else resolve(shapeSocialRow(row));
          }
        );
      }
    );
  });
}

/**
 * Update a social subscription. Changing platform/account resets the
 * bot-maintained polling state (account_id / last_video_id / last_live) so a
 * re-pointed subscription doesn't carry stale dedup state into the new target.
 * NOT_FOUND code if the row doesn't exist; UNIQUE violation bubbles to the route.
 */
export function updateSocialSubscription(guildId, subId, patch) {
  return new Promise((resolve, reject) => {
    db.get(
      `SELECT * FROM guild_social_subscriptions WHERE guild_id = ? AND id = ?`,
      [guildId, subId],
      (gErr, row) => {
        if (gErr) return reject(gErr);
        if (!row) {
          return reject(Object.assign(new Error('Subscription not found'), { code: 'NOT_FOUND' }));
        }

        const base = shapeSocialRow(row);
        let v;
        try {
          v = buildSocialValues(patch || {}, base);
        } catch (err) {
          return reject(err);
        }

        // Reset polling state if the target moved.
        const retarget = v.platform !== base.platform || v.account !== base.account;
        const resetClause = retarget
          ? ', account_id = NULL, display_name = NULL, last_video_id = NULL, last_live = 0, last_checked_at = 0'
          : '';

        db.run(
          `UPDATE guild_social_subscriptions
             SET platform = ?, account = ?, channel_id = ?, notify_live = ?,
                 notify_upload = ?, mention_role_id = ?, message_template = ?,
                 use_embed = ?, embed = ?, enabled = ?${resetClause},
                 updated_at = CURRENT_TIMESTAMP
           WHERE guild_id = ? AND id = ?`,
          [
            v.platform, v.account, v.channel_id, v.notify_live, v.notify_upload,
            v.mention_role_id, v.message_template, v.use_embed, v.embed, v.enabled,
            guildId, subId
          ],
          function (upErr) {
            if (upErr) return reject(upErr);
            db.get(
              `SELECT * FROM guild_social_subscriptions WHERE id = ?`,
              [subId],
              (g2Err, updated) => {
                if (g2Err) reject(g2Err);
                else resolve(shapeSocialRow(updated));
              }
            );
          }
        );
      }
    );
  });
}

/**
 * Delete a social subscription. Returns the number of deleted rows.
 */
export function deleteSocialSubscription(guildId, subId) {
  return new Promise((resolve, reject) => {
    db.run(
      `DELETE FROM guild_social_subscriptions WHERE guild_id = ? AND id = ?`,
      [guildId, subId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Bot-only: persist the polling state for a subscription after a check.
 * Only the keys present in `state` are written (account_id, display_name,
 * last_video_id, last_live); last_checked_at is always stamped.
 */
export function updateSocialSubscriptionState(subId, state, now) {
  return new Promise((resolve, reject) => {
    const s = state || {};
    const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);

    const fields = ['last_checked_at = ?'];
    const values = [ts];

    if (s.account_id !== undefined) {
      fields.push('account_id = ?');
      values.push(typeof s.account_id === 'string' ? s.account_id : null);
    }
    if (s.display_name !== undefined) {
      fields.push('display_name = ?');
      values.push(typeof s.display_name === 'string' ? s.display_name.slice(0, 200) : null);
    }
    if (s.last_video_id !== undefined) {
      fields.push('last_video_id = ?');
      values.push(typeof s.last_video_id === 'string' ? s.last_video_id : null);
    }
    if (s.last_live !== undefined) {
      fields.push('last_live = ?');
      values.push(s.last_live ? 1 : 0);
    }

    values.push(subId);

    db.run(
      `UPDATE guild_social_subscriptions SET ${fields.join(', ')} WHERE id = ?`,
      values,
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Module: Statistics =====

// Counter types the bot knows how to compute. `members` = total member_count,
// `humans`/`bots` split by the bot flag, `online`/`offline` need the privileged
// presence intent, `boosters` = premium_subscription_count, `channels`/`roles`
// = guild collection sizes.
export const STATS_COUNTER_TYPES = ['members', 'humans', 'bots', 'online', 'offline', 'boosters', 'channels', 'roles'];
const STATS_CHANNEL_KINDS = ['voice', 'text'];
const STATS_TEMPLATE_MAX = 100;
const STATS_INTERVAL_MIN = 5;     // Discord limits channel renames to ~2 / 10 min.
const STATS_INTERVAL_MAX = 1440;  // once a day
const STATS_SNAPSHOT_RETENTION_DAYS = 90;

const STATS_CATEGORY_NAME_DEFAULT = '📊 Statistics';
const STATS_CATEGORY_NAME_MAX = 100;

export const STATS_DEFAULTS = {
  enabled: false,
  update_interval: 10,
  category_id: null,
  auto_category: false,
  category_name: STATS_CATEGORY_NAME_DEFAULT,
  counters: []
};

function clampStatsInterval(value) {
  let n = Number(value);
  if (!Number.isFinite(n)) n = STATS_DEFAULTS.update_interval;
  n = Math.trunc(n);
  if (n < STATS_INTERVAL_MIN) n = STATS_INTERVAL_MIN;
  if (n > STATS_INTERVAL_MAX) n = STATS_INTERVAL_MAX;
  return n;
}

function shapeStatsCounterRow(row) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    type: STATS_COUNTER_TYPES.includes(row.type) ? row.type : 'members',
    channel_id: row.channel_id ?? null,
    channel_kind: STATS_CHANNEL_KINDS.includes(row.channel_kind) ? row.channel_kind : 'voice',
    name_template: row.name_template ?? '',
    auto_create: !!row.auto_create,
    position: row.position ?? 0,
    enabled: !!row.enabled,
    created_at: row.created_at ?? null,
    updated_at: row.updated_at ?? null
  };
}

/**
 * Validate + coerce a counter create/update payload into column values.
 * Throws an Error with code 'VALIDATION' on bad input.
 */
function buildStatsCounterValues(payload, base) {
  const pick = (key) => (payload[key] !== undefined ? payload[key] : base[key]);

  const type = pick('type');
  if (!STATS_COUNTER_TYPES.includes(type)) {
    throw Object.assign(new Error('type must be one of: ' + STATS_COUNTER_TYPES.join(', ')), { code: 'VALIDATION' });
  }

  const channelKind = STATS_CHANNEL_KINDS.includes(pick('channel_kind')) ? pick('channel_kind') : 'voice';
  const autoCreate = pick('auto_create') ? 1 : 0;
  const rawChannel = pick('channel_id');
  const channelId = isSnowflake(rawChannel) ? rawChannel : null;

  // A counter must either point at an existing channel or be auto-created.
  if (!autoCreate && !channelId) {
    throw Object.assign(new Error('channel_id required when auto_create is off'), { code: 'VALIDATION' });
  }

  let position = Number(pick('position'));
  if (!Number.isFinite(position)) position = 0;
  position = Math.trunc(position);

  return {
    type,
    channel_id: channelId,
    channel_kind: channelKind,
    name_template: truncate(pick('name_template') || '', STATS_TEMPLATE_MAX),
    auto_create: autoCreate,
    position,
    enabled: pick('enabled') ? 1 : 0
  };
}

/**
 * Get the stats module settings for a guild. Returns defaults (never null) so
 * the route can always respond with a usable shape.
 */
export function getStatsSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_stats_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({
        enabled: false,
        update_interval: STATS_DEFAULTS.update_interval,
        category_id: null,
        auto_category: false,
        category_name: STATS_CATEGORY_NAME_DEFAULT
      });
      resolve({
        enabled: !!row.enabled,
        update_interval: clampStatsInterval(row.update_interval),
        category_id: row.category_id ?? null,
        auto_category: !!row.auto_category,
        category_name: row.category_name ?? STATS_CATEGORY_NAME_DEFAULT
      });
    });
  });
}

/**
 * Upsert the stats module settings (enabled + update_interval + target
 * category). Booleans → 0/1, interval clamped to [5, 1440] minutes. `category_id`
 * is kept only if it's a snowflake, `category_name` truncated.
 */
export function upsertStatsSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const interval = clampStatsInterval(settings.update_interval);
    const categoryId = isSnowflake(settings.category_id) ? settings.category_id : null;
    const autoCategory = settings.auto_category ? 1 : 0;
    const categoryName = truncate(settings.category_name || STATS_CATEGORY_NAME_DEFAULT, STATS_CATEGORY_NAME_MAX);
    db.run(
      `INSERT INTO guild_stats_settings (guild_id, enabled, update_interval, category_id, auto_category, category_name)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         update_interval = excluded.update_interval,
         category_id = excluded.category_id,
         auto_category = excluded.auto_category,
         category_name = excluded.category_name,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, interval, categoryId, autoCategory, categoryName],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Bot-only: store the category_id the bot auto-created for a guild's stats
 * channels, so future cycles reuse it instead of creating another category.
 */
export function setStatsCategory(guildId, categoryId) {
  return new Promise((resolve, reject) => {
    const cid = isSnowflake(categoryId) ? categoryId : null;
    db.run(
      `UPDATE guild_stats_settings SET category_id = ?, updated_at = CURRENT_TIMESTAMP
       WHERE guild_id = ?`,
      [cid, guildId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Get all stats counters for a guild (ordered by position).
 */
export function getStatsCounters(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT * FROM guild_stats_counters
       WHERE guild_id = ?
       ORDER BY position ASC, created_at ASC`,
      [guildId],
      (err, rows) => {
        if (err) return reject(err);
        resolve((rows || []).map(shapeStatsCounterRow));
      }
    );
  });
}

/**
 * Create a stats counter. Generates a server-side UUID.
 */
export function createStatsCounter(guildId, payload) {
  return new Promise((resolve, reject) => {
    let v;
    try {
      v = buildStatsCounterValues(payload || {}, { ...STATS_DEFAULTS, type: 'members', channel_kind: 'voice', auto_create: false, enabled: true, position: 0, name_template: '', channel_id: null });
    } catch (err) {
      return reject(err);
    }
    const id = randomUUID();
    db.run(
      `INSERT INTO guild_stats_counters
         (id, guild_id, type, channel_id, channel_kind, name_template, auto_create, position, enabled)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, guildId, v.type, v.channel_id, v.channel_kind, v.name_template, v.auto_create, v.position, v.enabled],
      function (err) {
        if (err) return reject(err);
        db.get('SELECT * FROM guild_stats_counters WHERE id = ?', [id], (gErr, row) => {
          if (gErr) reject(gErr);
          else resolve(shapeStatsCounterRow(row));
        });
      }
    );
  });
}

/**
 * Update a stats counter. NOT_FOUND code if the row doesn't exist. Changing the
 * channel target or kind clears any previously stored/auto-created channel_id
 * unless a new one is supplied.
 */
export function updateStatsCounter(guildId, counterId, patch) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_stats_counters WHERE guild_id = ? AND id = ?',
      [guildId, counterId],
      (gErr, row) => {
        if (gErr) return reject(gErr);
        if (!row) {
          return reject(Object.assign(new Error('Counter not found'), { code: 'NOT_FOUND' }));
        }
        const base = shapeStatsCounterRow(row);
        let v;
        try {
          v = buildStatsCounterValues(patch || {}, base);
        } catch (err) {
          return reject(err);
        }
        db.run(
          `UPDATE guild_stats_counters
             SET type = ?, channel_id = ?, channel_kind = ?, name_template = ?,
                 auto_create = ?, position = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
           WHERE guild_id = ? AND id = ?`,
          [v.type, v.channel_id, v.channel_kind, v.name_template, v.auto_create, v.position, v.enabled, guildId, counterId],
          function (upErr) {
            if (upErr) return reject(upErr);
            db.get('SELECT * FROM guild_stats_counters WHERE id = ?', [counterId], (g2Err, updated) => {
              if (g2Err) reject(g2Err);
              else resolve(shapeStatsCounterRow(updated));
            });
          }
        );
      }
    );
  });
}

/**
 * Delete a stats counter. Returns the number of deleted rows.
 */
export function deleteStatsCounter(guildId, counterId) {
  return new Promise((resolve, reject) => {
    db.run(
      'DELETE FROM guild_stats_counters WHERE guild_id = ? AND id = ?',
      [guildId, counterId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Bot-only: store the channel_id the bot auto-created for a counter, so the next
 * cycle renames it in place instead of creating another channel.
 */
export function setStatsCounterChannel(guildId, counterId, channelId) {
  return new Promise((resolve, reject) => {
    const cid = isSnowflake(channelId) ? channelId : null;
    db.run(
      `UPDATE guild_stats_counters SET channel_id = ?, updated_at = CURRENT_TIMESTAMP
       WHERE guild_id = ? AND id = ?`,
      [cid, guildId, counterId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/**
 * Bot-only: every guild with the stats module enabled, each with its update
 * interval and its enabled counters. Read once per poll cycle by the stats cog.
 */
export function getAllEnabledStatsConfigs() {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT guild_id, update_interval, category_id, auto_category, category_name FROM guild_stats_settings WHERE enabled = 1 AND guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1) AND ${tierFilterSql('pro')}`,
      [],
      (sErr, settingsRows) => {
        if (sErr) return reject(sErr);
        const settings = settingsRows || [];
        if (settings.length === 0) return resolve([]);
        db.all(
          `SELECT c.* FROM guild_stats_counters c
           JOIN guild_stats_settings s ON c.guild_id = s.guild_id
           WHERE s.enabled = 1 AND c.enabled = 1
           ORDER BY c.guild_id ASC, c.position ASC`,
          [],
          (cErr, counterRows) => {
            if (cErr) return reject(cErr);
            const byGuild = new Map();
            for (const row of (counterRows || [])) {
              if (!byGuild.has(row.guild_id)) byGuild.set(row.guild_id, []);
              byGuild.get(row.guild_id).push(shapeStatsCounterRow(row));
            }
            resolve(settings.map((s) => ({
              guild_id: s.guild_id,
              update_interval: clampStatsInterval(s.update_interval),
              category_id: s.category_id ?? null,
              auto_category: !!s.auto_category,
              category_name: s.category_name ?? STATS_CATEGORY_NAME_DEFAULT,
              counters: byGuild.get(s.guild_id) || []
            })));
          }
        );
      }
    );
  });
}

function sanitizeCount(value) {
  let n = Number(value);
  if (!Number.isFinite(n)) n = 0;
  n = Math.trunc(n);
  return n < 0 ? 0 : n;
}

/**
 * Bot-only: insert a stats snapshot and prune rows older than the retention
 * window for that guild. Wrapped in a single transaction.
 */
export function insertStatsSnapshot(guildId, counts, now) {
  const c = counts || {};
  const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);
  const cutoff = ts - STATS_SNAPSHOT_RETENTION_DAYS * 86400;
  return runInTransaction(() => new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO guild_stats_snapshots (guild_id, ts, members, humans, bots, online, offline, boosters)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        guildId, ts,
        sanitizeCount(c.members), sanitizeCount(c.humans), sanitizeCount(c.bots),
        sanitizeCount(c.online), sanitizeCount(c.offline), sanitizeCount(c.boosters)
      ],
      function (insErr) {
        if (insErr) return reject(insErr);
        db.run(
          'DELETE FROM guild_stats_snapshots WHERE guild_id = ? AND ts < ?',
          [guildId, cutoff],
          function (delErr) {
            if (delErr) reject(delErr);
            else resolve({ inserted: true });
          }
        );
      }
    );
  }));
}

/**
 * Get snapshots for a guild since `sinceTs` (unix seconds), oldest first — for
 * the dashboard history graphs.
 */
export function getStatsSnapshots(guildId, sinceTs) {
  return new Promise((resolve, reject) => {
    const since = Number.isFinite(sinceTs) ? Math.floor(sinceTs) : 0;
    db.all(
      `SELECT ts, members, humans, bots, online, offline, boosters
       FROM guild_stats_snapshots
       WHERE guild_id = ? AND ts >= ?
       ORDER BY ts ASC`,
      [guildId, since],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

// ===== Module: Temp-Voice (Join-to-Create) =====

function clampRange(value, min, max, fallback) {
  let n = Number(value);
  if (!Number.isFinite(n)) n = fallback;
  n = Math.trunc(n);
  if (n < min) n = min;
  if (n > max) n = max;
  return n;
}

export const TEMPVOICE_DEFAULTS = {
  enabled: false,
  hub_channel_id: null,
  category_id: null,
  name_template: '🔊 {user}',
  user_limit: 0
};

export function getTempVoiceSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_tempvoice_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...TEMPVOICE_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        hub_channel_id: row.hub_channel_id ?? null,
        category_id: row.category_id ?? null,
        name_template: row.name_template ?? TEMPVOICE_DEFAULTS.name_template,
        user_limit: clampRange(row.user_limit, 0, 99, 0)
      });
    });
  });
}

export function upsertTempVoiceSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const hub = isSnowflake(settings.hub_channel_id) ? settings.hub_channel_id : null;
    const category = isSnowflake(settings.category_id) ? settings.category_id : null;
    const nameTemplate = truncate(settings.name_template || TEMPVOICE_DEFAULTS.name_template, 100);
    const userLimit = clampRange(settings.user_limit, 0, 99, 0);
    db.run(
      `INSERT INTO guild_tempvoice_settings (guild_id, enabled, hub_channel_id, category_id, name_template, user_limit)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         hub_channel_id = excluded.hub_channel_id,
         category_id = excluded.category_id,
         name_template = excluded.name_template,
         user_limit = excluded.user_limit,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, hub, category, nameTemplate, userLimit],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot-only: track a freshly-created temp voice channel. */
export function addTempVoiceChannel(guildId, channelId, ownerId) {
  return new Promise((resolve, reject) => {
    db.run(
      `INSERT INTO guild_tempvoice_channels (channel_id, guild_id, owner_id)
       VALUES (?, ?, ?)
       ON CONFLICT(channel_id) DO UPDATE SET owner_id = excluded.owner_id`,
      [channelId, guildId, ownerId ?? null],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot-only: untrack a temp voice channel (after it's deleted). */
export function removeTempVoiceChannel(channelId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_tempvoice_channels WHERE channel_id = ?', [channelId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Bot-only: all tracked temp voice channels (for empty-cleanup on startup). */
export function getAllTempVoiceChannels() {
  return new Promise((resolve, reject) => {
    db.all('SELECT channel_id, guild_id, owner_id FROM guild_tempvoice_channels WHERE guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1)', [], (err, rows) => {
      if (err) reject(err);
      else resolve(rows || []);
    });
  });
}

// ===== Module: Starboard =====

export const STARBOARD_DEFAULTS = {
  enabled: false,
  star_channel_id: null,
  emoji: '⭐',
  threshold: 3,
  self_star: false
};

export function getStarboardSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_starboard_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...STARBOARD_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        star_channel_id: row.star_channel_id ?? null,
        emoji: row.emoji || '⭐',
        threshold: clampRange(row.threshold, 1, 50, 3),
        self_star: !!row.self_star
      });
    });
  });
}

export function upsertStarboardSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const channel = isSnowflake(settings.star_channel_id) ? settings.star_channel_id : null;
    const emoji = truncate(settings.emoji || '⭐', 64);
    const threshold = clampRange(settings.threshold, 1, 50, 3);
    const selfStar = settings.self_star ? 1 : 0;
    db.run(
      `INSERT INTO guild_starboard_settings (guild_id, enabled, star_channel_id, emoji, threshold, self_star)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         star_channel_id = excluded.star_channel_id,
         emoji = excluded.emoji,
         threshold = excluded.threshold,
         self_star = excluded.self_star,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, channel, emoji, threshold, selfStar],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot-only: read the starboard entry for a source message (or null). */
export function getStarboardEntry(guildId, messageId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_starboard_entries WHERE guild_id = ? AND message_id = ?',
      [guildId, messageId],
      (err, row) => {
        if (err) return reject(err);
        if (!row) return resolve(null);
        resolve({
          guild_id: row.guild_id,
          message_id: row.message_id,
          channel_id: row.channel_id ?? null,
          star_message_id: row.star_message_id ?? null,
          count: row.count ?? 0
        });
      }
    );
  });
}

/** Bot-only: upsert the starboard entry (count + posted star message id). */
export function upsertStarboardEntry(guildId, messageId, data) {
  return new Promise((resolve, reject) => {
    const d = data || {};
    const channelId = isSnowflake(d.channel_id) ? d.channel_id : null;
    const starMessageId = isSnowflake(d.star_message_id) ? d.star_message_id : null;
    const count = clampRange(d.count, 0, 100000, 0);
    db.run(
      `INSERT INTO guild_starboard_entries (guild_id, message_id, channel_id, star_message_id, count)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(guild_id, message_id) DO UPDATE SET
         channel_id = excluded.channel_id,
         star_message_id = COALESCE(excluded.star_message_id, guild_starboard_entries.star_message_id),
         count = excluded.count,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, messageId, channelId, starMessageId, count],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot-only: delete a starboard entry (e.g. when it drops below threshold). */
export function deleteStarboardEntry(guildId, messageId) {
  return new Promise((resolve, reject) => {
    db.run(
      'DELETE FROM guild_starboard_entries WHERE guild_id = ? AND message_id = ?',
      [guildId, messageId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Module: Suggestions =====

export const SUGGESTION_DEFAULTS = {
  enabled: false,
  suggest_channel_id: null,
  upvote_emoji: '👍',
  downvote_emoji: '👎'
};

export function getSuggestionSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_suggestion_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...SUGGESTION_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        suggest_channel_id: row.suggest_channel_id ?? null,
        upvote_emoji: row.upvote_emoji || '👍',
        downvote_emoji: row.downvote_emoji || '👎'
      });
    });
  });
}

export function upsertSuggestionSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const channel = isSnowflake(settings.suggest_channel_id) ? settings.suggest_channel_id : null;
    const up = truncate(settings.upvote_emoji || '👍', 64);
    const down = truncate(settings.downvote_emoji || '👎', 64);
    db.run(
      `INSERT INTO guild_suggestion_settings (guild_id, enabled, suggest_channel_id, upvote_emoji, downvote_emoji)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         suggest_channel_id = excluded.suggest_channel_id,
         upvote_emoji = excluded.upvote_emoji,
         downvote_emoji = excluded.downvote_emoji,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, channel, up, down],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Module: Birthday =====

export const BIRTHDAY_DEFAULTS = {
  enabled: false,
  announce_channel_id: null,
  message_template: '🎉 Happy Birthday {user}!',
  birthday_role_id: null
};

export function getBirthdaySettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_birthday_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...BIRTHDAY_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        announce_channel_id: row.announce_channel_id ?? null,
        message_template: row.message_template ?? BIRTHDAY_DEFAULTS.message_template,
        birthday_role_id: row.birthday_role_id ?? null
      });
    });
  });
}

export function upsertBirthdaySettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const channel = isSnowflake(settings.announce_channel_id) ? settings.announce_channel_id : null;
    const template = truncate(settings.message_template || BIRTHDAY_DEFAULTS.message_template, 1000);
    const roleId = isSnowflake(settings.birthday_role_id) ? settings.birthday_role_id : null;
    db.run(
      `INSERT INTO guild_birthday_settings (guild_id, enabled, announce_channel_id, message_template, birthday_role_id)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         announce_channel_id = excluded.announce_channel_id,
         message_template = excluded.message_template,
         birthday_role_id = excluded.birthday_role_id,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, channel, template, roleId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot/dashboard: set a member's birthday. Validates day/month. */
export function setBirthday(guildId, userId, data) {
  return new Promise((resolve, reject) => {
    const month = clampRange(data.month, 1, 12, 0);
    const day = clampRange(data.day, 1, 31, 0);
    if (month === 0 || day === 0) {
      return reject(Object.assign(new Error('Invalid day/month'), { code: 'VALIDATION' }));
    }
    let year = null;
    if (data.year !== undefined && data.year !== null && data.year !== '') {
      year = clampRange(data.year, 1900, 2025, 0) || null;
    }
    db.run(
      `INSERT INTO guild_birthdays (guild_id, user_id, month, day, year)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(guild_id, user_id) DO UPDATE SET
         month = excluded.month, day = excluded.day, year = excluded.year`,
      [guildId, userId, month, day, year],
      function (err) {
        if (err) reject(err);
        else resolve({ month, day, year });
      }
    );
  });
}

export function getGuildBirthdays(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      'SELECT user_id, month, day, year FROM guild_birthdays WHERE guild_id = ? ORDER BY month ASC, day ASC',
      [guildId],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

export function removeBirthday(guildId, userId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_birthdays WHERE guild_id = ? AND user_id = ?', [guildId, userId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Bot: all members whose birthday is today (month/day), joined with the
 * enabled guild settings. Used by the birthday cog's daily loop. */
export function getTodaysBirthdays(month, day) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT b.guild_id, b.user_id, b.year,
              s.announce_channel_id, s.message_template, s.birthday_role_id
       FROM guild_birthdays b
       JOIN guild_birthday_settings s ON b.guild_id = s.guild_id
       WHERE s.enabled = 1 AND b.month = ? AND b.day = ?
         AND b.guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1)
         AND ${tierFilterSql('basic', 'b.guild_id')}`,
      [month, day],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

/** Bot: enabled guilds that have a birthday role configured (for the daily
 * "remove yesterday's role" sweep). */
export function getBirthdayRoleGuilds() {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT guild_id, birthday_role_id FROM guild_birthday_settings
       WHERE enabled = 1 AND birthday_role_id IS NOT NULL AND birthday_role_id != ''
         AND guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1)
         AND ${tierFilterSql('basic')}`,
      [],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

// ===== Module: Scheduled Announcements =====

export const SCHEDULED_TYPES = ['once', 'interval'];
const SCHEDULED_CONTENT_MAX = 2000;
const SCHEDULED_INTERVAL_MIN = 60;        // 1 min
const SCHEDULED_INTERVAL_MAX = 31536000;  // 1 year

function shapeScheduled(row) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    channel_id: row.channel_id,
    content: row.content ?? '',
    schedule_type: SCHEDULED_TYPES.includes(row.schedule_type) ? row.schedule_type : 'once',
    run_at: row.run_at ?? 0,
    interval_seconds: row.interval_seconds ?? 0,
    enabled: !!row.enabled,
    last_run: row.last_run ?? 0,
    created_at: row.created_at ?? null
  };
}

function buildScheduledValues(payload, base) {
  const pick = (key) => (payload[key] !== undefined ? payload[key] : base[key]);
  const channelId = pick('channel_id');
  if (!isSnowflake(channelId)) {
    throw Object.assign(new Error('channel_id must be a Discord snowflake'), { code: 'VALIDATION' });
  }
  const content = truncate(pick('content') || '', SCHEDULED_CONTENT_MAX);
  if (!content) {
    throw Object.assign(new Error('content required'), { code: 'VALIDATION' });
  }
  const scheduleType = SCHEDULED_TYPES.includes(pick('schedule_type')) ? pick('schedule_type') : 'once';
  const runAt = clampRange(pick('run_at'), 0, 4102444800, 0);
  const intervalSeconds = scheduleType === 'interval'
    ? clampRange(pick('interval_seconds'), SCHEDULED_INTERVAL_MIN, SCHEDULED_INTERVAL_MAX, SCHEDULED_INTERVAL_MIN)
    : 0;
  return {
    channel_id: channelId,
    content,
    schedule_type: scheduleType,
    run_at: runAt,
    interval_seconds: intervalSeconds,
    enabled: pick('enabled') ? 1 : 0
  };
}

export function getScheduledMessages(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      'SELECT * FROM guild_scheduled_messages WHERE guild_id = ? ORDER BY run_at ASC, created_at ASC',
      [guildId],
      (err, rows) => {
        if (err) reject(err);
        else resolve((rows || []).map(shapeScheduled));
      }
    );
  });
}

export function createScheduledMessage(guildId, payload) {
  return new Promise((resolve, reject) => {
    let v;
    try {
      v = buildScheduledValues(payload || {}, { schedule_type: 'once', run_at: 0, interval_seconds: 0, enabled: true, content: '', channel_id: null });
    } catch (err) {
      return reject(err);
    }
    const id = randomUUID();
    db.run(
      `INSERT INTO guild_scheduled_messages (id, guild_id, channel_id, content, schedule_type, run_at, interval_seconds, enabled)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, guildId, v.channel_id, v.content, v.schedule_type, v.run_at, v.interval_seconds, v.enabled],
      function (err) {
        if (err) return reject(err);
        db.get('SELECT * FROM guild_scheduled_messages WHERE id = ?', [id], (gErr, row) => {
          if (gErr) reject(gErr);
          else resolve(shapeScheduled(row));
        });
      }
    );
  });
}

export function updateScheduledMessage(guildId, id, patch) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_scheduled_messages WHERE guild_id = ? AND id = ?', [guildId, id], (gErr, row) => {
      if (gErr) return reject(gErr);
      if (!row) return reject(Object.assign(new Error('Scheduled message not found'), { code: 'NOT_FOUND' }));
      let v;
      try {
        v = buildScheduledValues(patch || {}, shapeScheduled(row));
      } catch (err) {
        return reject(err);
      }
      db.run(
        `UPDATE guild_scheduled_messages
           SET channel_id = ?, content = ?, schedule_type = ?, run_at = ?, interval_seconds = ?, enabled = ?
         WHERE guild_id = ? AND id = ?`,
        [v.channel_id, v.content, v.schedule_type, v.run_at, v.interval_seconds, v.enabled, guildId, id],
        function (upErr) {
          if (upErr) return reject(upErr);
          db.get('SELECT * FROM guild_scheduled_messages WHERE id = ?', [id], (g2, updated) => {
            if (g2) reject(g2);
            else resolve(shapeScheduled(updated));
          });
        }
      );
    });
  });
}

export function deleteScheduledMessage(guildId, id) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_scheduled_messages WHERE guild_id = ? AND id = ?', [guildId, id], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Bot: enabled messages whose run_at is due (across all guilds). */
export function getDueScheduledMessages(now) {
  return new Promise((resolve, reject) => {
    const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);
    db.all(
      `SELECT * FROM guild_scheduled_messages WHERE enabled = 1 AND run_at > 0 AND run_at <= ? AND guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1) AND ${tierFilterSql('pro')}`,
      [ts],
      (err, rows) => {
        if (err) reject(err);
        else resolve((rows || []).map(shapeScheduled));
      }
    );
  });
}

/** Bot: mark a scheduled message as run. 'once' → disabled; 'interval' → advance
 * run_at by interval_seconds. */
export function markScheduledRan(id, now) {
  return new Promise((resolve, reject) => {
    const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);
    db.get('SELECT * FROM guild_scheduled_messages WHERE id = ?', [id], (gErr, row) => {
      if (gErr) return reject(gErr);
      if (!row) return resolve(0);
      const isInterval = row.schedule_type === 'interval' && row.interval_seconds > 0;
      const nextRun = isInterval ? ts + row.interval_seconds : row.run_at;
      const enabled = isInterval ? 1 : 0;
      db.run(
        'UPDATE guild_scheduled_messages SET last_run = ?, run_at = ?, enabled = ? WHERE id = ?',
        [ts, nextRun, enabled, id],
        function (err) {
          if (err) reject(err);
          else resolve(this.changes);
        }
      );
    });
  });
}

// ===== Module: Anti-Raid =====

export const ANTIRAID_ACTIONS = ['alert', 'kick', 'ban'];

export const ANTIRAID_DEFAULTS = {
  enabled: false,
  join_rate_count: 5,
  join_rate_seconds: 10,
  action: 'alert',
  account_age_days: 0,
  alert_channel_id: null
};

export function getAntiRaidSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_antiraid_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...ANTIRAID_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        join_rate_count: clampRange(row.join_rate_count, 2, 100, 5),
        join_rate_seconds: clampRange(row.join_rate_seconds, 1, 600, 10),
        action: ANTIRAID_ACTIONS.includes(row.action) ? row.action : 'alert',
        account_age_days: clampRange(row.account_age_days, 0, 3650, 0),
        alert_channel_id: row.alert_channel_id ?? null
      });
    });
  });
}

export function upsertAntiRaidSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const count = clampRange(settings.join_rate_count, 2, 100, 5);
    const seconds = clampRange(settings.join_rate_seconds, 1, 600, 10);
    const action = ANTIRAID_ACTIONS.includes(settings.action) ? settings.action : 'alert';
    const ageDays = clampRange(settings.account_age_days, 0, 3650, 0);
    const alertChannel = isSnowflake(settings.alert_channel_id) ? settings.alert_channel_id : null;
    db.run(
      `INSERT INTO guild_antiraid_settings (guild_id, enabled, join_rate_count, join_rate_seconds, action, account_age_days, alert_channel_id)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         join_rate_count = excluded.join_rate_count,
         join_rate_seconds = excluded.join_rate_seconds,
         action = excluded.action,
         account_age_days = excluded.account_age_days,
         alert_channel_id = excluded.alert_channel_id,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, count, seconds, action, ageDays, alertChannel],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Module: Verification =====

export const VERIFICATION_DEFAULTS = {
  enabled: false,
  channel_id: null,
  verified_role_id: null,
  message: 'Click the button below to verify and unlock the server.',
  button_label: 'Verify'
};

export function getVerificationSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_verification_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...VERIFICATION_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        channel_id: row.channel_id ?? null,
        verified_role_id: row.verified_role_id ?? null,
        message: row.message ?? VERIFICATION_DEFAULTS.message,
        button_label: row.button_label || 'Verify'
      });
    });
  });
}

export function upsertVerificationSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const channel = isSnowflake(settings.channel_id) ? settings.channel_id : null;
    const role = isSnowflake(settings.verified_role_id) ? settings.verified_role_id : null;
    const message = truncate(settings.message || VERIFICATION_DEFAULTS.message, 2000);
    const label = truncate(settings.button_label || 'Verify', 80);
    db.run(
      `INSERT INTO guild_verification_settings (guild_id, enabled, channel_id, verified_role_id, message, button_label)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         channel_id = excluded.channel_id,
         verified_role_id = excluded.verified_role_id,
         message = excluded.message,
         button_label = excluded.button_label,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, channel, role, message, label],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot: store the posted verification panel message id. */
export function setVerificationPanelMessage(guildId, messageId) {
  return new Promise((resolve, reject) => {
    db.run(
      'UPDATE guild_verification_settings SET panel_message_id = ? WHERE guild_id = ?',
      [messageId ?? null, guildId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Module: Role Menus (buttons / select) =====

export const ROLE_MENU_TYPES = ['buttons', 'select'];

function shapeRoleMenu(row, options) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    channel_id: row.channel_id ?? null,
    message_id: row.message_id ?? null,
    name: row.name ?? '',
    menu_type: ROLE_MENU_TYPES.includes(row.menu_type) ? row.menu_type : 'buttons',
    exclusive: !!row.exclusive,
    use_embed: !!row.use_embed,
    embed: parseEmbedColumn(row.embed),
    options: Array.isArray(options) ? options : []
  };
}

function readRoleMenuOptions(menuId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT role_id, label, emoji FROM guild_role_menu_options WHERE menu_id = ? ORDER BY id ASC', [menuId], (err, rows) => {
      if (err) reject(err);
      else resolve((rows || []).map(r => ({ role_id: r.role_id, label: r.label ?? '', emoji: r.emoji ?? '' })));
    });
  });
}

function sanitizeRoleMenuOptions(input) {
  const arr = Array.isArray(input) ? input : [];
  const out = [];
  for (const o of arr.slice(0, 25)) {
    if (!o || !isSnowflake(o.role_id)) continue;
    out.push({
      role_id: o.role_id,
      label: truncate(o.label || '', 80),
      emoji: truncate(o.emoji || '', 64)
    });
  }
  return out;
}

export async function getRoleMenus(guildId) {
  const rows = await new Promise((resolve, reject) => {
    db.all('SELECT * FROM guild_role_menus WHERE guild_id = ? ORDER BY created_at ASC', [guildId], (err, r) => {
      if (err) reject(err); else resolve(r || []);
    });
  });
  const result = [];
  for (const row of rows) {
    result.push(shapeRoleMenu(row, await readRoleMenuOptions(row.id)));
  }
  return result;
}

/** Bot: role menus that are configured (have a channel) but not yet posted. */
export async function getPendingRoleMenus() {
  const rows = await new Promise((resolve, reject) => {
    db.all(`SELECT * FROM guild_role_menus WHERE channel_id IS NOT NULL AND (message_id IS NULL OR message_id = '') AND guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1) AND ${tierFilterSql('basic')}`, [], (err, r) => {
      if (err) reject(err); else resolve(r || []);
    });
  });
  const result = [];
  for (const row of rows) {
    result.push(shapeRoleMenu(row, await readRoleMenuOptions(row.id)));
  }
  return result;
}

function writeRoleMenuOptions(menuId, options) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_role_menu_options WHERE menu_id = ?', [menuId], (delErr) => {
      if (delErr) return reject(delErr);
      const clean = sanitizeRoleMenuOptions(options);
      if (clean.length === 0) return resolve();
      const stmt = db.prepare('INSERT INTO guild_role_menu_options (menu_id, role_id, label, emoji) VALUES (?, ?, ?, ?)');
      for (const o of clean) stmt.run([menuId, o.role_id, o.label, o.emoji]);
      stmt.finalize((err) => (err ? reject(err) : resolve()));
    });
  });
}

export function createRoleMenu(guildId, payload) {
  return runInTransaction(async () => {
    const id = randomUUID();
    const p = payload || {};
    const channelId = isSnowflake(p.channel_id) ? p.channel_id : null;
    const name = truncate(p.name || 'Role Menu', 100);
    const menuType = ROLE_MENU_TYPES.includes(p.menu_type) ? p.menu_type : 'buttons';
    const exclusive = p.exclusive ? 1 : 0;
    const useEmbed = p.use_embed ? 1 : 0;
    const embed = JSON.stringify(sanitizeEmbed(p.embed));
    await new Promise((resolve, reject) => {
      db.run(
        'INSERT INTO guild_role_menus (id, guild_id, channel_id, name, menu_type, exclusive, use_embed, embed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [id, guildId, channelId, name, menuType, exclusive, useEmbed, embed],
        (err) => (err ? reject(err) : resolve())
      );
    });
    await writeRoleMenuOptions(id, p.options);
    const row = await new Promise((resolve, reject) => {
      db.get('SELECT * FROM guild_role_menus WHERE id = ?', [id], (err, r) => (err ? reject(err) : resolve(r)));
    });
    return shapeRoleMenu(row, await readRoleMenuOptions(id));
  });
}

export function updateRoleMenu(guildId, menuId, patch) {
  return runInTransaction(async () => {
    const existing = await new Promise((resolve, reject) => {
      db.get('SELECT * FROM guild_role_menus WHERE guild_id = ? AND id = ?', [guildId, menuId], (err, r) => (err ? reject(err) : resolve(r)));
    });
    if (!existing) throw Object.assign(new Error('Role menu not found'), { code: 'NOT_FOUND' });
    const p = patch || {};
    const channelId = p.channel_id !== undefined ? (isSnowflake(p.channel_id) ? p.channel_id : null) : existing.channel_id;
    const name = p.name !== undefined ? truncate(p.name || 'Role Menu', 100) : existing.name;
    const menuType = p.menu_type !== undefined ? (ROLE_MENU_TYPES.includes(p.menu_type) ? p.menu_type : 'buttons') : existing.menu_type;
    const exclusive = p.exclusive !== undefined ? (p.exclusive ? 1 : 0) : existing.exclusive;
    const useEmbed = p.use_embed !== undefined ? (p.use_embed ? 1 : 0) : existing.use_embed;
    const embed = p.embed !== undefined ? JSON.stringify(sanitizeEmbed(p.embed)) : existing.embed;
    // Changing channel re-requires a fresh post → clear message_id.
    const clearMessage = channelId !== existing.channel_id;
    await new Promise((resolve, reject) => {
      db.run(
        `UPDATE guild_role_menus SET channel_id = ?, name = ?, menu_type = ?, exclusive = ?, use_embed = ?, embed = ?${clearMessage ? ', message_id = NULL' : ''}, updated_at = CURRENT_TIMESTAMP WHERE id = ?`,
        [channelId, name, menuType, exclusive, useEmbed, embed, menuId],
        (err) => (err ? reject(err) : resolve())
      );
    });
    if (p.options !== undefined) await writeRoleMenuOptions(menuId, p.options);
    const row = await new Promise((resolve, reject) => {
      db.get('SELECT * FROM guild_role_menus WHERE id = ?', [menuId], (err, r) => (err ? reject(err) : resolve(r)));
    });
    return shapeRoleMenu(row, await readRoleMenuOptions(menuId));
  });
}

export function deleteRoleMenu(guildId, menuId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_role_menus WHERE guild_id = ? AND id = ?', [guildId, menuId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Bot: a role menu by its posted message id (for exclusive-select handling). */
export async function getRoleMenuByMessage(guildId, messageId) {
  const row = await new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_role_menus WHERE guild_id = ? AND message_id = ?', [guildId, messageId], (err, r) => (err ? reject(err) : resolve(r)));
  });
  if (!row) return null;
  return shapeRoleMenu(row, await readRoleMenuOptions(row.id));
}

/** Bot: store the channel + posted message id for a role menu. */
export function setRoleMenuMessage(guildId, menuId, channelId, messageId) {
  return new Promise((resolve, reject) => {
    db.run(
      'UPDATE guild_role_menus SET channel_id = ?, message_id = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND id = ?',
      [isSnowflake(channelId) ? channelId : null, messageId ?? null, guildId, menuId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

// ===== Module: Tickets =====

export const TICKET_PANEL_TYPES = ['dropdown', 'buttons'];
export const TICKET_RATING_MODES = ['channel', 'dm', 'both'];
export const TICKET_BUTTON_STYLES = ['primary', 'secondary', 'success', 'danger'];

export const TICKET_DEFAULTS = {
  enabled: false,
  panel_channel_id: null,
  category_id: null,
  support_role_id: null,
  ping_role_id: null,
  panel_message: 'Need help? Click below to open a ticket.',
  button_label: 'Open Ticket',
  transcript_channel_id: null,
  log_channel_id: null,
  panel_type: 'dropdown',
  panel_embed: { ...DEFAULT_EMBED, title: 'Support Tickets', description: 'Need help? Open a ticket below and our team will assist you.' },
  welcome_embed: { ...DEFAULT_EMBED, description: 'Thanks for reaching out, {user}! A team member will be with you shortly. Use the buttons below to manage this ticket.' },
  naming_template: 'ticket-{user}',
  claim_enabled: true,
  close_confirm: true,
  rating_enabled: false,
  rating_mode: 'channel'
};

function ticketDefaults() {
  return {
    ...TICKET_DEFAULTS,
    panel_embed: { ...TICKET_DEFAULTS.panel_embed },
    welcome_embed: { ...TICKET_DEFAULTS.welcome_embed }
  };
}

export function getTicketSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_ticket_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve(ticketDefaults());
      const panelType = TICKET_PANEL_TYPES.includes(row.panel_type) ? row.panel_type : 'dropdown';
      const ratingMode = TICKET_RATING_MODES.includes(row.rating_mode) ? row.rating_mode : 'channel';
      resolve({
        enabled: !!row.enabled,
        panel_channel_id: row.panel_channel_id ?? null,
        category_id: row.category_id ?? null,
        support_role_id: row.support_role_id ?? null,
        ping_role_id: row.ping_role_id ?? null,
        panel_message: row.panel_message ?? TICKET_DEFAULTS.panel_message,
        button_label: row.button_label || 'Open Ticket',
        transcript_channel_id: row.transcript_channel_id ?? null,
        log_channel_id: row.log_channel_id ?? null,
        panel_type: panelType,
        panel_embed: row.panel_embed != null && row.panel_embed !== '' ? parseEmbedColumn(row.panel_embed) : { ...TICKET_DEFAULTS.panel_embed },
        welcome_embed: row.welcome_embed != null && row.welcome_embed !== '' ? parseEmbedColumn(row.welcome_embed) : { ...TICKET_DEFAULTS.welcome_embed },
        naming_template: row.naming_template || TICKET_DEFAULTS.naming_template,
        claim_enabled: row.claim_enabled == null ? true : !!row.claim_enabled,
        close_confirm: row.close_confirm == null ? true : !!row.close_confirm,
        rating_enabled: !!row.rating_enabled,
        rating_mode: ratingMode
      });
    });
  });
}

export function upsertTicketSettings(guildId, settings) {
  return new Promise((resolve, reject) => {
    const enabled = settings.enabled ? 1 : 0;
    const panelChannel = isSnowflake(settings.panel_channel_id) ? settings.panel_channel_id : null;
    const category = isSnowflake(settings.category_id) ? settings.category_id : null;
    const supportRole = isSnowflake(settings.support_role_id) ? settings.support_role_id : null;
    const pingRole = isSnowflake(settings.ping_role_id) ? settings.ping_role_id : null;
    const message = truncate(settings.panel_message || TICKET_DEFAULTS.panel_message, 2000);
    const label = truncate(settings.button_label || 'Open Ticket', 80);
    const transcriptChannel = isSnowflake(settings.transcript_channel_id) ? settings.transcript_channel_id : null;
    const logChannel = isSnowflake(settings.log_channel_id) ? settings.log_channel_id : null;
    const panelType = TICKET_PANEL_TYPES.includes(settings.panel_type) ? settings.panel_type : 'dropdown';
    const ratingMode = TICKET_RATING_MODES.includes(settings.rating_mode) ? settings.rating_mode : 'channel';
    const panelEmbed = JSON.stringify(sanitizeEmbed(settings.panel_embed));
    const welcomeEmbed = JSON.stringify(sanitizeEmbed(settings.welcome_embed));
    const naming = truncate(settings.naming_template || TICKET_DEFAULTS.naming_template, 80);
    const claim = settings.claim_enabled === false ? 0 : 1;
    const confirm = settings.close_confirm === false ? 0 : 1;
    const ratingEnabled = settings.rating_enabled ? 1 : 0;
    db.run(
      `INSERT INTO guild_ticket_settings
         (guild_id, enabled, panel_channel_id, category_id, support_role_id, ping_role_id, panel_message, button_label,
          transcript_channel_id, log_channel_id, panel_type, panel_embed, welcome_embed, naming_template,
          claim_enabled, close_confirm, rating_enabled, rating_mode)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         enabled = excluded.enabled,
         panel_channel_id = excluded.panel_channel_id,
         category_id = excluded.category_id,
         support_role_id = excluded.support_role_id,
         ping_role_id = excluded.ping_role_id,
         panel_message = excluded.panel_message,
         button_label = excluded.button_label,
         transcript_channel_id = excluded.transcript_channel_id,
         log_channel_id = excluded.log_channel_id,
         panel_type = excluded.panel_type,
         panel_embed = excluded.panel_embed,
         welcome_embed = excluded.welcome_embed,
         naming_template = excluded.naming_template,
         claim_enabled = excluded.claim_enabled,
         close_confirm = excluded.close_confirm,
         rating_enabled = excluded.rating_enabled,
         rating_mode = excluded.rating_mode,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, enabled, panelChannel, category, supportRole, pingRole, message, label,
       transcriptChannel, logChannel, panelType, panelEmbed, welcomeEmbed, naming,
       claim, confirm, ratingEnabled, ratingMode],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

export function setTicketPanelMessage(guildId, messageId) {
  return new Promise((resolve, reject) => {
    db.run('UPDATE guild_ticket_settings SET panel_message_id = ? WHERE guild_id = ?', [messageId ?? null, guildId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

// ----- Ticket categories (ticket types) -----

function shapeTicketCategory(row) {
  if (!row) return null;
  return {
    id: row.id,
    label: row.label || '',
    emoji: row.emoji || '',
    description: row.description || '',
    category_id: row.category_id ?? null,
    support_role_id: row.support_role_id ?? null,
    ping_role_id: row.ping_role_id ?? null,
    welcome_message: row.welcome_message || '',
    button_style: TICKET_BUTTON_STYLES.includes(row.button_style) ? row.button_style : 'primary',
    position: row.position ?? 0,
    enabled: row.enabled == null ? true : !!row.enabled
  };
}

export function getTicketCategories(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      'SELECT * FROM guild_ticket_categories WHERE guild_id = ? ORDER BY position ASC, created_at ASC',
      [guildId],
      (err, rows) => {
        if (err) reject(err);
        else resolve((rows || []).map(shapeTicketCategory));
      }
    );
  });
}

function ticketCategoryColumns(data) {
  return {
    label: truncate(data.label || 'Ticket', 80),
    emoji: truncate(data.emoji || '', 32) || null,
    description: truncate(data.description || '', 100) || null,
    category_id: isSnowflake(data.category_id) ? data.category_id : null,
    support_role_id: isSnowflake(data.support_role_id) ? data.support_role_id : null,
    ping_role_id: isSnowflake(data.ping_role_id) ? data.ping_role_id : null,
    welcome_message: truncate(data.welcome_message || '', 1000) || null,
    button_style: TICKET_BUTTON_STYLES.includes(data.button_style) ? data.button_style : 'primary',
    position: Number.isFinite(+data.position) ? Math.trunc(+data.position) : 0,
    enabled: data.enabled === false ? 0 : 1
  };
}

export function createTicketCategory(guildId, data) {
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const c = ticketCategoryColumns(data || {});
    db.run(
      `INSERT INTO guild_ticket_categories
         (id, guild_id, label, emoji, description, category_id, support_role_id, ping_role_id, welcome_message, button_style, position, enabled)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, guildId, c.label, c.emoji, c.description, c.category_id, c.support_role_id, c.ping_role_id, c.welcome_message, c.button_style, c.position, c.enabled],
      function (err) {
        if (err) reject(err);
        else resolve({ id });
      }
    );
  });
}

export function updateTicketCategory(guildId, id, data) {
  return new Promise((resolve, reject) => {
    const c = ticketCategoryColumns(data || {});
    db.run(
      `UPDATE guild_ticket_categories SET
         label = ?, emoji = ?, description = ?, category_id = ?, support_role_id = ?, ping_role_id = ?,
         welcome_message = ?, button_style = ?, position = ?, enabled = ?
       WHERE id = ? AND guild_id = ?`,
      [c.label, c.emoji, c.description, c.category_id, c.support_role_id, c.ping_role_id, c.welcome_message, c.button_style, c.position, c.enabled, id, guildId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

export function deleteTicketCategory(guildId, id) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_ticket_categories WHERE id = ? AND guild_id = ?', [id, guildId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Bot: full ticket config in one shot (settings + enabled categories). */
export async function getTicketConfig(guildId) {
  const settings = await getTicketSettings(guildId);
  const categories = (await getTicketCategories(guildId)).filter((c) => c.enabled);
  return { ...settings, categories };
}

// ----- Per-ticket state -----

function shapeTicket(row) {
  if (!row) return null;
  let extra = [];
  try { extra = row.extra_user_ids ? JSON.parse(row.extra_user_ids) : []; } catch { extra = []; }
  return {
    id: row.id,
    channel_id: row.channel_id ?? null,
    user_id: row.user_id ?? null,
    status: row.status || 'open',
    ticket_category_id: row.ticket_category_id ?? null,
    number: row.number ?? 0,
    claimed_by: row.claimed_by ?? null,
    rating: row.rating ?? null,
    rating_comment: row.rating_comment ?? null,
    closed_by: row.closed_by ?? null,
    closed_at: row.closed_at ?? null,
    extra_user_ids: Array.isArray(extra) ? extra : [],
    created_at: row.created_at ?? null
  };
}

/** Bot: record a newly-opened ticket channel; assigns a per-guild number. */
export function createTicket(guildId, channelId, userId, ticketCategoryId = null) {
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const catId = (typeof ticketCategoryId === 'string' && ticketCategoryId) ? ticketCategoryId : null;
    db.run(
      `INSERT INTO guild_tickets (id, guild_id, channel_id, user_id, ticket_category_id, number, status)
       VALUES (?, ?, ?, ?, ?, (SELECT COALESCE(MAX(number), 0) + 1 FROM guild_tickets WHERE guild_id = ?), 'open')`,
      [id, guildId, channelId, userId, catId, guildId],
      function (err) {
        if (err) return reject(err);
        db.get('SELECT number FROM guild_tickets WHERE id = ?', [id], (gErr, row) => {
          if (gErr) reject(gErr);
          else resolve({ id, number: row?.number ?? 0 });
        });
      }
    );
  });
}

/** Bot: the open ticket for a user (or null) — used to avoid duplicates. */
export function getOpenTicketForUser(guildId, userId) {
  return new Promise((resolve, reject) => {
    db.get(
      "SELECT * FROM guild_tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
      [guildId, userId],
      (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      }
    );
  });
}

/** Bot: ticket row for a channel (open or closed). */
export function getTicketByChannel(guildId, channelId) {
  return new Promise((resolve, reject) => {
    db.get(
      'SELECT * FROM guild_tickets WHERE guild_id = ? AND channel_id = ? ORDER BY created_at DESC LIMIT 1',
      [guildId, channelId],
      (err, row) => {
        if (err) reject(err);
        else resolve(shapeTicket(row));
      }
    );
  });
}

/** Bot: mark the ticket for a channel as closed. */
export function closeTicketByChannel(guildId, channelId, closedBy = null) {
  return new Promise((resolve, reject) => {
    db.run(
      "UPDATE guild_tickets SET status = 'closed', closed_by = ?, closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND channel_id = ?",
      [closedBy ?? null, guildId, channelId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot: claim a ticket (assign a staff handler). */
export function claimTicket(guildId, channelId, userId) {
  return new Promise((resolve, reject) => {
    db.run(
      'UPDATE guild_tickets SET claimed_by = ? WHERE guild_id = ? AND channel_id = ?',
      [userId ?? null, guildId, channelId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot: store the opener's rating (1-5) + optional comment, by ticket id. */
export function setTicketRating(guildId, ticketId, rating, comment = null) {
  return new Promise((resolve, reject) => {
    const r = clampRange(rating, 1, 5, null);
    if (r == null) return resolve(0);
    db.run(
      'UPDATE guild_tickets SET rating = ?, rating_comment = ? WHERE id = ? AND guild_id = ?',
      [r, truncate(comment || '', 1000) || null, ticketId, guildId],
      function (err) {
        if (err) reject(err);
        else resolve(this.changes);
      }
    );
  });
}

/** Bot: add/remove users manually granted access to a ticket channel. */
export function updateTicketExtraUsers(guildId, channelId, { add = [], remove = [] } = {}) {
  return new Promise((resolve, reject) => {
    db.get('SELECT extra_user_ids FROM guild_tickets WHERE guild_id = ? AND channel_id = ?', [guildId, channelId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve(0);
      let arr = [];
      try { arr = row.extra_user_ids ? JSON.parse(row.extra_user_ids) : []; } catch { arr = []; }
      if (!Array.isArray(arr)) arr = [];
      const addIds = (Array.isArray(add) ? add : []).filter(isSnowflake).map(String);
      const removeIds = new Set((Array.isArray(remove) ? remove : []).map(String));
      arr = arr.filter((u) => !removeIds.has(String(u)));
      for (const u of addIds) if (!arr.includes(u)) arr.push(u);
      db.run('UPDATE guild_tickets SET extra_user_ids = ? WHERE guild_id = ? AND channel_id = ?', [JSON.stringify(arr), guildId, channelId], function (uErr) {
        if (uErr) reject(uErr);
        else resolve(arr);
      });
    });
  });
}

export function getGuildTickets(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT id, channel_id, user_id, status, ticket_category_id, number, claimed_by, rating, rating_comment, closed_by, closed_at, created_at
       FROM guild_tickets WHERE guild_id = ? ORDER BY created_at DESC LIMIT 100`,
      [guildId],
      (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      }
    );
  });
}

// ===== Module: Giveaways =====

function shapeGiveaway(row) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    channel_id: row.channel_id ?? null,
    message_id: row.message_id ?? null,
    prize: row.prize ?? '',
    winners_count: row.winners_count ?? 1,
    ends_at: row.ends_at ?? 0,
    ended: !!row.ended,
    created_at: row.created_at ?? null
  };
}

/** Bot: create a giveaway (from !gstart). Returns the new id. */
export function createGiveaway(guildId, payload) {
  return new Promise((resolve, reject) => {
    const p = payload || {};
    const channelId = isSnowflake(p.channel_id) ? p.channel_id : null;
    if (!channelId) return reject(Object.assign(new Error('channel_id required'), { code: 'VALIDATION' }));
    const prize = truncate(p.prize || 'a prize', 256);
    const winners = clampRange(p.winners_count, 1, 50, 1);
    const endsAt = clampRange(p.ends_at, 0, 4102444800, 0);
    const id = randomUUID();
    db.run(
      'INSERT INTO guild_giveaways (id, guild_id, channel_id, prize, winners_count, ends_at) VALUES (?, ?, ?, ?, ?, ?)',
      [id, guildId, channelId, prize, winners, endsAt],
      function (err) {
        if (err) reject(err);
        else resolve({ id, prize, winners_count: winners, ends_at: endsAt });
      }
    );
  });
}

export function setGiveawayMessage(guildId, giveawayId, messageId) {
  return new Promise((resolve, reject) => {
    db.run('UPDATE guild_giveaways SET message_id = ? WHERE guild_id = ? AND id = ?', [messageId ?? null, guildId, giveawayId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Bot: add an entry (idempotent). */
export function addGiveawayEntry(giveawayId, userId) {
  return new Promise((resolve, reject) => {
    db.run('INSERT OR IGNORE INTO guild_giveaway_entries (giveaway_id, user_id) VALUES (?, ?)', [giveawayId, userId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

export function getGiveawayEntries(giveawayId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT user_id FROM guild_giveaway_entries WHERE giveaway_id = ?', [giveawayId], (err, rows) => {
      if (err) reject(err);
      else resolve((rows || []).map(r => r.user_id));
    });
  });
}

/** Bot: giveaways that have ended but not yet been drawn. */
export function getDueGiveaways(now) {
  return new Promise((resolve, reject) => {
    const ts = Number.isFinite(now) ? Math.floor(now) : Math.floor(Date.now() / 1000);
    db.all(`SELECT * FROM guild_giveaways WHERE ended = 0 AND ends_at > 0 AND ends_at <= ? AND guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1) AND ${tierFilterSql('pro')}`, [ts], (err, rows) => {
      if (err) reject(err);
      else resolve((rows || []).map(shapeGiveaway));
    });
  });
}

export function markGiveawayEnded(giveawayId) {
  return new Promise((resolve, reject) => {
    db.run('UPDATE guild_giveaways SET ended = 1 WHERE id = ?', [giveawayId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

export function getGuildGiveaways(guildId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT * FROM guild_giveaways WHERE guild_id = ? ORDER BY created_at DESC LIMIT 100', [guildId], (err, rows) => {
      if (err) reject(err);
      else resolve((rows || []).map(shapeGiveaway));
    });
  });
}

/** Bot: a single giveaway by id (for reroll). */
export function getGiveawayById(guildId, giveawayId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_giveaways WHERE guild_id = ? AND id = ?', [guildId, giveawayId], (err, row) => {
      if (err) reject(err);
      else resolve(shapeGiveaway(row));
    });
  });
}

export function deleteGiveaway(guildId, giveawayId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_giveaways WHERE guild_id = ? AND id = ?', [guildId, giveawayId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

// ============================================================
// New modules (v23-v27): Counting / Polls / Invite-Tracking /
// Applications / Economy
// ============================================================

/** Promisified db.run for the helpers below (returns the statement context). */
function runStmt(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) { if (err) reject(err); else resolve(this); });
  });
}

// ----- Counting -----

export const COUNTING_DEFAULTS = {
  enabled: false,
  channel_id: null,
  current_count: 0,
  last_user_id: null,
  high_score: 0,
  reset_on_fail: true,
  count_emoji: '✅'
};

function shapeCounting(row) {
  if (!row) return { ...COUNTING_DEFAULTS };
  return {
    enabled: !!row.enabled,
    channel_id: row.channel_id ?? null,
    current_count: row.current_count || 0,
    last_user_id: row.last_user_id ?? null,
    high_score: row.high_score || 0,
    reset_on_fail: !!row.reset_on_fail,
    count_emoji: row.count_emoji || '✅'
  };
}

export function getCountingSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_counting_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) reject(err); else resolve(shapeCounting(row));
    });
  });
}

/** Dashboard upsert — only the config columns; runtime state is bot-managed. */
export function upsertCountingSettings(guildId, settings) {
  const enabled = settings.enabled ? 1 : 0;
  const channel = isSnowflake(settings.channel_id) ? settings.channel_id : null;
  const reset = settings.reset_on_fail === false ? 0 : 1;
  const emoji = truncate(settings.count_emoji || '✅', 64);
  return runStmt(
    `INSERT INTO guild_counting_settings (guild_id, enabled, channel_id, reset_on_fail, count_emoji)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(guild_id) DO UPDATE SET
       enabled = excluded.enabled,
       channel_id = excluded.channel_id,
       reset_on_fail = excluded.reset_on_fail,
       count_emoji = excluded.count_emoji,
       updated_at = CURRENT_TIMESTAMP`,
    [guildId, enabled, channel, reset, emoji]
  );
}

/**
 * Bot: validate the next number in the counting channel (atomic). Returns
 * { accepted, current, high_score, expected, reset, reason }. A wrong number or
 * the same user counting twice in a row fails; on fail the count resets to 0
 * when reset_on_fail is set.
 */
export function recordCount(guildId, userId, number) {
  return runInTransaction(async () => {
    const row = await dbGet('SELECT * FROM guild_counting_settings WHERE guild_id = ?', [guildId]);
    const s = shapeCounting(row);
    if (!s.enabled) return { accepted: false, reason: 'disabled' };
    const expected = (s.current_count || 0) + 1;
    const n = Math.trunc(Number(number));
    if (userId && s.last_user_id && String(userId) === String(s.last_user_id)) {
      // Same user twice in a row.
      if (s.reset_on_fail) {
        await runStmt('UPDATE guild_counting_settings SET current_count = 0, last_user_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?', [guildId]);
        return { accepted: false, reason: 'double_count', reset: true, expected, current: 0, high_score: s.high_score };
      }
      return { accepted: false, reason: 'double_count', reset: false, expected, current: s.current_count, high_score: s.high_score };
    }
    if (n !== expected) {
      if (s.reset_on_fail) {
        await runStmt('UPDATE guild_counting_settings SET current_count = 0, last_user_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?', [guildId]);
        return { accepted: false, reason: 'wrong_number', reset: true, expected, current: 0, high_score: s.high_score };
      }
      return { accepted: false, reason: 'wrong_number', reset: false, expected, current: s.current_count, high_score: s.high_score };
    }
    const high = Math.max(s.high_score || 0, expected);
    await runStmt(
      'UPDATE guild_counting_settings SET current_count = ?, last_user_id = ?, high_score = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?',
      [expected, String(userId), high, guildId]
    );
    return { accepted: true, current: expected, high_score: high, new_record: high === expected && expected > (s.high_score || 0) };
  });
}

// ----- Polls -----

function capTextArray(raw, cap = 25, itemCap = 100) {
  let arr = [];
  if (Array.isArray(raw)) arr = raw;
  else if (typeof raw === 'string' && raw) { try { const p = JSON.parse(raw); if (Array.isArray(p)) arr = p; } catch { /* ignore */ } }
  return arr.map((x) => truncate(x ?? '', itemCap)).filter((x) => x !== '').slice(0, cap);
}

function shapePoll(row, counts) {
  if (!row) return null;
  return {
    id: row.id,
    guild_id: row.guild_id,
    channel_id: row.channel_id ?? null,
    message_id: row.message_id ?? null,
    question: row.question ?? '',
    options: capTextArray(row.options),
    multi: !!row.multi,
    ends_at: row.ends_at || 0,
    ended: !!row.ended,
    counts: counts || null
  };
}

function getPollCounts(pollId, optionCount) {
  return new Promise((resolve, reject) => {
    db.all('SELECT option_index, COUNT(*) AS n FROM guild_poll_votes WHERE poll_id = ? GROUP BY option_index', [pollId], (err, rows) => {
      if (err) return reject(err);
      const counts = new Array(optionCount).fill(0);
      for (const r of (rows || [])) { if (r.option_index >= 0 && r.option_index < optionCount) counts[r.option_index] = r.n; }
      resolve(counts);
    });
  });
}

export function createPoll(guildId, data) {
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const channel = isSnowflake(data.channel_id) ? data.channel_id : null;
    const question = truncate(data.question ?? '', 300);
    const options = capTextArray(data.options);
    if (options.length < 2) { const e = new Error('A poll needs at least 2 options'); e.code = 'VALIDATION'; return reject(e); }
    const multi = data.multi ? 1 : 0;
    const ends = data.ends_at && Number(data.ends_at) > 0 ? Math.floor(Number(data.ends_at)) : 0;
    db.run(
      'INSERT INTO guild_polls (id, guild_id, channel_id, message_id, question, options, multi, ends_at, ended) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)',
      [id, guildId, channel, null, question, JSON.stringify(options), multi, ends],
      (err) => { if (err) reject(err); else resolve({ id, guild_id: guildId, channel_id: channel, question, options, multi: !!multi, ends_at: ends, ended: false }); }
    );
  });
}

export function setPollMessage(guildId, pollId, messageId) {
  return runStmt('UPDATE guild_polls SET message_id = ? WHERE guild_id = ? AND id = ?', [isSnowflake(messageId) ? messageId : null, guildId, pollId]);
}

export async function getPoll(guildId, pollId) {
  const row = await dbGet('SELECT * FROM guild_polls WHERE guild_id = ? AND id = ?', [guildId, pollId]);
  if (!row) return null;
  const opts = capTextArray(row.options);
  const counts = await getPollCounts(pollId, opts.length);
  return shapePoll(row, counts);
}

/** Toggle/replace a user's vote; returns the updated counts array. */
export function votePoll(guildId, pollId, userId, optionIndex) {
  return runInTransaction(async () => {
    const row = await dbGet('SELECT * FROM guild_polls WHERE guild_id = ? AND id = ?', [guildId, pollId]);
    if (!row || row.ended) return { ok: false, reason: 'closed' };
    const opts = capTextArray(row.options);
    const idx = Math.trunc(Number(optionIndex));
    if (idx < 0 || idx >= opts.length) return { ok: false, reason: 'bad_option' };
    const existing = await dbGet('SELECT 1 AS x FROM guild_poll_votes WHERE poll_id = ? AND user_id = ? AND option_index = ?', [pollId, userId, idx]);
    if (existing) {
      await runStmt('DELETE FROM guild_poll_votes WHERE poll_id = ? AND user_id = ? AND option_index = ?', [pollId, userId, idx]);
    } else {
      if (!row.multi) await runStmt('DELETE FROM guild_poll_votes WHERE poll_id = ? AND user_id = ?', [pollId, userId]);
      await runStmt('INSERT OR IGNORE INTO guild_poll_votes (poll_id, user_id, option_index) VALUES (?, ?, ?)', [pollId, userId, idx]);
    }
    const counts = await getPollCounts(pollId, opts.length);
    return { ok: true, counts, options: opts, question: row.question, multi: !!row.multi };
  });
}

export function getDuePolls(now) {
  return new Promise((resolve, reject) => {
    db.all('SELECT * FROM guild_polls WHERE ended = 0 AND ends_at > 0 AND ends_at <= ?', [now], async (err, rows) => {
      if (err) return reject(err);
      try {
        const out = [];
        for (const row of (rows || [])) {
          const opts = capTextArray(row.options);
          const counts = await getPollCounts(row.id, opts.length);
          out.push(shapePoll(row, counts));
        }
        resolve(out);
      } catch (e) { reject(e); }
    });
  });
}

export function markPollEnded(pollId) {
  return runStmt('UPDATE guild_polls SET ended = 1 WHERE id = ?', [pollId]);
}

export function getGuildPolls(guildId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT * FROM guild_polls WHERE guild_id = ? ORDER BY created_at DESC LIMIT 100', [guildId], async (err, rows) => {
      if (err) return reject(err);
      try {
        const out = [];
        for (const row of (rows || [])) {
          const opts = capTextArray(row.options);
          const counts = await getPollCounts(row.id, opts.length);
          const poll = shapePoll(row, counts);
          poll.total_votes = counts.reduce((a, b) => a + b, 0);
          out.push(poll);
        }
        resolve(out);
      } catch (e) { reject(e); }
    });
  });
}

export function deletePoll(guildId, pollId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_polls WHERE guild_id = ? AND id = ?', [guildId, pollId], function (err) { if (err) reject(err); else resolve(this.changes); });
  });
}

// ----- Invite tracking -----

export const INVITE_DEFAULTS = {
  enabled: false,
  log_channel_id: null,
  message_template: '👋 {user} joined — invited by {inviter} (now {invites} invites)'
};

export function getInviteSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_invite_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve({ ...INVITE_DEFAULTS });
      resolve({
        enabled: !!row.enabled,
        log_channel_id: row.log_channel_id ?? null,
        message_template: row.message_template || INVITE_DEFAULTS.message_template
      });
    });
  });
}

export function upsertInviteSettings(guildId, settings) {
  const enabled = settings.enabled ? 1 : 0;
  const channel = isSnowflake(settings.log_channel_id) ? settings.log_channel_id : null;
  const tpl = truncate(settings.message_template || INVITE_DEFAULTS.message_template, 1000);
  return runStmt(
    `INSERT INTO guild_invite_settings (guild_id, enabled, log_channel_id, message_template)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(guild_id) DO UPDATE SET
       enabled = excluded.enabled,
       log_channel_id = excluded.log_channel_id,
       message_template = excluded.message_template,
       updated_at = CURRENT_TIMESTAMP`,
    [guildId, enabled, channel, tpl]
  );
}

/** Bot: replace the cached invite-use counts for a guild (sync on ready/create). */
export function replaceGuildInvites(guildId, invites) {
  return runInTransaction(async () => {
    await runStmt('DELETE FROM guild_invites WHERE guild_id = ?', [guildId]);
    for (const inv of (Array.isArray(invites) ? invites : [])) {
      if (!inv || !inv.code) continue;
      await runStmt('INSERT OR REPLACE INTO guild_invites (guild_id, code, inviter_id, uses) VALUES (?, ?, ?, ?)',
        [guildId, String(inv.code), inv.inviter_id ? String(inv.inviter_id) : null, Math.trunc(Number(inv.uses) || 0)]);
    }
    return { count: Array.isArray(invites) ? invites.length : 0 };
  });
}

export function getGuildInvitesCache(guildId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT code, inviter_id, uses FROM guild_invites WHERE guild_id = ?', [guildId], (err, rows) => {
      if (err) reject(err); else resolve(rows || []);
    });
  });
}

/** Bot: record who invited a joining member; returns the inviter's total invites. */
export function recordMemberInvite(guildId, { user_id, inviter_id, code } = {}) {
  return runInTransaction(async () => {
    if (!user_id) { const e = new Error('user_id required'); e.code = 'VALIDATION'; throw e; }
    await runStmt(
      `INSERT INTO guild_member_invites (guild_id, user_id, inviter_id, code, joined_at)
       VALUES (?, ?, ?, ?, strftime('%s','now'))
       ON CONFLICT(guild_id, user_id) DO UPDATE SET inviter_id = excluded.inviter_id, code = excluded.code, joined_at = excluded.joined_at`,
      [guildId, String(user_id), inviter_id ? String(inviter_id) : null, code ? String(code) : null]
    );
    let inviter_invites = 0;
    if (inviter_id) {
      const r = await dbGet('SELECT COUNT(*) AS n FROM guild_member_invites WHERE guild_id = ? AND inviter_id = ?', [guildId, String(inviter_id)]);
      inviter_invites = r?.n || 0;
    }
    return { inviter_invites };
  });
}

export function getInviteLeaderboard(guildId, limit = 25) {
  const lim = clampRange(limit, 1, 100, 25);
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT inviter_id, COUNT(*) AS invites FROM guild_member_invites
       WHERE guild_id = ? AND inviter_id IS NOT NULL
       GROUP BY inviter_id ORDER BY invites DESC LIMIT ?`,
      [guildId, lim],
      (err, rows) => { if (err) reject(err); else resolve((rows || []).map((r, i) => ({ inviter_id: r.inviter_id, invites: r.invites, rank: i + 1 }))); }
    );
  });
}

// ----- Applications -----

function shapeApplicationForm(row) {
  if (!row) return null;
  return {
    id: row.id,
    name: row.name ?? '',
    description: row.description ?? '',
    questions: capTextArray(row.questions, 5, 300),
    review_channel_id: row.review_channel_id ?? null,
    accepted_role_id: row.accepted_role_id ?? null,
    panel_channel_id: row.panel_channel_id ?? null,
    panel_message_id: row.panel_message_id ?? null,
    button_label: row.button_label || 'Apply',
    position: row.position || 0,
    enabled: !!row.enabled
  };
}

export function getApplicationForms(guildId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT * FROM guild_application_forms WHERE guild_id = ? ORDER BY position ASC, created_at ASC', [guildId], (err, rows) => {
      if (err) reject(err); else resolve((rows || []).map(shapeApplicationForm));
    });
  });
}

export function getEnabledApplicationForms(guildId) {
  return new Promise((resolve, reject) => {
    db.all('SELECT * FROM guild_application_forms WHERE guild_id = ? AND enabled = 1 ORDER BY position ASC, created_at ASC', [guildId], (err, rows) => {
      if (err) reject(err); else resolve((rows || []).map(shapeApplicationForm));
    });
  });
}

export function getApplicationForm(guildId, formId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_application_forms WHERE guild_id = ? AND id = ?', [guildId, formId], (err, row) => {
      if (err) reject(err); else resolve(shapeApplicationForm(row));
    });
  });
}

function coerceFormFields(data) {
  return {
    name: truncate(data.name ?? '', 100),
    description: truncate(data.description ?? '', 1000),
    questions: JSON.stringify(capTextArray(data.questions, 5, 300)),
    review_channel_id: isSnowflake(data.review_channel_id) ? data.review_channel_id : null,
    accepted_role_id: isSnowflake(data.accepted_role_id) ? data.accepted_role_id : null,
    button_label: truncate(data.button_label || 'Apply', 80),
    position: clampRange(data.position, 0, 1000, 0),
    enabled: data.enabled === false ? 0 : 1
  };
}

export function createApplicationForm(guildId, data) {
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const f = coerceFormFields(data);
    db.run(
      `INSERT INTO guild_application_forms (id, guild_id, name, description, questions, review_channel_id, accepted_role_id, button_label, position, enabled)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, guildId, f.name, f.description, f.questions, f.review_channel_id, f.accepted_role_id, f.button_label, f.position, f.enabled],
      (err) => { if (err) reject(err); else getApplicationForm(guildId, id).then(resolve).catch(reject); }
    );
  });
}

export function updateApplicationForm(guildId, formId, data) {
  return new Promise((resolve, reject) => {
    const f = coerceFormFields(data);
    db.run(
      `UPDATE guild_application_forms SET name = ?, description = ?, questions = ?, review_channel_id = ?, accepted_role_id = ?, button_label = ?, position = ?, enabled = ?
       WHERE guild_id = ? AND id = ?`,
      [f.name, f.description, f.questions, f.review_channel_id, f.accepted_role_id, f.button_label, f.position, f.enabled, guildId, formId],
      function (err) {
        if (err) return reject(err);
        if (this.changes === 0) { const e = new Error('Form not found'); e.code = 'NOT_FOUND'; return reject(e); }
        getApplicationForm(guildId, formId).then(resolve).catch(reject);
      }
    );
  });
}

export function deleteApplicationForm(guildId, formId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_application_forms WHERE guild_id = ? AND id = ?', [guildId, formId], function (err) { if (err) reject(err); else resolve(this.changes); });
  });
}

export function setApplicationPanelMessage(guildId, formId, channelId, messageId) {
  return runStmt('UPDATE guild_application_forms SET panel_channel_id = ?, panel_message_id = ? WHERE guild_id = ? AND id = ?',
    [isSnowflake(channelId) ? channelId : null, isSnowflake(messageId) ? messageId : null, guildId, formId]);
}

export function createApplication(guildId, { form_id, user_id, answers } = {}) {
  return new Promise((resolve, reject) => {
    if (!form_id || !user_id) { const e = new Error('form_id and user_id required'); e.code = 'VALIDATION'; return reject(e); }
    const id = randomUUID();
    let ans = [];
    if (Array.isArray(answers)) ans = answers.slice(0, 5).map((a) => ({ q: truncate(a?.q ?? '', 300), a: truncate(a?.a ?? '', 1024) }));
    db.run(
      "INSERT INTO guild_applications (id, form_id, guild_id, user_id, answers, status) VALUES (?, ?, ?, ?, ?, 'pending')",
      [id, form_id, guildId, String(user_id), JSON.stringify(ans)],
      (err) => { if (err) reject(err); else resolve({ id }); }
    );
  });
}

export function reviewApplication(guildId, appId, { status, reviewer_id } = {}) {
  const st = ['pending', 'accepted', 'denied'].includes(status) ? status : 'pending';
  return new Promise((resolve, reject) => {
    db.run('UPDATE guild_applications SET status = ?, reviewer_id = ? WHERE guild_id = ? AND id = ?',
      [st, reviewer_id ? String(reviewer_id) : null, guildId, appId],
      function (err) { if (err) reject(err); else resolve(this.changes); });
  });
}

export function getApplications(guildId, { status, limit = 50 } = {}) {
  const lim = clampRange(limit, 1, 200, 50);
  const where = status ? ' AND a.status = ?' : '';
  const params = status ? [guildId, status, lim] : [guildId, lim];
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT a.*, f.name AS form_name FROM guild_applications a
       LEFT JOIN guild_application_forms f ON f.id = a.form_id
       WHERE a.guild_id = ?${where} ORDER BY a.created_at DESC LIMIT ?`,
      params,
      (err, rows) => {
        if (err) return reject(err);
        resolve((rows || []).map((r) => ({
          id: r.id, form_id: r.form_id, form_name: r.form_name ?? null, user_id: r.user_id,
          answers: (() => { try { const p = JSON.parse(r.answers || '[]'); return Array.isArray(p) ? p : []; } catch { return []; } })(),
          status: r.status, reviewer_id: r.reviewer_id ?? null, created_at: r.created_at
        })));
      }
    );
  });
}

// ----- Economy -----

export const ECONOMY_DEFAULTS = {
  enabled: false,
  currency_name: 'coins',
  currency_symbol: '🪙',
  start_balance: 0,
  daily_amount: 200,
  work_min: 50,
  work_max: 250,
  work_cooldown: 3600
};

const DAILY_COOLDOWN = 86400;

function shapeEconomy(row) {
  if (!row) return { ...ECONOMY_DEFAULTS };
  return {
    enabled: !!row.enabled,
    currency_name: row.currency_name || 'coins',
    currency_symbol: row.currency_symbol || '🪙',
    start_balance: row.start_balance || 0,
    daily_amount: row.daily_amount || 0,
    work_min: row.work_min || 0,
    work_max: row.work_max || 0,
    work_cooldown: row.work_cooldown || 0
  };
}

export function getEconomySettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_economy_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) reject(err); else resolve(shapeEconomy(row));
    });
  });
}

export function upsertEconomySettings(guildId, settings) {
  const enabled = settings.enabled ? 1 : 0;
  const name = truncate(settings.currency_name || 'coins', 32);
  const symbol = truncate(settings.currency_symbol || '🪙', 16);
  const start = clampRange(settings.start_balance, 0, 1000000000, 0);
  const daily = clampRange(settings.daily_amount, 0, 1000000000, 200);
  let wmin = clampRange(settings.work_min, 0, 1000000000, 50);
  let wmax = clampRange(settings.work_max, 0, 1000000000, 250);
  if (wmax < wmin) wmax = wmin;
  const cd = clampRange(settings.work_cooldown, 0, 604800, 3600);
  return runStmt(
    `INSERT INTO guild_economy_settings (guild_id, enabled, currency_name, currency_symbol, start_balance, daily_amount, work_min, work_max, work_cooldown)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(guild_id) DO UPDATE SET
       enabled = excluded.enabled, currency_name = excluded.currency_name, currency_symbol = excluded.currency_symbol,
       start_balance = excluded.start_balance, daily_amount = excluded.daily_amount, work_min = excluded.work_min,
       work_max = excluded.work_max, work_cooldown = excluded.work_cooldown, updated_at = CURRENT_TIMESTAMP`,
    [guildId, enabled, name, symbol, start, daily, wmin, wmax, cd]
  );
}

async function ensureEconomyUserRow(guildId, userId, startBalance) {
  await runStmt('INSERT OR IGNORE INTO guild_economy_users (guild_id, user_id, balance) VALUES (?, ?, ?)', [guildId, String(userId), Math.trunc(startBalance) || 0]);
}

export function getEconomyBalance(guildId, userId) {
  return runInTransaction(async () => {
    const s = shapeEconomy(await dbGet('SELECT * FROM guild_economy_settings WHERE guild_id = ?', [guildId]));
    await ensureEconomyUserRow(guildId, userId, s.start_balance);
    const u = await dbGet('SELECT balance FROM guild_economy_users WHERE guild_id = ? AND user_id = ?', [guildId, String(userId)]);
    return { balance: u?.balance || 0, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
  });
}

export function economyDaily(guildId, userId, now) {
  return runInTransaction(async () => {
    const s = shapeEconomy(await dbGet('SELECT * FROM guild_economy_settings WHERE guild_id = ?', [guildId]));
    if (!s.enabled) return { ok: false, reason: 'disabled' };
    await ensureEconomyUserRow(guildId, userId, s.start_balance);
    const u = await dbGet('SELECT * FROM guild_economy_users WHERE guild_id = ? AND user_id = ?', [guildId, String(userId)]);
    const elapsed = now - (u.last_daily || 0);
    if (u.last_daily && elapsed < DAILY_COOLDOWN) {
      return { ok: false, reason: 'cooldown', remaining: DAILY_COOLDOWN - elapsed, balance: u.balance, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
    }
    const balance = (u.balance || 0) + s.daily_amount;
    await runStmt('UPDATE guild_economy_users SET balance = ?, last_daily = ? WHERE guild_id = ? AND user_id = ?', [balance, now, guildId, String(userId)]);
    return { ok: true, amount: s.daily_amount, balance, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
  });
}

export function economyWork(guildId, userId, now) {
  return runInTransaction(async () => {
    const s = shapeEconomy(await dbGet('SELECT * FROM guild_economy_settings WHERE guild_id = ?', [guildId]));
    if (!s.enabled) return { ok: false, reason: 'disabled' };
    await ensureEconomyUserRow(guildId, userId, s.start_balance);
    const u = await dbGet('SELECT * FROM guild_economy_users WHERE guild_id = ? AND user_id = ?', [guildId, String(userId)]);
    const elapsed = now - (u.last_work || 0);
    if (u.last_work && elapsed < s.work_cooldown) {
      return { ok: false, reason: 'cooldown', remaining: s.work_cooldown - elapsed, balance: u.balance, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
    }
    const span = Math.max(0, s.work_max - s.work_min);
    const amount = s.work_min + Math.floor(Math.random() * (span + 1));
    const balance = (u.balance || 0) + amount;
    await runStmt('UPDATE guild_economy_users SET balance = ?, last_work = ? WHERE guild_id = ? AND user_id = ?', [balance, now, guildId, String(userId)]);
    return { ok: true, amount, balance, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
  });
}

export function economyPay(guildId, fromId, toId, amount) {
  return runInTransaction(async () => {
    const s = shapeEconomy(await dbGet('SELECT * FROM guild_economy_settings WHERE guild_id = ?', [guildId]));
    if (!s.enabled) return { ok: false, reason: 'disabled' };
    const amt = Math.trunc(Number(amount));
    if (!Number.isFinite(amt) || amt <= 0) return { ok: false, reason: 'bad_amount' };
    if (String(fromId) === String(toId)) return { ok: false, reason: 'self' };
    await ensureEconomyUserRow(guildId, fromId, s.start_balance);
    await ensureEconomyUserRow(guildId, toId, s.start_balance);
    const from = await dbGet('SELECT balance FROM guild_economy_users WHERE guild_id = ? AND user_id = ?', [guildId, String(fromId)]);
    if ((from?.balance || 0) < amt) return { ok: false, reason: 'insufficient', balance: from?.balance || 0, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
    await runStmt('UPDATE guild_economy_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ?', [amt, guildId, String(fromId)]);
    await runStmt('UPDATE guild_economy_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?', [amt, guildId, String(toId)]);
    const updated = await dbGet('SELECT balance FROM guild_economy_users WHERE guild_id = ? AND user_id = ?', [guildId, String(fromId)]);
    return { ok: true, amount: amt, balance: updated?.balance || 0, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
  });
}

export function getEconomyLeaderboard(guildId, limit = 25) {
  const lim = clampRange(limit, 1, 100, 25);
  return new Promise((resolve, reject) => {
    db.all('SELECT user_id, balance FROM guild_economy_users WHERE guild_id = ? AND balance > 0 ORDER BY balance DESC LIMIT ?', [guildId, lim], (err, rows) => {
      if (err) reject(err); else resolve((rows || []).map((r, i) => ({ user_id: r.user_id, balance: r.balance, rank: i + 1 })));
    });
  });
}

function shapeShopItem(row) {
  if (!row) return null;
  return { id: row.id, name: row.name ?? '', description: row.description ?? '', price: row.price || 0, role_id: row.role_id ?? null, position: row.position || 0, enabled: !!row.enabled };
}

export function getEconomyShop(guildId, onlyEnabled = false) {
  const where = onlyEnabled ? ' AND enabled = 1' : '';
  return new Promise((resolve, reject) => {
    db.all(`SELECT * FROM guild_economy_shop WHERE guild_id = ?${where} ORDER BY position ASC, created_at ASC`, [guildId], (err, rows) => {
      if (err) reject(err); else resolve((rows || []).map(shapeShopItem));
    });
  });
}

function coerceShopItem(data) {
  return {
    name: truncate(data.name ?? '', 100),
    description: truncate(data.description ?? '', 300),
    price: clampRange(data.price, 0, 1000000000, 0),
    role_id: isSnowflake(data.role_id) ? data.role_id : null,
    position: clampRange(data.position, 0, 1000, 0),
    enabled: data.enabled === false ? 0 : 1
  };
}

export function createShopItem(guildId, data) {
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const it = coerceShopItem(data);
    db.run('INSERT INTO guild_economy_shop (id, guild_id, name, description, price, role_id, position, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      [id, guildId, it.name, it.description, it.price, it.role_id, it.position, it.enabled],
      (err) => { if (err) reject(err); else resolve({ id, ...it, enabled: !!it.enabled }); });
  });
}

export function updateShopItem(guildId, itemId, data) {
  return new Promise((resolve, reject) => {
    const it = coerceShopItem(data);
    db.run('UPDATE guild_economy_shop SET name = ?, description = ?, price = ?, role_id = ?, position = ?, enabled = ? WHERE guild_id = ? AND id = ?',
      [it.name, it.description, it.price, it.role_id, it.position, it.enabled, guildId, itemId],
      function (err) {
        if (err) return reject(err);
        if (this.changes === 0) { const e = new Error('Item not found'); e.code = 'NOT_FOUND'; return reject(e); }
        resolve({ id: itemId, ...it, enabled: !!it.enabled });
      });
  });
}

export function deleteShopItem(guildId, itemId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_economy_shop WHERE guild_id = ? AND id = ?', [guildId, itemId], function (err) { if (err) reject(err); else resolve(this.changes); });
  });
}

export function economyBuy(guildId, userId, itemId) {
  return runInTransaction(async () => {
    const s = shapeEconomy(await dbGet('SELECT * FROM guild_economy_settings WHERE guild_id = ?', [guildId]));
    if (!s.enabled) return { ok: false, reason: 'disabled' };
    const item = shapeShopItem(await dbGet('SELECT * FROM guild_economy_shop WHERE guild_id = ? AND id = ? AND enabled = 1', [guildId, itemId]));
    if (!item) return { ok: false, reason: 'not_found' };
    await ensureEconomyUserRow(guildId, userId, s.start_balance);
    const u = await dbGet('SELECT balance FROM guild_economy_users WHERE guild_id = ? AND user_id = ?', [guildId, String(userId)]);
    if ((u?.balance || 0) < item.price) return { ok: false, reason: 'insufficient', balance: u?.balance || 0, price: item.price, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
    const balance = (u.balance || 0) - item.price;
    await runStmt('UPDATE guild_economy_users SET balance = ? WHERE guild_id = ? AND user_id = ?', [balance, guildId, String(userId)]);
    return { ok: true, item, balance, role_id: item.role_id, currency_name: s.currency_name, currency_symbol: s.currency_symbol };
  });
}

// ----- Games category (v28) -----

export const GAME_KEYS = ['tictactoe', 'rps', 'trivia', 'connect4', 'hangman', 'poker'];

/** Valid Poker table render themes (felt design). Source of truth shared with the bot + dashboard picker. */
export const POKER_THEMES = ['classic', 'midnight', 'crimson', 'charcoal', 'royal'];

/** Valid game languages (shared across the whole Games category). Source of truth shared with the bot + dashboard picker. */
export const GAME_LANGUAGES = ['en', 'de', 'tr', 'ru', 'pl'];

export const GAMES_DEFAULTS = {
  games_channel_id: null,
  tictactoe_enabled: false,
  rps_enabled: false,
  trivia_enabled: false,
  connect4_enabled: false,
  hangman_enabled: false,
  poker_enabled: false,
  poker_table_theme: 'classic',
  games_language: 'en'
};

function shapeGames(row) {
  if (!row) return { ...GAMES_DEFAULTS };
  return {
    games_channel_id: row.games_channel_id ?? null,
    tictactoe_enabled: !!row.tictactoe_enabled,
    rps_enabled: !!row.rps_enabled,
    trivia_enabled: !!row.trivia_enabled,
    connect4_enabled: !!row.connect4_enabled,
    hangman_enabled: !!row.hangman_enabled,
    poker_enabled: !!row.poker_enabled,
    poker_table_theme: POKER_THEMES.includes(row.poker_table_theme) ? row.poker_table_theme : 'classic',
    games_language: GAME_LANGUAGES.includes(row.games_language) ? row.games_language : 'en'
  };
}

export function getGamesSettings(guildId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_games_settings WHERE guild_id = ?', [guildId], (err, row) => {
      if (err) reject(err); else resolve(shapeGames(row));
    });
  });
}

/** Partial-merge upsert: only keys present in `settings` overwrite the row. */
export function upsertGamesSettings(guildId, settings) {
  return runInTransaction(async () => {
    const current = shapeGames(await dbGet('SELECT * FROM guild_games_settings WHERE guild_id = ?', [guildId]));
    const next = { ...current };
    if ('games_channel_id' in settings) next.games_channel_id = isSnowflake(settings.games_channel_id) ? settings.games_channel_id : null;
    for (const key of GAME_KEYS) {
      const flag = `${key}_enabled`;
      if (flag in settings) next[flag] = settings[flag] ? 1 : 0;
    }
    if ('poker_table_theme' in settings) {
      next.poker_table_theme = POKER_THEMES.includes(settings.poker_table_theme) ? settings.poker_table_theme : 'classic';
    }
    if ('games_language' in settings) {
      next.games_language = GAME_LANGUAGES.includes(settings.games_language) ? settings.games_language : 'en';
    }
    await runStmt(
      `INSERT INTO guild_games_settings (guild_id, games_channel_id, tictactoe_enabled, rps_enabled, trivia_enabled, connect4_enabled, hangman_enabled, poker_enabled, poker_table_theme, games_language)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(guild_id) DO UPDATE SET
         games_channel_id = excluded.games_channel_id,
         tictactoe_enabled = excluded.tictactoe_enabled,
         rps_enabled = excluded.rps_enabled,
         trivia_enabled = excluded.trivia_enabled,
         connect4_enabled = excluded.connect4_enabled,
         hangman_enabled = excluded.hangman_enabled,
         poker_enabled = excluded.poker_enabled,
         poker_table_theme = excluded.poker_table_theme,
         games_language = excluded.games_language,
         updated_at = CURRENT_TIMESTAMP`,
      [guildId, next.games_channel_id,
        next.tictactoe_enabled ? 1 : 0, next.rps_enabled ? 1 : 0, next.trivia_enabled ? 1 : 0,
        next.connect4_enabled ? 1 : 0, next.hangman_enabled ? 1 : 0, next.poker_enabled ? 1 : 0,
        next.poker_table_theme, next.games_language]
    );
    return shapeGames(await dbGet('SELECT * FROM guild_games_settings WHERE guild_id = ?', [guildId]));
  });
}

/** Bot: record a game result (plays +1, wins +1 on a win). */
export function recordGameScore(guildId, userId, game, win) {
  if (!GAME_KEYS.includes(game)) { return Promise.reject(Object.assign(new Error('unknown game'), { code: 'VALIDATION' })); }
  return runStmt(
    `INSERT INTO guild_game_scores (guild_id, user_id, game, wins, plays)
     VALUES (?, ?, ?, ?, 1)
     ON CONFLICT(guild_id, user_id, game) DO UPDATE SET
       wins = wins + ?, plays = plays + 1`,
    [guildId, String(userId), game, win ? 1 : 0, win ? 1 : 0]
  );
}

export function getGameLeaderboard(guildId, game, limit = 25) {
  const lim = clampRange(limit, 1, 100, 25);
  const g = GAME_KEYS.includes(game) ? game : GAME_KEYS[0];
  return new Promise((resolve, reject) => {
    db.all(
      'SELECT user_id, wins, plays FROM guild_game_scores WHERE guild_id = ? AND game = ? AND plays > 0 ORDER BY wins DESC, plays ASC LIMIT ?',
      [guildId, g, lim],
      (err, rows) => { if (err) reject(err); else resolve((rows || []).map((r, i) => ({ user_id: r.user_id, wins: r.wins, plays: r.plays, rank: i + 1 }))); }
    );
  });
}

export const MODULE_DEFAULTS = {
  autorole: AUTOROLE_DEFAULTS,
  logs: LOG_DEFAULTS,
  moderation: MODERATION_DEFAULTS,
  welcome_leave: WELCOME_LEAVE_DEFAULTS,
  leveling: LEVELING_DEFAULTS,
  social: SOCIAL_DEFAULTS,
  stats: STATS_DEFAULTS,
  tempvoice: TEMPVOICE_DEFAULTS,
  starboard: STARBOARD_DEFAULTS,
  suggestions: SUGGESTION_DEFAULTS,
  birthday: BIRTHDAY_DEFAULTS,
  scheduled: { messages: [] },
  antiraid: ANTIRAID_DEFAULTS,
  verification: VERIFICATION_DEFAULTS,
  rolemenus: { menus: [] },
  tickets: TICKET_DEFAULTS,
  giveaways: { giveaways: [] },
  counting: COUNTING_DEFAULTS,
  polls: { polls: [] },
  invitetracking: INVITE_DEFAULTS,
  applications: { forms: [] },
  economy: ECONOMY_DEFAULTS,
  games: GAMES_DEFAULTS
};

// ============================================================
// Server Backup & Restore (v32) — snapshots + async job queue
// ============================================================

export const BACKUP_JOB_TYPES = ['snapshot', 'restore'];
export const BACKUP_JOB_STATUSES = ['pending', 'running', 'done', 'failed'];
export const RESTORE_MODES = ['missing', 'mirror'];
export const RESTORE_PARTS = ['roles', 'channels', 'server_name', 'server_icon'];
export const BACKUP_MAX_PER_GUILD = 15;

function backupNowSeconds() { return Math.floor(Date.now() / 1000); }

/**
 * Normalize a restore "parts" selection (which pieces to restore). Accepts a
 * partial object of booleans; returns `{roles,channels,server_name,server_icon}`.
 * Missing/empty input → all true (full restore, backward compatible).
 */
function sanitizeBackupParts(parts) {
  if (!parts || typeof parts !== 'object') return null; // null = all parts
  const out = {};
  let anyTrue = false;
  for (const key of RESTORE_PARTS) {
    out[key] = !!parts[key];
    if (out[key]) anyTrue = true;
  }
  if (!anyTrue) return null; // nothing selected → treat as full restore
  return out;
}

/** Parse the stored parts JSON; null/invalid → null (= all parts). */
function parseBackupParts(raw) {
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw);
    return sanitizeBackupParts(obj);
  } catch { return null; }
}

/** Count channels/roles inside a snapshot data blob (best-effort). */
function backupCounts(data) {
  let channels = 0, roles = 0;
  try {
    const obj = typeof data === 'string' ? JSON.parse(data) : (data || {});
    if (Array.isArray(obj.channels)) channels = obj.channels.length;
    if (Array.isArray(obj.roles)) roles = obj.roles.length;
  } catch { /* ignore malformed */ }
  return { channels, roles };
}

/** Snapshot row → dashboard list shape (no data blob). */
function shapeBackupMeta(row) {
  if (!row) return null;
  return {
    id: row.id,
    name: row.name || '',
    guild_name: row.guild_name || '',
    guild_icon_url: row.guild_icon_url || '',
    channels_count: row.channels_count || 0,
    roles_count: row.roles_count || 0,
    created_at: row.created_at || 0
  };
}

function shapeBackupJob(row) {
  if (!row) return null;
  return {
    id: row.id,
    type: row.type,
    status: row.status,
    backup_id: row.backup_id || null,
    mode: row.mode || null,
    parts: parseBackupParts(row.parts),
    message: row.message || null,
    created_at: row.created_at || 0,
    updated_at: row.updated_at || 0
  };
}

/** Bot: store a snapshot the bot just captured. Trims to BACKUP_MAX_PER_GUILD. */
export function createBackup(guildId, { name, guild_name, guild_icon_url, data } = {}) {
  return runInTransaction(async () => {
    const id = randomUUID();
    const now = backupNowSeconds();
    const dataStr = typeof data === 'string' ? data : JSON.stringify(data || {});
    const { channels, roles } = backupCounts(dataStr);
    const cleanName = (name && String(name).trim()) ? String(name).trim().slice(0, 120) : `Snapshot ${new Date(now * 1000).toISOString().slice(0, 16).replace('T', ' ')}`;
    await runStmt(
      `INSERT INTO guild_backups (id, guild_id, name, guild_name, guild_icon_url, channels_count, roles_count, data, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, guildId, cleanName, guild_name || null, guild_icon_url || null, channels, roles, dataStr, now]
    );
    // Retention: keep only the newest BACKUP_MAX_PER_GUILD snapshots.
    await runStmt(
      `DELETE FROM guild_backups WHERE guild_id = ? AND id NOT IN (
         SELECT id FROM guild_backups WHERE guild_id = ? ORDER BY created_at DESC, id DESC LIMIT ?
       )`,
      [guildId, guildId, BACKUP_MAX_PER_GUILD]
    );
    return shapeBackupMeta(await dbGet('SELECT * FROM guild_backups WHERE id = ?', [id]));
  });
}

/** Dashboard: snapshot metadata list (no data blob). */
export function getBackups(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      'SELECT id, guild_id, name, guild_name, guild_icon_url, channels_count, roles_count, created_at FROM guild_backups WHERE guild_id = ? ORDER BY created_at DESC, id DESC',
      [guildId],
      (err, rows) => { if (err) reject(err); else resolve((rows || []).map(shapeBackupMeta)); }
    );
  });
}

/** Full snapshot incl. parsed data blob. */
export function getBackup(guildId, backupId) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_backups WHERE guild_id = ? AND id = ?', [guildId, backupId], (err, row) => {
      if (err) return reject(err);
      if (!row) return resolve(null);
      let data = {};
      try { data = JSON.parse(row.data || '{}'); } catch { data = {}; }
      resolve({ ...shapeBackupMeta(row), data });
    });
  });
}

export function deleteBackup(guildId, backupId) {
  return new Promise((resolve, reject) => {
    db.run('DELETE FROM guild_backups WHERE guild_id = ? AND id = ?', [guildId, backupId], function (err) {
      if (err) reject(err);
      else resolve(this.changes);
    });
  });
}

/** Dashboard: enqueue a snapshot/restore job. */
export function createBackupJob(guildId, { type, backup_id = null, mode = null, parts = null } = {}) {
  if (!BACKUP_JOB_TYPES.includes(type)) {
    return Promise.reject(Object.assign(new Error('invalid job type'), { code: 'VALIDATION' }));
  }
  const safeMode = type === 'restore' ? (RESTORE_MODES.includes(mode) ? mode : 'missing') : null;
  const safeParts = type === 'restore' ? sanitizeBackupParts(parts) : null;
  return new Promise((resolve, reject) => {
    const id = randomUUID();
    const now = backupNowSeconds();
    db.run(
      `INSERT INTO guild_backup_jobs (id, guild_id, type, status, backup_id, mode, parts, created_at, updated_at)
       VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)`,
      [id, guildId, type, backup_id, safeMode, safeParts ? JSON.stringify(safeParts) : null, now, now],
      function (err) {
        if (err) return reject(err);
        db.get('SELECT * FROM guild_backup_jobs WHERE id = ?', [id], (gErr, row) => {
          if (gErr) reject(gErr); else resolve(shapeBackupJob(row));
        });
      }
    );
  });
}

/** Dashboard: jobs still pending/running for this guild (progress polling). */
export function getActiveBackupJobs(guildId) {
  return new Promise((resolve, reject) => {
    db.all(
      "SELECT * FROM guild_backup_jobs WHERE guild_id = ? AND status IN ('pending', 'running') ORDER BY created_at ASC",
      [guildId],
      (err, rows) => { if (err) reject(err); else resolve((rows || []).map(shapeBackupJob)); }
    );
  });
}

/**
 * Bot: pending jobs across all guilds (skips blocked guilds + non-pro tiers, so a
 * downgrade/lapsed-Premium guild stops getting snapshot/restore work). Restore
 * jobs embed the source snapshot's parsed data so the bot needs only one call.
 */
export function getDueBackupJobs() {
  return new Promise((resolve, reject) => {
    db.all(
      `SELECT j.*, b.data AS backup_data, b.guild_name AS backup_guild_name
         FROM guild_backup_jobs j
         LEFT JOIN guild_backups b ON b.id = j.backup_id
        WHERE j.status = 'pending'
          AND j.guild_id NOT IN (SELECT id FROM guilds WHERE blocked = 1)
          AND ${tierFilterSql('pro', 'j.guild_id')}
        ORDER BY j.created_at ASC`,
      [],
      (err, rows) => {
        if (err) return reject(err);
        const jobs = (rows || []).map((row) => {
          const job = shapeBackupJob(row);
          job.guild_id = row.guild_id;
          if (job.type === 'restore') {
            let data = null;
            try { data = row.backup_data ? JSON.parse(row.backup_data) : null; } catch { data = null; }
            job.data = data;
          }
          return job;
        });
        resolve(jobs);
      }
    );
  });
}

/** Bot: report job progress/result. */
export function updateBackupJob(jobId, { status, backup_id, message } = {}) {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM guild_backup_jobs WHERE id = ?', [jobId], (gErr, row) => {
      if (gErr) return reject(gErr);
      if (!row) return resolve(0);
      const nextStatus = BACKUP_JOB_STATUSES.includes(status) ? status : row.status;
      const nextBackup = backup_id !== undefined ? backup_id : row.backup_id;
      const nextMessage = message !== undefined ? (message == null ? null : String(message).slice(0, 2000)) : row.message;
      db.run(
        'UPDATE guild_backup_jobs SET status = ?, backup_id = ?, message = ?, updated_at = ? WHERE id = ?',
        [nextStatus, nextBackup, nextMessage, backupNowSeconds(), jobId],
        function (err) { if (err) reject(err); else resolve(this.changes); }
      );
    });
  });
}

/**
 * Close database connection
 */
export function closeDb() {
  return new Promise((resolve, reject) => {
    db.close((err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}
