# boerdi-chat

Cleaner Neubau des WLO-Chatbots **BadBoerdi** (Arbeitstitel „BadBoerdi 2.0"):

- **Backend:** FastAPI + LangGraph, PostgreSQL 17 + pgvector — clusterfähig (N stateless Replikas)
- **Chat-Widget:** Angular-21-Webkomponente `<boerdi-chat>` (zoneless, Single-File-Bundle)
- **Studio/Webadmin:** Angular-SPA im selben Workspace (Schema-getriebene Formulare)

Leitprinzipien: minimaler Eigencode, maximale Nachnutzung stabiler Open-Source-Software
(nur MIT/Apache-2.0/BSD-artige Lizenzen), **volle Funktions- und Config-Parität** zum
Altsystem, generisch über deklarative Konfiguration.

| | |
|---|---|
| 🚀 **Auf einem Server installieren** (Debian 13, Docker, Seed-Daten) | [INSTALL.md](INSTALL.md) |
| 🛠 Betrieb danach (Skalieren, Backup, Restore, Rollback) | [deploy/README.md](deploy/README.md) |
| 🏗 **Architektur** — Bestandteile, Stack, Abläufe (Einstieg für Entwickler) | [docs/architektur.md](docs/architektur.md) |
| 🧩 **Chatbot einbinden** — Browser-Plugin / fremde Seite | [docs/browser-plugin-einbindung.md](docs/browser-plugin-einbindung.md) |
| 🏫 **Chatbot einbinden** — edu-sharing-Repositorium (mit Ticket-Anmeldung) | [docs/edu-sharing-einbindung.md](docs/edu-sharing-einbindung.md) |
| 📘 Bauplan/Spec (Quelle der Wahrheit) | [docs/plans/2026-07-10-boerdi-chat-neubau.md](docs/plans/2026-07-10-boerdi-chat-neubau.md) |
| 🤖 Arbeits-Hinweise für KI-Sessions | [CLAUDE.md](CLAUDE.md) |
| 🏛 Altsystem (Referenz, läuft parallel) | `../badboerdi/` |
| 🔌 WLO-MCP-Server (extern, unverändert) | `../wlo-mcp-server/` |

**Status:** Umsetzung läuft paketweise (P0–P11) — der aktuelle Stand steht in der
Status-Tabelle oben in der Spec. Das Altsystem bleibt bis zum Cutover (P11) produktiv.
