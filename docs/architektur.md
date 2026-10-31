# Architektur

Technische Übersicht über boerdi-chat: welche Bestandteile es gibt, womit sie
gebaut sind, wie sie zusammenarbeiten und wie ein Ablauf von der Eingabe bis zur
Antwort durchläuft.

Zielgruppe sind Entwicklerinnen und Entwickler, die das Gesamtbild brauchen —
zum Mitarbeiten, zum Betreiben oder zum Bewerten. Alle Zahlen und Wege sind am
Quelltext erhoben; Fundstellen stehen in Klammern.

| Vertiefung | Dokument |
|---|---|
| Installation auf einem Server | [`../INSTALL.md`](../INSTALL.md) |
| Betrieb, Skalieren, Backup, Rollback | [`../deploy/README.md`](../deploy/README.md) |
| Bauplan/Spezifikation (Quelle der Wahrheit) | [`plans/2026-07-10-boerdi-chat-neubau.md`](plans/2026-07-10-boerdi-chat-neubau.md) |
| Widget in fremde Seiten einbetten | [`browser-plugin-einbindung.md`](browser-plugin-einbindung.md) · [`edu-sharing-einbindung.md`](edu-sharing-einbindung.md) |
| Agent-Schleife | [`agent-modus.md`](agent-modus.md) |
| Interaktive Grafiken: Gesamtbild, Software-Stack, Abläufe und Konfiguration je Modus | [Bilder (PNG)](architektur-grafiken/png/) · [Übersicht und Quellen](architektur-grafiken/README.md) |
| Master-Skill (Vorgehen, Zielgruppen, Suchdisziplin, 30 Anwendungsfälle) | [`skills/vorgehen.md`](skills/vorgehen.md) |
| Eingefrorener HTTP-Vertrag | [`api/openapi-v1.json`](api/openapi-v1.json) |

---

## 1. Was das System ist

Ein Chatbot für **WirLernenOnline (WLO)**, der Lehrende und Lernende zu offenen
Bildungsmaterialien führt. Er sucht nicht in einer eigenen Datenbank, sondern
spricht über einen **MCP-Server** mit dem edu-sharing-Repositorium — und ergänzt
das um eigenes Redaktionswissen (RAG) und eine redaktionell gepflegte
Gesprächsführung.

Drei Bestandteile, ein Auslieferungsartefakt:

```
                    ┌──────────────────────────────────────────┐
   Gastseite ──────▶│  WIDGET  <boerdi-chat>                   │
   (WLO, edu-       │  Angular 22 Custom Element, Shadow DOM   │
    sharing, CMS,   │  eine JS-Datei, ~525 KB                  │
    Browser-Plugin) └────────────────┬─────────────────────────┘
                                     │  HTTPS  /api/chat[/stream], /api/agent
                                     ▼
   Redaktion ──────▶┌──────────────────────────────────────────┐
   (Studio-Login)   │  BACKEND                                 │
                    │  FastAPI + LangGraph, Python 3.12        │
                    │  ├── Zug-Graph (13 Knoten)               │
                    │  ├── Muster │ Agent                      │
                    │  ├── MCP-Client · RAG · Safety           │
                    │  └── Config-Store (36 Bereiche)          │
                    └──┬────────┬─────────┬────────────┬───────┘
                       │        │         │            │
                       ▼        ▼         ▼            ▼
                  Postgres17  Valkey   LLM-Provider  MCP-Server
                  +pgvector  (Limits)  (B-API/LiteLLM) (WLO/edu-sharing)
                                     ▲
                    ┌────────────────┴─────────────────────────┐
                    │  STUDIO  /studio                         │
                    │  Angular 22 SPA, statisch aus demselben  │
                    │  Image, BFF-Proxy /studio/api/* → /api/* │
                    └──────────────────────────────────────────┘
```

**Die tragende Idee:** fast alles Verhalten ist **Konfiguration in der
Datenbank**, nicht Code. Muster, Personas, Intents, Zustände, Tonfall,
Sicherheitsregeln, Begrüßung, Anzeige-Regeln — 36 Bereiche, im Studio pflegbar,
**ohne Neustart wirksam**. Der Code ist die Maschine; was sie sagt und wann,
steht daneben.

---

## 2. Software-Stack

### Backend (`backend/`)

| Aufgabe | Wahl | Anmerkung |
|---|---|---|
| Sprache | **Python ≥ 3.12** | |
| Web | **FastAPI** + uvicorn | 21 Router, OpenAPI eingefroren |
| Zug-Orchestrierung | **LangGraph** `StateGraph` | ohne Checkpointer (§4.2) |
| Datenbank | **Postgres 17 + pgvector** | über SQLAlchemy 2 (async) + asyncpg |
| Migrationen | **Alembic** | |
| LLM-Transport | **LiteLLM** | ein Aufruf, viele Anbieter |
| Strukturierte Ausgabe | **instructor** (`Mode.TOOLS`) | Klassifikation als getyptes Objekt |
| Werkzeuge | **MCP-SDK** (`mcp`) | Streamable HTTP zum WLO-Server |
| Drosselung | **slowapi** + `limits` | Zähler in **Valkey** |
| Reranking / lokale Embeddings | **onnxruntime** + `tokenizers` + `numpy` | CPU, kein Torch |
| Dokument-Konvertierung | **markitdown** | RAG-Ingest |
| Beobachtbarkeit | **OpenTelemetry** → Jaeger | FastAPI, HTTPX, SQLAlchemy instrumentiert |
| Konfiguration | **pydantic-settings** | 74 Felder (Stand 2026-10-03) |
| Tests / Lint | **pytest** (285 Dateien, Stand 2026-10-03) · **ruff** | |

### Widget (`frontend/projects/widget` + `ui`)

| Aufgabe | Wahl |
|---|---|
| Framework | **Angular 22**, standalone, **signals**, zoneless |
| Auslieferungsform | **Custom Element** via `@angular/elements`, **Shadow DOM** |
| Gestaltung | **Angular Material 3**, Theme an `:host` (nicht `:root`) |
| Markdown | `marked` + **DOMPurify** |
| Transport | `fetch` + **SSE**, Fallback auf POST |
| Sprache | TypeScript 6 |
| Tests | **Vitest** (Unit) · **Playwright** (E2E) |

### Studio (`frontend/projects/studio`)

Dieselbe Angular-22-Basis, eigene SPA. Formulare entstehen **aus den
Bereichs-Schemata** (`schema-form/`), nicht handgeschrieben — ein neues Feld im
Pydantic-Modell erscheint im Studio, ohne dass jemand ein Formular pflegt.

### Geteilte Bibliothek (`frontend/projects/ui`)

Alles, was Widget und Studio teilen könnten, und alles, was das Widget
ausmacht: Karten, Chips, Chat-Shell, Controller, Stream-Client, Seitenkontext,
Host-Ereignisse, Sitzung/Anmeldung, i18n, Theme, Sprachausgabe.

---

## 3. Auslieferung

**Ein Docker-Image für alles.** Der Build ist dreistufig
(`Dockerfile:25,40,61`):

1. `node:22-slim` — baut **Widget** und **Studio** (`npm run build:widget`,
   `build:studio`).
2. `python:3.12-slim` + `uv` — löst die Python-Abhängigkeiten in ein `.venv`.
3. `python:3.12-slim` — Laufzeit; kopiert `.venv`, das Widget-Bündel nach
   `widget_dist/` und die Studio-SPA nach `studio_dist/`.

Das eine Bild bedient damit drei Oberflächen:

| Pfad | Was |
|---|---|
| `/api/*` | die HTTP-Fläche (Chat, Agent, Config, RAG, Eval …) |
| `/widget/boerdi-widget.js` | das Widget-Bündel (302 → gehashte URL, `ACAO: *`) |
| `/studio` | die Studio-SPA (StaticFiles mit SPA-Fallback) |
| `/studio/api/*` | BFF — Pfad-Umschrift nach `/api/*` (§7) |

**Zwei Ports in einem Prozess (Paket 17).** Der Container startet `python -m boerdi.serve`:
8100 trägt die Tabelle oben samt einer reduzierten `/openapi.json` (die öffentliche
Chat-API), 8101 ist intern — `/health` (Liveness), `/ready` (Start fertig, Postgres
antwortet, kein Herunterfahren), `/metrics` (Prometheus), `/openapi-full.json`. Nur der
Hauptserver führt die Signale; zu Beginn seines Herunterfahrens schließt er die Lasttest- und
Eval-Läufe dieses Pods (`services/laeufe_beenden`). Wessen `X-Forwarded-*` er glaubt, sagt
`FORWARDED_ALLOW_IPS` (Vorgabe `*`; Tabelle in `deploy/README.md`).

### Produktions-Topologie (`deploy/compose.prod.yml`)

```
        Internet
           │  443
      ┌────▼─────┐
      │ traefik  │  v3.6, TLS, einziger veröffentlichter Port
      └────┬─────┘
           │
     ┌─────▼──────┐   replicas: BACKEND_REPLICAS (Vorgabe 1)
     │  backend   │◀── zustandslos: Sitzung + Config in Postgres,
     └──┬───┬───┬─┘    Sperre je Sitzung in Postgres über alle Repliken (§8)
        │   │   └──────────────▶ jaeger 2.19
        │   └──────▶ valkey 8   (Drossel-Zähler)
        ▼
   postgres 17 + pgvector
        ▲
   migrate (einmalig): alembic upgrade head && boerdi import-config --werksabgleich
```

Der `migrate`-Dienst ist **idempotent**: `--werksabgleich` legt an, was fehlt, hebt
unberührte Bereiche auf eine neue Werksfassung und rührt Gepflegtes nicht an — sonst
drehte jeder Neustart die redaktionelle Arbeit auf den Auslieferungsstand zurück.
Je Bereich merkt sich die Datenbank, auf welcher Werksfassung er steht (`werk_hash`),
und eine stillgelegte eigene Fassung (`eigene_fassung`); Status und Regeln stehen in
`services/werkfassung.py` (Paket 12).

---

## 4. Backend

### 4.1 Schichten und Abhängigkeitsrichtung

```
api/        HTTP-Grenze: Router, Schemata, Auth, Drossel, SSE
  │
graph/      der Zug: StateGraph + 13 Knoten + TurnContext
  │
services/   alles mit Außenwelt: LLM, MCP, RAG, DB, Config, Safety   (66 Module)
  │
domain/     framework-freie Logik: Muster, Policy, Karten, Zustände  (35 Module)
  │
db/ obs/ i18n/   Fundament: Modelle, Sitzung, Sperren, NOTIFY, Traces, Sprache
```

Abhängigkeiten zeigen **nach innen**. `domain/` importiert kein FastAPI, keine
DB-Sitzung, kein LLM — nur die Lese-Fassaden der Konfiguration. Das ist der
Grund, warum die Entscheidungslogik ohne Server testbar ist.

Zwei Konventionen, die man beim Lesen sofort bemerkt: **≈300 Zeilen je Datei**
(Ausnahmen sind im Kopf der Datei begründet) und **Deutsch für Inhalte,
Englisch für Bezeichner**.

### 4.2 Der Zug — ein Chat-Turn als Graph

`graph/build.py` setzt 13 Knoten zu einem `StateGraph` zusammen. Zustand ist ein
`TurnContext` (`graph/state.py`), der von Knoten zu Knoten wächst.

```
START → setup → tour ──early?──▶ END
                 └─▶ page_context_enrich → context_greeting ──early?──▶ END
                        └─▶ persist_user → preflight ──early?──▶ END
                               └─▶ assess → safety_log → merge → route
                                      → respond → assemble → persist → END
```

| Knoten | Aufgabe |
|---|---|
| `setup` | Sitzung + `session_state` laden, Zug-Rahmen bauen |
| `tour` | Webseiten-Tour (eigene Zustandsmaschine) — **kann früh enden** |
| `page_context_enrich` | Seiten-IDs einsetzen, Metadaten am MCP auflösen (best effort), bei Sammlung/Themenseite zusätzlich Bestandszahlen + Skill-Übersicht |
| `context_greeting` | Kontext-Begrüßung beim Öffnen — **kann früh enden** |
| `persist_user` † | Nutzer-Nachricht speichern |
| `preflight` | Sicherheits-Vorprüfung + **Direkt-Aktionen** (Sammlung öffnen, Lernpfad, Volltext) — **kann früh enden** |
| `assess` | **Klassifikation**: Persona, Intent, Signale, Entitäten, Folgezustand |
| `safety_log` † | Zug-Protokoll, konfig-gesteuert |
| `merge` | Entitäten des Zuges mit dem Gedächtnis verschmelzen |
| `route` | **Entscheidungskern**: Muster wählen, Policy anwenden, Schnellpfade |
| `respond` | Antwort erzeugen — Muster-Engine **oder** Agent-Schleife |
| `assemble` | Karten, Inline-Dokumente, Quick-Replies, Links zusammensetzen |
| `persist` | Zustand + Nachricht + Kennzahlen schreiben |

† Beide sind vollwertige Graph-Knoten; nur ihre Rümpfe stehen in `build.py`
statt in `graph/nodes/` — es sind reine Zug-Sequenz-Seiteneffekte, die erst
zwischen den großen Knoten Sinn ergeben.

Nur `tour`, `context_greeting` und `preflight` brechen ab. Die Schnellpfade für
Lernpfad und Canvas tun das **nicht**: `route` hinterlässt Marker, die `respond`
aufgreift — die Kette läuft trotzdem bis `persist` durch, damit Zusammenbau und
Speichern an genau einer Stelle stehen.

**Ohne Checkpointer kompiliert.** Der Zug-Zustand liegt in eigenen Tabellen
(`setup` liest, `persist` schreibt); ein LangGraph-Checkpointer wäre eine zweite
Buchführung und brächte nur Unterbrechen/Fortsetzen — was ein Zug, der bis zum
Ende läuft, nicht braucht.

**Alles ist anfrage-gebunden.** DB-Sitzung, echte Peer-IP und der Token-Haken
fürs Streaming werden je Anfrage per `functools.partial` gebunden. Es gibt keine
modul-globale Engine.

### 4.3 Zwei Maschinen im `respond`-Knoten

| | **Muster-Engine** (Vorgabe) | **Agent-Schleife** |
|---|---|---|
| Modul | `respond.py` → `tool_loop.py` | `respond_agent.py` → `agent_loop.py` |
| Klassifikator | ja (größter Prompt des Zuges) | nein |
| Werkzeugwahl | pro Muster gebunden (`response_tool_selection`) | voller Katalog |
| Vorabruf | über Intent (`prefetch.py`) | — |
| Ende | eine Antwort | `submit_result`, Prosa oder Deckel |
| Deckel | Muster-Grenzen | `max_iterations`, `deadline_s`, `token_budget` |

Eine dritte Maschine, den **Hybrid** (die Schleife mit dem Musterkatalog als
Werkzeug `waehle_vorgehen`), gibt es seit K1-1 (2026-09-27) nicht mehr: die
K0-Messung zeigte ihn zwischen den beiden anderen, ohne eigenen Mehrwert.
`hybrid` aus Attribut, Kopfzeile oder gespeicherter Vorgabe gilt als `agent`.

Gewählt wird in `engine_choice.py` — Studio-Vorgabe (`01-base/engine`),
überschreibbar je Einbau (Attribut `engine`) und je Anfrage (Kopfzeile
`X-Boerdi-Engine`).

Die Agent-Schleife hat außerdem einen **eigenen Endpunkt** `POST /api/agent` für
Gastgeber ohne Chat-Rahmen: Anweisung rein, Text **plus JSON nach eigenem
Schema** raus. Das ist der einzige Weg zu strukturierter Ausgabe — ein Chat-Zug
liefert Text, Karten und Quick-Replies, kein Ergebnisobjekt.

### 4.4 MCP-Anbindung (`services/mcp/`)

Der Zugang zum WLO-Bestand. Kein eigener Index, keine Kopie des Repositoriums.

| Modul | Aufgabe |
|---|---|
| `transport.py` | MCP-SDK, Streamable HTTP |
| `client.py` | `call_mcp_tool` — der eine Aufrufweg, mit Zug-Sammlern |
| `tool_defs.py` / `tool_defs_curation.py` | Werkzeugliste fürs LLM |
| `fremdwerkzeuge.py` | Werkzeuge **weiterer** MCP-Server, nur lesend, im Zug `server__werkzeug` (Paket 11) — eigener Aufrufweg, nie mit dem Block der WLO-Anmeldung |
| `tool_args.py` | Argument-Prüfung (Pydantic) vor dem Absetzen |
| `arg_resolvers.py` | Platzhalter aus dem Zug-Zustand auflösen |
| `tool_cache.py` | Ergebnis-Zwischenspeicher je Zug |
| `parsers/` | Antworten lesen: Karten, Themenseiten, Skill-Registry, JSON-Scan |
| `auth.py` | Zugangsblock je Zug (persönliche Anmeldung) |

Zwei Muster prägen das Verhalten: **spekulativer Vorabruf** (`prefetch.py`
startet eine Suche parallel zur Klassifikation, damit die Antwort nicht wartet)
und **Werkzeugaufrufe seriell** innerhalb eines Zuges, damit sich Argumente
aufeinander stützen können.

### 4.5 RAG (`services/rag/`)

Für Wissen, das **nicht** im Repositorium steht — Redaktionsregeln,
Plattformwissen, Handreichungen.

```
Datei/URL ─▶ ingest (markitdown) ─▶ chunking ─▶ embed ─▶ rag_chunks (pgvector)
                                                            │
Frage ──────────────────────────▶ embed ─▶ Kosinus-Suche ───┘
                                              └─▶ rerank (ONNX-Cross-Encoder) ─▶ Kontext
```

Embeddings laufen wahlweise über den LLM-Anbieter (`embed.py`) oder **lokal auf
onnxruntime** (`embed_local.py`); das Reranking ist ein lokaler
Cross-Encoder (`rerank.py`). Beides bewusst ohne Torch: `onnxruntime`,
`tokenizers`, `numpy` — CPU-tauglich und lizenzkonform.

### 4.6 Konfiguration — der Kern der Pflegbarkeit

**36 Bereiche** (`domain/config_models/__init__.py:55-103`), jeder ein
Pydantic-Modell:

| Gruppe | Anzahl | Beispiele |
|---|---|---|
| `01-base` | 20 | Persona, Guardrails, Anzeige-Regeln, Sicherheit, Tonfall, Begrüßung, **Engine**, Suchwerte (`rag-retrieval`, Paket 7) |
| `02-domain` | 3 | Domänenregeln, Lotsen-Regeln, WLO-Plattformwissen |
| Gruppierte MD-Bereiche | 2 | `03-patterns`, `04-personas` |
| `04-*` Dimensionen | 4 | Entitäten, Intents, Signale, Zustände |
| `05-canvas` | 3 | Materialtypen, Typ-Aliase, Persona-Prioritäten (Auslöser gestrichen, Paket 7) |
| `05-knowledge` + `eval` | 3 | MCP-Server, RAG-Konfiguration, Gold-Flows |

Der Weg einer Änderung:

```
Studio-Formular ──PUT /api/config/…──▶ config_store.put()
                                          │  ein Transaktionsschritt:
                                          │  UPSERT config_areas (version++)
                                          │  + INSERT config_history
                                          ▼
                                    Postgres-Trigger trg_config_notify
                                          │  NOTIFY
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                   Replik 1          Replik 2          Replik 3
                   Cache-Eintrag verwerfen → nächster Lesezugriff holt neu
```

Ziel der Ausbreitung: **unter 2 Sekunden**, ohne Neustart, über alle Repliken.
Lesende Zugriffe laufen über die Fassade `services/config_loader/` — 13
Submodule mit Prozess-Cache, damit ein Zug nicht dutzendfach die DB fragt.

Der **Seed-Baum** `backend/seeds/` (69 Dateien, Stand 2026-10-03) ist der Auslieferungsstand;
`boerdi import-config` bringt ihn in die DB. Er ist die Import-Quelle — nicht
der ALT-Baum.

### 4.7 Sicherheit

| Ebene | Umsetzung |
|---|---|
| Eingabe-Prüfung | `services/safety/regex_gate.py` (Muster), `moderation.py` (Anbieter), `legal.py` (rechtliche Hinweise), `service.py` (Reihenfolge) |
| Drosselung | slowapi + `limits`, Zähler in Valkey; `/api/chat` und `/api/agent` gleich behandelt |
| Zugang Studio | Cookie-Sitzung, BFF spritzt `X-Studio-Key` serverseitig (§7) |
| Zugang Agent | `AGENT_OPEN` \| persönlicher `WLO-Access-Block` \| `X-Studio-Key` |
| Ausgehende Abrufe | `url_safety.py` — SSRF-Riegel inklusive Redirect-Prüfung |
| Fremdtext | `domain/untrusted_text.py` — MCP-Antworten sind Eingabe, nicht Wahrheit |
| Schreibzugriffe | zweistufige Abnahme (Vorschau → Bestätigung), Schlüssel an den Hash der Änderung gebunden (`domain/write_confirm.py`) |
| Geheimnisse | ausschließlich aus Umgebung; nie protokolliert |

### 4.8 Beobachtbarkeit (`obs/`)

`otel.py` (Traces nach Jaeger), `quality_events.py` (Sicherheits- und
Qualitätsprotokolle, datenschutz-gesteuert), `usage.py` (Token und Kosten je
Zug), `progress.py` (Phasen-Ereignisse für SSE), `tasks.py` (Hintergrund-Aufgaben
mit ehrlicher Fehlerauswertung). Seit Paket 17: `metrics.py` (Prometheus — HTTP je
Pfad-Vorlage, Züge, LLM- und MCP-Aufrufe), `trace_id.py` (Trace-ID je Anfrage, weiter nur an
b-api und eigenen MCP-Server), `log_format.py` (`LOG_FORMAT` json/text auf stdout),
`herzschlag.py` (Lasttest- und Eval-Läufe schreiben alle 15 s `heartbeat_at`; verwaist ist
nur, wessen Herzschlag ausbleibt).

---

## 5. Zusammenspiel mit edu-sharing (WLO)

Der Chatbot hält **keine Kopie** des Bestands. Alles, was er über
Bildungsmaterialien weiß, holt er zur Laufzeit über den **MCP-Server** aus dem
edu-sharing-Repositorium — und alles, was er dazu sagt, formuliert ein Modell
aus der **B-API**, der LLM-Versorgung des Bildungssektors. Diese Doppelrolle in
einem Bild:

```
            LESEN                          SCHREIBEN (zweistufig)
  Suche · Details · Kompendium ·      Inhalt anlegen/ändern · einsortieren ·
  Volltext · Skills · Vokabulare      Metadaten-/Redaktionsvorschläge
            ▲                                   ▲
            └────────────┬──────────────────────┘
                    MCP-Server  (Streamable HTTP, ein Aufrufweg: call_mcp_tool)
                         ▲                     ▲
   BACKEND ──────────────┘   Zugangsblock je Zug: anonym ODER Ticket → EDU-TICKET
      │
      └── LLM-Aufrufe ─▶  B-API  (Chat · Embeddings · je nach Modus Speech/Moderation)
```

### 5.1 Inhalte lesen

| Werkzeugfamilie | Zweck |
|---|---|
| `search_wlo_all` | **eine** breite Suche über Inhalte, Sammlungen und Themenseiten — der Standardweg |
| `search_wlo_content` / `_collections` / `_topic_pages` / `_within_collection` | gezielte Einzelsuchen; Filter als deutsche Labels (`learningResourceType`, `discipline`, `educationalContext`), dazu `license` (u. a. Sammelwert `"OER"`) und `excludeNodeIds` („zeig mehr davon"; bei `_within_collection` stattdessen `skipCount`, der Server kennt dort kein `excludeNodeIds`). Alle Filter gleicht der Client vor dem Aufruf ab (`arg_resolvers`, `lizenz_abgleich`) |
| `get_node_details` / `get_nodes_details` | Einzelheiten, im Bündel bis 50 Knoten in einem Aufruf |
| `get_compendium_text` | die kuratierte Übersichts-Prosa einer Sammlung; mit `query` nur die passenden Absätze, im Bündel bis 9 Sammlungen je Aufruf (bewusst unter dem Server-Maximum 25, weil die Langform ungedeckelt in den Prompt geht). Suchtreffer tragen nur das Signal `hasCompendium` — den Text holt der Seitenkontext bei Bedarf nach |
| `get_related_content` · `get_node_breadcrumb` · `get_node_collections` | „mehr wie dieses", Einordnung im Baum |
| `lookup_wlo_vocabulary` · `lookup_wlo_publishers` | Vokabularwerte für Schreibvorgänge und Metadaten-Prüfung, Anbieterauflösung. Suchfilter (Fach, Stufe, Typ, Zielgruppe, Lizenz) gleicht der Client selbst ab (`arg_resolvers`, `lizenz_abgleich`) |

Die Suchdisziplin steht im **Master-Skill** (`docs/skills/vorgehen.md`): die
`query` trägt nur den Kernbegriff, Materialart/Fach/Stufe gehören in die Filter.
Wächter-Tests halten das Dokument synchron zum Werkzeugkatalog.

### 5.2 Textextraktion

Drei Wege, gestaffelt nach Quelle:

* **Einzelmaterial:** `get_wlo_content_text` liefert den extrahierten Volltext
  eines Materials — als LLM-Werkzeug und als deterministische Direkt-Aktion
  („Inhalt anzeigen"-Knopf an jeder Karte, Muster M17). Der Client setzt keinen
  eigenen Deckel mehr (seit 2026-08-21, Begründung in `services/mcp/tool_args.py`);
  es gilt die Server-Vorgabe von 200 000 Zeichen.
* **Sammlung:** das Kompendium (5.1) — redaktionelle Prosa statt Extraktion,
  dreiteilig (Weltwissen · Lehrplanbezüge je Stufe/Bundesland · Inhalte).
* **Eigenes Wissen:** der RAG-Ingest (`services/rag/ingest.py`) konvertiert
  Dateien und URLs mit **markitdown** nach Markdown (SSRF-Guard davor),
  zerlegt, bettet ein und legt sie in `rag_chunks` (pgvector) ab — für
  Redaktionswissen, das nicht im Repositorium steht.

### 5.3 Skills — Anleitungen aus dem Repositorium

Skills sind im Repositorium gepflegte Arbeitsanleitungen (Inhaltsart
`ai_skill`). Der Bot behandelt sie als **Vorrang-Wissen**:

* Suchtreffer und Sammlungen tragen ihre **Skill-Registry** mit (Katalog der
  freigegebenen Skills, je Eintrag mit Arbeitskontext); der volle Katalog ist
  die Vorgabe, ein Kontextfilter greift nur auf ausdrücklichen Wunsch.
* `get_skill` holt die Anleitung **ungekürzt** — sie wird Teil des Prompts und
  schlägt die mitgelieferte Systemvorlage (Skill-Vorrang,
  `domain/skill_precedence.py`): steht an einer Sammlung „Stunde planen", plant
  der Bot nach dieser Anleitung, nicht nach seinem Standardmuster.
* Im **Muster-Modus** führen nur sechs Muster die Skill-Werkzeuge. Die
  **Skill-Brücke** (`domain/skill_bruecke.py`, Studio-Schalter `muster_skills`,
  Vorgabe aus) hängt sie an jedes andere Werkzeug-Muster, sobald Skills im Spiel
  sind; ohne Werkzeuge steht im Prompt nur die Übersicht, kein Ladeweg.
* Der **Master-Skill** selbst (`vorgehen.md`, ~30 Anwendungsfälle) liegt als
  Knoten im Repositorium und reist als Prompt-Kopf in Agent-Zügen mit
  (`services/master_skill.py`; Einbettung schaltet mit `master-skill`).

### 5.4 Schreiben und Kuratieren

Der Schreibweg ist **zweistufig**: das Modell führt nie direkt aus, sondern
beschreibt die Änderung (`PreparedWrite` + Bestätigungs-Token); erst die
Bestätigung im Folgezug löst den MCP-Schreibaufruf aus. Werkzeuge
(`tool_defs_curation.py`): Inhalt anlegen/ändern/einreichen, in Sammlungen
einsortieren, Sammlungen anlegen/umbenennen, Metadaten-Vorschläge erzeugen und
entscheiden. Was eine Einbettung davon darf, begrenzt `tool_mode`
(`read-only` · `curate` · `full`) — die Grenze steht zusätzlich im Systemprompt,
damit das Modell nichts verspricht, was es nicht ausführen kann.

### 5.5 Identität — anonym oder als Person

Ohne Anmeldung liest der Bot den öffentlichen Bestand. Reicht die
edu-sharing-Seite ihr **Ticket** durch (Widget-Attribut `ticket` →
`POST /auth/ticket` am MCP-Server → EDU-TICKET upstream), handelt der MCP als
die angemeldete Person — Rechte, Vorschläge und Schreibzugriffe laufen unter
ihrem Konto. Das Backend braucht dafür keine Sonderwege; der Zugangsblock reist
je Zug mit (`services/mcp/auth.py`). Details: `edu-sharing-einbindung.md` §3.

### 5.6 B-API — die LLM-Versorgung

Alle Modellaufrufe laufen über **einen** Transport (`services/llm.py`, LiteLLM);
der Anbieter ist Konfiguration (`LLM_PROVIDER`), nicht Code:

| Modus | Chat-Modell (Vorgabe) | Embeddings | Speech/Moderation |
|---|---|---|---|
| `openai` | gpt-6-luna | text-embedding-3-small (1536) | ja |
| `b-api-openai` (Standard im Betrieb) | gpt-6-luna | text-embedding-3-small (1536) | ja |
| `b-api-academiccloud` (lauffähig, nicht Standard: langsamer, schwächer) | qwen3-30b-a3b-instruct-2507 | text-embedding-3-small (1536) über den OpenAI-Pfad der b-api — die AcademicCloud führt kein Einbettungsmodell | **nein** — Speech ehrlich abgeschaltet, Moderation aus |

**Endpunkt je Modell.** Chat-Completions ist der gemeinsame Nenner, die
AcademicCloud braucht genau diesen Weg. Die neuen OpenAI-Modelle (ab `gpt-6`)
laufen im Modus `openai` ausdrücklich über `/v1/responses` (LiteLLM-Präfix
`responses/`): `/v1/chat/completions` nimmt bei ihnen Werkzeuge nur ohne
Reasoning an. gpt-5.4 bis 5.6 leitet LiteLLM bei Werkzeugen mit gesetztem
`reasoning_effort` von sich aus dorthin um, und zwar in beiden OpenAI-Modi, weil
die App jeden Anbieter als `openai/…` anspricht. Regeln je Modellgruppe:
`services/llm_models.py`.

**B-API-Router (Paket 17).** Mit `B_API_ROUTE=<route>` (nur bei `b-api-openai`)
geht das Chat-Modell an `…/api/v1/llm/router` und schickt den Routennamen als
`model`; die b-api verteilt nach Priorität und Gewicht und weicht bei Ausfall aus.
Parameterregeln und Preis bleiben die von `LLM_CHAT_MODEL`, denn eine Route bündelt
nur Modelle **einer** Familie (gemessen 2026-10-20: `max_tokens` an eine
gpt-6-Route → 400). Einbettungen, Moderation und Sprache bleiben auf `/openai`;
Judge und Simulator nur, wenn `EVAL_JUDGE_MODEL`/`EVAL_SIMULATOR_MODEL` ein anderes
Modell nennen — ohne eigenes Modell SIND sie das Chat-Modell und folgen der Route
(`services/llm_router.py`). LiteLLM meldet unter einer Route den Routennamen als
`resp.model` — das antwortende Modell geht verloren; gebucht wird deshalb unter
`LLM_CHAT_MODEL` (`llm_router.antwort_modell`), auch wenn die Route auf ihre Reserve
auswich (deren Preis ist von außen nicht erkennbar). Vorgabe ist `B_API_ROUTE` leer.

**Schlüssel des Aufrufers (Paket 17).** Läuft der Chatbot hinter dem b-api-Proxy
(`/api/v1/proxy/badboerdichat/…`, `forwardApiKey`), trägt jede Anfrage
`Authorization: Bearer <key>` — den Schlüssel, den edu-sharing für Person oder Gast
wählt. Chat, Chat-Stream, Agent und Sprache übernehmen ihn (`api/turn_auth`,
`services/llm_auth`); alle LLM-Aufrufe des Zuges (auch Moderation und spekulative
Nebenaufgaben, die den Kontext erben) gehen mit genau diesem einen Kopf hinaus, die
b-api bucht auf ihn. Ohne Kopf gilt `B_API_KEY` — so laufen Direktaufrufe und alle
Hintergrundläufe (Eval, Lasttest, RAG-Import, Vorwärmung). Nur `Bearer <sichtbare
ASCII-Zeichen>` gilt; ein anderer Wert wird gemeldet (ohne Wert) und verworfen. Der
Studio-Proxy reicht `Authorization` nie durch. `X-API-KEY` geht seit Paket 17 nicht
mehr hinaus (b-api: ein zusätzlicher ungültiger Kopf → 401). **Die Schlüssel gehören
zu einem Deployment:** `B_API_BASE_URL` muss das Deployment nennen, dessen Proxy sie
reicht (Prod-Proxy → Prod-Adresse; die Vorgabe ist Staging) — sonst endet jeder Zug mit
401. Bekannte Grenze: LiteLLM hält je Schlüssel einen eigenen HTTP-Client (Cache-Schlüssel
ist der Hash des Schlüssels). Über den Proxy sind das drei (zwei WLO-Schlüssel, Person und
Gast, plus `B_API_KEY`). Im Modus `auto` (Vorgabe) wird der Kopf angenommen: wer den Chat direkt
aufruft, kann beliebige Schlüssel vorlegen — jeder kostet einen neuen Client im
(begrenzten) Cache und verdrängt die echten; die b-api weist ungültige mit 401 ab, die
Drosselung je IP begrenzt die Zahl. Abhilfe bei Bedarf: ein gemeinsamer Client
(`litellm.aclient_session`) oder `B_API_KEY_MODE=static` (Kopf zählt nicht). `forward`
(jeder Zug braucht ihn, sonst 401) verlangt einen Schlüssel, prüft ihn aber nicht und
begrenzt die Clients deshalb nicht; Züge der Anlage selbst (Studio-Proxy, gültiger
Studio-Schlüssel — Evaluation, Lasttest) sind davon frei. Der Schalter steht in
`api/turn_auth`, die Tabelle in `deploy/README.md`.

Die Embedding-Dimension bestimmt das pgvector-Schema (`EMBED_DIM`); alternativ
laufen Embeddings und Reranking **lokal** auf onnxruntime (§4.5) — dann braucht
der RAG-Weg gar keinen externen Anbieter. Schlüssel liegen ausschließlich in der
Umgebung (`B_API_KEY_*`), nie im Code oder in Logs.

### 5.7 Wo der Bot in edu-sharing sichtbar wird

| Fläche | Weg | Doku |
|---|---|---|
| Seitenleiste im Repositorium | `<boerdi-chat embed-mode="frameless">`, Link-Abfang per `linkClicked` (Opt-in) | `edu-sharing-einbindung.md` |
| Browser-Erweiterung | dasselbe Element, CORS-Regel für Extension-Origins | `browser-plugin-einbindung.md` |
| Maschinelle Aufträge | `POST /api/agent` — Anweisung rein, Text + JSON nach eigenem Schema raus | `agent-modus.md` |
| Seitenkontext | Widget erkennt Sammlung/Inhalt/Themenseite, Backend begrüßt kontextbezogen (`page_context`, Kontext-Aktionen) | `edu-sharing-einbindung.md` §6 |

---

## 6. Widget

Ein Custom Element `<boerdi-chat>` — 25 Attribute, 4 Ereignisse, 6 Methoden.
Vollständige Referenz in [`browser-plugin-einbindung.md`](browser-plugin-einbindung.md).

```
<boerdi-chat>                  Element-Kontrakt, Attribute → Signals
  └─ PanelState                auf/zu, Größenstufe, Lazy-Mount
  └─ GuideBoot                 Boot-Abruf /api/config/guide-mode
  └─ GuideNav                  Lotsen-Banner mit Zustimmung
  └─ HostBridges               Klick-Umschrift, window-Ereignisse, URL-Wächter
  └─ ChatShellComponent        der Chat selbst
       ├─ stream/              SSE-Client + Wachhunde + POST-Rückfall
       ├─ controllers/         Tour, Kontext-Begrüßung, Sammlungs-Aktionen …
       ├─ cards/ grouping/     Ergebnis-Boxen, Kacheln, Schwimmlinien
       ├─ markdown/            marked + DOMPurify
       ├─ session/             Sitzungs-ID, Anmeldung, Ticket, prepared-write
       └─ i18n/                de/en, zur Laufzeit umschaltbar
```

Vier Bauentscheidungen, die das Verhalten erklären:

* **Shadow DOM.** Stile der Gastseite bluten nicht herein, unsere nicht hinaus.
  Preis: Ereignisse brauchen `composed: true`, und der Klick-Wächter muss am
  Shadow-Root hängen, weil `event.target` außerhalb retargetiert würde.
* **Signals, zoneless.** Ein Signal-Write plant die Prüfung selbst — Aufrufe der
  Gastseite (`openChatbot()`) wirken ohne Zone-Wiedereintritt.
* **Lazy-Mount.** Die Chat-Shell entsteht erst beim ersten Öffnen. Rahmenlos
  wird sie sofort gemountet — dort gibt es keinen Knopf, der das Tor je öffnete.
* **Eine Datei.** Kein Nachladen von Teilstücken zur Laufzeit; das macht die
  Einbettung in fremde Seiten und Plugins berechenbar.

---

## 7. Studio

Die Redaktionsoberfläche: 36 Bereiche pflegen, Muster und Personas bearbeiten,
Auswertungen ansehen, Sicherungen ziehen, Agent und Widget testen.

**Zwei Arbeitsbereiche (Paket 14).** Oben wählt die Redaktion *Agent* oder *Muster*;
die Seitenleiste zeigt den eigenen Block der Maschine (Agent: Übersicht, Rolle & Schutz,
Prompt & Probelauf · Muster: Übersicht, Identität & Schutz, Domänenwissen, Patterns,
Dimensionen, Materialformate) und darunter, was beide teilen: *Gemeinsam* (Begrüßung,
Kontext-Aktionen, Tour & Lotse, Zielgruppen, Wissen, Werkzeuge, Skills, Anzeige,
Datenschutz), *Auswertung* (Nutzung, Sessions, Analyse, Evaluation, Lasttest,
Safety-Logs, Kosten) und *System* (Betrieb, Alle Bereiche, Sicherung, Vorschau). Ein
Bereich hat je Arbeitsbereich genau eine Heimat (`views/area-homes.ts`), jedes Feld
eine Plakette, in welcher Maschine es wirkt (`GET /api/config/effects`, `fields`).

**Werk und eigene Fassung (Paket 12).** Je Bereich hält die Datenbank die Werksfassung
aus dem Seed und, wenn die Redaktion etwas ändert, eine eigene; umschalten,
vergleichen (je Feld) und Schnappschüsse ziehen geht unter System → „Sicherung“.

**Formulare aus Schemata.** `schema-form/` erzeugt Eingabefelder aus dem
Bereichsmodell. Ein neues Feld im Pydantic-Modell erscheint automatisch — es gibt
keine zweite Stelle, an der jemand es nachtragen müsste.

**Der BFF ist eine Pfad-Umschrift, kein zweiter HTTP-Sprung**
(`api/studio_proxy.py`):

```
Browser ──/studio/api/sessions──▶ StudioProxyMiddleware
                                   │  Scope umschreiben auf /api/sessions
                                   │  Cookie prüfen, X-Studio-Key einsetzen
                                   ▼
                                 derselbe Prozess, normaler Router
```

Damit funktionieren Multipart-Uploads und SSE-Ströme unverändert (der
`receive`/`send`-Kanal bleibt erhalten, nichts wird gepuffert), und es gibt
keinen künstlichen Zeitablauf, der ein legitimes langes Backup abschneidet.
Der Admin-Schlüssel verlässt den Server nie — der Browser hält nur ein Cookie.

Angular routet clientseitig, deshalb bootet ein unbekannter Unterpfad die Hülle
statt zu 404en (`studio_static.py`); die drei echten Auth-Routen unter
`/studio/api/auth/*` sind vor dem Mount registriert und werden nicht verdeckt.

---

## 8. Datenmodell

17 Tabellen (15 in `db/models.py`, dazu `session_locks` aus Migration 0008 und
`master_skill_stand` aus 0015):

| Tabelle | Inhalt |
|---|---|
| `sessions` | Gesprächssitzung + `session_state` (jsonb: Entitäten, Zustand, Muster-Historie) |
| `messages` | Verlauf je Sitzung |
| `memory` | Langzeit-Gedächtnis je Sitzung |
| `safety_logs` | Sicherheits-Ereignisse |
| `quality_logs` | Qualitäts-Ereignisse je Zug |
| `usage_events` | Token und Kosten |
| `eval_runs` | Auswertungsläufe, mit `heartbeat_at` (0014) |
| `loadtest_runs` | Lasttest-Läufe, mit `heartbeat_at`; höchstens einer läuft (Unique-Teilindex, 0014) |
| `config_areas` | die 36 Bereiche (jsonb + Version) |
| `config_history` | jede Änderung, mit Urheber |
| `config_snapshots` | benannte Sicherungsstände (von Hand und automatisch vor Werks-Schritten) |
| `config_werk_entfernt` | im Studio gelöschte Werksbereiche — der Werksabgleich legt sie nicht wieder an (0011) |
| `prompt_versions` | feste Prompt-Bausteine je Prüfsumme, für die Messbedingungen der Evaluation (0012) |
| `session_locks` | Zug-Sperre je Sitzung über alle Repliken (0008); auch die Lauf-Sperren `__lauf:aufbewahrung` und `__lauf:master-skill` |
| `master_skill_stand` | geteilter Master-Skill-Stand je Kennung — eine Kopie holt, alle übernehmen (0015) |
| `rag_documents` | Quelldokumente |
| `rag_chunks` | Abschnitte + **pgvector**-Einbettung |

Nebenläufigkeit: Züge derselben Sitzung serialisiert seit Paket 7 (P1) eine
Sperre in Postgres über alle Repliken: ein Eintrag in `session_locks` (Migration
0008) mit Ablaufzeit, genommen von beiden Chat-Endpunkten
(`api/session_locks.sitzung_sperren` → `services/sitzungssperre`). Ein zweiter Zug
wartet bis 20 s und bekommt dann 409 bzw. im Stream `error` mit `code:
session_busy`. Die Sperre wird im Takt verlängert und verfällt nach einem Absturz
binnen 60 s; eine Advisory-Sperre schied aus, weil sie eine Verbindung über den
ganzen Zug hielte (eine xact-Sperre fiele beim ersten Commit). Ohne Datenbank
bleibt die prozessinterne Sperre (`asyncio.Lock`).

---

## 9. Abläufe

### 9.1 Ein Chat-Zug (Muster-Engine)

```
Widget                Backend                        Außen
  │ POST /api/chat/stream
  ├──────────────────▶│
  │                   │ Drossel · Sitzungssperre
  │                   │ setup: Sitzung + Zustand laden
  │◀── event: phase ──┤ tour? nein
  │                   │ page_context_enrich ─────────▶ MCP: Knoten-Metadaten
  │                   │ preflight: Safety + Direkt-Aktion?
  │                   │ assess ──────────────────────▶ LLM (instructor):
  │                   │   Persona · Intent · Signale · Entitäten
  │                   │ ┌─ prefetch (parallel) ──────▶ MCP: Suche
  │                   │ merge → route:
  │                   │   Muster wählen · Policy · Werkzeugliste
  │                   │ respond ─────────────────────▶ LLM + MCP-Werkzeugschleife
  │◀── event: token ──┤   (Token-Strom, sobald Text entsteht)
  │                   │ assemble: Karten · Boxen · Quick-Replies · Links
  │                   │ persist: Zustand · Nachricht · Kennzahlen
  │◀── event: result ─┤
  │ Ereignisse an die Gastseite (je nach emit-*): query-meta, guide-suggestion
```

### 9.2 Eine Redaktions-Änderung

```
Studio-Formular ─PUT /studio/api/config/…─▶ BFF-Umschrift ─▶ /api/config/…
   ─▶ Pydantic-Prüfung ─▶ config_store.put()  [UPSERT + history, eine Transaktion]
   ─▶ Postgres-Trigger NOTIFY ─▶ alle Repliken verwerfen den Cache-Eintrag
   ─▶ nächster Zug liest den neuen Wert          (Ziel: < 2 s, kein Neustart)
```

### 9.3 Ein Agent-Auftrag

```
Gastgeber ─POST /api/agent {instruction, collection_id, node_ids, result_schema}
   ─▶ Zugangsprüfung (AGENT_OPEN | WLO-Access-Block | X-Studio-Key) + Drossel
   ─▶ Vorabruf: get_skill_registry (Anleitungen), get_nodes_details (Gegenstand)
   ─▶ Schleife: LLM ⇄ MCP-Werkzeuge, bis submit_result | Prosa | Deckel
   ─▶ {text, result, stop_reason, iterations, tools_called}
```

Wer auswertet, prüft `stop_reason === "submit"`, bevor er `result` benutzt — die
sechs anderen Gründe liefern kein verlässliches Ergebnis.

---

## 10. Qualitätssicherung

| Ebene | Werkzeug | Umfang |
|---|---|---|
| Backend-Unit/Integration | pytest | **384 Testdateien**, > 6600 Tests (Stand 2026-10-20) |
| Frontend-Unit | Vitest | **236 Spec-Dateien** (ui 81, widget 4, studio 151; Stand 2026-10-20) |
| E2E | Playwright | Einbettungs- und Chat-Szenarien |
| Lint / Typen | ruff · ESLint · `tsc` | |
| Vertrags-Wächter | `test_openapi_contract.py` | die `/api`-Fläche ist eingefroren |
| Gestaltungs-Wächter | `check:tokens`, `check:a11y`, `check:contrast`, `check:radii` | keine hartcodierten Farben/Radien, Kontrast der Studio-Akzente |
| Bündelgröße | `check-widget-budget.mjs` | Widget-Budget im CI |
| Lizenzen | pip-licenses · license-checker | **Gate: nur MIT/Apache-2.0/BSD-artig** |

Dazu zwei fachliche Verfahren, die über Unit-Tests hinausgehen:

* **Golden-Läufe** (`evals/`, `services/eval/golden*.py`) — feste
  Anwendungsfall-Gespräche je Zielgruppe mit harten Ergebnis-Checks (v2:
  engine-fair, ein Lauf je Maschine wählbar); ein LLM-Richter bewertet
  daneben die Erfüllung des dokumentierten Soll-Angebots; seit Paket 13 zusätzlich
  ein Urteil je Ablauf (`judge_v2.py`), Matrizen und Messbedingungen je Lauf
  (`auswertung_v2.py`, `run_conditions.py`, `prompt_versions`). Pflicht, wenn sich
  Prompts ändern.
* **Generative Auswertung** (`scenario_gen.py`, `judge.py`) — erzeugte Szenarien
  über Personas und Intents, mit Kosten-Band im Studio.

---

## 11. Wo was hingehört

Wer etwas ändern will, findet hier den Ort:

| Vorhaben | Ort |
|---|---|
| Was der Bot sagt, wann, in welchem Ton | **Studio** — Konfiguration, kein Code |
| Neues Antwort-Muster | `03-patterns` (Konfiguration) + ggf. Werkzeugliste |
| Neue Entscheidungslogik | `domain/` — framework-frei, ohne Server testbar |
| Neuer Außenkontakt (API, DB, Datei) | `services/` |
| Neue HTTP-Route | `api/` — Achtung, `/api` ist vertraglich eingefroren |
| Neuer Schritt im Zug | `graph/nodes/` + Verdrahtung in `graph/build.py` |
| Neues Attribut am Widget | `widget.component.ts` + Studio-Referenztabelle (ein Test erzwingt beides) |
| Neues Feld in einem Bereich | Pydantic-Modell in `domain/config_models/` — das Studio-Formular folgt |
| Neue Tabelle/Spalte | `db/models.py` + Alembic-Migration |

**Zwei Regeln, die das System zusammenhalten:** Abhängigkeiten zeigen nach innen
(`api → graph → services → domain`), und was redaktionell entschieden wird,
gehört in die Konfiguration, nicht in den Code. Wer beide beachtet, kann fast
alles ändern, ohne etwas anderes zu brechen.
