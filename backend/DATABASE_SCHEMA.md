# Datenbank-Schema — projectx

> Kompakte Referenz des Datenbank-Schemas. Autoritativ für die tatsächliche Struktur ist immer der Code in [db.js](db.js) und [migrations.js](migrations.js); ein Überblick liegt zusätzlich in [../CLAUDE.md](../CLAUDE.md) §8.

---

## 1. Engine & Connection

- **Engine:** SQLite3 (`sqlite3`-npm-Paket).
- **Datei:** Pfad aus der Umgebungsvariable `DATABASE_URL` (Default `./data/bot.db`).
- **Connection + Setup:** [db.js](db.js) — eine **einzige** Connection für den gesamten Backend-Prozess. `initializeDatabase()` erzeugt alle Tabellen idempotent (`CREATE TABLE IF NOT EXISTS`) plus defensive `ALTER`s für Alt-DBs.
- **DB-Ready-Signal:** `whenDbReady` (Promise) — wird aufgelöst, sobald die Connection steht.

---

## 2. Migrations-Versionierung

- Logik in [migrations.js](migrations.js).
- **`CURRENT_SCHEMA_VERSION = 40`** (Konstante in [migrations.js](migrations.js)).
- **Versionstabelle:** `schema_version (version PK, applied_at)`.
- Ablauf: `initializeSchemaVersion()` legt die Versionstabelle an → `checkAndApplyMigrations()` liest die höchste angewandte Version → `applyMigrations(from, to)` ruft die fehlenden `migrationVN`-Funktionen **sequenziell** auf (jede stempelt am Ende ihre Version via `INSERT OR IGNORE INTO schema_version`).
- v23–v40 nutzen den Helper `runSchemaBatch(version, statements)` (CREATE/ALTER-Batch + Stamp).
- Alle Migrationen sind **idempotent**: `CREATE TABLE/INDEX IF NOT EXISTS` und `ALTER`s schlucken „duplicate column name". Jede neue Tabelle/Spalte wird zusätzlich in `initializeDatabase()` gespiegelt, damit auch frische DBs ohne vollständigen Migrations-Run lauffähig sind.

### Bei Schema-Änderung
1. Neue `migrationVN` in [migrations.js](migrations.js) hinzufügen (idempotent halten).
2. `CURRENT_SCHEMA_VERSION` inkrementieren + in die `migrations`-Map eintragen.
3. Tabelle/Spalte in `initializeDatabase()` ([db.js](db.js)) spiegeln.
4. Diese Datei + [../CLAUDE.md](../CLAUDE.md) §8 aktualisieren.

---

## 3. Performance-Pragmas

Gesetzt in `initializeDatabase()` ([db.js](db.js)):

| Pragma | Wert | Grund |
|---|---|---|
| `foreign_keys` | `ON` | FK-Constraints (`ON DELETE CASCADE` an fast allen Modul-Tabellen). |
| `journal_mode` | `TRUNCATE` | **Bewusst NICHT WAL.** Das Repo liegt auf dem `X:`-Volume (nicht-Standard-FS). WALs `-shm`-mmap + Spezial-Locking scheitern dort → `SQLITE_IOERR: disk I/O error`. TRUNCATE ist ein Rollback-Journal mit reinem File-I/O und läuft überall. |
| `synchronous` | `NORMAL` | Balance zwischen Sicherheit und Schreib-Performance. |
| `busy_timeout` | `5000` | Wartet bis 5 s, statt sofort zu erroren, wenn die eine Connection kurz belegt ist. |

> Bulk-Writes laufen über die `runInTransaction`-Queue (siehe [DATABASE_FUNCTIONS.md](DATABASE_FUNCTIONS.md)), damit ein fsync pro Transaktion statt pro Row anfällt.

---

## 4. Tabellen-Referenz

Konvention: alle Spalten-Keys sind `snake_case`. Snowflake-IDs (Discord) sind `TEXT`. Boolean = `INTEGER` 0/1. Timestamps sind je nach Tabelle `DATETIME` (CURRENT_TIMESTAMP) oder `INTEGER` (unix-seconds). JSON-Spalten sind `TEXT` (im DB-Layer geparst/stringified).

### 4.1 Kern

| Tabelle | PK | Wichtige Spalten | Zweck |
|---|---|---|---|
| `users` | `discord_id` | `username`, `email`, `avatar_url`, `access_token`, `refresh_token`, `token_expires_at`, `blocked`/`blocked_reason`/`blocked_at`/`blocked_until` | Discord-User + OAuth-Tokens (verlassen den Backend-Prozess nie) + Owner-Sperre. |
| `guilds` | `id` | `guild_name`, `guild_icon_url`, `enabled`, `bot_present`, `premium_tier`/`premium_source`/`premium_until`/`premium_reminded_at`, `command_prefix`, `blocked`/`blocked_reason`/`blocked_at`/`blocked_until` | Discord-Server: Bot-Präsenz, Premium-Gating, per-Guild-Prefix, Owner-Sperre. |
| `user_guilds` | `id` (AUTOINCR), `UNIQUE(user_id, guild_id)` | `user_id`, `guild_id`, `owner`, `admin` | Many-to-Many User↔Guild + Owner-/Admin-Bits. |
| `guild_settings` | `id` (AUTOINCR), `UNIQUE(guild_id)` | Welcome/Leave: `*_enabled`/`*_channel_id`/`*_message`, `*_use_embed`, `*_embed` (JSON), `welcome_ping_user`, `welcome_dm_enabled`/`_message`, `*_delete_after` | Welcome-/Leave-Konfiguration pro Guild. |
| `audit_log` | `id` (AUTOINCR) | `user_id`, `guild_id`, `action`, `changes` (JSON), `created_at` | Änderungs-Trail (Admin-Audit-Viewer). |
| `schema_version` | `version` | `applied_at` | Migrations-Tracking. |
| `system_settings` | `key` | `value`, `updated_at` | Key/Value-Store (`maintenance`, `announcement`). |

### 4.2 Modul-Settings (Resource-Cache + Basis-Module)

| Tabelle | PK | Zweck |
|---|---|---|
| `guild_channels` | `id` (Snowflake) | Bot-Sync-Cache der Channels (Dashboard-Dropdowns); `type`, `parent_id`, `position`. Index `idx_guild_channels_guild`. |
| `guild_roles` | `id` (Snowflake) | Bot-Sync-Cache der Rollen; `color`, `position`, `managed`, `is_default`. Index `idx_guild_roles_guild`. |
| `guild_general_settings` | `guild_id` | Allgemeine Dashboard-Settings (Free, kein `enabled`): `language`, `timezone`, `embed_color`, `dashboard_theme`. |
| `guild_autorole_settings` | `guild_id` | Auto-Role: `enabled`, `role_ids` (JSON), `apply_to_bots`. |
| `guild_log_settings` | `guild_id` | Server-Logs: `enabled`, `log_channel_id`, 10 Event-Flags, `log_ignored_channel_ids` (JSON). |
| `guild_moderation_settings` | `guild_id` | Moderation: Anti-Spam, `banned_words` (JSON), Filter (Invite/Link/Mention/Caps), `*_action`, Timeout, Warn-Eskalation, `exempt_role_ids`/`ignored_channel_ids` (JSON). |
| `guild_moderation_warnings` | `(guild_id, user_id)` | Persistenter Warn-Zähler (`count`/`total`) für die Eskalation. |

### 4.3 Engagement & Community

| Tabelle | PK | Zweck |
|---|---|---|
| `guild_reaction_role_messages` | `id` (UUID), `UNIQUE(guild_id, message_id)` | Reaction-Role-Message + `exclusive`-Bit. Index `idx_rr_guild`. |
| `guild_reaction_role_mappings` | `id` (AUTOINCR), `UNIQUE(rr_message_id, emoji)` | Emoji↔Role-Mappings (FK CASCADE auf RR-Message). |
| `guild_leveling_settings` | `guild_id` | XP-Range, Cooldown, Channel, Template, `ignored_channel_ids`, `stack_role_rewards`. |
| `guild_leveling_users` | `(guild_id, user_id)` | `xp`, `level`, `messages`, `last_xp_at`. Index `idx_lvl_users_guild_xp` (Leaderboard). |
| `guild_leveling_rewards` | `id` (AUTOINCR) | `(level, role_id)`-Reward-Tupel pro Guild. |
| `guild_custom_commands` | `id` (AUTOINCR), `UNIQUE(guild_id, trigger)` | Custom-Befehle (`match_type ∈ exact|contains|starts_with`). Index `idx_cc_guild`. |
| `guild_command_settings` | `(guild_id, command_key)` | An/Aus-Override für Built-in-Befehle (Command-Manager; Abwesenheit = aktiviert). |
| `guild_social_subscriptions` | `id` (UUID), `UNIQUE(guild_id, platform, account)` | Social-Alerts (YouTube/Twitch/Kick/…) + bot-gepflegter Polling-State. Index `idx_social_subs_guild`. |
| `guild_stats_settings` | `guild_id` | Statistics: `enabled`, `update_interval`, `category_id`/`auto_category`/`category_name`. |
| `guild_stats_counters` | `id` (UUID) | Ein Stats-Channel pro Counter (`type`, `channel_kind`, `name_template`, `auto_create`, `position`). Index `idx_stats_counters_guild`. |
| `guild_stats_snapshots` | `id` (AUTOINCR) | Verlaufs-Snapshots (`ts`, members/humans/bots/online/offline/boosters; Retention 90 Tage). Index `idx_stats_snap_guild_ts`. |
| `guild_tempvoice_settings` | `guild_id` | Temp-Voice: Hub/Kategorie/Name/Limit + Steuerungspanel (`panel_enabled`, `panel_destination ∈ voice|dm|channel`, `panel_channel_id`). |
| `guild_tempvoice_channels` | `channel_id` | Bot-Tracking lebender Temp-Channels (`owner_id`). Index `idx_tempvoice_channels_guild`. |
| `guild_starboard_settings` | `guild_id` | `enabled`, `star_channel_id`, `emoji`, `threshold`, `self_star`. |
| `guild_starboard_entries` | `(guild_id, message_id)` | Quell-Message → gepostete Starboard-Message (`star_message_id`, `count`). |
| `guild_suggestion_settings` | `guild_id` | `enabled`, `suggest_channel_id`, `upvote_emoji`, `downvote_emoji`. |
| `guild_birthday_settings` | `guild_id` | `enabled`, `announce_channel_id`, `message_template`, `birthday_role_id`. |
| `guild_birthdays` | `(guild_id, user_id)` | `month`, `day`, `year` (nullable). Index `idx_birthdays_md`. |
| `guild_scheduled_messages` | `id` (UUID) | Geplante Nachrichten (`schedule_type ∈ once|interval`, `run_at`, `interval_seconds`, `last_run`). Index `idx_scheduled_guild`. |
| `guild_antiraid_settings` | `guild_id` | `join_rate_count`/`_seconds`, `action ∈ alert|kick|ban`, `account_age_days`, `alert_channel_id`. |
| `guild_verification_settings` | `guild_id` | Button-Verify: `channel_id`, `verified_role_id`, `message`, `button_label`, `panel_message_id`. |
| `guild_role_menus` | `id` (UUID) | Rollen-Menüs (`menu_type ∈ buttons|select`, `exclusive`, `use_embed`, `embed` JSON, `message_id`). Index `idx_role_menus_guild`. |
| `guild_role_menu_options` | `id` (AUTOINCR) | Menü-Optionen (`role_id`, `label`, `emoji`; FK CASCADE). |
| `guild_ticket_settings` | `guild_id` | Tickets: Panel/Kategorie/Support-Rolle, `panel_type`, `panel_embed`/`welcome_embed` (JSON), Rating (`rating_mode`), Claim, Log/Transcript. |
| `guild_ticket_categories` | `id` (UUID) | Ticket-Typen fürs Panel (Label/Emoji + Overrides, `button_style`, `position`). Index `idx_ticket_categories_guild`. |
| `guild_tickets` | `id` (UUID) | Offene/geschlossene Ticket-Channels (`status`, `number`, `claimed_by`, `rating`/`_comment`, `closed_by`/`_at`, `extra_user_ids` JSON). Index `idx_tickets_guild`. |
| `guild_giveaways` | `id` (UUID) | `prize`, `winners_count`, `ends_at`, `ended`. Index `idx_giveaways_guild`. |
| `guild_giveaway_entries` | `(giveaway_id, user_id)` | Teilnahme-Einträge (FK CASCADE). |
| `guild_counting_settings` | `guild_id` | Counting: `channel_id`, `current_count`, `last_user_id`, `high_score`, `reset_on_fail`, `count_emoji`. |
| `guild_polls` | `id` (UUID) | Umfragen (`options` JSON, `multi`, `ends_at`, `ended`). Index `idx_polls_guild`. |
| `guild_poll_votes` | `(poll_id, user_id, option_index)` | Stimmen (FK CASCADE). |
| `guild_invite_settings` | `guild_id` | Invite-Tracking: `enabled`, `log_channel_id`, `message_template`. |
| `guild_invites` | `(guild_id, code)` | Use-Count-Cache je Invite-Code (`inviter_id`, `uses`). |
| `guild_member_invites` | `(guild_id, user_id)` | Beitritts-Record/Leaderboard-Quelle. Index `idx_member_invites_inviter`. |
| `guild_application_forms` | `id` (UUID) | Bewerbungsformulare (`questions` JSON ≤5, `review_channel_id`, `accepted_role_id`). Index `idx_application_forms_guild`. |
| `guild_applications` | `id` (UUID) | Einreichungen (`answers` JSON, `status ∈ pending|accepted|denied`, `reviewer_id`). Index `idx_applications_guild`. |
| `guild_economy_settings` | `guild_id` | Währung (`currency_name`/`_symbol`), `start_balance`, Daily/Work-Payouts + Cooldowns. |
| `guild_economy_users` | `(guild_id, user_id)` | `balance`, `last_daily`, `last_work`. Index `idx_economy_users_balance`. |
| `guild_economy_shop` | `id` (UUID) | Shop-Items (`price`, optionale `role_id`, `position`). Index `idx_economy_shop_guild`. |
| `guild_games_settings` | `guild_id` | Games-Kategorie: geteilter `games_channel_id` + pro-Spiel-Toggle (tictactoe/rps/trivia/connect4/hangman/poker) + `poker_table_theme` + `games_language`. |
| `guild_game_scores` | `(guild_id, user_id, game)` | `wins`/`plays` je Spiel. Index `idx_game_scores_lb`. |

### 4.4 Server-Backup & Marketplace

| Tabelle | PK | Zweck |
|---|---|---|
| `guild_backups` | `id` (UUID) | Server-Snapshots (`data` JSON-Blob `{server,roles,channels}` + Counts; Retention max 15/Guild). Index `idx_backups_guild`. |
| `guild_backup_jobs` | `id` (UUID) | Async Job-Queue (`type ∈ snapshot|restore`, `status`, `backup_id`, `mode ∈ missing|mirror`, `parts` JSON = NULL → alle). Index `idx_backup_jobs_status`. |
| `marketplace_templates` | `id` (UUID) | Owner-veröffentlichte Server-Vorlagen (`data` JSON-Blob, `status`, `uses`); `backup_id` eines Restore-Jobs kann hierauf zeigen. Index `idx_marketplace_status`. |

### 4.5 Premium / Admin / System

| Tabelle | PK | Zweck |
|---|---|---|
| `premium_codes` | `code` | Promo-/Trial-Codes (`tier`, `duration_days`, `max_uses`/`uses`, `expires_at`). Owner erstellt, Guild-Admin löst ein (Quelle `'code'`). |
| `admin_broadcasts` | `id` (UUID) | Owner-Broadcast-Queue (DM an alle Server-Owner; `status ∈ pending|sending|done|failed`, `sent_count`/`total`). |
| `admin_metrics_snapshots` | `day` (UTC-Mitternacht unix-s) | Tägliche System-Metriken (User/Guild/Premium-Totals + `module_adoption` JSON) für Admin-Analytics. |
| `error_log` | `id` (AUTOINCR) | Zentrales Fehler-Log (`source ∈ bot|backend`, `level`, `context`, `message`, `stack`, `guild_id`). Retention 2000 Zeilen. Index `idx_error_log_created`. |

---

## 5. Migrations-Übersicht v1–v40

| Version | Inhalt |
|---|---|
| v1 | Initialschema (Tabellen in `initializeDatabase()` angelegt). |
| v2 | `users.token_expires_at`. |
| v3 | `guild_autorole_settings`, `guild_log_settings`, `guild_moderation_settings`. |
| v4 | `guilds.bot_present`. |
| v5 | Welcome/Leave-Embed/DM/Auto-Delete/Ping (9 Spalten in `guild_settings`). |
| v6 | `guild_channels` + `guild_roles` (Resource-Cache). |
| v7 | Reaction-Roles (2 Tab.) + Leveling (3 Tab.) + Custom-Commands. |
| v8 | `guild_social_subscriptions`. |
| v9 | Moderation +12 Spalten / Logs +6 Spalten + `guild_moderation_warnings`. |
| v10 | Statistics: `guild_stats_settings` + `_counters` + `_snapshots`. |
| v11 | Stats-Kategorie-Spalten (`category_id`/`auto_category`/`category_name`). |
| v12 | Temp-Voice (2 Tab.) + Starboard (2 Tab.) + Suggestions. |
| v13 | Birthday (2 Tab.) + Scheduled Messages + Anti-Raid. |
| v14 | Verification + Role-Menus (2 Tab.). |
| v15 | Tickets (2 Tab.) + Giveaways (2 Tab.). |
| v16 | Ticket-Transcript-Channel + Role-Menu `exclusive`. |
| v17 | Owner-Sperre: `blocked`/`_reason`/`_at` auf `users` + `guilds`. |
| v18 | Ticket-Überarbeitung: Settings +10 / Tickets +8 Spalten + `guild_ticket_categories`. |
| v19 | Command-Manager: `guilds.command_prefix` + `guild_command_settings`. |
| v20 | Role-Menu-Embed-Designer: `use_embed` + `embed`. |
| v21 | Premium-Tiers: `guilds.premium_tier`/`_source`/`_until`. |
| v22 | Admin v2: `*.blocked_until` (Temp-Ban) + `system_settings`. |
| v23 | Counting: `guild_counting_settings`. |
| v24 | Polls: `guild_polls` + `guild_poll_votes`. |
| v25 | Invite-Tracking: `guild_invite_settings` + `guild_invites` + `guild_member_invites`. |
| v26 | Applications: `guild_application_forms` + `guild_applications`. |
| v27 | Economy: `guild_economy_settings` + `_users` + `_shop`. |
| v28 | Games-Kategorie: `guild_games_settings` + `guild_game_scores`. |
| v29 | `guild_games_settings.poker_enabled`. |
| v30 | `guild_games_settings.poker_table_theme`. |
| v31 | `guild_games_settings.games_language`. |
| v32 | Server-Backup: `guild_backups` + `guild_backup_jobs`. |
| v33 | `guild_backup_jobs.parts` (Teil-Auswahl). |
| v34 | `marketplace_templates`. |
| v35 | Temp-Voice-Steuerungspanel (3 Spalten). |
| v36 | `guild_general_settings`. |
| v37 | `error_log`. |
| v38 | `admin_metrics_snapshots`. |
| v39 | `admin_broadcasts`. |
| v40 | `premium_codes` + `guilds.premium_reminded_at`. |

---

> Für die DB-Helfer-Funktionen siehe [DATABASE_FUNCTIONS.md](DATABASE_FUNCTIONS.md).
