# Übergabe an den Betrieb (Team 6)

Stand: Paket 18, 2026-10-28 (zuerst Paket 17, 2026-10-20). Beantwortet die Checkliste „Übergabepaket“ des Leitfadens für Team 6, Punkt für Punkt. Wo eine Datei die Einzelheiten trägt und von einem Test aktuell gehalten wird, steht hier nur der Verweis.

**Kurzfassung:** [Service-Steckbrief](steckbrief-uebergabe.md) (Jira [GEN-329](https://edu-sharing.atlassian.net/browse/GEN-329)). **Offen, vom Nutzer einzutragen:** Wartungsverantwortung (§15), Abnahme des Beschreibungstexts der Spec (§2), Abstimmung SSE mit Wolli (§4). **Offen, technisch:** Ressourcen-Messung (§10).

## 1 Repository, CI und Images

- **Repository:** `github.com/janschachtschabel/edu-chatbot-sc` (privat — Zugang für T6 einrichten).
- **Images:** Registry `ghcr.io/janschachtschabel/edu-chatbot-sc` (privat — Pull-Zugang für T6
  einrichten; die Sichtbarkeit des Pakets ist eine eigene Einstellung neben der des Repos).
- **CI:**
  - `ci.yml`: Lint, Tests, Lizenz-Gate, `pip-audit`, OpenAPI-Gate.
  - `image.yml`: Build, Smoke mit Postgres und Valkey (beide Ports, `/ready`), Veröffentlichung erst nach grünem `ci`.
- **Image-Marken:**

| Marke | Wofür |
|---|---|
| `sha-<7>` | unveränderlich, für Deploys |
| `<Tag>` | SemVer ab `0.6.0`, für Produktion |
| `latest` | nur die Spitze von `main`, für Staging |

- **Image:**
  - dreistufig (Node-Build, uv-Build, `python:3.12-slim`)
  - läuft nicht als root (uid 1000)
  - ohne Daten und Modelle (§12)

## 2 OpenAPI

| | Ort |
|---|---|
| Öffentliche Spec (Chat-API) | `GET /openapi.json` am öffentlichen Port · Datei `docs/api/openapi-public.json` |
| Volle Spec (mit Studio/Verwaltung) | `GET /openapi-full.json` am internen Port · Datei `docs/api/openapi-v1.json` (eingefrorener Vertrag) |

- **Herkunft:** Beide Specs werden aus dem Code erzeugt (FastAPI). Ein CI-Gate prüft sie gegen die Dateien (`scripts/export_openapi.py --check`).
- **Anzeigename:** „BOERDi – Chatbot von WirLernenOnline“.
- **Beschreibungstext:** „BOERDi hilft beim Finden und Nutzen offener Bildungsinhalte von WirLernenOnline: Fragen stellen, passende Materialien, Themenseiten und Sammlungen erhalten, Inhalte zusammenfassen lassen.“ *(Entwurf, Abnahme Nutzer)*
- **Inhalt der öffentlichen Spec** (9 Operationen):
  - Chat (auch als Strom)
  - Agent für Gastanwendungen (auch als Strom)
  - Sprache (Status, Transkription, Sprachausgabe)
  - Verlauf einer Sitzung
  - Lotsen-Modus

## 3 Ports und auszublendende Pfade

| Port | Inhalt | Ingress |
|---|---|---|
| 8100 (öffentlich) | Widget, Chat, Agent, Sprache, Studio (hinter Login) | ja |
| 8101 (`INTERNAL_PORT`) | `/health` (Liveness, ohne DB), `/ready` (Readiness: Start fertig, Postgres antwortet, kein Herunterfahren), `/metrics`, `/openapi-full.json` | **nein** |

Im Cluster erreicht jeder Pod den Port 8101 (`/metrics`, volle Spec). Empfehlung: eine NetworkPolicy, die 8101 nur für Kubelet und den Prometheus-Namensraum öffnet.

- **Auszublenden am öffentlichen Port:** `/health`. Er liefert nur `{"status":"ok"}` und bleibt für ältere Proben bestehen.
- **`/api/health`:** braucht seit Paket 17 den Studio-Schlüssel.
- **Ein Prozess, zwei Server:** Einstieg ist `python -m boerdi.serve`.

## 4 Header, Content-Types, Antwortzeiten

**Eingehende Header** (alle optional):

| Header | Wofür |
|---|---|
| `Authorization: Bearer <key>` | b-api-Schlüssel des Aufrufers (Proxy, §5) |
| `WLO-Access-Block` | persönliche WLO-Anmeldung für den MCP-Server |
| `X-Boerdi-Engine` | Maschine wählen (`agent`/`pattern`) |
| `Accept-Language` | Sprache |
| `x-client-trace-id` bzw. B3 | Trace-ID (§7) |
| Cookie `boerdi_studio_auth`, `X-Studio-Key` | nur Studio |

**Ausgehende Header:**
- `Retry-After` bei 429.
- Sicherheitsköpfe: nosniff, Referrer-Policy, X-Frame-Options, HSTS, CSP am Studio.
- An den Strömen: `Cache-Control: no-cache, no-transform` und `X-Accel-Buffering: no` — für die
  Abstimmung mit Wolli wichtig (Pufferung im Proxy aus).
- Sonst keine.

**Content-Types:**

| Typ | Wo | Hinweis |
|---|---|---|
| `application/json` | Standard | |
| `text/event-stream` | `/api/chat/stream`, `/api/agent/stream` | **mit Wolli abstimmen**: Pufferung aus, Keepalive alle 10 s |
| `audio/mpeg` | Sprachausgabe | |
| `multipart/form-data` | Sprach-Upload; Studio: RAG-/Konfig-Upload | |
| JS/HTML | Widget-Dateien und Studio-Oberfläche | |
| ZIP/Markdown | Studio-Downloads | |

**Antwortzeiten:**
- Ein Zug dauert im Median 6,8 s (Agent) bzw. 9,1 s (Muster) — Messung 2026-10-01 (Plan Tempo-Kette).
- p95 liegt bis etwa 37 s — Messung 2026-09-27 (Golden-Läufe, E-5).
- Die LLM-Frist beträgt 75 s (`LLM_READ_TIMEOUT`).
- Empfehlung für Proxy und Ingress: Lese-Timeout 120 s.
- Rumpf-Grenzen der App (`api/body_limit`): Chat und Agent 2 MiB, Spracheingabe 11 MiB,
  Wiederherstellen und Werks-Upload 151 MiB, sonst 16 MiB. Der Ingress muss die größte
  durchlassen (Values: `proxy-body-size: 160m`; ingress-nginx deckelt sonst auf 1 MiB).
- Uvicorn hält leere Verbindungen 120 s offen — länger als der Ingress, damit dieser keine
  Anfrage auf eine gerade schließende Verbindung schickt.

**Lange Läufe:**
- Evaluation und Lasttest sind Jobs: Start, Lauf-ID, Status, Abbruch.
- Der RAG-Import (nur Studio) blockiert für die Dauer der Umwandlung.

## 5 B-API-Integration und Authentifizierung

**Variante A (Standard, hinter dem b-api-Proxy).**
- **Auth:** Der Proxy-Dienst `badboerdichat` ist mit `forwardApiKey` eingetragen. Chat, Agent und Sprache nehmen den durchgereichten `Authorization`-Kopf für **alle** LLM-Aufrufe des Zuges: Chat, Strom, Klassifikation, Moderation, Einbettung, Sprache.
- **Ein Header:** Hinaus geht genau dieser eine Kopf. Er wird nie geloggt oder gespeichert.
- **Schalter `B_API_KEY_MODE`:** `auto` (Vorgabe: Kopf, sonst `B_API_KEY`), `static` (immer
  `B_API_KEY`, Kopf zählt nicht), `forward` (jeder Zug braucht den Kopf, sonst 401 — für eine
  Anlage nur hinter dem Proxy). Hintergrundläufe nehmen immer `B_API_KEY`; Studio-Proben und
  Züge mit gültigem Studio-Schlüssel (Evaluation, Lasttest) sind auch unter `forward` frei.
  `forward` verlangt einen Schlüssel, prüft ihn aber nicht (das tut die b-api); nur `static`
  schließt beliebige Schlüssel direkter Aufrufer aus.
- **Studio-Proxy:** Er reicht ihn nie durch.
- **Rechte des virtuellen Schlüssels:**
  - Chat und Responses mit `gpt-6-luna` bzw. der Route
  - Moderation (`omni-moderation-latest`)
  - Einbettungen (`text-embedding-3-small`)
  - Audio nur bei `B_API_AUDIO=1`
  - **nicht** `LLM_ROUTE_MANAGE`
- **Modell-Routing:**
  - Eine Route je Dienst, `B_API_ROUTE=<name>`. Sie darf nur Modelle **einer** Familie bündeln. Empfehlung: `gpt-6-luna` (Priorität 0), `gpt-5.6-luna` (Priorität 1).
  - `LLM_CHAT_MODEL` bleibt das Modell, dessen Parameter und Preis gelten.
  - Reihenfolge: erst die Route anlegen, dann die Variable setzen.
  - Einzelheiten: `deploy/README.md`, Abschnitt „Auf eine Route des b-api-Routers umstellen“.
- **Deployment:** `B_API_BASE_URL` muss das Deployment des Proxys nennen (Prod-Proxy → Prod-Adresse).
- **Drosselung hinter dem Proxy:** Die Chat-Drosselung zählt je IP. Die Adresse bestimmt Uvicorn
  aus `X-Forwarded-For` — aber nur, wenn die Anfrage von einer Adresse in `FORWARDED_ALLOW_IPS`
  kommt (in Kubernetes die Pod-CIDR des Ingress; `*` heißt „jedem glauben“ und passt nur, wenn
  8100 allein über den Ingress erreichbar ist). `TRUST_FORWARDED_FOR` bleibt `false`. Reicht der
  b-api-Proxy die Nutzer-Adresse nicht weiter, teilen sich seine Nutzer ein Limit — mit dem
  b-api-Team klären, was der Proxy weitergibt.

**Variante B (direkt).**
- `B_API_KEY` (bzw. `OPENAI_API_KEY`) aus der Umgebung ist der Rückfall: für Direktaufrufe und für alle Hintergrundläufe (Eval, Lasttest, RAG-Import, Vorwärmung). Der Master-Skill-Abruf ist ein MCP-Aufruf und nutzt `MCP_AUTH_TOKEN`.
- Der Chat ist öffentlich und anonym, gedrosselt per IP (`RATE_LIMIT_*`).
- Das Studio verlangt Passwort bzw. `STUDIO_API_KEY`.
- Der Agent-Endpunkt verlangt eine persönliche WLO-Anmeldung oder den Studio-Schlüssel.

## 6 Monitoring

- **Endpunkt:** `/metrics` am internen Port (`prometheus-client`). Er liefert die Basis-Metriken (Prozess, Python, GC) und diese Applikationsmetriken:

| Metrik | Labels |
|---|---|
| `boerdi_http_requests_total` | route (Pfad-Vorlage), method, status |
| `boerdi_http_request_duration_seconds` | route, method |
| `boerdi_http_requests_in_progress` | – (überwiegend offene Zug-Ströme) |
| `boerdi_turns_total` | engine |
| `boerdi_llm_calls_total` | phase, outcome (ok/fehler/abbruch) |
| `boerdi_llm_call_duration_seconds` | phase |
| `boerdi_mcp_calls_total` | server, outcome (ok/tool/transport/timeout/auth) |
| `boerdi_mcp_call_duration_seconds` | server |
| `boerdi_safety_stage_total` | stage (`openai_moderation`, `llm_legal`), outcome (ok/fehler/keine_zugangsdaten/teilweise) |
| `boerdi_build_info` | version |

- **Alarmregeln:** als `PrometheusRule`-Beispiel in `deploy/helm/values.example.yaml`:
  - 5xx-Quote
  - LLM-Fehlerquote
  - p95 der Züge
  - MCP-Transportfehler
  - Moderationsausfall (mehr als die Hälfte scheitert, Paket 18A)
- **Synthetischer Verkehr zählt mit:** Lasttest (im Prozess) und Evaluation (über die
  Loopback-Adresse) laufen durch dieselben Zähler wie echte Nutzer, ohne eigenes Label.
  Während eines Laufs können die Alarme feuern; beides startet nur die Redaktion im Studio.

## 7 Logging und Tracing

- **Ausgabe:** stdout, keine Dateien.
- **Format:** `LOG_FORMAT=json` (eine Zeile je Eintrag: `time` UTC, `level`, `logger`, `message`, `trace_id`, ggf. `exc`) oder `text`.
- **Level:** `LOG_LEVEL`.
- **Trace-ID:**
  - **Quelle**, in dieser Reihenfolge: `x-client-trace-id`, sonst `X-B3-TraceId`/`b3`, sonst neu erzeugt.
  - **Wo sie steht:** in jeder Logzeile der Anfrage, auch in Uvicorns Zugriffszeile.
  - **Wohin sie geht:** an die b-api und den WLO-MCP-Server als `x-client-trace-id`; B3 (`X-B3-TraceId` in Kleinbuchstaben, neue `X-B3-SpanId`) nur, wenn die ID eine gültige B3-ID ist (16 oder 32 Hex-Zeichen). Nicht an OpenAI direkt und nicht an fremde MCP-Server. Nicht zurück an den Client.
- **Optional:** OpenTelemetry-Traces mit `OTEL_EXPORTER_OTLP_ENDPOINT`.

## 8 Datenbank und abschaltbare Bestandteile

- **Postgres 17 mit pgvector:**
  - enthält Sitzungen, Verlauf, Konfiguration, Sperren, Läufe, Qualitätsprotokoll, RAG-Vektoren
  - kein SQLite
- **Valkey:**
  - nur für die Rate-Limit-Zähler über alle Pods
  - ohne Persistenz
  - im Cluster **Pflicht** (`RATE_LIMIT_STORAGE_URI=valkey://…`)
- **Abschaltbar im Chart:** Beide stehen in den Values (`postgresql.enabled`, `valkey.enabled`), eine bestehende Instanz kann genutzt werden.
- **Migrationen:** als Job je Release, nicht je Pod (`migrateJob`).
- **Worker:** keine eigenen. Hintergrundarbeit läuft im Web-Prozess: Aufbewahrung alle 6 h
  (clusterweit einmal per Sperre), Master-Skill-Abruf alle 5 min (clusterweit einmal per Sperre),
  Evaluation und Lasttest als Jobs aus dem Studio. Im Chart gibt es deshalb nichts abzuschalten.

## 9 Zustand und horizontale Skalierung

- **Grundsatz:** Pods sind zustandslos, Sticky Sessions sind nicht nötig. Folgender Zustand liegt in Postgres:
  - Sitzungssperre je Gespräch
  - Konfiguration (Verteilung per `LISTEN/NOTIFY`, < 2 s gemessen)
  - offene Schreibvorgänge
  - Seitenkontext
  - Verlauf: Ein abgerissener Strom holt die Antwort von jedem Pod.
  - Master-Skill-Stand (Abruf durch einen Pod, Verteilung per `NOTIFY`)
  - Lauf-Herzschlag von Evaluation und Lasttest: Ein neuer Pod bricht keinen fremden Lauf ab;
    der Lauf eines beendeten Pods gilt nach 90 s (Lasttest) bzw. 3 min (Evaluation) als verwaist.
- **Caches je Pod:** MCP-Ergebnisse, Vokabular. Sie kosten nur Trefferquote, keine falschen Antworten.
- **Grenzen:**
  - **LLM-Deckel je Pod:** `LLM_MAX_CONCURRENCY` gilt je Pod. Bei N Pods sollte er auf Limit/N stehen.
  - **DB-Verbindungen:** 5+10 je Pod, eine LISTEN-Verbindung und kurz eine für `/ready`. Also `max_connections ≥ N×17 + Reserve` oder PgBouncer (Session-Modus, wegen LISTEN).
  - **MCP-Server:** Er drosselt auf 120 Anfragen je Minute **je IP**, und alle Pods teilen sich eine Egress-IP. Die Freischaltung klärt das MCP-Team.
  - **Herunterfahren:** Gnadenfrist ≥ 70 s (5 s Läufe schließen, 30 s Verbindungen, 25 s Nachlauf, 10 s Abbruch und Aufräumen) **plus** preStop (5 s) plus Luft = 80 s (Values) — Kubernetes zieht preStop von der Frist ab.
- **Abnahme:** `docs/cluster-checkliste.md` (Zusagen 1–8, davon SSE über den Load-Balancer und der verlustfreie Shutdown am laufenden Cluster).
- **Architekturübersicht:** sechs Grafiken in `docs/architektur-grafiken/` (Architektur, Abläufe Agent und Muster, Software-Stack, Konfiguration je Modus) — als PNG unter `png/`, interaktiv lokal über `index.html`.

## 10 Ressourcen

**Vorläufig** (Messung unter Last ausstehend):
- Werte in `deploy/helm/values.example.yaml`: Requests 500m CPU / 1 GiB, Limit 2 GiB.
- Der ganze Stack lief bisher auf 2 Kernen / 4 GB.
- Der Reranker lädt etwa 135 MB ins RAM je Pod.
- Speicher: Postgres wächst mit Verlauf (30 Tage), Qualitätsprotokoll (180 Tage, Nutzertext nach 30 Tagen geleert) und Sicherheitsprotokoll (90 Tage). **Sitzungen und Verbrauchszahlen (`usage_events`) werden nie automatisch gelöscht** — sie wachsen dauerhaft. Das Modell-Volume (1 GiB) braucht es nur mit eingeschaltetem Reranker.

## 11 Konfiguration und Secrets

- **Alle Einstellungen:** `deploy/.env.example` (je Variable Vorgabe und Bedeutung). Ein Test hält die Liste vollständig gegenüber dem Code.
- **Helm-Mapping:** `deploy/helm/values.example.yaml` (`env`, `secretEnv`, `imageEnv`), ebenfalls von einem Test gegen den Code gehalten.
- **Secrets** (in beiden Dateien als Geheimnis gekennzeichnet):
  - `STUDIO_API_KEY`, `STUDIO_PASSWORD`
  - `B_API_KEY`, `OPENAI_API_KEY`
  - `MCP_AUTH_TOKEN`
  - `POSTGRES_PASSWORD`, `DATABASE_URL`
- **Betriebswerte, die der Aufbau bestimmt:** `FORWARDED_ALLOW_IPS` (Ingress-CIDR; im
  Testbetrieb ohne Proxy `127.0.0.1`), `TRUST_FORWARDED_FOR` (`false`), `B_API_KEY_MODE`,
  `B_API_ROUTE`, `RATE_LIMIT_STORAGE_URI` (Valkey), `LOG_FORMAT=json`, `INTERNAL_PORT`.
- **Betriebsentscheid `MODERATION_FAILURE_MODE`** (Paket 18A): `open` (Vorgabe) beantwortet
  einen Zug auch ohne Moderation und macht den Ausfall sichtbar (Zähler, Warnung); `closed`
  antwortet dann mit einer freundlichen Absage — im Chat, bei Direktaktionen und an
  `/api/agent`. Für Schulbetrieb `closed` erwägen; das braucht einen erreichbaren
  Moderationszugang (nicht `b-api-academiccloud`). Einzelheiten: `deploy/README.md`.
- **Umbenannt (2026-10-28, alle Namen englisch):** `RAG_UMWANDLUNG_FRIST_S` →
  `RAG_CONVERSION_TIMEOUT_S`, `RAG_UMWANDLUNG_MAX_MB` → `RAG_CONVERSION_MAX_MB`. Die alten
  Namen wirken übergangsweise weiter, der Start warnt.
- **Fachliche Konfiguration:** Muster, Master-Skill-Optionen, Preise usw. liegen in der Datenbank und werden im Studio gepflegt. Die Werksfassung kommt aus dem Image (`seeds/`).
- **Referenz:** `docker-compose` (`deploy/compose.prod.yml`) dient nur als Referenz.

## 12 Große Daten

- **Reranker-Modell** (ONNX, ~135 MB; nur mit `RAG_RERANKER_ENABLED=true`, Vorgabe aus):
  - nicht im Image
  - Volume `/models`, beim ersten Start geladen (`RERANK_AUTO_DOWNLOAD`) oder per initContainer
  - mehrere Pods teilen es (ReadWriteMany)
- **RAG-Wissen:** Vektoren in Postgres, kein Volume.

## 13 Kosten

- **LLM je Zug** (gemessen 2026-09-27, Golden-Läufe E-5, Listenpreise USD): rund 0,0017 USD im Agent-Modus, 0,0030 USD im Muster-Modus.
- **Wo gebucht wird:**
  - Die b-api bucht auf den durchgereichten Schlüssel.
  - Der Chatbot führt eine eigene Kostenrechnung (Studio → Kosten) mit der Preistafel im Studio.
- **Evaluationen** kosten zusätzlich (Judge, Simulator), werden gesondert gebucht und vom Nutzer gestartet.
- **Externe Dienste:**
  - b-api (LLM)
  - WLO-MCP-Server
  - Hugging Face (einmaliger Modell-Download)

## 14 Ansprechperson

T4 – Jan Schachtschabel (technischer Owner).

## 15 Wartung und Lebenszyklus

- **Abhängigkeiten:**
  - CVE-Prüfung in jeder CI (`pip-audit`), Lizenz-Gate.
  - Python über `uv.lock`, Frontend über `package-lock.json`.
- **Modellwechsel:** über die b-api-Route, ohne Deploy; neue Familie nur mit Anpassung von `LLM_CHAT_MODEL`.
- **Wer Updates anstößt und umsetzt:** *(vom Nutzer einzutragen)*.
