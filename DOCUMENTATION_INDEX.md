# 📚 Dokumentations-Index — projectx

Einstiegspunkt zu allen Dokumentationsdateien des **projectx** Discord-Bot-Dashboards.
Hier findest du den schnellsten Weg zum richtigen Dokument.

---

## 🚀 Schnelleinstieg

| Du willst … | Lies |
|---|---|
| Das Projekt lokal aufsetzen & verstehen | [README.md](README.md) |
| Verstehen, wie die Komponenten zusammenspielen | [ARCHITECTURE.md](ARCHITECTURE.md) |
| In Produktion deployen | [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) + [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) |
| Das System manuell testen | [TEST_PLAN.md](TEST_PLAN.md) |
| Das Datenbankschema nachschlagen | [backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md) |
| Eine DB-Helfer-Funktion finden | [backend/DATABASE_FUNCTIONS.md](backend/DATABASE_FUNCTIONS.md) |
| Tiefe Detail-Referenz (verbindlich) | [CLAUDE.md](CLAUDE.md) |
| Endnutzer-Doku (GitBook) | [docs/](docs/) |

---

## 📋 Dokumente nach Zweck

### Für Entwickler & Betrieb

| Dokument | Inhalt |
|---|---|
| **[README.md](README.md)** | Projektüberblick, Tech-Stack, lokales Setup (PowerShell), Env-Variablen, Docker, Troubleshooting |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System-Design: 3 Komponenten + SQLite, Datenflüsse, Auth, Premium-Gating, Sicherheits-/Deployment-Architektur |
| **[backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md)** | SQLite-Schema (Version 40): Tabellen-Referenz, Migrations-Übersicht v1–v40, Pragmas |
| **[backend/DATABASE_FUNCTIONS.md](backend/DATABASE_FUNCTIONS.md)** | Referenz der exportierten `db.js`-Helfer (Signatur + Zweck), inkl. der kritischen Transaktions-/Premium-Helfer |
| **[PRODUCTION_SETUP.md](PRODUCTION_SETUP.md)** | Produktions-Deployment via Docker Compose + Nginx Proxy Manager (TLS), Auth-Hinweise, Backups, Skalierung |
| **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** | Abhakbare Pre-Deploy-Checkliste (Env-Variablen, Sicherheit, DB, Discord-Portal, Monitoring) |
| **[TEST_PLAN.md](TEST_PLAN.md)** | Automatisierte Tests (`npm test`) + manuelle Golden-Path-Szenarien |
| **[CLAUDE.md](CLAUDE.md)** | **Single Source of Truth** — verbindliche, vollständige interne Referenz (Architektur, vollständige API, Schema, Konventionen, Workflows) |

### Für Endnutzer (GitBook)

Die öffentliche Endnutzer-Doku liegt unter [docs/](docs/) (Git-Sync-Quelle für GitBook):

| Dokument | Inhalt |
|---|---|
| [docs/README.md](docs/README.md) | Einführung — was projectx ist und wie es funktioniert |
| [docs/getting-started.md](docs/getting-started.md) | In vier Schritten startklar |
| [docs/modules.md](docs/modules.md) | Alle Module nach Free/Basic/Pro |
| [docs/premium.md](docs/premium.md) | Tarife, Preise & Premium-Logik |
| [docs/faq.md](docs/faq.md) | Häufige Fragen |
| [docs/SUMMARY.md](docs/SUMMARY.md) | GitBook-Inhaltsverzeichnis |

---

## 🧭 Wo schlage ich was nach?

- **Endpoint-Vertrag / Shapes** → [CLAUDE.md](CLAUDE.md) §7 (API-Übersicht)
- **Tabelle oder Migration** → [backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md), Details in [CLAUDE.md](CLAUDE.md) §8
- **Auth-Flow (OAuth, Session-Cookie, JWT)** → [ARCHITECTURE.md](ARCHITECTURE.md) + [CLAUDE.md](CLAUDE.md) §6
- **Env-Variable** → [README.md](README.md) / [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md), vollständig in [CLAUDE.md](CLAUDE.md) §5
- **Build-/Start-/Test-Befehl** → [README.md](README.md), vollständig in [CLAUDE.md](CLAUDE.md) §4
- **Fehlerbild / „warum geht X nicht?"** → [CLAUDE.md](CLAUDE.md) §12 (Troubleshooting)

---

## 🏗️ Komponenten auf einen Blick

| Komponente | Stack | Ort | Zweck |
|---|---|---|---|
| **Bot** | Python 3.8+, discord.py 2.3.2 | [bot/](bot/) | Discord-Gateway-Events, ~34 Cogs, liest Settings über `/api/bot/*` |
| **Backend** | Node.js 18+, Express 4, SQLite3 | [backend/](backend/) | REST-API, Discord-OAuth2, Settings-CRUD, Audit-Log, interne Bot-API |
| **Frontend** | Vue 3 + Vite 4 | [frontend/](frontend/) | Web-Dashboard, 5 Sprachen, Mobile-Shell (Capacitor-Android) |

Datenbank: SQLite (dateibasiert, Schema-Version **40**) — siehe [backend/DATABASE_SCHEMA.md](backend/DATABASE_SCHEMA.md).

---

> **Hinweis:** Die früheren Status-Reports (`INTEGRATION_TESTING_STATUS.md`, `VERIFICATION_CHECKLIST.md`,
> `backend/COMPLETION_REPORT.md`, `backend/IMPLEMENTATION_SUMMARY.md`) waren historische Momentaufnahmen der
> ersten Bauphase und wurden entfernt. Aktueller, verbindlicher Stand steht in [CLAUDE.md](CLAUDE.md).
