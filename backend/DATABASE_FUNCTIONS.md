# DB-Funktions-Referenz — projectx

> Referenz der wichtigsten in [db.js](db.js) exportierten Helfer (+ [migrations.js](migrations.js) für Schema-Funktionen). Gruppiert nach Thema. Pro Eintrag: Signatur + 1 Satz Zweck. Schema-Details (Tabellen/Spalten) in [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

Konventionen: Settings-Module folgen meist dem Muster `getXxxSettings(guildId)` / `upsertXxxSettings(guildId, settings)` und liefern bei leerer Row die `XXX_DEFAULTS`. Alle Schreibpfade mit mehreren Statements laufen über `runInTransaction`.

---

## Kritische Helfer (zuerst lesen)

- **`runInTransaction(work)`** — Führt `work` in **einem** `BEGIN IMMEDIATE`/`COMMIT` aus (Rollback bei Fehler). **Serialisiert alle Transaktionen über eine interne Promise-Queue (`_txChain`)** — sqlite3 nutzt nur eine Connection, überlappende `BEGIN IMMEDIATE` würden „cannot start a transaction within a transaction" werfen. **Pflicht für jeden Bulk-Write** — niemals eigene `BEGIN`-Blöcke.
- **`grantXp(guildId, userId, now)`** — Leveling-Kern: Cooldown-Check, XP würfeln, Row schreiben, Level-Up + Reward-Roles berechnen — alles in einem `BEGIN IMMEDIATE` gegen Double-Grant bei parallelen Messages.
- **`syncBotPresence(presentGuildIds)`** — Bulk-Update in einer Transaktion: `bot_present = 1` für alle übergebenen Guild-IDs, `= 0` für alle anderen.
- **`addModerationWarning(guildId, userId, now)`** — Erhöht den persistenten Warn-Zähler atomar, prüft `warn_threshold`; bei Erreichen Reset + `escalation_action` zurück.
- **`effectiveTier(row)` / `tierFilterSql(minTier, col?)` / `moduleUnlockMap(tier)`** — Premium-Kern: effektiver Tier (expiry-aware), SQL-Filter „effektiver Tier ≥ minTier" (für Loop-Cog-Queries), Modul-Unlock-Map fürs Dashboard.

---

## User / Auth

- `getUser(discordId)` — User-Row inkl. Tokens lesen.
- `upsertUser(discordId, userData)` — User anlegen/aktualisieren (inkl. `token_expires_at`).
- `updateUserTokens(discordId, accessToken, refreshToken, tokenExpiresAt)` — Tokens nach `/auth/refresh-guilds` aktualisieren.
- `getUserGuilds(userId)` — alle Memberships des Users.
- `getUserManageableGuilds(userId)` — nur Guilds mit `owner=1 OR admin=1` (inkl. `blocked`-Flag) — für `GET /api/guilds`.
- `addUserToGuild(userId, guildId, owner, admin)` — Membership setzen (beide Bits).
- `removeUserFromGuild(userId, guildId)` / `removeUserGuildsNotIn(userId, keepGuildIds)` — Reconcile beim Login (parameterisiertes `NOT IN`, korrekt für leere Liste).
- `userHasGuildAccess(userId, guildId)` — beliebige Membership (intern).
- `userIsGuildAdmin(userId, guildId)` — Owner/Admin-Check (von `requireGuildAccess` genutzt).
- `deleteUser(discordId)` — User löschen (CASCADE).

## Guilds / Presence

- `getGuild(guildId)` / `getAllGuilds()` — Guild-Row(s) lesen.
- `createGuild(guildId, name, iconUrl)` / `upsertGuildRow(...)` — Guild anlegen/seeden (FK-Schutz vor Channel-/Role-Replace).
- `updateGuild(guildId, updates)` / `deleteGuild(guildId)` — Guild ändern/löschen.
- `syncBotPresence(presentGuildIds)` — Bot-Präsenz-Bulk-Update (siehe kritische Helfer).
- `replaceGuildChannels(guildId, channels, guildMeta?)` / `replaceGuildRoles(guildId, roles, guildMeta?)` — Vollständiges Replace (DELETE + Bulk-INSERT in einer Transaktion), optionaler Guild-Seed.
- `getGuildChannels(guildId)` / `getGuildRoles(guildId, {includeDefault, includeManaged})` — sortierte Listen für Dashboard-Dropdowns.

## Welcome / Leave

- `getGuildSettings(guildId)` — volle erweiterte Shape (parst `welcome_embed`/`leave_embed`-JSON); Defaults aus `WELCOME_LEAVE_DEFAULTS`.
- `upsertGuildSettings(guildId, settings)` — Single Source der Validierung (Längen-Caps, Hex-Color-Regex, URL-Form, Delete-After-Clamp 0..600, JSON-Stringify der Embeds).
- Konstante: `WELCOME_LEAVE_DEFAULTS`.

## Allgemein / Auto-Role / Logs / Moderation

- `getGeneralSettings` / `upsertGeneralSettings` — Sprache/Zeitzone/Embed-Farbe/Theme (validiert/fallbackt). Konstanten `GENERAL_LANGUAGES`/`GENERAL_THEMES`/`GENERAL_TIMEZONES`/`GENERAL_DEFAULTS`.
- `getAutoroleSettings` / `upsertAutoroleSettings` — JSON-Parse/Stringify für `role_ids`.
- `getLogSettings` / `upsertLogSettings` — Boolean-Coercion aller Event-Flags, JSON für `log_ignored_channel_ids`.
- `getModerationSettings` / `upsertModerationSettings` — JSON für `banned_words`/`exempt_role_ids`/`ignored_channel_ids`, Bounds-Checks + Enum-Validation. Konstanten `MOD_ACTIONS`/`MOD_ESCALATION_ACTIONS`.
- `addModerationWarning(guildId, userId, now)` — atomarer Warn-Zähler + Eskalation (siehe kritische Helfer).

## Engagement — Reaction-Roles / Leveling / Custom-Commands

- Reaction-Roles: `getReactionRoleMessages`, `createReactionRoleMessage`, `updateReactionRoleMessage` (Mappings-Replace in Transaktion), `deleteReactionRoleMessage`, `findReactionRoleByMessage`.
- Level-Math (exportiert): `totalXpForLevel(n)` (MEE6-Curve), `levelFromXp(xp)`, `xpForNextLevel(currentLevel)`.
- Leveling: `getLevelingSettings` / `upsertLevelingSettings`, `getLevelingRewards` / `setLevelingRewards` (Bulk-Replace), `getLevelingUser`, **`grantXp`** (Kern, siehe oben), `getLeaderboard(guildId, limit, offset)`, `countLeaderboardUsers`.
- Custom-Commands: `getCustomCommands`, `createCustomCommand` (UNIQUE→Route 409), `updateCustomCommand`, `deleteCustomCommand`.
- Command-Manager: `BUILTIN_COMMANDS` (Katalog, Single Source), `sanitizeCommandPrefix`, `getCommandPrefix`/`setCommandPrefix`, `getCommandSettings`/`setCommandEnabled`, `getCommandConfigForBot(guildId)`.

## Social / Statistics

- Social: `getSocialSubscriptions` (Dashboard), `getAllEnabledSocialSubscriptions` (Bot, alle Guilds), `createSocialSubscription`/`updateSocialSubscription`/`deleteSocialSubscription` (UUID, Account-Normalisierung, UNIQUE→409, State-Reset bei Plattform-/Account-Wechsel), `updateSocialSubscriptionState(subId, state, now)`. Konstanten `SOCIAL_PLATFORMS`/`SOCIAL_DEFAULTS`.
- Statistics: `getStatsSettings`/`upsertStatsSettings` (clamp `update_interval`), `setStatsCategory`, `getStatsCounters`/`createStatsCounter`/`updateStatsCounter`/`deleteStatsCounter`, `setStatsCounterChannel`, `getAllEnabledStatsConfigs` (Bot), `insertStatsSnapshot` (Insert + Prune >90 Tage in einer Transaktion), `getStatsSnapshots`. Konstanten `STATS_COUNTER_TYPES`/`STATS_DEFAULTS`.

## Community-Module (settings-zentriert)

- Temp-Voice: `getTempVoiceSettings`/`upsertTempVoiceSettings`, `addTempVoiceChannel`/`removeTempVoiceChannel`/`getAllTempVoiceChannels` (Bot-Tracking). Konstanten `TEMPVOICE_PANEL_DESTINATIONS`/`TEMPVOICE_DEFAULTS`.
- Starboard: `getStarboardSettings`/`upsertStarboardSettings`, `getStarboardEntry`/`upsertStarboardEntry`/`deleteStarboardEntry`. Konstante `STARBOARD_DEFAULTS`.
- Suggestions: `getSuggestionSettings`/`upsertSuggestionSettings`. Konstante `SUGGESTION_DEFAULTS`.
- Birthday: `getBirthdaySettings`/`upsertBirthdaySettings`, `setBirthday`, `getGuildBirthdays`, `removeBirthday`, `getTodaysBirthdays(month, day)`, `getBirthdayRoleGuilds`. Konstante `BIRTHDAY_DEFAULTS`.
- Scheduled: `getScheduledMessages`, `createScheduledMessage`/`updateScheduledMessage`/`deleteScheduledMessage`, `getDueScheduledMessages(now)`, `markScheduledRan(id, now)` (rechnet next/disable). Konstante `SCHEDULED_TYPES`.
- Anti-Raid: `getAntiRaidSettings`/`upsertAntiRaidSettings`. Konstanten `ANTIRAID_ACTIONS`/`ANTIRAID_DEFAULTS`.
- Verification: `getVerificationSettings`/`upsertVerificationSettings`, `setVerificationPanelMessage`. Konstante `VERIFICATION_DEFAULTS`.
- Role-Menus: `getRoleMenus`, `getPendingRoleMenus` (Bot), `createRoleMenu`/`updateRoleMenu`/`deleteRoleMenu` (Options-Replace in Transaktion), `getRoleMenuByMessage`, `setRoleMenuMessage`. Konstante `ROLE_MENU_TYPES`.
- Tickets: `getTicketSettings`/`upsertTicketSettings`, `setTicketPanelMessage`, Kategorie-CRUD (`getTicketCategories`/`createTicketCategory`/`updateTicketCategory`/`deleteTicketCategory`), `getTicketConfig` (Settings + enabled Kategorien für Bot), `createTicket` (mit Nummer), `getOpenTicketForUser`, `getTicketByChannel`, `closeTicketByChannel`, `claimTicket`, `setTicketRating`, `updateTicketExtraUsers`, `getGuildTickets`. Konstanten `TICKET_PANEL_TYPES`/`TICKET_RATING_MODES`/`TICKET_BUTTON_STYLES`/`TICKET_DEFAULTS`.
- Giveaways: `createGiveaway`, `setGiveawayMessage`, `addGiveawayEntry`, `getGiveawayEntries`, `getDueGiveaways(now)`, `markGiveawayEnded`, `getGuildGiveaways`, `getGiveawayById`, `deleteGiveaway`.
- Counting: `getCountingSettings`/`upsertCountingSettings`, `recordCount(guildId, userId, number)` (atomare Validierung). Konstante `COUNTING_DEFAULTS`.
- Polls: `createPoll`, `setPollMessage`, `getPoll`, `votePoll`, `getDuePolls(now)`, `markPollEnded`, `getGuildPolls`, `deletePoll`.
- Invite-Tracking: `getInviteSettings`/`upsertInviteSettings`, `replaceGuildInvites`, `getGuildInvitesCache`, `recordMemberInvite`, `getInviteLeaderboard`. Konstante `INVITE_DEFAULTS`.
- Applications: `getApplicationForms`/`getEnabledApplicationForms`/`getApplicationForm`, `createApplicationForm`/`updateApplicationForm`/`deleteApplicationForm`, `setApplicationPanelMessage`, `createApplication`, `reviewApplication`, `getApplications`.
- Economy: `getEconomySettings`/`upsertEconomySettings`, `getEconomyBalance`, `economyDaily`/`economyWork`/`economyPay`/`economyBuy` (transaktional), `getEconomyLeaderboard`, Shop-CRUD (`getEconomyShop`/`createShopItem`/`updateShopItem`/`deleteShopItem`). Konstante `ECONOMY_DEFAULTS`.
- Games: `getGamesSettings`/`upsertGamesSettings` (Partial-Merge), `recordGameScore(guildId, userId, game, win)`, `getGameLeaderboard(guildId, game, limit)`. Konstanten `GAME_KEYS`/`POKER_THEMES`/`GAME_LANGUAGES`/`GAMES_DEFAULTS`.

## Premium / Tiers

- `effectiveTier(row)` — abgelaufenes `premium_until` → `'free'`.
- `moduleUnlocked(tier, key)` / `moduleUnlockMap(tier)` — Modul-Unlock für einen Tier.
- `tierRank(tier)` — numerischer Rang (free<basic<pro).
- `tierFilterSql(minTier, column?)` — SQL-Fragment „effektiver Tier ≥ minTier" (expiry-aware) für Bulk-Bot-Queries.
- `getGuildPremium(guildId)` — rohe Premium-Felder.
- `setGuildPremium(guildId, {tier, source, until})` — Tier setzen (`source ∈ manual|sku|code`; `free` löscht).
- `syncSkuEntitlements(entitlements)` — Bot/SKU-Bulk-Sync + Downgrade abgelaufener SKU-Premiums (lässt `manual` unberührt), in `runInTransaction`.
- Codes: `createPremiumCode`, `getPremiumCodes`, `deletePremiumCode`, `redeemPremiumCode(rawCode, guildId)` (Quelle `'code'`, Fehler-`reason` invalid|expired|exhausted).
- `getRevenue()` — geschätzte MRR aus aktiven Premium-Counts × `PLAN_CATALOG`.
- `getExpiringPremiumGuilds(days?)` / `markPremiumReminded(guildId)` — Ablauf-Reminder (Bot, Dedupe via `premium_reminded_at`).
- Konstanten: `PREMIUM_TIERS`, `MODULE_TIERS` (Single Source Modul→Tier), `PLAN_CATALOG`.

## Owner-Admin / System

- Sperren: `isUserBlocked(discordId)` / `isGuildBlocked(guildId)` (temp-ban-aware), `getAdminUsers({search,limit,offset})` / `getAdminGuilds(...)`, `setUserBlocked(id, blocked, reason?, until?)` / `setGuildBlocked(id, blocked, reason?, until?)`.
- Übersicht/Audit: `getAdminOverview()`, `getAuditLogEntries({action,target,limit,offset})`, `getAuditActions()`, `getGuildInspect(guildId)`.
- Audit-Schreiben: `logAuditAction(userId, guildId, action, changes?)`, `getGuildAuditLog(guildId, limit?)`.
- System-Settings: `getSystemSetting`/`setSystemSetting`, `getMaintenanceState`/`setMaintenanceState`, `getAnnouncementState`/`setAnnouncementState` (Konstante `ANNOUNCEMENT_LEVELS`).
- Broadcasts: `createBroadcast`, `getDueBroadcast` (Bot), `updateBroadcast`, `getRecentBroadcasts`. Konstante `BROADCAST_STATUSES`.
- Export: `getUsersForExport()` / `getGuildsForExport()` (CSV).
- Analytics: `captureMetricsSnapshot()` (Upsert pro UTC-Tag), `getMetricsSnapshots(days)`, `getTopGuilds({by ∈ modules|activity})`.
- Fehler-Log: `logError({source,level,context,message,stack,guild_id})` (best-effort, Retention `ERROR_LOG_MAX`), `getErrorLog({source,level,limit,offset})`, `clearErrorLog()`. Konstanten `ERROR_LOG_SOURCES`/`ERROR_LOG_LEVELS`.

## Server-Backup & Marketplace

- Backups: `createBackup`, `getBackups`, `getBackup`, `deleteBackup` (Retention `BACKUP_MAX_PER_GUILD` = 15).
- Job-Queue: `createBackupJob({type,backup_id?,mode?,parts?})`, `getActiveBackupJobs`, `getDueBackupJobs` (Bot; joint Snapshot-`data` via `COALESCE` über `guild_backups`/`marketplace_templates`, gefiltert `tierFilterSql('pro')` + `blocked`), `updateBackupJob`, `getAllBackupJobs` (Admin), `retryBackupJob`.
- Marketplace: `createMarketplaceTemplate`, `getMarketplaceTemplates`, `getMarketplaceTemplate`, `getAdminMarketplaceTemplates`, `deleteMarketplaceTemplate`, `setMarketplaceTemplateStatus`, `incrementMarketplaceUses`.
- Konstanten: `BACKUP_JOB_TYPES`, `BACKUP_JOB_STATUSES`, `RESTORE_MODES`, `RESTORE_PARTS`, `MARKETPLACE_STATUSES`.

## Transaktion / Infrastruktur

- `runInTransaction(work)` — siehe kritische Helfer (oben).
- `whenDbReady` — Promise, das auflöst, sobald die Connection steht.
- `getDbStats()` — Zeilen-Counts der Kern-Tabellen.
- `closeDb()` — Connection schließen.

## Schema / Migrations ([migrations.js](migrations.js))

- `initializeSchemaVersion()` — `schema_version`-Tabelle anlegen.
- `checkAndApplyMigrations()` — fehlende Migrationen bis `CURRENT_SCHEMA_VERSION` (= 40) anwenden.
- `seedDatabase()` / `clearAllData()` / `getDbStats()` — Dev-/Test-Helfer.

---

> Schema-Details (Tabellen, Spalten, Indizes, Pragmas, Migrations-Übersicht) in [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md). Architektur-Kontext in [../CLAUDE.md](../CLAUDE.md) §8.
