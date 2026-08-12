# boerdi-chat — Hinweise für Claude

## Was dieses Projekt ist

**Cleaner Neubau des WLO-Chatbots „BadBoerdi"** als Monorepo: FastAPI-Backend (LangGraph-
Orchestrierung, Postgres 17 + pgvector, clusterfähig/stateless), Chat-Widget als Angular-21-
Webkomponente `<boerdi-chat>` (zoneless) und Studio/Webadmin als Angular-SPA — alle drei
Frontend-Teile in EINEM Angular-Workspace mit geteilter `ui`-Lib. Prinzip: möglichst wenig
Eigencode, maximale Nachnutzung etablierter OSS (NUR MIT/Apache-2.0/BSD-artige Lizenzen),
**vollständige Funktions- und Config-Parität** zum Altsystem, generisch konfigurierbar.

**Status: Umsetzung läuft paketweise (P0–P11).** Der aktuelle Stand steht IMMER in der
Status-Tabelle oben in der Spec (dort nach jedem Paket nachführen) — hier bewusst keine
Zahlen/Paket-Nennung, damit dieses Banner nicht driftet.

## Die Spec ist die Quelle der Wahrheit

📘 **[docs/plans/2026-07-10-boerdi-chat-neubau.md](docs/plans/2026-07-10-boerdi-chat-neubau.md)**
— verbindlicher Bauplan: Stack (§2, lizenzverifiziert), 12 bewusste Verbesserungen (§3),
Monorepo-Layout (§4), **Paritäts-Inventare (§5) = Abnahme-Checkliste** (~100 Endpoints,
~45 Env-Vars, 35 Config-Bereiche, Widget-Embed-Vertrag, Studio-Views, 12 Golden-Flows),
Postgres-DDL (§6), Arbeitspakete **P0–P11** mit Task-Listen und Portierungs-Referenzen.
Bei Abweichungen: ZUERST die Spec hier ändern, dann Code. Eiserne Regeln in Spec-§0 gelten
in jedem Paket (Lizenz-Gate, Parität, byte-genaue Verträge `__guide__|`/`__action__|`/
SSE-Events/`bb-<uuid>`, kein modul-globaler State, Domäne framework-frei, ≤300 Z./Datei,
deutsche Inhalte/englischer Code).

## Referenz-Repos (Geschwister-Ordner — NIE von hier aus verändern!)

- **Altsystem (Portierungs-Quelle):** `../badboerdi/` — läuft produktiv weiter, bleibt bis zum
  Cutover eingefroren. Die ~21k Zeilen Tests dort sind die Verhaltens-Spezifikation: beim
  Portieren IMMER zuerst die Alt-Testdatei portieren (Patch-Pfade anpassen), dann das Modul.
  `../badboerdi/backend/badboerdi.db` niemals beschreiben (für den RAG-Import nur eine KOPIE
  lesen). Secrets aus `../badboerdi/backend/.env` niemals ausgeben oder hierher kopieren.
- **MCP-Server (extern, wird NUR konsumiert):** `../wlo-mcp-server-sc/` — eigenes Repo, bleibt
  unverändert; selbst gehostet unter `https://wlo-mcp.87.106.195.152.nip.io/mcp` (Backend
  spricht ihn über `MCP_SERVER_URL` an, Default steht im Code). **23 Tools**, Stand
  2026-07-31 per `tools/list` VOM SERVER geholt. Verträge in Spec-§5.2.
  Die frühere Vercel-Instanz (`../wlo-mcp-server/`, 12 Tools) ist **abgelöst und wird nicht
  mehr verwendet** — sie kannte `get_wlo_content_text` nicht, wodurch M17 ins Leere rief.
  Beim nächsten Server-Wechsel: Liste erneut vom Server holen und
  `seeds/05-knowledge/mcp-servers.yaml` nachziehen — zwei Wächter halten das fest
  (Registry-Deckung gegen TOOL_DEFINITIONS + die zwei Default-URL-Zwillinge).

## Arbeitsweise

- **Paketweise P0→P11** (Spec-Task-Listen). Jedes Paket: Schritt 0 = `/better-coding-workflow`
  laden (UI-Pakete zusätzlich `/better-coding-frontend`); Abschluss = `/better-coding-verify`
  mit Evidenz. Ab P4 läuft nach jedem Paket die Golden-Flow-Suite (`evals/run_golden.py`,
  12 Flows) — Paket-Abnahme steht in der Spec.
- **Commits, Pushes und Deployments macht der Nutzer selbst.** Ebenso startet der Nutzer
  Golden-Referenzläufe gegen ALT und Lasttests; kleine lokale Smokes sind ok.
- Backend: Python 3.12, `uv`, ruff, pytest. Frontend: Angular-Workspace, npm, Vitest,
  Playwright. Dev-Umgebung: `deploy/compose.dev.yml` (Postgres+pgvector, Jaeger).
- Neue Dependency ⇒ Lizenz prüfen (CI-Gate). Verboten (verifiziert): shepherd.js (AGPL),
  intro.js (AGPL), Arize Phoenix (ELv2). Kein Copy-Paste aus Repos mit unklarer Lizenz.
- Secrets nur über Env/pydantic-settings (Spec-§5.4 inkl. ALT-Alias-Namen); nie loggen.

## Coding workflow (better-coding skills)

This project uses the better-coding skill set. Follow this process for all
coding work, and re-invoke the relevant skill before each new package or
coding section — skills unload as the session grows, so do not assume one is
still in context because it loaded earlier.

Pipeline: start (boot, once) → orient (route) → plan (design) → workflow
(implement) → review → verify. Bug: debug → workflow → review → verify.
Whole-repo health/security: audit. UI: pair frontend with workflow.

The skills and what each is for:
- /better-coding-start    — boot the workflow once per session; write/refresh this block
- /better-coding-orient   — route a new/unscoped task; understand unfamiliar code before changing it
- /better-coding-plan     — design & spec a non-trivial feature before code; produce the task list
- /better-coding-workflow — write or change any code (the engineering discipline)
- /better-coding-frontend — build or audit UI: accessibility, UX states, i18n, privacy
- /better-coding-review   — review a diff/PR before merge (read-only, severity-tagged)
- /better-coding-audit    — whole-repo health & security check (12 dimensions)
- /better-coding-debug    — anything broken: bug, failing test, build break (root-cause first)
- /better-coding-verify   — before claiming done/fixed/passing (evidence gate)
- /better-coding-help     — explain the set (for humans)

Re-invocation rule (skills unload — reload before each unit of work):
- Before EACH implementation package or coding section: /better-coding-workflow
  (plus /better-coding-frontend when it touches UI)
- Before reviewing a diff: /better-coding-review
- Before claiming done/fixed/passing: /better-coding-verify
- When something breaks: /better-coding-debug

## Quickstart für eine frische Session

1. Spec lesen: `docs/plans/2026-07-10-boerdi-chat-neubau.md` (mindestens §0–§4 + das
   anstehende Paket komplett).
2. Fortschritt prüfen: Status-Banner oben in der Spec (welches Paket ist ✅/offen?) —
   nach jedem abgeschlossenen Paket dort nachführen.
3. `/better-coding-workflow` laden und mit dem ersten offenen Task des Pakets starten
   (TDD: Alt-Test portieren → rot → Modul portieren → grün).
