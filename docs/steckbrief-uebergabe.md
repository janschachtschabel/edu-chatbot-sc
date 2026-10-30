# Technischer Service-Steckbrief — BOERDi (WLO-Chatbot)

Nach der Vorlage „Technischer Service-Steckbrief“ (Dienste an den Maschinenraum übergeben).
Stand 2026-10-28, `main` `56671f8` mit Paket 18A/18B ([PR #27](https://github.com/janschachtschabel/edu-chatbot-sc/pull/27)); Erstfassung 2026-10-20 (Paket 17, `2a589a6`). Ausführlich: [Übergabe an den Betrieb](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/uebergabe-betrieb.md).

Status je Punkt: ungeprüft · offen · in Arbeit · erfüllt · nicht anwendbar

| | |
|---|---|
| **Service** | BOERDi – Chatbot von WirLernenOnline (`edu-chatbot-sc`, Arbeitsname `boerdi-chat`) |
| **Technischer Owner** | T4 – Jan Schachtschabel |
| **Readiness Status** | Übergabeprüfung |
| **Offene Punkte** | 10 |
| **Kritische Offene Punkte** | 2 (Ressourcen unter Last messen · SSE-Abstimmung mit Wolli) |
| **Jira** | [GEN-329](https://edu-sharing.atlassian.net/browse/GEN-329) |

## Stammdaten & API

| Punkt | Inhalt | Status |
|---|---|---|
| Anzeigename und Beschreibung | „BOERDi – Chatbot von WirLernenOnline“ · „BOERDi hilft beim Finden und Nutzen offener Bildungsinhalte von WirLernenOnline: Fragen stellen, passende Materialien, Themenseiten und Sammlungen erhalten, Inhalte zusammenfassen lassen.“ (Entwurf, Abnahme durch T4 offen) | in Arbeit |
| Repository-Link | <https://github.com/janschachtschabel/edu-chatbot-sc> (privat; Zugang für T6 einrichten, siehe offene Punkte) | erfüllt |
| OpenAPI Spec | öffentlich: `GET /openapi.json` (Port 8100, 9 Operationen) · [openapi-public.json](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/api/openapi-public.json) · voll: `GET /openapi-full.json` (Port 8101) · [openapi-v1.json](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/api/openapi-v1.json); aus dem Code erzeugt, CI-Gate | erfüllt |
| Pipeline und Git-Tags | GitHub Actions: `ci.yml` (Lint, Tests, Lizenz-Gate, `pip-audit`, OpenAPI-Gate), `image.yml` (Build, Smoke beider Ports, Veröffentlichung nach grünem `ci`). Images `ghcr.io/janschachtschabel/edu-chatbot-sc` (privat): `sha-<7>` (unveränderlich), `latest` (Spitze `main`), SemVer-Tag ab `0.6.0` — erster SemVer-Tag und Pull-Zugang für T6 stehen aus | in Arbeit |
| Endpunkte (öffentliche und Infrastruktur) | **8100 öffentlich:** Widget (`/widget/`), Chat `/api/chat` (+ `/stream`), Agent `/api/agent` (+ `/stream`), Sprache `/api/speech/*`, Verlauf, Studio `/studio/` (hinter Login). **8101 intern:** `/health` (Liveness), `/ready` (Readiness), `/metrics`, `/openapi-full.json` — nicht über den Ingress. `/health` am öffentlichen Port ausblenden; `/api/health` nur mit Studio-Schlüssel | erfüllt |
| Spezielle Header und Content-Types | eingehend (optional): `Authorization: Bearer` (b-api-Schlüssel vom Proxy), `WLO-Access-Block`, `X-Boerdi-Engine`, `Accept-Language`, `x-client-trace-id`/B3. Content-Types: JSON, **`text/event-stream`** (Chat-/Agent-Strom: Pufferung aus, Keepalive alle 10 s, Lese-Timeout ≥ 120 s), `audio/mpeg`, `multipart/form-data`. Rumpf bis 151 MiB (Studio-Upload) → Ingress `proxy-body-size: 160m` | in Arbeit (SSE mit Wolli abstimmen) |
| Asynchrone Job-Endpunkte | Evaluation und Lasttest (nur Studio): Start → Lauf-ID → Status → Abbruch; Herzschlag in der DB, höchstens ein Lasttest | erfüllt |

## Architektur

| Punkt | Inhalt | Status |
|---|---|---|
| Übersicht | FastAPI + LangGraph, Postgres 17 + pgvector, Valkey (nur Ratenlimit), Angular-Widget und -Studio im selben Image; LLM über die b-api, Inhalte über den WLO-MCP-Server. [Architektur](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/architektur.md) · [Grafiken](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/architektur-grafiken/README.md) | erfüllt |
| zustandslos oder zustandsbehaftet | zustandslos: Sitzungen, Verlauf, Konfiguration, Sperren, Läufe und Master-Skill-Stand liegen in Postgres; keine Sticky Sessions | erfüllt |
| Horizontale Skalierbarkeit | ja, feste Replikas. Bedingungen: Valkey fürs Ratenlimit, `LLM_MAX_CONCURRENCY` = Limit/N, `max_connections ≥ N×17 + Reserve`, Gnadenfrist 80 s inkl. preStop 5 s. [Cluster-Checkliste](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/cluster-checkliste.md): 6 von 8 Zusagen automatisiert geprüft; SSE über den Load-Balancer und verlustfreier Shutdown am laufenden Cluster stehen aus | in Arbeit |

## Deployment und Infrastruktur

| Punkt | Inhalt | Status |
|---|---|---|
| Docker-Files | ein Image für alles ([Dockerfile](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/Dockerfile)), nicht root, Einstieg `python -m boerdi.serve`, HEALTHCHECK `/ready`; Compose als Referenz ([compose.prod.yml](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/deploy/compose.prod.yml)) | erfüllt |
| HELM-Chart und Beispiel-Values | Beispiel-Values ([values.example.yaml](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/deploy/helm/values.example.yaml)): Proben am internen Port, Ingress, Ressourcen, Secrets, `migrateJob`, PrometheusRule. Das Chart baut T6 (Absprache) | in Arbeit (Chart: T6) |
| Abschaltbare Komponenten | Postgres und Valkey (bestehende Instanz nutzbar), Reranker (`RAG_RERANKER_ENABLED`, Vorgabe aus), Sprache über b-api (`B_API_AUDIO`), Tracing (`OTEL_EXPORTER_OTLP_ENDPOINT`), Lasttest (`BOERDI_ALLOW_LOADTEST`). Keine eigenen Worker | erfüllt |
| Datenbank | Postgres 17 + pgvector; Migrationen (Alembic, Stand 0016) als Job je Release: `alembic upgrade head && boerdi import-config --werksabgleich`. Aufbewahrung: Verlauf 30 Tage, Qualitätsprotokoll 180 Tage, Sicherheitsprotokoll 90 Tage; Sitzungen und Verbrauchszahlen bleiben | erfüllt |
| Quelle und Volume-Größe für große Daten | Reranker-Modell (ONNX, ~135 MB) nur bei eingeschaltetem Reranker: Volume `/models`, 1 GiB, ReadWriteMany, Download beim Start von Hugging Face (fest gepinnt, Prüfsumme). RAG-Wissen als Vektoren in Postgres | erfüllt |

## Security und Konfiguration

| Punkt | Inhalt | Status |
|---|---|---|
| Authentifizierungskonzept | Chat und Widget öffentlich und anonym, gedrosselt je IP; Studio mit Passwort bzw. `STUDIO_API_KEY`; Agent-Endpunkt mit persönlicher WLO-Anmeldung oder Studio-Schlüssel; Schreiben im Repositorium nur mit persönlicher Anmeldung | erfüllt |
| mit oder ohne B-API | **mit B-API** (Standard, hinter dem b-api-Proxy) | erfüllt |
| mit B-API: welches Modell fürs Routing | siehe **Empfohlene LLM-Route** unten | offen |
| mit B-API: virtueller Key benötigt? | ja — Proxy-Dienst `badboerdichat` mit `forwardApiKey`; der Chatbot nimmt den durchgereichten `Authorization: Bearer` für alle LLM-Aufrufe des Zuges (genau ein Kopf, nie geloggt). Schalter `B_API_KEY_MODE`: `auto` (Vorgabe), `static`, `forward`. Hintergrundläufe nutzen `B_API_KEY` | erfüllt |
| mit B-API: Berechtigungen des Keys | Chat/Responses mit `gpt-6-luna` bzw. der Route, Moderation (`omni-moderation-latest`), Einbettungen (`text-embedding-3-small`), Audio nur bei `B_API_AUDIO=1`; **nicht** `LLM_ROUTE_MANAGE` | erfüllt |
| ohne B-API: LLM-Keys und Authentifizierung | `LLM_PROVIDER=openai` mit `OPENAI_API_KEY` (nur für Tests); bzw. `B_API_KEY` als fester Schlüssel (`B_API_KEY_MODE=static`) | erfüllt |
| **Empfohlene LLM-Route** | `LLM_PROVIDER=b-api-openai`, `LLM_CHAT_MODEL=gpt-6-luna`, `B_API_ROUTE=<Route>` mit **`gpt-6-luna`** (Priorität 0) und als Backup **`gpt-5.6-luna`** (Priorität 1). Die Route darf nur Modelle einer Familie bündeln; Parameter und Preis folgen `LLM_CHAT_MODEL`. Reihenfolge: Route in der b-api anlegen, dann Variable setzen. Auf Staging mit der Testroute `boerdi-test-luna` geprüft (Chat, Werkzeuge, Strom) | offen (Route in Produktion anlegen) |
| Env-Variablen inklusive Defaults | vollständig in [deploy/.env.example](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/deploy/.env.example) (je Variable Vorgabe und Bedeutung) und im Helm-Mapping; ein Test hält beide gegen den Code vollständig. Vom Aufbau bestimmt: `FORWARDED_ALLOW_IPS` (Ingress-CIDR), `TRUST_FORWARDED_FOR=false`, `RATE_LIMIT_STORAGE_URI` (Valkey), `LOG_FORMAT=json`; Betriebsentscheid `MODERATION_FAILURE_MODE`. Alle Namen englisch; umbenannt 2026-10-28: `RAG_UMWANDLUNG_FRIST_S`/`_MAX_MB` → `RAG_CONVERSION_TIMEOUT_S`/`_MAX_MB` (die alten Namen wirken übergangsweise weiter, der Start warnt) | erfüllt |
| Inhaltsprüfung | Regex-Gate (Krise, Drohung, persönliche Daten) läuft immer; dazu Moderation (`omni-moderation-latest`) und Rechtsprüfung über die b-api. Ein Ausfall steht in der Entscheidung und im Zähler, es wird nicht herabgestuft. **Betriebsentscheid `MODERATION_FAILURE_MODE`:** `open` (Vorgabe) antwortet auch ohne Moderation, `closed` antwortet dann mit einer Absage (Chat, Direktaktionen, `/api/agent`) — für Schulbetrieb erwägen, braucht einen Moderationszugang | erfüllt (Modus: Entscheid offen) |
| Benötigte Secrets (ohne Werte) | `STUDIO_API_KEY`, `STUDIO_PASSWORD`, `B_API_KEY`, `OPENAI_API_KEY` (nur ohne B-API), `MCP_AUTH_TOKEN` (optional), `POSTGRES_PASSWORD` bzw. `DATABASE_URL` | erfüllt |

## Monitoring und Betrieb

| Punkt | Inhalt | Status |
|---|---|---|
| Prometheus-Endpunkt | `GET /metrics` am internen Port 8101 (`prometheus-client`, Basis- und Applikationsmetriken); NetworkPolicy für 8101 empfohlen | erfüllt |
| Applikationsmetriken und Alarmregeln | `boerdi_http_requests_total`/`_duration_seconds`/`_in_progress`, `boerdi_turns_total`, `boerdi_llm_calls_total`/`_duration_seconds`, `boerdi_mcp_calls_total`/`_duration_seconds`, `boerdi_safety_stage_total` (Moderation und Rechtsprüfung: ok/fehler/keine_zugangsdaten/teilweise), `boerdi_build_info`. Alarme (PrometheusRule in den Values): 5xx-Quote, LLM-Fehlerquote, p95 der Züge > 60 s, MCP-Transportfehler, Moderationsausfall. Hinweis: Lasttest und Evaluation zählen mit | erfüllt |
| Log-Format und x-client-trace-id | stdout, `LOG_FORMAT=json` (`time`, `level`, `logger`, `message`, `trace_id`). Trace-ID aus `x-client-trace-id`, sonst B3, sonst neu; weitergegeben an b-api und WLO-MCP-Server, nicht an Dritte, nicht zurück an den Client. Keine Inhalte im Log (nur Längen, Sitzung als Kurzkennung, keine IP); Inhalt eines Zugs im Studio über die Trace-ID; `LOG_CONTENT` für eine akute Analyse | erfüllt |

## Ressourcen und Kosten

| Punkt | Inhalt | Status |
|---|---|---|
| CPU, RAM und Storage | vorläufig: Requests 500m CPU / 1 GiB RAM, Limit 2 GiB je Pod; bisher lief der ganze Stack auf 2 Kernen / 4 GB; Reranker +~135 MB RAM. Storage: Postgres wächst mit Sitzungen und Verbrauchszahlen dauerhaft. **Messung unter Last steht aus** | offen |
| Erwartete LLM-Kosten | je Zug rund 0,0017 USD (Agent-Modus) bzw. 0,0030 USD (Muster-Modus), Listenpreise, gemessen 2026-09-27. Gebucht wird auf den durchgereichten b-api-Schlüssel; Kostenübersicht zusätzlich im Studio. Evaluationen kosten extra (Judge, Simulator) | erfüllt |
| Kosten externer APIs | b-api (LLM, siehe oben); WLO-MCP-Server (intern); Hugging Face einmalig für das Reranker-Modell (kostenlos). Sonst keine | erfüllt |

## Übergabe

| Punkt | Inhalt | Status |
|---|---|---|
| Ansprechperson in T4 | Jan Schachtschabel (T4) | erfüllt |
| Bekannte Einschränkungen und offene Punkte | **kritisch:** (1) Ressourcen unter Last messen (Lasttest auf Staging); (2) SSE mit Wolli abstimmen (Pufferung aus, Lese-Timeout ≥ 120 s). **weitere:** (3) empfohlene Route in der Produktions-b-api anlegen und `B_API_ROUTE` setzen; (4) mit dem b-api-Team klären, ob der Proxy die Nutzer-Adresse weitergibt (sonst teilen sich alle Nutzer ein Ratenlimit); (5) MCP-Server drosselt 120 Anfragen/min je IP bei gemeinsamer Egress-IP — Freischaltung durch das MCP-Team; (6) erster SemVer-Tag sowie Zugang zum privaten Repo und Pull-Zugang zur privaten Registry für T6; (7) Beschreibungstext der Spec abnehmen; (8) Wartungsverantwortung festlegen (wer stößt Updates an) und festhalten, wann über den Dauerbetrieb entschieden wird; (9) Testroute `boerdi-test-luna` nach der Abnahme löschen; (10) `MODERATION_FAILURE_MODE` festlegen (`open`/`closed`) | in Arbeit |
| Links zu Betriebsdokumentation und Nachweisen | [Übergabe an den Betrieb](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/uebergabe-betrieb.md) · [Cluster-Checkliste](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/cluster-checkliste.md) · [Betrieb/Runbook](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/deploy/README.md) · [Installation](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/INSTALL.md) · [Änderungsnotiz Paket 17](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/aenderungen/2026-10-20-paket-17.md) · [PR #23](https://github.com/janschachtschabel/edu-chatbot-sc/pull/23) (CI grün; Backend-Suite 6600 Tests, Studio 1813) · [Änderungsnotiz Paket 18A/18B](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/aenderungen/2026-10-28-paket-18ab.md) · [Rückmeldung zum Störtest-Audit](https://github.com/janschachtschabel/edu-chatbot-sc/blob/main/docs/audits/2026-10-28-audit-follow-up.md) · [PR #27](https://github.com/janschachtschabel/edu-chatbot-sc/pull/27) | erfüllt |
