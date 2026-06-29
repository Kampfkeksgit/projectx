# projectx — Discord-Bot-Dashboard

**projectx** ist ein Discord-Bot-Dashboard, das aus drei Komponenten besteht und Server-Administratoren über ein Web-Interface ~34 Module konfigurieren lässt (Welcome/Leave, Moderation, Leveling, Tickets, Giveaways, Economy, Statistiken, Backups, Games u. v. m.).

| Komponente | Stack | Zweck |
|---|---|---|
| [bot/](bot/) | Python 3.8+, discord.py 2.3.2 | Reagiert auf Discord-Gateway-Events, lädt ~35 Cogs, liest Settings aus dem Backend |
| [backend/](backend/) | Node.js 18+, Express 4, SQLite3 | REST-API, Discord-OAuth2, Settings-CRUD, Audit-Log, Cookie-Session, interne Bot-API |
| [frontend/](frontend/) | Vue 3 + Vite 4, Vue Router 4, Axios | Web-Dashboard zum Konfigurieren der Module |

**Datenfluss:** Frontend ⇄ Backend über HTTP-only Cookie-Session (JWT); Backend ⇄ SQLite direkt; Bot ⇄ Backend über die interne API `/api/bot/*` (abgesichert per `X-Bot-Token`-Shared-Secret); Bot ⇄ Discord über das Gateway.

> Die autoritative interne Referenz für Architektur, Module, API-Verträge und Konventionen ist [CLAUDE.md](CLAUDE.md). Dieses README ist der Setup-Einstieg.

---

## Tech-Stack

**Bot** ([bot/requirements.txt](bot/requirements.txt)): `discord.py 2.3.2`, `python-dotenv`, `aiohttp`, `requests`, `Pillow` (optional — Poker-Karten-Rendering, fällt ohne Pillow auf Text zurück).

**Backend** ([backend/package.json](backend/package.json)): ESM, `express 4`, `sqlite3`, `cors`, `dotenv`, `axios`, `cookie-parser`, `jsonwebtoken`. Dev: `nodemon` (Polling-Watch). (`express-session`/`passport*` sind Legacy und ungenutzt.)

**Frontend** ([frontend/package.json](frontend/package.json)): `vue 3`, `vue-router 4`, `axios`, `vite 4`. Bewusst **ohne** Tailwind/Pinia/UI-Kit — Styling vanilla via Design-Tokens. Optional als Android-App via Capacitor 6.

---

## Verzeichnisstruktur (Top-Level)

```
projectx/
├── bot/                  # Python Discord-Bot (main.py, config.py, cogs/, utils/)
├── backend/              # Node/Express API (server.js, db.js, migrations.js, routes/, middleware/)
├── frontend/             # Vue 3 Dashboard (src/, vite.config.js, android/)
├── docker-compose.yml    # backend + bot + frontend (SQLite dateibasiert, kein db-Service)
├── Dockerfile.{backend,bot,frontend}
├── nginx.conf            # Frontend-Container: SPA + /api-Reverse-Proxy → backend
├── nginx-proxy-manager.yml # Separater Stack: TLS/Let's Encrypt vor dem Frontend
├── ARCHITECTURE.md       # System-Design (autoritativ für Architektur)
├── PRODUCTION_SETUP.md   # Production-Guide
├── DEPLOYMENT_CHECKLIST.md
└── CLAUDE.md             # Interne Single-Source-of-Truth-Referenz
```

---

## Voraussetzungen

- **Node.js** 18+ (Backend + Frontend)
- **Python** 3.8+ (Bot)
- **Discord-Application** mit OAuth2-Credentials + Bot-Token ([Discord Developer Portal](https://discord.com/developers/applications))

Im Dev-Portal aktivieren: **Message Content Intent**, **Server Members Intent** und **Presence Intent** (privilegiert — Presence wird für Online/Offline-Statistiken benötigt).

---

## Lokales Setup / Quick Start

PowerShell-Syntax (Windows). Lege zuerst die `.env`-Dateien an (siehe nächster Abschnitt).

### Backend (Port 3000)
```powershell
cd X:\projectx\backend
npm install
npm run dev          # nodemon --legacy-watch (Polling — Windows-Watch-Fix)
# npm start          # Production
# npm test           # node tests/db.test.js
```

### Frontend (Port 5173)
```powershell
cd X:\projectx\frontend
npm install
npm run dev          # vite (server.watch.usePolling = true)
# npm run build      # → dist/
# npm run preview
```

### Bot
```powershell
cd X:\projectx\bot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Bot zum Test-Server einladen
Im Dev-Portal unter OAuth2 → URL Generator den `bot`-Scope wählen und die nötigen Permissions setzen (die aktuelle Invite-Bitmask im Dashboard ist `285223990`). Dashboard danach öffnen: `http://localhost:5173`.

---

## Environment-Variablen

Die vollständige Liste mit Beschreibungen steht in [CLAUDE.md](CLAUDE.md) §5. `.env`-Dateien **niemals committen**. Die wichtigsten:

**`bot/.env`**
```env
DISCORD_TOKEN=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
BACKEND_URL=http://localhost:3000
BOT_API_KEY=...            # MUSS identisch zum Backend sein
DATABASE_URL=bot.db
```

**`backend/.env`**
```env
PORT=3000
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:5173/auth/callback
FRONTEND_URL=http://localhost:5173   # Pflicht für Cookies/CORS
DATABASE_URL=./data/bot.db
SESSION_SECRET=...                    # signiert das Session-JWT (kritisch)
BOT_API_KEY=...                       # identisch zum Bot
OWNER_DISCORD_ID=...                  # schaltet das Admin-Panel frei (leer = aus)
NODE_ENV=development                  # production → Secure-Cookie (HTTPS Pflicht)
```

**`frontend/.env`**
```env
VITE_BACKEND_URL=http://localhost:3000/api
VITE_DISCORD_CLIENT_ID=...
VITE_DISCORD_REDIRECT_URI=http://localhost:5173/auth/callback
```

Secrets generieren:
- `SESSION_SECRET`: `node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"`
- `BOT_API_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

> **Auth-Modell:** Login läuft über Discord-OAuth2; das Backend setzt ein HTTP-only Session-Cookie (`projectx_session`, JWT). Es gibt **keine** Bearer-Tokens und **kein** localStorage im Frontend. Details: [CLAUDE.md](CLAUDE.md) §6.

---

## Docker (Production-like)

```powershell
docker compose up --build
```

Services: `backend` (intern :3000, nicht published), `bot`, `frontend` (nginx serviert die SPA + reverse-proxyt `/api` → backend). **Kein `db`-Service** — SQLite ist dateibasiert, Persistenz über das Named Volume `projectx-data`. `VITE_*`-Variablen sind **Build-Args** (siehe Kopf von [docker-compose.yml](docker-compose.yml)).

**TLS:** Der `frontend` hängt am externen Docker-Netz `proxy`; ein separater Nginx-Proxy-Manager-Stack ([nginx-proxy-manager.yml](nginx-proxy-manager.yml)) macht Let's-Encrypt-TLS. **HTTPS ist in Production Pflicht**, da `NODE_ENV=production` das Session-Cookie auf `Secure` setzt. Vollständiger Guide: [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) + [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

---

## Tests

```powershell
cd X:\projectx\backend
npm test          # node tests/db.test.js
```

`[DB ERROR]`-Zeilen im Output sind erwartet — der Test triggert bewusst UNIQUE/FK-Fehler. Das Frontend hat aktuell keine automatisierten Tests; UI-Änderungen lokal im Browser bzw. via `npm run build` verifizieren.

---

## Troubleshooting (Kurzform)

Vollständige Tabelle in [CLAUDE.md](CLAUDE.md) §12.

| Symptom | Ursache / Fix |
|---|---|
| Bot bekommt **401** von `/api/bot/...` | `BOT_API_KEY` fehlt oder ist zwischen `bot/.env` und `backend/.env` unterschiedlich. |
| Bot bekommt **500** von `/api/bot/...` | `BOT_API_KEY` ist im Backend nicht gesetzt — Server lehnt aus Sicherheit ab. |
| Frontend wird auf `/` zurückgeworfen / `/auth/me` 401 | Cookie kommt nicht an: CORS-Origin-Mismatch oder `FRONTEND_URL` falsch. In Prod HTTPS prüfen (`Secure`-Cookie). |
| OAuth-Callback schlägt fehl | Redirect-URI muss in der Discord-App **und** beiden `.env`-Dateien identisch sein. |
| `ECONNRESET, watch` crasht `npm run dev` | Windows + nicht-Standard-Laufwerk (`X:\`). Backend nutzt `nodemon --legacy-watch`, Frontend `server.watch.usePolling: true` — beides aktiv lassen. |
| `SQLITE_IOERR: disk I/O error` auf allen Reads | WAL-Mode scheitert auf dem `X:`-Volume. Fix aktiv: `journal_mode = TRUNCATE` in [backend/db.js](backend/db.js) — **niemals** zurück auf WAL stellen. |
| `Cannot connect to host localhost:3000` (Bot) | IPv4/IPv6-Dual-Stack. Backend bindet auf `0.0.0.0` ([backend/server.js](backend/server.js)). |

---

## Weiterführende Dokumentation

- **Architektur / Datenflüsse:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **DB-Schema (Version 40):** [backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md)
- **Deployment:** [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md), [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- **Interne Single Source of Truth (Module, API-Verträge, Konventionen):** [CLAUDE.md](CLAUDE.md)
- **Endnutzer-Doku (GitBook):** [docs/](docs/)
