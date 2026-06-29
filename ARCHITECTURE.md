# ARCHITECTURE.md — projectx

> System-Design-Übersicht für **projectx**, ein Discord-Bot-Dashboard.
> Diese Datei ist autoritativ für **Architektur-Fragen**. Für die exakte
> Endpoint-/Schema-/Konventions-Referenz gilt [CLAUDE.md](CLAUDE.md) als Single
> Source of Truth.

---

## 1. High-Level-Überblick

projectx besteht aus drei Laufzeit-Komponenten plus einer dateibasierten Datenbank:

| Komponente | Stack | Aufgabe |
|---|---|---|
| [bot/](bot/) | Python 3.8+, discord.py 2.3.2 | Reagiert auf Gateway-Events (`on_member_join`/`on_member_remove`, Reaktionen, Interaktionen, Loops), führt alle Server-Features aus |
| [backend/](backend/) | Node.js 18+, Express 4, SQLite3 (ESM) | REST-API, Discord-OAuth2, Settings-CRUD, Audit-Log, Cookie-Session, interne Bot-API |
| [frontend/](frontend/) | Vue 3 + Vite 4, Vue Router 4, Axios | Web-Dashboard zum Konfigurieren aller Module |
| SQLite-Datei | via `DATABASE_URL` (`./data/bot.db`) | Persistenz; vom Backend exklusiv besessen |

### Datenfluss

```
        ┌────────────┐   Cookie-Session (HttpOnly JWT)   ┌────────────┐
        │  Frontend  │ <───────────────────────────────> │  Backend   │
        │  (Vue 3)   │        /api/* (withCredentials)    │ (Express)  │
        └────────────┘                                    └─────┬──────┘
                                                                │ direkt
                                                          ┌─────┴──────┐
                                                          │  SQLite    │
                                                          └─────┬──────┘
        ┌────────────┐   interne API /api/bot/*                │
        │    Bot     │ <──────────────────────────────────────┘
        │(discord.py)│   X-Bot-Token (Shared Secret)
        └─────┬──────┘
              │ Gateway-Events / REST
        ┌─────┴──────┐
        │  Discord   │
        └────────────┘
```

- **Frontend ⇄ Backend:** Cookie-Session `projectx_session` (HttpOnly-JWT,
  `SameSite=Lax`, `Secure` nur in Production). Kein Bearer-Header, kein
  localStorage-Token.
- **Bot ⇄ Backend:** separate interne API unter `/api/bot/*`, abgesichert per
  `X-Bot-Token`-Header (constant-time-Vergleich gegen `BOT_API_KEY`). Antworten
  sind **rohe** Settings-Objekte ohne Envelope, damit der Bot direkt lesen kann.
- **Bot ⇄ Discord:** Gateway-Events + REST-Calls über discord.py.
- **Backend ⇄ Discord:** OAuth-Token-Exchange + User-/Guild-Lookups via axios.

Details: [CLAUDE.md](CLAUDE.md) §1.

---

## 2. Komponenten-Architektur

### 2.1 Bot ([bot/main.py](bot/main.py))

- **Cog-basiert:** ~34 Cogs unter [bot/cogs/](bot/cogs/) werden **einmalig** in
  `setup_hook` per `load_extension` geladen (jeweils mit eigenem try/except),
  danach `bot.tree.sync()` für Slash-Commands. **Nicht** in `on_ready` laden —
  das feuert bei jedem Reconnect und würde „Extension already loaded" werfen.
- **Intents:** default + `message_content` + `members` + `presences`
  (presences ist privilegiert → im Dev-Portal aktivieren; nötig für die
  Online/Offline-Statistik).
- **Dynamischer Prefix:** `command_prefix = async _resolve_prefix` löst pro Guild
  via [utils/command_config.py](bot/utils/command_config.py) (60s-Cache) auf;
  Mention bleibt immer aktiv.
- **Globale Gates:** `@bot.check` (Prefix) + `bot.tree.interaction_check` (Slash)
  sperren pro Guild deaktivierte Befehle.
- **Fehler-Reporting:** `on_command_error` schluckt CheckFailure/CommandNotFound,
  meldet sonst via `report_error` → `POST /api/bot/errors`; ein globaler
  `on_error` fängt Event-Exceptions ins zentrale `error_log`.
- **Shared-Helfer:** Backend-Calls laufen über
  [utils/backend.py](bot/utils/backend.py) (`fetch_bot_settings`, `bot_get/put/post/delete`).
  Weitere Querschnitts-Helfer: [general_config.py](bot/utils/general_config.py)
  (Embed-Farbe/Sprache/Zeitzone, 60s-Cache), [bot_i18n.py](bot/utils/bot_i18n.py)
  + [game_i18n.py](bot/utils/game_i18n.py) (5-sprachige Bot-/Game-Strings),
  [ratelimit.py](bot/utils/ratelimit.py) (proaktives Pacing pro Channel gegen
  429-Fluten beim Logging/Backup-Restore).

### 2.2 Backend ([backend/server.js](backend/server.js))

- **Express, ESM** (`"type": "module"`) — `import`/`export`, kein CommonJS.
- **Ein Router pro Modul** unter [backend/routes/](backend/routes/). Mount-Reihenfolge
  und Schutz-Middleware werden in [server.js](backend/server.js) verdrahtet.
- **Startup-Sequenz:** `whenDbReady` → `initializeSchemaVersion()` →
  `checkAndApplyMigrations()`; bis dahin antwortet alles außer `/api/health` mit
  `503`. Danach läuft alle 6h `captureMetricsSnapshot()` (Admin-Analytics).
- **Middleware** unter [backend/middleware/](backend/middleware/):
  - [session.js](backend/middleware/session.js) — `requireSession` (lehnt
    gesperrte User ab, setzt `req.user.is_owner`), `requireBotToken`
    (constant-time), `requireOwner`/`isOwner`, Cookie-Helfer.
  - [auth.js](backend/middleware/auth.js) — `requireGuildAccess` (Owner/Admin,
    lehnt gesperrte Guilds ab).
  - [premium.js](backend/middleware/premium.js) — `requirePremiumModule(key)`
    (Write-Gate, GET frei).
  - [maintenance.js](backend/middleware/maintenance.js) — `maintenanceGate`
    (global vor `/api/guilds`, blockt Nicht-Owner-Writes mit `503`).
- **DB-Zugriff** ausschließlich über [db.js](backend/db.js) / [utils/dbHelper.js](backend/utils/dbHelper.js) —
  keine inline-`sqlite3.Database` in Routes. Globaler Error-Handler bündelt 500er
  und schreibt ins `error_log`. Bind explizit auf `0.0.0.0` (IPv4-Fix für Windows).

### 2.3 Frontend ([frontend/src/](frontend/src/))

- **Vue 3 Composition API** (`<script setup>`), Vanilla-CSS + Tokens
  ([styles/tokens.css](frontend/src/styles/tokens.css)) — bewusst **kein**
  Tailwind/Pinia/VueUse/UI-Kit.
- **HTTP** nur über [services/api.js](frontend/src/services/api.js) (axios,
  `withCredentials: true`, 401 → Event + Redirect). Nie ein `Authorization`-Header.
- **State** über Singleton-Composables/Stores: [stores/auth.js](frontend/src/stores/auth.js)
  (`useAuth()`), [stores/guildSettings.js](frontend/src/stores/guildSettings.js),
  [stores/premium.js](frontend/src/stores/premium.js) (`usePremium().isUnlocked(key)`).
- **Routing** zentral in [router/index.js](frontend/src/router/index.js); Guards
  warten via `auth.waitUntilResolved()` (inkl. `requiresAuth`/`requiresOwner`).
- **i18n** ([i18n/index.js](frontend/src/i18n/index.js)): 5 Sprachen (EN/DE/TR/RU/PL),
  hand-gerollt, Key-Parität Pflicht, Persistenz in localStorage.
- **Mobile/Native:** dedizierte Handy-Shell ([mobile/](frontend/src/mobile/),
  aktiv in der Capacitor-App oder per `?mobile=1`) und Capacitor-Android-Wrapper
  im Remote-URL-Modus ([native/capacitor.js](frontend/src/native/capacitor.js),
  No-Op auf Web) — derselbe Code, dieselbe Session.

---

## 3. Wichtige Abläufe

### 3.1 OAuth-Login & Session

1. Frontend ruft `useAuth().loginWithDiscord()` → Redirect auf Discord-OAuth
   (`scope=identify email guilds`).
2. Discord redirected nach `/auth/callback?code=…`;
   [AuthCallback.vue](frontend/src/pages/AuthCallback.vue) sendet
   `POST /api/auth/callback { code }`.
3. Backend tauscht Code → Discord-Tokens, holt `/users/@me` + `/users/@me/guilds`,
   persistiert User + Tokens (in `users`), reconciliert `user_guilds`
   (Admin-Bit aus `permissions & 0x8`), setzt das `projectx_session`-Cookie.
4. Antwort: `{ success, user: { id, username, avatar_url, email, is_owner } }`
   — **keine** Discord-Tokens ans Frontend. Frontend speichert den User,
   navigiert nach `/dashboard`.
5. Folge-Requests laufen cookie-authentifiziert; `GET /api/auth/me` re-hydriert
   den Auth-State, `POST /api/auth/refresh-guilds` aktualisiert serverseitig.

### 3.2 Settings speichern → Bot liest

1. Dashboard-Seite sendet `PUT /api/guilds/:id/settings/<modul>` (cookie,
   `requireSession` + `requireGuildAccess`, ggf. `requirePremiumModule`).
2. Backend validiert/coerced (Längen-Caps, Hex/URL-Form, Enums, Clamps) in den
   `upsert*`-Helfern von [db.js](backend/db.js) und schreibt in SQLite. Audit-Eintrag.
3. Der Bot liest dieselben Settings **lazy** über `/api/bot/guilds/:id/settings/<modul>`
   mit `X-Bot-Token` (rohes Objekt, meist 60s-Cache pro Cog). Dashboard-Änderungen
   greifen also nach max. einem Cache-TTL.

### 3.3 Member-Join → Welcome-Nachricht

1. Discord feuert `on_member_join` → das
   [welcome_leave.py](bot/cogs/welcome_leave.py)-Cog wird aktiv.
2. Cog holt die Welcome/Leave-Settings via `/api/bot/guilds/:id/settings`.
3. Bei `welcome_enabled` und gesetztem Channel: Platzhalter auflösen
   (`{user.*}`/`{guild.*}`), Plain- **oder** Embed-Nachricht bauen, optional
   `@`-Mention als content, optional DM, optional Auto-Delete.
4. Nachricht wird in den Ziel-Channel gesendet (Senden über das Rate-Limit-Pacing,
   wo relevant).

### 3.4 Premium-Gating (3 Schichten)

`MODULE_TIERS` in [db.js](backend/db.js) ist die Single Source (Modul-Key =
Dashboard-Route-Segment → min Tier `free|basic|pro`). Effektiver Tier ist
expiry-aware (`effectiveTier` → abgelaufenes Premium = `free`).

1. **Frontend-Lock:** [DashboardLayout.vue](frontend/src/pages/DashboardLayout.vue)
   rendert [PremiumLock.vue](frontend/src/components/PremiumLock.vue) statt der
   Modul-Seite, wenn der Tier nicht reicht (+ Sidebar-Lock-Icons, Overview-Ribbons).
2. **Backend-Write-Gate:** `requirePremiumModule(key)`
   ([middleware/premium.js](backend/middleware/premium.js)) — GET frei,
   PUT/POST/DELETE → `403 premium_required`.
3. **Bot-Runtime:** Guild-übergreifende Loop-Queries filtern serverseitig via
   `tierFilterSql(minTier)`; per-Guild Bot-GETs liefern über den
   `PREMIUM_BOT_GATES`-Guard in [routes/bot.js](backend/routes/bot.js) eine
   `disabled`-Shape. So gehen Premium-Features bei Tier-Verlust automatisch inert.

Premium-Quellen: Discord-SKU-Entitlements (Bot-Cog
[premium_sync.py](bot/cogs/premium_sync.py) → `PUT /api/bot/premium`),
Owner-Override (Admin-Panel) und einlösbare Codes
(`POST /api/guilds/:id/premium/redeem`).

---

## 4. API-Architektur

REST-API, Mount-Struktur und Schutzmodelle aus [server.js](backend/server.js).
Die **vollständige Endpoint-Referenz** (Bodies, Response-Shapes, Audit-Actions)
steht in [CLAUDE.md](CLAUDE.md) §7 — hier nur das Schema.

| Mount-Präfix | Schutz |
|---|---|
| `GET /api/health` | offen |
| `/api/auth/*` | gemischt (Callback offen, `me`/`logout`/`refresh-guilds` cookie) |
| `/api/guilds/*` | `requireSession` + `requireGuildAccess` (+ `maintenanceGate`) |
| `/api/guilds/:id/<premium-modul>` | zusätzlich `requirePremiumModule(key)` |
| `/api/public/*` | offen (Landing-Stats, Tarif-Katalog, Maintenance, Announcement) |
| `/api/admin/*` | `requireSession` + `requireOwner` |
| `/api/bot/*` | `requireBotToken` (+ Guard: gesperrte Guilds → 403) |

Konventionen: alle Settings-Keys sind `snake_case`. User-Routes liefern einen
`{ success, settings }`-Envelope, `/api/bot/*` liefert das **rohe** Objekt.

---

## 5. Datenbank-Architektur

- **Engine:** SQLite3 (eine Connection, dateibasiert via `DATABASE_URL`).
  Connection + Query-Helfer in [db.js](backend/db.js).
- **Migrations:** versioniert in [migrations.js](backend/migrations.js),
  `CURRENT_SCHEMA_VERSION` steuert Upgrades. **Aktuelle Schema-Version: v40.**
  `applyMigrations(from, to)` mappt Versionen → `migrationVN`-Funktionen (alle
  idempotent; Fresh-DBs bekommen dieselben Tabellen zusätzlich im
  `initializeDatabase()`-Pfad gespiegelt). Tracking-Tabelle `schema_version`.
- **Bewusste Pragmas** (gesetzt in `initializeDatabase`):
  - `journal_mode = TRUNCATE` — **bewusst NICHT WAL.** Das Repo liegt auf einem
    `X:`-Volume (nicht-Standard-FS); WALs memory-mapped `-shm`-Datei + Locking
    scheitern dort mit `SQLITE_IOERR`. TRUNCATE ist reines File-I/O und läuft
    überall.
  - `foreign_keys = ON`, `synchronous = NORMAL`, `busy_timeout = 5000`.
- **Transaktions-Disziplin:** Jeder Bulk-Write läuft über
  `runInTransaction(...)` (`BEGIN IMMEDIATE`), das alle Transaktionen über eine
  interne Promise-Queue (`_txChain`) **serialisiert** — eine einzelne sqlite3-
  Connection erlaubt keine verschachtelten Transaktionen. Niemals eigene
  `BEGIN`-Blöcke. Ohne Queue/Transaktion wäre ein Login mit 100+ Guilds auf
  Windows >15s (fsync pro Row).

Die vollständige Tabellenliste samt Spalten steht in
[backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md) und
[backend/DATABASE_FUNCTIONS.md](backend/DATABASE_FUNCTIONS.md); ein kompakter
Überblick in [CLAUDE.md](CLAUDE.md) §8.

---

## 6. Deployment-Architektur

- **Container-Stack:** [docker-compose.yml](docker-compose.yml) mit
  `backend` (intern :3000, nicht published), `bot` und `frontend`
  (nginx serviert die SPA + reverse-proxyt `/api` → backend).
  Dockerfiles: [Dockerfile.backend](Dockerfile.backend),
  [Dockerfile.bot](Dockerfile.bot), [Dockerfile.frontend](Dockerfile.frontend).
- **Kein `db`-Service** — SQLite ist dateibasiert; Persistenz über das Named
  Volume `projectx-data` an `/data`.
- **VITE_*-Variablen sind Build-Args** (nicht Runtime). `VITE_BACKEND_URL=/api`
  hält Frontend + API same-origin (keine CORS-/Cookie-Probleme).
- **TLS:** Nginx Proxy Manager ([nginx-proxy-manager.yml](nginx-proxy-manager.yml),
  eigener Stack) terminiert HTTPS und leitet die Domain auf `frontend:80`
  (externes Docker-Netz `proxy`). **HTTPS ist Pflicht**, weil
  `NODE_ENV=production` das Session-Cookie auf `Secure` setzt.

Detaillierte Schritte: [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) und
[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

---

## 7. Sicherheits-Architektur

- **Session:** HttpOnly-Cookie mit signiertem JWT (`SESSION_SECRET`), Payload
  `{ uid }`, 7 Tage. `SameSite=Lax`, `Secure` nur in Production. Kein Token im
  Frontend-JS.
- **Discord-Tokens** leben ausschließlich in der `users`-Tabelle und verlassen
  den Backend-Prozess nie — sie gelangen **nie** in API-Responses ans Frontend.
- **Bot-Auth:** Shared Secret `BOT_API_KEY` im `X-Bot-Token`-Header, verglichen
  per `crypto.timingSafeEqual` (mit Length-Pre-Check). Fehlende Env → 500
  (fail-closed).
- **Autorisierung:** `requireGuildAccess` verlangt Owner/Admin (Defense-in-Depth
  zum Listenfilter `getUserManageableGuilds`).
- **Owner-/Block-/Maintenance-Gates:** System-Owner (`OWNER_DISCORD_ID`) kann
  User/Guilds sperren (temp-ban-aware); gesperrte Entities werden in
  `requireSession`/`requireGuildAccess`/`/api/bot/*` abgewiesen. Der globale
  `maintenanceGate` blockt Nicht-Owner-Writes im Wartungsmodus.
- **Eingabe:** parameterisierte SQL-Queries; Settings werden zentral in den
  `upsert*`-Helfern validiert/sanitisiert; Vue escaped Templates (XSS).

---

## 8. Verweise

- [CLAUDE.md](CLAUDE.md) — autoritative Referenz (Tech-Stack, Auth-Vertrag,
  API-Endpoints, DB-Schema, Konventionen, Troubleshooting).
- [README.md](README.md) — Setup-Guide.
- [backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md) /
  [backend/DATABASE_FUNCTIONS.md](backend/DATABASE_FUNCTIONS.md) — DB-Detail.
- [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) /
  [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) — Deployment.
- [TEST_PLAN.md](TEST_PLAN.md) — manuelle End-to-End-Checks.
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) — Doku-Index.
