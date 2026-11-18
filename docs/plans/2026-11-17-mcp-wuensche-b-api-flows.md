# Plan für den MCP: Kestra-Flows über den Repository-Proxy (2026-11-17, Stand 18.11.)

An: Entwickler `wlo-mcp-server`. Von: Chatbot (boerdi-chat). Gegenstück im Chatbot:
`docs/plans/2026-11-17-b-api-delegation-und-upload.md` (dort Paket K, das diese Werkzeuge nutzt).
Alles hier ist so geschrieben, dass es ohne Vorwissen zu Kestra baubar ist; Reihenfolge und Abnahme
in §7, Quellen am Ende.

## 1 Warum der MCP

- Seit dem 10.11. nimmt die b-api (Bildungs-API) eine Person nur an, wenn das **Repository** für sie
  bürgt. Das geht nur über den Proxy des Repositorys: `{WLO_REPOSITORY_URL}/rest/bapi/**`
  (BApiProxyService). Er entfernt `x-edu-*`/`x-api-key` des Aufrufers, setzt seinen eigenen Schlüssel
  und eine signierte Assertion (30 s, an Methode, Pfad und Schlüssel gebunden). `X-Edu-User-Id`
  ist abgeschafft (403 `LEGACY_HEADERS`), ohne Person kommt 400 `EDU_USER_REQUIRED`.
- Der Chatbot bekommt hinter dem b-api-Proxy nur ein Delegations-Token (`bdt_…`): LLM und Lesen,
  **keine Jobs**.
- Die Repository-Anmeldung der Person liegt nach unserer Kette (Widget → Chatbot-Backend → MCP)
  **beim MCP** (Sitzung `EDU-SESSION`, Ticket oder Basic je Anfrage; `auth/credential.ts`,
  `auth/upstream-auth.ts`). Also startet der MCP. Der Chatbot entscheidet weiter, **wann** und
  **welcher** Flow läuft, und holt die Freigabe der Person ein.

Belegt ist der Weg schon: Die Beispielseite des Flows (`flow-start`) startet ihn genau so —
`POST /edu-sharing/rest/bapi/api/v1/jobs/flows/edusharing.chatbot/node-metadata-write` mit dem
Sitzungs-Cookie der Person, ohne eigenen Schlüssel.

## 2 Was Kestra hier ist (Kurzwissen)

- **Kestra** ist eine Workflow-Engine. Ein **Flow** hat einen Namen `namespace/id`, Eingaben (Inputs)
  und läuft als **Job** (Ausführung) asynchron, Sekunden bis Minuten.
- Die b-api kapselt Kestra unter `/api/v1/jobs/**`. Wir sprechen nur diese Schnittstelle, nie Kestra
  direkt. Welche Flows es gibt, legt die b-api fest (Freigabe je Schlüssel).
- Beim Start über `/rest/bapi/**` **friert die b-api die Person ein** und gibt dem Job ein eigenes
  Token (`bapi_token`). Der Flow ruft damit selbst die b-api und das Repository — mit den Rechten der
  Person. Der MCP muss dafür nichts mitschicken.

### Der Flow `edusharing.chatbot/node-metadata-write`

- **Eingabe:** `{"node_ids": ["<nodeId>", …], "language": "de"}`. nodeIds von `ccm:io`, die die
  Person gerade angelegt hat (bei uns: aus `wlo_store_batch_file`).
- **Was er tut, je Node:** holt den Volltext beim Repository (Text-Endpunkt, GET), erzeugt Metadaten
  mit dem Metadaten-Agenten der b-api und **schreibt sie überschreibend in den Node**: Titel,
  Beschreibung, Schlagworte, Sprache, Fach (taxon id), Bildungsstufe, Zielgruppe, Ressourcentyp.
- **Ergebnis:** bei `SUCCEEDED` unter `outputs.report` ein Bericht je Node. Schreibt er keinen Node,
  endet er mit `FAILED`.
- **Grenze bei uns:** höchstens 50 nodeIds je Job; der Chatbot teilt größere Mengen auf und startet
  die Teile nacheinander.
- Wichtig für die Vorschau: **überschreibt** vorhandene Metadaten — darum nur für frisch abgelegte
  Dateien und nur nach Freigabe.

## 3 Die Job-Schnittstelle der b-api (gemessen am Staging, B-API-Handbuch 2026-11-07)

Alle Pfade hinter `{WLO_REPOSITORY_URL}/rest/bapi` (über den Repository-Proxy):

| Zweck | Anfrage | Antwort |
|---|---|---|
| Flows auflisten | `GET /api/v1/jobs/flows` | Liste der freigegebenen Flows |
| Starten | `POST /api/v1/jobs/flows/{namespace}/{id}`, Body = Inputs als JSON | **202** `{"jobId": "…"}` |
| Stand | `GET /api/v1/jobs/{jobId}?details=true` | `{"status": …, "outputs": {…}, "files": [...], "warnings": bool, "error": {"code": …}}` |
| Abbrechen | `DELETE /api/v1/jobs/{jobId}` | 200/202/204 abgebrochen, **409** schon fertig, 404 fremd/unbekannt |
| Ergebnisdatei | `GET /api/v1/jobs/{jobId}/files/{outputId}` | Bytes; 404 unbekannt, **410** gelöscht (nach 7 Tagen) |

- **`status`:** laufend `QUEUED`, `RUNNING` (auch `CREATED`, `PAUSED`, `RESTARTED`, `RETRYING`);
  fertig `SUCCEEDED` (auch `SUCCESS`, `WARNING`); gescheitert `FAILED`, `CANCELLED`, `KILLED`.
  `outputs` gibt es erst bei `SUCCEEDED`. `error.code` dokumentiert ist nur `TIMEOUT`.
- **`files[]`:** `{name, size, outputId, available, reason}`. Bitte **nie** `downloadUrl` weitergeben
  oder folgen (öffnet mit der Anmeldung); Datei nur über den Pfad oben, ohne Redirects folgen.
- **Fehler:** 400 Eingaben passen nicht zum Flow **oder** `EDU_USER_REQUIRED`; 401/403 abgewiesen
  (`error.code`/`code`, z. B. `LEGACY_HEADERS`, `EDU_USER_NOT_VERIFIED`); 404 unbekannt;
  **429** mit `Retry-After` (Sekunden) — höchstens **20 unfertige Jobs je Schlüssel**.
- **Aufbewahrung:** Jobs 30 Tage, Dateien 7 Tage.
- **Multipart:** Die Beispielseite sah am Repository-Proxy 415; das Hochladen bleibt darum wie heute
  direkt am Repository (`wlo_store_batch_file`). Flows mit FILE-Inputs (Multipart, 50 MB je Datei,
  10 Dateien) sind ein späterer Kandidat, nicht Teil dieser Wünsche.
- **Fortschritt:** Bei Flows mit Schleifen liefert der Stand `progress` (started, running, succeeded,
  warning, failed), mit `?details=true` zusätzlich `iterations` (je Iteration Index, Status,
  `error.code`, höchstens 200). `warnings: true` heißt: Job gelungen, einzelne Iterationen nicht.
- **Laufzeit:** Label `bapi.maxRuntime` am Flow (Vorgabe 24 h); danach `FAILED` mit `error.code`
  `TIMEOUT`.

## 4 Wünsche

**W0 — zuerst messen** (nur lesend, Testkonto auf Staging, mit dessen Sitzung):
1. `GET {repo}/rest/bapi/api/v1/llm/openai/models` → 200? (Proxy überhaupt erreichbar)
2. `GET {repo}/rest/bapi/api/v1/jobs/flows` → 200 und enthält `edusharing.chatbot/node-metadata-write`?
3. `GET {repo}/rest/bapi/api/v1/jobs/<unbekannte-id>` → 404 (nicht 400/401)?

**Gemessen vom Chatbot-Team am 18.11.** (Testkonto, Staging, nur lesend; Anmeldung mit Basic an
`/rest/authentication/v1/validateSession`, danach nur das Sitzungs-Cookie `JSESSIONID`/`INGRESSCOOKIE`,
kein Schlüssel, kein `X-API-KEY`):

| Aufruf über `/rest/bapi` | Status |
|---|---|
| `GET /api/v1/llm/openai/models` | 200 |
| `GET /api/v1/jobs/flows` | **200**, Liste mit `edusharing.chatbot/node-metadata-write` |
| `GET /api/v1/jobs` | 200 (`items`, `page`, `size`, `total`) |
| `GET /api/v1/jobs/<unbekannt>` | 404 `{"error": "Job not found"}` |

Der Weg trägt also. Bitte nach dem Bau dieselben Aufrufe mit der Sitzung aus dem Zugangsblock
wiederholen (statt Basic). Vorlage für eigene Proben: das Python-Skript des b-api-Teams
`bapi_proxy_test.py` (validateSession → Cookie → `/rest/bapi/…`).

**W1 — Proxy-Client `bapiFetch(method, path, body?)`.**
- URL `{restBase}/bapi{path}`; Anmeldung wie bei jedem Repository-Aufruf über `applyUpstreamAuth`
  (Cookie/Ticket/Basic der Anfrage, `DisableGuest: true`). Da die URL unter `WLO_REPOSITORY_URL`
  liegt, sollte `isRepositoryUrl` greifen — bitte prüfen, dass **nur** die persönliche Anmeldung
  mitgeht.
- **Nie** mit Dienstkonto oder anonym (sonst 400 `EDU_USER_REQUIRED`): ohne persönliche Anmeldung
  sofort `login_required`.
- Gemessen ist der Weg mit Sitzungs-Cookie. Ob Ticket- (`EDU-TICKET`) und Basic-Anmeldungen am
  Proxy ebenso gelten, bitte beim Bau prüfen; gilt eine Art nicht, für sie `login_required`.
- Nur Pfade aus einer festen Liste im Code: Präfix `/api/v1/jobs/` und — nur mit W7 —
  `/api/v1/proxy/text-extraction/`. Kein `x-api-key`, keine `x-edu-*`.
- Ein Schalter: `WLO_BAPI_VIA_REPOSITORY=true`. Ohne ihn gibt es die Werkzeuge W2–W6 nicht
  (nicht registriert) und W7 bleibt beim heutigen Weg — heutiger Betrieb unverändert.
- Frist 30 s je Aufruf; 429 mit `Retry-After` durchreichen.

**W2 — `wlo_start_flow`** (schreibend, `registerCurationTool`, nur persönliche Anmeldung):

```ts
inputSchema: {
  flow: z.string().regex(/^[a-z0-9_.-]+\/[a-z0-9_.-]+$/i),    // "edusharing.chatbot/node-metadata-write"
  inputs: z.record(z.unknown()),                                // Body; JSON höchstens 64 KB
  confirm: z.string().optional(),                               // wie bei euren übrigen Schreibwerkzeugen
}
// Ausgabe (structuredContent):
{ status: 'preview', confirm: { token, expiresAt, preview } }   // ohne confirm
{ status: 'started', jobId: string, flow: string }              // mit gültigem confirm
{ status: 'failed', reason: 'not_allowed' | 'login_required' | 'edu_user_required'
                   | 'rejected' | 'bad_inputs' | 'rate_limited', retryAfter?: number, code?: string }
```

- Nur Flows aus `WLO_BAPI_FLOWS` (kommagetrennt, Vorgabe leer = keiner). `not_allowed` sonst.
- Für `node-metadata-write`: `inputs.node_ids` ist eine Liste von 1–50 nodeIds; jede muss für die
  Person **schreibbar** sein (vorher prüfen, sonst `bad_inputs` mit den betroffenen IDs). Die
  Vorschau nennt die Anzahl, die Titel und den Satz „überschreibt Titel, Beschreibung, Schlagworte,
  Fach, Bildungsstufe, Zielgruppe, Ressourcentyp und Sprache dieser Materialien“.
- Andere Flows: Vorschau mit Flow-Name und Inputs (gekürzt).

**W3 — `wlo_flow_status`** (lesend, persönlich): Eingabe `jobId`; Ausgabe
`{ status: 'running'|'succeeded'|'failed'|'cancelled', rawStatus, errorCode?, warnings?,
progress?: {started, running, succeeded, warning, failed}, outputs? (≤ 1 MB, sonst weggelassen mit
truncated: true), files?: [{outputId, name, size, available}] }`. `progress` gibt die b-api bei
Flows mit Schleifen (eine Iteration je Node) — der Chatbot zeigt daraus „k von n fertig“.
`iterations` aus `?details=true` bitte nur als Zahlen je Status weitergeben, keine Werte.
Mapping wie in §3. Ein fremder Job ergibt 404 → `{status: 'failed', reason: 'unknown_job'}`.

**W4 — `wlo_cancel_flow`** (schreibend, persönlich, ohne Bestätigung — nur eigener Job): Eingabe
`jobId`; Ausgabe `{status: 'cancelled' | 'already_finished' | 'unknown_job'}`.

**W5 — optional `wlo_flow_file`** (lesend): Eingabe `jobId`, `outputId`, `maxBytes` (≤ 2 MB); Ausgabe
der Inhalt als Text (UTF-8) oder `{status: 'too_large'|'gone'|'unknown'}`. Ohne Redirects, ohne
komprimierte Antworten.

**W6 — optional `wlo_list_flows`** (lesend): `GET /api/v1/jobs/flows`, geschnitten mit
`WLO_BAPI_FLOWS` — für die Flow-Auswahl im Studio des Chatbots.

**W7 — optional Textextraktion** über `/rest/bapi/api/v1/proxy/text-extraction/…`, wenn eine Person
angemeldet ist; sonst wie heute mit `X-API-KEY`.

## 5 Rahmen

- Heutiger Betrieb ohne b-api bleibt unverändert; ohne `WLO_BAPI_VIA_REPOSITORY` keine neuen Werkzeuge.
- Kein Wert der Anmeldung und keine Job-Ausgaben in Logs; Job-Daten nie in geteilte Caches.
- Der Chatbot erkennt die Werkzeuge über `tools/list` und benutzt sie nur, wenn alle drei
  (`wlo_start_flow`, `wlo_flow_status`, `wlo_cancel_flow`) da sind.
- Tests gegen die Drahtform aus §3 (202/`jobId`, Status-Mapping, 404/409/410/429, `Retry-After`).
- Der Chatbot fragt den Stand nur im Zug der Person ab („Stand prüfen“ bzw. beim nächsten Zug);
  einen Wächter im Hintergrund braucht es nicht.

## 6 Für den Autor des Flows `node-metadata-write`

Nach der Jobs-Doku der b-api (18.11.):

```yaml
labels:
  bapi.expose: "true"
  bapi.scopes: "edu-sharing-repo,edu-sharing-repo-write,llm"   # lesen, Metadaten schreiben, Agent
  bapi.maxRuntime: "PT30M"
inputs:
  - id: bapi_token        # füllt die b-api je Job, Typ SECRET ist Pflicht
    type: SECRET
  - id: node_ids          # …
```

Im Flow nur `Authorization: Bearer {{ inputs.bapi_token }}`, keine Personen-Header. Die Person ist
die beim Start (über `/rest/bapi/**`) eingefrorene; Schreiben geht über `PATCH
…/edu-sharing/repo/nodes/{id}/metadata`. Der b-api-Schlüssel des **Repositorys** braucht die Rolle
`JOBS` und die Rechte `EDU_SHARING_REPO_READ` und `EDU_SHARING_REPO_WRITE` (b-api-Admin). Warum ein
Flow nicht angeboten wird, zeigt die b-api auf der Seite „Flows“ unter „Letzter Sync“.

## 7 Reihenfolge, Tests, Abnahme

| Schritt | Inhalt | Fertig, wenn |
|---|---|---|
| 1 | W1 Proxy-Client + Schalter | Unit-Tests: nur persönliche Anmeldung geht mit, Dienstkonto/anonym → `login_required`, fremder Pfad abgewiesen, keine `x-api-key`/`x-edu-*`; ohne Schalter nichts registriert |
| 2 | W3 Stand, W4 Abbruch | Tests gegen die Drahtform aus §3 (Status-Mapping, `progress`, 404/409, 429 mit `Retry-After`) |
| 3 | W2 Start mit Vorschau/Bestätigung | Tests: Freigabeliste, 1–50 nodeIds, Schreibrecht je Node, Vorschautext, 202 → `jobId`, 400 `EDU_USER_REQUIRED` → `edu_user_required` |
| 4 | Probe auf Staging | Mit Testkonto und Sitzung aus dem Zugangsblock: W0-Aufrufe über `bapiFetch` grün; dann **ein** Start von `node-metadata-write` für einen eigenen Test-Knoten (Präfix `boerdi-durchtest-`, danach löschen) → `SUCCEEDED`, Metadaten am Knoten geändert |
| 5 | optional W5–W7 | je eigene Tests |
| 6 | Bereitstellen | Schalter und `WLO_BAPI_FLOWS=edusharing.chatbot/node-metadata-write` auf Staging gesetzt; Rückmeldung an das Chatbot-Team mit Commit und Werkzeugschemas |

Danach baut das Chatbot-Team Paket K (Start, Stand, Abbruch über diese Werkzeuge) und testet die
ganze Kette: Upload → Ablage → Flow → Metadaten lesen → Themenbaum.

## Quellen

- b-api-Entwickler, „(Update) B-API Personen-Nachweis bei Delegation“ (17.11.)
- Chatbot-Client `boerdi-chat/backend/src/boerdi/services/auftraege/client.py` (Drahtform, gemessen)
- `boerdi-chat/docs/plans/2026-11-10-themenbaum-aus-inhalten.md` §2 (Beispielseite `flow-start`)
- MCP-Entwurf `wlo-mcp-server-sc/docs/plans/2026-11-15-b-api-betrieb.md`
