# CLAUDE.md — projectx

> Diese Datei ist der Einstiegspunkt für Claude Code in diesem Repository.
> Sie beschreibt Architektur, Konventionen, Workflows und Regeln, die bei jeder Arbeit am Code zu beachten sind.

---

## ⚠️ Pflicht-Regel: CLAUDE.md aktuell halten

**Nach JEDER Anpassung am Projekt (Code, Struktur, Konfiguration, Dependencies, Scripts, API, DB-Schema, Workflows, .env-Variablen) muss diese CLAUDE.md auf den aktuellen Stand gebracht werden — im selben Arbeitsschritt, bevor die Aufgabe als erledigt gemeldet wird.**

Konkret bedeutet das:
- Neue Datei/Route/Komponente/Cog hinzugefügt → entsprechenden Abschnitt unten ergänzen.
- Bestehende Datei/Funktion umbenannt oder entfernt → Verweise hier korrigieren oder löschen.
- Neue Dependency in `package.json` / `requirements.txt` → Tech-Stack-Abschnitt aktualisieren.
- Neue `.env`-Variable → Environment-Abschnitt erweitern.
- DB-Schema-Änderung (Migration) → Datenbank-Abschnitt + Schema-Version anpassen.
- API-Endpoint geändert → API-Übersicht aktualisieren.
- Build-/Start-/Test-Befehl geändert → Commands-Abschnitt anpassen.
- Neue Konvention oder Pattern eingeführt → Konventionen-Abschnitt erweitern.

Wenn eine Änderung **keinen** Einfluss auf die hier dokumentierten Inhalte hat, kurz im Reasoning erwähnen, dass CLAUDE.md geprüft wurde und kein Update nötig ist.

Diese Regel hat Vorrang vor „Brevity"-Gewohnheiten — die CLAUDE.md ist Single Source of Truth für jede zukünftige Claude-Session.

---

## 1. Projektüberblick

**projectx** ist ein Discord-Bot-Dashboard mit drei Komponenten, die zusammen ein System für die Verwaltung von Welcome-/Leave-Nachrichten in Discord-Servern bilden:

| Komponente | Stack | Zweck |
|---|---|---|
| [bot/](bot/) | Python 3.8+, discord.py 2.3.2 | Hört auf `on_member_join` / `on_member_remove`, sendet konfigurierte Nachrichten |
| [backend/](backend/) | Node.js 18+, Express 4, SQLite3 | REST-API, Discord-OAuth2, Settings-CRUD, Audit-Log, Cookie-Session, interne Bot-API |
| [frontend/](frontend/) | Vue 3 + Vite 4, Vue Router 4, Axios | Web-Dashboard zum Konfigurieren der Bot-Nachrichten |

**Datenfluss:**
- Frontend ⇄ Backend: Cookie-Session (`projectx_session`, HTTP-only JWT)
- Backend ⇄ SQLite: direkt
- Bot ⇄ Backend: separate interne API unter `/api/bot/*`, abgesichert via `X-Bot-Token`-Header (Shared Secret)
- Bot ⇄ Discord: Gateway-Events (`on_member_join` / `on_member_remove`)

Tiefere Architektur-Details: [ARCHITECTURE.md](ARCHITECTURE.md)
Doku-Index: [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)

---

## 2. Verzeichnisstruktur

```
projectx/
├── bot/                        # Python Discord-Bot
│   ├── main.py                 # Entry-Point, lädt 34 Cogs in setup_hook (läuft 1× beim Start — NICHT in on_ready, das bei jedem Reconnect feuert → sonst „Extension already loaded")
│   │                           # Danach in setup_hook: bot.tree.sync() für Slash-Commands. on_ready loggt nur noch die Verbindung.
│   │                           # command_prefix = async _resolve_prefix (per-Guild via command_config, Cache, Mention immer aktiv)
│   │                           # Globale Gates: @bot.check (Prefix) + bot.tree.interaction_check (Slash) sperren deaktivierte Befehle
│   │                           # on_command_error schluckt CheckFailure/CommandNotFound (deaktiviert/keine Perms), printet sonst Traceback
│   │                           # Intents: default + message_content + members + presences (presences = PRIVILEGED, im Dev-Portal aktivieren — nötig für Online/Offline-Stats)
│   ├── config.py               # Lädt .env (DISCORD_TOKEN, BACKEND_URL, BOT_API_KEY, Social-API-Keys …)
│   ├── requirements.txt
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── backend.py          # fetch_bot_settings(backend_url, api_key, guild_id, module)
│   │   │                       # Shared async-Helper für alle Cogs (5s timeout, X-Bot-Token)
│   │   ├── command_config.py   # get_config/get_prefix/is_disabled — pro-Guild Command-Config (Prefix + disabled Keys)
│   │   │                       # via GET /api/bot/guilds/:id/commands, 60s In-Memory-Cache
│   │   └── game_i18n.py        # make_translator(strings)/lang_of(settings)/normalize_lang — Übersetzungs-Helper
│   │                           # für die Games-Cogs (per-Guild games_language, Fallback EN→key, .format-safe)
│   └── cogs/
│       ├── welcome_leave.py    # Event-Handler + /welcome_test Command
│       ├── autorole.py         # on_member_join → Rollen aus role_ids zuweisen (skipt Bots wenn !apply_to_bots)
│       ├── logs.py             # join/leave/ban/unban/message_edit/message_delete/member_update
│       │                       # /channel_*/role_*/voice_state → Embed in log_channel_id;
│       │                       # log_ignored_channel_ids schließt Channels vom Message-Logging aus
│       ├── moderation.py       # on_message → Banned-Words + Anti-Invite/Link/Mass-Mention/Caps +
│       │                       # Anti-Spam (sliding window); Aktionen delete/warn/mute/kick/timeout;
│       │                       # Whitelist (exempt_role_ids/ignored_channel_ids); Warn-Eskalation
│       │                       # via POST /api/bot/.../moderation/warn
│       ├── presence.py         # on_ready + on_guild_join/remove + 5min loop → PUT /api/bot/presence
│       │                       # (Backend setzt guilds.bot_present für Frontend Invite/Configure-Logik)
│       ├── guild_sync.py       # on_ready + on_guild_join + on_guild_channel_* + on_guild_role_*
│       │                       # + 15min loop → PUT /api/bot/guilds/:id/{channels,roles}
│       │                       # (Backend füllt guild_channels / guild_roles für Dashboard-Dropdowns)
│       ├── reaction_roles.py   # on_raw_reaction_add/remove → Rolle (de-)assign; in-memory Cache
│       │                       # keyed by (guild_id, message_id); 10min refresh; exclusive-Mode
│       ├── leveling.py         # on_message → POST /api/bot/.../leveling/xp; postet Announcement
│       │                       # + Reward-Roles bei leveled_up; non-stacking respektiert
│       ├── custom_commands.py  # on_message → Match (exact/contains/starts_with) gegen Cache;
│       │                       # 5min refresh; nutzt resolve_placeholders aus welcome_leave
│       └── social_notify.py    # tasks.loop (SOCIAL_POLL_INTERVAL, default 180s) → pollt
│                               # YouTube (RSS + optional Data-API), Twitch (Helix Get Streams),
│                               # Kick (offizielle API). Erkennt neue Videos / Live-Übergänge,
│                               # postet Ankündigung (Template-Platzhalter + optional Embed),
│                               # schreibt Polling-State via PUT zurück. TikTok/Instagram = Stub.
│       ├── tempvoice.py        # on_voice_state_update: Join in Hub-Channel → erstellt temp Voice-Channel
│       │                       # (in Kategorie, user_limit), moved Member rein, löscht bei leer. on_ready-Cleanup.
│       │                       # Settings-Cache (5min TTL). Tracking via /api/bot/.../tempvoice/channels.
│       ├── starboard.py        # on_raw_reaction_add/remove: zählt Stern-Emoji, ab threshold Repost ins
│       │                       # star_channel (Embed + Jump), hält count aktuell, entfernt bei Unterschreitung.
│       │                       # Entry-State via /api/bot/.../starboard/entries/:message_id.
│       ├── suggestions.py      # !suggest <text> → postet Embed in suggest_channel + Up/Down-Vote-Reaktionen.
│       ├── birthday.py         # 30min-Loop (1×/Tag aktiv): GET /birthdays/today → Announce + Geburtstags-Rolle,
│       │                       # Rollen-Sweep (gestrige entfernen). !birthday TT.MM[.YYYY] speichert via POST.
│       ├── scheduler.py        # 30s-Loop: GET /scheduled/due → postet Nachricht, PUT .../ran (Backend rechnet next/disable).
│       ├── antiraid.py         # on_member_join: Account-Alter-Gate + Join-Rate-Burst (deque) → alert|kick|ban + Alarm.
│       ├── slash_utils.py      # Slash-Commands /ping /userinfo /serverinfo /avatar (app_commands, tree.sync in main.py).
│       ├── verification.py     # !verifypanel postet Verify-Button; on_interaction "verify" → Verifiziert-Rolle.
│       ├── rolemenus.py        # 60s-Loop postet unposted Menüs (Buttons/Select; Embed = Auto-Liste ODER eigenes use_embed-Embed);
│       │                       # on_interaction "rr:<role>"/"rrselect" → Rolle toggeln.
│       ├── tickets.py          # !ticketpanel postet Panel (Dropdown ODER Buttons je panel_type, Embed aus panel_embed).
│       │                       # on_interaction: ticket_select/ticketcat:<id>/ticket_open → Channel (Kategorie-Overrides),
│       │                       # ticket_claim, ticket_add/ticket_remove (UserSelect), ticket_close (+confirm),
│       │                       # ticketrate:<gid>:<id>:<n> → RatingModal. Commands: !claim/!ticketadd/!ticketremove/!ticketclose.
│       │                       # Bewertung (channel/dm/both), Transcript, Log-Channel, per-Guild-Nummerierung.
│       ├── giveaways.py        # !gstart <dur> <winners> <prize> → Button-Entry; on_interaction "ge:<id>"; 30s-Loop lost Gewinner aus.
│       ├── premium_sync.py     # Liest Discord-Entitlements (Premium-App-SKUs) → mappt SKU→Tier (config.SKU_BASIC_ID/SKU_PRO_ID),
│       │                       # PUT /api/bot/premium (Bulk). Inert ohne SKU-IDs (Owner-Override im Dashboard greift trotzdem).
│       └── stats.py            # tasks.loop (60s Takt, per-Guild gegen update_interval gegatet) →
│                               # GET /api/bot/stats/configs; zählt members/humans/bots/online/offline/
│                               # boosters/channels/roles je Guild (online/offline brauchen presences-Intent),
│                               # löst/erstellt Ziel-Kategorie (auto_category → create_category, id via PUT zurück),
│                               # benennt/erstellt Stats-Channels darin (auto_create: Voice locked / Text;
│                               # channel_id via PUT zurück), VERSCHIEBT bot-managed Channels in die Kategorie
│                               # (self-heal, nur wenn nicht drin), erzwingt Reihenfolge (position) via _enforce_order,
│                               # POSTet Snapshot. Rename/Reorder nur bei Abweichung (Rate-Limit-Schutz).
│       ├── counting.py         # on_message im Zähl-Channel → POST /counting/count (Backend validiert atomar);
│       │                       # ✅ bei Erfolg, ❌ + Reset bei falscher Zahl/Doppel-Count. (Free)
│       ├── polls.py            # !poll Frage | A | B | … → Button-Umfrage; on_interaction "pv:<id>:<idx>" toggelt Vote,
│       │                       # editiert Embed-Tally; 30s-Loop schließt fällige (timed) Umfragen. (Free)
│       ├── invitetracking.py   # on_ready cached guild.invites(), on_member_join difft Use-Counts → Einlader,
│       │                       # POST /invites/join + Ankündigung. Braucht MANAGE_GUILD. (Basic)
│       ├── applications.py     # !applypanel postet Form-Buttons; "app:<fid>" → Modal (≤5 Fragen); Submit → Review-Embed
│       │                       # mit Accept/Deny ("appok:"/"appno:"); Accept vergibt Rolle + DM. (Pro)
│       ├── economy.py          # !balance/!daily/!work/!pay/!rich/!shop/!buy → POST /economy/* (Backend rechnet
│       │                       # Balance/Cooldowns in Transaktionen); !buy vergibt optional Shop-Rolle. (Pro)
│       ├── tictactoe.py        # Games-Kategorie (alle Basic, geteilte /games-Settings + /games/score):
│       │                       # !ttt @gegner → 3×3 Button-Grid, on_interaction "ttt:<token>:<pos>", In-Memory-Session.
│       ├── rps.py              # !rps [@gegner] → Schere/Stein/Papier-Buttons (vs Spieler oder Bot).
│       ├── trivia.py           # !trivia → Frage-Bank (built-in) + 4 Buttons "trv:<token>:<idx>", erster Treffer punktet, 25s-Auto-Reveal.
│       ├── connect4.py         # !connect4 @gegner → 7-Spalten-Buttons "c4:<token>:<col>", Emoji-Board, 4-in-Reihe.
│       ├── hangman.py          # !hangman → Wort-Bank, Raten via on_message (Einzelbuchstaben), 6 Versuche, Solver punktet.
│       └── poker.py            # !poker → Texas-Hold'em-Tisch (1 pro Channel): Lobby (Join/Start + Add/Remove bot), Blinds,
│                               # Hole-Cards (ephemeral via "🃏 My cards"-Button), Flop/Turn/River, Setzrunden (Fold/Check/Call/
│                               # Raise-Modal/All-in) als State-Machine, layered Side-Pots, 7-Karten-Hand-Evaluator (mit Self-Test),
│                               # KI-Bots füllen Sitze (Hand-Strength+Pot-Odds-Heuristik, auto-Act, nie im Leaderboard),
│                               # GANZER TISCH als PNG gerendert (Filz+Holzrand, Sitze rund um Ellipse, Community-Cards, Pot,
│                               # D/SB/BB, aktiver Spieler hervorgehoben, Showdown enthüllt Hole-Cards) mit wählbarem Filz-Design
│                               # (THEMES: classic/midnight/crimson/charcoal/royal, aus poker_table_theme); Text-Fallback ohne Pillow.
│                               # Chip-Leader bei Tisch-Ende → /games/score. custom_id "pk:<action>:<tid>".
│       └── server_backup.py    # Server-Backup & Restore (Pro): @tasks.loop(20s) pollt GET /api/bot/backup/jobs/due,
│                               # claimt Job (status=running), führt aus, meldet done/failed zurück.
│                               # snapshot: serialisiert Rollen + Channels (Topic/NSFW/Slowmode/Bitrate/Limit + Permission-
│                               # Overwrites als allow/deny-Bitfields) + Server-Style → POST /api/bot/guilds/:id/backups.
│                               # restore: Rollen-Mapping old→neu (Hierarchie-Guard < Bot-Top-Rolle, @everyone gemappt),
│                               # Kategorien dann Channels, Overwrites umgemappt; mode=missing legt nur Fehlendes an,
│                               # mode=mirror gleicht zusätzlich an + löscht Channels die NICHT im Snapshot sind;
│                               # Server-Name/-Icon nur mit MANAGE_GUILD. asyncio.sleep zwischen Creates (Rate-Limit).
├── backend/                    # Node.js / Express API
│   ├── server.js               # App-Init, CORS+cookies, Migration-Bootstrap, Route-Mounts, Warnings
│   ├── db.js                   # SQLite-Connection + Query-Helper (inkl. updateUserTokens,
│   │                           # removeUserGuildsNotIn, getXxxSettings/upsertXxxSettings je Modul, MODULE_DEFAULTS)
│   ├── migrations.js           # Schema-Versioning + Migrations (aktuell v29)
│   ├── package.json
│   ├── middleware/
│   │   ├── session.js          # signSession / setSessionCookie / clearSessionCookie /
│   │   │                       # requireSession (lehnt gesperrte User ab, setzt req.user.is_owner) /
│   │   │                       # requireBotToken (constant-time compare) / requireOwner / isOwner (OWNER_DISCORD_ID)
│   │   ├── auth.js             # requireGuildAccess (verifyToken entfernt; lehnt gesperrte Guilds ab)
│   │   ├── premium.js          # requirePremiumModule(key) — write-gate für Premium-Module (GET frei, PUT/POST/DELETE → 403 premium_required)
│   │   └── maintenance.js      # maintenanceGate — global vor /api/guilds gemountet; blockt Nicht-Owner-Writes (POST/PUT/PATCH/DELETE)
│   │                           # mit 503 bei aktivem Wartungsmodus (Owner via JWT-Decode ausgenommen, 5s-Cache, fail-open)
│   ├── routes/
│   │   ├── auth.js             # /api/auth/{callback,me,logout,refresh-guilds}
│   │   ├── guilds.js           # /api/guilds/* (cookie-protected)
│   │   ├── settings.js         # /api/guilds/:id/settings (welcome/leave, cookie-protected)
│   │   ├── modules.js          # /api/guilds/:id/settings/{autorole,logs,moderation} (cookie-protected)
│   │   ├── resources.js        # /api/guilds/:id/{channels,roles} (cookie-protected) — Dashboard-Dropdowns
│   │   ├── reaction-roles.js   # /api/guilds/:id/reaction-roles (GET/POST/PUT/DELETE, cookie)
│   │   ├── leveling.js         # /api/guilds/:id/settings/leveling + .../leveling/leaderboard (cookie)
│   │   ├── custom-commands.js  # /api/guilds/:id/custom-commands (GET/POST/PUT/DELETE, cookie)
│   │   ├── social.js           # /api/guilds/:id/social (GET/POST/PUT/DELETE, cookie) — Social-Alerts
│   │   ├── stats.js            # /api/guilds/:id/stats (settings GET/PUT) + .../stats/counters
│   │   │                       # (POST/PUT/DELETE) + .../stats/history (cookie) — Statistik-Modul
│   │   ├── tempvoice.js        # /api/guilds/:id/tempvoice (settings GET/PUT, cookie) — Temp-Voice
│   │   ├── starboard.js        # /api/guilds/:id/starboard (settings GET/PUT, cookie) — Starboard
│   │   ├── suggestions.js      # /api/guilds/:id/suggestions (settings GET/PUT, cookie) — Vorschläge
│   │   ├── birthday.js         # /api/guilds/:id/birthday (settings GET/PUT + /list GET/DELETE, cookie)
│   │   ├── scheduled.js        # /api/guilds/:id/scheduled (GET/POST/PUT/DELETE, cookie) — geplante Nachrichten
│   │   ├── antiraid.js         # /api/guilds/:id/antiraid (settings GET/PUT, cookie) — Anti-Raid
│   │   ├── verification.js     # /api/guilds/:id/verification (settings GET/PUT, cookie)
│   │   ├── rolemenus.js        # /api/guilds/:id/rolemenus (GET/POST/PUT/DELETE, cookie) — Button/Select-Rollen
│   │   ├── tickets.js          # /api/guilds/:id/tickets (settings GET/PUT + /list, cookie)
│   │   ├── giveaways.js        # /api/guilds/:id/giveaways (GET list + DELETE, cookie)
│   │   ├── counting.js         # /api/guilds/:id/counting (settings GET/PUT, cookie) — Counting (Free)
│   │   ├── polls.js            # /api/guilds/:id/polls (GET list + DELETE, cookie) — Umfragen (Free)
│   │   ├── invitetracking.js   # /api/guilds/:id/invitetracking (settings GET/PUT + /leaderboard, cookie) — Invite-Tracking (Basic)
│   │   ├── applications.js     # /api/guilds/:id/applications/forms (CRUD) + /submissions (cookie) — Bewerbungen (Pro)
│   │   ├── economy.js          # /api/guilds/:id/economy (settings GET/PUT) + /shop (CRUD) + /leaderboard (cookie) — Wirtschaft (Pro)
│   │   ├── games.js           # /api/guilds/:id/games (shared settings GET/PUT, inkl. poker_table_theme) + /leaderboard?game= (cookie) — Games-Kategorie (Basic)
│   │   ├── backup.js          # /api/guilds/:id/backups (GET Liste+aktive Jobs, GET /templates Snapshots anderer eigener Server, GET /:id voller Snapshot für Vorschau,
│   │   │                       # POST Snapshot-Job, POST /apply-template {source_guild_id,backup_id,mode}, POST /:id/restore {mode}, DELETE /:id, cookie) — Server-Backup (Pro)
│   │   ├── public.js           # /api/public/stats + /api/public/plans (KEIN Auth — Landing-Page Stats + Tarif-Katalog)
│   │   ├── premium.js          # /api/guilds/:id/premium (GET, cookie) — Tier + Modul-Unlock-Map fürs Dashboard
│   │   ├── admin.js            # /api/admin/{users,guilds} (GET list + POST .../block[until] + POST .../premium, requireSession+requireOwner)
│   │   │                       # Owner-only: User/Guilds sperren/entsperren (+Temp-Ban) + Tier setzen (Audit ADMIN_BLOCK_*/UNBLOCK_*/SET_PREMIUM)
│   │   │                       # + /overview (Metriken), /audit(+/actions) (Audit-Viewer), /guilds/:id/inspect (Modul-Snapshot),
│   │   │                       # /maintenance (GET/PUT Wartungsmodus, Audit ADMIN_MAINTENANCE), /{users,guilds}/export (CSV)
│   │   └── bot.js              # /api/bot/guilds/:id/settings(/*) + .../channels/roles/presence +
│   │                           # .../reaction-roles + .../leveling/{settings,rewards,xp} +
│   │                           # .../custom-commands + /social/subscriptions(/:id/state) +
│   │                           # /stats (PUT) + /stats/configs + .../stats/counters/:cid/channel +
│   │                           # .../stats/snapshot (X-Bot-Token-protected)
│   ├── state/
│   │   └── botStats.js         # In-Memory Cache für Bot-Stats (guild_count, user_count, started_at)
│   │                           # 15min Stale-Window — danach gilt der Bot als offline
│   ├── utils/
│   │   └── dbHelper.js
│   └── tests/
│       ├── db.test.js
│       └── verify.js
├── frontend/                   # Vue 3 Dashboard (komplett neu strukturiert)
│   ├── index.html              # Inter / Space Grotesk / JetBrains Mono via Google Fonts
│   ├── vite.config.js
│   ├── package.json
│   ├── capacitor.config.json   # Capacitor-Config (Android-App): appId com.projectx.dashboard,
│   │                           # server.url = deployte Dashboard-Domain (Remote-URL-Modus),
│   │                           # allowNavigation discord.com, dunkles Theme + Splash/StatusBar
│   ├── resources/              # Icon/Splash-Quellen (icon.png/splash.png) für @capacitor/assets
│   ├── android/                # Generiertes Capacitor-Android-Projekt (committet, buildbar);
│   │                           # AndroidManifest + network_security_config (Dev-Cleartext 10.0.2.2)
│   └── src/
│       ├── main.js             # App-Bootstrap, lädt tokens.css + mobile/mobile.css, kickstartet
│       │                       # useAuth().fetchMe(), ruft applyMobileClass() + initNative() (Capacitor — No-Op auf Web)
│       ├── native/capacitor.js # Native (Android) Integration: Statusbar/Splash/Back-Button/
│       │                       # externe Links → System-Browser. Hinter isNativePlatform() (No-Op auf Web)
│       ├── mobile/             # Dedizierte Handy-Oberfläche (NUR in nativer App / ?mobile=1 aktiv; Desktop-Web unberührt)
│       │   ├── platform.js     # isMobileUI (computed: Capacitor.isNativePlatform() ODER ?mobile=1-Override in
│       │   │                   # localStorage projectx_force_mobile) + applyMobileClass() (setzt .mobile-ui auf <html>)
│       │   ├── mobile.css      # Globale Mobile-Schicht unter .mobile-ui (mappt --nav-height auf Top-Bar-Höhe,
│       │   │                   # Overview einspaltig, Save-Bar über Bottom-Nav heben, Tabellen-Scroll). Greift NICHT auf Desktop.
│       │   ├── MobileShell.vue # App-Shell für Mobile: TopBar + <router-view> + TabBar + AccountSheet (statt NavBar/Footer/Sidebar)
│       │   ├── MobileTopBar.vue# Sticky Top-Bar: Zurück (Modul-Seite → Overview-Hub) / Brand, Titel (Route→i18n), Avatar→AccountSheet
│       │   ├── MobileTabBar.vue# Fixe Bottom-Nav, kontextabhängig (ohne Guild: Home/Server/Konto; in Guild: Server/Module/Premium/Konto)
│       │   └── MobileAccountSheet.vue # Bottom-Sheet: User, LanguageSwitcher, Server-Link, Admin (Owner), Logout
│       ├── App.vue             # Branch: <MobileShell> wenn isMobileUI, sonst Desktop-Shell (AppNavBar + <router-view> + Footer); AppToast global
│       ├── router/index.js     # async beforeEach, wartet auf Auth-Resolution
│       ├── services/api.js     # axios mit withCredentials:true (KEIN Bearer-Header,
│       │                       # KEIN localStorage). 401 → CustomEvent + redirect /
│       ├── styles/
│       │   └── tokens.css      # Design-Tokens (Farben, Spacing, Radii, Shadows)
│       ├── stores/
│       │   ├── auth.js         # Singleton useAuth(): user, status, fetchMe,
│       │   │                   # loginWithDiscord, logout, waitUntilResolved
│       │   ├── guildSettings.js# Per-Guild-Settings-Cache (Welcome+Leave teilen sich State)
│       │   └── premium.js      # Per-Guild Premium-Cache (tier/modules-Unlock-Map); usePremium().isUnlocked(key)/tierOf(key)
│       ├── i18n/
│       │   ├── index.js        # useI18n(): { t, locale, setLocale }, ref-based,
│       │   │                   # persistiert in localStorage (key: projectx_locale).
│       │   │                   # Setzt document.documentElement.lang. KEINE Dep.
│       │   └── locales/        # 5 Sprachen, je 1088 Keys (Key-Parität Pflicht)
│       │       ├── en.js       # English (Quell-/Fallback-Sprache)
│       │       ├── de.js       # Deutsch
│       │       ├── tr.js       # Türkçe (Türkisch)
│       │       ├── ru.js       # Русский (Russisch)
│       │       └── pl.js       # Polski (Polnisch)
│       ├── composables/
│       │   ├── useToast.js     # Toast-System-Composable
│       │   └── useGuildResources.js # Per-Guild-Cache (channels + roles) mit 5min stale-while-revalidate
│       │                       # Wird von ChannelSelector + RoleSelector gemeinsam genutzt
│       ├── components/
│       │   ├── AppNavBar.vue   # Top-Bar mit User-Pill + LanguageSwitcher
│       │   ├── LanguageSwitcher.vue # Sprach-Dropdown EN/DE in der NavBar
│       │   ├── AppButton.vue   # variant: primary | ghost | danger
│       │   ├── AppCard.vue
│       │   ├── AppToggle.vue
│       │   ├── AppToast.vue
│       │   ├── AppFooter.vue   # Globaler Footer (Brand/©/Version, Legal-Links, GitHub)
│       │   ├── CookieBanner.vue # Cookie-Consent-Banner (bottom-right, localStorage projectx_cookie_consent)
│       │   ├── MaintenanceBanner.vue # Globaler Wartungs-Banner; pollt GET /api/public/maintenance (60s), rendert nur bei enabled
│       │   │                       # (Normal-Flow oben in beiden Shells — App.vue + MobileShell.vue)
│       │   ├── ChipInput.vue   # Reusable Chip-Input — nur noch für Banned-Words in Moderation
│       │   ├── ChannelSelector.vue # Searchable Dropdown (single) — :types filter (text/voice/category/...)
│       │   ├── RoleSelector.vue    # Searchable Dropdown — single oder :multiple, Color-Dots, Hierarchie
│       │   ├── EmbedEditor.vue # v-model embed config (Title/Desc/Color/Author/Thumb/Image/Footer/Timestamp)
│       │   ├── embedPlaceholders.js # Shared PLACEHOLDERS-Liste + insertAtCaret-Helper (Welcome/Leave/EmbedEditor)
│       │   ├── DiscordMessagePreview.vue  # Mock-Discord-Bubble — plain ODER embed-mode (props: mode, embed, pingUser)
│       │   ├── GuildAvatar.vue # Icon + Gradient-Initials-Fallback
│       │   ├── CustomCommandRow.vue # Inline-Editor-Row für CustomCommands (lokales Dirty-Tracking)
│       │   ├── SocialSubscriptionRow.vue # Inline-Editor-Row für Social-Alerts (Platform/Account/Channel/
│       │   │                       # Toggles/Mention-Role/Template+Embed; eigene Platzhalter-Liste)
│       │   ├── StatsCounterRow.vue # Inline-Editor-Row für Stats-Counter (Metrik-Typ/Name-Template mit
│       │   │                       # {count}/Modus existing↔auto-create/Voice|Text/Toggle; ChannelSelector)
│       │   ├── StatsChart.vue  # Vanilla-SVG-Liniendiagramm (props: title, points[{ts,...}], lines[{key,label,color}])
│       │   ├── ScheduledMessageRow.vue # Inline-Editor-Row für geplante Nachrichten (once/interval, datetime-local)
│       │   ├── RoleMenuRow.vue  # Inline-Editor-Row für Rollen-Menüs (Buttons/Select + Options-Repeater)
│       │   ├── TicketCategoryRow.vue # Inline-Editor-Row für Ticket-Kategorien (Label/Emoji/Desc/
│       │   │                       # Kategorie+Support-Rolle+Ping-Rolle-Override/Button-Style/Welcome/Toggle)
│       │   ├── PremiumLock.vue # Sperrseite für Premium-Module (in DashboardLayout statt router-view gerendert, wenn Tier < Modul)
│       │   ├── Sidebar.vue     # Dashboard-Sidebar mit 4 Gruppen (Configuration/Moderation/Engagement/Games) + Premium-Link + Lock-Icons
│       │   └── LoadingPage.vue # Animierter Orb
│       └── pages/
│           ├── Landing.vue          # /  (frei zugänglich, auch für authed User — Home-Button im /dashboard)
│           ├── Servers.vue          # /dashboard  (Guild-Auswahl, requiresAuth) — mit Home- + Refresh-Button
│           ├── DashboardLayout.vue  # Wrapper für /dashboard/:guild_id/* mit Sidebar
│           ├── Overview.vue         # /dashboard/:guild_id (Übersicht — 33 Modul-Cards mit Live-Status)
│           ├── Welcome.vue          # /dashboard/:guild_id/welcome (Config + Live-Preview)
│           ├── Leave.vue            # /dashboard/:guild_id/leave
│           ├── AutoRole.vue         # /dashboard/:guild_id/autorole (Toggle + Role-Chips + Apply-to-Bots)
│           ├── Logs.vue             # /dashboard/:guild_id/logs (Toggle + Channel-ID + 5 Event-Toggles)
│           ├── Moderation.vue       # /dashboard/:guild_id/moderation (Anti-Spam + Banned-Words-Chips + Action)
│           ├── ReactionRoles.vue    # /dashboard/:guild_id/reaction-roles (Liste + Inline-Editor; Mappings emoji↔role)
│           ├── Leveling.vue         # /dashboard/:guild_id/leveling (Settings + Rewards + Leaderboard Top 25)
│           ├── CustomCommands.vue   # /dashboard/:guild_id/custom-commands (Server-Prefix + Befehlskatalog aller Module
│           │                        # mit An/Aus-Toggles je Befehl + eigene Custom-Commands mit per-Row-Save, 3 Match-Types)
│           ├── SocialNotifications.vue # /dashboard/:guild_id/social (Liste + Inline-Editor; YouTube/Twitch/Kick)
│           ├── Stats.vue            # /dashboard/:guild_id/stats (Modul-Settings + Counter-Liste + Verlaufs-Graphen)
│           ├── TempVoice.vue        # /dashboard/:guild_id/tempvoice (Hub/Kategorie/Name/Limit)
│           ├── Starboard.vue        # /dashboard/:guild_id/starboard (Channel/Emoji/Threshold/Self-Star)
│           ├── Suggestions.vue      # /dashboard/:guild_id/suggestions (Channel/Vote-Emojis)
│           ├── Birthday.vue         # /dashboard/:guild_id/birthday (Settings + gespeicherte Geburtstage)
│           ├── ScheduledAnnouncements.vue # /dashboard/:guild_id/scheduled (CRUD-Liste, ScheduledMessageRow)
│           ├── AntiRaid.vue         # /dashboard/:guild_id/antiraid (Account-Alter/Join-Rate/Aktion/Alarm-Channel)
│           ├── Verification.vue     # /dashboard/:guild_id/verification (Channel/Rolle/Nachricht/Button)
│           ├── RoleMenus.vue        # /dashboard/:guild_id/rolemenus (CRUD-Liste, RoleMenuRow)
│           ├── Tickets.vue          # /dashboard/:guild_id/tickets (General/Panel-Design+EmbedEditor+DiscordMessagePreview/
│           │                        # Welcome-Embed+Preview/Bewertung/Kategorien-Liste via TicketCategoryRow — Settings-Save + per-Row-CRUD)
│           ├── Giveaways.vue        # /dashboard/:guild_id/giveaways (Read-only Liste + Löschen; Start via !gstart)
│           ├── Counting.vue         # /dashboard/:guild_id/counting (Toggle/Channel/Emoji/Reset + Live-Count/Highscore)
│           ├── Polls.vue            # /dashboard/:guild_id/polls (Read-only Liste + Löschen; Start via !poll)
│           ├── InviteTracking.vue   # /dashboard/:guild_id/invitetracking (Settings + Top-Inviter-Leaderboard)
│           ├── Applications.vue     # /dashboard/:guild_id/applications (Formular-CRUD inkl. Fragen + Einreichungs-Liste)
│           ├── Economy.vue          # /dashboard/:guild_id/economy (Settings + Shop-CRUD + Balance-Leaderboard)
│           ├── TicTacToe.vue / RockPaperScissors.vue / Trivia.vue / ConnectFour.vue / Hangman.vue / Poker.vue
│           │                        # Games-Kategorie: je Toggle + geteilter Spiele-Channel + Spiel-Bestenliste (alle nutzen /games)
│           ├── Backup.vue           # /dashboard/:guild_id/backup (Pro): Snapshot-jetzt-Button + Liste (Name/Datum/Channel-/Rollen-Anzahl)
│           │                        # + Vorschau-Modal (Server/Kanäle-Baum/Rollen mit Farben, lädt GET /:id) + Restore-Modal (missing|mirror)
│           │                        # + Löschen-Confirm; pollt aktive Jobs alle 4s bis fertig
│           ├── Premium.vue         # /dashboard/:guild_id/premium (Tarif-Übersicht Free/Basic/Pro + aktueller Tier + Upgrade-CTA)
│           ├── Admin.vue           # /admin (OWNER-only — Tabs Overview/Users/Guilds/Audit/System; Router-Guard requiresOwner)
│           │                       # Overview (Metrik-Karten + Premium-läuft-ab + Modul-Adoption), Users/Guilds (Sperren mit Temp-Ban-Dauer,
│           │                       # Tier-Select, CSV-Export, Guild-Inspektor-Modal), Audit (filterbarer Log), System (Wartungsmodus-Toggle)
│           ├── AuthCallback.vue     # /auth/callback (OAuth-Return → /dashboard)
│           └── legal/
│               ├── LegalLayout.vue  # Shared Typography-Wrapper (TOC, Sections, Last-Updated)
│               ├── Impressum.vue    # /legal/impressum
│               ├── Privacy.vue      # /legal/datenschutz (+ Alias /legal/privacy)
│               └── Terms.vue        # /legal/agb (+ Alias /legal/terms)
├── docker-compose.yml          # backend + bot + frontend + db
├── Dockerfile.backend
├── Dockerfile.bot
├── Dockerfile.frontend
├── nginx.conf                  # Frontend-Container: SPA + /api-Reverse-Proxy → backend
├── nginx-proxy-manager.yml     # Separater Portainer-Stack: NPM (TLS/Let's Encrypt) vor dem Frontend (Netzwerk `proxy`)
├── docs/                       # Öffentliche Endnutzer-Doku für GitBook (Git-Sync-Quelle): README.md + SUMMARY.md
│                               # + getting-started/modules/premium/faq. NICHT die internen Architektur-Files hier reinmischen.
├── ARCHITECTURE.md             # System-Design (autoritativ für Architektur-Fragen)
├── DOCUMENTATION_INDEX.md
├── README.md                   # Setup-Guide (Endnutzer-orientiert)
├── DEPLOYMENT_CHECKLIST.md
├── PRODUCTION_SETUP.md
├── TEST_PLAN.md
├── VERIFICATION_CHECKLIST.md
├── INTEGRATION_TESTING_STATUS.md
└── CLAUDE.md                   # ← diese Datei
```

`.env` und `.env.production.*` liegen versteckt (`-a-h-`) im Root bzw. in den Komponenten — **niemals committen, niemals den Inhalt in Outputs leaken**.

---

## 3. Tech-Stack & Dependencies (aktueller Stand)

### Bot — [bot/requirements.txt](bot/requirements.txt)
- `discord.py==2.3.2`
- `python-dotenv==1.0.0`
- `aiohttp==3.9.0` — async HTTP zum Backend
- `requests==2.31.0`
- `Pillow==10.4.0` — Karten-Bild-Rendering im Poker-Cog (PNG-Hole-Cards + Community-Board). **Optional zur Laufzeit:** [poker.py](bot/cogs/poker.py) fällt ohne Pillow auf Text-Karten zurück (`IMAGES_AVAILABLE`-Guard), crasht also nie.

### Backend — [backend/package.json](backend/package.json)
- Runtime: ESM (`"type": "module"`)
- `express ^4.18.2`, `cors ^2.8.5`
- `sqlite3 ^5.1.6`
- `dotenv ^16.3.1`
- `axios ^1.6.0` — für Discord-API-Calls
- `cookie-parser ^1.4.7` — liest `projectx_session`-Cookie
- `jsonwebtoken ^9.0.3` — signiert/verifiziert Session-JWT
- `express-session ^1.17.3`, `passport ^0.7.0`, `passport-oauth2 ^1.8.0` (legacy, **ungenutzt** — nicht entfernen ohne Abstimmung)
- **devDeps:** `nodemon ^3.1` — Watch-Mode mit Polling (`--legacy-watch`), weil `node --watch` auf X:\-Laufwerken (Windows, nicht-Standard-FS) mit `ECONNRESET` crasht.

### Frontend — [frontend/package.json](frontend/package.json)
- `vue ^3.3.4`, `vue-router ^4.2.4`
- `axios ^1.6.0`
- Build: `vite ^4.4.9`, `@vitejs/plugin-vue ^4.3.4`
- **Bewusst keine** Tailwind / Pinia / VueUse / UI-Kit — Styling vanilla via `<style scoped>` + `styles/tokens.css`.

### Android-App (Capacitor — wrappt das Frontend)
- `@capacitor/core ^6.1.2`, `@capacitor/cli ^6.1.2`, `@capacitor/android ^6.1.2` (Capacitor **6** — passt zu JDK 17; Cap 7 bräuchte JDK 21).
- Plugins: `@capacitor/app`, `@capacitor/status-bar`, `@capacitor/splash-screen`, `@capacitor/browser` (alle ^6).
- Dev-Tool: `@capacitor/assets ^3.0.5` (Icon-/Splash-Generierung aus `frontend/resources/`).
- **Architektur „Remote-URL":** Die native Hülle lädt **das deployte Dashboard (HTTPS)** in einer WebView (`server.url` in [frontend/capacitor.config.json](frontend/capacitor.config.json)) — KEIN gebundeltes Offline-Frontend. Grund: So bleiben HTTP-only-Session-Cookie und Discord-OAuth-Redirect unverändert funktionsfähig (alles same-origin in der WebView, kein Token-Umbau — respektiert das „kein localStorage-Token"-Verbot). `allowNavigation` enthält `discord.com`, damit der OAuth-Login in der WebView bleibt und das Cookie korrekt setzt.
- **Native Integration** in [frontend/src/native/capacitor.js](frontend/src/native/capacitor.js) (aus `main.js` aufgerufen) — auf dem Web ein **No-Op** (alles hinter `Capacitor.isNativePlatform()`): dunkle Statusbar, Splash-Hide, Hardware-Back → History/Exit, externe Links im System-Browser via `@capacitor/browser`. **Damit die nativen Features greifen, muss das deployte Web-Frontend das aktualisierte `main.js` enthalten (nach Änderungen neu deployen).**

> Beim Hinzufügen/Upgraden einer Dependency: diesen Block aktualisieren.

---

## 4. Commands (lokale Entwicklung)

PowerShell-Syntax (Windows). Bash-Tool ist auch verfügbar — siehe `# Environment`-Hinweis im Harness.

```powershell
# Backend (Port 3000)
cd X:\projectx\backend
npm install
npm run dev          # nodemon --legacy-watch server.js (Polling — Windows-Watch-Fix)
npm test             # node tests/db.test.js  (74/74 grün)
npm start            # production

# Frontend (Port 5173)
cd X:\projectx\frontend
npm install
npm run dev          # vite (mit server.watch.usePolling = true)
npm run build        # vite build → dist/
npm run preview      # vite preview

# Bot
cd X:\projectx\bot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Android-App (Capacitor)
Voraussetzungen: JDK 17, Android SDK (via Android Studio), `frontend/android/local.properties` mit `sdk.dir=...` (lokal, gitignored).
```powershell
cd X:\projectx\frontend
# 1) server.url in capacitor.config.json auf die DEPLOYTE Dashboard-Domain setzen
#    (Platzhalter: https://CHANGE-ME.example.com). Für Emulator-Dev gegen den
#    lokalen Vite-Server: "url": "http://10.0.2.2:5173", "cleartext": true.
npm run cap:sync     # vite build + cap sync android  (Web-Assets + Plugins → android/)
npm run cap:open     # öffnet android/ in Android Studio (dort Run/Build APK)
npm run cap:assets   # Icons/Splash aus frontend/resources/ neu generieren
npm run cap:run      # build + sync + auf angeschlossenem Gerät/Emulator starten

# APK per CLI (ohne Android Studio):
cd X:\projectx\frontend\android
.\gradlew.bat assembleDebug   # → app\build\outputs\apk\debug\app-debug.apk
```
Verifiziert: Debug-APK baut grün (Capacitor 6, JDK 17, AGP via Wrapper). Das generierte `frontend/android/`-Projekt ist committet (buildbar); Build-Artefakte/`local.properties`/Keystores sind gitignored.

### Docker (Production-like / Portainer)
```powershell
docker compose up --build
```
Services: `backend` (intern :3000, nicht published), `bot`, `frontend` (nginx serviert die SPA + reverse-proxyt `/api` → backend). **Kein `db`-Service** (SQLite ist dateibasiert; Persistenz über das Named Volume `projectx-data` an `/data`). Alle Dockerfiles liegen im Root und builden mit `context: .` (COPY aus `backend/`,`bot/`,`frontend/`). **VITE_*-Variablen sind Build-Args** (in `docker-compose.yml` unter `frontend.build.args`), nicht Runtime-Env. `VITE_BACKEND_URL=/api` hält Frontend+API same-origin (keine CORS-/Cookie-Probleme).
Portainer: als **Stack** aus dem Git-Repo deployen, Env-Vars im Stack setzen (siehe Kopf von [docker-compose.yml](docker-compose.yml)).
**TLS via Nginx Proxy Manager:** Der `frontend` ist **nicht** auf einen Host-Port gemappt, sondern hängt am externen Docker-Netzwerk `proxy`; NPM ([nginx-proxy-manager.yml](nginx-proxy-manager.yml), eigener Stack) leitet die Domain auf `frontend:80` und macht Let's-Encrypt-TLS. Netzwerk `proxy` muss einmalig in Portainer angelegt werden. **HTTPS ist Pflicht**, da `NODE_ENV=production` das Session-Cookie auf `Secure` setzt. Ohne NPM betreiben: `proxy`-Netz am `frontend` entfernen + `ports: ["8080:80"]` setzen.

---

## 5. Environment-Variablen

> Wenn eine neue Variable hinzugefügt wird, **hier UND in der jeweiligen `.env.example` ergänzen**.

### `bot/.env`
- `DISCORD_TOKEN` — Bot-Token
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `BACKEND_URL` — z. B. `http://localhost:3000`

> ⚠️ **Presence-Intent (kein Env, sondern Portal-Toggle):** Das `stats`-Cog zählt Online/Offline über `member.status` — dafür ist das **privilegierte Presence-Intent** nötig. In [main.py](bot/main.py) ist `intents.presences = True` gesetzt; zusätzlich muss es im **Discord Developer Portal** (Bot → Privileged Gateway Intents → Presence Intent) aktiviert werden, sonst zählt der Bot alle Member als offline. Auto-Create von Stats-Channels braucht außerdem `MANAGE_CHANNELS`, Temp-Voice zusätzlich `MOVE_MEMBERS`, Server-Backup/Restore zusätzlich `MANAGE_ROLES` (bereits enthalten) + `MANAGE_GUILD` (Server-Name/-Icon) — die Invite-Bitmask wurde auf `285223990` erhöht (= `268446742 | MOVE_MEMBERS | MANAGE_GUILD`).
- `BOT_API_KEY` — **muss identisch zu `backend/.env`** sein; wird als `X-Bot-Token`-Header an `/api/bot/*` gesendet. Generierung: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `DATABASE_URL` — Pfad zur SQLite-DB (i. d. R. nicht direkt genutzt; Bot liest via Backend)
- **Social-Notifications (alle optional — `social_notify`-Cog skippt Plattformen ohne Creds, crasht nie):**
  - `YOUTUBE_API_KEY` — nur nötig zum Auflösen von `@handle` → `UC…`-channelId und für best-effort Live-Erkennung. Neue-Video-Erkennung läuft per RSS (0 Quota, kein Key). Ohne Key muss die rohe `UC…`-ID eingegeben werden.
  - `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` — App-Access-Token (client_credentials) für Helix `Get Streams`.
  - `KICK_CLIENT_ID`, `KICK_CLIENT_SECRET` — App-Token (client_credentials) für die offizielle Kick-API.
  - `SOCIAL_POLL_INTERVAL` — Poll-Intervall in Sekunden (default `180`, hartes Minimum 30).
- **Premium / SKU (alle optional — `premium_sync`-Cog ist ohne SKU-IDs inert; Owner-Override im Dashboard greift trotzdem):**
  - `APPLICATION_ID` — Discord-App-ID für den Entitlements-Endpoint (default = `DISCORD_CLIENT_ID`).
  - `SKU_BASIC_ID`, `SKU_PRO_ID` — Premium-App-Subscription-SKU-IDs aus dem Dev-Portal; werden auf die Tiers `basic`/`pro` gemappt.
  - `PREMIUM_POLL_INTERVAL` — Entitlement-Poll-Intervall in Sekunden (default `300`, hartes Minimum 60).

### `backend/.env`
- `PORT` (default 3000)
- `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`
- `DISCORD_REDIRECT_URI`
- `FRONTEND_URL` — wird in CORS-Config genutzt und MUSS gesetzt sein, damit Cookies cross-origin funktionieren ([server.js:25-28](backend/server.js#L25-L28)).
- `DATABASE_URL` — z. B. `./bot.db`
- `SESSION_SECRET` — signiert das Session-JWT. **Kritisch.** Generierung: `node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"`.
- `BOT_API_KEY` — Shared Secret für Bot↔Backend. Identisch zu `bot/.env`.
- `OWNER_DISCORD_ID` — Discord-User-ID(s) des System-Owners. Schaltet `/api/admin/*` + das Dashboard-Admin-Panel frei (User/Guilds sperren). Komma-separiert für mehrere Owner. Der Owner kann nie selbst gesperrt werden. Leer = Admin-Panel deaktiviert.
- `NODE_ENV` — `development` | `production` (steuert u. a. `Secure`-Flag des Session-Cookies).

Beim Start warnt der Server laut (aber crasht nicht), wenn `SESSION_SECRET` oder `BOT_API_KEY` fehlen — siehe [server.js:15-20](backend/server.js#L15-L20).

### `frontend/.env`
- `VITE_BACKEND_URL` — z. B. `http://localhost:3000` oder `http://localhost:3000/api`
- `VITE_DISCORD_CLIENT_ID`
- `VITE_DISCORD_REDIRECT_URI`

Production-Pendants: `.env.production.backend`, `.env.production.bot`, `.env.production.frontend` (im Root, hidden).

---

## 6. Auth-Flow (verbindlicher Vertrag)

### Session-Modell
- **Cookie:** `projectx_session`, `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age=7d`.
  - `Secure=true` ausschließlich wenn `NODE_ENV === 'production'`.
- **Inhalt:** JWT signiert mit `SESSION_SECRET`, Payload `{ uid: <discord_user_id> }`, exp 7 Tage.
- **Discord-Access-/Refresh-Tokens** liegen ausschließlich in der `users`-Tabelle — sie verlassen den Backend-Prozess nicht und gehen nie ans Frontend.
- Middleware: [backend/middleware/session.js](backend/middleware/session.js) — exportiert `signSession`, `setSessionCookie`, `clearSessionCookie`, `requireSession`, `requireBotToken`.

### Frontend-Client
- `axios` mit `withCredentials: true` ([frontend/src/services/api.js](frontend/src/services/api.js)).
- Kein Authorization-Header, kein localStorage-Token.
- 401-Response → CustomEvent `projectx:unauthorized` + Redirect nach `/`.
- Auth-State im Singleton-Composable `useAuth()` ([frontend/src/stores/auth.js](frontend/src/stores/auth.js)): `status: 'unknown' | 'authenticating' | 'authenticated' | 'guest'`.

### Login-Sequenz
1. NavBar/Landing ruft `useAuth().loginWithDiscord()` → `window.location` auf Discord-OAuth-URL (`scope=identify email guilds`).
2. Discord redirected zurück nach `/auth/callback?code=…`.
3. [AuthCallback.vue](frontend/src/pages/AuthCallback.vue) sendet `POST /api/auth/callback { code }`.
4. Backend tauscht Code → Discord-Tokens, holt `/users/@me` + `/users/@me/guilds`, persistiert User + Tokens (inkl. `token_expires_at`), versöhnt `user_guilds` (Admin-Bit via `(BigInt(permissions) & 0x8n) !== 0n`, entfernt User-Guild-Rows für Guilds, die der User verlassen hat), setzt `projectx_session`-Cookie, antwortet `{ success: true, user: { id, username, avatar_url, email } }`.
5. Frontend speichert User im Store, `router.replace('/')`.

### Logout
- `POST /api/auth/logout` → Cookie wird gecleart. Frontend setzt `status = 'guest'`, navigiert nach `/`.

### Guild-Refresh (lazy)
- `POST /api/auth/refresh-guilds` (cookie-protected) → Backend refreshed Discord-Tokens serverseitig via `refresh_token` aus DB, holt Guilds neu, reconciliert.
- Bei Refresh-Fail: Session wird gecleart, 401.

### Bot↔Backend
- Bot sendet `GET /api/bot/guilds/:guild_id/settings` mit Header `X-Bot-Token: <BOT_API_KEY>`.
- Constant-Time-Vergleich (`crypto.timingSafeEqual`) in [middleware/session.js](backend/middleware/session.js).
- Response ist **rohes** Settings-Objekt (kein `{ success, settings }`-Envelope), damit der Bot direkt `welcome_enabled` etc. lesen kann.

### Anti-Replay / Defensive
- [AuthCallback.vue](frontend/src/pages/AuthCallback.vue) speichert den letzten konsumierten OAuth-Code in `sessionStorage`, um Refresh-Replay zu verhindern.

---

## 7. API-Übersicht (Backend)

Mount-Points aus [backend/server.js](backend/server.js):

| Mount | Datei | Schutz |
|---|---|---|
| `GET /api/health` | inline in server.js | offen |
| `/api/auth/*` | [backend/routes/auth.js](backend/routes/auth.js) | gemischt (siehe unten) |
| `/api/guilds/*` | [backend/routes/guilds.js](backend/routes/guilds.js) | `requireSession` + `requireGuildAccess` |
| `/api/guilds/:guild_id/settings/*` (welcome/leave) | [backend/routes/settings.js](backend/routes/settings.js) | `requireSession` + `requireGuildAccess` |
| `/api/guilds/:guild_id/settings/{autorole,logs,moderation}` | [backend/routes/modules.js](backend/routes/modules.js) | `requireSession` + `requireGuildAccess` |
| `/api/guilds/:guild_id/{channels,roles}` | [backend/routes/resources.js](backend/routes/resources.js) | `requireSession` + `requireGuildAccess` |
| `/api/guilds/:guild_id/social` | [backend/routes/social.js](backend/routes/social.js) | `requireSession` + `requireGuildAccess` |
| `/api/admin/*` | [backend/routes/admin.js](backend/routes/admin.js) | `requireSession` + `requireOwner` |
| `/api/bot/*` | [backend/routes/bot.js](backend/routes/bot.js) | `requireBotToken` (+ Guard: gesperrte Guilds → 403 auf `/guilds/:id/*`) |

### Endpoints (Vertrag — Shapes garantiert)

**Auth**
- `POST /api/auth/callback` — body `{ code }`. Setzt `projectx_session`-Cookie. → `{ success: true, user: { id, username, avatar_url, email, is_owner } }`. **Keine Tokens in Response.** Gesperrte User (außer Owner) → 403 `{ blocked: true }`, kein Cookie.
- `GET  /api/auth/me` — Cookie. → 200 `{ authenticated: true, user: { …, is_owner } }`, 401 `{ authenticated: false }`, oder 403 `{ authenticated: false, blocked: true }` (gesperrt, Cookie wird gecleart). `is_owner` kommt aus `OWNER_DISCORD_ID`.
- `POST /api/auth/logout` — Cookie. → `{ success: true }`, Cookie wird gecleart.
- `POST /api/auth/refresh-guilds` — Cookie. → `{ success: true }`. Refreshed Discord-Tokens + reconciled Guild-Liste.

**Guilds** (Cookie required)
- `GET /api/guilds` → `{ success: true, guilds: [...] }` — Array liegt unter `.guilds`!
  - **Filter:** liefert nur Guilds, in denen der User **Owner ODER Administrator** ist (`getUserManageableGuilds`). Member-only Memberships werden ausgeblendet.
- `GET /api/guilds/:id` → `{ success: true, guild }` — abgesichert mit `requireGuildAccess`, das jetzt ebenfalls Owner/Admin verlangt (Defense-in-Depth zum Listenfilter).
- `GET /api/guilds/:id/full` → `{ success: true, guild, settings }` — gleiche Schutzlogik.

**Welcome / Leave Settings** (Cookie required) — Body und Response enthalten **die vollständige erweiterte Shape**:
```js
{
  // Basis (legacy)
  welcome_enabled, welcome_channel_id, welcome_message,
  leave_enabled,   leave_channel_id,   leave_message,
  // Embed-Mode pro Seite
  welcome_use_embed,                    // bool — false: plain, true: embed
  welcome_embed: {                      // JSON-Spalte; parsed-Objekt
    title, description, color,          // color: '#RRGGBB' (invalid → '#5865F2')
    thumbnail, image,                   // URL oder '{user.avatar}' oder ''
    footer, show_timestamp,
    author_name, author_icon_url
  },
  welcome_ping_user,                    // bool — postet @-Mention als content
  welcome_dm_enabled, welcome_dm_message,// optional DM beim Beitritt (max 2000)
  welcome_delete_after,                 // 0..600 Sekunden; 0 = kein Auto-Delete
  // Leave (kein DM/Ping, User ist weg)
  leave_use_embed, leave_embed: { … },
  leave_delete_after                    // 0..600
}
```
- `GET    /api/guilds/:id/settings` → `{ success: true, settings: <full shape> }` (Defaults wenn keine Row).
- `PUT    /api/guilds/:id/settings` body = full shape → `{ success: true, message, settings }`. Backend coerced/validiert in `upsertGuildSettings` (Längen-Caps, Hex-Regex, URL-Form, Delete-Clamp).
- `PATCH  /api/guilds/:id/settings` body partial → merged + upsert.

**String-Caps (vom Backend erzwungen):** Title 256, Description 4096, Footer 2048, Author-Name 256, Plain-Message 1000, DM 2000. Color-Regex `/^#[0-9A-Fa-f]{6}$/`. URL-Felder akzeptieren `''`, `'{user.avatar}'` oder `https?://…`.

**Module-Settings — Auto-Role / Logs / Moderation** (Cookie required, jeweils Owner/Admin)
- `GET /api/guilds/:id/settings/autorole` → `{ success: true, settings: { enabled, role_ids: string[], apply_to_bots } }`
- `PUT /api/guilds/:id/settings/autorole` body matches → `{ success: true, message, settings }`
- `GET /api/guilds/:id/settings/logs` → `{ success: true, settings: { enabled, log_channel_id, log_joins, log_leaves, log_message_edits, log_message_deletes, log_member_bans } }`
- `PUT /api/guilds/:id/settings/logs` body matches → `{ success: true, message, settings }`. Log-Settings-Shape: `{ enabled, log_channel_id, log_joins, log_leaves, log_message_edits, log_message_deletes, log_member_bans, log_member_unbans, log_member_updates, log_channels, log_roles, log_voice, log_ignored_channel_ids: string[] }`.
- `GET /api/guilds/:id/settings/moderation` → `{ success: true, settings: { enabled, anti_spam_enabled, max_messages_per_10s, banned_words: string[], banned_word_action, mute_role_id, anti_invite, anti_link, filter_action, anti_mention, max_mentions, anti_caps, caps_percentage, timeout_duration, warn_threshold, warn_escalation_action, exempt_role_ids: string[], ignored_channel_ids: string[] } }`
- `PUT /api/guilds/:id/settings/moderation` body matches → `{ success: true, message, settings }` (Response ist die **re-gelesene** Row, damit geclampte Zahlen stimmen).

`banned_word_action`/`filter_action` Enum `'delete' | 'warn' | 'mute' | 'kick' | 'timeout'`; `warn_escalation_action` Enum `'mute' | 'kick' | 'ban' | 'timeout'`. PUT-Audit-Actions: `UPDATE_AUTOROLE_SETTINGS` / `UPDATE_LOG_SETTINGS` / `UPDATE_MODERATION_SETTINGS`. GET liefert bei leerer Row die Defaults aus `MODULE_DEFAULTS` in [db.js](backend/db.js).

**Bot-Intern** (`X-Bot-Token` header required) — alle liefern **rohes** Settings-Objekt ohne Envelope. Fehlender/falscher Header → 401. Fehlende `BOT_API_KEY`-Env → 500.
- `GET /api/bot/guilds/:guild_id/settings` → Welcome/Leave Settings
- `GET /api/bot/guilds/:guild_id/settings/autorole` → AutoRole-Settings
- `GET /api/bot/guilds/:guild_id/settings/logs` → Log-Settings
- `GET /api/bot/guilds/:guild_id/settings/moderation` → Moderation-Settings (volle erweiterte Shape inkl. Filter/Whitelist/Warn-Felder)
- `POST /api/bot/guilds/:guild_id/moderation/warn` body `{ user_id }` → `{ count, total, threshold, threshold_reached, escalation_action, timeout_duration }`. Erhöht den Warn-Zähler atomar; bei erreichter Schwelle eskaliert der Bot mit `escalation_action`. Wird vom `moderation`-Cog bei jedem Content-Filter-Verstoß aufgerufen (nur wenn `warn_threshold > 0`).
- `PUT /api/bot/presence` body `{ guild_ids: string[] }` → `{ success: true, present: N, absent: M, received: K }`. Setzt `guilds.bot_present = 1` für alle übergebenen Guild-IDs (sofern die Row existiert) und `= 0` für alle anderen Rows. Wird vom Bot-Cog `presence.py` aufgerufen (on_ready + on_guild_join/remove + 5min loop). Snowflake-Filter `^\d{15,25}$`.
- `PUT /api/bot/stats` body `{ guild_count, user_count, started_at }` → `{ success: true }`. Befüllt den In-Memory-Cache in [state/botStats.js](backend/state/botStats.js) für die Landing-Page. `started_at` ist unix-seconds (Bot setzt das einmal beim ersten `on_ready` und behält es über Reconnects hinweg). Wird zusammen mit `presence` alle 5 Minuten aufgerufen.
- `PUT /api/bot/premium` body `{ entitlements: [{ guild_id, tier, until? }] }` → `{ success, synced, downgraded }`. Bulk-Sync der Discord-SKU-Entitlements: setzt `source = 'sku'`-Premium für entitled Guilds und downgradet Guilds, deren SKU-Premium nicht mehr aktiv ist (Owner-`manual`-Premium bleibt unberührt). Vom `premium_sync`-Cog aufgerufen. Nicht unter dem `/guilds/:id`-Guard (guild-übergreifend).

**Admin** (Cookie required + Owner-only via `requireOwner`/`OWNER_DISCORD_ID`) — System-Owner sperrt User/Guilds, sieht System-Metriken, das Audit-Log, inspiziert Guilds und schaltet den Wartungsmodus.
- `GET  /api/admin/users?search=&limit=&offset=` → `{ success, users: [{ discord_id, username, email, avatar_url, blocked, blocked_reason, blocked_at, blocked_until, created_at }], total }`. Suche matcht Username/ID. Keine Tokens in der Response.
- `POST /api/admin/users/:user_id/block` body `{ blocked, reason?, until? }` → `{ success, user_id, blocked }`. `until` (unix-seconds, in der Zukunft) = Temp-Ban; ohne/abgelaufen = permanent. Der Owner kann nicht gesperrt werden (**400**). 404 wenn User unbekannt. Audit `ADMIN_BLOCK_USER`/`ADMIN_UNBLOCK_USER`.
- `GET  /api/admin/guilds?search=&limit=&offset=` → `{ success, guilds: [{ id, guild_name, guild_icon_url, bot_present, blocked, blocked_reason, blocked_at, blocked_until, premium_tier, premium_source, premium_until, premium_effective, created_at }], total }`.
- `POST /api/admin/guilds/:guild_id/block` body `{ blocked, reason?, until? }` → `{ success, guild_id, blocked }`. `until` = Temp-Ban (s. o.). 404 wenn Guild unbekannt. Audit `ADMIN_BLOCK_GUILD`/`ADMIN_UNBLOCK_GUILD`.
- `POST /api/admin/guilds/:guild_id/premium` body `{ tier ∈ {free|basic|pro}, until? }` → `{ success, guild_id, tier, until }`. Owner setzt den Tier manuell (`source = 'manual'`, `free` löscht Premium). 400 bei ungültigem Tier, 404 wenn Guild unbekannt. Audit `ADMIN_SET_PREMIUM`. `getAdminGuilds` liefert jetzt zusätzlich `premium_tier`/`premium_source`/`premium_until`/`premium_effective`.
- `GET /api/admin/overview` → `{ success, overview: { users:{total,blocked}, guilds:{total,bot_present,bot_absent,blocked}, premium:{free,basic,pro}, premium_expiring:[{id,guild_name,guild_icon_url,premium_tier,premium_until}], module_adoption:{[key]:count}, audit_last_24h } }`. Aggregierte System-Metriken (Premium-Counts expiry-aware). `getAdminOverview`.
- `GET /api/admin/audit?action=&target=&limit=&offset=` → `{ success, entries: [{ id, action, user_id, actor_username, guild_id, guild_name, changes, created_at }], total }`. Filterbarer globaler Audit-Feed (newest first; `target` matcht Actor-/Guild-ID oder Guild-Name). `GET /api/admin/audit/actions` → `{ success, actions: [...] }` (distinct Action-Namen fürs Filter-Dropdown). `getAuditLogEntries`/`getAuditActions`.
- `GET /api/admin/guilds/:guild_id/inspect` → `{ success, inspect: { id, guild_name, guild_icon_url, bot_present, blocked, blocked_reason, blocked_until, premium_tier, premium_source, premium_until, premium_effective, dashboard_members, created_at, modules:[{key,kind,enabled,configured,count?}] } }`. Read-only Modul-/Premium-/Presence-Snapshot (Support-Tool). 404 wenn Guild unbekannt. `getGuildInspect`.
- `GET /api/admin/maintenance` → `{ success, enabled, message }`. `PUT /api/admin/maintenance` body `{ enabled, message? }` → `{ success, enabled, message }`. Globaler Wartungsmodus. Audit `ADMIN_MAINTENANCE`. `getMaintenanceState`/`setMaintenanceState`.
- `GET /api/admin/users/export` + `GET /api/admin/guilds/export` → CSV-Download (`text/csv`, UTF-8 BOM). `getUsersForExport`/`getGuildsForExport`.

**Premium / Tiers** (Cookie required) — Modul-Gating Free/Basic/Pro (`MODULE_TIERS` in [db.js](backend/db.js) ist Single Source).
- `GET /api/guilds/:id/premium` → `{ success, tier, source, until, module_tiers: { key: tier }, modules: { key: bool } }`. Liefert dem Dashboard den effektiven Tier (abgelaufenes Premium → `free`) + die Unlock-Map pro Modul-Key (= Dashboard-Route-Segment).
- **Enforcement:** Cookie-Writes der Premium-Modul-Router laufen durch `requirePremiumModule(key)` ([middleware/premium.js](backend/middleware/premium.js)) → GET frei, PUT/POST/DELETE → **403 `{ error: 'premium_required', module, required_tier, current_tier }`** wenn der Tier nicht reicht (Leveling gated im eigenen Router, da bare-prefix-Mount). Guild-übergreifende Loop-Cog-Queries (social/stats/scheduled/birthday/rolemenus/giveaways) filtern via `tierFilterSql(minTier)` serverseitig; per-Guild Bot-GETs (leveling-xp/tempvoice/starboard/antiraid/tickets/invitetracking/applications/economy) liefern eine `disabled`-Shape über den zentralen `PREMIUM_BOT_GATES`-Guard in [bot.js](backend/routes/bot.js). **Frei:** welcome/leave/autorole/logs/moderation/reaction-roles/verification/suggestions/custom-commands/counting/polls. **Basic:** leveling/starboard/tempvoice/birthday/rolemenus/antiraid/invitetracking + Games-Kategorie (games/tictactoe/rps/trivia/connect4/hangman/poker — geteilte `/games`-Settings, Gate-Key `games`). **Pro:** social/stats/tickets/giveaways/scheduled/applications/economy/backup. **Backup** hat keinen Bot-Settings-GET → kein `PREMIUM_BOT_GATES`-Eintrag; stattdessen filtert `getDueBackupJobs()` serverseitig via `tierFilterSql('pro')`, sodass herabgestufte Guilds keine Snapshot-/Restore-Jobs mehr ausgeführt bekommen.

> **Enforcement gesperrter Entities:** Gesperrte **User** werden von `requireSession` (403 `{ blocked: true }`), `/auth/me` (403 + Cookie-Clear) und dem OAuth-Callback (403, kein Cookie) abgewiesen — der Owner ist immer ausgenommen. Gesperrte **Guilds** bleiben im Server-Picker sichtbar (`getUserManageableGuilds` liefert das `blocked`-Flag mit), werden dort aber rot umrandet + nicht klickbar gerendert ([Servers.vue](frontend/src/pages/Servers.vue)); `requireGuildAccess` liefert 403, die Bot-Endpoints unter `/api/bot/guilds/:id/*` liefern 403 (Bot wird dort inert), und alle guild-übergreifenden Loop-Cog-Queries (social/stats/tempvoice/birthday/scheduled/rolemenus/giveaways) filtern `blocked = 1` per `NOT IN (SELECT id FROM guilds WHERE blocked = 1)`.

**Public** (KEIN Auth — wird von der Landing-Page gefetched)
- `GET /api/public/stats` → `{ servers, users, uptime_seconds, online }`. Liest aus dem `botStats`-Cache. Wenn der letzte Bot-Stats-Push > 15min zurückliegt: `servers/users` werden auf 0 gesetzt und `online: false` zurückgegeben, damit das Frontend einen Offline-Indicator zeigen kann. `Cache-Control: public, max-age=30`.
- `GET /api/public/plans` → `{ currency, tiers: [{ key, price_monthly }], modules: [{ key, tier }] }`. Tarif-/Preis-Katalog (`PLAN_CATALOG` aus [db.js](backend/db.js)) für die Landing-Pricing-Sektion + Modul-Tier-Badges. `Cache-Control: public, max-age=300`.
- `GET /api/public/maintenance` → `{ enabled, message }`. Globaler Wartungsmodus-Status (kein Auth) — der `MaintenanceBanner` im Frontend pollt das alle 60s. `Cache-Control: public, max-age=15`.
- `PUT /api/bot/guilds/:guild_id/channels` body `{ channels: [{ id, name, type, parent_id, position }], guild_name?, guild_icon_url? }` → `{ success: true, count }`. Vollständiges Replace via `replaceGuildChannels` (DELETE + bulk INSERT in einer Transaktion). Items ohne snowflake-id / Name werden gedroppt. `type`-Enum `text|voice|category|announcement|forum|stage|thread` (fallback `text`). **Optional `guild_name` und `guild_icon_url` im Body**: triggern einen UPSERT der `guilds`-Row vor dem Channel-Replace, damit der FK-Constraint nicht knallt, wenn die Guild noch nicht in der DB ist (z. B. weil kein Dashboard-User dort eingeloggt war). Wird vom Bot-Cog `guild_sync.py` aufgerufen.
- `PUT /api/bot/guilds/:guild_id/roles` body `{ roles: [{ id, name, color, position, managed, is_default }], guild_name?, guild_icon_url? }` → `{ success: true, count }`. Gleiches Replace-Pattern + gleicher optionaler Guild-Seed. `color` als Integer (clamped `[0, 0xFFFFFF]`). `@everyone` wird mit `is_default: true` mitgesendet, damit der Dashboard-Read-Path es per Default ausfiltern kann.

**Resources** (Cookie required) — Channels & Roles für Dashboard-Dropdowns (statt Roh-Snowflake-Inputs). Beide Endpoints geben `[]` zurück, wenn der Bot noch nie synced hat (kein 404).
- `GET /api/guilds/:guild_id/channels` → `{ success: true, channels: [{ id, name, type, parent_id, position }] }`. Sortiert: Kategorien zuerst, dann Channels nach Parent gruppiert (`(parent_id IS NULL) DESC, parent_id ASC, position ASC, name ASC`).
- `GET /api/guilds/:guild_id/roles?include_default=0&include_managed=1` → `{ success: true, roles: [{ id, name, color, position, managed, is_default }] }`. Sortiert nach `position DESC`. `include_default=0` filtert `@everyone` raus (Default), `include_managed=0` blendet Integration-Rollen aus.

**Reaction Roles** (Cookie required) — Mehrere RR-Messages pro Guild, jede mit 1-25 Emoji↔Role-Mappings.
- `GET    /api/guilds/:id/reaction-roles` → `{ success, messages: [{ id, channel_id, message_id, name, exclusive, mappings: [{ emoji, role_id }] }] }`. `id` ist UUID v4 (intern, nicht Discord).
- `POST   /api/guilds/:id/reaction-roles` body `{ channel_id, message_id, name, exclusive, mappings }` → `{ success, message }`. Audit `RR_CREATE`.
- `PUT    /api/guilds/:id/reaction-roles/:rr_id` → updates; Mappings werden komplett ersetzt (delete + insert in einer Transaktion). Audit `RR_UPDATE`.
- `DELETE /api/guilds/:id/reaction-roles/:rr_id` → `{ success }`. Audit `RR_DELETE`.

**Leveling** (Cookie required)
- `GET /api/guilds/:id/settings/leveling` → `{ success, settings: { enabled, xp_per_message_min, xp_per_message_max, cooldown_seconds, level_up_channel_id, level_up_message, ignored_channel_ids, stack_role_rewards, rewards: [{ level, role_id }] } }`. Rewards inline.
- `PUT /api/guilds/:id/settings/leveling` body matches → `{ success, message, settings }`. Wenn `rewards` im Body kommt, wird die komplette Liste ersetzt. Audit `UPDATE_LEVELING_SETTINGS`.
- `GET /api/guilds/:id/leveling/leaderboard?limit=25&offset=0` → `{ success, leaderboard: [{ user_id, xp, level, messages, rank }], total }` (`total` = Anzahl Users mit `xp > 0`).

**Custom Commands** (Cookie required)
- `GET    /api/guilds/:id/custom-commands` → `{ success, commands: [{ id, trigger, response, match_type, enabled }] }`
- `POST   /api/guilds/:id/custom-commands` body `{ trigger, response, match_type?, enabled? }` → `{ success, command }`. Duplicate-Trigger → **409 `{ error: 'Trigger already exists' }`**. Audit `CC_CREATE`.
- `PUT    /api/guilds/:id/custom-commands/:cmd_id` body `{...}` → `{ success, command }`. Audit `CC_UPDATE`.
- `DELETE /api/guilds/:id/custom-commands/:cmd_id` → `{ success }`. Audit `CC_DELETE`.

**Command-Manager** (Cookie required) — Katalog der Built-in-Befehle + per-Guild Prefix/An-Aus. Liegt im selben Router wie Custom-Commands (literale Pfade vor `/:cmd_id` registriert).
- `GET /api/guilds/:id/custom-commands/catalog` → `{ success, prefix, catalog: [{ key, name, type ∈ {prefix|slash}, module, usage, description }], settings: { [key]: bool } }`. `catalog` = `BUILTIN_COMMANDS` aus [db.js](backend/db.js) (Single Source, `key` = qualified command name).
- `PUT /api/guilds/:id/custom-commands/prefix` body `{ prefix }` → `{ success, prefix }`. Sanitisiert (1–5 Zeichen, kein Whitespace, sonst `'!'`). Audit `COMMAND_PREFIX_UPDATE`.
- `PUT /api/guilds/:id/custom-commands/toggle/:key` body `{ enabled }` → `{ success, key, enabled }`. 404 wenn `key` unbekannt. Audit `COMMAND_TOGGLE`.

**Social Notifications** (Cookie required) — getrackte Creator-Accounts (YouTube/Twitch/Kick) pro Guild.
- `GET    /api/guilds/:id/social` → `{ success, subscriptions: [{ id, platform, account, account_id, display_name, channel_id, notify_live, notify_upload, mention_role_id, message_template, use_embed, embed, enabled, last_video_id, last_live, last_checked_at }] }`. `id` ist UUID v4.
- `POST   /api/guilds/:id/social` body `{ platform, account, channel_id, notify_live, notify_upload, mention_role_id, message_template, use_embed, embed, enabled }` → `{ success, subscription }`. `platform ∈ {youtube|twitch|kick|tiktok|instagram}`. Duplikat `(guild_id, platform, account)` → **409**. Audit `SOCIAL_CREATE`. Account wird normalisiert (`@`/Whitespace strip; Twitch/Kick lowercased).
- `PUT    /api/guilds/:id/social/:sub_id` body `{...}` → `{ success, subscription }`. Plattform-/Account-Wechsel **resettet** den Polling-State (`account_id`/`last_video_id`/`last_live`). 404 / 409 / Audit `SOCIAL_UPDATE`.
- `DELETE /api/guilds/:id/social/:sub_id` → `{ success }`. Audit `SOCIAL_DELETE`.

**Statistics** (Cookie required) — Stats-Channels + Verlaufs-Graphen pro Guild.
- `GET    /api/guilds/:id/stats` → `{ success, settings: { enabled, update_interval, category_id, auto_category, category_name }, counters: [{ id, type, channel_id, channel_kind, name_template, auto_create, position, enabled }] }`. `id` ist UUID v4. `type ∈ {members|humans|bots|online|offline|boosters|channels|roles}`, `channel_kind ∈ {voice|text}`. `category_id` = Ziel-Kategorie (existing-Pick oder bot-auto-created), `auto_category`/`category_name` für Auto-Create.
- `PUT    /api/guilds/:id/stats` body `{ enabled, update_interval, category_id, auto_category, category_name }` → `{ success, message, settings }`. `update_interval` in Minuten, clamp `[5,1440]`; `category_id` nur wenn Snowflake, sonst null. Audit `UPDATE_STATS_SETTINGS`.
- `POST   /api/guilds/:id/stats/counters` body `{ type, channel_id, channel_kind, name_template, auto_create, position, enabled }` → `{ success, counter }`. **400** wenn `auto_create` aus UND kein `channel_id`. Audit `STATS_COUNTER_CREATE`.
- `PUT    /api/guilds/:id/stats/counters/:cid` body `{...}` → `{ success, counter }`. 404 / Audit `STATS_COUNTER_UPDATE`.
- `DELETE /api/guilds/:id/stats/counters/:cid` → `{ success }`. Audit `STATS_COUNTER_DELETE`.
- `GET    /api/guilds/:id/stats/history?days=7` → `{ success, snapshots: [{ ts, members, humans, bots, online, offline, boosters }], days }`. `days` clamp `[1,90]`, `ts` unix-seconds, sortiert aufsteigend.

**Temp-Voice / Starboard / Suggestions** (Cookie required, settings-only) — alle `{ success, settings }` / PUT `{ success, message, settings }`. Audit `UPDATE_TEMPVOICE_SETTINGS` / `UPDATE_STARBOARD_SETTINGS` / `UPDATE_SUGGESTION_SETTINGS`.
- `GET|PUT /api/guilds/:id/tempvoice` → `{ enabled, hub_channel_id, category_id, name_template, user_limit }`
- `GET|PUT /api/guilds/:id/starboard` → `{ enabled, star_channel_id, emoji, threshold, self_star }`
- `GET|PUT /api/guilds/:id/suggestions` → `{ enabled, suggest_channel_id, upvote_emoji, downvote_emoji }`

**Birthday / Scheduled / Anti-Raid** (Cookie required) — Audit `UPDATE_BIRTHDAY_SETTINGS` / `SCHEDULED_*` / `UPDATE_ANTIRAID_SETTINGS`.
- `GET|PUT /api/guilds/:id/birthday` → `{ enabled, announce_channel_id, message_template, birthday_role_id }`; `GET /api/guilds/:id/birthday/list` → `{ birthdays: [{ user_id, month, day, year }] }`; `DELETE /api/guilds/:id/birthday/list/:user_id`.
- `GET /api/guilds/:id/scheduled` → `{ messages }`; `POST` / `PUT /:id` / `DELETE /:id` (Felder `channel_id, content, schedule_type ∈ {once|interval}, run_at, interval_seconds, enabled`; VALIDATION→400, 404).
- `GET|PUT /api/guilds/:id/antiraid` → `{ enabled, join_rate_count, join_rate_seconds, action ∈ {alert|kick|ban}, account_age_days, alert_channel_id }`.

**Verification / Role-Menus / Tickets / Giveaways** (Cookie required)
- `GET|PUT /api/guilds/:id/verification` → `{ enabled, channel_id, verified_role_id, message, button_label }`. Audit `UPDATE_VERIFICATION_SETTINGS`.
- `GET /api/guilds/:id/rolemenus` → `{ menus: [{ id, channel_id, message_id, name, menu_type ∈ {buttons|select}, exclusive, use_embed, embed: {…}, options: [{ role_id, label, emoji }] }] }`; `POST` / `PUT /:id` / `DELETE /:id`. Audit `ROLEMENU_*`. `use_embed` schaltet zwischen Auto-Liste (Embed aus Name + Rollen) und eigenem Embed (`embed`-JSON, gleiche Shape wie Welcome/Tickets), das im Backend via `sanitizeEmbed` validiert wird.
- `GET|PUT /api/guilds/:id/tickets` → volle Shape `{ enabled, panel_channel_id, category_id, support_role_id, ping_role_id, panel_message, button_label, transcript_channel_id, log_channel_id, panel_type, panel_embed, welcome_embed, naming_template, claim_enabled, close_confirm, rating_enabled, rating_mode }`; `GET /api/guilds/:id/tickets/list`. Audit `UPDATE_TICKET_SETTINGS`. **Ticket-Kategorien:** `GET /api/guilds/:id/tickets/categories` → `{ categories }`; `POST` / `PUT /categories/:cat_id` / `DELETE /categories/:cat_id` (Audit `TICKET_CATEGORY_CREATE|UPDATE|DELETE`, 404 wenn unbekannt).
- `GET /api/guilds/:id/giveaways` → `{ giveaways: [{ id, channel_id, message_id, prize, winners_count, ends_at, ended }] }`; `DELETE /:id`. Audit `GIVEAWAY_DELETE`.

**Bot-Intern Endpoints für v7-Module** (`X-Bot-Token` header required)
- `GET /api/bot/guilds/:id/reaction-roles` → `{ messages }` (raw, no envelope).
- `GET /api/bot/guilds/:id/settings/leveling` → raw Settings (ohne `rewards`).
- `GET /api/bot/guilds/:id/leveling/rewards` → `{ rewards }`.
- `POST /api/bot/guilds/:id/leveling/xp` body `{ user_id, channel_id }` → `{ granted, leveled_up, xp_gained, total_xp, new_level, role_rewards, announce_channel_id, announce_message_template }` ODER `{ granted: false }` (Cooldown / disabled / ignored channel). **`grantXp` läuft in einer `BEGIN IMMEDIATE`-Transaktion**, damit parallele Messages vom gleichen User nicht doppelt XP geben.
- `GET /api/bot/guilds/:id/custom-commands` → `{ commands }` (nur `enabled = 1`).
- `GET /api/bot/guilds/:id/commands` → `{ prefix, disabled: [keys] }` — per-Guild Command-Config (Custom-Prefix + deaktivierte Built-in-Befehle). Vom Bot (`utils/command_config.py`) gelesen, um Prefix aufzulösen und Befehle per Guild zu sperren.

**Bot-Intern Endpoints für v8 (Social Notifications)** (`X-Bot-Token` header required)
- `GET /api/bot/social/subscriptions` → `{ subscriptions }` — **alle** enabled Subscriptions über **alle** Guilds (inkl. Polling-State). Vom `social_notify`-Cog 1× pro Cycle gelesen.
- `PUT /api/bot/social/subscriptions/:sub_id/state` body `{ account_id?, display_name?, last_video_id?, last_live? }` → `{ success }`. Nur übergebene Keys werden geschrieben; `last_checked_at` wird serverseitig gestempelt. 404 wenn sub_id unbekannt.

**Bot-Intern Endpoints für v10/v11 (Statistics)** (`X-Bot-Token` header required)
- `GET /api/bot/stats/configs` → `{ configs: [{ guild_id, update_interval, category_id, auto_category, category_name, counters: [...] }] }` — **alle** Guilds mit aktiviertem Stats-Modul inkl. Kategorie-Config + enabled Counter. Vom `stats`-Cog 1× pro Cycle gelesen.
- `PUT /api/bot/guilds/:id/stats/category` body `{ category_id }` → `{ success }`. Speichert die vom Bot auto-erstellte Kategorie-ID zurück. 404 wenn keine Stats-Settings-Row.
- `PUT /api/bot/guilds/:id/stats/counters/:counter_id/channel` body `{ channel_id }` → `{ success }`. Speichert die vom Bot auto-erstellte `channel_id` zurück. 404 wenn Counter unbekannt.
- `POST /api/bot/guilds/:id/stats/snapshot` body `{ members, humans, bots, online, offline, boosters }` → `{ success }`. Insert + Prune (>90 Tage) via `insertStatsSnapshot` in einer Transaktion.

**Bot-Intern Endpoints für v12 (Temp-Voice / Starboard / Suggestions)** (`X-Bot-Token` header required, rohes Objekt)
- `GET /api/bot/guilds/:id/settings/{tempvoice,starboard,suggestions}` → raw Settings.
- `POST /api/bot/guilds/:id/tempvoice/channels` body `{ channel_id, owner_id }` / `DELETE /api/bot/guilds/:id/tempvoice/channels/:channel_id` — Tracking lebender Temp-Channels.
- `GET /api/bot/tempvoice/channels` → `{ channels }` — alle getrackten Temp-Channels (on_ready-Cleanup).
- `GET /api/bot/guilds/:id/starboard/entries/:message_id` → `{ entry|null }` / `PUT` body `{ channel_id, star_message_id, count }` / `DELETE` — Starboard-Entry-State.

**Bot-Intern Endpoints für v13 (Birthday / Scheduled / Anti-Raid)** (`X-Bot-Token` header required)
- `GET /api/bot/guilds/:id/settings/{birthday,antiraid}` → raw Settings.
- `POST /api/bot/guilds/:id/birthdays` body `{ user_id, day, month, year? }` → setzt Geburtstag (vom `!birthday`-Command). VALIDATION→400.
- `GET /api/bot/birthdays/today` → `{ birthdays }` (heute, server-berechnetes Datum, joined mit enabled Settings). `GET /api/bot/birthdays/role-guilds` → `{ guilds }` (enabled Guilds mit Geburtstags-Rolle, für den Rollen-Sweep).
- `GET /api/bot/scheduled/due` → `{ messages }` (fällig, alle Guilds). `PUT /api/bot/scheduled/:id/ran` → advance interval / disable once.

**Bot-Intern Endpoints für v14/v15 (Verification / Role-Menus / Tickets / Giveaways)** (`X-Bot-Token`)
- `GET /api/bot/guilds/:id/settings/{verification,tickets}` → raw Settings. `PUT .../verification/panel` / `.../tickets/panel` body `{ message_id }`.
- `GET /api/bot/rolemenus/pending` → `{ menus }` (konfiguriert, noch nicht gepostet). `PUT /api/bot/guilds/:id/rolemenus/:menu_id/message` body `{ channel_id, message_id }`.
- Tickets: `GET /api/bot/guilds/:id/settings/tickets` liefert jetzt **settings + enabled `categories`** (`getTicketConfig`). `GET .../tickets/open?user_id=` (Dedup), `GET .../tickets/by-channel?channel_id=` → `{ ticket }`, `POST .../tickets` body `{ channel_id, user_id, ticket_category_id? }` → `{ id, number }`, `PUT .../tickets/close` body `{ channel_id, closed_by? }`, `PUT .../tickets/claim` body `{ channel_id, user_id }`, `PUT .../tickets/rating` body `{ ticket_id, rating, comment? }` (per Ticket-ID, damit DM-Rating funktioniert), `PUT .../tickets/users` body `{ channel_id, add?:[], remove?:[] }`.
- Giveaways: `POST .../giveaways` body `{ channel_id, prize, winners_count, ends_at }` → `{ id }`; `PUT .../giveaways/:gid/message`; `POST .../giveaways/:gid/entries` body `{ user_id }`; `GET .../giveaways/:gid` → `{ giveaway }` (Reroll); `GET .../giveaways/:gid/entries` → `{ user_ids }`; `GET /api/bot/giveaways/due` → `{ giveaways }`; `PUT /api/bot/giveaways/:gid/ended`.
- Role-Menus: `GET /api/bot/guilds/:id/rolemenus/by-message/:message_id` → `{ menu }` (für exklusive Select-Auswertung).

**Server-Backup & Restore (v32, Pro)** — async Job-Queue (Bot pollt, Dashboard kann nicht pushen).
- Cookie (`requireSession` + `requireGuildAccess`, Premium-Gate `backup`): `GET /api/guilds/:id/backups` → `{ success, snapshots: [{ id, name, guild_name, guild_icon_url, channels_count, roles_count, created_at }], jobs: [{ id, type, status, backup_id, mode, message, created_at, updated_at }] }`; `GET /api/guilds/:id/backups/templates` → `{ success, sources: [{ guild_id, guild_name, guild_icon_url, snapshots: [...] }] }` (Snapshots **aller anderen vom User verwalteten** Server — für Server-Vorlagen); `GET /api/guilds/:id/backups/:backup_id` → `{ success, snapshot }` (voller Snapshot **inkl. `data`-Blob** für die Dashboard-Vorschau vor dem Restore, 404 wenn fehlt); `POST /api/guilds/:id/backups` → legt Snapshot-Job an, `{ success, job }` (Audit `BACKUP_SNAPSHOT_REQUEST`); `POST /api/guilds/:id/backups/apply-template` body `{ source_guild_id, backup_id, mode }` → wendet eine Vorlage von einem anderen Server an (verifiziert User-Zugriff auf BEIDE Guilds; legt Restore-Job auf der Ziel-Guild an), `{ success, job }`, 403/404 (Audit `BACKUP_APPLY_TEMPLATE`); `POST /api/guilds/:id/backups/:backup_id/restore` body `{ mode ∈ {missing|mirror} }` → Restore-Job, `{ success, job }`, 404 wenn Snapshot fehlt (Audit `BACKUP_RESTORE_REQUEST`); `DELETE /api/guilds/:id/backups/:backup_id` → `{ success }`, 404 (Audit `BACKUP_DELETE`).
  - **Cross-Server (Vorlagen):** Der Bot braucht dafür **keine** Änderung — `getDueBackupJobs()` joint `data` per `backup_id` (guild-übergreifend), und die Restore-Logik mappt Rollen per Name (legt fehlende an) + überspringt Member-Overwrites, die im Zielserver nicht existieren. Die Tier-Prüfung gilt für die **Ziel**-Guild (`j.guild_id`).
- Bot (`X-Bot-Token`): `GET /api/bot/backup/jobs/due` → `{ jobs }` (alle pending Jobs, restore-Jobs inkl. eingebetteter Snapshot-`data`; gefiltert via `tierFilterSql('pro')` + `blocked`); `PUT /api/bot/backup/jobs/:job_id` body `{ status, backup_id?, message? }` → `{ success }`; `POST /api/bot/guilds/:guild_id/backups` body `{ name, guild_name, guild_icon_url, data }` → `{ id }` (Bot speichert erstellten Snapshot; Retention max 15/Guild via `createBackup`).
- DB-Helfer in [db.js](backend/db.js): `createBackup`/`getBackups`/`getBackup`/`deleteBackup`, `createBackupJob`/`getActiveBackupJobs`/`getDueBackupJobs`/`updateBackupJob`; Konstanten `BACKUP_JOB_TYPES`/`BACKUP_JOB_STATUSES`/`RESTORE_MODES`/`BACKUP_MAX_PER_GUILD`. Snapshot-`data`-Shape: `{ server:{name,icon_url,verification_level}, roles:[{id,name,color,position,hoist,mentionable,permissions,managed,is_default}], channels:[{id,name,type,parent_id,position,topic,nsfw,slowmode,bitrate,user_limit,overwrites:[{target_id,target_type,allow,deny}]}] }`.

> ⚠️ **Feld-Konvention:** alle Settings-Keys sind `snake_case`. Wenn das Backend hier auf `camelCase` umstellen würde, müsste der Bot SYNCHRON angepasst werden.

---

## 8. Datenbank

- Engine: **SQLite3** (Datei via `DATABASE_URL`, default `./data/bot.db`)
- Connection: [backend/db.js](backend/db.js)
- Migrations: [backend/migrations.js](backend/migrations.js)
  - **Aktuelle Schema-Version: `32`**
  - `CURRENT_SCHEMA_VERSION` Konstante steuert Upgrades.
  - `applyMigrations(from, to)` mappt Versionsnummern → Migration-Funktionen (`migrationV1`, …, `migrationV32`). v23–v32 nutzen den `runSchemaBatch(version, statements)`-Helper.
  - Versionstabelle: `schema_version (version PK, applied_at)`.
  - `migrationV2` fügt `users.token_expires_at INTEGER` hinzu (idempotent).
  - `migrationV3` legt `guild_autorole_settings`, `guild_log_settings`, `guild_moderation_settings` an (`CREATE TABLE IF NOT EXISTS` — idempotent; werden parallel auch im `initializeDatabase()`-Pfad erzeugt, damit Fresh-DBs auch ohne Migrations-Run funktionieren).
  - `migrationV4` fügt `guilds.bot_present BOOLEAN DEFAULT 0` hinzu (idempotent — ignoriert „duplicate column"). Fresh-DBs bekommen die Spalte zusätzlich direkt im `CREATE TABLE`-Block in [db.js](backend/db.js).
  - `migrationV5` erweitert `guild_settings` um 9 neue Spalten für Embed/DM/Auto-Delete (alle idempotent): `welcome_use_embed`, `welcome_embed` (TEXT/JSON), `welcome_ping_user`, `welcome_dm_enabled`, `welcome_dm_message`, `welcome_delete_after`, `leave_use_embed`, `leave_embed`, `leave_delete_after`. Fresh-DBs bekommen die Spalten zusätzlich direkt im `CREATE TABLE`-Block.
  - `migrationV6` legt `guild_channels` und `guild_roles` an (`CREATE TABLE IF NOT EXISTS` — idempotent), inkl. Indizes `idx_guild_channels_guild` und `idx_guild_roles_guild` auf `guild_id`. Beide Tabellen haben `id TEXT PRIMARY KEY` (Discord-Snowflake) und FK auf `guilds(id) ON DELETE CASCADE`. Werden parallel auch im `initializeDatabase()`-Pfad erzeugt.
  - `migrationV7` legt 6 Tabellen für Reaction Roles, Leveling und Custom Commands an (alle idempotent): `guild_reaction_role_messages` (`id TEXT PK` als UUID v4, `idx_rr_guild`), `guild_reaction_role_mappings` (FK CASCADE auf RR-Messages), `guild_leveling_settings`, `guild_leveling_users` (composite PK `(guild_id, user_id)`, `idx_lvl_users_guild_xp` für Leaderboard), `guild_leveling_rewards`, `guild_custom_commands` (`idx_cc_guild`, UNIQUE `(guild_id, trigger)`).
  - `migrationV8` legt `guild_social_subscriptions` an (`id TEXT PK` als UUID v4, FK CASCADE auf `guilds`, `idx_social_subs_guild`, UNIQUE `(guild_id, platform, account)`) — Social-Notifications-Modul. Idempotent + Mirror in `initializeDatabase()`.
  - `migrationV9` erweitert **Moderation** + **Server-Logs** (alle ALTERs idempotent, „duplicate column" geschluckt; Mirror in `initializeDatabase()`):
    - `guild_moderation_settings` +12 Spalten: `anti_invite`, `anti_link`, `filter_action`, `anti_mention`, `max_mentions`, `anti_caps`, `caps_percentage`, `timeout_duration`, `warn_threshold`, `warn_escalation_action`, `exempt_role_ids` (JSON), `ignored_channel_ids` (JSON).
    - `guild_log_settings` +6 Spalten: `log_member_updates`, `log_member_unbans`, `log_channels`, `log_roles`, `log_voice`, `log_ignored_channel_ids` (JSON).
    - Neue Tabelle `guild_moderation_warnings` (`(guild_id, user_id) PK`, `count`/`total`/`updated_at`, FK CASCADE) — persistenter Warn-Zähler für die Eskalation.
  - `migrationV10` legt 3 Tabellen für das **Statistics**-Modul an (alle idempotent, Mirror in `initializeDatabase()`): `guild_stats_settings` (`guild_id PK`, `enabled`, `update_interval`), `guild_stats_counters` (`id TEXT PK` als UUID v4, `idx_stats_counters_guild`, FK CASCADE), `guild_stats_snapshots` (`id AUTOINCREMENT`, `idx_stats_snap_guild_ts (guild_id, ts)`, FK CASCADE).
  - `migrationV11` erweitert `guild_stats_settings` um 3 Kategorie-Spalten (idempotent, „duplicate column" geschluckt; Mirror in `initializeDatabase()`): `category_id` (Ziel-Kategorie), `auto_category` (Bot legt Kategorie selbst an), `category_name` (Default `'📊 Statistics'`).
  - `migrationV12` legt 5 Tabellen für **Batch-1-Module** an (alle idempotent, Mirror in `initializeDatabase()`): `guild_tempvoice_settings` + `guild_tempvoice_channels` (Temp-Voice, `idx_tempvoice_channels_guild`), `guild_starboard_settings` + `guild_starboard_entries` (Starboard, PK `(guild_id, message_id)`), `guild_suggestion_settings` (Vorschläge). Alle FK CASCADE auf `guilds`.
  - `migrationV13` legt 4 Tabellen für **Batch-2-Module** an (idempotent, Mirror): `guild_birthday_settings` + `guild_birthdays` (PK `(guild_id, user_id)`, `idx_birthdays_md`), `guild_scheduled_messages` (`id` UUID, `idx_scheduled_guild`, `schedule_type ∈ {once|interval}`), `guild_antiraid_settings`.
  - `migrationV14` legt **Batch-3-A**-Tabellen an: `guild_verification_settings`, `guild_role_menus` (`id` UUID, `idx_role_menus_guild`) + `guild_role_menu_options` (FK CASCADE).
  - `migrationV15` legt **Batch-3-B**-Tabellen an: `guild_ticket_settings` + `guild_tickets` (`id` UUID, `idx_tickets_guild`), `guild_giveaways` (`id` UUID, `idx_giveaways_guild`) + `guild_giveaway_entries` (PK `(giveaway_id, user_id)`, FK CASCADE).
  - `migrationV16` (Batch-3-Erweiterungen, idempotente ALTERs + Mirror): `guild_ticket_settings.transcript_channel_id` (Transcript beim Schließen), `guild_role_menus.exclusive` (Select = Einzelauswahl, entfernt andere Menü-Rollen).
  - `migrationV17` (Owner-Admin-Moderation, idempotente ALTERs + Mirror): `users.blocked`/`blocked_reason`/`blocked_at` und `guilds.blocked`/`blocked_reason`/`blocked_at`. Erlaubt dem System-Owner, einzelne User und Guilds vom Dashboard/Bot auszusperren.
  - `migrationV19` (Command-Manager, idempotenter ALTER + neue Tabelle + Mirror): `guilds.command_prefix` (Default `'!'`, per-Guild Prefix für Built-in-Prefix-Befehle); neue Tabelle `guild_command_settings` (PK `(guild_id, command_key)`, `enabled`, FK CASCADE — nur Rows für umgeschaltete Befehle, Abwesenheit = aktiviert).
  - `migrationV20` (Rollen-Menü-Embed-Designer, idempotente ALTERs + Mirror): `guild_role_menus.use_embed` (Default 0 → Auto-Liste, legacy) und `guild_role_menus.embed` (TEXT/JSON, gleiche Embed-Shape wie Welcome/Tickets). Bei `use_embed = 1` postet der Bot das eigene Embed statt der auto-generierten Name+Rollen-Liste.
  - `migrationV21` (Premium-Tiers, idempotente ALTERs + Mirror): `guilds.premium_tier` (Default `'free'`), `guilds.premium_source` (`'sku'|'manual'|null`), `guilds.premium_until` (unix-seconds Ablauf, null = unbegrenzt). Steuert das Modul-Gating (Free/Basic/Pro). Effektiver Tier wird abgelaufen → `'free'` (siehe `effectiveTier` in [db.js](backend/db.js)).
  - `migrationV22` (Admin v2, idempotente ALTERs + neue Tabelle + Mirror): `users.blocked_until` + `guilds.blocked_until` (unix-seconds; null = permanente Sperre, sonst Temp-Ban-Ablauf — `isUserBlocked`/`isGuildBlocked` behandeln abgelaufene Sperren automatisch als „nicht gesperrt", kein Sweeper nötig); neue Tabelle `system_settings (key PK, value, updated_at)` — Key/Value-Store für den globalen Wartungsmodus.
  - `migrationV23` (Counting, Free): Tabelle `guild_counting_settings` (`guild_id PK`, `enabled`, `channel_id`, `current_count`, `last_user_id`, `high_score`, `reset_on_fail`, `count_emoji`). Idempotent + Mirror.
  - `migrationV24` (Polls, Free): `guild_polls` (`id` UUID, `options` JSON, `multi`, `ends_at`, `ended`, `idx_polls_guild`) + `guild_poll_votes` (PK `(poll_id, user_id, option_index)`, FK CASCADE). Idempotent + Mirror.
  - `migrationV25` (Invite-Tracking, Basic): `guild_invite_settings` (`guild_id PK`, `enabled`, `log_channel_id`, `message_template`), `guild_invites` (Cache PK `(guild_id, code)`), `guild_member_invites` (PK `(guild_id, user_id)`, `idx_member_invites_inviter`). Idempotent + Mirror.
  - `migrationV26` (Applications, Pro): `guild_application_forms` (`id` UUID, `questions` JSON ≤5, `review_channel_id`, `accepted_role_id`, `panel_message_id`, `idx_application_forms_guild`) + `guild_applications` (`id` UUID, `answers` JSON, `status ∈ {pending|accepted|denied}`, `idx_applications_guild`). Idempotent + Mirror.
  - `migrationV27` (Economy, Pro): `guild_economy_settings` (`guild_id PK`, `currency_name`/`currency_symbol`, `start_balance`, `daily_amount`, `work_min`/`work_max`/`work_cooldown`), `guild_economy_users` (PK `(guild_id, user_id)`, `balance`, `last_daily`/`last_work`, `idx_economy_users_balance`), `guild_economy_shop` (`id` UUID, `price`, `role_id`, `idx_economy_shop_guild`). Idempotent + Mirror.
  - `migrationV28` (Games-Kategorie, alle Basic): `guild_games_settings` (`guild_id PK`, gemeinsamer `games_channel_id` + pro-Spiel-Flags `tictactoe_enabled`/`rps_enabled`/`trivia_enabled`/`connect4_enabled`/`hangman_enabled`) + `guild_game_scores` (PK `(guild_id, user_id, game)`, `wins`/`plays`, `idx_game_scores_lb`). Eine geteilte Settings-Row + eine Scores-Tabelle für alle Spiele. Idempotent + Mirror.
  - `migrationV29` (Poker, Games-Kategorie): idempotenter ALTER `guild_games_settings.poker_enabled` (6. Spiel der Games-Kategorie, teilt sich `/games`-Settings + `guild_game_scores`). Mirror + defensiver ALTER in `initializeDatabase()`. `GAME_KEYS` in [db.js](backend/db.js) um `poker` erweitert.
  - `migrationV30` (Poker-Tisch-Design): idempotenter ALTER `guild_games_settings.poker_table_theme TEXT DEFAULT 'classic'` (per-Guild Filz-Design fürs gerenderte Tisch-Bild). Mirror + defensiver ALTER in `initializeDatabase()`. `POKER_THEMES` (`classic|midnight|crimson|charcoal|royal`) in [db.js](backend/db.js) ist Single Source (vom Backend validiert, vom Bot zum Rendern + von der Dashboard-Auswahl gespiegelt); `GAMES_DEFAULTS`/`shapeGames`/`upsertGamesSettings` um `poker_table_theme` erweitert.
  - `migrationV31` (Games-Sprache): idempotenter ALTER `guild_games_settings.games_language TEXT DEFAULT 'en'` (per-Guild Sprache für **alle** In-Game-Texte der Games-Kategorie). Mirror + defensiver ALTER in `initializeDatabase()`. `GAME_LANGUAGES` (`en|de|tr|ru|pl`) in [db.js](backend/db.js) ist Single Source (Backend-Validierung in `shapeGames`/`upsertGamesSettings`, vom Bot via [utils/game_i18n.py](bot/utils/game_i18n.py) zum Übersetzen + von der Dashboard-Auswahl gespiegelt); `GAMES_DEFAULTS`/`shapeGames`/`upsertGamesSettings` um `games_language` erweitert.
  - `migrationV32` (Server-Backup & Restore, Pro): legt 2 Tabellen an (idempotent + Mirror in `initializeDatabase()`): `guild_backups` (`id` UUID, FK CASCADE, `name`/`guild_name`/`guild_icon_url`/`channels_count`/`roles_count`/`data` JSON-Blob/`created_at`, `idx_backups_guild`) — gespeicherte Server-Snapshots; `guild_backup_jobs` (`id` UUID, FK CASCADE, `type ∈ {snapshot|restore}`, `status ∈ {pending|running|done|failed}`, `backup_id`, `mode ∈ {missing|mirror}`, `message`, `created_at`/`updated_at`, `idx_backup_jobs_status`) — asynchrone Job-Queue (Dashboard legt Job an, Bot pollt fällige, führt aus, meldet Status zurück; der Bot kann nicht gepusht werden).
  - `migrationV18` (Ticket-Überarbeitung, idempotente ALTERs + neue Tabelle + Mirror): `guild_ticket_settings` +10 Spalten (`panel_type ∈ {dropdown|buttons}`, `panel_embed`/`welcome_embed` JSON, `ping_role_id`, `naming_template`, `claim_enabled`, `close_confirm`, `rating_enabled`, `rating_mode ∈ {channel|dm|both}`, `log_channel_id`); `guild_tickets` +8 Spalten (`ticket_category_id`, `number`, `claimed_by`, `rating`, `rating_comment`, `closed_by`, `closed_at`, `extra_user_ids` JSON); neue Tabelle `guild_ticket_categories` (`id` UUID, `idx_ticket_categories_guild`, FK CASCADE) — Ticket-Typen mit Label/Emoji/Desc + Kategorie-/Support-Rollen-/Ping-Rollen-Override, Welcome-Text, `button_style`, Position, Enabled.

**Kern-Tabellen** (Details: [backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md), [backend/DATABASE_FUNCTIONS.md](backend/DATABASE_FUNCTIONS.md))
- `users` — Discord-User; `discord_id PK`, plus `access_token`, `refresh_token`, `token_expires_at` (unix-seconds), `blocked`/`blocked_reason`/`blocked_at`/`blocked_until` (Owner-Sperre; `blocked_until` = Temp-Ban-Ablauf, null = permanent)
- `guilds` — Discord-Server; `id PK`, `guild_name`, `guild_icon_url`, `enabled`, `bot_present` (1 wenn der Bot aktuell auf diesem Server ist — vom `presence`-Cog gesetzt), `blocked`/`blocked_reason`/`blocked_at`/`blocked_until` (Owner-Sperre; `blocked_until` = Temp-Ban-Ablauf), `premium_tier` (`free|basic|pro`), `premium_source` (`sku|manual|null`), `premium_until` (unix-seconds Ablauf) — Premium-Modul-Gating
- `user_guilds` — Many-to-Many (User ↔ Guild + `owner`/`admin` Bits)
- `guild_settings` — Welcome/Leave-Config pro Guild (inkl. `*_use_embed`, JSON-Spalten `*_embed`, `welcome_ping_user`, `welcome_dm_enabled`/`_message`, `*_delete_after`)
- `guild_autorole_settings` — `guild_id PK`, `enabled`, `role_ids` (JSON-string), `apply_to_bots`
- `guild_log_settings` — `guild_id PK`, `enabled`, `log_channel_id`, 10 per-event-Flags (joins/leaves/edits/deletes/bans/unbans/member_updates/channels/roles/voice) + `log_ignored_channel_ids` (JSON)
- `guild_moderation_settings` — `guild_id PK`, `enabled`, `anti_spam_enabled`, `max_messages_per_10s`, `banned_words` (JSON), `banned_word_action`, `mute_role_id`, `anti_invite`, `anti_link`, `filter_action`, `anti_mention`, `max_mentions`, `anti_caps`, `caps_percentage`, `timeout_duration`, `warn_threshold`, `warn_escalation_action`, `exempt_role_ids` (JSON), `ignored_channel_ids` (JSON)
- `guild_moderation_warnings` — `(guild_id, user_id) PK`, `count` (zur Schwelle), `total` (lifetime), `updated_at` — für Warn-Eskalation
- `guild_channels` — Discord-Channels-Cache pro Guild (Bot synct via `guild_sync`-Cog)
- `guild_roles` — Discord-Roles-Cache pro Guild
- `guild_reaction_role_messages` — RR-Konfiguration pro Discord-Message (`id` UUID, `exclusive`-Bit)
- `guild_reaction_role_mappings` — Emoji↔Role-Mappings per RR-Message (`emoji` als Unicode oder Custom-Snowflake)
- `guild_leveling_settings` — Leveling-Config pro Guild (XP-Range, Cooldown, Channel, Template, Ignored, Stack)
- `guild_leveling_users` — `(guild_id, user_id) PK` mit `xp`, `level`, `messages`, `last_xp_at` (unix-seconds)
- `guild_leveling_rewards` — `(level, role_id)`-Tupel pro Guild
- `guild_custom_commands` — `(guild_id, trigger) UNIQUE`, `match_type ∈ {exact|contains|starts_with}`, `response` (max 2000)
- `guild_command_settings` — `(guild_id, command_key) PK`, `enabled` — per-Guild An/Aus-Override für Built-in-Befehle (Command-Manager); `guilds.command_prefix` hält den per-Guild Prefix (Default `'!'`)
- `guild_social_subscriptions` — `id` UUID, `(guild_id, platform, account) UNIQUE`, `platform ∈ {youtube|twitch|kick|tiktok|instagram}`, `channel_id`, `notify_live`/`notify_upload`, `mention_role_id`, `message_template`, `use_embed`+`embed` (JSON), `enabled`, plus bot-gepflegter Polling-State `account_id`/`display_name`/`last_video_id`/`last_live`/`last_checked_at`
- `guild_stats_settings` — `guild_id PK`, `enabled`, `update_interval` (Minuten, clamp `[5,1440]`), `category_id` (Ziel-Kategorie), `auto_category`, `category_name` — Statistics-Modul
- `guild_stats_counters` — `id` UUID, `guild_id`, `type ∈ {members|humans|bots|online|offline|boosters|channels|roles}`, `channel_id` (null bis auto-created), `channel_kind ∈ {voice|text}`, `name_template` (`{count}`-Platzhalter), `auto_create`, `position`, `enabled`
- `guild_stats_snapshots` — `id AUTOINCREMENT`, `guild_id`, `ts` (unix-seconds), `members`/`humans`/`bots`/`online`/`offline`/`boosters` — Verlaufs-Snapshots für die Dashboard-Graphen (Retention 90 Tage)
- `guild_tempvoice_settings` — `guild_id PK`, `enabled`, `hub_channel_id`, `category_id`, `name_template` (`{user}`), `user_limit` — Temp-Voice
- `guild_tempvoice_channels` — `channel_id PK`, `guild_id`, `owner_id` — bot-gepflegte Liste lebender Temp-Channels (Empty-Cleanup über Restarts)
- `guild_starboard_settings` — `guild_id PK`, `enabled`, `star_channel_id`, `emoji` (Default `⭐`), `threshold`, `self_star` — Starboard
- `guild_starboard_entries` — `(guild_id, message_id) PK`, `channel_id`, `star_message_id`, `count` — Mapping Quell-Message → gepostete Starboard-Message
- `guild_suggestion_settings` — `guild_id PK`, `enabled`, `suggest_channel_id`, `upvote_emoji`, `downvote_emoji` — Vorschläge
- `guild_birthday_settings` — `guild_id PK`, `enabled`, `announce_channel_id`, `message_template` (`{user}`), `birthday_role_id` — Birthday
- `guild_birthdays` — `(guild_id, user_id) PK`, `month`, `day`, `year` (nullable) — gespeicherte Geburtstage
- `guild_scheduled_messages` — `id` UUID, `guild_id`, `channel_id`, `content`, `schedule_type ∈ {once|interval}`, `run_at` (unix), `interval_seconds`, `enabled`, `last_run` — geplante Nachrichten
- `guild_antiraid_settings` — `guild_id PK`, `enabled`, `join_rate_count`, `join_rate_seconds`, `action ∈ {alert|kick|ban}`, `account_age_days`, `alert_channel_id` — Anti-Raid
- `guild_verification_settings` — `guild_id PK`, `enabled`, `channel_id`, `verified_role_id`, `message`, `button_label`, `panel_message_id` — Verification
- `guild_role_menus` + `guild_role_menu_options` — Rollen-Menüs (`id` UUID, `menu_type ∈ {buttons|select}`, `exclusive` (Select-Einzelauswahl), `use_embed` + `embed` (JSON — eigenes Embed statt Auto-Liste), `message_id`; Optionen: `role_id`/`label`/`emoji`)
- `guild_ticket_settings` — `guild_id PK`, `enabled`, `panel_channel_id`, `category_id`, `support_role_id`, `ping_role_id`, `panel_message`, `button_label`, `panel_message_id`, `transcript_channel_id`, `log_channel_id`, `panel_type ∈ {dropdown|buttons}`, `panel_embed`/`welcome_embed` (JSON), `naming_template`, `claim_enabled`, `close_confirm`, `rating_enabled`, `rating_mode ∈ {channel|dm|both}` — Tickets
- `guild_ticket_categories` — `id` UUID, `guild_id`, `label`, `emoji`, `description`, `category_id`/`support_role_id`/`ping_role_id` (Overrides, nullable = erben), `welcome_message`, `button_style ∈ {primary|secondary|success|danger}`, `position`, `enabled` — Ticket-Typen fürs Panel
- `guild_tickets` — `id` UUID, `channel_id`, `user_id`, `status ∈ {open|closed}`, `ticket_category_id`, `number` (per-Guild-Zähler), `claimed_by`, `rating` (1–5), `rating_comment`, `closed_by`, `closed_at`, `extra_user_ids` (JSON — manuell hinzugefügte Member) — offene/geschlossene Ticket-Channels
- `guild_giveaways` + `guild_giveaway_entries` — Giveaways (`id` UUID, `prize`, `winners_count`, `ends_at`, `ended`; Entries PK `(giveaway_id, user_id)`)
- `audit_log` — Änderungs-Trail (vom Admin-Audit-Viewer gelesen: `getAuditLogEntries`/`getAuditActions`)
- `system_settings` — `key PK`, `value`, `updated_at` — globaler Key/Value-Store; aktuell `maintenance` (JSON `{enabled, message}`) für den Wartungsmodus
- `guild_counting_settings` — `guild_id PK`, `enabled`, `channel_id`, `current_count`, `last_user_id`, `high_score`, `reset_on_fail`, `count_emoji` — Counting (Free)
- `guild_polls` + `guild_poll_votes` — Umfragen (`id` UUID, `options` JSON, `multi`, `ends_at`, `ended`; Votes PK `(poll_id, user_id, option_index)`) (Free)
- `guild_invite_settings` + `guild_invites` (Use-Count-Cache) + `guild_member_invites` (Beitritts-Record/Leaderboard-Quelle) — Invite-Tracking (Basic)
- `guild_application_forms` (`questions` JSON ≤5, `review_channel_id`, `accepted_role_id`) + `guild_applications` (`answers` JSON, `status`, `reviewer_id`) — Bewerbungen (Pro)
- `guild_economy_settings` + `guild_economy_users` (`balance`, `last_daily`/`last_work`) + `guild_economy_shop` (`price`, optionale `role_id`) — Wirtschaft (Pro)
- `guild_games_settings` (eine Row, geteilter `games_channel_id` + pro-Spiel-Toggle inkl. `poker_enabled` + `poker_table_theme` Filz-Design + `games_language` In-Game-Sprache) + `guild_game_scores` (`(guild_id, user_id, game)`, `wins`/`plays`) — Games-Kategorie (Basic): Tic-Tac-Toe/RPS/Trivia/Connect-Four/Hangman/Poker
- `guild_backups` (`id` UUID, `name`, `guild_name`/`guild_icon_url`, `channels_count`/`roles_count`, `data` JSON-Blob mit `{server,roles,channels}`, `created_at`; Retention max 15/Guild) + `guild_backup_jobs` (`id` UUID, `type ∈ {snapshot|restore}`, `status`, `backup_id`, `mode ∈ {missing|mirror}`, `message`, `created_at`/`updated_at`) — Server-Backup & Restore (Pro)
- `schema_version` — Migrations-Tracking

**Wichtige DB-Helper** in [backend/db.js](backend/db.js):
- `upsertUser(discordId, { …, token_expires_at })`
- `updateUserTokens(discordId, access_token, refresh_token, token_expires_at)` — für `/auth/refresh-guilds`
- `addUserToGuild(userId, guildId, owner, admin)` — beide Flags werden tatsächlich gesetzt (admin aus Permissions-Bit)
- `removeUserGuildsNotIn(userId, keepGuildIds)` — Reconcile beim Login, parameterisiertes `NOT IN`, korrekt für `keepGuildIds = []`
- `getUserGuilds(userId)` — **alle** Memberships (intern, aktuell von keinem Endpoint genutzt)
- `getAutoroleSettings(guildId)` / `upsertAutoroleSettings(guildId, settings)` — JSON-Parse/Stringify für `role_ids`, Boolean-Coercion.
- `getLogSettings(guildId)` / `upsertLogSettings(guildId, settings)` — Boolean-Coercion aller per-event-Flags, JSON-Parse/Stringify für `log_ignored_channel_ids` (Snowflakes).
- `getModerationSettings(guildId)` / `upsertModerationSettings(guildId, settings)` — JSON-Parse/Stringify für `banned_words`/`exempt_role_ids`/`ignored_channel_ids`, Bounds-Checks (`max_messages_per_10s [1,100]`, `max_mentions [1,50]`, `caps_percentage [50,100]`, `timeout_duration [60,2419200]`, `warn_threshold [0,20]`), Enum-Validation via `MOD_ACTIONS` (delete|warn|mute|kick|timeout) und `MOD_ESCALATION_ACTIONS` (mute|kick|ban|timeout) — beide aus [db.js](backend/db.js) exportiert.
- `addModerationWarning(guildId, userId, now)` — erhöht den persistenten Warn-Zähler in **einer** `runInTransaction`-Transaktion, prüft `warn_threshold`. Bei Erreichen: `count` reset auf 0, `threshold_reached: true` + `escalation_action`/`timeout_duration` zurück. Aufgerufen vom `POST /api/bot/guilds/:id/moderation/warn`-Endpoint.
- `MODULE_DEFAULTS` (exportiert) — Single Source of Truth für die Default-Settings der Module (autorole/logs/moderation + welcome_leave + leveling + social + stats + tempvoice/starboard/suggestions + birthday/scheduled/antiraid + verification/rolemenus/tickets/giveaways), von [routes/modules.js](backend/routes/modules.js), [routes/settings.js](backend/routes/settings.js) und [routes/bot.js](backend/routes/bot.js) gemeinsam genutzt.
- `WELCOME_LEAVE_DEFAULTS` (exportiert) — Vollständige Default-Settings für Welcome/Leave inkl. Embed-Defaults (`color: '#5865F2'`, alle anderen Felder leer/0). Wird bei leerer Row zurückgegeben.
- `getGuildSettings`/`upsertGuildSettings` — Parsen/Stringifyen die JSON-Spalten `welcome_embed`/`leave_embed`, sanitisieren Strings (`truncate`), Farben (`sanitizeColor` Regex `/^#[0-9A-Fa-f]{6}$/`), URLs (`sanitizeUrlLike` — `''` / `'{user.avatar}'` / `https?://…`), Delete-After (`clampDeleteAfter` 0..600). Booleans → 0/1.
- `syncBotPresence(presentGuildIds)` — Bulk-Update in **einer** Transaktion: setzt `bot_present = 1` für alle Guilds in der Liste und `= 0` für alle anderen Rows. Wird vom `/api/bot/presence`-Endpoint aufgerufen.
- **Level-Math** (exportiert): `totalXpForLevel(n)` (MEE6-Curve `Σ 5i² + 50i + 100` für i in `[0, n)`), `levelFromXp(xp)`, `xpForNextLevel(currentLevel)`. Beispielwerte: Level 1 @ 100 XP, Level 5 @ 1150 XP.
- `grantXp(guildId, userId, now)` — **THE CORE für Leveling**. Liest Settings + User-Row, checkt Cooldown, würfelt XP-Granted, schreibt Row, rechnet altes vs. neues Level. Bei Level-Up: sammelt Reward-Roles für alle übersprungenen Levels; wenn `!stack_role_rewards` nur die höchste. **Alles in einer `BEGIN IMMEDIATE`-Transaktion**, damit parallele Messages kein Double-Grant erzeugen.
- `getReactionRoleMessages`/`createReactionRoleMessage`/`updateReactionRoleMessage`/`deleteReactionRoleMessage` — UUID-generiert via `crypto.randomUUID()`, Mappings werden bei Update komplett ersetzt (delete + insert in einer Transaktion).
- `getLevelingSettings`/`upsertLevelingSettings` mit JSON-Stringify für `ignored_channel_ids`, Range-Validation (xp 1–500, cooldown 0–600). `getLevelingRewards`/`setLevelingRewards` (Bulk-Replace). `getLeaderboard(guildId, limit, offset)` — sortiert by `xp DESC` mit dem `idx_lvl_users_guild_xp`-Index.
- `getCustomCommands`/`createCustomCommand`/`updateCustomCommand`/`deleteCustomCommand` — wirft auf UNIQUE-Violation; Route fängt → 409.
- **Social** (`SOCIAL_PLATFORMS`, `SOCIAL_DEFAULTS` exportiert): `getSocialSubscriptions(guildId)` (Dashboard), `getAllEnabledSocialSubscriptions()` (Bot, alle Guilds, inkl. State), `createSocialSubscription`/`updateSocialSubscription`/`deleteSocialSubscription` (UUID, Account-Normalisierung, Embed-Sanitize via `sanitizeEmbed`, UNIQUE→409; Update resettet State bei Plattform-/Account-Wechsel), `updateSocialSubscriptionState(subId, {account_id?,display_name?,last_video_id?,last_live?})` (bot-only, stempelt `last_checked_at`).
- **Statistics** (`STATS_COUNTER_TYPES`, `STATS_DEFAULTS` exportiert): `getStatsSettings`/`upsertStatsSettings` (clamp `update_interval`, Kategorie-Felder `category_id`/`auto_category`/`category_name`), `getStatsCounters`/`createStatsCounter`/`updateStatsCounter`/`deleteStatsCounter` (UUID, Enum-/`channel_kind`-Validation, `channel_id` Pflicht wenn `!auto_create` → VALIDATION→400), `getAllEnabledStatsConfigs()` (Bot, alle enabled Guilds + Kategorie-Config + Counter), `setStatsCounterChannel`/`setStatsCategory` (Bot schreibt auto-erstellte Channel-/Kategorie-IDs zurück), `insertStatsSnapshot` (Insert + Prune >90 Tage in einer Transaktion), `getStatsSnapshots(guildId, sinceTs)` (für Graphen).
- **Temp-Voice/Starboard/Suggestions** (`TEMPVOICE_DEFAULTS`/`STARBOARD_DEFAULTS`/`SUGGESTION_DEFAULTS` exportiert): `get*Settings`/`upsert*Settings` (Defaults statt null). Temp-Voice zusätzlich `addTempVoiceChannel`/`removeTempVoiceChannel`/`getAllTempVoiceChannels` (Bot-Tracking). Starboard zusätzlich `getStarboardEntry`/`upsertStarboardEntry`/`deleteStarboardEntry` (Bot, Count + gepostete Message). `clampRange(value,min,max,fallback)`-Helper für Zahlen.
- **Birthday/Scheduled/Anti-Raid** (`BIRTHDAY_DEFAULTS`/`SCHEDULED_TYPES`/`ANTIRAID_DEFAULTS`+`ANTIRAID_ACTIONS` exportiert): `get*Settings`/`upsert*Settings`. Birthday: `setBirthday`/`getGuildBirthdays`/`removeBirthday`/`getTodaysBirthdays(month,day)`/`getBirthdayRoleGuilds` (Bot). Scheduled: `getScheduledMessages`/`create`/`update`/`delete` (UUID, VALIDATION→400) + `getDueScheduledMessages(now)`/`markScheduledRan(id,now)` (Bot, rechnet next/disable).
- **Verification/Role-Menus/Tickets/Giveaways** (`VERIFICATION_DEFAULTS`/`ROLE_MENU_TYPES`/`TICKET_DEFAULTS` exportiert): `get*Settings`/`upsert*Settings` + `setVerificationPanelMessage`/`setTicketPanelMessage`. Role-Menus: `getRoleMenus`/`create`/`update`/`delete` (Options-Replace in `runInTransaction`), `getPendingRoleMenus`/`setRoleMenuMessage` (Bot). Tickets: `createTicket`/`getOpenTicketForUser`/`closeTicketByChannel`/`getGuildTickets`. Giveaways: `createGiveaway`/`setGiveawayMessage`/`addGiveawayEntry`/`getGiveawayEntries`/`getDueGiveaways`/`markGiveawayEnded`/`getGuildGiveaways`/`deleteGiveaway`.
- `getUserManageableGuilds(userId)` — Guilds mit `owner=1 OR admin=1` (inkl. gesperrter, das `blocked`-Flag wird mitgeliefert, damit das Frontend sie markieren kann). Für `GET /api/guilds`.
- **Owner-Admin** (V17): `isUserBlocked(discordId)`/`isGuildBlocked(guildId)` (Enforcement, **temp-ban-aware** via `isEffectivelyBlocked` — abgelaufenes `blocked_until` zählt als nicht gesperrt), `getAdminUsers({search,limit,offset})`/`getAdminGuilds(...)` (paginierte Listen, keine Tokens, liefern `blocked_until`), `setUserBlocked(id, blocked, reason, until?)`/`setGuildBlocked(id, blocked, reason, until?)` (stempelt `blocked_at`, kürzt Reason auf 500, `until` via `sanitizeBlockUntil` = zukünftiger unix-seconds-Wert oder null). Owner-Check liegt in der Middleware (`isOwner`/`requireOwner` aus [session.js](backend/middleware/session.js)), nicht in db.js.
- **Admin v2** (V22): `getAdminOverview()` (aggregierte Metriken — User/Guild-Counts, expiry-aware Premium-Verteilung, `premium_expiring` <7d, `module_adoption` via `FLAG_MODULE_TABLES`/`COUNT_MODULE_TABLES`, `audit_last_24h`), `getAuditLogEntries({action,target,limit,offset})`/`getAuditActions()` (Audit-Viewer mit Actor-/Guild-Join), `getGuildInspect(guildId)` (read-only Modul-/Premium-/Presence-Snapshot), `getSystemSetting`/`setSystemSetting` (Key/Value) + `getMaintenanceState`/`setMaintenanceState` (Wartungsmodus-JSON), `getUsersForExport`/`getGuildsForExport` (CSV). Interne Promise-Helfer `dbGet`/`dbAll`.
- **Premium / Tiers** (V21, exportiert): `PREMIUM_TIERS` (`['free','basic','pro']`), `tierRank(t)`, `MODULE_TIERS` (Modul-Key → min Tier, Single Source), `PLAN_CATALOG` (Preis-/Modul-Katalog für die Landing). Helfer: `effectiveTier(guildRow)` (abgelaufenes `premium_until` → `free`), `moduleUnlocked(tier, key)`, `moduleUnlockMap(tier)`, `getGuildPremium(guildId)`, `setGuildPremium(guildId, {tier, source, until})` (Owner/manual), `syncSkuEntitlements(entitlements)` (Bot/SKU — Bulk-Set + Downgrade lapsed sku, lässt `manual` unberührt, in `runInTransaction`), `tierFilterSql(minTier, col?)` (SQL-Fragment „effektiver Tier ≥ minTier", expiry-aware — in alle Premium-Bulk-Bot-Queries eingehängt).
- `userHasGuildAccess(userId, guildId)` — beliebige Membership (intern, nicht von der Middleware genutzt)
- `userIsGuildAdmin(userId, guildId)` — Owner/Admin-Check. Wird von `requireGuildAccess` verwendet.
- `runInTransaction(async () => { … })` — `BEGIN IMMEDIATE` + `COMMIT`/`ROLLBACK`. Pflicht für jeden Bulk-Write-Pfad (z. B. Reconcile), sonst dauert auf Windows ein Login mit 100+ Guilds >15s wegen fsync pro Row. **Serialisiert alle Transaktionen über eine interne Promise-Queue (`_txChain`)** — sqlite3 nutzt nur **eine** Connection und Transaktionen sind nicht verschachtelbar; ohne Queue werfen überlappende `BEGIN IMMEDIATE` (z. B. presence-/channel-/role-Sync gleichzeitig beim Bot-Start) `SQLITE_ERROR: cannot start a transaction within a transaction`. **Jede neue Transaktion MUSS über `runInTransaction` laufen** — keine eigenen `BEGIN`-Blöcke mehr (auch `syncBotPresence` nutzt es jetzt).

**Performance-Pragmas** (gesetzt in [db.js](backend/db.js) `initializeDatabase`):
- `PRAGMA foreign_keys = ON`
- `PRAGMA journal_mode = TRUNCATE` — **bewusst NICHT WAL.** Das Repo liegt auf `X:` (nicht-standard Volume — kein `Win32_LogicalDisk`-Eintrag, bricht File-Watcher). WAL nutzt eine memory-mapped `-shm`-Datei + spezielles File-Locking, das solche FS nicht können → `SQLITE_IOERR: disk I/O error` auf jedem Read/Write, sobald der WAL nicht checkpointbar ist. TRUNCATE ist ein Rollback-Journal mit reinem File-I/O und läuft überall; mit der `runInTransaction`-Queue bleiben Bulk-Writes schnell genug.
- `PRAGMA synchronous = NORMAL`
- `PRAGMA busy_timeout = 5000`

**Bei Schema-Änderung:**
1. Neue `migrationVN` in [backend/migrations.js](backend/migrations.js) hinzufügen (idempotent halten).
2. `CURRENT_SCHEMA_VERSION` inkrementieren.
3. `migrations`-Map erweitern.
4. `DATABASE_SCHEMA.md` aktualisieren.
5. **Diese CLAUDE.md aktualisieren** (Tabellenliste + Schema-Version im Datenbank-Abschnitt).

---

## 9. Konventionen

### Allgemein
- Auf Windows-Pfaden achten — Repo lebt unter `X:\projectx\…`. PowerShell ist Default-Shell.
- Niemals `.env`-Inhalte oder Secrets in Outputs, Commits oder Logs schreiben.
- Niemals neue Doku-Markdown-Dateien anlegen, wenn nicht explizit gewünscht — bestehende erweitern.

### Backend (Node.js, ESM)
- `import`/`export`, **kein** CommonJS.
- Routes sind als Express-Router pro Datei in `backend/routes/` zu pflegen.
- Auth: **immer** `requireSession` für User-Routes, **nie** den alten `verifyToken` (Discord-Re-Verification ist gestrichen). Für reine Guild-Access-Checks zusätzlich `requireGuildAccess` aus [middleware/auth.js](backend/middleware/auth.js).
- Bot-Routes: **immer** `requireBotToken`.
- DB-Aufrufe gehen über `db.js` / `utils/dbHelper.js` — keine inline-`sqlite3.Database`-Instanzen in Routes.
- Async-DB-Aufrufe als Promises (siehe `initializeSchemaVersion` als Vorlage).
- Fehler bubblen zum globalen Error-Handler in [server.js:72-75](backend/server.js#L72-L75) — kein doppeltes `res.status(500)` in Routes nötig.
- Secrets-Vergleiche **constant-time** (`crypto.timingSafeEqual` mit Length-Pre-Check).

### Bot (Python)
- Discord-Events in **Cogs** unter [bot/cogs/](bot/cogs/) — `main.py` bleibt schlank, lädt jedes Cog mit eigenem try/except.
- Backend-Calls async via `aiohttp.ClientSession` mit Timeout. **Neue Cogs nutzen den gemeinsamen Helper `fetch_bot_settings(backend_url, api_key, guild_id, module)` aus [bot/utils/backend.py](bot/utils/backend.py)** — kein eigener aiohttp-Boilerplate-Code mehr in Cogs. Ausnahme: `welcome_leave.py` ist legacy und nutzt eigenen Code (nicht refactoren ohne Abstimmung).
- **Settings werden ausschließlich über `/api/bot/*` mit `X-Bot-Token`-Header gelesen** — nicht über `/api/guilds/*`. Endpoint-Pfad pro Modul: `/api/bot/guilds/:id/settings` (welcome/leave), `/api/bot/guilds/:id/settings/autorole`, `/.../logs`, `/.../moderation`.
- Config wird in [bot/config.py](bot/config.py) zentralisiert via `python-dotenv` geladen.
- Admin-Befehle werden mit `@commands.has_permissions(administrator=True)` geschützt.
- Beim Hinzufügen eines neuen Cogs: in `main.py` per `await bot.load_extension('cogs.X')` mit try/except in den `on_ready`-Block einfügen.

### Frontend (Vue 3)
- Composition API (`<script setup>`).
- HTTP **immer** über [frontend/src/services/api.js](frontend/src/services/api.js) — kein direkter `axios.get` in Komponenten. Niemals `Authorization`-Header setzen — Auth läuft komplett über Cookies.
- Auth-State **ausschließlich** über `useAuth()` aus [stores/auth.js](frontend/src/stores/auth.js). Kein localStorage für Tokens. Kein `localStorage.getItem('discord_*')`.
- Routing zentral in [frontend/src/router/index.js](frontend/src/router/index.js); Guards warten via `auth.waitUntilResolved()` bevor sie entscheiden.
- Vite-Env-Variablen müssen mit `VITE_` prefixed sein.
- Styling: scoped CSS + Tokens aus [styles/tokens.css](frontend/src/styles/tokens.css). Keine CSS-Frameworks. Keine neuen UI-Kits ohne Abstimmung.
- Toasts über `useToast()`-Composable, nicht über lokale `message`-Refs.
- Welcome/Leave: vor jedem PUT die **vollständige** erweiterte Settings-Shape mergen (via `stores/guildSettings.js`), damit die jeweils andere Kategorie nicht überschrieben wird. Die nested Embed-Objekte (`welcome_embed`, `leave_embed`) werden **deep-merged** gegen `defaultEmbed()` — sonst würde ein Welcome-Edit das Leave-Embed wegblasen.
- Placeholder-Helper-Liste lebt in [components/embedPlaceholders.js](frontend/src/components/embedPlaceholders.js) (export `PLACEHOLDERS` + `insertAtCaret(el, current, token)`). Nutze diese auch in neuen Forms mit Text-Templates; nie eigene Placeholder-Listen anlegen.
- **i18n**: alle user-sichtbaren Strings laufen über `t('key')` aus [`useI18n()`](frontend/src/i18n/index.js). Quell-Sprache ist EN; **5 Sprachen gleichwertig gepflegt: EN, DE, TR (Türkçe), RU (Русский), PL (Polski)** — je 1088 Keys, **Key-Parität ist Pflicht** (alle Locales müssen exakt dieselben Key-Pfade haben). **Beim Hinzufügen neuer UI-Strings**: Key in **allen fünf** Locales (en/de/tr/ru/pl.js) ergänzen — fehlt ein Key, fällt der `t()`-Lookup automatisch auf EN zurück, aber das ist Bug-Verhalten, nicht der Soll-Zustand. Platzhalter-Tokens (`{count}` etc.) müssen in jeder Übersetzung erhalten bleiben. `SUPPORTED_LOCALES` in [index.js](frontend/src/i18n/index.js) ist die Liste fürs Dropdown. Reactive: `locale.value` wird in `t()` gelesen, jede Template-Stelle aktualisiert sich automatisch bei Sprachwechsel. HTML-Strings (z. B. `messageHintHtml`) mit `v-html` rendern.

### Git/Workflow
- Sekret-Dateien (`.env`, `.env.production.*`, `bot.db`) **nie** stagen.
- `node_modules/`, `dist/`, `__pycache__/`, `venv/` sind ausgeschlossen.

---

## 10. Testing

- **Backend:** `npm test` führt [backend/tests/db.test.js](backend/tests/db.test.js) aus (74/74 grün), ergänzt durch [backend/tests/verify.js](backend/tests/verify.js).
  - `[DB ERROR]`-Zeilen im Output sind erwartet — der Test triggert bewusst UNIQUE/FK-Fehler, um `handleDbError` zu prüfen.
- **Manuell:** [TEST_PLAN.md](TEST_PLAN.md) listet die End-to-End-Checks.
- **Integration-Status:** [INTEGRATION_TESTING_STATUS.md](INTEGRATION_TESTING_STATUS.md).
- **Verification:** [VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md).
- Frontend hat aktuell keine automatisierten Tests — UI-Änderungen müssen lokal im Browser verifiziert werden (Dev-Server + Klick-Test der goldenen Pfade) oder zumindest via `npm run build`.

---

## 11. Deployment

- Production-Guide: [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)
- Pre-Deploy-Checks: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- Container-Stack: [docker-compose.yml](docker-compose.yml) + `Dockerfile.{backend,bot,frontend}` + [nginx.conf](nginx.conf)
- Production-Env-Files: `.env.production.{backend,bot,frontend}` im Root

**Produktion-Hinweise speziell zu Auth:**
- `NODE_ENV=production` setzt `Secure=true` am Session-Cookie → erfordert HTTPS.
- `FRONTEND_URL` und Backend-Origin müssen so gesetzt sein, dass Cookies cross-origin gesendet werden (Same-Site oder vollständig konfiguriertes CORS).
- `SESSION_SECRET` muss in Production **stark zufällig** sein. Rotation invalidiert alle aktiven Sessions.
- `BOT_API_KEY` muss in Production **stark zufällig** sein und in Bot+Backend identisch konfiguriert.

Empfehlung aus [README.md](README.md): SQLite → PostgreSQL für Multi-Instance, Redis für Cache, HTTPS via Let's Encrypt, PM2/systemd, Rate-Limiting, Sentry.

---

## 12. Troubleshooting (Kurzform)

| Symptom | Erste Anlaufstelle |
|---|---|
| Bot sendet keine Nachricht | `welcome_enabled` true? `welcome_channel_id` gesetzt? Bot online? Channel-Permissions? **`BOT_API_KEY` in beiden .env identisch?** |
| Bot bekommt 401 von `/api/bot/...` | `BOT_API_KEY` nicht gesetzt oder unterschiedlich zwischen `bot/.env` und `backend/.env`. |
| Bot bekommt 500 von `/api/bot/...` | `BOT_API_KEY` ist im Backend nicht gesetzt — Server lehnt aus Sicherheit ab. |
| 503 vom Backend | DB noch nicht ready — siehe [server.js:57-63](backend/server.js#L57-L63) |
| Frontend wird auf `/` zurückgeworfen / `/auth/me` 401 | Cookie nicht gesetzt: meist CORS-Origin-Mismatch oder `withCredentials` fehlt. `FRONTEND_URL` im Backend prüfen. |
| Session-Cookie kommt nicht an | In Dev: `Secure=false` ist korrekt; falls in Prod: HTTPS-Endpunkt? `SameSite` korrekt? |
| OAuth-Callback schlägt fehl | Redirect-URI in Discord-App **und** beiden `.env`-Dateien identisch? |
| `VITE_*` nicht in Frontend lesbar | Prefix `VITE_` vergessen oder Dev-Server nicht neugestartet |
| Migrations-Fehler | `schema_version`-Tabelle prüfen, `bot.db` ggf. löschen (Dev only!) |
| Admin-Badge fehlt im Frontend | Sicherstellen, dass User sich seit dem Auth-Rewrite mindestens einmal neu eingeloggt hat (Admin-Bit wird erst seit Migration v2 / Auth-Rewrite gesetzt). |
| `ECONNRESET, watch` crasht `npm run dev` (Backend oder Frontend) | Windows + nicht-Standard-Laufwerk (z. B. `X:\` ist `subst`-Mount, externe Disk, OneDrive, Netzwerkshare). Backend nutzt deshalb `nodemon --legacy-watch` (Polling), Frontend hat `server.watch.usePolling: true` in [vite.config.js](frontend/vite.config.js). Beides aktiv lassen. Alternative: Projekt nach `C:\` umziehen. |
| Bot loggt `Cannot connect to host localhost:3000` obwohl Backend läuft | Windows-IPv6/IPv4-Dual-Stack-Problem: Node bindet ohne expliziten Host gerne nur auf `::` (IPv6), aber Python aiohttp löst `localhost` zu `127.0.0.1` (IPv4) auf → Connection-Refused. Fix in [server.js](backend/server.js): `app.listen(PORT, '0.0.0.0', …)`. Quick-Check: `Get-NetTCPConnection -LocalPort 3000 -State Listen` — wenn `LocalAddress :: ` allein steht, fehlt der IPv4-Bind. |
| Bot bekommt HTTP 500 bei `PUT /api/bot/guilds/:id/channels` oder `/roles` | FK-Verletzung auf `guild_channels.guild_id → guilds(id)`. Tritt auf, wenn der Bot eine Guild syncen will, in der noch nie ein Dashboard-User OAuth-eingeloggt war (also keine `guilds`-Row existiert). Fix bereits aktiv: Bot schickt im Body `guild_name` + `guild_icon_url` mit, Backend macht UPSERT auf `guilds` vor dem Replace. Falls trotzdem 500 → Backend-Log mit Stack-Trace prüfen (logs `error.stack` jetzt). |
| `SQLITE_ERROR: cannot start a transaction within a transaction` (z. B. „Bot presence sync error") | Überlappende Transaktionen auf der einen sqlite3-Connection (mehrere Cogs syncen gleichzeitig beim Bot-Start). Fix aktiv: `runInTransaction` serialisiert über `_txChain`, `syncBotPresence` nutzt es. **Niemals** eigene `BEGIN IMMEDIATE`-Blöcke schreiben — immer `runInTransaction`. |
| `Extension 'cogs.X' is already loaded` (alle Cogs nach einem Reconnect) | Cogs wurden früher in `on_ready` geladen, das bei jedem Gateway-Reconnect / `session invalidated` erneut feuert. **Fix aktiv:** Laden + `tree.sync()` liegen in `setup_hook` (läuft genau 1× beim Start); `on_ready` loggt nur noch. Niemals `load_extension` in `on_ready` legen. |
| `SQLITE_IOERR: disk I/O error` auf **allen** Backend-Reads (Bot bekommt überall 500) | WAL-Mode auf dem `X:`-Volume (nicht-standard FS). WALs `-shm`-mmap + Locking scheitern dort, sobald der WAL nicht checkpointbar ist. **Fix aktiv:** `journal_mode = TRUNCATE` (Rollback-Journal) in [db.js](backend/db.js) — niemals zurück auf WAL stellen. Recovery falls `bot.db-wal`/`-shm` übrig sind: Backend stoppen, dann der **erste** Connect mit TRUNCATE-Code checkpointet den WAL automatisch in `bot.db` und entfernt `-wal`/`-shm` (Daten bleiben erhalten); im Notfall `bot.db`+`-wal`+`-shm` auf ein lokales `C:`-Verzeichnis kopieren, dort checkpointen, zurückkopieren. |

---

## 13. Was Claude NICHT tun soll

- Keine `.env`-Dateien lesen, sofern nicht explizit angefragt — und bei Zustimmung niemals den Inhalt in Antworten zurückgeben.
- Keine `bot.db` / `data/`-Inhalte löschen oder überschreiben ohne explizite Anweisung.
- Keine neuen Markdown-Doku-Dateien anlegen (Doku ist üppig genug — Bestehendes erweitern).
- Keine Dependency-Updates „nebenbei" einschmuggeln (z. B. bei einem Bugfix nicht `vue` upgraden).
- Keine Sprache wechseln, wenn der User Deutsch verwendet — Antworten und Commits in Deutsch halten, sofern der User nicht umsteigt.
- Keine destruktiven Git-Operationen ohne ausdrückliche Zustimmung.
- Keine localStorage-Tokens im Frontend wieder einführen — Auth läuft **ausschließlich** über das HTTP-only Session-Cookie.
- Den alten `verifyToken`-Middleware-Pfad **nicht** wiederbeleben — `requireSession` ist die einzige User-Auth-Middleware.
- Keine Tailwind / Pinia / VueUse / UI-Kits ohne Abstimmung hinzufügen — Frontend bleibt vanilla.
- Discord-Access-/Refresh-Tokens dürfen **nie** in API-Responses ans Frontend gelangen.

---

## 14. Letzte Aktualisierung

- **Datum:** 2026-06-22
- **Server-Vorlagen (Cross-Server-Backup, kein Schema-Change):** Erweiterung des Backup-Moduls — ein Snapshot von **einem** Server kann als **Vorlage** auf einen **anderen** Server angewendet werden (Rollen + Channels + Struktur kopieren).
  - **Backend** ([backup.js](backend/routes/backup.js)): `GET /backups/templates` (listet Snapshots aller anderen vom User verwalteten Server) + `POST /backups/apply-template {source_guild_id, backup_id, mode}` (verifiziert `userIsGuildAdmin` für **Quelle UND Ziel**, legt einen Restore-Job auf der Ziel-Guild an, Audit `BACKUP_APPLY_TEMPLATE`). **Kein Bot-/Schema-Change**: `getDueBackupJobs()` joint die Snapshot-`data` bereits guild-übergreifend per `backup_id`, und die Restore-Logik mappt Rollen per Name + überspringt fremde Member-Overwrites; die Pro-Prüfung gilt für die Ziel-Guild.
  - **Frontend** ([Backup.vue](frontend/src/pages/Backup.vue)): Header-Button „Vorlage anwenden" → Modal mit Quell-Server-Dropdown → Snapshot-Dropdown → Modus (missing/mirror) → Anwenden. i18n `backup.template*` (11 Keys) in **allen 5 Sprachen** (Key-Parität 1327/Locale).
  - Verifiziert: backup.js-Syntax OK, i18n-Parität 1327/Locale, Frontend-Build grün.
- **Server-Backup & Restore (Schema v32, Tier Pro):** Neues 33. Modul — speichert manuelle Snapshots der kompletten Server-Struktur und stellt sie wieder her, falls Channels/Rollen gelöscht werden.
  - **Architektur (Job-Queue):** Snapshot-Inhalt + Channel-/Rollen-Erstellung kann nur der Bot (Live-Guild + Discord-Rechte); das Dashboard kann den Bot nicht pushen. Daher async **Job-Queue** (analog `scheduled`): Dashboard legt Job an → Bot pollt fällige Jobs alle 20s → führt aus → meldet Status zurück.
  - **Schema:** Migration v32 = 2 Tabellen (`guild_backups` Snapshots mit JSON-`data`-Blob + Retention max 15/Guild, `guild_backup_jobs` Queue), idempotent + Mirror in `initializeDatabase()`. db.js-Helfer `createBackup`/`getBackups`/`getBackup`/`deleteBackup` + `createBackupJob`/`getActiveBackupJobs`/`getDueBackupJobs`/`updateBackupJob` + Konstanten. `MODULE_TIERS.backup = 'pro'`.
  - **Backend:** neue Cookie-Route [backup.js](backend/routes/backup.js) (`GET /backups` Liste+Jobs, `POST` Snapshot-Job, `POST /:id/restore {mode}`, `DELETE /:id`; Audit `BACKUP_*`), Pro-Gate-Mount in [server.js](backend/server.js), 3 Bot-Endpoints in [bot.js](backend/routes/bot.js) (`GET /backup/jobs/due`, `PUT /backup/jobs/:id`, `POST /guilds/:id/backups`). `getDueBackupJobs()` filtert via `tierFilterSql('pro')` + `blocked` (kein `PREMIUM_BOT_GATES`-Eintrag nötig).
  - **Bot:** neues Cog [server_backup.py](bot/cogs/server_backup.py) (34 Cogs gesamt). Snapshot serialisiert Rollen (inkl. `permissions`-Bitfield) + Channels (Topic/NSFW/Slowmode/Bitrate/Limit + Permission-Overwrites als allow/deny) + Server-Style. Restore baut Rollen-Mapping old→neu (Hierarchie-Guard < Bot-Top-Rolle, `@everyone` gemappt, managed übersprungen), legt Kategorien dann Channels an, mappt Overwrites um; `mode=missing` nur Fehlendes, `mode=mirror` gleicht an + löscht Channels die NICHT im Snapshot sind; Server-Name/-Icon nur mit `MANAGE_GUILD`; `asyncio.sleep` gegen Rate-Limits; alles in try/except (Fehler in Job-`message` gesammelt).
  - **Permissions:** Invite-Bitmask `285223958` → `285223990` (+ `MANAGE_GUILD`; `MANAGE_CHANNELS`/`MANAGE_ROLES` bereits enthalten).
  - **Frontend:** Seite [Backup.vue](frontend/src/pages/Backup.vue) (Snapshot-jetzt-Button, Liste mit Counts, **Vorschau-Modal** „Ansehen" das via `GET /backups/:id` den vollen Snapshot lädt und Server/Kanäle-Baum nach Kategorien/Rollen mit Farb-Dots zeigt — mit „Restore"-Button direkt im Modal, Restore-Modal mit `missing`/`mirror`-Wahl, Löschen-Confirm, 4s-Job-Polling). Router-Child `backup`, Sidebar-Link (Configuration-Gruppe), Overview-Karte (33), PremiumLock automatisch. i18n-Namespace `backup` (38 Keys inkl. `view`/`details*`/`close`) + `sidebar.linkBackup` + `overview.backup*` in **allen 5 Sprachen** (Key-Parität verifiziert: 1316/Locale, 0 missing/extra).
  - **Umsetzung mit Sub-Agents:** Schema + db.js-Helfer + API-Vertrag selbst gebaut, dann 3 Sub-Agents parallel (Backend-Routen / Bot-Cog / Frontend+EN/DE) + 3 Übersetzungs-Agents (TR/RU/PL).
  - Verifiziert: Migration v32 sauber, DB-Smoke (createBackup/Liste/Job-Roundtrip/Retention-15/Tier-Filter/Validation) grün, alle 34 Cogs parsen, Frontend-Build grün, i18n-Parität 1307/Locale. **Hinweis:** Nachrichten-Inhalte/Member-Rollenzuweisungen/Emojis sind nicht Teil des Snapshots (out of scope v1).
- **Datum:** 2026-06-19
- **Games-In-Game-Sprache (Schema v31):** Die **gesamte Games-Kategorie** rendert ihre In-Game-Texte jetzt in einer **pro Server wählbaren Sprache** (EN/DE/TR/RU/PL) — eine geteilte Einstellung für alle 6 Spiele (Tic-Tac-Toe/RPS/Trivia/Connect-Four/Hangman/Poker), unabhängig von der Dashboard-UI-Sprache.
  - **Schema:** Migration v31 = idempotenter ALTER `guild_games_settings.games_language TEXT DEFAULT 'en'` (+ Mirror/defensiver ALTER). `GAME_LANGUAGES` (`en|de|tr|ru|pl`) in [db.js](backend/db.js) ist Single Source (Validierung in `shapeGames`/`upsertGamesSettings`; `GAMES_DEFAULTS` erweitert). **Kein neuer Endpoint** — `games_language` fließt durch `/games` (Cookie GET/PUT, Partial-Merge) und `/api/bot/guilds/:id/settings/games`.
  - **Bot:** Neuer Helper [utils/game_i18n.py](bot/utils/game_i18n.py) (`make_translator(strings)` → `t(lang, key, **kwargs)`, `lang_of(settings)`, `normalize_lang` — Fallback EN→raw-key, `.format`-safe, crasht nie bei unvollständiger Tabelle). Alle 6 Games-Cogs ([tictactoe.py](bot/cogs/tictactoe.py)/[rps.py](bot/cogs/rps.py)/[trivia.py](bot/cogs/trivia.py)/[connect4.py](bot/cogs/connect4.py)/[hangman.py](bot/cogs/hangman.py)/[poker.py](bot/cogs/poker.py)) bekommen eine flache `_STRINGS`-Tabelle pro Sprache + `t = make_translator(_STRINGS)`; die Sprache wird beim Spielstart via `lang_of(settings)` aufgelöst und **in der In-Memory-Session gespeichert** (`session.lang`/`table.lang`), damit spätere Button-/Message-Interaktionen dieselbe Sprache nutzen. Trivia-Fragebank ist pro Sprache vorhanden.
  - **Frontend:** Neue Komponente [GameLanguagePicker.vue](frontend/src/components/GameLanguagePicker.vue) (Dropdown mit nativen Sprachnamen, `v-model`), in **allen 6** Games-Seiten eingebunden (`form.games_language`, lädt/speichert mit, Partial-PUT). i18n: `games.languageLabel`/`languageHint` in **allen 5 Sprachen** (Key-Parität verifiziert: 1270/Locale, 0 missing/extra).
  - Verifiziert: Migration v31 + DB-Konstanten grün, alle 6 Cogs kompilieren, **Poker-Evaluator-Self-Test grün**, Frontend-Build grün, i18n-Parität 1270/Locale.
- **Datum:** 2026-06-18
- **Poker-Tisch-Render + wählbares Tisch-Design (Schema v30):** Der Poker-Tisch wird jetzt als **vollständiges Tisch-Bild** gerendert (statt nur Karten + Text-Embed) und das **Filz-Design ist pro Server im Dashboard wählbar**.
  - **Voller Tisch-Render (Bot):** Neue Funktion `render_table_png(table)` in [poker.py](bot/cogs/poker.py) zeichnet via Pillow Filz-Ellipse + Holzrand, Community-Cards zentral mit Pot-/Street-Label, alle Sitze rund um die Ellipse (Seat 0 = unten) mit Name/Stack/Chip-Icon, D/SB/BB-Tags, BOT-Tag, Fold/All-in-Status; der Spieler am Zug wird mit Akzent-Glow hervorgehoben; beim Showdown werden die Hole-Cards der noch aktiven Spieler an ihrem Sitz enthüllt. `_render` schickt das Bild als **normalen Anhang** (`table.png`, NICHT im Embed — Discord zeigt es so groß/inline, kein Klick zum Erkennen nötig); die Caption (`_caption_text`: Spieler am Zug / to-call bzw. Showdown-Ergebnis) steht als Message-`content` darüber. `start`/`nexthand` laufen über `defer()` + `_render`. **Text-Embed bleibt als Fallback** wenn Pillow fehlt/Render scheitert.
  - **5 Themes:** `THEMES`-Dict in [poker.py](bot/cogs/poker.py) (classic/midnight/crimson/charcoal/royal — je bg-Gradient, Filz, Holzrand, Akzent, Embed-Farbe). Das aktive Design wird beim `!poker` aus `settings.poker_table_theme` in `table.theme` gesetzt und im Lobby-Footer angezeigt.
  - **Schema:** Migration v30 = idempotenter ALTER `guild_games_settings.poker_table_theme TEXT DEFAULT 'classic'` (+ Mirror/defensiver ALTER). `POKER_THEMES` in [db.js](backend/db.js) ist Single Source (Backend-Validierung in `shapeGames`/`upsertGamesSettings`, vom Bot gerendert, von der Dashboard-Auswahl gespiegelt). Kein neuer Endpoint — `poker_table_theme` fließt durch `/games` (Cookie GET/PUT, Partial-Merge) und `/api/bot/guilds/:id/settings/games`.
  - **Frontend:** [Poker.vue](frontend/src/pages/Poker.vue) bekommt einen Theme-Picker (5 klickbare Filz-Swatches mit Akzent-Punkt), bindet `form.poker_table_theme`, lädt/speichert es mit. i18n: `poker.themeLabel`/`themeHint` + 5 Theme-Namen + aktualisierter `usageNote` in **allen 5 Sprachen** (Key-Parität verifiziert: 1268/Locale, 0 missing/extra; tr/ru/pl via 3 parallele Sub-Agents).
  - Verifiziert: Migration v30 sauber, Games-Theme-DB-Roundtrip grün (default classic, Partial-Merge behält Theme, Invalid→classic), `render_table_png` über alle 5 Themes × Spielerzahlen (2/3/5/8) × Zustände (Preflop/Flop/River/Showdown) grün + visuell geprüft, Evaluator-Self-Test grün, alle 33 Cogs kompilieren, Frontend-Build grün, i18n-Parität 1268/Locale.
- **Poker-Ausbau: KI-Bots + Karten-Bilder (kein Schema-Change):** Der Poker-Cog [poker.py](bot/cogs/poker.py) bekommt zwei reine Bot-seitige Features — keine DB-/Backend-/Frontend-Änderung (Games-Modul-Infra unverändert).
  - **KI-Bots:** Der Host kann leere Sitze mit Bots füllen (Lobby-Buttons „Add bot" 🤖 / „Remove bot" 🗑️, custom_id `pk:addbot`/`pk:rmbot`). Bot-Spieler (`PokerPlayer.is_bot`, ID `bot:<uuid8>`, Namen aus `BOT_NAMES`) spielen automatisch am Zug: `_arm_timeout` routet bei Bot-Zug auf `_bot_act` (1.2–2.4s „Denkpause") statt auf den Idle-Timeout. Entscheidung via `_bot_decide` (Hand-Strength-Heuristik `_bot_strength` aus Hole-Cards/Board + Pot-Odds + Jitter → fold/check/call/raise, gelegentlicher Bluff). Bots landen **nie** in `participants` → werden nie ans `/games/score`-Leaderboard gemeldet; gewinnt ein Bot den Tisch, bekommt kein Mensch den `win`.
  - **Karten-Bilder:** Hole-Cards (über „🃏 My cards") und das Community-Board werden als PNG gerendert (`render_cards_png` via Pillow — Kartenflächen mit Rang/Suit-Symbolen, Rückseiten für verdeckte Karten). `_render` hängt das Board-Bild als `attachment://board.png` ans Embed; Lobby→Start cleart Attachments (`attachments=[]`). **Pillow ist optional:** ohne die Lib (`IMAGES_AVAILABLE = False`) fällt der Cog auf Text-Karten zurück, crasht nie.
  - **Dependency:** `Pillow==10.4.0` in [bot/requirements.txt](bot/requirements.txt) ergänzt (Tech-Stack-Block oben aktualisiert).
  - Verifiziert: `poker.py` kompiliert, **Evaluator-Self-Test grün** (`python cogs/poker.py`), PNG-Rendering produziert valide Bilder (Board 7.9 kB / Hand+verdeckt 6.4 kB), Bot-KI-Smoke (strength/decide) grün. Lobby hat jetzt 6 Buttons (wrappen automatisch auf 2 Action-Rows).
- **Datum:** 2026-06-17
- **Poker (Texas Hold'em) als 6. Spiel der Games-Kategorie (Schema v29, Tier Basic):** Vollwertiges Mehrspieler-Tisch-Spiel, teilt sich die `/games`-Infrastruktur (kein neues Schema außer einem `poker_enabled`-Flag).
  - **Schema:** Migration v29 = idempotenter ALTER `guild_games_settings.poker_enabled` (+ Mirror/defensiver ALTER). `GAME_KEYS`/`GAMES_DEFAULTS`/`shapeGames`/`upsertGamesSettings` (INSERT) + `PREMIUM_BOT_GATES`-disabled-Shape + `MODULE_TIERS` (`poker: basic` + Segment) um Poker erweitert. Kein neuer Endpoint — nutzt `/games`, `/games/score`, `/games/leaderboard`.
  - **Bot-Cog [poker.py](bot/cogs/poker.py) (33 Cogs gesamt):** 1 Tisch pro Channel. `!poker` → Lobby-Embed mit Join/Leave/Start/Cancel-Buttons (Start-Stack 1000, Blinds 10/20, max 8). Pro Hand: Dealer-Button rotiert, Blinds (inkl. Heads-up-Sonderfall), 2 Hole-Cards (ephemeral über „🃏 My cards"-Button, nicht öffentlich), Flop/Turn/River. Setzrunden als State-Machine (Fold/Check/Call/Raise via Modal/All-in) mit korrekter Min-Raise-Logik und 90s-Auto-Fold/Check-Timeout. **Layered Side-Pots** bei All-ins, **7-Karten-Hand-Evaluator** (`evaluate_5`/`best_hand`, inkl. Wheel-Straight) mit eingebautem `_self_test()`. Showdown enthüllt Hände + verteilt Pots (Split + Remainder). Moderne Embeds (Community-Cards, Pot, Spieler-Status mit D/SB/BB-Tags, ➤ am Zug). Bei Tisch-Ende → Chip-Leader = `win` an `/games/score`, alle Teilnehmer = `play`. custom_id-Schema `pk:<action>:<tid>`, In-Memory-State (Restart = Tisch verloren).
  - **Frontend:** Seite [Poker.vue](frontend/src/pages/Poker.vue) (Toggle + geteilter Spiele-Channel + Bestenliste), Router-Child, Sidebar-Link (Games-Gruppe), Overview-Card (`gameCards`), i18n-Namespace `poker` + `sidebar.linkPoker` + `overview.poker*` in **allen 5 Sprachen** (Key-Parität 1261/Locale).
  - **Umsetzung:** Cog selbst geschrieben (Korrektheit/Komplexität), tr/ru/pl-i18n parallel via 3 Background-Sub-Agents.
  - Verifiziert: Migration v29 sauber, DB-Smoke (poker-Flag/Score/Leaderboard) grün, **Evaluator-Self-Test grün** (`python cogs/poker.py`), alle 33 Cogs kompilieren, Frontend-Build grün, i18n-Parität 1261/Locale.
- **Neue Games-Kategorie mit 5 Spielen (Schema v28, alle Tier Basic):** Eigene Sidebar-Gruppe „Games" (4. Gruppe) mit Tic-Tac-Toe, Schere-Stein-Papier, Trivia, Vier gewinnt und Galgenmännchen (26 → 31 Modul-Cards).
  - **Schlanke geteilte Architektur:** EINE Settings-Row `guild_games_settings` (gemeinsamer `games_channel_id` + pro-Spiel-Toggle) + EINE `guild_game_scores`-Tabelle (`(guild_id, user_id, game)` → wins/plays). Eine Cookie-Route [games.js](backend/routes/games.js) (`GET/PUT /games` mit Partial-Merge, `GET /games/leaderboard?game=`), gated über `requirePremiumModule('games')`. Bot-Endpoints `GET /api/bot/guilds/:id/settings/games` + `POST .../games/score` + `GET .../games/leaderboard` in [bot.js](backend/routes/bot.js), `PREMIUM_BOT_GATES`-Eintrag `games`. db.js: `GAMES_DEFAULTS`/`GAME_KEYS`, `getGamesSettings`/`upsertGamesSettings` (Merge), `recordGameScore`, `getGameLeaderboard`.
  - **Bot:** 5 Cogs ([tictactoe.py](bot/cogs/tictactoe.py)/[rps.py](bot/cogs/rps.py)/[trivia.py](bot/cogs/trivia.py)/[connect4.py](bot/cogs/connect4.py)/[hangman.py](bot/cogs/hangman.py)) in [main.py](bot/main.py) geladen (32 Cogs gesamt). Button-Spiele via `on_interaction` (custom_id `ttt:`/`rps:`/`trv:`/`c4:`), In-Memory-Sessions (Token = `uuid4().hex[:8]`, „expired" bei Restart). Hangman via `on_message` (Einzelbuchstaben). Alle lesen `/settings/games` (60s-Cache), prüfen pro-Spiel-Flag + optionalen `games_channel_id`, posten Ergebnis an `/games/score`.
  - **Frontend:** 5 Seiten (TicTacToe/RockPaperScissors/Trivia/ConnectFour/Hangman) — je Toggle (pro-Spiel-Flag im geteilten Settings-Objekt, Partial-PUT) + geteilter Spiele-Channel + Spiel-Bestenliste. Router-Childs + neue Sidebar-Gruppe „Games" + 5 Overview-Cards (per `v-for` über `gameCards`). `MODULE_TIERS` um `games`+5 Segmente (alle basic) erweitert. i18n: `sidebar.sectionGames`+5 Links, 10 `overview.*`-Keys, 5 Namespaces (tictactoe/rps/trivia/connect4/hangman) in **allen 5 Sprachen** (Key-Parität verifiziert: 1244 Keys/Locale).
  - **Umsetzung mit Sub-Agents:** geteiltes Scaffolding (Migration/db/Routen/Nav/i18n EN+DE) selbst gebaut, dann 5 Cog-Agents + 1 Seiten-Agent + 3 Übersetzungs-Agents (tr/ru/pl) parallel.
  - Verifiziert: Migration v28 sauber, DB-Smoke-Test (Merge-Upsert/Scoring/Leaderboard/Validation) grün, alle 32 Cogs kompilieren, Frontend-Build grün, i18n-Parität 1244/Locale. **Hinweis:** alle Spiele teilen sich EINEN Tier (`games` = Basic) → daher EINE `/games`-Route trotz 5 Modul-Seiten.
- **Datum:** 2026-06-16
- **5 neue Module: Counting + Polls + Invite-Tracking + Applications + Economy (Schema v23–v27):** Großer Modul-Rollout in einem Rutsch (21 → 26 Module). Tier-Verteilung: Counting/Polls = **Free**, Invite-Tracking = **Basic**, Applications/Economy = **Pro**.
  - **Counting (Free, v23):** Zähl-Channel — der Bot validiert jede Zahl atomar (`recordCount` in Transaktion), trackt `current_count`/`high_score`/`last_user_id`, optionaler Reset bei Fehler/Doppel-Count. Cog [counting.py](bot/cogs/counting.py) (on_message), Route [counting.js](backend/routes/counting.js), Page [Counting.vue](frontend/src/pages/Counting.vue).
  - **Polls (Free, v24):** Button-Umfragen mit Live-Tally (`!poll Frage | A | B | …`). `guild_polls` + `guild_poll_votes` (single/multi); 30s-Loop schließt timed Polls. Cog [polls.py](bot/cogs/polls.py) (on_interaction `pv:<id>:<idx>`), Route [polls.js](backend/routes/polls.js) (Read-only + Delete), Page [Polls.vue](frontend/src/pages/Polls.vue).
  - **Invite-Tracking (Basic, v25):** `on_ready` cached `guild.invites()`, `on_member_join` difft Use-Counts → Einlader, Ankündigung + Leaderboard. Braucht **MANAGE_GUILD**. `guild_invite_settings`/`guild_invites`/`guild_member_invites`. Cog [invitetracking.py](bot/cogs/invitetracking.py), Route [invitetracking.js](backend/routes/invitetracking.js), Page [InviteTracking.vue](frontend/src/pages/InviteTracking.vue).
  - **Applications (Pro, v26):** Bewerbungsformulare (`!applypanel` → Button → Modal ≤5 Fragen → Review-Embed mit Accept/Deny; Accept vergibt Rolle + DM). `guild_application_forms`/`guild_applications`. Cog [applications.py](bot/cogs/applications.py), Route [applications.js](backend/routes/applications.js) (Forms-CRUD + Submissions), Page [Applications.vue](frontend/src/pages/Applications.vue).
  - **Economy (Pro, v27):** Server-Währung — `!balance/!daily/!work/!pay/!rich/!shop/!buy`, alle Mutationen transaktional im Backend. `guild_economy_settings`/`guild_economy_users`/`guild_economy_shop` (Shop vergibt optional Rolle). Cog [economy.py](bot/cogs/economy.py), Route [economy.js](backend/routes/economy.js) (Settings + Shop-CRUD + Leaderboard), Page [Economy.vue](frontend/src/pages/Economy.vue).
  - **Integration:** `MODULE_TIERS` + `FLAG/COUNT_MODULE_TABLES` + `MODULE_DEFAULTS` in [db.js](backend/db.js) erweitert; `PREMIUM_BOT_GATES` in [bot.js](backend/routes/bot.js) um invitetracking/applications/economy ergänzt; 28 neue Bot-Endpoints in [bot.js](backend/routes/bot.js); 5 Route-Mounts + Premium-Gates in [server.js](backend/server.js); 5 Cogs in [main.py](bot/main.py); Router/Sidebar/Overview (26 Cards) im Frontend; i18n-Namespaces `counting`/`polls`/`inviteTracking`/`applications`/`economy` + `common.save` in **allen 5 Sprachen** (Key-Parität verifiziert: 1158 Keys/Locale, 0 missing/extra).
  - Verifiziert: Migrationen v23–v27 sauber, DB-Smoke-Test aller neuen Helfer grün (counting/polls/invite/applications/economy end-to-end), Frontend-Build grün, alle 27 Cogs kompilieren. **Hinweis:** `npm test` zeigt lokal weiter 12 vorbestehende Fehler (Test-Harness wartet nicht auf die async Schema-Init / gesperrte `data/bot.db`) — unabhängig von dieser Änderung.
- **Admin-Bereich v2 (Schema v22):** Der Owner-Admin-Bereich wird von „nur Sperren" zu einem vollwertigen Betriebs-Dashboard erweitert — 5 neue Funktionsbereiche.
  - **System-Overview** (`GET /api/admin/overview`): Metrik-Karten (User/Server-Counts, Bot-Präsenz, Premium-Verteilung, Audit-Ereignisse 24h), „Premium läuft bald ab"-Liste (<7 Tage) und Modul-Adoption-Balken. Premium-Counts sind expiry-aware.
  - **Audit-Log-Viewer** (`GET /api/admin/audit` + `/audit/actions`): die längst befüllte `audit_log`-Tabelle ist jetzt im Dashboard sichtbar — filterbar nach Action (Dropdown) + Target (Actor-/Guild-ID/Name), mit Actor-/Guild-Join. Deckt auch die Block-History ab.
  - **Temporäre Sperren** (Schema): `users.blocked_until` + `guilds.blocked_until`. Block-Modal hat eine Dauer-Auswahl (permanent / 1h / 24h / 7d / 30d). `isUserBlocked`/`isGuildBlocked` sind temp-ban-aware (`isEffectivelyBlocked`) — abgelaufene Sperren gelten automatisch als aufgehoben, kein Sweeper.
  - **Guild-Inspektor** (`GET /api/admin/guilds/:id/inspect`): read-only Modal mit Modul-Status (an/aus + Count), Premium (Tier/Quelle/Ablauf), Bot-Präsenz, Dashboard-Mitglieder — plus Premium-Setzen mit Ablaufdauer direkt im Modal. Support-Tool („warum sendet der Bot keine Welcome-Nachricht?").
  - **Wartungsmodus / Kill-Switch** (`GET/PUT /api/admin/maintenance` + public `GET /api/public/maintenance`): neue Tabelle `system_settings` (Key/Value). Middleware [maintenance.js](backend/middleware/maintenance.js) (`maintenanceGate`, global vor `/api/guilds`) blockt Nicht-Owner-Writes mit **503** (Owner via JWT-Decode ausgenommen, 5s-Cache, fail-open). Globaler [MaintenanceBanner.vue](frontend/src/components/MaintenanceBanner.vue) (pollt 60s, Normal-Flow oben in beiden Shells).
  - **CSV-Export** (`GET /api/admin/{users,guilds}/export`): UTF-8-BOM-CSV-Download.
  - **Schema:** Migration v22 (2 idempotente ALTERs + neue Tabelle `system_settings` + Mirror). DB-Helfer-Set in [db.js](backend/db.js) (`getAdminOverview`/`getAuditLogEntries`/`getAuditActions`/`getGuildInspect`/`get|setSystemSetting`/`get|setMaintenanceState`/`getUsersForExport`/`getGuildsForExport`; `set*Blocked` + `getAdmin*` um `until`/`blocked_until` erweitert). [routes/admin.js](backend/routes/admin.js) (+6 Endpoints, `until` in Block-Bodies), [routes/public.js](backend/routes/public.js) (+maintenance), [server.js](backend/server.js) (Gate-Mount). Frontend: [Admin.vue](frontend/src/pages/Admin.vue) neu (5 Tabs + Inspektor-Modal + Temp-Ban-Dauer + Export), MaintenanceBanner in [App.vue](frontend/src/App.vue) + [MobileShell.vue](frontend/src/mobile/MobileShell.vue). i18n: ~43 neue `admin.*`-Keys + neuer `maintenance`-Namespace in **allen 5 Sprachen** (Key-Parität verifiziert: 1046 Keys/Locale, 0 missing/extra; tr/ru/pl via parallele Sub-Agents).
  - Verifiziert: 74/74 Backend-Tests grün, DB-Smoke-Test aller neuen Helfer grün (Migration v22 sauber), Frontend-Build grün (Admin-Chunk ~11.5 kB CSS, 225 Module). **Modul-Keys im Overview/Inspektor werden als Rohtext gezeigt** (Owner-Tool — bewusst keine 20×5 Übersetzungs-Keys).
- **3 neue Sprachen — Türkisch, Russisch, Polnisch (kein Schema-Change):** Die i18n deckt jetzt **5 Sprachen** ab (EN, DE, TR, RU, PL). Neue Locale-Dateien [tr.js](frontend/src/i18n/locales/tr.js)/[ru.js](frontend/src/i18n/locales/ru.js)/[pl.js](frontend/src/i18n/locales/pl.js) — vollständige Übersetzung aller Module + Legal-Seiten, je 1088 Keys (Key-Parität gegen en.js verifiziert: 0 missing/extra, Platzhalter-Token-Parität ok). Registriert in [index.js](frontend/src/i18n/index.js) (`messages` + `SUPPORTED_LOCALES` mit Labels Türkçe/Русский/Polski). LanguageSwitcher zieht die Liste dynamisch → Dropdown zeigt automatisch alle 5. Legal-Texte übersetzt, aber Paragraphen-Referenzen (§ TMG/MStV, DSGVO/GDPR-Artikel) + Kontaktdaten unverändert. **Hinweis:** Locales werden eager gebündelt → Haupt-Bundle ~309 kB → ~481 kB (gzip ~168 kB); bei Bedarf später lazy-loadbar. Build grün.
- **Datum:** 2026-06-15
- **Dedizierte Handy-Oberfläche (kein Schema-Change):** Eigene Mobile-UI **im selben Frontend-Projekt**, die NUR in der nativen App (Capacitor) bzw. mit `?mobile=1` aktiv wird — die Desktop-Website rendert unverändert, der Login (Discord-OAuth + Session-Cookie) bleibt heil, weil alles same-origin auf derselben Domain läuft (kein getrenntes/gebündeltes Frontend).
  - **Schaltlogik:** [frontend/src/mobile/platform.js](frontend/src/mobile/platform.js) `isMobileUI` = `Capacitor.isNativePlatform()` ODER `?mobile=1` (persistiert in `localStorage.projectx_force_mobile`, `?mobile=0` schaltet ab). `applyMobileClass()` (aus [main.js](frontend/src/main.js)) setzt die Klasse `.mobile-ui` auf `<html>`.
  - **App-Chrome:** [App.vue](frontend/src/App.vue) branched: `<MobileShell>` statt Desktop-Shell (AppNavBar/Footer/Sidebar). [MobileShell.vue](frontend/src/mobile/MobileShell.vue) = sticky **MobileTopBar** (Zurück-Pfeil auf Modul-Seiten → Overview-Hub / Brand, Route→i18n-Titel, Avatar→AccountSheet) + `<router-view>` + fixe **MobileTabBar** (kontextabhängig: ohne Guild Home/Server/Konto, in Guild Server/Module/Premium/Konto) + **MobileAccountSheet** (Bottom-Sheet: User, LanguageSwitcher, Server-Link, Admin für Owner, Logout). AppToast bleibt global über beiden Shells.
  - **Navigation:** Die bestehende [Overview.vue](frontend/src/pages/Overview.vue) dient als Modul-Hub (einspaltig via mobile.css), Modul-Seiten werden 1:1 wiederverwendet. [DashboardLayout.vue](frontend/src/pages/DashboardLayout.vue) blendet Sidebar + Hamburger aus, wenn `isMobileUI`.
  - **CSS:** [frontend/src/mobile/mobile.css](frontend/src/mobile/mobile.css) (global, nur unter `.mobile-ui`): mappt `--nav-height` auf die Top-Bar-Höhe (sticky Previews sitzen korrekt), Overview einspaltig + kompakter, Sticky-Save-Bar (`.config__footer`) über die Bottom-Nav heben, Form-Felder 16px (kein iOS-Auto-Zoom), Tabellen horizontal scrollbar, Safe-Area-Insets (Notch/Gesten-Leiste).
  - **i18n:** neuer Namespace `mobile` (nav/back/login/language/tabServers/tabModules/tabAccount) in EN+DE; Modul-Titel + Premium-Tab nutzen die vorhandenen `sidebar.link*`-Keys.
  - **Wichtig:** Da die App im Remote-URL-Modus die deployte Domain lädt, erscheint die Mobile-UI in der **installierten App erst nach erneutem Deploy des Web-Frontends**. Sofort testbar: deployte/lokale Seite mit `?mobile=1` im Handy-Browser öffnen. Frontend-Build grün (Mobile-Shell im Haupt-Bundle).
- **Android-App via Capacitor (kein Schema-Change):** Das bestehende Vue-Frontend wird in eine native Android-App gewrappt — vollständige Feature-Parität (alle 21 Module, Admin, Premium), da dieselbe SPA läuft.
  - **Ansatz „Remote-URL":** [frontend/capacitor.config.json](frontend/capacitor.config.json) `server.url` zeigt auf die deployte Dashboard-Domain; die native WebView lädt das Live-Dashboard. Damit bleiben **HTTP-only-Session-Cookie + Discord-OAuth-Redirect** unverändert funktionsfähig (same-origin in der WebView) — **kein** Token-/Auth-Umbau, respektiert das „kein localStorage-Token"-Verbot. `allowNavigation: discord.com` hält den OAuth-Login in der WebView (Cookie wird gesetzt).
  - **Native Integration:** [frontend/src/native/capacitor.js](frontend/src/native/capacitor.js) (aus [main.js](frontend/src/main.js) aufgerufen, **No-Op auf Web** via `Capacitor.isNativePlatform()`): dunkle Statusbar (`#0b0d12`), Splash-Hide, Hardware-Back → History/`exitApp`, externe Links (GitHub/Bot-Invite/Discord-Store) im System-Browser via `@capacitor/browser` (der OAuth-Login via `window.location` bleibt bewusst in der WebView).
  - **Setup:** Capacitor 6 (`core`/`cli`/`android` + Plugins `app`/`browser`/`status-bar`/`splash-screen`, dev `@capacitor/assets`) in [frontend/package.json](frontend/package.json); Scripts `cap:sync`/`cap:open`/`cap:run`/`cap:assets`. Generiertes [frontend/android/](frontend/android/)-Projekt committet (buildbar), `network_security_config.xml` erlaubt Cleartext nur für Dev-Hosts (10.0.2.2/localhost). Icons/Splash aus [frontend/resources/](frontend/resources/) (Logo) generiert. `.gitignore` um Android-Build-Artefakte/`local.properties`/Keystores erweitert.
  - **Verifiziert:** `npm run build` grün, `cap add android` + `cap sync` grün, **Debug-APK gebaut** (`gradlew assembleDebug` → `android/app/build/outputs/apk/debug/app-debug.apk`, ~12 MB, JDK 17).
  - **Noch zu tun vorm Release:** (1) `server.url` auf die echte Domain setzen (Platzhalter `https://CHANGE-ME.example.com`). (2) Web-Frontend **neu deployen** (damit das deployte `main.js` die native Integration enthält). (3) Für Play Store: Release-Keystore + `assembleRelease` (signiert) + App-Icons final.
- **Datum:** 2026-06-13
- **Premium-Tiers + Landing-Ausbau (Schema v21):** Neues Monetarisierungs-/Gating-System (Free/Basic/Pro) plus komplett erweiterte Landing-Page.
  - **Tier-Modell:** `MODULE_TIERS` in [db.js](backend/db.js) ist Single Source (Modul-Key = Dashboard-Route-Segment → min Tier). **Free:** welcome/leave/autorole/logs/moderation/reaction-roles/verification/suggestions/custom-commands. **Basic:** leveling/starboard/tempvoice/birthday/rolemenus/antiraid. **Pro:** social/stats/tickets/giveaways/scheduled. `guilds.premium_tier`/`premium_source`/`premium_until` (Migration v21, idempotent + Mirror). `effectiveTier()` behandelt abgelaufenes `premium_until` als `free`.
  - **Premium-Quelle:** Discord SKUs **+** Owner-Override. Bot-Cog [premium_sync.py](bot/cogs/premium_sync.py) liest die App-Entitlements (`GET /applications/{id}/entitlements`), mappt SKU→Tier (`SKU_BASIC_ID`/`SKU_PRO_ID`) und pusht via `PUT /api/bot/premium` (`syncSkuEntitlements`: setzt sku-Premium, downgradet lapsed, lässt `manual` unberührt). Ohne SKU-IDs inert. Owner setzt Tiers manuell im Admin-Panel (`POST /api/admin/guilds/:id/premium`, Audit `ADMIN_SET_PREMIUM`).
  - **Enforcement (3 Schichten):** (1) Frontend-Locks — DashboardLayout rendert [PremiumLock.vue](frontend/src/components/PremiumLock.vue) statt der Modul-Seite, wenn Tier < Modul (ein Gate für alle 11 Premium-Seiten); Sidebar-Lock-Icons + Overview-Karten-Ribbons. (2) Backend-Write-Gate [middleware/premium.js](backend/middleware/premium.js) `requirePremiumModule(key)` (GET frei, Writes → 403 `premium_required`; Leveling im eigenen Router gegated). (3) Bot-Runtime: Premium-Bulk-Queries via `tierFilterSql` gefiltert, per-Guild Bot-GETs über `PREMIUM_BOT_GATES`-Guard in [bot.js](backend/routes/bot.js) → `disabled`-Shape. So gehen Premium-Features bei Tier-Verlust (SKU abgelaufen / Downgrade) automatisch inert.
  - **Backend:** Migration v21, db.js-Premium-Block (Konstanten + Helfer + `PLAN_CATALOG`), neue Route [premium.js](backend/routes/premium.js) (`GET /api/guilds/:id/premium`), [public.js](backend/routes/public.js) `GET /api/public/plans`, admin `POST .../premium`, bot `PUT /api/bot/premium`. Tier-Filter in 6 Bulk-Queries (social/stats/scheduled/birthday/rolemenus/giveaways). `getAdminGuilds` liefert Premium-Felder.
  - **Bot:** [config.py](bot/config.py) `APPLICATION_ID`/`SKU_BASIC_ID`/`SKU_PRO_ID`/`PREMIUM_POLL_INTERVAL`, Cog in [main.py](bot/main.py) geladen.
  - **Frontend:** Store [premium.js](frontend/src/stores/premium.js) (`usePremium().isUnlocked(key)/tierOf(key)`), Page [Premium.vue](frontend/src/pages/Premium.vue) (`/dashboard/:id/premium`, 3 Plan-Cards + aktueller Tier), PremiumLock-Komponente, Sidebar-Premium-Link + Lock-Icons, Overview-Lock-Ribbons (`data-lock`), Admin-Tier-Select pro Server. **Landing komplett erweitert:** alle 21 Module mit Tier-Badges (vorher 8), neue **Pricing-Sektion** (Free/Basic/Pro, datengetrieben aus `/api/public/plans`) + **FAQ-Sektion**. i18n-Namespaces `premium`/`premiumLock` + `landing.pricing`/`landing.faq` + erweiterte `landing.modules` + `sidebar.linkPremium` + `admin.tier*` in EN+DE.
  - DB-Round-Trip verifiziert (Tier setzen/effektiv/SKU-Sync/Filter), Frontend-Build grün (Landing ~16 kB, neuer Premium-Chunk), Backend-Imports + Bot-Syntax OK. **Hinweis:** `npm test` zeigt lokal 12 vorbestehende Fehler, weil ein anderer Prozess `data/bot.db` gesperrt hält (siehe Eintrag unten) — auf freier DB grün.
- **Rollen-Menü-Embed-Designer (Schema v20):** Das Rollen-Menü-Modul bekommt einen eigenen Embed-Creator mit Live-Vorschau — analog zum Ticket-System.
  - **Nachrichten-Modus:** pro Menü umschaltbar zwischen **Auto-Liste** (Bot baut das Embed wie bisher aus Menü-Name + Rollen-Liste, lila `#A78BFA` — Default, abwärtskompatibel) und **eigenem Embed** (`use_embed = 1`). Bei eigenem Embed gestaltet der User Titel/Beschreibung/Farbe/Thumbnail/Bild/Footer/Author/Timestamp über den wiederverwendeten `EmbedEditor`. Platzhalter `{guild}` wird vom Bot ersetzt.
  - **Live-Vorschau:** [RoleMenuRow.vue](frontend/src/components/RoleMenuRow.vue) rendert die Discord-Optik via `DiscordMessagePreview` (Embed) + Mock-Komponenten: Button-Reihe (Buttons-Modus) oder Dropdown-Platzhalter (Select-Modus, exklusiv/multi). Das Auto-Listen-Embed wird in der Vorschau exakt nachgebaut.
  - **Schema:** Migration v20 (2 idempotente ALTERs auf `guild_role_menus`: `use_embed`, `embed` JSON; Mirror in `initializeDatabase()`). DB-Helfer in [db.js](backend/db.js) erweitert (`shapeRoleMenu` parst `embed` via `parseEmbedColumn` + liefert `use_embed`; `createRoleMenu`/`updateRoleMenu` schreiben `use_embed`/`embed` via `sanitizeEmbed`). Cookie-Route [rolemenus.js](backend/routes/rolemenus.js) reicht den Body durch (keine Änderung nötig). Bot-Endpoints `GET /api/bot/rolemenus/pending` + `.../rolemenus/by-message/:id` liefern die Felder automatisch mit.
  - **Bot:** [rolemenus.py](bot/cogs/rolemenus.py) — neuer `build_custom_embed(cfg, guild)`-Helper; `_post_menu` baut bei `use_embed` das eigene Embed (Fallback auf Name+Liste, falls leer), sonst die Auto-Liste wie bisher.
  - **Frontend:** Mode-Switch + `EmbedEditor` + Vorschau in [RoleMenuRow.vue](frontend/src/components/RoleMenuRow.vue); `serialize`/`emptyDraft` in [RoleMenus.vue](frontend/src/pages/RoleMenus.vue) um `use_embed`/`embed` erweitert. i18n `rolemenus.*` (messageMode*/embedLabel/livePreview/previewSelectPlaceholder*) in EN+DE.
  - DB-Round-Trip verifiziert (Create/List/Update/Embed-Persistenz), Frontend-Build grün (RoleMenus-Chunk ~12 kB), Bot-Syntax OK. **Hinweis:** Die Backend-`npm test`-Suite zeigte lokal 12 Fehler, weil ein anderer Prozess `data/bot.db` gesperrt hielt (`disk I/O error` / „Device or resource busy" auf dem Journal) — die Tests warten nicht auf die async Schema-Init; auf einer freien DB läuft alles grün.
- **Datum:** 2026-06-10
- **Command-Manager im Custom-Commands-Modul (Schema v19):** Das Modul listet jetzt **alle** eingebauten Befehle aller Module auf und macht sie pro Server konfigurierbar.
  - **Katalog:** `BUILTIN_COMMANDS` in [db.js](backend/db.js) ist die Single Source (30 Befehle über alle Module — Welcome/Birthday/Suggestions/Verification/Tickets/Giveaways/Polls/Applications/Economy/Games/Utility; `key` = qualified command name, `type ∈ {prefix|slash}`, `module`, `usage`, `description`). Frontend gruppiert nach Modul (Labels in `commandManager.modules.*`, Fallback = roher Modul-Key) und zeigt pro Befehl einen An/Aus-Toggle + Typ-Badge. **Beim Hinzufügen eines neuen Bot-Befehls hier ergänzen**, sonst fehlt er im Command-Manager.
  - **Server-Prefix:** `guilds.command_prefix` (Default `'!'`, 1–5 Zeichen). Bot löst den Prefix dynamisch pro Guild auf (`command_prefix = async _resolve_prefix`), Mention bleibt immer aktiv.
  - **An/Aus pro Befehl:** `guild_command_settings` (PK `(guild_id, command_key)`). Bot sperrt deaktivierte Befehle über zwei globale Gates: `@bot.check` (Prefix → CheckFailure, in `on_command_error` geschluckt) und `bot.tree.interaction_check` (Slash → ephemerale „disabled"-Antwort).
  - **Schema:** Migration v19 (idempotenter `guilds`-ALTER + neue Tabelle + Mirror). DB-Helfer in [db.js](backend/db.js) (`getCommandPrefix`/`setCommandPrefix`/`sanitizeCommandPrefix`, `getCommandSettings`/`setCommandEnabled`, `getCommandConfigForBot`). Cookie-Routes in [custom-commands.js](backend/routes/custom-commands.js) (`/catalog`, `/prefix`, `/toggle/:key`; literale Pfade vor `/:cmd_id`). Bot-Endpoint `GET /api/bot/guilds/:id/commands`. Bot: neuer Helper [command_config.py](bot/utils/command_config.py) (60s-Cache) + [main.py](bot/main.py) (dynamischer Prefix, 2 Gates, `on_command_error`). Frontend: [CustomCommands.vue](frontend/src/pages/CustomCommands.vue) erweitert (Prefix-Card + Katalog-Sektion). i18n-Namespace `commandManager` (inkl. `modules.*`) in EN+DE.
  - 74/74 Backend-Tests grün, Frontend-Build grün, Bot-Syntax OK. **Verzögerung:** Dashboard-Änderungen greifen im Bot nach max. 60s (Cache-TTL).
- **Ticket-System-Ausbau (Schema v18):** Das Ticket-Modul wurde umfassend erweitert — Kategorien, Embed-Gestaltung, Bewertung, Claim, Add/Remove-User.
  - **Kategorien (Ticket-Typen):** neue Tabelle `guild_ticket_categories` (CRUD im Dashboard). Jede Kategorie ist eine Panel-Option mit Label/Emoji/Beschreibung und optionalen Overrides für Discord-Kategorie, Support-Rolle und Ping-Rolle, eigenem Welcome-Text und Button-Farbe. Panel-Darstellung pro Guild wählbar (`panel_type ∈ {dropdown|buttons}`); ohne Kategorien fällt das Panel auf einen einzelnen „Open Ticket"-Button zurück.
  - **Embed-Gestaltung:** Panel-Embed (`panel_embed`) und Ticket-Willkommens-Embed (`welcome_embed`) als JSON, im Dashboard via wiederverwendetem `EmbedEditor`. Bot baut sie mit Platzhaltern (`{user}`/`{guild}`/`{number}`/`{category}`).
  - **Bewertung:** `rating_enabled` + `rating_mode ∈ {channel|dm|both}`. Beim Schließen 1–5-Sterne-Buttons im Channel und/oder per DM → `RatingModal` (optionaler Kommentar) → Ergebnis in `log_channel_id`. Bei Channel-Rating bleibt der Channel bis zur Abgabe (Staff-„Delete"-Button), sonst Auto-Delete nach 5s.
  - **Claim / Add / Remove:** Control-Bar im Ticket (Claim, Add user, Remove user, Close) — Add/Remove via `UserSelect`. Parallel Prefix-Commands `!claim`, `!ticketadd @user`, `!ticketremove @user`, `!ticketclose`. Optionale Close-Bestätigung (`close_confirm`). Per-Guild-Ticket-Nummerierung (`number`), `naming_template` mit `{user}`/`{number}`/`{category}`.
  - **Schema:** Migration v18 (idempotente ALTERs auf `guild_ticket_settings` +10 / `guild_tickets` +8, neue Tabelle, Mirror in `initializeDatabase()`). DB-Helfer-Set in [db.js](backend/db.js) (`getTicketConfig`, Kategorie-CRUD, `createTicket` mit Nummer, `claimTicket`, `setTicketRating`, `updateTicketExtraUsers`, `getTicketByChannel`), Cookie-Route-Erweiterung in [routes/tickets.js](backend/routes/tickets.js) (Kategorien-CRUD), neue Bot-Endpoints in [routes/bot.js](backend/routes/bot.js) (by-channel/claim/rating/users + Config mit Kategorien). Cog [tickets.py](bot/cogs/tickets.py) komplett überarbeitet. Frontend: [Tickets.vue](frontend/src/pages/Tickets.vue) neu (4 Settings-Cards + Kategorien-Liste) + neue Komponente [TicketCategoryRow.vue](frontend/src/components/TicketCategoryRow.vue). i18n `tickets.*` + `common.delete`/`common.cancel` in EN+DE.
  - 74/74 Backend-Tests grün, Frontend-Build grün (Tickets-Chunk ~19.9 kB), alle 22 Cogs parsen sauber.
- **Owner-Admin-Bereich (Schema v17):** Neuer Owner-only Dashboard-Bereich zum Sperren von Usern und Guilds.
  - **Owner-Identifikation:** env `OWNER_DISCORD_ID` (komma-separiert). `isOwner`/`requireOwner` in [session.js](backend/middleware/session.js); `requireSession` setzt `req.user.is_owner`. `/auth/me` + `/auth/callback` liefern `is_owner` mit.
  - **Schema:** Migration v17 (idempotente ALTERs + Mirror) — `blocked`/`blocked_reason`/`blocked_at` auf `users` UND `guilds`.
  - **Backend:** neue Route [admin.js](backend/routes/admin.js) (`/api/admin/{users,guilds}` GET-Liste + `POST .../block`, requireSession+requireOwner, Audit `ADMIN_BLOCK_*`/`ADMIN_UNBLOCK_*`). DB-Helfer `isUserBlocked`/`isGuildBlocked`/`getAdminUsers`/`getAdminGuilds`/`setUserBlocked`/`setGuildBlocked` in [db.js](backend/db.js).
  - **Enforcement:** Gesperrte User → 403 in `requireSession`/`/auth/me`/Callback (Owner ausgenommen). Gesperrte Guilds → bleiben im Server-Picker sichtbar, aber rot umrandet + nicht klickbar ([Servers.vue](frontend/src/pages/Servers.vue) `guild-card--blocked`, `servers.blocked*`-i18n), 403 in `requireGuildAccess`, 403-Guard in [bot.js](backend/routes/bot.js) auf `/guilds/:id/*` (Bot wird inert), und `blocked=0`-Filter in allen 8 guild-übergreifenden Loop-Cog-Queries.
  - **Frontend:** Page [Admin.vue](frontend/src/pages/Admin.vue) (Tabs User/Server, Suche mit Debounce, Block-Modal mit Grund, Load-More-Paginierung), Route `/admin` (`requiresOwner`-Guard in [router/index.js](frontend/src/router/index.js)), Owner-Link im NavBar-Usermenü, i18n-Namespace `admin` + `nav.adminPanel` in EN+DE. auth-Store reicht `is_owner` automatisch durch.
  - 74/74 Backend-Tests grün, Frontend-Build grün (neuer Chunk `Admin` ~8.8 kB). Bot unverändert (Enforcement rein backend-seitig).
- **Batch-3-Erweiterungen (Schema v16) + Sidebar-Fix:**
  - **Sidebar:** Bei 21 Modul-Links lief der Inhalt aus der Box. [Sidebar.vue](frontend/src/components/Sidebar.vue): `.sidebar` `overflow: hidden`, `.sidebar__nav` `overflow-y: auto` + `min-height: 0` (+ dünne Scrollbar) → Head/Foot bleiben fix, die Modul-Liste scrollt.
  - **Ticket-Transcripts:** optionaler `transcript_channel_id` — beim Schließen sammelt der Bot die Channel-History (max 1000) und postet sie als `.txt`-Datei + Embed, bevor der Channel gelöscht wird ([tickets.py](bot/cogs/tickets.py) `_maybe_transcript`).
  - **Giveaway-Reroll:** `!greroll <giveaway_id>` zieht aus den bestehenden Einträgen einen neuen Gewinner (Bot-Endpoint `GET .../giveaways/:gid` + `getGiveawayById`).
  - **Exklusive Select-Rollen-Menüs:** `exclusive`-Flag — im Select-Modus `max_values=1`, die Auswahl ersetzt die anderen Menü-Rollen. Bot lädt das Menü via `GET .../rolemenus/by-message/:message_id` (`getRoleMenuByMessage`) zur Laufzeit.
  - Schema: Migration v16 (2 idempotente ALTERs + Mirror). 74/74 Backend-Tests grün, Frontend-Build grün, alle 22 Cogs parsen sauber.
- **Datum (Batch 3):** 2026-06-10
- **Batch 3: Slash-Utils + Verification + Role-Menus + Tickets + Giveaways (Schema v14/v15):** Neue **Interaktions-Architektur** im Bot.
  - **Architektur:** `bot.tree.sync()` einmalig nach Cog-Load in [main.py](bot/main.py) (Flag-gesichert) für Slash-Commands. Component-Interaktionen (Buttons/Selects) laufen über `on_interaction` mit custom_id-Encoding (`rr:<role>`, `rrselect`, `verify`, `ticket_open/close`, `ge:<id>`) → **persistent über Restarts ohne View-Registrierung**.
  - **Slash-Utils:** `/ping` `/userinfo` `/serverinfo` `/avatar` ([slash_utils.py](bot/cogs/slash_utils.py), keine DB).
  - **Verification (v14):** Button-Gate → Verifiziert-Rolle. `!verifypanel` postet das Panel. [verification.js](backend/routes/verification.js), [Verification.vue](frontend/src/pages/Verification.vue).
  - **Role-Menus (v14):** Buttons/Select-Dropdown für selbst-vergebbare Rollen. Dashboard-CRUD; 60s-Loop postet unposted Menüs; on_interaction toggelt Rollen. [rolemenus.js](backend/routes/rolemenus.js), [RoleMenuRow.vue](frontend/src/components/RoleMenuRow.vue).
  - **Tickets (v15):** Panel-Button → privater Support-Channel (Overwrites: Opener + Support-Rolle), Close-Button löscht. `!ticketpanel`. Braucht `MANAGE_CHANNELS`. [tickets.js](backend/routes/tickets.js).
  - **Giveaways (v15):** `!gstart <dur> <winners> <prize>` → Button-Entry; 30s-Loop lost zufällige Gewinner aus (`random.sample`). Dashboard zeigt Liste read-only + löschen. [giveaways.js](backend/routes/giveaways.js).
  - Schema: Migrationen v14 (3 Tabellen) + v15 (4 Tabellen), idempotent + Mirror. DB-Helfer-Sets + Bot-Endpoints in [bot.js](backend/routes/bot.js). Frontend: 4 Pages + RoleMenuRow + Router/Sidebar/Overview (21 Cards) + i18n EN/DE. **74/74 Backend-Tests grün, Frontend-Build grün, alle 22 Cogs parsen sauber.**
- **Datum (Batch 2):** 2026-06-09
- **Batch 2: Birthday + Scheduled Announcements + Anti-Raid (Schema v13):**
  - **Birthday:** `!birthday TT.MM[.YYYY]` speichert den Geburtstag; 30min-Loop (1×/Tag aktiv) announced in `announce_channel_id` (`{user}`), vergibt optionale `birthday_role_id` für den Tag und entfernt sie am Folgetag (Rollen-Sweep über `getBirthdayRoleGuilds`). Dashboard zeigt gespeicherte Geburtstage (löschbar).
  - **Scheduled Announcements:** CRUD-Liste geplanter Nachrichten (`once` mit datetime ODER `interval` in Minuten). 30s-Scheduler-Loop pollt `/scheduled/due`, postet, meldet `/ran` zurück (Backend rechnet `run_at`+`interval_seconds` neu bzw. disabled `once`).
  - **Anti-Raid:** `on_member_join` — Account-Alter-Gate (`account_age_days`) + Join-Rate-Burst (`join_rate_count`/`join_rate_seconds`, in-memory deque + Cooldown) → Aktion `alert|kick|ban` + Alarm-Embed in `alert_channel_id`.
  - Schema: Migration v13 (4 Tabellen, idempotent + Mirror). Backend: 3 Cookie-Routes ([birthday.js](backend/routes/birthday.js)/[scheduled.js](backend/routes/scheduled.js)/[antiraid.js](backend/routes/antiraid.js)) + Bot-Endpoints. DB-Helfer-Sets. Bot: 3 Cogs ([birthday.py](bot/cogs/birthday.py)/[scheduler.py](bot/cogs/scheduler.py)/[antiraid.py](bot/cogs/antiraid.py)). Frontend: 3 Pages + [ScheduledMessageRow.vue](frontend/src/components/ScheduledMessageRow.vue) + Router/Sidebar/Overview (16 Cards) + i18n EN/DE. 74/74 Backend-Tests grün, Frontend-Build grün, Bot-Syntax OK.
  - **Noch offen:** Batch 3 (Interaktions-/Slash-Architektur) = Tickets, Giveaways, Button/Select-Role-Menüs, Verification, Slash-Utility-Commands.
- **Datum (Batch 1):** 2026-06-09
- **Batch 1: Temp-Voice + Starboard + Suggestions (Schema v12):** Drei neue Module (Teil eines geplanten Mehr-Batch-Rollouts).
  - **Temp-Voice (Join-to-Create):** Hub-Channel → Bot erstellt persönlichen Voice-Channel (Kategorie, `name_template` `{user}`, `user_limit`), moved Member rein, löscht bei leer; `on_ready`-Cleanup über getrackte Channels. Braucht `MANAGE_CHANNELS` + `MOVE_MEMBERS` → **Invite-Bitmask `268446742` → `285223958`**.
  - **Starboard:** Stern-Reaktionen ab `threshold` → Repost (Embed + Jump) in `star_channel`, Count wird aktualisiert, Entfernen bei Unterschreitung. Entry-State (`star_message_id`/`count`) bot-gepflegt.
  - **Suggestions:** `!suggest <text>` → Embed in `suggest_channel` + Up/Down-Vote-Reaktionen (konfigurierbare Emojis).
  - Schema: Migration v12 (5 Tabellen, idempotent + Mirror). Backend: 3 Cookie-Routes ([tempvoice.js](backend/routes/tempvoice.js)/[starboard.js](backend/routes/starboard.js)/[suggestions.js](backend/routes/suggestions.js)) + Bot-Endpoints in [bot.js](backend/routes/bot.js). DB-Helfer + `clampRange`. Bot: 3 Cogs + `bot_delete`-Helper in [utils/backend.py](bot/utils/backend.py). Frontend: 3 Settings-Pages + Router/Sidebar/Overview (13 Cards) + i18n EN/DE. 74/74 Backend-Tests grün, Frontend-Build grün, Bot-Syntax OK.
  - **Noch offen (geplante Batches):** Batch 2 = Birthday, Scheduled Announcements, Anti-Raid. Batch 3 (braucht Interaktions-/Slash-Architektur) = Tickets, Giveaways, Button/Select-Role-Menüs, Verification, Slash-Utility-Commands.
- **Datum (Stats-Kategorie/Reihenfolge):** 2026-06-09
- **Statistics: Kategorie + Reihenfolge (Schema v11):** Stats-Channels werden jetzt innerhalb einer **Kategorie** angelegt — wahlweise eine **bestehende** (ChannelSelector `types=['category']`) oder vom **Bot auto-erstellt** (`auto_category` + `category_name`, Bot schreibt die erzeugte `category_id` via `PUT /api/bot/guilds/:id/stats/category` zurück). Die **Reihenfolge** der Counter innerhalb der Kategorie ist konfigurierbar (1·2·3·4) — Up/Down-Buttons in [StatsCounterRow.vue](frontend/src/components/StatsCounterRow.vue) persistieren `position`, der Bot erzwingt sie via `_enforce_order` (nur bei Abweichung, Rate-Limit-schonend). Schema: Migration v11 (3 Kategorie-Spalten in `guild_stats_settings`, idempotent + Mirror). DB-Helfer um Kategorie erweitert + neuer `setStatsCategory`. Bot-Endpoint `PUT .../stats/category`. Cog [stats.py](bot/cogs/stats.py): `_resolve_category` + `category=`-Param bei Channel-Create + `_enforce_order`. Frontend: Kategorie-Card in [Stats.vue](frontend/src/pages/Stats.vue) + Reorder. i18n `stats.category*`/`stats.move*` EN+DE. 74/74 Backend-Tests grün, Frontend-Build grün, Bot-Syntax OK.
- **Datum (Stats-Modul-Erstrelease):** 2026-06-08
- **Statistics-Modul (Schema v10):** Neues 10. Modul — zeigt Live-Serverzahlen als Channel-Namen (Stats-Channels wie im klassischen „MEMBER: 166"-Pattern) plus Verlaufs-Graphen im Dashboard.
  - Kennzahlen: `members`, `humans`, `bots`, `online`, `offline`, `boosters`, `channels`, `roles`. **Online/Offline brauchen das privilegierte Presence-Intent** (`intents.presences = True` in [main.py](bot/main.py) + Aktivierung im Dev-Portal). Channel pro Counter wahlweise **selbst ausgewählt** (ChannelSelector) oder **vom Bot auto-erstellt** (Voice locked / Text) — Auto-Create braucht `MANAGE_CHANNELS`, daher **Invite-Bitmask `268446726` → `268446742`** in [Overview.vue](frontend/src/pages/Overview.vue).
  - Schema: Migration v10 + 3 Tabellen (`guild_stats_settings`, `guild_stats_counters` UUID-PK, `guild_stats_snapshots`), idempotent + Mirror in `initializeDatabase()`. Snapshot-Retention 90 Tage.
  - Backend: neue Route [routes/stats.js](backend/routes/stats.js) (`/api/guilds/:id/stats` GET/PUT, `/stats/counters` POST/PUT/DELETE, `/stats/history` GET, cookie) + 3 Bot-Endpoints in [routes/bot.js](backend/routes/bot.js) (`GET /api/bot/stats/configs`, `PUT .../stats/counters/:cid/channel`, `POST .../stats/snapshot`). DB-Helfer-Set + `STATS_COUNTER_TYPES`/`STATS_DEFAULTS` in [db.js](backend/db.js). Audit-Actions `UPDATE_STATS_SETTINGS`/`STATS_COUNTER_CREATE|UPDATE|DELETE`. `update_interval` clamp `[5,1440]` Min (Channel-Rename-Rate-Limit).
  - Bot: neues Cog [stats.py](bot/cogs/stats.py) — `tasks.loop` 60s-Takt, per-Guild gegen `update_interval` gegatet. Zählt je Guild, benennt/erstellt Stats-Channels (Rename nur bei Namensänderung wg. Rate-Limit), schreibt auto-Channel-IDs + Snapshots zurück. Nutzt `bot_get`/`bot_put`/`bot_post` aus [utils/backend.py](bot/utils/backend.py).
  - Frontend: Page [Stats.vue](frontend/src/pages/Stats.vue) (Modul-Settings + Counter-Liste + Graphen-Sektion mit 7/30-Tage-Switch) + Components [StatsCounterRow.vue](frontend/src/components/StatsCounterRow.vue) (Inline-Editor: Metrik/Template+`{count}`/Modus existing↔auto/Voice|Text) und [StatsChart.vue](frontend/src/components/StatsChart.vue) (Vanilla-SVG-Liniendiagramm, keine neue Dependency). Routen-Child `/dashboard/:guild_id/stats`, Sidebar-Eintrag in Configuration-Gruppe, 10. Overview-Card. i18n-Namespace `stats` + `sidebar.linkStats` + `overview.stats*` in EN+DE.
  - 74/74 Backend-Tests grün, Frontend-Build grün (neuer Chunk `Stats` ~15.7 kB), Bot-Cogs parsen sauber.
- **Datum (vorherige Iteration):** 2026-06-07
- **Moderation- & Server-Logs-Ausbau (Schema v9):**
  - **Moderation:** neue Filter Anti-Invite, Anti-Link, Mass-Mention (`max_mentions`), Caps (`caps_percentage`) mit gemeinsamer `filter_action`; natives Discord-**Timeout** als Aktion (`timeout_duration`, max 28 Tage) für alle Action-Selects (`banned_word_action`/`filter_action`/Eskalation); **Warn-Eskalation** (`warn_threshold` + `warn_escalation_action`) mit persistentem Zähler in `guild_moderation_warnings`; **Whitelist** (`exempt_role_ids` umgehen alles, `ignored_channel_ids` werden ignoriert). Enums via `MOD_ACTIONS`/`MOD_ESCALATION_ACTIONS` (exportiert). Neuer Bot-Endpoint `POST /api/bot/guilds/:id/moderation/warn` (atomar via `addModerationWarning`). Cog [moderation.py](bot/cogs/moderation.py) komplett überarbeitet (Invite/URL-Regex, Caps-%, Mention-Count, Timeout via `member.timeout`, Eskalations-Apply).
  - **Server-Logs:** 5 neue Event-Kategorien — Member-Updates (Rollen/Nickname/Timeout via `on_member_update`), Unbans, Channel-Events, Rollen-Events, Voice-Aktivität (join/leave/move) — + `log_ignored_channel_ids` (schließt Channels vom Message-Edit/Delete-Logging aus). Cog [logs.py](bot/cogs/logs.py) um die Listener erweitert.
  - Schema: Migration v9 (12 Moderation- + 6 Log-ALTERs idempotent, neue Tabelle `guild_moderation_warnings`) + Mirror in `initializeDatabase()`. Backend-Helper + Enums + `addModerationWarning` in [db.js](backend/db.js), Validierung in [routes/modules.js](backend/routes/modules.js), Bot-Shapes + Warn-Endpoint in [routes/bot.js](backend/routes/bot.js).
  - Frontend: [Moderation.vue](frontend/src/pages/Moderation.vue) (Content-Filter-Card, Action-Settings, Warn-Card, Whitelist mit RoleSelector-multi + Channel-Picker+Add) und [Logs.vue](frontend/src/pages/Logs.vue) (5 neue Toggles + Ignored-Channels-Picker) erweitert. i18n `moderation.*`/`logs.*` in EN+DE ergänzt (Action-Keys jetzt `action_<enum>`).
  - 74/74 Backend-Tests grün, Frontend-Build grün (Moderation-Chunk 17.7 kB), Bot-Cogs parsen sauber.
- **Social-Notifications-Modul (Schema v8):** Neues Engagement-Modul — kündigt neue Videos / Livestreams getrackter Creator in einem Channel an.
  - Plattformen: **YouTube + Twitch + Kick** voll funktionsfähig; **TikTok + Instagram** sind als Adapter-Stubs vorhanden (kein freies offizielles API → bewusst deaktiviert, im Frontend als „coming soon"). Mechanismus durchgängig **Polling** (self-hosted Bot, kein öffentlicher HTTPS-Callback nötig).
  - Schema: Migration v8 + Tabelle `guild_social_subscriptions` (UUID PK, UNIQUE `(guild_id, platform, account)`, idempotent + Mirror in `initializeDatabase()`). Bot-gepflegter Polling-State (`account_id`/`display_name`/`last_video_id`/`last_live`/`last_checked_at`).
  - Backend: neue Route [routes/social.js](backend/routes/social.js) (`/api/guilds/:id/social` GET/POST/PUT/DELETE, cookie) + 2 Bot-Endpoints in [routes/bot.js](backend/routes/bot.js) (`GET /api/bot/social/subscriptions`, `PUT /api/bot/social/subscriptions/:id/state`). DB-Helper-Set + `SOCIAL_PLATFORMS`/`SOCIAL_DEFAULTS` in [db.js](backend/db.js). Audit-Actions `SOCIAL_CREATE`/`SOCIAL_UPDATE`/`SOCIAL_DELETE`. Account-Normalisierung (Twitch/Kick lowercased), Embed-Sanitize wiederverwendet, Plattform-/Account-Wechsel resettet Polling-State.
  - Bot: neues Cog [social_notify.py](bot/cogs/social_notify.py) — `tasks.loop` (`SOCIAL_POLL_INTERVAL`, default 180s). YouTube via Atom-RSS (stdlib `xml.etree`, 0 Quota; Data-API nur für Handle-Resolution/Live-Check wenn `YOUTUBE_API_KEY` gesetzt), Twitch via Helix (App-Token + batched `Get Streams`), Kick via offizielle API (App-Token + `/public/v1/channels`). App-Tokens werden im Cog gecached. Ankündigung mit Platzhaltern `{creator}`/`{platform}`/`{url}`/`{title}`/`{type}` + optional Embed + Mention-Rolle. Erste Sichtung eines YT-Channels announced **keinen** Backlog. Neue Env-Vars in [config.py](bot/config.py) (alle optional). Nutzt `bot_get`/`bot_put` aus [utils/backend.py](bot/utils/backend.py) + rohes aiohttp für Drittanbieter-APIs.
  - Frontend: Page [SocialNotifications.vue](frontend/src/pages/SocialNotifications.vue) + Component [SocialSubscriptionRow.vue](frontend/src/components/SocialSubscriptionRow.vue) (Inline-Editor, per-Row-Save, eigene Platzhalter-Liste, ChannelSelector + RoleSelector + EmbedEditor wiederverwendet). Routen-Child `/dashboard/:guild_id/social`, Sidebar-Eintrag in Engagement-Gruppe, 9. Overview-Card. i18n-Namespace `socialNotifications` + `sidebar.linkSocial` + `overview.social*` in EN+DE.
  - 74/74 Backend-Tests grün, Frontend-Build grün (neuer Chunk `SocialNotifications` ~12.3 kB), Bot-Cogs parsen sauber.
- **Datum (vorherige Iteration):** 2026-06-06
- **Legal/Footer/Cookie:** Drei öffentliche Legal-Seiten (`/legal/impressum`, `/legal/datenschutz`, `/legal/agb` + `/legal/privacy` und `/legal/terms` als Redirects) mit gemeinsamem `LegalLayout.vue`. Globaler `AppFooter.vue` (drei Spalten, mobil gestapelt) und `CookieBanner.vue` (bottom-right, z-index 9000, AppToast bleibt darüber) sind global in `App.vue` eingebunden. Inline-Footer aus `Landing.vue` entfernt (DRY). i18n: neue Top-Level-Namespaces `footer`, `cookieBanner`, `legal` in `en.js` + `de.js`. **TODO vor Live-Gang:** Platzhalter `[Bitte ausfüllen — …]`, `[E-Mail]`, `[Telefon (optional)]`, `[Datenschutz-Kontakt-E-Mail]`, `[Hosting-Anbieter]` in `frontend/src/i18n/locales/de.js` (+ EN-Pendants) durch echte Daten ersetzen. Cookie-Consent-Wert liegt in `localStorage.projectx_cookie_consent` (`accepted` | `necessary`).
- **Stand:** Auth-Flow komplett refactored (Cookie-Session, JWT, Admin-Bit, Reconcile, `/auth/me`+`/logout`+`/refresh-guilds`, `/api/bot/*` mit `X-Bot-Token`, Schema-Version 2). Frontend visuell komplett neu (Landing/Servers/DashboardLayout/Overview, neue Komponenten-Suite, Design-Tokens, Inter+Space Grotesk+JetBrains Mono). Backend: 74/74 Tests grün. Frontend: `npm run build` grün.
- **Patch nach erstem Live-Test (Callback-Timeout):** WAL + `synchronous=NORMAL` aktiviert, `runInTransaction`-Helper, `reconcileUserGuilds` jetzt in einer Transaktion, Frontend-Axios-Timeout 15s → 45s, Timing-Logs `[auth/callback]` im Backend-Output.
- **Routing-Refactor:** Guild-Auswahl wohnt jetzt unter `/dashboard` (vorher `/`). Landing (`/`) ist **frei zugänglich** — auch authed User können dorthin zurück (Home-Button im `/dashboard`-Header). AuthCallback redirected nach `/dashboard`. `HomePage.vue` entfernt (Branch nicht mehr nötig). Der `guestOnly`-Guard wurde wieder entfernt, da er einen manuellen Wechsel zur Landing blockiert hätte.
- **Berechtigungs-Filter:** `GET /api/guilds` liefert nur noch Guilds, in denen der User Owner oder Admin ist. `requireGuildAccess` verlangt jetzt ebenfalls Owner/Admin (Defense-in-Depth: Member kann auch per direktem API-Call keine Settings ändern). Member-Badge im Frontend entfernt.
- **i18n:** Komplette UI ist mehrsprachig (EN + DE). Sprach-Switcher in der NavBar. Hand-gerollte Lösung in [`frontend/src/i18n/`](frontend/src/i18n/), Persistenz in localStorage, Browser-Sprache als Initialwert. Keine externe Dep.
- **Dev-Watcher Polling-Fix:** `node --watch` crashed mit `ECONNRESET` auf X:\-Laufwerk. Backend dev-Script auf `nodemon --legacy-watch`, Vite-Config auf `server.watch.usePolling: true`. Symptom: Dev-Server crasht ~1s nach Start mit `Error: ECONNRESET, watch`.
- **Module-Rollout (Schema v3):** Drei neue Feature-Module live — **Auto-Role**, **Server-Logs**, **Moderation**.
  - Backend: Migration v3 + 3 neue Tabellen (`guild_autorole_settings`, `guild_log_settings`, `guild_moderation_settings`), 6 neue Cookie-Endpoints unter `/api/guilds/:id/settings/{autorole,logs,moderation}` (GET/PUT) und 3 neue Bot-Endpoints unter `/api/bot/guilds/:id/settings/{autorole,logs,moderation}`. Helper-Set + `MODULE_DEFAULTS` in [db.js](backend/db.js). Audit-Log-Actions: `UPDATE_AUTOROLE_SETTINGS`/`UPDATE_LOG_SETTINGS`/`UPDATE_MODERATION_SETTINGS`.
  - Bot: 3 neue Cogs ([autorole.py](bot/cogs/autorole.py), [logs.py](bot/cogs/logs.py), [moderation.py](bot/cogs/moderation.py)) + shared Helper [bot/utils/backend.py](bot/utils/backend.py) (`fetch_bot_settings`). Moderation nutzt Sliding-Window via `collections.deque(maxlen=…)` pro `(guild_id, user_id)`.
  - Frontend: Pages [AutoRole.vue](frontend/src/pages/AutoRole.vue), [Logs.vue](frontend/src/pages/Logs.vue), [Moderation.vue](frontend/src/pages/Moderation.vue) + Routen-Childs unter `/dashboard/:guild_id/{autorole,logs,moderation}`. Neue Component [ChipInput.vue](frontend/src/components/ChipInput.vue) (verwendet für Role-IDs in AutoRole und Banned-Words in Moderation, Enter/Komma als Separator, Validator-Prop für Snowflake-Pattern). Sidebar mit zwei Gruppen umstrukturiert (`Configuration` = Overview/Welcome/Leave/AutoRole, `Moderation` = Logs/Moderation). Overview zeigt jetzt 5 Modul-Cards mit Live-Enabled-Status (via `Promise.all` der GET-Endpoints in `onMounted`). i18n vollständig in EN + DE.
  - 74/74 Backend-Tests grün, Frontend `npm run build` grün.
- **Bot-Presence (Schema v4):** Backend kennt jetzt pro Guild, ob der Bot dort drauf ist (`guilds.bot_present`). Frontend [Overview.vue](frontend/src/pages/Overview.vue) zeigt bei `!bot_present` einen Invite-Banner oben und ersetzt die Configure-Buttons der Modul-Cards durch „Invite bot"-Links auf die Discord-OAuth-Invite-URL (Permissions-Bitmask `268446726` = VIEW_CHANNEL + SEND_MESSAGES + MANAGE_MESSAGES + KICK_MEMBERS + BAN_MEMBERS + MANAGE_ROLES). Bot-Cog [presence.py](bot/cogs/presence.py) synct via `PUT /api/bot/presence` auf `on_ready` / `on_guild_join` / `on_guild_remove` und alle 5 Minuten. Backend-Helper `syncBotPresence` in einer Transaktion. i18n-Keys `common.invite`, `common.botMissing`, `overview.botMissing*` + `overview.inviteBot` in EN+DE.
- **Welcome/Leave-Erweiterung (Schema v5):** Beide Module bekommen volle Embed-Unterstützung + erweiterte Optionen.
  - Schema: 9 neue Spalten in `guild_settings` (Migration v5, idempotent). `welcome_embed`/`leave_embed` als JSON-TEXT, sanitisiert + geparst von `db.js`-Helpern. Color-Hex-Validation, URL-Form-Check, Längen-Caps, Delete-After-Clamp 0..600.
  - Backend: [routes/settings.js](backend/routes/settings.js) komplett auf die erweiterte Shape umgestellt; Validation lebt in `upsertGuildSettings` (Single Source of Truth). [routes/bot.js](backend/routes/bot.js) liefert die full extended raw shape (mit parsed Embed-Objekten). Neue Konstante `WELCOME_LEAVE_DEFAULTS`.
  - Bot: [welcome_leave.py](bot/cogs/welcome_leave.py) komplett refactored — Helper `resolve_placeholders` mit erweitertem Set (`{user.name|id|tag|avatar}`, `{guild.id|member_count}`), `build_embed` baut `discord.Embed`, Auto-Delete via `asyncio.create_task(_schedule_delete(...))`, optional DM via `member.send` (try/except), `welcome_ping_user` postet `member.mention` als `content` neben dem Embed. `/welcome_test` reused das echte Send-Path mit `[TEST]`-Marker. `fetch_bot_settings` akzeptiert jetzt `module=None` für `/settings` (Welcome/Leave).
  - Frontend: Welcome/Leave-Pages komplett rewritten — Segmented-Mode-Switch Plain/Embed, neue Component [EmbedEditor.vue](frontend/src/components/EmbedEditor.vue) (Title, Description mit Counter, synchronisierter Color-Picker + Hex-Draft mit Regex-Revert-on-Blur, Author, Thumbnail/Image mit Live-Preview, Footer, Timestamp-Toggle), DM-Card + Auto-Delete-Slider (Welcome only). Erweiterte [DiscordMessagePreview.vue](frontend/src/components/DiscordMessagePreview.vue) rendert echte Discord-Embed-Optik (Color-Bar links, Author-Row, Title, Description, Thumbnail rechts, Image unten, Footer + Timestamp; Mock-Placeholder `Alex` / `42` / Gradient-Avatar-Fallback). Geteilter Helper [embedPlaceholders.js](frontend/src/components/embedPlaceholders.js) (`PLACEHOLDERS` + `insertAtCaret`). Store [guildSettings.js](frontend/src/stores/guildSettings.js) mit `defaultEmbed()` + deep-merge für nested Embeds + `normalizeSettings()` defensiv. i18n-Namespace `embedEditor` + erweiterte `welcome.*`/`leave.*` Keys in EN+DE.
  - 74/74 Backend-Tests grün, Frontend `npm run build` grün (28.9s, 140 Module).
- **Channel/Role-Selektoren (Schema v6):** Statt rohe IDs zu tippen, wählen Dashboard-User Channels und Rollen jetzt aus Dropdowns.
  - Backend: Migration v6 + 2 neue Tabellen `guild_channels` (`id`, `guild_id`, `name`, `type ∈ {text|voice|category|announcement|forum|stage|thread}`, `parent_id`, `position`) und `guild_roles` (`id`, `guild_id`, `name`, `color INT`, `position`, `managed`, `is_default`), beide mit `id_guild`-Index. Helper `replaceGuildChannels` / `replaceGuildRoles` (Bulk-Replace in einer Transaktion). Neue Routes: `GET /api/guilds/:id/{channels,roles}` (cookie-protected, sortiert by hierarchy) und `PUT /api/bot/guilds/:id/{channels,roles}` (bot-only).
  - Bot: neues Cog [guild_sync.py](bot/cogs/guild_sync.py) — synct via `on_ready`, `on_guild_join`, `on_guild_channel_create|update|delete`, `on_guild_role_create|update|delete` und 15min-Loop. `bot/utils/backend.py` um `bot_put`-Helper erweitert.
  - Frontend: Composable [useGuildResources.js](frontend/src/composables/useGuildResources.js) (per-Guild-Cache, 5min stale-while-revalidate, gemeinsam von beiden Selektoren genutzt). Komponenten [ChannelSelector.vue](frontend/src/components/ChannelSelector.vue) (single-select mit Search, Category-Grouping, Type-Icons) und [RoleSelector.vue](frontend/src/components/RoleSelector.vue) (single/multi, Color-Dots, Hierarchie-Sortierung). Integriert in: Welcome/Leave/Logs (`*_channel_id` → ChannelSelector `types=['text','announcement']`), Moderation (`mute_role_id` → RoleSelector single), AutoRole (`role_ids` → RoleSelector multi, ChipInput entfernt). i18n-Namespace `resourceSelector` in EN+DE.
  - 74/74 Backend-Tests grün, Frontend `npm run build` grün.
- **Engagement-Module (Schema v7):** Drei neue Module live — **Reaction Roles**, **Leveling/XP**, **Custom Commands**.
  - Schema: 6 neue Tabellen (siehe § 8), Migration v7 idempotent + Mirror in `initializeDatabase()`. Level-Math (MEE6-Curve) als exportierter Helper.
  - Backend: 3 neue Route-Files ([reaction-roles.js](backend/routes/reaction-roles.js), [leveling.js](backend/routes/leveling.js), [custom-commands.js](backend/routes/custom-commands.js)) — full CRUD pro Modul. 5 neue Bot-Endpoints in [bot.js](backend/routes/bot.js) — u. a. `POST /api/bot/guilds/:id/leveling/xp` mit `grantXp` in `BEGIN IMMEDIATE`-Transaktion (kein Double-Grant). Leaderboard via `idx_lvl_users_guild_xp`-Index. Custom-Command-Duplicate → 409.
  - Bot: 3 neue Cogs ([reaction_roles.py](bot/cogs/reaction_roles.py), [leveling.py](bot/cogs/leveling.py), [custom_commands.py](bot/cogs/custom_commands.py)). Custom-Emoji-Resolution symmetrisch zwischen Cache und Reaction-Payload via Regex `^<a?:[^:]+:(\d+)>$`. Leveling: Bot POSTet pro Message → Backend macht Cooldown/Level-Math, Bot postet Announcement + Rewards (non-stacking: optionales `previous_role_rewards`-Feld vom Backend wird vor Add abgezogen). Custom Commands: in-memory Cache, 5min Refresh, nutzt `resolve_placeholders` aus `welcome_leave`. [bot/utils/backend.py](bot/utils/backend.py) um `bot_post` + `bot_get` erweitert.
  - Frontend: 3 neue Pages ([ReactionRoles.vue](frontend/src/pages/ReactionRoles.vue), [Leveling.vue](frontend/src/pages/Leveling.vue), [CustomCommands.vue](frontend/src/pages/CustomCommands.vue)) + neue Komponente [CustomCommandRow.vue](frontend/src/components/CustomCommandRow.vue). Reaction-Roles: Inline-Editor (kein Modal) mit Channel-Selector + Mappings-Repeater (Emoji-Input + Role-Selector pro Row). Leveling: Settings-Form + Rewards-Repeater + **Leaderboard Top 25** als Table. Custom Commands: per-Row-Edit (kein Sticky-Bar), 409-Toast bei Duplicate. Ignored-Channels in Leveling via Picker+Add-Pattern (Workaround weil ChannelSelector single-only ist). Sidebar bekommt 3. Gruppe `Engagement`. Overview-Cards um 3 Karten erweitert (5 → 8). i18n-Namespaces `reactionRoles`, `leveling`, `customCommands` in EN+DE.
  - 74/74 Backend-Tests grün, Frontend-Build 13.02s grün (165+ Module, neue Lazy-Chunks für ReactionRoles 11.28kB + Leveling 14.47kB).

> Bei der nächsten Anpassung am Code: Datum hier aktualisieren UND betroffene Abschnitte oben pflegen (siehe Pflicht-Regel ganz oben).
