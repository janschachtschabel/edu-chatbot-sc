# Paket 18C/18D — volle Umsetzung: Logs ohne Inhalte, Zugakte, `ui`/`debug`, Fehlernummer

Stand 2026-10-29. Grundlage: [Datenbedarf und Entscheide](2026-10-29-paket-18cd-datenbedarf.md)
(§1–§7, D1–D9) und [Paket 18](2026-10-28-paket-18-audit-und-fehlerbehandlung.md) (E2, E3).
Pfade ohne Präfix beziehen sich auf `backend/src/boerdi/`.

## 1 Ziel

Im Normalbetrieb und auf DEBUG ohne Schalter stehen **keine Inhalte, IPs oder Sitzungs-IDs im
Log**, ohne dass die Fehlersuche leidet: Was gefragt und aufgerufen wurde, steht je Zug in der
Datenbank (Zugakte, nur Studio), und die Trace-ID führt aus dem Log und aus der Fehlerblase
dorthin. Öffentlich geht nur noch der **`ui`-Block** hinaus; Diagnose (`debug`) nur an die Anlage
selbst (Studio-Proxy, Studio-Schlüssel).

## 2 Entscheide (Nutzer 2026-10-29)

| | Entscheid |
|---|---|
| Umfang | volle Version (§7 der Grundlage), Empfehlungen D1–D9 |
| Übergang | **harter Schnitt**: öffentlich nur `ui`; Widget und Studio werden im selben PR umgestellt (Backend und Widget gehen immer gemeinsam live). Das Browser-Plugin holt sein Bündel danach neu |
| Studio | Zugakte im Gesprächsverlauf **und** Suche nach Fehlernummer |
| Routing-Ereignis | `persona`, `signals` nur mit Freigabe |
| Lieferung | vier kleine PRs nacheinander |

**Festgelegt im Plan (mit Begründung):**
- **Freigabe** = `turn_auth._interner_zug` (Studio-Proxy oder gültiger `X-Studio-Key`), wird
  öffentlich als `ist_interner_zug`. Dazu der Entwicklungsmodus `BOERDI_ALLOW_OPEN_ADMIN=1` —
  sonst verlöre der Lasttest lokal seine Kennzahlen.
- **Fehlernummer** = die ersten 12 Zeichen der Trace-ID (Zeichenvorrat ist schon auf
  `[A-Za-z0-9._:-]` begrenzt). Das Studio sucht per Präfix (mindestens 8 Zeichen).
- **Strukturierte Ereignisse statt Freitext nur für die neuen Zeilen** (Zugriff, MCP-Aufruf,
  Umschreibung). Die übrigen ~50 Stellen bleiben normale Logaufrufe mit Platzhaltern. Schutz gegen
  Rückfall: AST-Wächter **und** Kanarienvogel-Tests auf allen Zugwegen. Eine typisierte
  Ereignis-API für alle Stellen brächte viel Umbau, aber keinen zusätzlichen Schutz: ein einzelnes
  Wort („Klimawandel“) ist als Feldwert nicht von einer Kennung zu unterscheiden — erkennen kann
  das nur der Laufzeittest. (Abweichung von §7.4 der Grundlage.)
- **`ui` wird an der API-Grenze aus dem Debug-Block abgeleitet**, nicht an den ~40 Stellen, die
  heute `debug` füllen. Eine Funktion, drei Ausgänge (Antwort, Strom-`result`, Verlauf).

## 3 Was daran hängt (geprüft am Code)

| Abnehmer | Liest heute | Danach | Abgesichert durch |
|---|---|---|---|
| Widget: Wiederherstellung nach Neuladen | `debug._query_metas`, `_web_links`, `_type_focus`, `_dokumente`, `_topic_page_view`, `_prepared_write` (Verlaufsabruf) | dieselben Daten aus `ui` | PR 4: Umstellung + Unit-Tests je Abnehmer |
| Widget: Tour, Begrüßung, Gruppierung | `debug.pattern` (live und Verlauf) | `ui.pattern` | dito |
| Widget: Routing-Ereignis (Opt-in `emit-routing-debug`) | `pattern`, `intent`, `state`, `persona`, `tools_called`, `phase3_modulations`, `signals` | aus `ui`; `persona`/`signals` nur, wenn `debug` da ist | dito |
| Widget: Debug-Panel (Opt-in `show-debug-button`) | ganzer Block | `debug`, wenn vorhanden; sonst `ui` + Hinweis „Diagnose nur im Studio“ | dito, Kontrast-E2E bleibt |
| Studio: Chat-Probe, Agent-Spur, Gesprächsverlauf | `/studio/api/chat`, `/studio/api/sessions/{id}/messages` — **dieselbe öffentliche Route über den Proxy** | voller `debug` (Proxy = Freigabe) | Freigabe je Anfrage, nicht je Route; Test mit Proxy-Kennung |
| Evaluation (Runner) | `debug` über `EVAL_CHAT_URL`, Schlüssel nur an Loopback | unverändert voll; bei fehlendem `debug` eine Warnung | Test + Warnung |
| Golden-Läufe (`evals/run_golden.py`) | `debug.pattern`, `tools_called`, `trace` | Schlüssel aus `STUDIO_API_KEY` an eigene Hosts, sonst Warnung | Test + Anleitung |
| Lasttest | im Prozess (ASGI), mit Studio-Schlüssel | unverändert; im Entwicklungsmodus ohne Schlüssel auch frei | Test |
| `/api/agent` | kein Debug-Block | unverändert | – |
| Strom: `connected` | nur `history`/`after_id` | unverändert | – |
| Auswertung: Fehlerantworten erkennen | Satzanfang von `error.internal` bis `{` | Fehlernummer steht am Satzende | Test |
| Browser-Plugin | eigene Bündel-Kopie (`fetch-widget.mjs`) | nach dem Deploy neu holen | Änderungsnotiz |
| Host-Seiten mit `persona`/`signals` | Routing-Ereignis | leer ohne Freigabe | Änderungsnotiz |
| OpenAPI (`openapi-v1.json` eingefroren) | `ChatResponse.debug` immer | `ui` neu, `debug` nullable | neu erzeugt, `bewusste-vertragszusaetze.md` |

**Technische Randbedingungen:**
- LangGraph-Knoten laufen als eigene Tasks: Den Sammler der Zugakte bindet `graph/build.py`
  einmal je Zug als **geteiltes Objekt** (wie `reset_query_metas`), nie `ContextVar.set` in einem
  Knoten (Paket 10).
- Der Strom-Zug läuft in eigener Task mit eigener DB-Sitzung (Paket 7): Trace-ID und Sammler
  stehen im Kontext dieser Task, gebunden vor dem Zug.
- `save_message` (13 Aufrufe in 11 Dateien) und das Qualitäts- und Sicherheitsprotokoll lesen
  Trace-ID und Zugakte **zentral** aus dem Kontext — kein Aufrufer ändert sich.
- Die Metrik-Middleware kennt Pfad-Vorlage, Status und Dauer; die Zugriffszeile hängt dort.
- LiteLLM bringt einen eigenen stderr-Handler mit; er wird entfernt, sonst laufen Zeilen am JSON
  und an jeder Deckelung vorbei.
- Große Dateien wachsen nicht weiter: Neue Zuständigkeiten bekommen eigene Module (§4).

## 4 Architektur

**Neue Module**

| Datei | Zuständig für |
|---|---|
| `obs/log_inhalt.py` | `inhalt(text) -> "‹N Zeichen›"`, `kennung(session_id) -> 8 Hex`, `filterwerte(args) -> dict` (Filter und IDs mit Wert, Freitext nur als Länge), `ereignis(logger, name, **felder)` |
| `obs/drittlogger.py` | `drittlogger_einstellen(log_content: bool)`: LiteLLM*, `openai`, `mcp`, `httpcore`, `h11`, `uvicorn.access` auf WARNING, `slowapi` auf ERROR; LiteLLM-Handler entfernen. Mit `LOG_CONTENT` folgen alle der Wurzel |
| `obs/zugriffslog.py` | `zugriff(methode, route, status, dauer_ms)`: eine Zeile je Anfrage ohne IP und Query; `/widget/`, `/studio/` (Dateien) nur auf DEBUG |
| `services/zugakte.py` | Sammler je Zug: `binde_zugakte()`, `aktuelle_zugakte()`, `Zugakte.werkzeug(...)`, `.umschreibung(...)`, `.schnellweg(...)`, `.als_dict()`; Deckel und Schwärzung |
| `api/schemas_ui.py` | `UiInfo` (öffentlicher Vertrag) |
| `api/publikum.py` | `ui_aus_debug(DebugInfo)`, `ui_aus_gespeichert(dict)`, `antwort_fuer(resp, intern)`, `verlauf_fuer(nachrichten, intern)` |
| `alembic/versions/0016_trace_id.py` | `trace_id TEXT NULL` an `chat_messages`, `quality_logs`, `safety_logs`; Index `text_pattern_ops` an `chat_messages.trace_id` |

**Geänderte Dateien (Kern):** `settings.py` (`log_content`), `main.py`, `serve.py`
(`access_log=False`), `obs/metrics.py` (ruft `zugriff`), `obs/otel.py` (Verlaufspfade
ausgenommen), `obs/trace_id.py` (`fehlernummer()`), `db/session.py` (`hide_parameters`),
`db/models.py`, `services/db_sessions.py`, `services/turn_quality.py`, `obs/quality_events.py`,
`graph/build.py`, `services/mcp/client.py`, `services/turn_links.py`, `api/turn_auth.py`,
`api/schemas.py`, `api/chat.py`, `api/sse.py`, `api/sessions.py`, `i18n/bot_text.py`,
`graph/nodes/respond.py`, `services/tool_loop.py`, `services/canvas_fast_path.py`,
`services/canvas_service.py`, `services/eval/runner.py`, `evals/run_golden.py` und die ~50
Logstellen (§1 der Grundlage).

**`UiInfo`** (Feldnamen ohne Unterstrich, alle optional, Vorgabe leer):
`pattern`, `intent`, `state`, `tools_called`, `modulations` (aus `phase3_modulations`), und nur im
Verlauf: `query_metas`, `web_links`, `type_focus`, `dokumente`, `topic_page_view`,
`prepared_write`. Diagnose-Felder kommen hier nie hinein; ein Vertragstest hält die Schlüssel fest.

**Zugakte** (im gespeicherten Debug-Block unter `_zugakte`, nur Studio; Stand nach Phase 1,
Abweichungen im Log):
```
{"werkzeuge": [{"name", "argumente_eingang", "argumente_gesendet",
                "status": "ok|tool|transport|timeout|auth", "aus_cache": bool, "dauer_ms",
                "zeichen": int|None, "fehler": str|None}],
 "werkzeuge_ausgelassen": int,        # nur bei mehr als 50 Aufrufen
 "umschreibungen": [{"art": "typ_fokus|waechter", "original", "ersatz", "grund"}],
 "schnellwege": [{"art": "canvas|lernpfad", "thema"}]}
```
Leere Teile fehlen; eine leere Akte wird nicht gespeichert. Deckel: 1 000 Zeichen je Wert,
20 Einträge je Liste (Rest als `‹N weitere›`), 50 Werkzeugaufrufe je Zug; `confirmToken` nie,
`fileBase64` und `content` nur als Länge (wie `_args_for_log`), was JSONB nicht nimmt als Text.
`get_messages` gibt `_zugakte` nur mit `zugakte=True` heraus (sonst `debug - '_zugakte'` in SQL);
der öffentliche Verlauf setzt das nur bei `_interner_zug`.

**Datenfluss:** Anfrage → `TraceIdMiddleware` (Trace-ID) → `run_turn` bindet Sammler →
MCP-Client und Umschreibungen tragen ein → `save_message` legt `trace_id` und `_zugakte` ab →
API-Grenze baut `ui`, `debug` nur bei `ist_interner_zug` → Log enthält Ereignisse mit Kennungen.

## 5 Nicht im Umfang

- Inhalte in der Datenbank (Verlauf 30 Tage, Qualitätsprotokoll, IP-Spalte im
  Sicherheitsprotokoll): eigene Aufbewahrung aus Paket 8, unverändert.
- B3 `ParentSpanId`/`Sampled` (Rückfrage an Team 6, eigener Punkt).
- 18E (Exceptions) und 18F (Betrieb, Rate-Limit).

## 6 Aufgaben

Jede Phase ist ein PR mit thematischen Commits und eigener Änderungsnotiz. Schritt 0 jeder
Phase: `/better-coding-workflow` laden (Phase 4 zusätzlich `/better-coding-frontend`). Jede
Aufgabe: zuerst der Test, der rot ist, dann die Umsetzung.

### Phase 1 — Fundament: Trace-ID und Zugakte (PR 1, Backend)

Schritt 0: `/better-coding-workflow`

**1.1 Migration 0016.** `trace_id` an drei Tabellen, Index. Test `test_trace_id_pg.py`: Spalten
und Index da; Abwärtsmigration entfernt sie. Rücknahme: `alembic downgrade 0015`.

**1.2 Trace-ID beim Speichern.** `save_message`, `log_turn_quality`, `log_safety_event` lesen
`trace_id.aktuelle()` (leer → `NULL`). Tests: Zug über `/api/chat` mit `x-client-trace-id: abc…`
→ Nachricht, Qualitätszeile und Sicherheitsereignis tragen sie; Hintergrundlauf ohne Anfrage →
`NULL`.

**1.3 Sammler.** `services/zugakte.py` mit Deckeln und Schwärzung. Unit-Tests: Deckel greifen,
`confirmToken` fehlt, `fileBase64` nur als Länge, `als_dict()` ohne Sammler leer.

**1.4 Bindung je Zug.** `graph/build.py` bindet den Sammler neben `reset_query_metas()`.
Test: Ein Eintrag aus einem Knoten (eigene Task) kommt in `persist` an — für Muster- und
Agent-Weg.

**1.5 MCP-Aufrufe eintragen.** In `call_mcp_tool_status` (einzige Engstelle): Argumente wie
gesendet vom Modell, nach Prüfung und Auflösung, Status, Cache, Dauer, Trefferzahl. Das
Auffächern trägt jeden Teilaufruf ein. Tests: Erfolg, `-32602`-Ablehnung, Zeitüberschreitung,
Cache-Treffer, Liste mit zwei Werten.

**1.6 Umschreibungen und Schnellwege eintragen.** `turn_links` (Typ-Fokus, Wächter),
Schnellwege Canvas/Lernpfad/Themenseite. Tests je Art.

**1.7 Zugakte speichern.** `save_message` legt bei `role="assistant"` `_zugakte` in `debug` ab —
auch bei früh endenden Zügen (`pruefung_fehlt`, Preflight) und in der Fehlerblase. Tests für alle
drei Wege, Strom-Zug eingeschlossen.

**1.8 Suche nach Fehlernummer (API).** `GET /api/sessions/zug/{nummer}` am Studio-Router: Präfix
≥ 8 Zeichen aus `[A-Za-z0-9._:-]`, höchstens 20 Treffer (`session_id`, `message_id`,
`created_at`). Tests: ohne Anmeldung 401, zu kurz 422, Treffer per Präfix. (`trace_id` in der
Verlaufsantwort folgt in 4.6 — erst dort gibt es die Freigabe je Publikum.)

**1.9 Doku PR 1.** Änderungsnotiz (Migration 0016), Plan-Log.

### Phase 2 — Logs ohne Inhalte (PR 2, Backend; setzt PR 1 voraus)

Schritt 0: `/better-coding-workflow`

**2.1 Kanarienvogel-Test zuerst (rot).** `test_kanarienvogel_logs.py`: ein Zug je Weg (Muster,
Agent, Direktaktion, Canvas-Schnellweg, Fehlerblase), LLM und MCP als Attrappe; Nachricht,
Modellantwort und Werkzeugergebnis tragen das Markierwort. Alle Logeinträge (Wurzel, DEBUG,
`LOG_CONTENT` aus) dürfen es nicht enthalten. Heute rot — der Test treibt die Phase.

**2.2 `LOG_CONTENT`.** Einstellung (Vorgabe aus), `.env.example`, Compose, Helm (die Wächter
verlangen alle drei), Startwarnung bei an.

**2.3 Fremd-Logger.** `obs/drittlogger.py`, aufgerufen in `_configure_logging`. Tests: Stufen je
Logger mit und ohne Schalter; LiteLLM-Logger ohne eigene Handler, auch nach einem
nachgebildeten `acompletion`.

**2.4 Zugriffszeile.** `serve.py` `access_log=False`; `MetrikMiddleware` ruft `zugriff`. Tests:
Vorlage statt Pfad (Sitzungs-ID fehlt), keine IP, kein Query, Dateien auf DEBUG.

**2.5 Helfer.** `obs/log_inhalt.py` mit Tests (`inhalt`, `kennung`, `filterwerte`, `ereignis`).

**2.6 MCP-Logzeilen.** `mcp/client.py` und `prefetch.py`: Werkzeug, Filterwerte, Länge des
Freitexts, Status, Dauer, Trefferzahl; Werte der kuratierenden Werkzeuge nur mit `LOG_CONTENT`.

**2.7 Übrige Stellen umstellen**, gruppiert nach Datei (je Gruppe ein Commit): `turn_links`,
`widget_postprocess`, `canvas_fast_path`/`lp_fast_path`/`lp_intent`, `topic_pages`/
`card_pipeline`/`page_duplicate`/`page_context`, `merge`, `turn_persist` (Schnellantworten),
`agent_skill_directory`, `arg_resolvers`, Sitzungs-IDs (`write_approval`, `usage_store`,
`sitzungssperre`, `content_text_action`).

**2.8 Fehlermeldungen.** `hide_parameters=True`; Pydantic-Fehler über `_fehlerorte`. Test: ein
DB-Fehler mit Nachrichtentext im Parameter erscheint ohne ihn.

**2.9 OpenTelemetry.** `excluded_urls` für `/api/sessions/` und `/studio/api/sessions/`. Test
auf die Konfiguration.

**2.10 AST-Wächter.** `test_log_ohne_inhalt.py`: verbotene Namen in Logaufrufen ab INFO
(`req.message`, `response_text`, `_new_response`, `_new_text`, `_dropped_qrs`, `_narrow_qrs`,
`session_id`, `spec_tool_args`, `query`, `_fallback_term`, `_c_topic`, `topic`, `thema` …),
erlaubt nur in `inhalt()`/`kennung()`/`len()`.

**2.11 Wächter grün, Doku.** Kanarienvogel und Wächter grün; `deploy/README` (Logs & Traces,
`LOG_CONTENT`), Übergabe §7, Änderungsnotiz, Plan-Log.

### Phase 3 — Antworten: `ui` dazu, Fehlernummer (PR 3, Backend, additiv)

Schritt 0: `/better-coding-workflow`

**3.1 `UiInfo` und Ableitung.** `api/schemas_ui.py`, `api/publikum.py`. Tests: Ableitung aus
live-`DebugInfo` und aus gespeichertem Dict (alte und neue Nachrichten), Vertragstest der
Schlüssel.

**3.2 `ui` ausliefern** in Antwort, Strom-`result` und Verlauf — **zusätzlich**, `debug` bleibt
in dieser Phase unverändert (main bleibt mit dem alten Widget lauffähig). Tests für alle drei
Ausgänge.

**3.3 `ist_interner_zug`.** Aus `turn_auth._interner_zug`, plus Entwicklungsmodus. Tests:
Proxy, Schlüssel, falscher Schlüssel, offener Entwicklungsmodus.

**3.4 Fehlernummer.** `trace_id.fehlernummer()`; `error.internal`, `material.genFailed` und neu
`error.answerFailed` (statt des hart deutschen Textes in `respond.py`) mit `{nummer}` am
Satzende, de/en; Canvas ohne Anbietertext. Tests: keine Ausnahme-Klasse in der Blase, Nummer da,
`fallback_texts()` erkennt die neuen Texte. Aus dem Review von Phase 1: eine Client-Trace-ID unter
8 Zeichen ist mit der Suche (≥ 8) nicht zu finden, und ein Client, der eine ID über mehrere Züge
wiederverwendet, lässt die Suche diese Züge zu einem Treffer zusammenfassen — in 3.4 entscheiden
(z. B. eigene ID je Zug neben der Client-ID).

**3.5 Auswertung und Golden.** Runner warnt, wenn `debug` fehlt; `run_golden` schickt
`X-Studio-Key` aus `STUDIO_API_KEY` an eigene Hosts und warnt sonst. Tests.

**3.6 OpenAPI und Doku.** Specs neu erzeugen, `bewusste-vertragszusaetze.md` (`ui` neu),
Änderungsnotiz, Plan-Log.

### Phase 4 — Oberflächen und Schnitt (PR 4, Widget, Studio, Backend)

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend`

**4.1 Widget-Typen.** `ChatResponse.ui`, `ChatMessage.ui`; `addBotMessage` nimmt `ui` mit
(Aufrufer: `send-message`, `collection-actions` ×2, `context-greeting`, `tour`,
`history-restore`).

**4.2 Wiederherstellung aus `ui`.** `history-transport.ts`, `history-restore.ts`,
`antwort-aus-verlauf.ts`, `result-grouping.ts`. Specs je Datei auf `ui` umstellen (zuerst rot).

**4.3 Routing-Ereignis.** `host-events.ts` aus `ui`; `persona`/`signals` nur aus `debug`. Spec:
ohne `debug` leer.

**4.4 Debug-Panel.** Mit `debug` wie bisher; ohne: `ui`-Zusammenfassung und Hinweis „Diagnose nur
im Studio“ (de/en). Spec; Kontrast-E2E unverändert grün.

**4.5 Schnitt im Backend.** `antwort_fuer`/`verlauf_fuer`: ohne Freigabe `debug = null`. Tests:
anonym nur `ui`, über Proxy und Schlüssel voller `debug`; die neun Backend-Testdateien, die
`debug` aus Antworten lesen, schicken die Freigabe mit oder lesen `ui`.

**4.6 Studio: Zugakte im Verlauf.** `verlauf_fuer` gibt der Anlage `trace_id` je Nachricht mit.
`session-transcript`: Fehlernummer je Antwort, Abschnitt
„Werkzeugaufrufe“ (Name, Quelle, Status, Dauer, Treffer; Argumente aufklappbar) und
„Umschreibungen“ (Original/Ersatz). Leere Akte: kein Abschnitt. Specs; Tastatur und Kontrast
(`check:contrast`).

**4.7 Studio: Suche nach Fehlernummer.** Suchfeld auf der Gesprächsseite mit Beschriftung,
Lade-, Leer- und Fehlerzustand; ein Treffer öffnet den Verlauf an der Nachricht, mehrere als
Liste. Specs, i18n (`sessions.ts`).

**4.8 E2E und Bündel.** E2E-Fixtures um `ui`; Playwright grün; Widget-Build im Budget;
`grep -c` im Bündel auf einen `ui`-Schlüssel.

**4.9 Doku.** Steckbrief (offene Punkte 11 → erledigt), Übergabe §6/§7, Audit-Rückmeldung (18C/D
erledigt), Änderungsnotiz mit **Deploy-Schritten**: Image mit Widget, Migration 0016, Plugin-Bündel
neu holen (`node scripts/fetch-widget.mjs <backend>`), Hinweis an Host-Seiten zu
`persona`/`signals`.

## 7 Abnahme

| Phase | Nachweis |
|---|---|
| 1 | Migration auf/ab; Zug über alle Wege → Trace-ID in Nachricht, Qualität, Sicherheit; Zugakte mit Werkzeugaufrufen (auch gescheiterten) im gespeicherten Zug; Suche per Präfix |
| 2 | Kanarienvogel grün auf allen Wegen, auch auf DEBUG ohne Schalter; mit `LOG_CONTENT` erscheint der Inhalt auf DEBUG; Fremd-Logger-Test; keine IP und kein roher Pfad im Log |
| 3 | `ui` in allen drei Ausgängen; Fehlertexte ohne Klasse, mit Nummer; Auswertung erkennt sie; Specs neu |
| 4 | anonym kein `debug`, Anlage voller `debug`; Widget-Specs, Studio-Specs, E2E grün; Studio zeigt Zugakte und findet per Fehlernummer |
| alle | volle Backend-Suite, Frontend-Tests (ui, widget, studio), Lint, `check:contrast`, Widget-Budget, OpenAPI-Gate, Lizenz- und Audit-Gates |

Live (nach Deploy, vom Nutzer): ein Zug im Widget anonym (kein `debug` in der Netzwerkansicht),
derselbe im Studio (voller Block, Zugakte), eine provozierte Fehlerblase → Nummer im Studio finden.

## 8 Regressionsrisiken

| # | Risiko | Gegenmittel |
|---|---|---|
| R1 | Widget verliert Wiederherstellung, Tour-Erkennung oder Gruppierung | Umstellung und Schnitt im selben PR; Spec je Abnehmer zuerst rot |
| R2 | Studio verliert Diagnose (Verlauf läuft über die öffentliche Route) | Freigabe je Anfrage über den Proxy; Test mit Proxy-Kennung |
| R3 | Auswertung oder Golden zählen still nichts (kein Schlüssel) | Warnung bei fehlendem `debug`; Golden schickt den Schlüssel an eigene Hosts |
| R4 | Lasttest lokal ohne Kennzahlen | Entwicklungsmodus zählt als Freigabe |
| R5 | Plugin-Kopie alt | Deploy-Schritt in der Änderungsnotiz |
| R6 | Einträge aus Knoten gehen verloren (eigene Tasks) | Sammler als geteiltes Objekt in `build.py`; Test |
| R7 | Strom-Zug ohne Trace-ID oder Akte | Bindung in der Strom-Task; Test über `/api/chat/stream` |
| R8 | Datenbank wächst | Deckel je Wert und Zug; Größe im Test gemessen; Aufbewahrung 30 Tage |
| R9 | Migration im Betrieb | nur neue, nullable Spalten und ein Index; Abwärtsweg getestet |
| R10 | LiteLLM hängt Handler neu an oder benennt Logger um | Test nach nachgebildetem Aufruf; Liste an einer Stelle |
| R11 | Diagnose fehlt zwischen PR 2 und Zugakte | Reihenfolge: PR 1 vor PR 2 |
| R12 | Fehlernummer spiegelt Client-Eingabe | Zeichenvorrat schon begrenzt, 12 Zeichen, als Text; Test mit Sonderzeichen-Kopf |
| R13 | Eingefrorener OpenAPI-Vertrag | neu erzeugen, Zusatz dokumentieren, Gate |
| R14 | Host-Seiten nutzen `persona`/`signals` | Änderungsnotiz |
| R15 | Bestehende Tests lesen `debug` aus Antworten | in 4.5 umstellen |
| R16 | Zugriffszeile erzeugt viel Volumen | Dateien auf DEBUG; Umfang wie bisher Uvicorns Zeile |
| R17 | Zugakte speichert Suchtexte in der DB | innerhalb der bestehenden 30 Tage, nur Studio; in Übergabe/Datenschutz vermerkt |

## 9 Aufwand

PR 1 etwa 1 Tag · PR 2 etwa 1 Tag · PR 3 etwa ½–1 Tag · PR 4 etwa 1–1½ Tage.

## 10 Log

- 2026-10-29: Plan nach Bestandsaufnahme (Konsumenten, Log-Kanäle per Laufzeitprobe, Speicherwege,
  Studio-Routen, Plugin) und Nutzer-Entscheiden.
- 2026-10-29: **Phase 1 gebaut** (1.1–1.9, nur Staging). Abweichungen vom Plan, jede am Code
  begründet:
  - **`argumente_eingang` statt `argumente_modell`:** an der Engstelle kommen Argumente auch aus
    Vorabruf und Direktaktion, nicht nur vom Modell.
  - **Kein Feld `quelle`:** `call_mcp_tool_status` kennt seinen Aufrufer nicht; ein Parameter
    durch alle Aufrufer brächte Umbau ohne Diagnosegewinn (Werkzeugname und Reihenfolge zeigen
    den Weg). **`zeichen` statt `treffer`:** die Trefferzahl hieße, jedes Werkzeugformat nur für
    die Diagnose zu parsen; die Länge der Antwort genügt, um „leer“ von „voll“ zu trennen.
  - **Schnellwege nur `canvas` und `lernpfad`:** die Themenseite ist kein Schnellweg, sondern ein
    gewöhnlicher Werkzeugweg — ihre Aufrufe stehen unter `werkzeuge`.
  - **Zusätzlich `werkzeuge_ausgelassen`** (Zähler über dem Deckel) und **die Auffächerung zählt
    nur ihre Teilaufrufe**, nicht den Sammelaufruf (der lief nie zum Server).
  - **`finalize_message` legt die Akte ebenfalls ab:** es ersetzt den Diagnoseteil ganz und lief
    nach dem ersten Speichern; ohne das ginge die Akte im Normalweg verloren (und Einträge des
    M16-Auflösers dazu).
  - **Öffentlicher Verlauf ohne `_zugakte` schon in PR 1** (`GET /api/sessions/{id}/messages`,
    außer `_interner_zug`): bis PR 4 liefert der Verlauf den ganzen Debug-Block ohne Anmeldung —
    sonst wären Werkzeug-Argumente und umgeschriebene Entwürfe zwischen PR 1 und PR 4 öffentlich.
    Seit dem Review nimmt schon `get_messages` sie heraus, außer mit `zugakte=True`.
  - **Suche liefert auch `trace_id`** und **einen Treffer je Zug** (seine letzte Nachricht):
    Frage und Antwort tragen dieselbe ID; zwei Treffer je Zug zwängen das Studio immer in die
    Liste. `_` gilt als Zeichen (`autoescape`); der Index trägt die Suche (geprüft mit `EXPLAIN`).
  - **1.2/1.4 ohne eigenen Endpunkttest je Weg:** die Ablage liest den Kontext zentral; geprüft
    sind die Ablage (pg) und, dass Trace-ID und Akte die Fehlerblase in `/api/chat` und im Strom
    erreichen. Der Agent-Weg im Chat läuft durch denselben Graphen; `/api/agent` speichert nichts.
- 2026-10-29: **Review Phase 1** (frischer Prüfer, nur lesend) — sechs Befunde, alle am Code
  geprüft:
  1. OpenAPI-Vertrag rot (neue Route) — schon behoben: Routen-Inventar, Vertrag neu erzeugt (nur
     dieser Pfad), Eintrag in `bewusste-vertragszusaetze.md`.
  2. **Nachtrag fehlte**, wenn nach dem ersten Speichern nur die Akte wuchs (M16-Auflöser
     scheitert, sonst ändert sich nichts) → `turn_persist` zieht auch bei gewachsener Akte nach
     (`zugakte_umfang`). Test.
  3. **Offenes Tor mit gesetztem Schlüssel:** jeder kam durch den Proxy und galt als intern →
     `_interner_zug` wertet den Proxy dann nicht als Freigabe (wie `_injectable_key`); reiner
     Entwicklungsmodus ohne Schlüssel bleibt offen. Tests für alle fünf Fälle
     (`test_zugakte_verlauf.py`, mit echtem Proxy-Weg und Anmelde-Cookie).
  4. **Listen ungedeckelt** (`excludeNodeIds` bis 200 Kennungen) → 20 Einträge je Liste. Gemessen:
     typischer Zug (3 Aufrufe) 6 KB, schwerer Zug (10 Suchen mit 200 Ausschlüssen und langem
     Fehlertext) 31 KB (Test < 32 KB), Grenzfall (50 Aufrufe, alle Werte am Deckel) 251 KB.
     `setup` lud die Akten der letzten 20 Nachrichten je Zug mit → `get_messages` nimmt sie in
     SQL heraus, außer mit `zugakte=True`.
  5. Testlücken geschlossen: `argumente_gesendet` nach Auflösung (`outputFormat`),
     Fremdwerkzeug, Verlauf über den echten Proxy.
  6. Kleinigkeiten: Nutzlast-Schlüssel jeden Typs nur als Länge; was JSONB nicht nimmt (Menge,
     UUID, `inf`) als Text, sonst scheiterte das Speichern der Antwort. **Bewusst gelassen:**
     `wlo_auth_status` läuft am Engpass vorbei (Anmeldeprobe, kein Werkzeugaufruf eines Zugs);
     `/zug/{nummer}` verdeckt den Verlauf einer Sitzung namens `zug` (echte Kennungen `bb-…`);
     bei aufgefächerten Listen steht je Teilaufruf der Einzelwert, nicht die Liste des Modells;
     Fehlernummer und Client-Trace-IDs → Hinweis bei 3.4.
- 2026-10-29: **Phase 2 gebaut** (2.1–2.11, nur Staging; PR erst nach Merge von #29). Entscheide und
  Abweichungen, am Code begründet:
  - **`LOG_CONTENT` öffnet nur Inhalts-Logger** (LiteLLM, OpenAI, MCP folgen der Wurzel) und die
    Werte-Zeile der Werkzeugargumente auf DEBUG. Rauschen und Adressen bleiben immer gedeckelt
    (`httpx`, `httpcore`, `h11`, `uvicorn.access` WARNING, `slowapi` ERROR) — der Schalter gilt
    Inhalten, nicht IPs. **SQLAlchemy** zusätzlich auf WARNING (der Kanarienvogel fand auf DEBUG
    Ergebniszeilen samt Sitzungs-ID und Texten; SQLAlchemy deckelt sich zwar beim Import selbst,
    die Liste steht nun an einer Stelle).
  - **`inhalt()` zeigt nur die Länge, auch mit Schalter** — Inhalte stehen in der Zugakte; im Log
    nur die Werkzeugargumente (DEBUG) und die Fremd-Logger.
  - **Keine eigene Drosselungszeile:** die Zugriffszeile zeigt `status=429` mit Route; slowapi
    (IP als Schlüssel) auf ERROR. `/health` steht wie Dateien auf DEBUG (Proben).
  - **MCP:** Argumentzeile mit `filterwerte` (Erlaubnisliste der Filter- und Kennungsschlüssel;
    Unbekanntes nur als Länge); „returned … chars“ ersetzt durch das Ereignis `mcp_aufruf` je
    Aufruf (auch Fehler, Cache, Fremdwerkzeug). Fehlertexte des Servers (`-32602` wiederholt die
    Eingabe) und abgelehnte Schreibvorgänge nur als Länge — der Text steht in der Zugakte.
    `_args_for_log(nur_laengen)` entfällt. **Zwei Tests bewusst geändert:** Suchtext und Titel
    sind auf INFO nicht mehr lesbar (Filter weiterhin).
  - `fehlerorte` ist jetzt Helfer in `obs/log_inhalt` (vorher privat in `tool_args`), genutzt
    auch in `config_elements`. `domain/lp_intent` nimmt `len()` statt des Helfers: `domain`
    importiert nichts aus `obs`.
  - **Kanarienvogel** (Gerüst von einem eigenen Agenten): alle fünf Wege über `POST /api/chat`,
    Markierwort auch in der Sitzungs-ID; Wurzel auf DEBUG, alle anderen Logger erben, Fremd-Logger
    wie im Betrieb. Funde über den AST-Wächter hinaus: Begründung des Klassifikators
    (`prefetch`), Such-Adresse mit `q=` (`turn_links`), Wikipedia-Suchtext, Begründung der
    Kartenauswahl (`tool_loop`, vom Wächter gefunden).
  - **AST-Wächter** mit Ausnahme-Kommentar `# log-ok: <Grund>` (Fehlertext einer Ausnahme,
    Konfigurationswert, Repo-Dokument, öffentlicher Titel).
- 2026-10-29: **Review Phase 2** (frischer Prüfer, nur lesend) — Kern: der AST-Wächter verglich
  ganze Ausdrücke, Aliasnamen (`_user_msg`, `extra_args`, `query_tokens`, `_m16_thema`,
  `_prev_slots_pre`, `signature`) und Ketten (`ctx.req.message`) liefen durch, und der
  Kanarienvogel durchläuft diese Zweige nicht. Behoben:
  - **Wächter neu:** letzter Namensteil gegen Wortstämme, Inhaltsschlüssel in `.get()`/`[]`,
    `ereignis(...)` mitgeprüft, Stufe per Bedingung als INFO, **DEBUG außerhalb
    `if … log_content` ebenfalls**. 28 echte Funde: Inline-Ergänzung (Nachricht), Off-Topic-Filter
    (Wörter der Nachricht), spekulative Extras (`query`), M16 (Thema), `merge` (Vorbelegung samt
    Werten, Platzhalter-Thema), Kartenauswahl (Suchwörter), Begrüßung (Signatur mit Suchbegriff
    bzw. Adresse), Seitenkontext (Titel der Seite), Parser und Transport (Fehlertext des Servers
    mit der Eingabe), Fremdwerkzeug, Skill-Suche; öffentliche Titel, Zahlen und Werkzeugnamen
    mit `# log-ok`. Die Strom-Bezeichnung trug `session=<Sitzungs-ID>` → Kurzkennung.
  - **Ausnahmetexte:** `classify` loggte `InstructorRetryException` (jeder Versuch samt
    `input_value` und die letzte Antwort mit dem Thema) → Zahl der Versuche und Fehlerorte.
    Die Formatierer schwärzen Postgres-`DETAIL:` (Fremdschlüssel: Sitzungs-ID; NOT NULL/CHECK:
    die Zeile — `hide_parameters` erreicht das nicht) und Pydantic-`input_value=` in Meldung und
    Traceback; JSON mit `default=str`.
  - `instructor` zu den Inhalts-Loggern (loggt auf DEBUG Anfrage und Antwort des Klassifikators);
    OpenTelemetry nimmt auch `/api/usage/session/` aus; Filter-Erlaubnisliste um `subject`,
    `vocabulary`, `parentId`, `suggestionId`, `field`, `method`, `decision`, `status`,
    `contentFormat`, `licenseKey`, `licenseVersion`, `contentType` ergänzt.
  - **Bewusst gelassen:** `arg_resolvers` loggt Fach- und Sammlungsnamen, die das Modell statt
    einer Kennung schickte (Filterwerte, `# log-ok`); der Titel eines verworfenen
    Wikipedia-Artikels (öffentlich); der Kanarienvogel deckt nicht jeden Zweig ab — dafür der
    schärfere Wächter.
