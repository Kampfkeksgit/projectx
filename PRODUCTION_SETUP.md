# Produktions-Setup — projectx

> Anleitung zum Deploy von projectx (Bot + Backend + Frontend) in Produktion via Docker Compose.
> Pre-Deploy-Checks: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md). Architektur/Env-Referenz: [CLAUDE.md](CLAUDE.md). Test-Abnahme: [TEST_PLAN.md](TEST_PLAN.md).

---

## 1. Überblick

Der empfohlene Weg ist der Container-Stack aus [docker-compose.yml](docker-compose.yml). Drei Services:

| Service    | Rolle | Netzwerk |
|------------|-------|----------|
| `backend`  | Express-API (intern `:3000`, **nicht** auf den Host gepublished) | intern |
| `bot`      | Discord-Bot (verbindet sich zum Backend via `BACKEND_URL`) | intern |
| `frontend` | nginx — serviert die gebaute SPA **und** reverse-proxyt `/api` → `backend` | `default` + extern `proxy` |

- **Kein eigener DB-Service** — SQLite ist dateibasiert; Persistenz über das Named Volume `projectx-data` an `/data`.
- Alle Dockerfiles liegen im Root (`Dockerfile.backend`, `Dockerfile.bot`, `Dockerfile.frontend`) und builden mit `context: .`.

---

## 2. Deploy

```bash
docker compose up --build
```

Vorab die Variablen aus [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) setzen (in Portainer als Stack-Env oder in einer `.env` neben der Compose-Datei). Pflicht: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_TOKEN`, `DISCORD_REDIRECT_URI`, `FRONTEND_URL`, `SESSION_SECRET`, `BOT_API_KEY`, `OWNER_DISCORD_ID`.

### Frontend-Build-Args (wichtig)
`VITE_*` werden **zur Build-Zeit** eingebacken (unter `frontend.build.args`), nicht zur Laufzeit. Daher:
- `VITE_BACKEND_URL=/api` — hält Frontend und API **same-origin** (nginx proxyt `/api` → `backend`), also keine CORS-/Cookie-Probleme.
- Bei Änderung von `VITE_*` muss das Frontend-Image **neu gebaut** werden (`--build`).

### Reverse-Proxy in nginx
[nginx.conf](nginx.conf) serviert die SPA (`try_files … /index.html`) und leitet `/api/` an `http://backend:3000` weiter (Service-Name via Docker-DNS aufgelöst, gibt 502 statt zu crashen, wenn das Backend kurz weg ist).

---

## 3. TLS / Domain

### Variante A — Nginx Proxy Manager (empfohlen)
[nginx-proxy-manager.yml](nginx-proxy-manager.yml) ist ein **eigener** Portainer-Stack vor projectx.

1. Externes Docker-Netz **einmalig** anlegen (Portainer → Networks → Add → Name `proxy`, Driver `bridge`).
2. NPM-Stack deployen. Der `frontend`-Service hängt am selben `proxy`-Netz, daher erreicht NPM ihn als Host `frontend:80`.
3. NPM-Admin-UI unter `http://<host>:81` (Default-Login `admin@example.com` / `changeme` — **sofort ändern**).
4. Proxy Host anlegen: Domain → Forward `http://frontend:80`, Let's-Encrypt-Zertifikat anfordern, „Websockets Support" + „Force SSL" aktivieren.

**HTTPS ist Pflicht**, da `NODE_ENV=production` das Session-Cookie auf `Secure` setzt.

### Variante B — ohne NPM (direkt)
Im `frontend`-Service das `proxy`-Netz entfernen und `ports: ["8080:80"]` setzen (sowie den Top-Level-`networks:`-Block streichen). TLS muss dann anderweitig terminiert werden — ohne HTTPS funktioniert der Login in Produktion nicht.

> Hinweis: Die Compose-Datei mappt standardmäßig `${FRONTEND_PORT:-8080}:80` für Direkt-/LAN-Zugriff; NPM erreicht den Container parallel über das `proxy`-Netz. Für reinen NPM-/Prod-Betrieb das `ports`-Mapping entfernen.

---

## 4. Produktions-Auth-Hinweise

- **`NODE_ENV=production` → `Secure`-Cookie → HTTPS Pflicht.** In Dev ist `Secure=false` korrekt.
- **`FRONTEND_URL`** muss gesetzt sein, damit Cookies/CORS korrekt funktionieren. Bei same-origin (`VITE_BACKEND_URL=/api` + nginx-Proxy) gibt es ohnehin keine Cross-Origin-Probleme.
- **`SESSION_SECRET`** stark zufällig wählen — eine Rotation invalidiert alle aktiven Sessions.
- **`BOT_API_KEY`** muss in Bot **und** Backend identisch sein (Shared Secret für `/api/bot/*`).
- **`DISCORD_REDIRECT_URI`** muss exakt im Discord-Portal und in Backend + Frontend übereinstimmen.

---

## 5. Datenbank-Persistenz & Backups

- Daten liegen im Named Volume `projectx-data` (`/data/bot.db`).
- Migrationen laufen automatisch beim Backend-Start (Schema-Version **40**).
- **Backup:** das Volume regelmäßig sichern, z. B. Container stoppen und `bot.db` aus dem Volume kopieren bzw. `docker run --rm -v projectx-data:/data -v $(pwd):/backup alpine cp /data/bot.db /backup/`.
- SQLite läuft mit `journal_mode = TRUNCATE` (nicht WAL — bewusst, siehe [CLAUDE.md](CLAUDE.md) §8). Beim Sichern auf einen konsistenten Zustand achten (idealerweise Backend kurz stoppen).

---

## 6. Verifikation nach Deploy

```bash
# Backend-Health (über die Domain)
curl https://<deine-domain>/api/health
```

- Bot zeigt sich auf Discord als online.
- Frontend lädt unter der Domain, Discord-Login funktioniert (OAuth-Redirect).
- Ein Settings-Save (z. B. Welcome) persistiert und der Bot wirkt.

Vollständige End-to-End-Szenarien: [TEST_PLAN.md](TEST_PLAN.md).

---

## 7. Empfehlungen für den Betrieb

- **Skalierung:** SQLite ist single-instance. Für mehrere Backend-Instanzen → PostgreSQL; Redis als Cache.
- **Sicherheit:** Rate-Limiting vor der API, regelmäßige Dependency-Updates.
- **Monitoring:** Sentry o. Ä. für Fehler; das integrierte Admin-Health-Panel (`/admin` → Health) zeigt Bot-Latenz/Uptime, der Job- und Fehler-Viewer den Betriebszustand.
- **Wartungsmodus:** Bei Eingriffen den globalen Wartungsmodus im Admin-Bereich aktivieren (blockt Nicht-Owner-Writes mit 503).
