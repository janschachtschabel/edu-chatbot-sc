# Paket 17 — B-API-Router, Schlüssel durchreichen, Clusterfähigkeit, Übergabe an den Betrieb

Stand: Entwurf 2026-10-20, wartet auf Freigabe. Grundlage: Nutzer-Vorgaben 2026-10-20 (Leitfaden „Übergabe an Team 6“, B-API-Routing-Doku, B-API-Doku „Authentifizierung über den durchgereichten Authorization-Header“) und drei Prüfungen am Staging-Baum (nur lesend, 2026-10-20).

## 1 Ziel

1. **B-API-Router:** Der Chatbot akzeptiert einen Routennamen der B-API (`/api/v1/llm/router/…`). Vorgabe bleibt **ohne Route**, mit `gpt-6-luna` über den bisherigen Weg.
2. **Schlüssel durchreichen:** Kommt die Anfrage über den B-API-Proxy (`/api/v1/proxy/badboerdichat/…`) mit `Authorization: Bearer <key>`, laufen alle LLM-Aufrufe dieses Zugs mit genau diesem Kopf. Sonst gilt wie heute `B_API_KEY`.
3. **Clusterfähigkeit:** N Repliken ohne Sticky Sessions, ohne Fehlverhalten.
4. **Übergabe an T6:** die Checkliste des Leitfadens vollständig beantworten.

## 2 Ausgangslage (drei Prüfungen, 2026-10-20)

### 2.1 B-API-Anbindung

| Befund | Beleg |
|---|---|
| Anbieter nur `openai`, `b-api-openai`, `b-api-academiccloud`. `route()` hängt `/openai` oder `/academiccloud` an; einen Router-Weg gibt es nicht. | `settings.py:30`, `services/llm.py:138-162` |
| Parameterregeln über den Präfix des Modellnamens (`_GROUPS`). Ein Routenname wie `chat-standard` fiele auf `_CLASSIC`: `temperature` und `max_tokens` gingen an eine GPT-5-Route, `responses_api` entfiele. | `services/llm_models.py:96-146`, `llm.py:117-130` |
| Der Schlüssel geht doppelt hinaus: als Bearer (SDK) und als `X-API-KEY`. Moderation und Sprache bauen die Köpfe selbst. | `llm.py:159-161`, `safety/moderation.py:79-83`, `services/speech_proxy.py:138-146` |
| Cache-Umgehung auf `b-api-openai` über ein zufälliges `user` je Anfrage. `ignore-caching` wird nicht genutzt. | `llm.py:182-195` |
| Kosten werden nach `resp.model` gebucht, das passt auch für eine Route. Die Eval-Kostenschätzung rechnet aber mit dem eingestellten Namen. | `obs/usage.py:68,82`, `eval/cost.py:143`, `eval/run_conditions.py:75` |
| Vorbild für einen Wert je Anfrage: der WLO-Zugangsblock (`ContextVar`, im Endpunkt gesetzt, weil LangGraph-Knoten Kontextkopien bekommen). | `services/mcp/auth.py:44,121-142`, `api/turn_auth.py:33-58` |
| Kein Client schickt heute `Authorization` an das Backend (Widget: `WLO-Access-Block`; Studio: Cookie und `X-Studio-Key`). Es gibt also keine Kollision. Der Studio-Proxy reicht `Authorization` aber durch. | `api/turn_auth.py:23-30`, `api/deps.py:28`, `api/studio_proxy.py:54,89` |
| Der MCP-Kopf wird neu gebaut; eingehende Köpfe gelangen nicht zum MCP. | `services/mcp/http_fabrik.py:36-46` |

### 2.2 Clusterfähigkeit

Schon über die Datenbank gelöst und bleibt so:
- Sitzungssperre (`session_locks`)
- Config mit NOTIFY
- Merkposten und Seitenkontext (`session_state`)
- SSE-Wiederaufnahme aus dem Verlauf
- Aufbewahrungslauf (clusterweit einmal)
- Studio-Login (HMAC, kein Prozessgeheimnis)
- Migrationen als eigener Job
- „ein Eval zugleich“ (Unique-Index 0006)

Fehler oder Schwächen bei N>1:

| Befund | Wirkung | Beleg |
|---|---|---|
| Lasttest-Aufräumen beim Start setzt **alle** `running`-Zeilen auf `failed`; der Wächter „ein Lauf zugleich“ ist nur Prüfen-dann-Einfügen | Jeder neue Pod bricht fremde Läufe ab; Wettlauf | `services/loadtest.py:267-304`, `main.py:129-135` |
| Eval-Lauf ist eine Task im Webprozess, ohne Heartbeat | Pod-Ende hinterlässt `running` bis 2 h, blockiert neue Läufe | `obs/tasks.py:69-78`, `services/eval/run_store.py:31-33,75-92` |
| Master-Skill je Pod im Speicher, Takt je Pod, „Neu laden“ nur lokal | bis 5 min verschiedene Anleitungen je Pod | `services/master_skill.py:52-76,270-313` |
| Rate-Limit-Speicher fällt auf `memory://` zurück | Limits und Login-Bremse N-fach | `settings.py:412-415` |
| LLM-Deckel je Pod (20 / AcademicCloud 2 / Moderation 4) | N×20 gegen ein Schlüssel-Limit | `services/llm_parallel.py:44-90` |
| DB-Pool 5+10 je Pod plus LISTEN | erschöpft `max_connections=100` ab N≈5 | `settings.py:407-411`, `db/notify.py:69` |
| Herunterfahren: Uvicorn 30 s + Lifespan 25 s | in K8s (Vorgabe 30 s Grace) gehen Antworten verloren | `api/sse.py:82-104`, `Dockerfile:142-144` |
| Reranker-Modell (~135 MB) wird je Pod von Hugging Face geladen | doppelte Arbeit ohne gemeinsames Volume | `services/rag/reranker_bezug.py:45-71` |

### 2.3 Übergabe-Checkliste

| Punkt | Stand | Lücke |
|---|---|---|
| OpenAPI | automatisch erzeugt, eingefroren, CI-Gate (`docs/api/openapi-v1.json`) | `/openapi.json` öffentlich mit ~90 Admin-Pfaden; keine Beschreibung; Version fest `0.1.0` |
| Ports | ein Port 8100; `/health` nur Liveness; `/api/health` zeigt Betriebsdetails öffentlich | kein `/ready`, kein `/metrics`, keine Trennung öffentlich/intern |
| Header, Typen, Zeiten | SSE, Audio, Multipart, ZIP/MD; Eval und Lasttest asynchron mit Status | nirgends gesammelt beschrieben |
| Monitoring | nur OTel-Traces (optional) | kein Prometheus, keine App-Metriken, keine Alarmregeln |
| Logging | Klartext, stdout, `LOG_LEVEL` | kein JSON, Zeit ohne Datum, keine Trace-ID, kein B3, kein `x-client-trace-id` |
| Build | dreistufig, Non-Root, CI, GHCR (`sha-…`, `latest`, Git-Tag) | Tags nicht SemVer (`0.5`); `reranker-model-v1.tar.gz` fehlt in `.dockerignore` |
| Konfiguration | `settings.py` mit Vorgaben, `SecretStr` | in `deploy/.env.example` fehlen 36 Variablen; Geheimnisse nicht getrennt; keine Values-Vorlage; keine gemessenen Ressourcen |
| Doku | `deploy/README.md`, `INSTALL.md`, `docs/architektur.md`, `docs/cluster-checkliste.md` | kein Übergabedokument |

## 3 Entscheide des Nutzers (2026-10-20)

1. **Schlüssel:** „Beides: Header vor Env“. Mit Kopf wird der Kopf genutzt, sonst `B_API_KEY`. Direkter Zugang bleibt möglich.
2. **Router:**
   - **Eine** Route reicht; nicht nach Zweck trennen.
   - Vorgabe bleibt ohne Routing mit `gpt-6-luna`, weil die Routen noch nicht angelegt sind. Der Chatbot muss aber eine Route annehmen können.
   - Für Tests darf eine **persönliche Route** am B-API-Schlüssel angelegt werden, mit `gpt-6-luna` und `gpt-5.6-luna`.
3. **Ports:** Studio bleibt öffentlich hinter dem Login. `/health`, `/ready` und `/metrics` kommen auf einen internen zweiten Port.
4. **Helm:** Values-Beispiel und Doku, feste Replikazahl. T6 baut das Chart.

## 4 Ansätze

**Router (Entscheid 2).**
- (A) Neuer Anbieter `b-api-router` mit eigenen Vorgaben. Verworfen: Er dupliziert `b-api-openai` in allen Verzweigungen (`llm_parallel`, `llm_nachrichten`, Moderation, Sprache).
- (B) **Gewählt:** eine Einstellung `B_API_ROUTE` (leer = aus), nur wirksam bei `LLM_PROVIDER=b-api-openai`. Ist sie gesetzt:
  - Chat-Aufrufe (Completions, Responses, Streaming, Klassifikator) gehen an `…/router` und schicken den Routennamen als `model`.
  - Die **Parameterregeln** kommen weiter vom eingestellten Chat-Modell (`LLM_CHAT_MODEL`, Vorgabe `gpt-6-luna`). Es steht für die Familie der Route: „Die Route verhält sich wie gpt-6-luna.“ Das passt, weil eine Route laut B-API nur Modelle einer Familie bündeln kann.
  - Einbettungen, Moderation und Sprache bleiben auf `/openai` („wir halten es einfach“).

**Cache auf dem Router.**
- Die Router-Doku nennt `?ignore-caching=true`.
- Ob LiteLLM einen Abfrage-Parameter auf Chat- **und** Responses-Weg weiterreicht (`extra_query`), ist ungeprüft. In `api_base` darf er nicht stehen, weil das SDK den Pfad dahinter anhängt.
- **Gewählt:** zuerst mit einem Fang-Server messen (wie Paket 7). Trägt `extra_query` auf beiden Wegen, wird es genutzt. Sonst gilt der gemessene Weg von `b-api-openai` weiter (zufälliges `user`); der Cache-Schlüssel der B-API umfasst den Body.

**Schlüssel durchreichen (Entscheid 1).** Ein `ContextVar` nach dem Vorbild des Zugangsblocks.
- Gesetzt wird er **nur** in den Endpunkten Chat, Chat-Stream, Agent und Sprache, und zwar immer, auch leer. Sonst erbte eine Studio-Anfrage den Wert eines vorigen Kontexts.
- Gelesen wird er an **einer** Stelle (`llm_auth.b_api_kopf()`), die `route()`, die Moderation und die Sprache nutzen.
- Hinaus geht **genau ein** Kopf `Authorization: Bearer …`, auch mit Env-Schlüssel. `X-API-KEY` entfällt (B-API-Regel „genau einen Header“; Bearer ist seit 13.10. gemessen gleichwertig).

**Lange Läufe im Cluster.**
- (A) Worker-Deployment mit Job-Claim. Verworfen für jetzt: Es braucht einen neuen Prozess und eine neue Komponente, und Entscheid 4 sieht feste Repliken vor.
- (B) **Gewählt:** Heartbeat-Spalte und Besitzer je Lauf. Aufgeräumt wird nur, was veraltet ist; ein Unique-Teilindex verhindert zwei Lauf-Zeilen. Der Worker bleibt als Ausblick im Übergabedokument.

**Metriken.**
- `prometheus-client` (Apache-2.0, offizielle Bibliothek) und eine kleine eigene Middleware.
- Verworfen: `prometheus-fastapi-instrumentator`. Er bringt eine Abhängigkeit mehr für das, was 40 Zeilen leisten.

**Logs.** Ein JSON-Formatter aus der Standardbibliothek, ohne neue Abhängigkeit, umschaltbar mit `LOG_FORMAT=json|text`.

**Zweiter Port.** Zwei `uvicorn.Server` in einem Prozess per `asyncio.gather` (eigener Einstieg `boerdi.serve`).
- Port 1: die bisherige App.
- Port 2: eine kleine App mit `/health`, `/ready`, `/metrics` und der vollen OpenAPI.
- Verworfen: zwei Prozesse. Dann wären die Metriken getrennt, und der Shutdown müsste zweimal abgestimmt werden.

## 5 Design

### 5.1 Neue und geänderte Einstellungen

| Variable | Vorgabe | Wirkung |
|---|---|---|
| `B_API_ROUTE` | leer | Routenname; nur bei `LLM_PROVIDER=b-api-openai`. Bei anderem Anbieter: Warnung beim Start, wirkungslos. |
| `INTERNAL_PORT` | `8101` | Port für `/health`, `/ready`, `/metrics`, `/openapi-full.json` |
| `LOG_FORMAT` | `text` | `json` für den Betrieb (Values-Beispiel setzt `json`) |
| `BOERDI_VERSION` | Build-Argument aus dem Git-Tag | `info.version` der Spec, `/ready`, Metrik `boerdi_build_info` |

`B_API_KEY` bleibt der Rückfall für Direktaufrufe und Hintergrundläufe: Eval, Lasttest, RAG-Import, Einbettungswechsel, Master-Skill-Takt, Vorwärmen.

### 5.2 Weg eines Zugs mit durchgereichtem Schlüssel

```
B-API-Proxy ──Authorization: Bearer K──▶ /api/chat(/stream) | /api/agent | /api/speech
   uebernimm_llm_schluessel(request)   → ContextVar = "Bearer K" (geprüft: ^Bearer [!-~]{8,512}$, sonst leer)
   Graph / Werkzeugschleife / Moderation / Schnellantworten (erben den Kontext)
   llm_auth.b_api_kopf() → {"Authorization": "Bearer K"}  (ohne Wert: "Bearer " + B_API_KEY)
   → B-API /openai/… bzw. /router/…
```

- **Nie geloggt.** Ein Test fängt alle Log-Einträge eines Zugs und sucht den Schlüssel; zusätzlich gilt das für die Texte von LiteLLM-Ausnahmen.
- Bei `LLM_PROVIDER=openai` wird ein eingehender Kopf ignoriert.

### 5.3 Trace-ID

Middleware auf Port 1, Quelle in dieser Reihenfolge:
1. `x-client-trace-id`
2. `X-B3-TraceId`
3. erster Teil von `b3`
4. sonst neu erzeugt (32 Hex-Zeichen)

Die ID gelangt in einen `ContextVar`, von dort per `logging.Filter` als Feld `trace_id` in jede Logzeile. Ausgehend wird sie an B-API und MCP weitergegeben, als `x-client-trace-id` und `X-B3-TraceId` plus neuer `X-B3-SpanId`. Zurück an den Client geht kein Kopf (Leitfaden: Standard ohne Header).

### 5.4 Metriken (Port 2, `/metrics`)

| Metrik | Labels |
|---|---|
| `boerdi_http_requests_total`, `boerdi_http_request_duration_seconds` | `route` (Pfad-Vorlage), `method`, `status` |
| `boerdi_turns_total`, `boerdi_turn_duration_seconds` | `engine`, `outcome` |
| `boerdi_llm_calls_total`, `boerdi_llm_call_duration_seconds` | `phase`, `outcome` |
| `boerdi_mcp_calls_total`, `boerdi_mcp_call_duration_seconds` | `server`, `outcome` (kein Werkzeugname: begrenzte Kardinalität) |
| `boerdi_sse_streams_active` | – |
| `boerdi_llm_slots_in_use` | `pool` |
| `boerdi_build_info` | `version` |

Alarmregeln als `PrometheusRule`-Beispiel im Values-Dokument:
- 5xx-Quote über 5 % in 10 min
- LLM-Fehlerquote über 10 %
- p95 Zugdauer über 30 s
- `/ready` fällt

### 5.5 OpenAPI

- **Port 1, `/openapi.json`:** gefilterte Spec mit den öffentlichen Pfaden: `/api/chat`, `/api/chat/stream`, `/api/agent*`, `/api/speech/*`, `/api/sessions/{id}/messages`, `/api/config/welcome`, `/api/config/guide-mode`, `/widget/*`.
  - `info.title`: „BOERDi – Chatbot von WirLernenOnline“
  - `info.description`: Text für Endnutzende; Entwurf §8, vom Nutzer abzunehmen
  - `info.version` = `BOERDI_VERSION`
- **Port 2, `/openapi-full.json`:** alles.
- **Export:** `docs/api/openapi-v1.json` bleibt der eingefrorene Gesamtvertrag. Neu ist `docs/api/openapi-public.json` mit demselben CI-Gate.

### 5.6 Dateien

| Datei | Verantwortung |
|---|---|
| `backend/src/boerdi/services/llm_auth.py` (neu) | `ContextVar`, Prüfung, `b_api_kopf()`, `uebernimm_llm_schluessel()` |
| `services/llm.py`, `services/llm_models.py` | Router-Weg, Regel-Modell, ein Auth-Kopf |
| `safety/moderation.py`, `services/speech_proxy.py` | Kopf über `llm_auth` |
| `api/chat.py`, `api/agent.py`, `api/speech.py`, `api/studio_proxy.py` | Schlüssel übernehmen bzw. streichen |
| `obs/trace_id.py` (neu) | Middleware, `ContextVar`, Log-Filter, ausgehende Köpfe |
| `obs/log_format.py` (neu) | JSON-Formatter |
| `obs/metrics.py` (neu) | Registry, Middleware, Zähler-Helfer |
| `api/intern.py` (neu) | interne App: `/health`, `/ready`, `/metrics`, `/openapi-full.json` |
| `serve.py` (neu) | Einstieg: zwei Uvicorn-Server, gemeinsamer Shutdown |
| `api/openapi_public.py` (neu) | Filter und Info-Block der öffentlichen Spec |
| `services/loadtest.py`, `services/eval/run_store.py`, `alembic/versions/0014_…` | Besitzer und Heartbeat der Läufe |
| `services/master_skill.py`, `alembic/versions/0014_…` | Master-Skill-Stand in der DB, NOTIFY, Takt über `__lauf:master-skill` |
| `Dockerfile`, `.dockerignore`, `.github/workflows/image.yml` | Port 2, Healthcheck, `BOERDI_VERSION`, SemVer-Tags |
| `deploy/.env.example`, `deploy/helm/values.example.yaml` (neu) | vollständige Env-Liste, Geheimnisse getrennt, Values-Mapping |
| `docs/uebergabe-betrieb.md` (neu) | Antworten auf die T6-Checkliste |

## 6 Aufgaben

Jede Phase beginnt mit **Schritt 0: `/better-coding-workflow` aufrufen**. Rot zuerst: Jeder Test wird vor der Umsetzung geschrieben und scheitert nachweislich.

### Phase A — B-API-Router

| # | Aufgabe | Test (rot zuerst) | Dateien |
|---|---|---|---|
| A0 | Persönliche Test-Route anlegen: `boerdi-test-luna`, Deployments `gpt-6-luna` (Prio 0) und `gpt-5.6-luna` (Prio 1), `maxAttempts` 2. Der Schlüssel kommt aus der OS-Umgebung (`B_API_KEY_STAGING`) und wird nie ausgegeben. Danach den Abruf über `GET /router/routes` prüfen. | – (Live) | – |
| A1 | Einstellung `B_API_ROUTE`; Warnung beim Start, wenn der Anbieter nicht `b-api-openai` ist | `test_settings_route.py`: Vorgabe leer; Warnung bei `openai` | `settings.py` |
| A2 | `route()`: mit Route `api_base=…/router`, `model=<route>`; Regeln, Responses-Weg und Preis-Vorgabe kommen vom Regel-Modell (`get_chat_model()`) | `test_llm_route_router.py`: gpt-6-Regeln mit Routenname, Pfad `/router/responses`, keine `temperature`/`max_tokens`; ohne Route unverändert | `services/llm.py`, `services/llm_models.py` |
| A3 | Fang-Server-Messung zu `ignore-caching` (Chat und Responses, LiteLLM `extra_query`), dann umsetzen wie gemessen | `test_llm_cache_bust.py`: Router-Weg setzt den gemessenen Mechanismus, `/openai` unverändert | `services/llm.py` |
| A4 | Eval-Kostenschätzung und Laufbedingungen mit dem Regel-Modell statt Routenname; die Laufbedingung nennt die Route zusätzlich | `test_eval_cost.py` erweitert | `eval/cost.py:143`, `eval/run_conditions.py:75` |
| A5 | Live-Probe mit `B_API_ROUTE=boerdi-test-luna` (lokal, Wegwerf-DB): ein Muster-Zug, ein Agent-Zug mit Werkzeugen, ein Stream-Zug. `resp.model` im Verbrauchsbuch muss ein gebuchtes Upstream-Modell sein. Den kleinen Chat-Smoke macht Claude, Golden-Läufe der Nutzer. | – (Live, Log im Plan) | – |
| A6 | Doku: `docs/architektur.md` §5.6 (vierte Zeile Router), `deploy/README.md` (Umstellung: erst Route, dann `B_API_ROUTE`), Skill-Hinweis `wlo-b-api-llm` veraltet (Bearer) | – | Doku |

### Phase B — Schlüssel durchreichen

| # | Aufgabe | Test (rot zuerst) | Dateien |
|---|---|---|---|
| B1 | `llm_auth.py`: `ContextVar`, Formprüfung (`^Bearer [!-~]{8,512}$`, kein CR/LF, Groß-B), `b_api_kopf()` | `test_llm_auth.py`: gültig, kleingeschrieben → verworfen, zu lang → verworfen, ohne → Env | neu |
| B2 | Übernahme in `api/chat.py` (POST und Stream), `api/agent.py` (beide), `api/speech.py`, immer neben `uebernimm_zugang` | `test_llm_auth_endpunkte.py`: der Kopf erreicht die LLM-Attrappe; eine Studio-Anfrage danach sieht leer | `api/*` |
| B3 | `route()`, Moderation und Sprache nehmen `b_api_kopf()`; `X-API-KEY` entfällt | `test_llm_route_kopf.py`: genau ein `Authorization`, kein `X-API-KEY` (Chat, Responses, Moderation, STT/TTS) | `llm.py`, `moderation.py`, `speech_proxy.py` |
| B4 | Studio-Proxy streicht `Authorization` | `test_studio_proxy.py` erweitert | `api/studio_proxy.py` |
| B5 | Hintergrundläufe nehmen den Env-Schlüssel, auch wenn eine Proxy-Anfrage sie anstößt (Eval aus dem Studio, spekulative Tasks nach Zugende) | `test_llm_auth_hintergrund.py` | – |
| B6 | Nie geloggt: ein Zug mit Schlüssel und ein Zug mit 401 der Attrappe; kein Log-Eintrag und keine Fehlerblase enthält den Schlüssel | `test_llm_auth_kein_leck.py` (caplog) | ggf. `api/chat.py:122` |
| B7 | Live-Probe lokal: Anfrage mit eigenem Schlüssel als `Authorization` ohne `B_API_KEY` in der Umgebung → 200; kleingeschriebenes `bearer` → Rückfall bzw. 401-Fehlerpfad sauber; Moderation mit Bearer allein klärt `entscheidungen-offen.md:278` | – (Live) | Doku |

### Phase C — Clusterfähigkeit

| # | Aufgabe | Test (rot zuerst) | Dateien |
|---|---|---|---|
| C1 | Migration 0014: `loadtest_runs.owner`, `heartbeat_at`, Unique-Teilindex auf `status='running'`; Heartbeat alle 15 s; Aufräumen beim Start nur bei `heartbeat_at` älter als 90 s | `test_loadtest_cluster.py`: frischer Lauf eines anderen Besitzers bleibt; veralteter wird `failed`; zweiter Start → 409 | `services/loadtest.py`, `api/loadtest.py`, Migration |
| C2 | Eval: `heartbeat_at`, Frist 3 min statt 2 h; im Lifespan-Ende eigene Läufe auf `failed` (`abgebrochen: Pod beendet`) | `test_eval_heartbeat.py` | `services/eval/run_store.py`, `main.py` |
| C3 | Master-Skill: Stand (Text, Hash, Abrufzeit) in einer DB-Zeile; Verteilung über die NOTIFY-Bahn; Takt nur unter `sitzungssperre("__lauf:master-skill", warten_s=0)`; „Neu laden“ schreibt die Zeile | `test_master_skill_cluster.py`: zwei Instanzen sehen nach Neu-Laden denselben Hash; nur eine ruft im Takt ab | `services/master_skill.py`, Migration |
| C4 | Warnung beim Start, wenn `RATE_LIMIT_STORAGE_URI=memory://` und `KUBERNETES_SERVICE_HOST` gesetzt ist | `test_ratelimit_warnung.py` | `main.py` oder `api/ratelimit.py` |
| C5 | `reranker-model-v1.tar.gz` in `.dockerignore` | – (Build-Kontext prüfen) | `.dockerignore` |
| C6 | `docs/cluster-checkliste.md` ergänzen: Lasttest/Eval/Master-Skill, Pool-Rechnung, Grace ≥ 65 s, preStop 5 s, SSE ohne Pufferung, Lese-Timeout > 10 s | – | Doku |

### Phase D — Übergabe an T6

| # | Aufgabe | Test (rot zuerst) | Dateien |
|---|---|---|---|
| D1 | Interne App und Einstieg `boerdi.serve`: Port 1 öffentlich, Port 2 `/health` (Liveness), `/ready` (DB `SELECT 1`, Lifespan fertig, Version). Gemeinsamer Shutdown mit den bisherigen Fristen. Dockerfile: `EXPOSE 8101`, Healthcheck auf 8101, CMD `python -m boerdi.serve`. CI-Smoke auf 8101. | `test_intern_app.py`: `/ready` 503 ohne DB, 200 mit; Port 1 liefert `/health` nicht mehr | `serve.py`, `api/intern.py`, `Dockerfile`, `image.yml`, `compose*.yml` |
| D2 | `/api/health` nur mit Studio-Anmeldung (das Studio nutzt es für Anzeige und Status) | `test_api_health_auth.py` | `api/health.py` |
| D3 | Prometheus-Metriken nach §5.4, Lizenz-Gate prüfen | `test_metrics.py`: Zähler steigen nach einem Zug; `/metrics` nur auf Port 2 | `obs/metrics.py`, Aufrufstellen |
| D4 | JSON-Log und Trace-ID nach §5.3: Datum in der Klartext-Zeit; ausgehende Köpfe an B-API und MCP | `test_trace_id.py`: Übernahme, Erzeugung, Weitergabe an LLM- und MCP-Attrappe, Feld im JSON-Log; `test_log_format.py` | `obs/trace_id.py`, `obs/log_format.py`, `main.py`, `llm_auth.py`, `mcp/http_fabrik.py` |
| D5 | Öffentliche Spec nach §5.5; Export und CI-Gate für `openapi-public.json` | `test_openapi_public.py`: keine `/api/config/*` außer welcome/guide-mode, Info-Block gesetzt | `api/openapi_public.py`, `scripts/export_openapi.py`, `ci.yml` |
| D6 | Env-Inventar: Test vergleicht `Settings`-Felder und `os.getenv`-Stellen mit `deploy/.env.example`. Die 36 fehlenden ergänzen. Geheimnisse in eigenem Abschnitt. | `test_env_beispiel.py` | `deploy/.env.example` |
| D7 | `deploy/helm/values.example.yaml`: Image (SemVer-Tag), Replikas, Ressourcen, `env` / `secretEnv`, Ports und Probes, `postgresql.enabled` / `valkey.enabled` mit externen Verbindungsdaten, Migrate-Job, Reranker-initContainer, `terminationGracePeriodSeconds`, Alarmregeln | – (Prüfung: jede Variable aus D6 kommt vor, per Test) | neu |
| D8 | SemVer: `BOERDI_VERSION` als Build-Argument aus dem Tag; nächstes Release `0.6.0`; `__init__.__version__` liest es | `test_version.py` | `Dockerfile`, `image.yml`, `__init__.py` |
| D9 | `docs/uebergabe-betrieb.md`: je Checklistenpunkt die Antwort. Enthält: Header und Content-Types (SSE mit Wolli abstimmen), Antwortzeiten, Zustand und Skalierung, Architektur-Kurzbild (Link Pages), Datenbankwahl, Daten (Reranker-Volume), Kosten je Zug, Ansprechperson (Nutzer trägt ein), Wartung | – | neu |
| D10 | Ressourcen-Grundlast messen (`docker stats` während eines Lasttests). **Wartet auf freien Speicher beim Nutzer**; Startwerte bis dahin aus `INSTALL.md` | – | `docs/uebergabe-betrieb.md` |

Reihenfolge: A → B (beide ändern `route()`), C und D unabhängig davon; in D zuerst D1, dann D3, D4 und D5.

## 7 Abnahme

- **Alle Phasen:**
  - `cd backend && uv run pytest -q -p no:cacheprovider` grün
  - `uv run ruff check src tests` sauber
  - `scripts/export_openapi.py --check` für beide Specs
- **A:** Live-Probe A5 im Log: Route trifft, gebuchtes Modell ist ein Upstream-Modell, kein 400 wegen Parametern.
- **B:** B6 grün; Live-Probe B7 im Log.
- **C:** neue Tests grün mit Postgres (`compose.dev.yml up -d postgres valkey`); `test_cluster_checklist.py` weiter grün.
- **D:**
  - Image-Smoke in CI auf Port 8101.
  - `curl :8100/metrics` → 404, `curl :8101/metrics` → 200.
  - Übergabedokument deckt jeden Checklistenpunkt ab (Abgleich in der Abschlussprüfung).
- **Regression:**
  - Muster- und Agent-Zug ohne `B_API_ROUTE` und ohne Kopf verhalten sich wie vorher.
  - Golden-Lauf (Nutzer) vor dem Merge.

## 8 Offen bzw. vom Nutzer abzunehmen

- Beschreibungstext der öffentlichen Spec. Entwurf: „BOERDi hilft beim Finden und Nutzen offener Bildungsinhalte von WirLernenOnline: Fragen stellen, passende Materialien, Themenseiten und Sammlungen erhalten, Inhalte zusammenfassen lassen.“
- Ansprechperson T4 und Wartungsverantwortung (Übergabedokument).
- SSE über den B-API-Proxy: mit Wolli abstimmen (Content-Type `text/event-stream`, Pufferung, Timeout).
- An das B-API-Team, nicht hier zu lösen:
  - Dauerfehler kommen als 503, kosten mit den SDK-Wiederholungen etwa 15 s.
  - Cache-Treffer sind nicht gekennzeichnet.
- An das MCP-Team: 120 Anfragen je Minute und IP teilen sich alle Pods.
- Persönliche Test-Route `boerdi-test-luna`: bleibt bis zur Abnahme, danach löschen (Nutzer).

## 9 Log

| Datum | Eintrag |
|---|---|
| 2026-10-20 | Plan nach drei Prüfungen und vier Nutzer-Entscheiden. Freigabe: „better coding workflow skill nutzen und mit der umsetzung beginnen“. |
| 2026-10-20 | **A0:** persönliche Route `boerdi-test-luna` am Staging-Schlüssel angelegt (`gpt-6-luna` Prio 0, `gpt-5.6-luna` Prio 1, `maxAttempts` 2; Skript `p17_route.py` im Scratchpad, Schlüssel aus `B_API_KEY_STAGING`, nie ausgegeben). Roh gemessen: `/router/responses` und `/router/chat/completions` 200, Antwortmodell `gpt-6-luna`; `max_tokens` an die Route → 400 „Use 'max_completion_tokens'“. **Cache:** wortgleiche Anfragen kamen heute auf `/router` UND `/openai` jedes Mal frisch (neue id, 0,8–1,2 s, kein Kennzeichen) — der b-api-Cache greift derzeit nicht; `?ignore-caching=true` wird angenommen (200). |
| 2026-10-20 | **A1/A2:** `B_API_ROUTE` (Vorgabe leer) ersetzt den Wire-Namen NUR des eingestellten Chat-Modells (`llm.router_route`); `/router` statt `/openai`; Regeln/Responses-Weg vom Chat-Modell; Einbettungen, Judge, Simulator bleiben auf `/openai`. Warnung beim Start, wenn der Anbieter nicht `b-api-openai` ist. `weg_beschreibung` nennt `route` (damit auch die Messbedingungen der Läufe). Tests `test_llm_router.py` (rot zuerst: 5 rot, 5 Altverhalten grün). |
| 2026-10-20 | **A3 (Entscheid nach Messung):** keine Änderung. Weil die b-api heute nichts cacht, ist keine Umgehung gegen echte Treffer messbar; der Router läuft unter `b-api-openai`, also mit dem 2026-08-21 gemessenen Weg (zufälliges `user` im Body — Cache-Schlüssel der b-api ist der Body). `extra_query`/`ignore-caching` erst, wenn der Cache wieder greift und es gemessen werden kann. |
| 2026-10-20 | **A5 Live-Probe** über den Chatbot-Transport (`p17_a5_probe.py`, Staging, Route): einfacher Aufruf 2,1 s, Werkzeugaufruf `respond_to_user` 6,9 s, Stream mit Token-Weitergabe 6,9 s — alle über `/router/responses`. **Befund:** LiteLLM meldet den ROUTENNAMEN als `resp.model` (auch `_hidden_params` trägt das Upstream-Modell nicht) → Kosten blieben unbepreist. Behoben mit `llm.antwort_modell` an den drei Transportstellen (Chat, Stream, Klassifikator inkl. Fehlversuche): gebucht wird unter `LLM_CHAT_MODEL`. Nachmessung: `model='gpt-6-luna'` in allen drei Fällen. **A4** ohne Code: `eval/cost.py` rechnet schon mit `get_chat_model()`; die Route steht über `weg` in den Messbedingungen. |
| 2026-10-20 | **B1–B4:** `services/llm_auth.py` (`ContextVar`, Form `^Bearer [!-~]{8,512}$` als fullmatch — Groß-B, ein Leerzeichen, kein CR/LF; `b_api_schluessel()` = Zug vor `B_API_KEY`). Übernahme in `api/turn_auth.uebernimm_zugang` (damit in Chat POST/Stream und beiden Agent-Endpunkten) und in den drei Sprach-Endpunkten; ein unbrauchbarer Wert wird ohne Wert gemeldet und verworfen. `route()`, Moderation und Sprache: genau EIN Kopf (SDK baut `Authorization: Bearer` aus `api_key`), **`X-API-KEY` entfällt**. Studio-Proxy streicht `authorization`. `speech_enabled` zählt auch den durchgereichten Schlüssel. Tests `test_llm_auth.py` (rot zuerst: Import fehlte), u. a. Zug ohne Kopf erbt nichts, kein Schlüssel in Log/Antwort (caplog, Fehlerpfad). Sechs Alt-Tests pinnten den Zweitkopf `X-API-KEY` — auf den neuen Vertrag umgestellt (Schlüssel + „kein zweiter Kopf“, nicht abgeschwächt); die Kennlinie prüft das jetzt auf dem Draht (Fang-Server: nur `authorization`). Moderations-Tests binden `llm_auth` per Fixture an ihre Settings-Attrappe (sonst hingen sie an der `.env`). |
| 2026-10-20 | **B5:** ohne Code — Studio-gestartete Läufe (Eval, Lasttest) rufen `/api/chat` ohne `Authorization` bzw. über den Studio-Proxy (streicht ihn) und nehmen damit `B_API_KEY`; jede ASGI-Anfrage startet mit frischer Kontextkopie, ein Wert kann nicht in eine andere Anfrage wandern. Spekulative Nebenaufgaben EINES Zuges erben seinen Schlüssel — gewollt, sie gehören zu diesem Zug. |
| 2026-10-20 | **B7 Live-Probe** (Staging, `p17_b7_probe.py`, Anlage-Schlüssel hart leer — Achtung `env_ignore_empty`: ein leeres `B_API_KEY=` fiele auf `backend/.env` zurück): Chat mit durchgereichtem Bearer allein → „OK“, `gpt-6-luna`; **Moderation mit Bearer allein → vollständige Antwort** (klärt `entscheidungen-offen.md`, Eintrag B-API-Moderation); `bearer` klein → verworfen → 401; falscher Schlüssel → 401. In keinem Fehlertext stand der Schlüssel. Doku: `architektur.md` §5.6 (Absatz „Schlüssel des Aufrufers“), `deploy/.env.example`, `entscheidungen-offen.md`. Hinweis an den Nutzer: der globale Skill `wlo-b-api-llm` beschreibt noch „X-API-KEY, kein Bearer“ (SKILL.md:19, :217) — veraltet. |
| 2026-10-20 | **Review A und B** (Nutzer: „je Phase einen kurzen Review … Befunde beheben“; zwei frische Prüfer, better-coding-review). A: 0 CRITICAL/MAJOR, 4 MINOR, 2 NIT; B: 0/0, 3 MINOR, 1 NIT — jeder Befund am Quelltext nachgeprüft. Behoben: **A-1** Doku/Kommentar „Judge und Simulator bleiben auf `/openai`“ falsch — ohne `EVAL_JUDGE_MODEL`/`EVAL_SIMULATOR_MODEL` sind sie das Chat-Modell und folgen der Route (Text berichtigt, Verhalten gewollt). **A-2** Warnung beim Start, wenn `LLM_CHAT_MODEL` der Routenname ist (rot zuerst). **A-3** Tests für Anbieter-Prüfung (openai direkt: Modellname statt `responses/<route>`) und AcademicCloud mit Route. **A-4** Buchungs-Tests für Strom und Klassifikator inkl. Fehlversuche. **A-5** `router_route`/`antwort_modell` nach `services/llm_router.py` (Re-Export in `llm`), `llm.py` 331 → 311 Zeilen. **A-6** `deploy/README.md` „Auf eine Route des b-api-Routers umstellen“, Buchung beim Ausweichen in §5.6. **B-2** Test-Lücken: Draht-Tests am lokalen Fang-Server (genau der eingehende Kopf, kein `x-api-key`; ein 401 mit leerem Rumpf trägt den Schlüssel in keinen Fehlertext/Log), Sprachstatus mit Kopf; **Mutationsprobe** (`p17_mutation.py`): der Endpunkt-Test „ohne Kopf erbt nichts“ blieb ohne Löschen grün — FastAPI führt den Endpunkt in eigenem Kontext aus, auch unter `ASGITransport`; ersetzt durch einen Funktionstest (Mutation → rot). Die Wächter für Rückabbildung und Anbieter-Prüfung wurden unter Mutation rot. **B-3** `B_API_BASE_URL` gehört zum Deployment des Proxys (`.env.example`, §5.6). **B-4** veraltete Docstrings (Moderation, Sprache). Sprache: mit `B_API_AUDIO=1` ohne Schlüssel nennt der Grund jetzt den fehlenden Schlüssel (rot zuerst). **Nicht umgesetzt (B-1, begründet):** LiteLLM baut je Schlüssel einen eigenen HTTP-Client — es gibt aber nur drei Schlüssel (WLO Person, WLO Gast, `B_API_KEY`); ein globaler `litellm.aclient_session` beträfe jeden LiteLLM-Aufruf. Als bekannte Grenze in §5.6 vermerkt. Gezielte Suiten 168 grün, ruff sauber. |
| 2026-10-20 | **Phase C zurückgestellt, D vorgezogen** (Nutzer-Zustimmung): C braucht Postgres für die Tests, Docker wartet auf freien Speicher. |
| 2026-10-20 | **D1:** `api/intern.py` (eigene App ohne Spec: `/health` Liveness ohne DB, `/ready` = Lifespan fertig + `SELECT 1` mit 2-s-Frist + Hauptserver fährt nicht herunter; Fehlertext nur ins Log), `serve.py` (`python -m boerdi.serve`: Hauptserver 8100 mit den bisherigen Flags, interner Server `INTERNAL_PORT`=8101 ohne Lifespan und ohne eigene Signal-Handler — Uvicorn setzt sie je Server, der zweite überschriebe den ersten). Prozess-Probe (`p17_serve_probe.py`): beide Ports antworten, `/ready` 503 „startet“, ein Signal beendet den Prozess; Uvicorn löst das abgefangene Signal nach dem geordneten Ende erneut aus (wie bisher unter dem CLI). Fehlstart (Postgres unerreichbar) endet mit **3** wie der Uvicorn-CLI (live geprüft; den Code setzt Uvicorn selbst — die zunächst gebaute `beendigungs_code` war toter Code und ist seit dem Review entfernt). Dockerfile: `EXPOSE 8100 8101`, HEALTHCHECK auf 8101, CMD `python -m boerdi.serve`. CI-Smoke: `-p 8101:8101`, `/health` + `/ready` (200 mit DB) am internen Port, `/api/health` ohne Schlüssel = 401. **Abweichung vom Plan:** `/health` bleibt am öffentlichen Port (nur `{"status":"ok"}`, bestehende Proben/Traefik hängen daran; der Vertrags-Wächter kennt keine entfernten Operationen) — er kommt auf die Ausblend-Liste des Ingress (Leitfaden: „die auszublendenden Pfade explizit benennen“). Wächter `test_das_herunterfahren_passt_in_die_gnadenfrist` las die Frist per Regex aus der Dockerfile-CMD → liest sie jetzt aus `serve.baue_server`. |
| 2026-10-20 | **D2:** `GET`/`HEAD /api/health` mit `Security(require_studio_key)` (Studio liest über seinen Proxy); `/` leitet auf `/studio/` statt auf `/api/health`. Vertrag gemessen: genau zwei Blätter (`security` an beiden Operationen), eingetragen in `bewusste-vertragszusaetze.md`, neu erzeugt, `--check` grün. `PUBLIC_ROUTES` im Vertragstest ohne `/api/health`; Form-Tests öffnen per `BOERDI_ALLOW_OPEN_ADMIN`, die Anmeldung prüft `test_api_health_auth.py`. Eval-Vorabprüfung (`run_store._ensure_chat_reachable`) unberührt: sie zählt jede Antwort, auch 401, als erreichbar. Volle Suite: 6043 grün, 1 Fehlschlag = DB-Lifespan-Test (kein Docker). |
| 2026-10-20 | **D3:** `prometheus-client` 0.26 (Apache-2.0 AND BSD-2-Clause, Lizenz-Gate grün) mit der Standard-Registry (Prozess-, Python-, GC-Metriken). `obs/metrics.py`: `boerdi_http_requests_total`/`_duration_seconds` {route, method, status}, `boerdi_http_requests_in_progress` (statt eines SSE-Zählers in `sse.py` — die laufenden Anfragen sind überwiegend offene Zug-Ströme, der empfindliche Abbruch-Code bleibt unberührt), `boerdi_turns_total` {engine} im Buchungs-Trichter (`api/chat._record_usage`, `api/agent._buchen`), `boerdi_llm_calls_total`/`_duration_seconds` {phase, outcome} über `metrics.llm_messung` an allen drei Transportstellen (`chat_completion`, Strom = Phase `strom`, Klassifikator), `boerdi_mcp_calls_total`/`_duration_seconds` {server = Host, outcome = ok/tool/transport/timeout/auth} in `transport.call_tool`, `boerdi_build_info` {version}. `/metrics` nur an der internen App. **Routen-Label, zwei Fehlversuche, dann gemessen:** Starlette 1.3 setzt kein `scope["route"]`, ein gesetztes `endpoint` kommt aus der Scope-Kopie des Routers nicht zurück, und FastAPI 0.139 hängt eingebundene Router als `_IncludedRouter` ohne Pfad ein → die Vorlagen kommen aus `app.openapi()` (stabil, öffentlich), feste vor parametrisierten, `/studio`, sonst `andere`; scheitert das, kostet es nur das Label (Test). Tests `test_metrics.py` (rot zuerst), u. a. keine Sitzungs-ID im Label. Gezielte Suiten 170 grün. |
| 2026-10-20 | **D4:** `obs/trace_id.py` (reines ASGI, äußerste Schicht: ID aus `x-client-trace-id` [sichtbar, ≤128], sonst `X-B3-TraceId`, sonst erster Teil von `b3`, sonst neu, 32 Hex; `TraceIdFilter` je Logzeile; ausgehend `x-client-trace-id` + B3 `X-B3-TraceId`/neue `X-B3-SpanId`, B3 nur bei gültiger Hex-ID; nie zurück an den Client), `obs/log_format.py` (`LOG_FORMAT=json|text`, Vorgabe `text`; JSON: Zeit UTC ISO mit `Z`, Level, Logger, Nachricht, Trace-ID, Ausnahme; Klartext jetzt mit Datum und Trace-ID). Ausgehend über `llm.route()` (Chat, Strom, Klassifikator, Einbettung, Sprache) und die Moderation — **nur an die b-api**, nicht an OpenAI direkt (externer Dritter, Test); an den eigenen MCP-Server über `build_http_client_factory` (mit und ohne Zugangsblock), fremde Server der Registry bekommen nichts. `boerdi.serve` mit `log_config=None`: Uvicorns Zeilen laufen über die Wurzel (Minimal-Nachbau: Zugriffszeile `uvicorn.access` als JSON mit `trace_id: probe-4711`). **Befund der Prozess-Probe:** Logging nach stdout (Leitfaden) statt bisher stderr — stdout kodiert streng, auf einer Konsole ohne UTF-8 warf jede Zeile mit „⚠“ einen Logging-Fehler → JSON als ASCII (gültig, `\u`-Escapes), `StdoutHandler` bildet Klartext auf die Kodierung des Stroms ab (beide rot zuerst). Ein verwaister Probe-Prozess (eigener) hielt die Ports — beendet, nur nach Prüfung der Kommandozeile. `.env.example`/`compose.prod.yml`: `LOG_FORMAT`, `INTERNAL_PORT`. Gezielte Suiten 724 grün. |
| 2026-10-20 | **D5:** `api/openapi_public.py` leitet die öffentliche Spec aus der vollen ab (nie veraltet): 9 Operationen (Chat + Strom, Agent + Strom, Sprache ×3, Verlauf, Lotsen-Modus; Widget-Dateien sind keine API), nur die transitiv gebrauchten Schemas (23) und Verfahren (`StudioKey`), `info` = „BOERDi – Chatbot von WirLernenOnline“ + Beschreibungs-Entwurf (§8, Nutzer) + `BOERDI_VERSION`. Haupt-App: `openapi_url=None`, eigene `/openapi.json` (außerhalb des Schemas) liefert die öffentliche; interne App: `/openapi-full.json`. `/docs`, `/redoc` weiter aus. Export: `docs/api/openapi-public.json` (Version im Export fest „1“, sonst driftete die Datei mit jedem Tag) mit demselben `--check` (CI-Schritt bleibt). Gesamtvertrag gegen den Klon: genau die zwei D2-Sicherheitsangaben. **Falle wiederholt:** ein `replace` ohne Prüfung im Bash-Heredoc lief still ins Leere (Rückstrich) → Datei mit dem Edit-Werkzeug berichtigt; Patch-Skripte prüfen seither jede Ersetzung. Tests `test_openapi_public.py` (rot zuerst). |
| 2026-10-20 | **D6:** Wächter `test_env_beispiel.py` (rot zuerst: 38 fehlende Variablen, 6 ungekennzeichnete Geheimnisse) gleicht `Settings` + `os.getenv`-Stellen mit `deploy/.env.example` ab und verlangt `[GEHEIMNIS]` über jedem Geheimnis (SecretStr-Felder + `POSTGRES_PASSWORD`, `DATABASE_URL`) — und nur dort. `.env.example`: Abschnitt „WEITERE EINSTELLUNGEN“ (Vorgabe + Bedeutung, nach Themen), Image-Werte ehrlich als „im Compose-Betrieb nicht über die .env einstellbar“. Der bestehende Compose-Wächter („dokumentiert ⇒ durchgereicht“) verlangte die neuen Namen in `compose.prod.yml`: konfigurierbare als `${VAR:-}` durchgereicht (leer = Code-Vorgabe), die sechs Image-Werte bewusst NICHT (eine leere Durchreichung überschriebe die Dockerfile-ENV) — dort als Kommentar mit Grund. Veralteter Hinweis zu `EMBED_INGEST_PARALLEL` berichtigt. |
| 2026-10-20 | **D7:** `deploy/helm/values.example.yaml` (einmalig aus `Settings` erzeugt, Betriebswerte darüber; danach Handpflege): Image mit SemVer-Tag, `replicaCount`, Ports public/internal, Ingress nur public (SSE ohne Pufferung, Lese-Timeout 120 s, `/health` ausblenden), Proben am internen Port, `terminationGracePeriodSeconds: 70` + preStop 5 s, Ressourcen **vorläufig** (D10), `migrateJob` = Compose-Befehl, Reranker-Volume RWX, `postgresql.enabled: false` + externe Verbindung, `valkey.enabled`, PrometheusRule (5xx, LLM-Fehler, p95 Zug, MCP-Transport), `secretEnv` aus bestehendem Secret (7), `imageEnv` (6), `env` (76). Wächter `test_helm_values.py` (rot zuerst): jede Einstellung abgebildet, Geheimnisse nur als Secret, Proben/Ingress, Gnadenfrist ≥ Herunterfahren, Valkey statt `memory://`, JSON-Logs, Migration = Compose, Tag ≠ `latest`. |
| 2026-10-20 | **D8 ohne Code:** die CI setzt `BOERDI_VERSION` schon aus dem Git-Ref-Namen und veröffentlicht `sha-…`, den Tag-Namen und `latest` (nur main). SemVer = Tag-Schema ab `0.6.0` (vorher `0.5`); `__version__` bleibt fest (`0.1.0`), weil der eingefrorene Vertrag sie trägt — die öffentliche Spec nimmt `BOERDI_VERSION`. Kein `test_version.py`. |
| 2026-10-20 | **D9:** `docs/uebergabe-betrieb.md` — die T6-Checkliste in 15 Punkten (Repo/CI/Marken, OpenAPI, Ports + Ausblend-Pfad `/health`, Header/Content-Types/Zeiten, b-api Variante A und B samt Schlüssel-Rechten und Route, Monitoring, Logging/Tracing, Datenbank + abschaltbare Teile, Zustand/Skalierung mit den offenen Phase-C-Punkten, Ressourcen vorläufig, Konfiguration/Secrets, große Daten, Kosten, Ansprechperson, Wartung); verweist auf die von Tests gehaltenen Dateien statt sie zu wiederholen. Offen beim Nutzer: Ansprechperson, Wartungsverantwortung, Beschreibungstext, SSE mit Wolli. **D10** wartet auf freien Speicher (Docker). |
| 2026-10-20 | **Review Phase D** (zwei frische Prüfer, better-coding-review; Code: 2 MAJOR, 7 MINOR, 4 NIT; Konfiguration/Doku: 1 MAJOR, 8 MINOR, 3 NIT — jeder Befund am Quelltext geprüft). Behoben, Tests rot zuerst (`test_review_phase_d.py`): **C1** Routen-Label der Studio-SPA (der Mount setzt `root_path` um, `/studio/` zählte als `/`) → Pfad vor dem Aufruf gemerkt. **C2** `LOG_LEVEL=WARN` → `KeyError` in Uvicorn (Container startete nicht) → Stufe als Zahl (`serve._log_stufe`, Unbekanntes = INFO). **C3** Abbruch als eigener Ausgang `abbruch` statt `fehler` (Alarmregel). **C4** Trace-ID wird nur nach Erfolg zurückgesetzt — Uvicorns Fehlerzeile trägt sie. **C5** `/ready` erst mit laufendem Hauptserver (`gestartet_von`), nicht schon mitten im Lifespan. **C6** eigene Probe-Engine ohne Pool (ein voller Chat-Pool macht nicht alle Pods „nicht bereit“), `timeoutSeconds: 3` an den Proben. **C7** öffentliche Spec: `/api/agent*` nennen zuerst den Zugangsblock (`WloAccessBlock`, Kopf `WLO-Access-Block`), dann den Studio-Schlüssel — vorher nur der Admin-Schlüssel. **C10** B3 in Kleinbuchstaben, Null-ID verworfen. **C11** `beendigungs_code` entfernt — Uvicorn beendet einen Fehlstart selbst mit 3 (toter Code; die Log-Zeile D1 dazu berichtigt). **C12** `INTERNAL_PORT=8100` abgewiesen, der HEALTHCHECK liest `INTERNAL_PORT`. **C13** öffentliche Spec je App einmal gebaut. **C9** (Lücken HEAD/fremder MCP/Moderation) als Wächter ergänzt, waren schon richtig. **K1 (MAJOR)** Values `TRUST_FORWARDED_FOR: "false"` mit Bedingung (Ingress muss XFF überschreiben) + Hinweis „hinter dem b-api-Proxy teilen sich ohne XFF alle Nutzer ein Limit“ (Übergabe §5, mit dem b-api-Team klären). **K2** Alarm p95 > 60 s, Chat und Agent. **K3** Gnadenfrist-Test zählt preStop mit. **K4** Doku: SSE-Köpfe, Histogramm-Labels, B3 nur bei Hex-ID, Text-Extraktion ohne Verbraucher. **K5** Reranker-Volume an `RAG_RERANKER_ENABLED` gekoppelt (Vorgabe aus), initContainer-Beispiel als Kommentar. **K6** Worker-Aussage, `valkey.external`. **K8/K9/K11/K12** Kennzeichnungen in `.env.example` (in Compose fest, ohne Verbraucher, `curl` mit Studio-Schlüssel), Staging-Adressen in den Values kommentiert, Messdaten mit Datum, Aufbewahrung um Sicherheitsprotokoll (90 Tage) und „Sitzungen/usage_events nie gelöscht“ ergänzt. **K10** Gegenrichtung im Env-Wächter. **K7** durch C12 erledigt. **C8 — bewusste Abweichungen vom Plan §5.4/5.5:** kein `boerdi_turn_duration_seconds` (die Zugdauer liefert das HTTP-Histogramm je Route; ein Strom dauert so lange wie seine Anfrage), kein `outcome` an `boerdi_turns_total` (Fehler zeigen 5xx- und LLM-Zähler), kein `boerdi_llm_slots_in_use` (nicht gebaut, bei Bedarf in `llm_parallel.platz`); `/api/config/welcome` nicht in der öffentlichen Spec — die Route ist hier Studio-geschützt. **Bekannter Wackel-Test (außerhalb):** `test_loadtest_anfragen::test_die_werkzeugzeit_kommt_vom_echten_erzeuger` erwartet ≥ 20 ms aus zwei `asyncio.sleep(0.01)`; der Windows-Timer liefert unter Suite-Last weniger, einzeln grün. |
| 2026-10-20 | **A6:** `docs/architektur.md` §5.6 (Router-Absatz), `deploy/.env.example` (`B_API_ROUTE` mit Reihenfolge-Hinweis), `deploy/compose.prod.yml` reicht `B_API_ROUTE` durch. Gezielte Suiten 166 grün, ruff sauber. |
| 2026-10-20 | **C1/C2:** Lauf-Herzschlag — `obs/herzschlag.mit_herzschlag` schreibt `heartbeat_at` alle 15 s, solange ein Lasttest/Eval-Lauf arbeitet (Migration 0014: Spalten an `loadtest_runs`/`eval_runs`, Unique-Teilindex `uq_loadtest_runs_ein_laufender`, vorher überzählige laufende Lasttests auf `failed`). Lasttest verwaist nach 90 s ohne Herzschlag (`any_run_running` räumt selbst ab, kein Neustart nötig), gleichzeitiger Start → 409 aus der DB (`LastTestLaeuftSchon`); Eval verwaist nach 3 min statt 2 h nach dem Start. Tests: `test_cluster_laeufe_pg.py` (8), `test_loadtest_pg.py`/`test_loadtest_router.py` angepasst (Spawn trägt jetzt den Herzschlag-Wrapper, geprüft). **Abweichung vom Plan:** kein Besitzer je Pod und kein Abräumen beim Herunterfahren — der Herzschlag deckt geordnetes Gehen, Absturz und Netzverlust gleich ab. |
| 2026-10-20 | **C3:** Master-Skill geteilt — Stand in `master_skill_stand` (Migration 0015, Laufzeit-Zustand, bewusst nicht in `config_areas`), Datenzugriff in `services/master_skill_stand.py`. Takt: liest die Zeile; abgefragt wird nur, wenn sie ≥ 0,8 Takt alt ist, und nur unter `sitzungssperre("__lauf:master-skill", warten_s=0)` (in der Sperre neu gelesen); sonst Zeile übernehmen. „Neu laden“ wartet bis 45 s auf die Sperre und teilt. Signal `__master_skill` auf `config_changed` (mit dem Commit); `ConfigStore._on_area_changed` reicht `__`-Nutzlasten nur an Abonnenten (kein Abruf), `master_skill.bei_signal` übernimmt. Frische Kopie liest vor dem ersten eigenen Abruf die Zeile. Alter von der DB gerechnet (keine Uhrenabweichung). Ohne Engine (Tests) unverändert prozesslokal. Tests: `test_master_skill_cluster.py` (8, pg) + 2 in `test_master_skill.py` (Signal-Wächter per Mutation geprüft). |
| 2026-10-20 | **C4:** Startwarnung bei `KUBERNETES_SERVICE_HOST` + `RATE_LIMIT_STORAGE_URI=memory://` (`test_ratelimit_warnung.py`, 3); die Env-Wächter nehmen die Plattform-Variable aus. **C5:** `reranker-model-*.tar.gz` in `.dockerignore` (77 MB weniger Build-Kontext). **C6:** `docs/cluster-checkliste.md` um die Zusagen 6–8 und „Was der Betrieb einstellen muss“ (Pool N×17, Gnadenfrist ≥ 65 s/70 s mit preStop, preStop 5 s, SSE ohne Pufferung, Lese-Timeout > 10 s, Rate-Limit geteilt); Pool-Rechnung in Values und Übergabe auf N×17 angeglichen (Bereitschaftsprobe zählt mit). Docstring „Neu laden“ → OpenAPI neu erzeugt. **Deploy braucht Migration 0014 + 0015.** Volle Suite vor C: 6516 grün. |
| 2026-10-20 | **Review Phase C** (frischer Prüfer, better-coding-review: 2 MAJOR, 4 MINOR, 1 NIT — alle am Quelltext bestätigt), behoben mit Tests rot zuerst: **1 (MAJOR)** eine frische Kopie, deren Takt-Abruf scheiterte, schrieb `text=NULL` in die Zeile, ihr Signal nahm allen Kopien die Anleitung → `_hole_und_teile` legt die unter der Sperre gelesene Zeile zuerst in den Speicher (gilt auch für „Neu laden“). **2 (MAJOR)** abgeräumter, aber lebender Läufer drehte `failed` zurück auf `completed`/`done` → `_persist` und `_finalize_run` schreiben nur noch auf `running`; der Lasttest-Sweep ist eine bedingte UPDATE-Anweisung (kein Fenster zwischen Lesen und Schreiben, danach `expire_all`). **3** Herzschlag-Test zahnlos → startet mit 1 h altem Schlag und prüft das Ende (Mutation: kein Schlag → rot, kein Abbruch → hängt). **4** Routertest für 409 aus `LastTestLaeuftSchon`. **5** Grenzen und erster Herzschlag nach der DB-Uhr (`now()`, `func.now()`). **6** 0014 schreibt einen Grund ins Ergebnis, Migrationstest 0013→head; Checkliste: Umstieg ohne laufende Läufe, Grenze der Zusagen 6/7. **7** Eval-Sweep setzt `completed_at`. |
| 2026-10-20 | **Gesamt-Review Paket 17** (drei frische Prüfer, better-coding-review, gegen den Diff zum Klon `5074445`: A+B 3 MINOR/1 NIT, C 2 MAJOR/4 MINOR/2 NIT, D 1 MAJOR/5 MINOR/2 NIT — jeder Befund am Quelltext geprüft), behoben mit Tests rot zuerst (`test_review_gesamt_d.py`, `test_laeufe_beenden.py`, Ergänzungen in `test_master_skill*.py`, `test_cluster_laeufe_pg.py`, `test_eval_*`, Strom-/Agent-/Sprach-/Lasttest-Tests; Studio-Spec). **D1 (MAJOR)** fest `forwarded_allow_ips="*"` machte `TRUST_FORWARDED_FOR=false` in Helm wirkungslos → Einstellung `FORWARDED_ALLOW_IPS` (Vorgabe `*` = Compose wie bisher; Values: Ingress-CIDR), Doku §5 berichtigt. **D2** HEALTHCHECK auf `/ready` (traefik routete vor dem Lifespan). **D3** Methoden-Label endlich (`OTHER`), 405 → `andere`. **D4** `proxy-body-size: 160m` + Rumpf-Grenzen in §4. **D5** `timeout_keep_alive=120` (über Ingress/traefik). **D6** `curl …/api/health` mit `X-Studio-Key` in README/INSTALL/Schnellstart; Plugin-Doku auf `/health`. **D7** Gnadenfrist 75 s, Test liest die Uvicorn-Frist aus `serve`. **D8** Hinweis Valkey-URI mit Passwort → secretEnv; NetworkPolicy-Empfehlung für 8101. **C1 (MAJOR)** Takt während „Neu laden“ ließ den alten Text teilen → `_hole_und_teile` teilt das Ergebnis des eigenen Abrufs (nie den Speicher). **C2 (MAJOR)** Herunterfahren mitten im Eval sammelte Verbindungsfehler → `_HauptServer.shutdown` ruft vor dem Schließen `services/laeufe_beenden.beende` (Zeilen der eigenen Läufe → `failed` „abgebrochen: Pod beendet“, Tasks abbrechen); die frühere Abweichung „kein Abräumen beim Herunterfahren“ ist damit zurückgenommen. **C3** Master-Skill-Abruf in leerem Kontext (nie mit der WLO-Anmeldung der Person). **C4** `_persist`/`_finalize_run` lesen gesperrt (`FOR UPDATE`) — kein deterministischer Test (das Fenster liegt innerhalb einer Funktion). **C5** synthetischer Verkehr in §6 benannt. **C6** belegte Sperre beim Neu-Laden → `last_error`. **C7** Signal-Übernahmen beim Herunterfahren beendet. **C8/AB4** Master-Skill aus den `B_API_KEY`-Rückfall-Listen (MCP-Aufruf). **AB1** `weg.route` in Vergleich (fehlender Schlüssel = alter Lauf, unbekannt), Bericht und Studio-Messbedingungen. **AB2** Grenze „beliebige Schlüssel direkter Aufrufer“ in architektur.md benannt (Abhilfe offen: gemeinsamer Client oder Schalter — Nutzer-Entscheid). **AB3** Ende-zu-Ende: Strom, beide Agent-Wege, Sprache ein/aus übernehmen den Schlüssel, ein Lasttest nie (Mutationsprobe: 5 rot). Offen außerhalb: Dev-DB steht vor 0014 (`alembic upgrade head` nötig). |
| 2026-10-20 | **AB2-Schalter (Nutzer-Entscheid):** `B_API_KEY_MODE` = `auto` (Vorgabe, auch leer/unbekannt: Kopf vor `B_API_KEY`) · `static` (Kopf zählt nicht, wie vor Paket 17) · `forward` (Zug ohne gültigen Kopf → 401 `WWW-Authenticate: Bearer`, nur bei `LLM_PROVIDER=b-api-*`; `/api/speech/status` ausgenommen; Hintergrundläufe immer `B_API_KEY`). `settings.b_api_key_mode` (Validator wie `log_format`), `api/turn_auth.uebernimm_llm_schluessel(pflicht=)`, Startwarnung bei `forward` ohne b-api; `.env.example`, Compose, Helm-Werte. Tests rot zuerst (`test_llm_auth.py`: 10 neu). **Dev-DB** `boerdi` 0011 → 0015 + `import-config --werksabgleich` (2 aktualisiert, 3 angepasste mit neuer Werksfassung; Sicherung nach der Migration im Scratchpad — die Sicherung davor scheiterte an der Pfadumschreibung von Git Bash, die Migration lief trotzdem; 0014 änderte keine Zeile). **Testcontainer** `boerdi-chat-test`: Image `edu-chatbot-sc:paket17-lokal` aus dem Staging-Baum, DB `boerdi_test` 0013 → 0015 + Werksabgleich (Sicherung davor), neu gestartet mit 8180→8100, 8181→8101, `FORWARDED_ALLOW_IPS=127.0.0.1`; Prüfung: `/health` 200, `/api/health` 401 ohne / 200 mit Schlüssel, `/metrics` 404 öffentlich / 200 intern, öffentliche Spec 9 Operationen, `healthy` über `/ready`, Chat-Smoke beantwortet. **Doku:** README (Betrieb in Kürze, Übergabe/Cluster verlinkt), INSTALL (Abnahme `/ready`), `deploy/README.md` („Welche Proxys Uvicorn glaubt“ mit Tabelle compose/Kubernetes/Testbetrieb, `docker run`- und Compose-Beispiel, `B_API_KEY_MODE`, Migration 0015, Logs/Metriken), Architektur §3/§4.8/§5.6/§8, Übergabe §5/§11, `offene-befunde-und-todo.md`. |
| 2026-10-20 | **Review-Runde 3** (frischer Prüfer, better-coding-review, über Gesamt-Review-Fixes + AB2: 1 MAJOR, 5 MINOR, 4 NIT — alle am Quelltext bestätigt), behoben mit Tests rot zuerst (`test_review_runde3.py`, 21): **1 (MAJOR)** unter `forward` scheiterten Evaluation, Lasttest und Studio-Proben an 401 (kein Proxy-Kopf) → Züge der Anlage selbst sind frei (`turn_auth._interner_zug`: Studio-Proxy oder gültiger `X-Studio-Key`, zeitkonstant verglichen) und nehmen `B_API_KEY`; der Lasttest schickt den Schlüssel im Prozess, der Eval-Runner nur an Loopback (`runner._interne_koepfe`); Schlüssel-Ableitung nach `settings.studio_schluessel` (Dienste hängen nicht an `api/deps`). Mutationsprobe: ohne Ausnahme 3 rot. **2** älterer geteilter Stand überschrieb einen neueren (Takt las vor dem Signal) → Stände tragen `geprueft_um` (DB-Uhr, `schreibe` gibt ihn zurück), `_uebernimm` verwirft ältere. **3** Gnadenfrist ohne den 5-s-Abschluss → Compose 70 s, Helm 80 s, drei Tests rechnen `laeufe_beenden._FRIST_S` ein, Doku. **4** vertippter Modus → Startwarnung (es gilt `auto`). **5** forward über alle sechs Zug-Wege (401 + `WWW-Authenticate`, kein Zug) und Schlüssel-Übernahme je Weg. **6** Doku: interne Züge, „forward verlangt, prüft nicht“, nur `static` begrenzt Clients. **7** Verdrahtungstest prüft den echten Abschluss-Aufruf. **8** static meldet auch einen kaputten Kopf nicht. **9** Lebenszyklus löst den Master-Skill vor dem Beenden der Übernahmen. **10** Dockerfile-Kommentar `FORWARDED_ALLOW_IPS`. |
