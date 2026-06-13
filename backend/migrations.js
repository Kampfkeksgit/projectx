import { db } from './db.js';

/**
 * Schema version tracking
 * Allows for future database migrations
 */
const CURRENT_SCHEMA_VERSION = 21;

/**
 * Initialize schema version tracking
 */
export function initializeSchemaVersion() {
  return new Promise((resolve, reject) => {
    db.run(
      `CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )`,
      (err) => {
        // Just ensure the schema_version table exists. server.js calls
        // checkAndApplyMigrations() exactly once after this — calling it here
        // too caused two concurrent migration runs (race → corrupt upgrades).
        if (err) reject(err);
        else resolve();
      }
    );
  });
}

/**
 * Check current schema version and apply necessary migrations
 */
export function checkAndApplyMigrations() {
  return new Promise((resolve, reject) => {
    db.get('SELECT version FROM schema_version ORDER BY version DESC LIMIT 1', (err, row) => {
      if (err) {
        reject(err);
        return;
      }

      const currentVersion = row?.version || 0;

      if (currentVersion < CURRENT_SCHEMA_VERSION) {
        console.log(`Database schema version is ${currentVersion}, upgrading to ${CURRENT_SCHEMA_VERSION}`);
        applyMigrations(currentVersion + 1, CURRENT_SCHEMA_VERSION)
          .then(() => resolve())
          .catch(reject);
      } else {
        console.log(`Database schema is up to date (v${CURRENT_SCHEMA_VERSION})`);
        resolve();
      }
    });
  });
}

/**
 * Apply migrations between versions — SEQUENTIALLY. Each migration must finish
 * before the next starts; running them concurrently let e.g. migrationV2
 * (ALTER users) fire before migrationV1's table existed → "no such table".
 */
async function applyMigrations(fromVersion, toVersion) {
  const migrations = {
    1: migrationV1,
    2: migrationV2,
    3: migrationV3,
    4: migrationV4,
    5: migrationV5,
    6: migrationV6,
    7: migrationV7,
    8: migrationV8,
    9: migrationV9,
    10: migrationV10,
    11: migrationV11,
    12: migrationV12,
    13: migrationV13,
    14: migrationV14,
    15: migrationV15,
    16: migrationV16,
    17: migrationV17,
    18: migrationV18,
    19: migrationV19,
    20: migrationV20,
    21: migrationV21
  };

  for (let v = fromVersion; v <= toVersion; v++) {
    if (migrations[v]) {
      await migrations[v]();
    }
  }
}

/**
 * Migration V1: Initial schema (already created in db.js)
 */
function migrationV1() {
  return new Promise((resolve, reject) => {
    db.run(
      'INSERT OR IGNORE INTO schema_version (version) VALUES (1)',
      (err) => {
        if (err) reject(err);
        else {
          console.log('✓ Migration V1 applied');
          resolve();
        }
      }
    );
  });
}

/**
 * Migration V2: Add token_expires_at column to users (unix seconds when the
 * Discord access_token expires). Safe to re-run — ignore "duplicate column" errors.
 */
function migrationV2() {
  return new Promise((resolve, reject) => {
    db.run('ALTER TABLE users ADD COLUMN token_expires_at INTEGER', (alterErr) => {
      // SQLite returns an error if the column already exists. That's fine.
      if (alterErr && !/duplicate column name/i.test(alterErr.message)) {
        reject(alterErr);
        return;
      }
      db.run(
        'INSERT OR IGNORE INTO schema_version (version) VALUES (2)',
        (err) => {
          if (err) reject(err);
          else {
            console.log('✓ Migration V2 applied');
            resolve();
          }
        }
      );
    });
  });
}

/**
 * Migration V3: Add tables for Auto-Role, Server-Logs, and Moderation modules.
 *   - guild_autorole_settings: roles auto-assigned on member join.
 *   - guild_log_settings: per-event flags + channel for server logs.
 *   - guild_moderation_settings: anti-spam + banned-words filter.
 * All tables are keyed on guild_id (FK guilds(id) ON DELETE CASCADE).
 * Safe to re-run: CREATE TABLE IF NOT EXISTS.
 */
function migrationV3() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      let pending = 3;
      let failed = false;

      const done = (err, label) => {
        if (failed) return;
        if (err) {
          failed = true;
          reject(err);
          return;
        }
        console.log(`✓ Migration V3: ${label} created`);
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (3)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V3 applied');
                resolve();
              }
            }
          );
        }
      };

      db.run(
        `CREATE TABLE IF NOT EXISTS guild_autorole_settings (
          guild_id TEXT PRIMARY KEY,
          enabled BOOLEAN DEFAULT 0,
          role_ids TEXT DEFAULT '[]',
          apply_to_bots BOOLEAN DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        (err) => done(err, 'guild_autorole_settings')
      );

      db.run(
        `CREATE TABLE IF NOT EXISTS guild_log_settings (
          guild_id TEXT PRIMARY KEY,
          enabled BOOLEAN DEFAULT 0,
          log_channel_id TEXT,
          log_joins BOOLEAN DEFAULT 1,
          log_leaves BOOLEAN DEFAULT 1,
          log_message_edits BOOLEAN DEFAULT 0,
          log_message_deletes BOOLEAN DEFAULT 0,
          log_member_bans BOOLEAN DEFAULT 1,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        (err) => done(err, 'guild_log_settings')
      );

      db.run(
        `CREATE TABLE IF NOT EXISTS guild_moderation_settings (
          guild_id TEXT PRIMARY KEY,
          enabled BOOLEAN DEFAULT 0,
          anti_spam_enabled BOOLEAN DEFAULT 0,
          max_messages_per_10s INTEGER DEFAULT 5,
          banned_words TEXT DEFAULT '[]',
          banned_word_action TEXT DEFAULT 'delete',
          mute_role_id TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        (err) => done(err, 'guild_moderation_settings')
      );
    });
  });
}

/**
 * Migration V4: Add bot_present flag to guilds. The bot syncs its current
 * membership list via PUT /api/bot/presence on startup, on guild join/leave
 * events, and every 5 minutes — the frontend uses this flag to show "Invite"
 * vs. "Configure" buttons on the overview.
 * Safe to re-run — ignore "duplicate column" errors.
 */
function migrationV4() {
  return new Promise((resolve, reject) => {
    db.run('ALTER TABLE guilds ADD COLUMN bot_present BOOLEAN DEFAULT 0', (alterErr) => {
      if (alterErr && !/duplicate column name/i.test(alterErr.message)) {
        reject(alterErr);
        return;
      }
      db.run(
        'INSERT OR IGNORE INTO schema_version (version) VALUES (4)',
        (err) => {
          if (err) reject(err);
          else {
            console.log('✓ Migration V4 applied');
            resolve();
          }
        }
      );
    });
  });
}

/**
 * Migration V5: Extend guild_settings with rich-embed, DM-on-join, auto-delete,
 * ping-user fields for the Welcome/Leave module. All ALTERs are idempotent —
 * "duplicate column name" errors are swallowed so the migration can re-run
 * safely on partially-upgraded DBs.
 */
function migrationV5() {
  return new Promise((resolve, reject) => {
    const alters = [
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

    db.serialize(() => {
      let pending = alters.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (5)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V5 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of alters) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V6: Add tables for guild channel/role sync. The bot syncs the
 * per-guild list of text/voice/etc. channels and roles to these tables so the
 * dashboard can render dropdowns instead of raw-ID inputs.
 *   - guild_channels: one row per Discord channel (categories, text, voice,
 *     announcement, forum, stage, thread).
 *   - guild_roles: one row per Discord role (incl. @everyone, flagged via
 *     is_default so the read path can filter it out by default).
 * Both keyed by Discord snowflake (TEXT PRIMARY KEY) with FK to guilds(id)
 * ON DELETE CASCADE. Safe to re-run: CREATE TABLE/INDEX IF NOT EXISTS.
 */
function migrationV6() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_channels (
          id          TEXT PRIMARY KEY,
          guild_id    TEXT NOT NULL,
          name        TEXT NOT NULL,
          type        TEXT NOT NULL,
          parent_id   TEXT,
          position    INTEGER DEFAULT 0,
          updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_guild_channels_guild ON guild_channels(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_roles (
          id          TEXT PRIMARY KEY,
          guild_id    TEXT NOT NULL,
          name        TEXT NOT NULL,
          color       INTEGER DEFAULT 0,
          position    INTEGER DEFAULT 0,
          managed     BOOLEAN DEFAULT 0,
          is_default  BOOLEAN DEFAULT 0,
          updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_guild_roles_guild ON guild_roles(guild_id)`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (6)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V6 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V7: Add tables for Reaction Roles, Leveling/XP and Custom Commands.
 *   - guild_reaction_role_messages + guild_reaction_role_mappings: emoji-role
 *     bindings on a specific Discord message.
 *   - guild_leveling_settings + guild_leveling_users + guild_leveling_rewards:
 *     per-guild XP system, with per-level role rewards.
 *   - guild_custom_commands: simple text trigger → response commands.
 * Each `db.run` is wrapped so "already exists"-type errors are swallowed,
 * making the migration safe to re-run.
 */
function migrationV7() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        // ----- Reaction Roles -----
        `CREATE TABLE IF NOT EXISTS guild_reaction_role_messages (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_rr_guild ON guild_reaction_role_messages(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_reaction_role_mappings (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          rr_message_id TEXT NOT NULL,
          emoji         TEXT NOT NULL,
          role_id       TEXT NOT NULL,
          FOREIGN KEY (rr_message_id) REFERENCES guild_reaction_role_messages(id) ON DELETE CASCADE,
          UNIQUE(rr_message_id, emoji)
        )`,

        // ----- Leveling -----
        `CREATE TABLE IF NOT EXISTS guild_leveling_settings (
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
        )`,
        `CREATE TABLE IF NOT EXISTS guild_leveling_users (
          guild_id    TEXT NOT NULL,
          user_id     TEXT NOT NULL,
          xp          INTEGER DEFAULT 0,
          level       INTEGER DEFAULT 0,
          messages    INTEGER DEFAULT 0,
          last_xp_at  INTEGER DEFAULT 0,
          PRIMARY KEY (guild_id, user_id),
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_lvl_users_guild_xp ON guild_leveling_users(guild_id, xp DESC)`,
        `CREATE TABLE IF NOT EXISTS guild_leveling_rewards (
          id        INTEGER PRIMARY KEY AUTOINCREMENT,
          guild_id  TEXT NOT NULL,
          level     INTEGER NOT NULL,
          role_id   TEXT NOT NULL,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
          UNIQUE(guild_id, level, role_id)
        )`,

        // ----- Custom Commands -----
        `CREATE TABLE IF NOT EXISTS guild_custom_commands (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_cc_guild ON guild_custom_commands(guild_id)`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        // "already exists" / "duplicate column" are expected on re-runs.
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (7)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V7 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V8: Add the Social-Notifications module table.
 *   - guild_social_subscriptions: one row per tracked creator account
 *     (platform + account) per guild, with the Discord channel to announce in,
 *     per-account toggles (live / new upload), an optional custom message +
 *     embed, and bot-maintained polling state (last_video_id / last_live).
 * Keyed by UUID (TEXT PRIMARY KEY), FK to guilds(id) ON DELETE CASCADE.
 * UNIQUE(guild_id, platform, account) blocks duplicate tracking entries.
 * Safe to re-run: CREATE TABLE/INDEX IF NOT EXISTS.
 */
function migrationV8() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_social_subscriptions (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_social_subs_guild ON guild_social_subscriptions(guild_id)`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (8)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V8 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V9: Extend Moderation + Server-Logs modules.
 *   - guild_moderation_settings: anti-invite/link/mention/caps filters, a shared
 *     filter_action, native-timeout duration, warn-threshold escalation, and
 *     whitelist (exempt_role_ids / ignored_channel_ids).
 *   - guild_log_settings: member-update / unban / channel / role / voice events
 *     + log_ignored_channel_ids (channels excluded from message logging).
 *   - guild_moderation_warnings: persistent per-user warn counter for escalation.
 * All ALTERs are idempotent ("duplicate column name" swallowed); the warnings
 * table uses CREATE TABLE IF NOT EXISTS. Mirrored in initializeDatabase().
 */
function migrationV9() {
  return new Promise((resolve, reject) => {
    const alters = [
      // --- Moderation ---
      "ALTER TABLE guild_moderation_settings ADD COLUMN anti_invite BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_moderation_settings ADD COLUMN anti_link BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_moderation_settings ADD COLUMN filter_action TEXT DEFAULT 'delete'",
      "ALTER TABLE guild_moderation_settings ADD COLUMN anti_mention BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_moderation_settings ADD COLUMN max_mentions INTEGER DEFAULT 5",
      "ALTER TABLE guild_moderation_settings ADD COLUMN anti_caps BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_moderation_settings ADD COLUMN caps_percentage INTEGER DEFAULT 70",
      "ALTER TABLE guild_moderation_settings ADD COLUMN timeout_duration INTEGER DEFAULT 300",
      "ALTER TABLE guild_moderation_settings ADD COLUMN warn_threshold INTEGER DEFAULT 0",
      "ALTER TABLE guild_moderation_settings ADD COLUMN warn_escalation_action TEXT DEFAULT 'mute'",
      "ALTER TABLE guild_moderation_settings ADD COLUMN exempt_role_ids TEXT DEFAULT '[]'",
      "ALTER TABLE guild_moderation_settings ADD COLUMN ignored_channel_ids TEXT DEFAULT '[]'",
      // --- Server-Logs ---
      "ALTER TABLE guild_log_settings ADD COLUMN log_member_updates BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_log_settings ADD COLUMN log_member_unbans BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_log_settings ADD COLUMN log_channels BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_log_settings ADD COLUMN log_roles BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_log_settings ADD COLUMN log_voice BOOLEAN DEFAULT 0",
      "ALTER TABLE guild_log_settings ADD COLUMN log_ignored_channel_ids TEXT DEFAULT '[]'"
    ];

    db.serialize(() => {
      let pending = alters.length + 1; // +1 for the warnings table
      let failed = false;

      const done = (err, isAlter = true) => {
        if (failed) return;
        const tolerable = isAlter
          ? (err && /duplicate column name/i.test(err.message))
          : (err && /already exists/i.test(err.message));
        if (err && !tolerable) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (9)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V9 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of alters) {
        db.run(stmt, (err) => done(err, true));
      }

      db.run(
        `CREATE TABLE IF NOT EXISTS guild_moderation_warnings (
          guild_id    TEXT NOT NULL,
          user_id     TEXT NOT NULL,
          count       INTEGER DEFAULT 0,
          total       INTEGER DEFAULT 0,
          updated_at  INTEGER DEFAULT 0,
          PRIMARY KEY (guild_id, user_id),
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        (err) => done(err, false)
      );
    });
  });
}

/**
 * Migration V10: Add the Statistics module tables.
 *   - guild_stats_settings: per-guild module toggle + channel-rename interval.
 *   - guild_stats_counters: one row per stats channel (member/online/booster/…),
 *     either pointing at an existing channel or auto-created by the bot.
 *   - guild_stats_snapshots: periodic count snapshots powering the dashboard
 *     history graphs.
 * Each table FK to guilds(id) ON DELETE CASCADE. Safe to re-run:
 * CREATE TABLE/INDEX IF NOT EXISTS. Mirrored in initializeDatabase().
 */
function migrationV10() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_stats_settings (
          guild_id        TEXT PRIMARY KEY,
          enabled         BOOLEAN DEFAULT 0,
          update_interval INTEGER DEFAULT 10,
          updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE TABLE IF NOT EXISTS guild_stats_counters (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_stats_counters_guild ON guild_stats_counters(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_stats_snapshots (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_stats_snap_guild_ts ON guild_stats_snapshots(guild_id, ts)`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (10)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V10 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V11: Add the target-category columns to the Statistics module
 * settings, so stats channels can be grouped inside a category — either an
 * existing one the user picks (`category_id`) or one the bot auto-creates
 * (`auto_category` + `category_name`, with the bot writing the created id back
 * into `category_id`). All ALTERs are idempotent ("duplicate column name"
 * swallowed); mirrored in initializeDatabase().
 */
function migrationV11() {
  return new Promise((resolve, reject) => {
    const alters = [
      'ALTER TABLE guild_stats_settings ADD COLUMN category_id TEXT',
      'ALTER TABLE guild_stats_settings ADD COLUMN auto_category BOOLEAN DEFAULT 0',
      "ALTER TABLE guild_stats_settings ADD COLUMN category_name TEXT DEFAULT '📊 Statistics'"
    ];

    db.serialize(() => {
      let pending = alters.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (11)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V11 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of alters) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V12: Add tables for three new modules (Batch 1).
 *   - Temp-Voice (Join-to-Create): guild_tempvoice_settings + guild_tempvoice_channels
 *     (bot-managed list of live temp channels, for empty-cleanup across restarts).
 *   - Starboard: guild_starboard_settings + guild_starboard_entries
 *     (one row per starred source message → its posted starboard message + count).
 *   - Suggestions: guild_suggestion_settings (channel + up/down emojis).
 * All idempotent (CREATE TABLE/INDEX IF NOT EXISTS); mirrored in initializeDatabase().
 */
function migrationV12() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_tempvoice_settings (
          guild_id       TEXT PRIMARY KEY,
          enabled        BOOLEAN DEFAULT 0,
          hub_channel_id TEXT,
          category_id    TEXT,
          name_template  TEXT DEFAULT '🔊 {user}',
          user_limit     INTEGER DEFAULT 0,
          updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE TABLE IF NOT EXISTS guild_tempvoice_channels (
          channel_id  TEXT PRIMARY KEY,
          guild_id    TEXT NOT NULL,
          owner_id    TEXT,
          created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_tempvoice_channels_guild ON guild_tempvoice_channels(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_starboard_settings (
          guild_id        TEXT PRIMARY KEY,
          enabled         BOOLEAN DEFAULT 0,
          star_channel_id TEXT,
          emoji           TEXT DEFAULT '⭐',
          threshold       INTEGER DEFAULT 3,
          self_star       BOOLEAN DEFAULT 0,
          updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE TABLE IF NOT EXISTS guild_starboard_entries (
          guild_id        TEXT NOT NULL,
          message_id      TEXT NOT NULL,
          channel_id      TEXT,
          star_message_id TEXT,
          count           INTEGER DEFAULT 0,
          updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (guild_id, message_id),
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE TABLE IF NOT EXISTS guild_suggestion_settings (
          guild_id           TEXT PRIMARY KEY,
          enabled            BOOLEAN DEFAULT 0,
          suggest_channel_id TEXT,
          upvote_emoji       TEXT DEFAULT '👍',
          downvote_emoji     TEXT DEFAULT '👎',
          updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (12)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V12 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V13: Add tables for Batch 2 modules.
 *   - Birthday: guild_birthday_settings + guild_birthdays (per-member day/month).
 *   - Scheduled Announcements: guild_scheduled_messages (once / interval).
 *   - Anti-Raid: guild_antiraid_settings (join-rate + account-age gate).
 * All idempotent; mirrored in initializeDatabase().
 */
function migrationV13() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_birthday_settings (
          guild_id           TEXT PRIMARY KEY,
          enabled            BOOLEAN DEFAULT 0,
          announce_channel_id TEXT,
          message_template   TEXT DEFAULT '🎉 Happy Birthday {user}!',
          birthday_role_id   TEXT,
          updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE TABLE IF NOT EXISTS guild_birthdays (
          guild_id    TEXT NOT NULL,
          user_id     TEXT NOT NULL,
          month       INTEGER NOT NULL,
          day         INTEGER NOT NULL,
          year        INTEGER,
          created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (guild_id, user_id),
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_birthdays_md ON guild_birthdays(month, day)`,
        `CREATE TABLE IF NOT EXISTS guild_scheduled_messages (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_scheduled_guild ON guild_scheduled_messages(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_antiraid_settings (
          guild_id          TEXT PRIMARY KEY,
          enabled           BOOLEAN DEFAULT 0,
          join_rate_count   INTEGER DEFAULT 5,
          join_rate_seconds INTEGER DEFAULT 10,
          action            TEXT DEFAULT 'alert',
          account_age_days  INTEGER DEFAULT 0,
          alert_channel_id  TEXT,
          updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (13)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V13 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V14: Add tables for Batch 3 (Part A) modules.
 *   - Verification: guild_verification_settings (button-gated verified role).
 *   - Button/Select Role Menus: guild_role_menus + guild_role_menu_options.
 * (Slash-Utility-Commands need no tables.) All idempotent; mirrored in
 * initializeDatabase().
 */
function migrationV14() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_verification_settings (
          guild_id         TEXT PRIMARY KEY,
          enabled          BOOLEAN DEFAULT 0,
          channel_id       TEXT,
          verified_role_id TEXT,
          message          TEXT DEFAULT 'Click the button below to verify and unlock the server.',
          button_label     TEXT DEFAULT 'Verify',
          panel_message_id TEXT,
          updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE TABLE IF NOT EXISTS guild_role_menus (
          id          TEXT PRIMARY KEY,
          guild_id    TEXT NOT NULL,
          channel_id  TEXT,
          message_id  TEXT,
          name        TEXT,
          menu_type   TEXT DEFAULT 'buttons',
          created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_role_menus_guild ON guild_role_menus(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_role_menu_options (
          id        INTEGER PRIMARY KEY AUTOINCREMENT,
          menu_id   TEXT NOT NULL,
          role_id   TEXT NOT NULL,
          label     TEXT,
          emoji     TEXT,
          FOREIGN KEY (menu_id) REFERENCES guild_role_menus(id) ON DELETE CASCADE
        )`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (14)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V14 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V15: Add tables for Batch 3 (Part B) modules.
 *   - Tickets: guild_ticket_settings + guild_tickets (open/closed support channels).
 *   - Giveaways: guild_giveaways + guild_giveaway_entries (button-entry, timed draw).
 * All idempotent; mirrored in initializeDatabase().
 */
function migrationV15() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      const statements = [
        `CREATE TABLE IF NOT EXISTS guild_ticket_settings (
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
        )`,
        `CREATE TABLE IF NOT EXISTS guild_tickets (
          id          TEXT PRIMARY KEY,
          guild_id    TEXT NOT NULL,
          channel_id  TEXT,
          user_id     TEXT,
          status      TEXT DEFAULT 'open',
          created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        `CREATE INDEX IF NOT EXISTS idx_tickets_guild ON guild_tickets(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_giveaways (
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
        )`,
        `CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON guild_giveaways(guild_id)`,
        `CREATE TABLE IF NOT EXISTS guild_giveaway_entries (
          giveaway_id TEXT NOT NULL,
          user_id     TEXT NOT NULL,
          PRIMARY KEY (giveaway_id, user_id),
          FOREIGN KEY (giveaway_id) REFERENCES guild_giveaways(id) ON DELETE CASCADE
        )`
      ];

      let pending = statements.length;
      let failed = false;

      const done = (err) => {
        if (failed) return;
        if (err && !/already exists|duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run(
            'INSERT OR IGNORE INTO schema_version (version) VALUES (15)',
            (insertErr) => {
              if (insertErr) reject(insertErr);
              else {
                console.log('✓ Migration V15 applied');
                resolve();
              }
            }
          );
        }
      };

      for (const stmt of statements) {
        db.run(stmt, done);
      }
    });
  });
}

/**
 * Migration V16: Batch 3 enhancements.
 *   - guild_ticket_settings.transcript_channel_id: post a transcript here on close.
 *   - guild_role_menus.exclusive: a select menu where picking a role removes the
 *     other roles from that menu (mutually-exclusive choice).
 * Idempotent ALTERs ("duplicate column name" swallowed); mirrored in initializeDatabase().
 */
function migrationV16() {
  return new Promise((resolve, reject) => {
    const alters = [
      'ALTER TABLE guild_ticket_settings ADD COLUMN transcript_channel_id TEXT',
      'ALTER TABLE guild_role_menus ADD COLUMN exclusive BOOLEAN DEFAULT 0'
    ];
    db.serialize(() => {
      let pending = alters.length;
      let failed = false;
      const done = (err) => {
        if (failed) return;
        if (err && !/duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run('INSERT OR IGNORE INTO schema_version (version) VALUES (16)', (insertErr) => {
            if (insertErr) reject(insertErr);
            else {
              console.log('✓ Migration V16 applied');
              resolve();
            }
          });
        }
      };
      for (const stmt of alters) db.run(stmt, done);
    });
  });
}

/**
 * Migration V17: Owner-only admin moderation — add "blocked" flags so the
 * system owner can lock individual users and guilds out of the dashboard/bot.
 *   - users.blocked / blocked_reason / blocked_at: a blocked user can no longer
 *     authenticate or use any cookie-protected route (the owner is exempt).
 *   - guilds.blocked / blocked_reason / blocked_at: a blocked guild disappears
 *     from the server picker, its dashboard routes return 403, and the bot's
 *     /api/bot endpoints stop serving it so the bot goes inert there.
 * All ALTERs are idempotent ("duplicate column name" swallowed); mirrored in
 * initializeDatabase().
 */
function migrationV17() {
  return new Promise((resolve, reject) => {
    const alters = [
      'ALTER TABLE users ADD COLUMN blocked BOOLEAN DEFAULT 0',
      'ALTER TABLE users ADD COLUMN blocked_reason TEXT',
      'ALTER TABLE users ADD COLUMN blocked_at INTEGER',
      'ALTER TABLE guilds ADD COLUMN blocked BOOLEAN DEFAULT 0',
      'ALTER TABLE guilds ADD COLUMN blocked_reason TEXT',
      'ALTER TABLE guilds ADD COLUMN blocked_at INTEGER'
    ];
    db.serialize(() => {
      let pending = alters.length;
      let failed = false;
      const done = (err) => {
        if (failed) return;
        if (err && !/duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run('INSERT OR IGNORE INTO schema_version (version) VALUES (17)', (insertErr) => {
            if (insertErr) reject(insertErr);
            else {
              console.log('✓ Migration V17 applied');
              resolve();
            }
          });
        }
      };
      for (const stmt of alters) db.run(stmt, done);
    });
  });
}

/**
 * Migration V18: Ticket system overhaul.
 *   - guild_ticket_settings: panel_type (dropdown|buttons), panel_embed +
 *     welcome_embed (JSON), ping_role_id, naming_template, claim_enabled,
 *     close_confirm, rating_enabled, rating_mode (channel|dm|both), log_channel_id.
 *   - guild_ticket_categories (NEW): per-guild ticket types shown on the panel,
 *     each with its own label/emoji/description, optional Discord-category +
 *     support-role + ping-role overrides, welcome text, button style and order.
 *   - guild_tickets: ticket_category_id, number (per-guild counter), claimed_by,
 *     rating + rating_comment, closed_by + closed_at, extra_user_ids (JSON — users
 *     manually added to the ticket).
 * Idempotent ALTERs ("duplicate column name" swallowed) + CREATE IF NOT EXISTS;
 * mirrored in initializeDatabase().
 */
function migrationV18() {
  return new Promise((resolve, reject) => {
    const alters = [
      // --- settings ---
      "ALTER TABLE guild_ticket_settings ADD COLUMN panel_type TEXT DEFAULT 'dropdown'",
      'ALTER TABLE guild_ticket_settings ADD COLUMN panel_embed TEXT',
      'ALTER TABLE guild_ticket_settings ADD COLUMN welcome_embed TEXT',
      'ALTER TABLE guild_ticket_settings ADD COLUMN ping_role_id TEXT',
      "ALTER TABLE guild_ticket_settings ADD COLUMN naming_template TEXT DEFAULT 'ticket-{user}'",
      'ALTER TABLE guild_ticket_settings ADD COLUMN claim_enabled BOOLEAN DEFAULT 1',
      'ALTER TABLE guild_ticket_settings ADD COLUMN close_confirm BOOLEAN DEFAULT 1',
      'ALTER TABLE guild_ticket_settings ADD COLUMN rating_enabled BOOLEAN DEFAULT 0',
      "ALTER TABLE guild_ticket_settings ADD COLUMN rating_mode TEXT DEFAULT 'channel'",
      'ALTER TABLE guild_ticket_settings ADD COLUMN log_channel_id TEXT',
      // --- per-ticket state ---
      'ALTER TABLE guild_tickets ADD COLUMN ticket_category_id TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN number INTEGER DEFAULT 0',
      'ALTER TABLE guild_tickets ADD COLUMN claimed_by TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN rating INTEGER',
      'ALTER TABLE guild_tickets ADD COLUMN rating_comment TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN closed_by TEXT',
      'ALTER TABLE guild_tickets ADD COLUMN closed_at DATETIME',
      "ALTER TABLE guild_tickets ADD COLUMN extra_user_ids TEXT DEFAULT '[]'"
    ];

    db.serialize(() => {
      let pending = alters.length + 2; // +1 categories table, +1 index
      let failed = false;
      const done = (err, isAlter = true) => {
        if (failed) return;
        const tolerable = isAlter
          ? (err && /duplicate column name/i.test(err.message))
          : (err && /already exists/i.test(err.message));
        if (err && !tolerable) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run('INSERT OR IGNORE INTO schema_version (version) VALUES (18)', (insertErr) => {
            if (insertErr) reject(insertErr);
            else {
              console.log('✓ Migration V18 applied');
              resolve();
            }
          });
        }
      };

      for (const stmt of alters) db.run(stmt, (err) => done(err, true));

      db.run(
        `CREATE TABLE IF NOT EXISTS guild_ticket_categories (
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
        )`,
        (err) => done(err, false)
      );
      db.run('CREATE INDEX IF NOT EXISTS idx_ticket_categories_guild ON guild_ticket_categories(guild_id)', (err) => done(err, false));
    });
  });
}

/**
 * Migration V19: Command manager.
 *   - guilds.command_prefix: per-guild prefix for the bot's built-in prefix
 *     commands (default '!').
 *   - guild_command_settings (NEW): per-guild enable/disable override for each
 *     built-in command (only rows for toggled commands; absence = enabled).
 * Idempotent ALTER + CREATE IF NOT EXISTS; mirrored in initializeDatabase().
 */
function migrationV19() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      let pending = 2; // ALTER guilds + CREATE table
      let failed = false;
      const done = (err, isAlter) => {
        if (failed) return;
        const tolerable = isAlter
          ? (err && /duplicate column name/i.test(err.message))
          : (err && /already exists/i.test(err.message));
        if (err && !tolerable) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run('INSERT OR IGNORE INTO schema_version (version) VALUES (19)', (insertErr) => {
            if (insertErr) reject(insertErr);
            else {
              console.log('✓ Migration V19 applied');
              resolve();
            }
          });
        }
      };

      db.run("ALTER TABLE guilds ADD COLUMN command_prefix TEXT DEFAULT '!'", (err) => done(err, true));
      db.run(
        `CREATE TABLE IF NOT EXISTS guild_command_settings (
          guild_id    TEXT NOT NULL,
          command_key TEXT NOT NULL,
          enabled     BOOLEAN DEFAULT 1,
          PRIMARY KEY (guild_id, command_key),
          FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        )`,
        (err) => done(err, false)
      );
    });
  });
}

/**
 * Migration V20: Role-menu embed designer.
 *   - guild_role_menus.use_embed: when off, the bot keeps auto-building the embed
 *     from the menu name + option list (legacy behaviour). When on, the bot posts
 *     the custom embed below.
 *   - guild_role_menus.embed (JSON): the custom embed config (title/description/
 *     color/thumbnail/image/footer/timestamp/author), same shape as tickets.
 * Idempotent ALTERs ("duplicate column name" swallowed); mirrored in
 * initializeDatabase().
 */
function migrationV20() {
  return new Promise((resolve, reject) => {
    const alters = [
      'ALTER TABLE guild_role_menus ADD COLUMN use_embed BOOLEAN DEFAULT 0',
      'ALTER TABLE guild_role_menus ADD COLUMN embed TEXT'
    ];
    db.serialize(() => {
      let pending = alters.length;
      let failed = false;
      const done = (err) => {
        if (failed) return;
        if (err && !/duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run('INSERT OR IGNORE INTO schema_version (version) VALUES (20)', (insertErr) => {
            if (insertErr) reject(insertErr);
            else {
              console.log('✓ Migration V20 applied');
              resolve();
            }
          });
        }
      };
      for (const stmt of alters) db.run(stmt, done);
    });
  });
}

/**
 * Migration V21: Premium tiers (Free / Basic / Pro) for module gating.
 *   - guilds.premium_tier: effective tier ('free' default). Modules are unlocked
 *     when the guild tier rank >= the module's required tier (MODULE_TIERS in db.js).
 *   - guilds.premium_source: 'sku' (Discord entitlement) | 'manual' (owner-set) | null.
 *   - guilds.premium_until: unix-seconds expiry (null = no expiry). Past expiry =
 *     treated as 'free' by effectiveTier().
 * Idempotent ALTERs ("duplicate column name" swallowed); mirrored in
 * initializeDatabase().
 */
function migrationV21() {
  return new Promise((resolve, reject) => {
    const alters = [
      "ALTER TABLE guilds ADD COLUMN premium_tier TEXT DEFAULT 'free'",
      'ALTER TABLE guilds ADD COLUMN premium_source TEXT',
      'ALTER TABLE guilds ADD COLUMN premium_until INTEGER'
    ];
    db.serialize(() => {
      let pending = alters.length;
      let failed = false;
      const done = (err) => {
        if (failed) return;
        if (err && !/duplicate column name/i.test(err.message)) {
          failed = true;
          reject(err);
          return;
        }
        pending--;
        if (pending === 0) {
          db.run('INSERT OR IGNORE INTO schema_version (version) VALUES (21)', (insertErr) => {
            if (insertErr) reject(insertErr);
            else {
              console.log('✓ Migration V21 applied');
              resolve();
            }
          });
        }
      };
      for (const stmt of alters) db.run(stmt, done);
    });
  });
}

/**
 * Seed initial data for development/testing
 */
export function seedDatabase() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      // Check if data already seeded
      db.get('SELECT COUNT(*) as count FROM guilds', (err, row) => {
        if (err) {
          reject(err);
          return;
        }

        // Only seed if no guilds exist
        if (row.count === 0) {
          console.log('Seeding database with sample data...');

          // Create sample guild
          db.run(
            `INSERT INTO guilds (id, guild_name, guild_icon_url, enabled)
             VALUES (?, ?, ?, ?)`,
            ['123456789', 'Sample Guild', 'https://example.com/icon.png', 1],
            function(err) {
              if (err) {
                reject(err);
                return;
              }

              // Create sample user
              db.run(
                `INSERT INTO users (discord_id, username, email, avatar_url)
                 VALUES (?, ?, ?, ?)`,
                ['987654321', 'SampleUser', 'sample@example.com', 'https://example.com/avatar.png'],
                function(err) {
                  if (err) {
                    reject(err);
                    return;
                  }

                  // Link user to guild as owner
                  db.run(
                    `INSERT INTO user_guilds (user_id, guild_id, owner, admin)
                     VALUES (?, ?, ?, ?)`,
                    ['987654321', '123456789', 1, 1],
                    function(err) {
                      if (err) {
                        reject(err);
                        return;
                      }

                      // Create guild settings
                      db.run(
                        `INSERT INTO guild_settings (guild_id, welcome_enabled, welcome_channel_id, welcome_message, leave_enabled, leave_channel_id, leave_message)
                         VALUES (?, ?, ?, ?, ?, ?, ?)`,
                        [
                          '123456789',
                          1,
                          '111111111',
                          'Welcome {user} to our server! 👋',
                          1,
                          '111111111',
                          '{user} has left the server 👋'
                        ],
                        function(err) {
                          if (err) {
                            reject(err);
                          } else {
                            console.log('✓ Sample data seeded successfully');
                            resolve();
                          }
                        }
                      );
                    }
                  );
                }
              );
            }
          );
        } else {
          console.log('Database already seeded, skipping seed operation');
          resolve();
        }
      });
    });
  });
}

/**
 * Clear all data (for testing)
 */
export function clearAllData() {
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      db.run('DELETE FROM audit_log', (err) => {
        if (err) reject(err);
      });
      db.run('DELETE FROM user_guilds', (err) => {
        if (err) reject(err);
      });
      db.run('DELETE FROM guild_settings', (err) => {
        if (err) reject(err);
      });
      db.run('DELETE FROM users', (err) => {
        if (err) reject(err);
      });
      db.run('DELETE FROM guilds', (err) => {
        if (err) reject(err);
        else {
          console.log('✓ All data cleared');
          resolve();
        }
      });
    });
  });
}

/**
 * Get database statistics
 */
export function getDbStats() {
  return new Promise((resolve, reject) => {
    const stats = {};
    let completed = 0;

    const tables = ['guilds', 'users', 'user_guilds', 'guild_settings', 'audit_log'];

    tables.forEach((table) => {
      db.get(`SELECT COUNT(*) as count FROM ${table}`, (err, row) => {
        if (err) {
          reject(err);
          return;
        }
        stats[table] = row.count;
        completed++;

        if (completed === tables.length) {
          resolve(stats);
        }
      });
    });
  });
}
