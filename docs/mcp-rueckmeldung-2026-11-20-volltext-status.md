# Rückmeldung an den MCP: Volltext-Status des Repositoriums (2026-11-20)

Anlass: Eine Person legte über den MCP eine Text-PDF in WLO ab und ließ daraus einen Themenbaum
entwerfen. Der Chatbot bekam von `get_wlo_content_text` immer wieder `reason: not_extracted` und riet
zu „nochmal“. Das half nie. Gemessen auf Staging mit dem Testkonto, direkt über REST (nicht über den
MCP). Die eigenen Testknoten sind danach endgültig gelöscht. Gelesen wurde dein Stand in
`wlo-mcp-server-sc`.

## 1 Befund

**Das Repositorium erzeugt den Volltext synchron beim ersten Lesen.** Vor dem ersten
`GET …/textContent` antwortet es `200 {"text": null}`, danach steht der Text sofort da. Gemessen:
0,4 s nach dem Upload bei einer Text-PDF mit 223 KB (58 410 Zeichen), 10,5 s bei einer 8-MB-PDF. Im
Hintergrund nach dem Upload passiert nichts. Danach setzt das Repositorium die Eigenschaft
`ccm:fulltext_status`:

| Wert | Bedeutung (gemessen) |
|---|---|
| `CONTENT_AVAILABLE` | Text erzeugt |
| `NO_CONTENT` | PDF ohne Textebene (Scan) |
| `TRANSFORM_ERROR_UNSUPPORTED` | Format ohne Umwandlung (etwa `.md`) |
| `TRANSFORM_ERROR_INTERNAL` | Umwandlung intern gescheitert |

**`TRANSFORM_ERROR_INTERNAL` sitzt fest.** Am betroffenen Knoten stand dieser Status. Das
Repositorium wiederholt die Extraktion nie: Jedes weitere `GET …/textContent` antwortet sofort
`{"text": null}`. `forceUpdate=true` dürfen nur Admins. Sieben Nachspiele deines Wegs mit derselben
Datei lieferten sofort Text — der Auslöser liegt im Repositorium (Transformer-Logs nötig), nicht
im MCP.

**Der MCP liest den Status nicht.** Fundstellen:

- `src/services/content-text.ts:164` — `NODE_PROPS` liest nur `ccm:wwwurl`, `cclom:title`,
  `cm:title`, `cm:name`.
- `src/services/content-text.ts:244-248` — ohne `ccm:wwwurl` und ohne Text wird jede Datei mit
  Größe `not_extracted` — gleich ob Scan, nicht umwandelbares Format oder gescheiterte
  Umwandlung.
- `src/wlo-node-text.ts:142-145` — `{"text": null}` gilt als beantwortete Leere (`none`), auch
  wenn das Repositorium die Extraktion gar nicht mehr versucht.

Für einen Client heißt `not_extracted` damit „endgültig, Grund unbekannt“. Ein Scan, eine
Markdown-Datei und eine gescheiterte Umwandlung sehen gleich aus. Nur die gescheiterte Umwandlung
ließe sich reparieren.

## 2 Was der Chatbot schon geändert hat

Plan 2026-11-20 §8, Paket E (noch nicht ausgerollt):

- `not_extracted` gilt als endgültig. Statt „nochmal“ nennt der Chatbot zwei Auswege: das Dokument
  im Chat lesen lassen (dort mit Texterkennung) oder ohne Dokument weiter.
- Nur `text_unreadable` und eigene Abruffehler gelten als vorübergehend. Der Chatbot fragt dann im
  selben Zug nach 5 s und 10 s noch einmal nach.
- Sobald es `extractionStatus` gibt (Vorschlag 2), unterscheiden wir nach dem Status. Das kommt als
  eigenes Paket.

## 3 Vorschläge

| Nr. | Vorschlag | Für bestehende Clients | Für den Chatbot |
|---|---|---|---|
| 1 | `ccm:fulltext_status` in `NODE_PROPS` aufnehmen | keine Wirkung, ein Feld mehr gelesen | Grundlage für 2 |
| 2 | Neues optionales Feld `extractionStatus` in der Antwort von `get_wlo_content_text` (der Rohwert aus 1). Alternativ ein eigener Grund `extraction_error` für `TRANSFORM_ERROR_INTERNAL` statt `not_extracted` | additiv; ein neuer Grund wäre für Clients mit fester Liste neu | Wir sagen „Scan“, „Format nicht lesbar“ oder „Umwandlung gescheitert“ statt eines Sammelsatzes |
| 3 | Zu klären: ein bestätigtes Werkzeug „Extraktion neu anstoßen“ für eigene Knoten | neues Werkzeug, schreibend, mit Bestätigung | Ausweg bei `TRANSFORM_ERROR_INTERNAL`, ohne die Datei neu hochzuladen |

Zu 3, gemessen: Die Status-Eigenschaft löschen über
`POST …/node/v1/nodes/-home-/{nodeId}/property?property=ccm:fulltext_status` (ohne Wert) und danach
`GET …/textContent` lesen. Das stellt den Text wieder her — das Repositorium extrahiert neu
(gemessen mit dem Testkonto an einem eigenen Knoten, ohne Admin-Rechte). `forceUpdate=true` ist dafür kein Weg, er gilt
nur für Admins. Offen: ob das Löschen der Eigenschaft ein gewollter Weg ist oder eine Lücke, die das
Repositorium schließt. Darum „zu klären“, nicht „direkt umsetzen“.

## 4 An den Autor des Flows `edusharing.chatbot/node-metadata-write`

Gemessen auf Staging: Der Flow läuft (202, dann `SUCCEEDED` nach 13,2 s, acht Felder). Zwei Punkte:

- **jobId im Klartext:** Der Flow schreibt die jobId in `ccm:version_comment` am Knoten. Lesen kann
  sie jeder mit Leserecht am Knoten. Vorschlag: keine jobId in Eigenschaften, die mit dem Knoten
  geteilt werden — oder nur einen Verweis, der ohne weitere Rechte nichts öffnet.
- **Titel wird überschrieben:** Der Flow ersetzt den Titel, den die Person gesetzt hat.
  Vorschlag: einen vorhandenen Titel stehen lassen (nur leere Felder füllen) oder den Vorschlag als
  Metadaten-Vorschlag ablegen statt direkt zu schreiben.
