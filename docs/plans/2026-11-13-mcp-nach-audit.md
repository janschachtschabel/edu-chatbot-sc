# MCP nach dem Audit: Änderungsbedarf und Planung (2026-11-13)

Anlass: Der MCP-Entwickler hat die Audit-Nacharbeit P1–P14 umgesetzt (noch nicht committet) und
fünf Entscheide offen gelassen. Dieser Plan beantwortet drei Fragen:

1. Was muss der Chatbot anpassen, weil sich der MCP für Clients sichtbar ändert?
2. Welche Werkzeuge und Änderungen braucht der Chatbot noch vom MCP?
3. Was fehlt dem MCP zum Diensteleitfaden von Team 6?

Dazu kommt eine Empfehlung zu den fünf offenen Entscheiden.

Grundlage: der Arbeitsstand des MCP in `wlo-mcp-server-sc` (nur gelesen, 92 geänderte Dateien)
und der Chatbot auf `main` plus PR #62. Zwei unabhängige Lese-Durchgänge, Kernaussagen
stichprobenartig am Code nachgeprüft. Nichts davon ist gemessen oder im Betrieb getestet.

## 1 Kurzfassung

- **Der Chatbot läuft mit dem neuen MCP ohne Änderung weiter.** Keine der Änderungen bricht einen
  Aufruf. Die neuen Fehlercodes landen aber als „abgelehnt“ ohne Grund bei der Person, und ein
  Ausfall sieht an mehreren Stellen weiter wie „nichts gefunden“ aus.
- **Vier kleine Pakete am Chatbot** (C1–C4) holen den Nutzen der MCP-Änderungen ab. Das größte
  ist C1 „Ausfall ist nicht leer“.
- **Vom MCP brauchen wir weiter vier Dinge:** Messung MA-0 mit eingeschaltetem Stapel-Upload,
  den Ordnerpfad je Datei im Stapel, die Bytes einer privaten Datei und die Messung zu
  `would_replace_file`. Neu dazu: Der MCP soll unsere Trace-Kennung lesen.
- **Zum Diensteleitfaden fehlt dem MCP viel Betriebliches:** zweiter Port, Log-Format und
  Trace-Header, Helm-Chart, getaggte Images, gemessene Ressourcen, Steckbrief, eine Dienst-ID.
  Fachlich ist er weiter als die meisten Dienste (Fehler als JSON, 503 nur vorübergehend,
  gehärtetes Image).
- **Empfehlung zu den Entscheiden:** zuerst Version und Dokumente schneiden (3), dann den
  einheitlichen Vertrag (1) als angekündigte neue Version, danach die Ausgabeschemata (2).
  `WLO_PUBLIC_BASE_URL` (4) zur Pflicht machen, mit einer Version Vorlauf. Sammlungen und Ordner nur beim Einreichen
  ablehnen, Metadaten für Sammlungen offen lassen (5, korrigiert).

## 2 Was der Chatbot anpasst

Je sichtbarer Änderung des MCP, ob der Chatbot betroffen ist:

| Änderung am MCP | Chatbot betroffen | Heute | Paket |
|---|---|---|---|
| `incomplete: true`, `isError` bei Ausfall, Wikipedia `unreachable` | ja | geht an vier Stellen verloren, Ausfall wird „nichts gefunden“ | C1 |
| Vorschläge: `already_decided`, `suggestion_not_marked`, Annehmen ergänzt | ja | „abgelehnt, nichts geändert“ ohne Grund | C2 |
| Anlegen: id trotz Folgefehler (`unverified`, `error.nodeId`, `recordExists`) | ja | „ob sie angekommen ist, kann ich nicht sagen“; die id liest niemand | C2 |
| Stapel: volle Vorschau, `too_many_batches`, 429 `rate_limited` | ja, nur bei eingeschaltetem Upload | `too_many_batches` wird „abgewiesen“; `Retry-After` ungelesen | C2 |
| `already_submitted` bei `wlo_submit_content` | ja | Ablauf endet mit „abgelehnt“ ohne Grund | C2 |
| `/auth/status`: `authority: null` beim Dienstkonto | nein | Dienstkonto galt schon bisher nicht als Person | – |
| `X-Request-Id` in jeder Antwort | nicht genutzt | keine MCP-Kennung in Log und Zugakte | C3 |
| Ordner nicht mehr löschbar (`is_a_folder`), Einordnen legt das Original ab | kaum | „abgelehnt“ ohne Grund | C2 |
| `get_skill` lehnt über 2 MiB und Binärdateien ab | ja | die Ablehnung käme als Anleitung an und würde 180 s gecacht | C4 |
| `WLO_UPSTREAM_CONCURRENCY` (24) | ja | „ausgelastet“ wird schon behandelt; die Stapel-Ablage kennt den Code nicht | C2 |

### C1 Ausfall ist nicht „nichts gefunden“ (mittel)

Der MCP unterscheidet jetzt Ausfall und leere Liste. Der Chatbot verliert das an vier Stellen:

- **Cache** (`services/mcp/client.py`, `tool_cache.py`): Geprüft wird nur `missing`. Eine
  unvollständige Liste und Wikipedia `unreachable` bleiben 300 s im Cache.
- **Kürzung für die KI** (`domain/tool_result_redaction.py`): Von `search_wlo_collections` und
  `search_wlo_all` bleiben nur `total`, `count`, `results`. `incomplete` und der Hinweissatz
  fallen weg.
- **Karten-Ernte** (`services/mcp/parsers/`): Die Parser lesen nur `results`. Ein Fehlertext
  ergibt eine leere Liste.
- **Wege ohne KI** (`services/card_pipeline.py`, `services/topic_pages.py`): Sie prüfen keinen
  Fehler. Ein Ausfall zeigt eine leere Box; M16 schreibt „eventuell noch leer oder nicht
  freigegeben“.

Zu tun:

1. `incomplete` und `unreachable` nicht cachen (wie `missing`).
2. `incomplete` und den Hinweissatz in der Kürzung behalten.
3. In den Karten-Wegen Fehler, „unvollständig“ und „leer“ trennen, mit je eigenem Satz für die
   Person („WLO hat gerade nicht geantwortet“ statt „nichts gefunden“).

Mit `WLO_UPSTREAM_CONCURRENCY` wird das wichtiger: Die Lesehelfer des MCP stufen einen vollen
Durchlass zu „leer“ herab, und der Vorabruf des Chatbots feuert je Zug drei bis vier Aufrufe
parallel.

### C2 Neue Fehlercodes mit Grund zeigen (klein)

Die Behandlung der Codes ist im Chatbot verstreut (`write_approval.py`, `plan_fortsetzen.py`,
`mcp_ablage.py`, `abdeckung.py`). Ein unbekannter Code führt nie zum Absturz, aber zu „WLO hat
abgelehnt“ ohne Grund.

- In `_GRUND_ZEIGEN` (`services/write_approval.py`): `already_decided`, `suggestion_not_marked`,
  `already_submitted`, `is_a_folder`, `is_a_collection`.
- Anlegen: ein Zweig für `recordExists`. Der Satz sagt, dass der Datensatz angelegt ist und
  nachgetragen statt neu angelegt wird. Die id aus `error.nodeId` wird für den Folgezug und den
  Ablauf gemerkt. Das schließt unseren Befund 4 aus der Rückmeldung vom 07.11.
- Stapel-Ablage (`services/ablage/mcp_ablage.py`): `too_many_batches` auf den vorhandenen Text
  „Stapel offen“ legen, `upstream_busy` auf „voll“ (wiederholbar), bei 429 `Retry-After` lesen.
- Texte: Die Beschreibung von `wlo_decide_suggestion` und M18 sagen, dass Annehmen ergänzt und
  nur offene Vorschläge entscheidbar sind.

Folgearbeit, nicht Teil des Pakets: eine gemeinsame Tabelle Code → Text statt fünf Listen.

### C3 Eine Kennung für beide Logs — entfallen

Stand 13.11. nach dem Review: nicht umgesetzt. Der Arbeitsstand des MCP liest
`x-client-trace-id` und B3 inzwischen selbst und loggt unsere Trace-ID als `client_trace_id`.
Eine gemeinsame `X-Request-Id` nähme dem MCP seine Kennung je Anfrage. Der ursprüngliche Plan:

Der Chatbot sendet `x-client-trace-id` und B3, der MCP liest beides nicht. Der MCP übernimmt
aber ein mitgeschicktes `X-Request-Id` (8 bis 64 Zeichen), und unsere Trace-ID passt in dieses
Format. An den drei Sende-Stellen (`services/mcp/client.py`, `http_fabrik.py`,
`mcp_ablage.py`) zusätzlich `X-Request-Id: <Trace-ID>` senden. Die Fehlernummer aus der
Chat-Blase ist dann im MCP-Log suchbar. Das entfällt, sobald der MCP `x-client-trace-id` liest
(Abschnitt 3, W5).

### C4 Abgelehnte Anleitung nicht als Anleitung übernehmen (klein)

`get_skill` meldet eine Ablehnung als Erfolgstext mit neuer Schlusszeile. `_keine_anleitung`
(`services/master_skill.py`) kennt nur die alte Zeile. Beide neuen Zeilenanfänge aufnehmen, auch
in `_FEHLTREFFER` und in der Prüfung der Werkzeug-Schleife. Der Master-Skill selbst ist mit rund
27 000 Zeichen weit unter der Grenze von 2 MiB.

### Reihenfolge und Verträglichkeit

- C1 bis C4 sind mit dem alten und dem neuen MCP verträglich. Die Reihenfolge der Deploys ist
  frei.
- Vorschlag: C2 bis C4 als ein Paket (ein Tag), C1 als eigenes Paket mit Review.
- Doku nachziehen: `docs/mcp-rueckmeldung-2026-11-07.md` (Befund 4 erledigt),
  `offene-befunde-und-todo.md` (`get_skill` ohne Größengrenze erledigt).

## 3 Was der Chatbot vom MCP braucht

Stand im MCP laut Lesedurchgang: 56 Werkzeuge, davon 4 für den Stapel hinter
`WLO_BATCH_UPLOAD_ENABLED`.

| Nr. | Wunsch | Wofür | Stand im MCP |
|---|---|---|---|
| W1 | Messung MA-0 (Ordnerrecht, Dateiarten, `textContent`), dann `WLO_BATCH_UPLOAD_ENABLED` einschalten | „In den persönlichen Bereich übertragen“ und der Ablauf „Themenbaum · aus eigenen Inhalten“ wirken erst dann | offen; Live-Nachweis scheitert, weil Staging mit 500 antwortet |
| W2 | Ordnerpfad oder Index je Datei im Stapel | Dienst `ablage_zuordnen`: Dateien den Punkten des Themenbaums zuordnen | fehlt; Einträge tragen nur Titel, Prüfsumme, Größe, Endung, Rolle; abgelegt wird flach |
| W3 | Bytes einer privaten Datei (Werkzeug oder HTTP-Pfad, mit den Rechten der Person) | Umwandlung im Chatbot über die nodeId (AS-T) | fehlt; `eduservlet/download` 403 und `GET …/content` 405 sind gemessen |
| W4 | Messung zu `would_replace_file`, danach Volltext auch an Datensätze mit Datei | Volltext an hochgeladene Inhalte (trifft den Upload-Fall immer) | offen, wartet auf den Repository-Fix (`POST textContent` gibt 500) |
| W5 | `x-client-trace-id` und B3 lesen, in die Logzeile schreiben und ans Repository weitergeben | Fehlersuche über Chatbot, MCP und Repository; verlangt auch der Leitfaden | **erledigt** im Arbeitsstand vom 13.11. (`request-id.ts`) |
| W6 | Maschinenlesbare Ablehnung bei `get_skill` | C4 ohne Textvergleich | **erledigt** im Arbeitsstand vom 13.11. (`contentLoaded`, `contentRefused`) |
| W7 | Client-Schlüssel tauschen, Herkunftslisten melden, Widerruf über den Client-Schlüssel zählen | Budget und Anmeldung bei vielen Personen | offen seit 07.11. |
| W8 | Lasttest mit 30 Personen, Ursache der kalten ersten Suche (22 s) | Stabilität | Lasttest liegt bei uns |

Neue Werkzeuge über W2 und W3 hinaus braucht der Chatbot derzeit nicht. Die Kestra-Flows steuert
der Chatbot selbst über die B-API (Entscheid 07.11.). Sammlungen aus einem Entwurf anlegen
(`wlo_create_collection_tree`) gibt es schon; der Ablaufschritt dazu ist zurückgestellt (N15).

W2 und W3 hängen an Fragen an das Repository-Team (T1, Rechte am Download). Ohne Antwort kann
der MCP sie nicht bauen.

## 4 Empfehlung zu den fünf Entscheiden

| Nr. | Entscheid | Empfehlung | Begründung aus Sicht des Chatbots |
|---|---|---|---|
| 3 | Dokumente und Version | **zuerst, ja** | Ohne geschnittene Versionen gibt es kein getaggtes Image, kein Chart je Version und keine Kompatibilitätsmatrix. `/health` meldet immer 1.0.0, der Chatbot kann den Stand des MCP nicht erkennen. |
| 1 | Einheitlicher Vertrag (A-3) | **ja, als neue Hauptversion mit Vorlauf** | Der Chatbot wertet Codes aus und gewinnt am meisten: eine Form für „nicht gefunden“, Weiterblättern überall. Es ändert Antwortformen, darum angekündigt, mit Liste der Änderungen, und der Chatbot zieht in einem Paket nach. |
| 2 | Ausgabeschemata der zwölf Lesewerkzeuge | **ja, nach A-3** | Für Clients additiv. Vor A-3 würde jede Form zweimal festgeschrieben. Mit `additionalProperties: false` ist jedes spätere Feld eine Vertragsänderung, darum erst nach der Vereinheitlichung. |
| 4 | OAuth nur mit `WLO_PUBLIC_BASE_URL` | **ja, mit einer Version Vorlauf** | Die Adresse aus dem Host-Kopf zu bilden ist hinter Ingress oder B-API ohnehin falsch und ein Risiko. Erst die Variable auf dem vServer setzen und prüfen, die Startwarnung eine Version stehen lassen, dann erzwingen. |
| 5 | Sammlungen und Ordner in `wlo_update_content[s]`, Vorschlägen und `wlo_submit_content` ablehnen | **nur beim Einreichen ablehnen; Metadaten und Vorschläge für Sammlungen offen lassen** (korrigiert am 13.11.) | Redaktionen pflegen die Metadaten von Sammlungen wie die von Inhalten; die Felder sind dieselben. Nur Titel und Beschreibung liegen bei Sammlungen in anderen Feldern (`cm:title`, `cm:description`) und gehören über `wlo_rename_collection`. |

Zu 5: Die erste Fassung dieser Empfehlung lautete „ablehnen“. Sie stützte sich darauf, dass
der Chatbot den Weg nicht nutzt, und übersah, dass Redaktionen Sammlungen wie Inhalte pflegen
(Nutzer-Hinweis 13.11.). Offen ist, ob die Kurations-Anleitung (M18) der KI sagen soll, dass
`wlo_update_content` auch für Sammlungen gilt und Titel und Beschreibung über
`wlo_rename_collection` laufen.

## 5 Der MCP und der Diensteleitfaden

Der MCP ist kein Dienst wie „Kompendiale Texte“: Er ist der Zugang zum Repository, nutzt kein
LLM und wird von MCP-Clients (ChatGPT, Claude, der Chatbot) direkt angesprochen. Zwei Kapitel
des Leitfadens gelten deshalb nur eingeschränkt.

**Als Ausnahme zu begründen (im Steckbrief):**

- **Betrieb ohne B-API** (Leitfaden 2.2, „Ausnahme“): Der MCP hat eine eigene Anmeldung (anonym,
  Dienstkonto, Person über OAuth 2.1, Zugangs-Token oder Ticket). `Authorization` trägt den
  WLO-Zugang, keinen B-API-Schlüssel. Hinter der B-API müsste diese den Header unverändert
  durchreichen, den Strom nicht puffern und die OAuth-Pfade durchlassen. Der Leitfaden verlangt
  für die Ausnahme: Begründung, eigene Auth, zwei Ports, Doku der Env für T6.
- **Repository-Bindung** (Leitfaden 1): Der MCP ist an WLO gebunden (Vokabulare im Code,
  `ccm:oeh_*` an 161 Stellen, feste Wurzel-Kennung, Gruppe `GROUP_ORG_WLO-Uploadmanager`). Als
  „WLO-Zugang“ begründen.
  - **Nutzer-Entscheid 13.11.:** Die Adresse des Repositoriums bleibt fest in der Env des MCP
    (`WLO_REPOSITORY_URL`), weil es je Repository genau einen MCP gibt. Das ist die Begründung
    für die Abweichung vom Leitfaden im Steckbrief.
  - Vorschlag, kein Muss: die Staging-Vorgabe im Code streichen, damit eine vergessene Variable
    nicht still auf Staging zeigt.

**Lücken zum Leitfaden:**

| Thema | Stand | Was fehlt |
|---|---|---|
| Dienst-ID | drei Namen (`wlomcp`, `wlo-mcp`, `wlo-mcp-sc`) | ein Name für Image, Chart, Log-Feld `service`, Proxy-Eintrag |
| Version | 1.0.0, keine Tags, Changelog nur „Unreleased“ | Versionen schneiden (Entscheid 3) |
| Ports | ein Port; `/health`, `/ready`, `/metrics` öffentlich | interner Port für die drei Pfade |
| Readiness | `/ready` meldet 503, wenn das Repository nicht antwortet | als Readiness nähme ein Repository-Ausfall alle Pods heraus; trennen in „Prozess bereit“ und „Repository erreichbar“ (Metrik oder Alarm) |
| Logging | JSON nach stderr mit `ts, level, name, msg, req` | stdout, Feldnamen `timestamp, service, trace_id, span_id, message`, `LOG_LEVEL`; Logs tragen IP, Benutzername, Suchbegriff |
| Tracing | im Arbeitsstand vom 13.11.: `x-client-trace-id` und B3 gelesen, geloggt (`trace_id`, `span_id`, `client_trace_id`) und ans Repository weitergegeben | – |
| Metriken | Zähler für Anfragen, Werkzeuge, Repository-Aufrufe | Histogramme, Prozessmetriken, Alarmregeln im Chart |
| Zustand | eine Instanz; Bestätigungen, Pläne, Stapel, OAuth-Codes, Limiter im Speicher; Zugangsliste auf Platte | `replicas: 1` mit PVC festschreiben oder gemeinsamer Speicher (Redis); im Steckbrief sagen, was mit mehreren Pods nicht geht |
| Ressourcen | 512 MB und 1 CPU in Compose, nicht gemessen | Leerlauf, warm, Spitze messen (Spitze: Uploads bis 128 MB, Volltext-Pläne bis 64 MiB) |
| Build | Multi-Stage, Digest, nicht root, `npm audit`, Starttest | CI taggt und veröffentlicht kein Image; Compose nutzt `latest` |
| Helm | kein `deploy/` | Chart mit NetworkPolicy, ServiceMonitor, PrometheusRule, Secrets getrennt |
| API-Beschreibung | keine OpenAPI | OpenAPI für die REST-Nebenpfade (`/api/…`, `/auth/…`); für die Werkzeuge gilt `tools/list` |
| Antwortzeiten | Latenzmessung vorhanden | Tabelle je Werkzeug; Schreibvorgänge bis 60 s und Pläne in 40-s-Scheiben nennen (Proxy-Timeout) |
| Übergabe | – | Steckbrief, Eintrag in der Kompatibilitätsmatrix, Ansprechperson und Vertretung |

**Erfüllt oder nicht anwendbar:** kein LLM (Kapitel 2.1 entfällt), keine Daten im Image, Fehler
als JSON mit 4xx und 5xx getrennt, 503 nur für vorübergehende Ausfälle mit `Retry-After`, Image
läuft nicht als root, Dependabot.

**Vorschlag für die Reihenfolge am MCP** (Pakete des MCP-Entwicklers, nicht unsere):

1. Version schneiden, Dienst-ID festlegen, Audit-Nacharbeit committen (Voraussetzung für alles).
2. Betrieb: zweiter Port, Log-Format mit Trace-Headern, `LOG_LEVEL`, Readiness trennen.
3. Ressourcen messen, Zustand dokumentieren (`replicas: 1`).
4. CI mit getaggtem Image, Helm-Chart mit NetworkPolicy und Alarmregeln.
5. Steckbrief, Kompatibilitätsmatrix, OpenAPI der Nebenpfade.
6. Einheitlicher Vertrag (A-3) als neue Hauptversion, danach die Ausgabeschemata.

Mit T6 vorab zu klären: ob der MCP als Ausnahme „ohne B-API“ übernommen wird und wer das Chart
pflegt (Leitfaden Kapitel 8).

## 6 Umsetzung am Chatbot (Stand 13.11.)

C1, C2 und C4 sind umgesetzt, je mit unabhängigem Review. Abweichungen vom Plan oben:

- **C2, eigene Sätze statt Servertext:** Die neuen Ablehnungen (`already_decided`,
  `already_submitted`, `is_a_folder`, `is_a_collection`, `not_a_record`) bekommen eigene Sätze
  in Deutsch und Englisch. Der Text des Servers ist an die KI gerichtet und nennt Werkzeuge und
  Status-Kennungen.
- **C2, `suggestion_not_marked`:** kein eigener Satz. Der Code kommt nur nach der Einlösung und
  wird dort neu vorgelegt oder führt zu „bitte in WLO nachsehen“.
- **C2, `too_many_batches`:** wird „voll“ (wiederholbar), nicht „Stapel offen“. Der Server sagt
  nicht, ob eigene Stapel offen sind oder der Server insgesamt voll ist (Wunsch W8 an den MCP).
  `Retry-After` am Upload wird weiter nicht gelesen.
- **C2, `recordExists`:** Die Kennung steht im Satz an die Person. Ein Ablauf merkt sie nicht;
  er endet wie bei jedem offenen Ausgang. Die Kennung liest der Client auch neben `error`
  (Wunsch W9).
- **C2, `upstream_busy` mit offenem Ausgang** in der Ablage wird „zu langsam“ statt „voll“:
  Die Datei kann abgelegt sein.
- **C3:** entfallen, siehe oben.
- **C4:** Die Prüfung sitzt in beiden Schleifen (Muster-Weg und Agent). Sie vergleicht weiter
  die Schlusszeile des Textes; das neue Feld `contentRefused` nutzt sie noch nicht.
  `_FEHLTREFFER` im Cache ist nicht erweitert: Die Ablehnung ist ein fester Zustand der Datei
  und darf 180 Sekunden im Cache stehen; gemerkt wird sie nicht.
- **C1, Cache:** Eine unvollständige Antwort steht 30 Sekunden im Cache, nicht gar nicht
  (zweites Review). Bei Überlast träfe sonst jeder Wiederholversuch den MCP. Wo der Server
  einen dauerhaften Zustand so meldet (etwa 403 an einer Unterliste), würde sonst bei jedem
  Aufruf neu geholt.
- **C1, Geltung:** Die Erkennung gilt nur für die Such- und Listen-Werkzeuge
  (`mcp_unvollstaendig.WERKZEUGE`), nicht für Anleitungen, Volltexte oder fremde MCP-Server.
  Die Skill-Suche zählt nicht, weil ihr Kennzeichen auch für dauerhafte Grenzen steht.
- **C1, Sammlungsbaum:** `browse_collection_tree` meldet einen nicht gelesenen Zweig als
  `childrenUnread`. Das war im Plan nicht genannt und kam im zweiten Review dazu.

Notiz: `docs/aenderungen/2026-11-13-mcp-nach-audit.md`.

## 7 Offene Fragen

1. Erledigt: C1, C2 und C4 sind umgesetzt (Abschnitt 6).
2. Erledigt: `docs/mcp-rueckmeldung-2026-11-13.md`, seit dem Abend des 13.11. in zweiter Fassung. Sie trennt, was der MCP-Entwickler direkt umsetzen kann (D1 bis D13), von dem, was eine Entscheidung des Nutzers braucht (Version, Dienst-ID, Reihenfolge der Entscheide 1, 2 und 4) oder an anderen Stellen hängt (W1 bis W4, W7, Team 6).
3. Zu Entscheid 5: Pflegen Redaktionen heute Beschreibung oder Schlagworte von Sammlungen über
   den MCP? Wenn ja, braucht es dafür erst ein eigenes Werkzeug.
4. Der Chatbot selbst ist hier nicht gegen den Diensteleitfaden geprüft. Soll das ein eigener
   Abgleich werden?
