# Test-Leitfaden — projectx

> Abnahme-Leitfaden für projectx (Bot + Backend + Frontend).
> Setup/Deploy: [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md). Pre-Deploy: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md). Architektur: [CLAUDE.md](CLAUDE.md).

---

## 1. Automatisierte Tests

**Backend** — DB-Layer-Tests:

```bash
cd X:\projectx\backend
npm test          # node tests/db.test.js (74/74 grün)
```

- `[DB ERROR]`-Zeilen im Output sind **erwartet** — der Test triggert bewusst UNIQUE-/FK-Fehler, um `handleDbError` zu prüfen.
- Ergänzend: [backend/tests/verify.js](backend/tests/verify.js).
- **Frontend** hat keine automatisierten Tests. UI-Änderungen lokal im Browser verifizieren oder mindestens `npm run build` grün durchlaufen lassen.

### Lokale Test-Umgebung
1. `bot/.env` mit Test-Token + `BOT_API_KEY` (identisch zu `backend/.env`).
2. Backend: `cd X:\projectx\backend && npm run dev` (Port 3000).
3. Frontend: `cd X:\projectx\frontend && npm run dev` (Port 5173).
4. Bot: `cd X:\projectx\bot && python main.py`.
5. Privater Test-Discord-Server mit eingeladenem Bot (Invite-Bitmask `285223990`).

---

## 2. Manuelle End-to-End-Szenarien (Golden Paths)

### 1 — OAuth-Login / Session / Logout
1. Landing öffnen → „Mit Discord anmelden".
2. Auf Discord autorisieren → Rückleitung nach `/auth/callback` → `/dashboard`.
3. **Erwartet:** Avatar/Name in der NavBar; Cookie `projectx_session` (HttpOnly) gesetzt; **kein** Token im localStorage.
4. Seite neu laden → Session bleibt bestehen (`/auth/me` liefert 200).
5. Logout → zurück auf Landing, Cookie gelöscht, `/auth/me` liefert 401.

### 2 — Server-Auswahl (nur Owner/Admin)
1. Unter `/dashboard` werden nur Server gelistet, in denen der User **Owner oder Administrator** ist.
2. **Erwartet:** Member-only-Server erscheinen nicht. Gesperrte Server sind rot umrandet und nicht klickbar.
3. Auf einen Server klicken → Modul-Übersicht öffnet sich.

### 3 — Free-Modul konfigurieren + Bot wirkt (Beispiel: Welcome)
1. Modul „Welcome" öffnen, aktivieren, Channel wählen, Nachricht/Embed mit Platzhaltern (`{user.name}`, `{guild.member_count}`) setzen.
2. Live-Vorschau aktualisiert sich; speichern → Erfolgs-Toast; nach Reload sind die Werte da.
3. Ein Mitglied tritt dem Server bei (oder `/welcome_test`).
4. **Erwartet:** Der Bot postet die konfigurierte Nachricht im richtigen Channel mit aufgelösten Platzhaltern.

### 4 — Premium-Gating (gesperrt ohne Tier / entsperrt mit Tier)
1. Auf einem Free-Server ein Premium-Modul öffnen (z. B. Tickets = Pro, Leveling = Basic).
2. **Erwartet:** Statt der Konfig-Seite erscheint die `PremiumLock`-Sperrseite; Sidebar zeigt Schloss-Icon; ein API-Write liefert 403 `premium_required`.
3. Als Owner unter `/admin` → Guild den Tier setzen (oder Premium-Code einlösen unter `/dashboard/:id/premium`).
4. Modul erneut öffnen → **Erwartet:** Konfig-Seite ist freigeschaltet, Speichern funktioniert, das Bot-Feature wird aktiv.

### 5 — Moderation & Logs
1. Moderation aktivieren: Banned-Words / Anti-Invite / Anti-Spam + Aktion (delete/warn/mute/kick/timeout) konfigurieren, speichern.
2. Verstoß im Test-Server provozieren → **Erwartet:** Bot wendet die Aktion an; bei `warn_threshold` greift die Eskalation.
3. Logs aktivieren, Log-Channel setzen, Events togglen.
4. Join/Leave/Message-Delete auslösen → **Erwartet:** Embeds im Log-Channel; ignorierte Channels werden ausgelassen.

### 6 — Admin-Bereich (Owner-only)
1. Als Owner (`OWNER_DISCORD_ID`) `/admin` öffnen.
2. User sperren → **Erwartet:** gesperrter User erhält 403 bei Login/`/auth/me` (Owner selbst kann nicht gesperrt werden).
3. Guild sperren → **Erwartet:** Server im Picker rot/nicht klickbar, Bot wird auf dem Server inert.
4. Wartungsmodus aktivieren → **Erwartet:** globaler Wartungs-Banner; Nicht-Owner-Writes liefern 503; Owner bleibt schreibfähig.

### 7 — Mehrsprachigkeit
1. In der NavBar (bzw. Account-Sheet) die Sprache wechseln: EN / DE / TR / RU / PL.
2. **Erwartet:** UI-Strings übersetzen sich sofort; Auswahl bleibt nach Reload (localStorage `projectx_locale`).

### 8 — Mobile-UI
1. Dashboard mit `?mobile=1` öffnen (oder native App).
2. **Erwartet:** TopBar + Bottom-TabBar + Account-Sheet statt Desktop-Shell; Overview einspaltig; Save-Bar über der Bottom-Nav. `?mobile=0` schaltet zurück; Desktop-Web bleibt unverändert.

---

## 3. Abnahme-Checkliste
- [ ] `npm test` grün (74/74)
- [ ] `npm run build` (Frontend) grün
- [ ] Szenarien 1–8 erfolgreich
- [ ] Keine unerwarteten Fehler in Browser-, Backend- und Bot-Konsole
- [ ] Bereit für Produktion (siehe [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md))

---

## 4. Hinweise
- Discord-Rate-Limits können bei intensivem Testen auftreten (der Bot pacet Log-Bursts pro Channel).
- Der Bot braucht Sende-Rechte in den konfigurierten Channels.
- Settings-Änderungen aus dem Dashboard greifen im Bot teils erst nach kurzer Cache-TTL (z. B. Command-Config/Allgemein-Settings bis ~60s).
