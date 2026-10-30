# boerdi-chat

Cleaner Neubau des WLO-Chatbots **BadBoerdi** (Arbeitstitel „BadBoerdi 2.0"):

- **Backend:** FastAPI + LangGraph, PostgreSQL 17 + pgvector — clusterfähig angelegt (N stateless Replikas; Züge einer Sitzung sperrt eine Postgres-Sperre über alle Replikas, Vorgabe 1 Replik)
- **Chat-Widget:** Angular-22-Webkomponente `<boerdi-chat>` (zoneless, Single-File-Bundle)
- **Studio/Webadmin:** Angular-SPA im selben Workspace (Schema-getriebene Formulare)

Leitprinzipien: minimaler Eigencode, maximale Nachnutzung stabiler Open-Source-Software
(nur MIT/Apache-2.0/BSD-artige Lizenzen), **volle Funktions- und Config-Parität** zum
Altsystem, generisch über deklarative Konfiguration.

| | |
|---|---|
| 🚀 **Auf einem Server installieren** (Debian 13, Docker, Seed-Daten) | [INSTALL.md](INSTALL.md) |
| ⚡ Kurzweg der Installation (Befehle ohne Erklärung) | [deploy/INSTALL-schnellstart.md](deploy/INSTALL-schnellstart.md) |
| 🛠 Betrieb danach (Skalieren, Backup, Restore, Rollback) | [deploy/README.md](deploy/README.md) |
| 🚢 **Übergabe an den Betrieb** — Ports, Health/Ready/Metriken, Logs, b-api, Cluster, Konfiguration | [docs/uebergabe-betrieb.md](docs/uebergabe-betrieb.md) |
| 🧮 Cluster-Abnahme (Zusagen bei mehreren Repliken, Pflicht-Einstellungen) | [docs/cluster-checkliste.md](docs/cluster-checkliste.md) |
| 🏗 **Architektur** — Bestandteile, Stack, Abläufe (Einstieg für Entwickler) | [docs/architektur.md](docs/architektur.md) |
| 🗺 **Architektur-Grafiken** — interaktiv: Gesamtbild, Software-Stack, Abläufe und Konfiguration je Modus | [Bilder (PNG)](docs/architektur-grafiken/png/) · [Übersicht und Quellen](docs/architektur-grafiken/README.md) |
| 🤖 Agent-Modus — Maschinen, Master-Skill, Grenzen | [docs/agent-modus.md](docs/agent-modus.md) |
| 🔑 MCP-Server und Anmeldung (für das MCP-Team) | [docs/mcp-und-anmeldung.md](docs/mcp-und-anmeldung.md) |
| 🧩 **Chatbot einbinden** — Browser-Plugin / fremde Seite | [docs/browser-plugin-einbindung.md](docs/browser-plugin-einbindung.md) |
| 🏫 **Chatbot einbinden** — edu-sharing-Repositorium (mit Ticket-Anmeldung) | [docs/edu-sharing-einbindung.md](docs/edu-sharing-einbindung.md) |
| 📘 Bauplan/Spec (Quelle der Wahrheit) | [docs/plans/2026-07-10-boerdi-chat-neubau.md](docs/plans/2026-07-10-boerdi-chat-neubau.md) |
| 🤖 Arbeits-Hinweise für KI-Sessions | [CLAUDE.md](CLAUDE.md) |
| 🏛 Altsystem (Referenz, läuft parallel) | `../badboerdi/` |
| 🔌 WLO-MCP-Server (extern, unverändert) | `../wlo-mcp-server-sc/` |

**Betrieb in Kürze** (Stand Paket 18, 2026-10-30):

- Start im Container: `python -m boerdi.serve` — Port **8100** öffentlich (Widget, Chat, Agent,
  Sprache, Studio), Port **8101** intern (`/health`, `/ready`, `/metrics`, `/openapi-full.json`).
- Datenbank-Stand: Migration **0016**. Der `migrate`-Dienst hebt bei jedem Deploy
  (`alembic upgrade head && boerdi import-config --werksabgleich`).
- b-api: `B_API_ROUTE` (Route des Routers, Vorgabe leer) und `B_API_KEY_MODE`
  (`auto` Vorgabe · `static` · `forward`) — [deploy/README.md](deploy/README.md).
- Ohne vorgeschalteten Proxy (Port direkt veröffentlicht, etwa im Testbetrieb mit
  `docker run`) `FORWARDED_ALLOW_IPS=127.0.0.1` setzen — sonst glaubt Uvicorn jedem
  `X-Forwarded-For` ([deploy/README.md](deploy/README.md), „Welche Proxys Uvicorn glaubt“).

**Status:** Umsetzung läuft paketweise (P0–P11) — der aktuelle Stand steht in der
Status-Tabelle oben in der Spec. Das Altsystem bleibt bis zum Cutover (P11) produktiv.
