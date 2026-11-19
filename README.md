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
| 🗺 **Architektur-Grafiken** — interaktiv: Gesamtbild, Software-Stack, Abläufe und Konfiguration je Modus, UI-Module, Datenstrom vom Upload bis Kestra | [Bilder (PNG)](docs/architektur-grafiken/png/) · [Übersicht und Quellen](docs/architektur-grafiken/README.md) |
| 🤖 Agent-Modus — Maschinen, Master-Skill, Grenzen | [docs/agent-modus.md](docs/agent-modus.md) |
| 🔑 MCP-Server und Anmeldung (für das MCP-Team) | [docs/mcp-und-anmeldung.md](docs/mcp-und-anmeldung.md) |
| 🎫 **b-api-Betrieb** — direkt mit `B_API_KEY` oder hinter dem b-api-Proxy mit Delegations-Token `bdt_` (durchgereicht, nie Rückfall), Admin-Liste für den Proxy-Eintrag, Fehlerzuordnung | [docs/b-api-betrieb.md](docs/b-api-betrieb.md) · Plan: [docs/plans/2026-11-17-b-api-delegation-und-upload.md](docs/plans/2026-11-17-b-api-delegation-und-upload.md) |
| ⚙️ **Kestra über den MCP** — schreibende Flows startet der WLO-MCP über den Repository-Proxy `/rest/bapi/**` mit der Anmeldung der Person; vorher eine Freigabe-Box mit der Vorschau des MCP (erst „Freigeben“ startet); Warten mit Stand, „Später weitermachen“ | [docs/b-api-betrieb.md](docs/b-api-betrieb.md) §5 · [docs/ablaeufe.md](docs/ablaeufe.md) („Aufträge, die schreiben“) · MCP-Plan: [docs/plans/2026-11-17-mcp-wuensche-b-api-flows.md](docs/plans/2026-11-17-mcp-wuensche-b-api-flows.md) |
| 🧭 **Nachbesserungen Themenbaum und Betrieb (Paket N)** — Betriebsanzeige der b-api im Studio und unter `/api/health`, Vokabular für Fach und Stufe, Zuordnung Datei → Punkt, Freigabe-Box | Plan: [docs/plans/2026-11-19-nachbesserungen-themenbaum-betrieb.md](docs/plans/2026-11-19-nachbesserungen-themenbaum-betrieb.md) · Notizen: [docs/aenderungen/](docs/aenderungen/) (`2026-11-19-paket-n*`) |
| 📤 **Ein Upload-Weg** — „Hier im Chat“ / „In WLO ablegen und erschließen“ / „Nur Namen senden“; ein Datenstrom aus Teilen mit `quelle`; Fach und Stufe aus dem WLO-Vokabular (wenn erreichbar), Themenbaum-Entwurf ordnet die Materialien den Punkten zu | [docs/ui-module.md](docs/ui-module.md) §6 („Ein Upload-Weg“) · Grafik: [Datenstrom (PNG)](docs/architektur-grafiken/png/datenstrom-upload-kestra.png) |
| 🧩 **Chatbot einbinden** — Browser-Plugin / fremde Seite | [docs/browser-plugin-einbindung.md](docs/browser-plugin-einbindung.md) |
| 🏫 **Chatbot einbinden** — edu-sharing-Repositorium (Anmeldung über Ticket oder aus der WLO-Sitzung) | [docs/edu-sharing-einbindung.md](docs/edu-sharing-einbindung.md) |
| 📘 Bauplan/Spec (Quelle der Wahrheit) | [docs/plans/2026-07-10-boerdi-chat-neubau.md](docs/plans/2026-07-10-boerdi-chat-neubau.md) |
| 🤖 Arbeits-Hinweise für KI-Sessions | [CLAUDE.md](CLAUDE.md) |
| 🏛 Altsystem (Referenz, läuft parallel) | `../badboerdi/` |
| 🔌 WLO-MCP-Server (extern; vorausgesetzt ist der Stand vom 07.11.2026, für die Stabilitätspunkte S1–S7 Commit `9093a5d`; ein älterer Stand geht, nutzt sie aber nicht. Kestra-Flows brauchen die Flow-Werkzeuge `wlo_start_flow`/`wlo_flow_status`/`wlo_cancel_flow` vom Stand 18.11.2026; ohne sie legt „In WLO“ nur ab, ohne Erschließung) | `../wlo-mcp-server-sc/` |
| 🔁 Anpassung an den MCP-Stand 07.11.2026 (Antwortvertrag, Anlegen mit Sammlung, Pläne, letzte Ablagen) | [docs/plans/2026-11-07-mcp-vertrag.md](docs/plans/2026-11-07-mcp-vertrag.md) |
| 🔐 Anmeldung aus der WLO-Sitzung (das Widget übernimmt auf Seiten des Repositorys die angemeldete Sitzung; `MCP_SESSION_URL`, ohne Vorgabe aus) | [docs/plans/2026-11-15-anmeldung-aus-der-sitzung.md](docs/plans/2026-11-15-anmeldung-aus-der-sitzung.md) · Einrichten: [deploy/README.md](deploy/README.md) · Antwort ans MCP-Team: [docs/mcp-antwort-2026-11-15-sitzung.md](docs/mcp-antwort-2026-11-15-sitzung.md), Folge-Antworten [-2](docs/mcp-antwort-2026-11-15-sitzung-2.md), [-3](docs/mcp-antwort-2026-11-15-sitzung-3.md), [-4](docs/mcp-antwort-2026-11-15-sitzung-4.md) |
| 🛡 Stabile MCP-Anbindung (Budget, Ausfall-Schalter, sichere Wiederholung, Anmeldung mit Frist, Abmelden widerruft) | [docs/plans/2026-11-07-stabilitaet-mcp-anbindung.md](docs/plans/2026-11-07-stabilitaet-mcp-anbindung.md) · Rückmeldung ans MCP-Team: [docs/mcp-rueckmeldung-2026-11-07.md](docs/mcp-rueckmeldung-2026-11-07.md) |

**Betrieb in Kürze** (Stand Paket N, 2026-11-19):

- Start im Container: `python -m boerdi.serve` — Port **8100** öffentlich (Widget, Chat, Agent,
  Sprache, Studio), Port **8101** intern (`/health`, `/ready`, `/metrics`, `/openapi-full.json`).
- Datenbank-Stand: Migration **0023**. Der `migrate`-Dienst hebt bei jedem Deploy
  (`alembic upgrade head && boerdi import-config --werksabgleich`).
- b-api: `B_API_ROUTE` (Route des Routers, Vorgabe leer) und `B_API_KEY_MODE`
  (`auto` Vorgabe, auch ohne gesetzte Variable · `static` · `forward`) —
  [deploy/README.md](deploy/README.md). Hinter dem b-api-Proxy mit `forwardDelegation` empfiehlt
  sich `forward`; Einzelheiten und Admin-Liste in [docs/b-api-betrieb.md](docs/b-api-betrieb.md)
  (Stand Pakete D, K, U, N, 2026-11-19). Welche Art zuletzt galt (Delegation, Schlüssel, direkt),
  zeigt die Betriebsanzeige im Studio und `/api/health` (Studio-Schlüssel); das offene `/health`
  bleibt `{"status":"ok"}`.
- Ohne vorgeschalteten Proxy (Port direkt veröffentlicht, etwa im Testbetrieb mit
  `docker run`) `FORWARDED_ALLOW_IPS=127.0.0.1` setzen — sonst glaubt Uvicorn jedem
  `X-Forwarded-For` ([deploy/README.md](deploy/README.md), „Welche Proxys Uvicorn glaubt“).

**Status:** Umsetzung läuft paketweise (P0–P11) — der aktuelle Stand steht in der
Status-Tabelle oben in der Spec. Das Altsystem bleibt bis zum Cutover (P11) produktiv.
