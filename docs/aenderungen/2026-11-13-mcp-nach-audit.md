# Chatbot nach der Audit-Nacharbeit des MCP (2026-11-13)

Plan [`2026-11-13-mcp-nach-audit.md`](../plans/2026-11-13-mcp-nach-audit.md), Pakete C1, C2 und
C4. Rückmeldung an den MCP-Entwickler: [`mcp-rueckmeldung-2026-11-13.md`](../mcp-rueckmeldung-2026-11-13.md).

Der MCP-Server meldet seit seiner Audit-Nacharbeit Ausfälle, neue Ablehnungen und angelegte, aber
unvollständige Datensätze genauer. Der Chatbot lief damit ohne Änderung weiter, gab das aber nicht
an die Person weiter. Alle Änderungen vertragen sich mit dem alten und dem neuen MCP-Stand.

## C1 Ein Ausfall ist nicht „nichts gefunden“

- **Erkennen an einer Stelle** (`domain/mcp_unvollstaendig.py`): `incomplete: true` an einer
  Liste oder einem Topf, `childrenUnread: true` an einem Zweig des Sammlungsbaums,
  `unreachable: true` (Wikipedia), `reason: "source_unreachable"` (Themenseiten-Inhalt) und die
  Hinweissätze des Servers hinter dem JSON-Umschlag oder im Markdown-Text. Das gilt nur für die
  Such- und Listen-Werkzeuge, nicht für Anleitungen, Volltexte oder fremde MCP-Server.
- **Cache:** Eine solche Antwort steht nur 30 Sekunden im Cache (`services/mcp/tool_cache.py`).
  Vorher galt die Frist des Werkzeugs: 300 Sekunden bei den Suchen, 30 Minuten beim
  Sammlungsbaum. So lange stand ein Ausfall als Befund da.
- **Was die KI sieht:** Der Hinweissatz des Servers bleibt an der gekürzten Antwort, im Muster-
  und im Agent-Weg (`domain/tool_result_redaction.py`). Vorher fiel er weg: bei der
  Sammlungssuche und der Kombi-Suche durch die Kurzfassung, bei langen Listen durch den
  Zeichen-Deckel, im Gruppiermodus durch den Ersatz der Einzelinhalte.
- **Themenseiten-Muster ohne KI (M16):** Bei einem Ausfall heißt es „Zur Themenseite … hat WLO
  gerade nicht geantwortet. Versuch es bitte in einem Moment noch einmal, oder such über die
  normale Suche zum Thema.“ statt „eventuell noch leer oder nicht vollständig freigegeben“.
  Als Ausfall gilt, was der Client als „keine Antwort“, „Frist“ oder „ausgelastet“ einordnet,
  dazu ein Fehler des Repositoriums. Eine Ablehnung des Servers gilt nicht als Ausfall.

Nicht geändert:

- Die Karten unter der Antwort lesen weiter nur `results`. Bei einem Ausfall ist die Box leer;
  den Text dazu schreibt die KI, die den Ausfall jetzt sieht.
- Der Hinweis der Skill-Suche („Die Sammlung wurde nicht vollständig gelesen“) zählt nicht als
  Ausfall. Er steht auch für dauerhafte Grenzen; eine solche Antwort käme sonst nie in den Cache.

## C2 Neue Ablehnungen und „angelegt, aber unvollständig“

- **Eigene Sätze je Grund** (`services/write_approval.py`, Deutsch und Englisch):
  `already_decided`, `already_submitted`, `is_a_folder`, `is_a_collection`, `not_a_record`.
  Vorher: „WLO hat die Änderung abgelehnt“ ohne Grund. Der Text des Servers taugt dafür nicht,
  er ist an die KI gerichtet und nennt Werkzeuge und Status-Kennungen.
- **`recordExists`:** Ist der Datensatz angelegt und ein Schritt danach offen, sagt der Chatbot
  das mit der Kennung und bittet, nicht noch einmal anzulegen. Vorher: „ob sie angekommen ist,
  kann ich nicht sagen“. Die Kennung liest der Client aus `error.nodeId` oder, wo der Server sie
  nur daneben schreibt, aus dem strukturierten Teil (`services/mcp/client.py`).
- **Stapel-Ablage** (`services/ablage/mcp_ablage.py`): `too_many_batches` und `upstream_busy`
  werden „voll“ (wiederholbar) statt „abgewiesen“. `upstream_busy` mit offenem Ausgang wird „zu
  langsam“, weil die Datei abgelegt sein kann.
- **Texte für die KI:** Die Beschreibung von `wlo_decide_suggestion` und die Kurations-Anleitung
  (M18) sagen, dass Annehmen mehrwertige Felder ergänzt, nur offene Vorschläge entscheidbar sind
  und Ordner sich nicht löschen lassen.

Abweichungen vom Plan stehen dort in Abschnitt 6 (unter anderem: `too_many_batches` wird „voll“,
ein Ablauf merkt die Kennung nicht).

## C4 Eine abgelehnte Anleitung ist keine Anleitung

`get_skill` lehnt Dateien über 2 MiB und Binärdateien ab, als Erfolgstext mit eigener
Schlusszeile. `master_skill.keine_anleitung` erkennt beide Zeilen. Eine solche Antwort wird
weder als Master-Skill übernommen noch als laufende Anleitung gemerkt, in der Werkzeug-Schleife
des Muster-Wegs und in der Agent-Schleife.

## C3 entfallen

Geplant war, die Trace-ID zusätzlich als `X-Request-Id` zu senden. Der Arbeitsstand des MCP liest
`x-client-trace-id` und B3 inzwischen selbst. Eine gemeinsame `X-Request-Id` nähme ihm die
Kennung je Anfrage.

## Reviews

Je ein unabhängiges Review für C2 bis C4 und für C1, alle Befunde behoben oder entschieden:

- **C2 bis C4** (2 MAJOR, 6 MINOR):
  - Die Kennung fehlte in zwei von drei `recordExists`-Fällen, weil der Server sie dort neben
    `error` schreibt.
  - Die Prüfung aus C4 saß nur im Muster-Weg, nicht im Agenten (der Vorgabe-Engine).
  - Dazu: eigene Sätze statt Servertext, `suggestion_not_marked` aus der Liste, `upstream_busy`
    mit offenem Ausgang, C3 gestrichen.
- **C1** (2 MAJOR, 5 MINOR):
  - Die Kürzung der Sammlungssuche las das Kennzeichen aus dem Text, wo der Server es nicht
    schreibt. Jetzt reist der Satz des Servers mit.
  - `source_unreachable` blieb 300 Sekunden im Cache.
  - Dazu: der Satz überlebt Deckel und Ersatz, M16 unterscheidet Ausfall und Ablehnung, die Tests
    nutzen die echte Antwortform des Servers.

**Zweites Review über die ganze Lieferung** (1 MAJOR, 7 MINOR), weil beide ersten Reviews je
zwei schwere Befunde hatten:

- Der Sammlungsbaum fehlte: Ein nicht gelesener Zweig (`childrenUnread`) wäre 30 Minuten im Cache
  geblieben.
- Statt „gar nicht cachen“ jetzt 30 Sekunden.
- Die Erkennung gilt nur noch für die Such- und Listen-Werkzeuge; höchstens drei Hinweissätze
  reisen mit.
- M16 prüft die Art des Fehlers statt einer Liste von Codes.
- Der Satz zu `is_a_folder` passt jetzt auch außerhalb des Löschens.
- Ein Test für C4 im Muster-Weg ist ergänzt.

Bekannte Grenze: Der MCP meldet jeden Nicht-OK-Status des Repositoriums (auch 403 und 404) als
„nicht erreichbar“. Der Chatbot sagt dann „hat gerade nicht geantwortet“, obwohl es dauerhaft so
bleiben kann. Das steht als Wunsch W10 in der Rückmeldung an den MCP.

## Tests

- `tests/test_mcp_ausfall_ist_nicht_leer.py` (neu, C1): Erkennen je Werkzeug, Cache über drei
  echte Aufrufe mit Zeitsprung, Kürzung in beiden Wegen, Deckel und Ersatz, M16.
- `tests/test_mcp_nach_audit.py` (neu, C2 und C4): Sätze je Grund in beiden Sprachen,
  `recordExists` mit Kennung aus beiden Stellen, Stapel-Ablage, abgelehnte Anleitung in beiden
  Schleifen.
- `tests/test_topic_pages.py`: Ein Fehler des Aufrufs ergibt „nicht geantwortet“.

## Deploy

- Keine Migration, keine neue Variable.
- Image neu bauen, danach `boerdi import-config --werksabgleich` (M18 „Kuration“ hat zwei
  geänderte Zeilen).
