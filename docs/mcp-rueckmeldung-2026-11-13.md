# Rückmeldung an den MCP nach der Audit-Nacharbeit (2026-11-13, zweite Fassung)

Antwort des Chatbot-Teams auf den Stand „Audit-Nacharbeit P1–P14“ und auf deinen Nachtrag
„Rückmeldung des Chatbot-Teams — der vertragsneutrale Teil ist umgesetzt“. Gelesen wurde dein
Arbeitsstand in `wlo-mcp-server-sc` (noch nicht committet) und der Chatbot-Code. Gemessen oder im
Betrieb getestet ist davon nichts.

Diese Fassung ersetzt die erste vom selben Tag. Neu sind Abschnitt 2 (was du direkt umsetzen
kannst) und die Entscheide des Nutzers in Abschnitt 3. Die Empfehlung zu Entscheid 5 ist
korrigiert.

## 1 Stand auf beiden Seiten

**Verträglichkeit:** Der Chatbot läuft mit deinem Stand ohne Änderung weiter. Du kannst committen
und deployen, ohne auf uns zu warten.

**Von dir schon umgesetzt, danke:** voller Durchlass wird nicht mehr zu „leer“ (`incomplete`,
`childrenUnread`, `source_unreachable`), der parsebare erste Block im Leerfall, W5 (Trace-Kennung
gelesen, geloggt, weitergegeben) und W6 (`contentLoaded`, `contentRefused` bei `get_skill`).

**Im Chatbot umgesetzt** (noch nicht ausgerollt; je Änderung von dir in Abschnitt 7, was wir
dir noch schulden in Abschnitt 8):

- Ein Ausfall kommt bei der Person nicht mehr als „nichts gefunden“ an. Wir erkennen
  `incomplete`, `childrenUnread`, `unreachable` und `reason: source_unreachable`, halten solche
  Antworten nur 30 Sekunden im Cache und reichen deinen Hinweissatz bis zur KI durch.
- Die neuen Ablehnungen (`already_decided`, `already_submitted`, `is_a_folder`,
  `is_a_collection`, `not_a_record`, `too_many_batches`) bekommen eigene Sätze. Deinen Text
  zeigen wir der Person nicht, er ist an die KI gerichtet und nennt Werkzeuge.
- Bei `recordExists` nennen wir die Kennung des Datensatzes, statt „ob es angekommen ist, kann
  ich nicht sagen“.
- Eine abgelehnte Anleitung (`get_skill`, zu groß oder kein Text) gilt nicht mehr als Anleitung.
- Wir senden keine eigene `X-Request-Id`. Deine Kennung je Anfrage bleibt erhalten, unsere
  Trace-ID steht als `client_trace_id` in deinem Log.

## 2 Was du direkt umsetzen kannst

Für diese Pakete braucht es keine weitere Entscheidung und keine andere Stelle. Sie ändern für
bestehende Clients nichts oder fügen nur etwas hinzu. Wir empfehlen, sie in dieser Reihenfolge
umzusetzen.

### Fachlich, klein

| Nr. | Paket | Warum direkt | Für den Chatbot |
|---|---|---|---|
| D1 | `wlo_submit_content` lehnt Sammlungen und Ordner ab (`is_a_collection`, `is_a_folder`) | Entscheid 5 ist für diesen Teil gefallen (Abschnitt 3) | Sätze dafür sind schon da |
| D2 | Titel und Beschreibung an einer **Sammlung** über `wlo_update_content[s]` und die Vorschlags-Werkzeuge nicht ins falsche Feld schreiben: an `wlo_rename_collection` verweisen oder dorthin leiten. Dazu in der Beschreibung der Werkzeuge sagen, dass sie auch für Sammlungen gelten | Kein Verhalten wird geschlossen, eine stille Fehlschreibung fällt weg | Die KI weiß dann, dass sie Sammlungs-Metadaten so pflegen darf |
| D3 | Bei `recordExists: true` die Kennung immer in `error.nodeId` (W9) | additiv | Wir lesen sie heute in zwei Fällen neben `error` |
| D4 | `scope` an `too_many_batches`: `owner` oder `server` (W8) | additiv | Wir können dann sagen, ob die Person einen eigenen Stapel abschließen oder nur warten soll |
| D5 | Bei `search_skill` den Grund für `incomplete` nennen: Ausfall oder dauerhafte Grenze (W11) | additiv | Wir werten `incomplete` dort heute gar nicht, weil es beides heißt |
| D6 | „Nicht erreichbar“ von „nicht lesbar“ trennen: 403 und 404 des Repositoriums nicht als `reachable: false` melden (W10) | macht `incomplete`, `childrenUnread` und `source_unreachable` genauer; kein Client verlässt sich auf den heutigen Zustand | Wir sagen sonst „hat gerade nicht geantwortet, versuch es noch einmal“, obwohl es dauerhaft so bleibt |
| D7 | `incomplete: true` auch in den JSON-Text von `search_wlo_collections` und in den Teilausfall von `search_wlo_topic_pages` | additiv; im strukturierten Teil steht es schon | Wir erkennen den Ausfall dort heute am Wortlaut deines Hinweissatzes |

Zu D2: Titel und Beschreibung liegen bei einer Sammlung in `cm:title` und `cm:description`, bei
einem Inhalt in `cclom:title` und `cclom:general_description`. Aus deinem Code gelesen
(`services/write/fields.ts`, `collections.ts`), nicht gemessen.

Zu D6: Den Code kannst du sofort umstellen. Der Live-Nachweis, welche Status das Repository
wirklich liefert, geht erst, wenn Staging wieder antwortet.

Zu D7, solange es das Feld nicht gibt: Wir erkennen deine Hinweise an vier Wendungen. Bitte lass
sie stehen oder sag uns Bescheid, wenn du sie änderst: „hat nicht (vollständig) geantwortet“,
„war nur teilweise erreichbar“, „ließ(en) sich gerade nicht lesen“, „Wikipedia hat gerade nicht
geantwortet“.

### Betrieb nach dem Diensteleitfaden, ohne Wirkung auf Clients

| Nr. | Paket | Warum direkt |
|---|---|---|
| D8 | Logging: im HTTP-Modus nach stdout, Feldnamen `timestamp, level, service, trace_id, span_id, message`, Stufe per `LOG_LEVEL` | Nur das Log ändert sich. Unter stdio bleibt stderr, dort ist stdout der Protokollkanal |
| D9 | Metriken: Histogramme für Dauern und die üblichen Prozessmetriken | additiv, weiter hinter `METRICS_TOKEN` |
| D10 | Zweiter, interner Port für `/health`, `/ready`, `/metrics` als Zusatz (etwa `INTERNAL_PORT`) | Die Pfade bleiben vorerst auch am öffentlichen Port; entfernt werden sie dort erst mit dem Chart |
| D11 | Ressourcen messen (Leerlauf, warm, Spitze mit Upload bis 128 MB und Volltext-Plan bis 64 MiB) und den Zustand beschreiben: was im Speicher liegt, warum nur eine Instanz | reine Messung und Doku |
| D12 | OpenAPI für die REST-Nebenpfade (`/api/…`, `/auth/…`), Tabelle der Antwortzeiten je Werkzeug | Doku; für die Werkzeuge gilt weiter `tools/list` |
| D13 | Entwurf für Helm-Chart (`replicas: 1`, PVC, NetworkPolicy, Alarmregeln) und Steckbrief | Dateien ohne Wirkung auf die laufende Installation; Name und Ports folgen aus Abschnitt 3 |

Zur Readiness braucht es keinen Code: `/ready` bleibt die Auskunft „Repository erreichbar“. Das
Chart nimmt `/health` für beide Proben. Sonst nähme ein Ausfall des Repositoriums alle Pods aus
dem Dienst. Die Erreichbarkeit des Repositoriums gehört in einen Alarm.

## 3 Was eine Entscheidung des Nutzers braucht

| Thema | Stand | Was daraus folgt |
|---|---|---|
| Entscheid 5, Sammlungen | **entschieden:** Redaktionen pflegen die Metadaten von Sammlungen wie die von Inhalten. `wlo_update_content[s]` und die Vorschlags-Werkzeuge bleiben für Sammlungen offen. Nur das Einreichen lehnt Sammlungen und Ordner ab | D1 und D2 |
| Adresse des Repositoriums | **entschieden:** Sie bleibt fest in der Env (`WLO_REPOSITORY_URL`). Es gibt je Repository genau einen MCP | Das ist die Begründung für die Abweichung vom Leitfaden und gehört in den Steckbrief |
| Staging-Vorgabe im Code | Vorschlag von uns, kein Muss, nicht entschieden: streichen, damit eine vergessene Variable nicht still auf Staging zeigt | erst nach einem Ja; es bräche Installationen ohne die Variable |
| Entscheid 3, Version und Dokumente | Empfehlung: jetzt schneiden, zum Beispiel 1.1.0 für den Stand nach dem Audit. Nicht entschieden | Voraussetzung für getaggte Images, Chart je Version und `/health` mit echter Version |
| Dienst-ID | Empfehlung: `wlo-mcp` (so heißen schon Compose-Dienst, Log-Feld und `/health`). Nicht entschieden | Image, Chart, Proxy-Eintrag, Feld `service` |
| Entscheide 1, 2 und 4 | Empfehlung zur Reihenfolge unten. Nicht entschieden | siehe unten |
| Veröffentlichtes Image aus der CI | Registry und Sichtbarkeit sind offen | Workflow lässt sich vorbereiten |

**Unsere Empfehlung zur Reihenfolge der Entscheide 1, 2 und 4:**

1. **Einheitlicher Vertrag (A-3):** nicht in den laufenden Stand, sondern als neue Hauptversion
   mit Ankündigung und einer Liste „alt → neu“. Der Chatbot wertet die heutigen Formen aus und
   zieht dann in einem Paket nach. Sofort eingebaut müsste der Chatbot am selben Tag mit
   ausgerollt werden.
2. **Ausgabeschemata:** erst nach A-3. Vorher würdest du jede Form zweimal festschreiben.
3. **`WLO_PUBLIC_BASE_URL` als Pflicht:** erst die Variable auf dem Server setzen und prüfen, die
   Startwarnung eine Version stehen lassen, dann erzwingen. Sonst fällt die OAuth-Anmeldung nach
   dem Update aus.

## 4 Was an anderen Stellen hängt

| Nr. | Wunsch | Wofür | Hängt an |
|---|---|---|---|
| W1 | Messung MA-0 (Ordnerrecht, Dateiarten, `textContent`), dann `WLO_BATCH_UPLOAD_ENABLED` einschalten | „In den persönlichen Bereich übertragen“ und der Ablauf „Themenbaum aus eigenen Inhalten“ | Staging antwortet mit 500 |
| W4 | Messung zu `would_replace_file`, danach Volltext auch an Datensätze mit Datei | Volltext an hochgeladene Inhalte | Repository-Fix (`POST textContent` gibt 500) |
| W2 | Ordnerpfad oder Index je Datei im Stapel | Dateien den Punkten eines Themenbaums zuordnen | Frage ans Repository-Team (Ordnerliste im eigenen Bereich) |
| W3 | Bytes einer privaten Datei, mit den Rechten der Person | Umwandlung im Chatbot über die nodeId | Frage ans Repository-Team (`eduservlet/download` 403, `GET …/content` 405) |
| W7 | Client-Schlüssel tauschen, Herkunftslisten melden, Widerruf über den Client-Schlüssel zählen | Budget und Anmeldung bei vielen Personen | Abstimmung zwischen uns |
| – | Übernahme als Ausnahme „Betrieb ohne B-API“, Pflege des Charts | Übergabe an den Betrieb | Team 6 |

Sag Bescheid, wenn wir die Fragen zu W2 und W3 mittragen sollen.

## 5 Der MCP und der Diensteleitfaden von Team 6

Der MCP ist kein Dienst wie „Kompendiale Texte“: Er ist der Zugang zum Repository, nutzt kein LLM
und wird von MCP-Clients direkt angesprochen. Zwei Punkte gelten deshalb nur eingeschränkt und
gehören als Begründung in den Steckbrief.

- **Betrieb ohne B-API** (Leitfaden 2.2, „Ausnahme“): eigene Anmeldung (anonym, Dienstkonto,
  Person über OAuth 2.1, Zugangs-Token oder Ticket). `Authorization` trägt den WLO-Zugang,
  keinen B-API-Schlüssel. Der Leitfaden verlangt für die Ausnahme: Begründung, eigene Auth, zwei
  Ports, Doku der Env für T6.
- **Repository-Bindung** (Leitfaden 1): Vokabulare im Code, `ccm:oeh_*`, feste Wurzel-Kennung,
  `GROUP_ORG_WLO-Uploadmanager`, feste Adresse in der Env. Begründung: ein MCP je Repository.

| Thema | Stand | Was fehlt | Paket |
|---|---|---|---|
| Dienst-ID | drei Namen (`wlomcp`, `wlo-mcp`, `wlo-mcp-sc`) | ein Name | Abschnitt 3 |
| Version | 1.0.0, keine Tags, Changelog nur „Unreleased“ | Versionen schneiden | Abschnitt 3 |
| Ports | ein Port; `/health`, `/ready`, `/metrics` öffentlich | interner Port | D10 |
| Readiness | `/ready` meldet 503, wenn das Repository nicht antwortet | nicht als Readiness-Probe nutzen | Chart (D13) |
| Logging | JSON nach stderr mit `ts, level, name, msg, req` | stdout, Feldnamen, `LOG_LEVEL`; Logs tragen IP, Benutzername und Suchbegriff | D8 |
| Tracing | `x-client-trace-id` und B3 gelesen, geloggt, weitergegeben | – | erledigt |
| Metriken | Zähler für Anfragen, Werkzeuge, Repository-Aufrufe | Histogramme, Prozessmetriken, Alarmregeln | D9, D13 |
| Zustand | eine Instanz; Bestätigungen, Pläne, Stapel, OAuth-Codes und Limiter im Speicher, Zugangsliste auf Platte | `replicas: 1` mit PVC festschreiben; im Steckbrief sagen, was mit mehreren Pods nicht geht | D11, D13 |
| Ressourcen | 512 MB und 1 CPU in Compose, nicht gemessen | Messung | D11 |
| Build | Multi-Stage, Digest, nicht root, `npm audit`, Starttest | die CI taggt und veröffentlicht kein Image; Compose nutzt `latest` | Abschnitt 3 |
| Helm | kein `deploy/` | Chart mit NetworkPolicy, ServiceMonitor, PrometheusRule, Secrets getrennt | D13 |
| API-Beschreibung | keine OpenAPI | OpenAPI für die Nebenpfade | D12 |
| Antwortzeiten | Latenzmessung vorhanden | Tabelle je Werkzeug; Schreibvorgänge bis 60 s und Pläne in 40-s-Scheiben nennen | D12 |
| Übergabe | – | Steckbrief, Kompatibilitätsmatrix, Ansprechperson und Vertretung | D13, Abschnitt 3 |

**Schon erfüllt oder nicht anwendbar:** kein LLM (Kapitel 2.1 entfällt), keine Daten im Image,
Fehler als JSON mit 4xx und 5xx getrennt, 503 nur für vorübergehende Ausfälle mit
`Retry-After`, Image läuft nicht als root, Dependabot, Trace-Header.

## 6 Vorschlag für die Reihenfolge

1. Audit-Nacharbeit committen.
2. D1 bis D7 (fachlich, klein).
3. D8 bis D10 (Logging, Metriken, zweiter Port).
4. D11 bis D13 (Messung, Doku, Entwürfe für Chart und Steckbrief).
5. Nach den Entscheiden aus Abschnitt 3: Version schneiden, Dienst-ID umstellen, CI mit
   getaggtem Image.
6. Einheitlicher Vertrag als neue Hauptversion, danach die Ausgabeschemata.
7. W1 bis W4, sobald Staging und das Repository-Team es zulassen.

## 7 Umsetzungsstand im Chatbot, je Änderung von dir

Stand 13.11.: im Code umgesetzt und dreimal unabhängig reviewt, noch nicht ausgerollt. Es
verträgt sich mit deinem alten und deinem neuen Stand.

| Deine Änderung | Was der Chatbot jetzt tut | Offen oder bewusst nicht |
|---|---|---|
| `incomplete: true` an Listen und Töpfen, `childrenUnread` am Sammlungsbaum, Hinweissätze | Erkennt es für die Such- und Listen-Werkzeuge. Die Antwort steht nur 30 Sekunden im Cache (vorher 300 Sekunden, beim Baum 30 Minuten). Dein Hinweissatz bleibt an der gekürzten Antwort für die KI, höchstens drei Sätze | Die Karten unter der Antwort lesen weiter nur `results`; bei einem Ausfall ist die Box leer, den Satz dazu schreibt die KI |
| `isError` statt leer bei `search_wlo_topic_pages` mit `collectionId` und beim schlanken `search` | `search` und `/api/wikipedia` nutzt der Chatbot nicht. Ein Fehler eines Werkzeugs war schon vorher kein Treffer und wurde nie gecacht | – |
| `reason: source_unreachable` bei `get_topic_page_content` | Das Themenseiten-Muster sagt „hat WLO gerade nicht geantwortet, versuch es in einem Moment noch einmal“ statt „eventuell noch leer oder nicht freigegeben“. Dasselbe, wenn der Aufruf selbst scheitert (keine Antwort, Frist, ausgelastet) | Meldest du ein 403 als „nicht erreichbar“, ist der Satz falsch (D6) |
| Wikipedia `unreachable` | Zählt als „kein Treffer“ wie bisher, steht aber nur 30 Sekunden im Cache | – |
| `search_skill` mit `incomplete` | Wertet der Chatbot nicht als Ausfall, weil es auch für dauerhafte Grenzen steht | D5 |
| Vorschläge: `already_decided`, Annehmen ergänzt | Eigener Satz für `already_decided`. Die Beschreibung des Werkzeugs und die Kurations-Anleitung sagen der KI: nur offene Vorschläge, Annehmen ergänzt mehrwertige Felder | – |
| `suggestion_not_marked` | Kein eigener Satz: Der Code kommt nur nach der Einlösung. Mit `outcomeOpen: false` legt der Chatbot neu vor, sonst sagt er „bitte in WLO nachsehen“ | – |
| Anlegen: `recordExists`, `error.nodeId`, `unverified` | Satz „Der Datensatz ist angelegt (Kennung), ein Schritt danach ist nicht bestätigt, bitte nicht noch einmal anlegen“. Die Kennung lesen wir aus `error.nodeId` oder daneben | Ein geführter Ablauf merkt die Kennung nicht, er endet wie bei jedem offenen Ausgang (D3 hilft) |
| Stapel: volle Vorschau, `too_many_batches`, 429 am Upload | Die Vorschau lasen wir schon vollständig aus `entries`. `too_many_batches` und 429 werden „gerade voll, gleich noch einmal“ | `Retry-After` am Upload lesen wir nicht; ohne `scope` können wir nicht sagen, ob eigene Stapel offen sind (D4) |
| `already_submitted` | Eigener Satz „Der Inhalt ist schon zur Prüfung eingereicht“, auch in der Vorschau eines Ablaufs | – |
| `is_a_folder`, `is_a_collection`, `not_a_record` | Eigene Sätze. Die Kurations-Anleitung sagt, dass sich Ordner nicht löschen lassen | – |
| `authority: null` beim Dienstkonto | Keine Änderung nötig: Das Dienstkonto galt bei uns nie als Person, der Name wurde nie angezeigt | – |
| `X-Request-Id`, Trace-Header | Wir senden weiter `x-client-trace-id` und B3, keine eigene `X-Request-Id` | – |
| `get_skill` lehnt große und binäre Dateien ab | Eine solche Antwort wird weder als Master-Skill übernommen noch als laufende Anleitung gemerkt | Wir erkennen sie an der Schlusszeile des Textes; `contentRefused` nutzen wir noch nicht |
| `WLO_UPSTREAM_CONCURRENCY`, `upstream_busy` | Wie bisher: einmal kurz warten, die Abnahme bleibt liegen. Neu in der Stapel-Ablage: „voll“, mit offenem Ausgang „zu langsam“ | – |

## 8 Was wir dir noch schulden

Aus deiner Liste vom 07.11. („Was wir von euch brauchen“), unverändert offen:

| Was | Stand |
|---|---|
| `TICKET_ALLOWED_ORIGINS` (Herkünfte der Seiten, die das Widget mit `ticket` einbetten; dieselbe Liste wie `CORS_ORIGINS` am Chatbot) | Die Werte für Staging und Produktion liefert der Betrieb, noch nicht geschehen |
| `WIDGET_OAUTH_ORIGINS` (die öffentliche Herkunft des Chatbot-Backends) | wie oben |
| Client-Schlüssel | Der Nutzer erzeugt ihn und tauscht ihn außerhalb jedes Chats mit dir. Bis dahin hält der Chatbot das Adress-Budget selbst ein (`MCP_BUDGET_RPM` 280) |
| Lasttest mit 30 Personen, Zeitpunkte langsamer Aufrufe | Den Lasttest startet der Nutzer, noch nicht gelaufen |
