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
| Master-Skill (Suchdisziplin, 30 Anwendungsfälle) | [`skills/vorgehen.md`](skills/vorgehen.md) |
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
                    │  ├── Muster │ Agent │ Hybrid             │
                    │  ├── MCP-Client · RAG · Safety           │
                    │  └── Config-Store (37 Bereiche)          │
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
Sicherheitsregeln, Begrüßung, Anzeige-Regeln — 37 Bereiche, im Studio pflegbar,
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
| Konfiguration | **pydantic-settings** | 65 Felder |
| Tests / Lint | **pytest** (208 Dateien) · **ruff** | |

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

### Produktions-Topologie (`deploy/compose.prod.yml`)

```
        Internet
           │  443
      ┌────▼─────┐
      │ traefik  │  v3.6, TLS, einziger veröffentlichter Port
      └────┬─────┘
           │
     ┌─────▼──────┐   replicas: 3 (Vorgabe)
     │  backend   │◀── zustandslos: Sitzung + Config in Postgres,
     └──┬───┬───┬─┘    Sperre per pg_advisory_xact_lock → keine Sticky Sessions
        │   │   └──────────────▶ jaeger 2.19
        │   └──────▶ valkey 8   (Drossel-Zähler)
        ▼
   postgres 17 + pgvector
        ▲
   migrate (einmalig): alembic upgrade head && boerdi import-config --only-missing
```

Der `migrate`-Dienst ist **idempotent**: `--only-missing` legt an, was fehlt, und
rührt Gepflegtes nicht an — sonst drehte jeder Neustart die redaktionelle Arbeit
auf den Auslieferungsstand zurück.

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

### 4.3 Drei Maschinen im `respond`-Knoten

| | **Muster-Engine** (Vorgabe) | **Agent-Schleife** | **Hybrid** |
|---|---|---|---|
| Modul | `respond.py` → `tool_loop.py` | `respond_agent.py` → `agent_loop.py` | wie Agent |
| Klassifikator | ja (größter Prompt des Zuges) | nein | nein |
| Werkzeugwahl | pro Muster gebunden (`response_tool_selection`) | voller Katalog | Katalog **plus** `waehle_vorgehen`: das Modell wählt ein redaktionelles Muster als Werkzeug, dessen Body wird Anweisung, die Werkzeugliste wechselt mit |
| Vorabruf | über Intent (`prefetch.py`) | — | deterministisch (`_looks_like_search_query`) |
| Ende | eine Antwort | `submit_result`, Prosa oder Deckel | wie Agent |
| Deckel | Muster-Grenzen | `max_iterations`, `deadline_s`, `token_budget` | wie Agent |

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

**37 Bereiche** (`domain/config_models/__init__.py:55-103`), jeder ein
Pydantic-Modell:

| Gruppe | Anzahl | Beispiele |
|---|---|---|
| `01-base` | 19 | Persona, Guardrails, Anzeige-Regeln, Sicherheit, Tonfall, Begrüßung, **Engine** |
| `02-domain` | 3 | Domänenregeln, Lotsen-Regeln, WLO-Plattformwissen |
| Gruppierte MD-Bereiche | 2 | `03-patterns`, `04-personas` |
| `04-*` Dimensionen | 4 | Entitäten, Intents, Signale, Zustände |
| `05-canvas` | 5 | Auslöser, Materialtypen, Persona-Prioritäten |
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

Der **Seed-Baum** `backend/seeds/` (61 Dateien) ist der Auslieferungsstand;
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
mit ehrlicher Fehlerauswertung).

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
| `search_wlo_content` / `_collections` / `_topic_pages` / `_within_collection` | gezielte Einzelsuchen; Filter als deutsche Labels (`learningResourceType`, `discipline`, `educationalContext`), dazu `license` (u. a. Sammelwert `"OER"`) und `excludeNodeIds` („zeig mehr davon") |
| `get_node_details` / `get_nodes_details` | Einzelheiten, im Bündel bis 50 Knoten in einem Aufruf |
| `get_compendium_text` | die kuratierte Übersichts-Prosa einer Sammlung; mit `query` nur die passenden Absätze, im Bündel bis 9 Sammlungen je Aufruf (bewusst unter dem Server-Maximum 25, weil die Langform ungedeckelt in den Prompt geht). Suchtreffer tragen nur das Signal `hasCompendium` — den Text holt der Seitenkontext bei Bedarf nach |
| `get_related_content` · `get_node_breadcrumb` · `get_node_collections` | „mehr wie dieses", Einordnung im Baum |
| `lookup_wlo_vocabulary` · `lookup_wlo_publishers` | Vokabular-/Anbieterauflösung, wenn ein Label nicht greift |

Die Suchdisziplin steht im **Master-Skill** (`docs/skills/vorgehen.md`): die
`query` trägt nur den Kernbegriff, Materialart/Fach/Stufe gehören in die Filter.
Wächter-Tests halten das Dokument synchron zum Werkzeugkatalog.

### 5.2 Textextraktion

Drei Wege, gestaffelt nach Quelle:

* **Einzelmaterial:** `get_wlo_content_text` liefert den extrahierten Volltext
  eines Materials — als LLM-Werkzeug und als deterministische Direkt-Aktion
  („Inhalt anzeigen"-Knopf an jeder Karte, Muster M17). Der Client deckelt auf
  `CONTENT_TEXT_MAX_CHARS` = 50 000 Zeichen (`services/mcp/tool_args.py:205`).
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
* Der **Master-Skill** selbst (`vorgehen.md`, ~30 Anwendungsfälle) liegt als
  Knoten im Repositorium und reist als Prompt-Kopf in Agent- und Hybrid-Zügen
  mit (`services/master_skill.py`; Einbettung schaltet mit `master-skill`).

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
| `openai` | gpt-5.6-luna | text-embedding-3-small (1536) | ja |
| `b-api-openai` | gpt-5.6-luna | text-embedding-3-small (1536) | ja |
| `b-api-academiccloud` | mistral-large-3-675b | e5-mistral-7b-instruct (4096) | **nein** — Speech ehrlich abgeschaltet, Moderation degradiert kontrolliert |

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

Die Redaktionsoberfläche: 37 Bereiche pflegen, Muster und Personas bearbeiten,
Auswertungen ansehen, Sicherungen ziehen, Agent und Widget testen.

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

13 Tabellen (`db/models.py`):

| Tabelle | Inhalt |
|---|---|
| `sessions` | Gesprächssitzung + `session_state` (jsonb: Entitäten, Zustand, Muster-Historie) |
| `messages` | Verlauf je Sitzung |
| `memory` | Langzeit-Gedächtnis je Sitzung |
| `safety_logs` | Sicherheits-Ereignisse |
| `quality_logs` | Qualitäts-Ereignisse je Zug |
| `usage_events` | Token und Kosten |
| `eval_runs` | Auswertungsläufe |
| `loadtest_runs` | Lasttest-Läufe |
| `config_areas` | die 37 Bereiche (jsonb + Version) |
| `config_history` | jede Änderung, mit Urheber |
| `config_snapshots` | benannte Sicherungsstände |
| `rag_documents` | Quelldokumente |
| `rag_chunks` | Abschnitte + **pgvector**-Einbettung |

Nebenläufigkeit über `pg_advisory_xact_lock` je Sitzung (`db/locks.py`) — zwei
gleichzeitige Züge derselben Sitzung serialisieren sich, ohne dass das Backend
Zustand halten müsste. Genau das macht die Repliken austauschbar.

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
  │ Ereignisse an die Gastseite: query-meta, ggf. guide-suggestion
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
| Backend-Unit/Integration | pytest | **208 Testdateien**, > 3400 Tests |
| Frontend-Unit | Vitest | **154 Spec-Dateien** (ui, widget, studio) |
| E2E | Playwright | Einbettungs- und Chat-Szenarien |
| Lint / Typen | ruff · ESLint · `tsc` | |
| Vertrags-Wächter | `test_openapi_contract.py` | die `/api`-Fläche ist eingefroren |
| Gestaltungs-Wächter | `check:tokens`, `check:a11y`, `check:radii` | keine hartcodierten Farben/Radien |
| Bündelgröße | `check-widget-budget.mjs` | Widget-Budget im CI |
| Lizenzen | pip-licenses · license-checker | **Gate: nur MIT/Apache-2.0/BSD-artig** |

Dazu zwei fachliche Verfahren, die über Unit-Tests hinausgehen:

* **Golden-Läufe** (`evals/`, `services/eval/golden*.py`) — feste Szenarien mit
  festgehaltener Erwartung; ein LLM-Richter bewertet Abweichungen. Pflicht,
  wenn sich Prompts ändern.
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
