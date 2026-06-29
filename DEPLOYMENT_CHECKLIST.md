# Deployment-Checkliste — projectx

> Pre-Deploy-Checkliste für projectx (Bot + Backend + Frontend).
> Single Source of Truth für Architektur/Env: [CLAUDE.md](CLAUDE.md). Setup-Details: [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md). Tests: [TEST_PLAN.md](TEST_PLAN.md).

Alle Punkte vor dem Go-Live abhaken.

---

## 1. Environment-Variablen

### Bot — `bot/.env` (bzw. `.env.production.bot`)
- [ ] `DISCORD_TOKEN` — Bot-Token
- [ ] `DISCORD_CLIENT_ID`
- [ ] `DISCORD_CLIENT_SECRET`
- [ ] `BACKEND_URL` — im Container i. d. R. `http://backend:3000`
- [ ] `BOT_API_KEY` — **identisch zu `backend/.env`** (X-Bot-Token-Header)
- [ ] `BOT_VERSION` — optional (Anzeige im Admin-Health-Panel, Default `1.0.0`)
- [ ] Social-Keys (optional, Plattform wird ohne Creds übersprungen): `YOUTUBE_API_KEY`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `KICK_CLIENT_ID`, `KICK_CLIENT_SECRET`, `SOCIAL_POLL_INTERVAL`
- [ ] Premium/SKU (optional, Cog inert ohne SKU-IDs): `APPLICATION_ID`, `SKU_BASIC_ID`, `SKU_PRO_ID`, `PREMIUM_POLL_INTERVAL`

### Backend — `backend/.env` (bzw. `.env.production.backend`)
- [ ] `PORT` (Default `3000`)
- [ ] `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`
- [ ] `DISCORD_REDIRECT_URI` — muss exakt dem Eintrag im Discord-Portal entsprechen
- [ ] `FRONTEND_URL` — **Pflicht** (CORS-/Cookie-Origin)
- [ ] `DATABASE_URL` — z. B. `/data/bot.db`
- [ ] `SESSION_SECRET` — **kritisch**, stark zufällig
- [ ] `BOT_API_KEY` — identisch zum Bot
- [ ] `OWNER_DISCORD_ID` — Owner-User-ID(s), komma-separiert (schaltet den Admin-Bereich frei)
- [ ] `NODE_ENV=production`

### Frontend — `frontend/.env` (bzw. `.env.production.frontend`)
> `VITE_*` sind **Build-Args** (zur Build-Zeit eingebacken), keine Runtime-Variablen. Im Docker-Stack unter `frontend.build.args`.
- [ ] `VITE_BACKEND_URL` — `/api` (same-origin via nginx-Reverse-Proxy)
- [ ] `VITE_DISCORD_CLIENT_ID`
- [ ] `VITE_DISCORD_REDIRECT_URI`

---

## 2. Sicherheit
- [ ] `SESSION_SECRET` stark zufällig: `node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"`
- [ ] `BOT_API_KEY` stark zufällig **und in Bot + Backend identisch**: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] HTTPS aktiv — bei `NODE_ENV=production` setzt das Backend das Session-Cookie auf `Secure`; ohne HTTPS funktioniert der Login nicht
- [ ] `OWNER_DISCORD_ID` gesetzt (sonst ist der Admin-Bereich deaktiviert)
- [ ] Keine `.env` / `.env.production.*` / `bot.db` im Git committet

---

## 3. Datenbank
- [ ] SQLite-Persistenz sichergestellt — Named Volume `projectx-data` an `/data` (Docker)
- [ ] Migrationen laufen automatisch beim Backend-Start (aktuelle Schema-Version: **40**) — kein manueller Schritt
- [ ] Backup-Strategie für das Volume vorhanden (siehe [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md))

---

## 4. Discord Developer Portal
- [ ] **Privileged Gateway Intents** aktiviert: **Presence Intent** (Online/Offline-Stats) + **Server Members Intent**
- [ ] **OAuth2 Redirect URI** eingetragen — identisch zu `DISCORD_REDIRECT_URI` (Backend) und `VITE_DISCORD_REDIRECT_URI` (Frontend)
- [ ] OAuth2-Scopes: `identify email guilds`
- [ ] **Invite-Bitmask `285223990`** für den Bot-Invite (enthält u. a. Manage Channels/Roles, Move Members, Manage Guild, Kick/Ban)

---

## 5. Performance & Monitoring
- [ ] `GET /api/health` liefert 200 (Docker-Healthcheck grün)
- [ ] Bot ist auf Discord online und im Admin-Health-Panel sichtbar (Latenz/Uptime)
- [ ] Fehler-Log (`/admin` → Errors) leer bzw. nur erwartete Einträge
- [ ] Wartungsmodus deaktiviert, kein Ankündigungs-Banner aktiv (`/admin` → System)
- [ ] Empfohlen für Skalierung: SQLite → PostgreSQL bei Multi-Instance, Rate-Limiting, Sentry (siehe [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md))
