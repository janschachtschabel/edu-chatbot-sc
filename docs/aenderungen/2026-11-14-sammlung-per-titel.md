# Eine Sammlung über ihren Titel ansprechen (2026-11-14)

Plan [`2026-11-14-mcp-stand-8cbc051.md`](../plans/2026-11-14-mcp-stand-8cbc051.md), Paket N3.

Der MCP nimmt ab dem Stand vom 14.11. an fünf lesenden Werkzeugen statt der Kennung den Titel der
Sammlung (`collection`), dazu das Fach für gleichnamige. Er rät nie: Trägt keine oder mehr als
eine Sammlung den Titel, kommen Kandidaten statt eines Ergebnisses (`ambiguous_collection`).

Bisher brauchte „Was gibt es unter Optik?“ zwei Werkzeugrunden: erst die Sammlung suchen, dann
ihre Kennung übergeben. Jetzt reicht eine, wenn der Titel eindeutig ist.

## Wie zuverlässig ist die Auflösung im MCP

Gemessen am neuen Stand des Servers, lokal gestartet gegen das Staging-Repository (nur lesend,
anonym), mit 24 Themennamen:

| | aufgelöst | abgelehnt mit Kandidaten |
|---|---|---|
| mit Fach | 13 | 11 |
| ohne Fach | 10 | 14 |

- Alle 23 Auflösungen trafen eine Sammlung mit genau diesem Titel. Geraten wurde nie.
- Abgelehnt wurde, wo der Titel nicht genau stimmt („Genetik“ heißt „Genetik und Vererbung“) oder
  mehrere Sammlungen so heißen („Grammatik“ in fünf Sprachen). Die Kandidaten enthielten die
  gemeinte Sammlung.
- Zwei Schwächen, beide durch Community-Sammlungen ohne Fachangabe (Rückmeldung an den
  Entwickler, Abschnitt 8 der Antwort):
  - „Mechanik“ mit Fach Physik wird abgelehnt, weil eine gleichnamige Community-Sammlung kein
    Fach trägt. Kostet eine Runde; das Ergebnis stimmt.
  - „Klimawandel“ mit Fach Geografie liefert eine Community-Sammlung ohne Fach, weil sie als
    einzige nicht ausgeschlossen wird. Die Antwort nennt den Pfad, und die KI sagte das in 3 von
    3 Läufen dazu („liegt unter Communities, nicht im Fach Geografie“).
- Zeit: 1,3 bis 3,3 s je aufgelöstem Aufruf, 0,8 bis 1,7 s je Ablehnung.

Urteil: zuverlässig genug zum Nutzen. Der schlechteste Fall kostet dieselben zwei Runden wie
bisher; ein falscher Treffer bleibt möglich, wird aber mit Pfad genannt.

## Was sich im Chatbot ändert

- **Der Server sagt, was er kann** (`services/mcp/faehigkeiten.py`). Chatbot und MCP werden
  getrennt bereitgestellt. Der Chatbot fragt beim Start und alle fünf Minuten die Werkzeugliste
  ab und bietet `collection` der KI nur an, wenn der Server den Parameter führt. Unbekannt heißt
  „kann es nicht“. Kein Schalter, kein Deploy-Schritt, keine Reihenfolge.
- **Angebot an die KI** (`services/mcp/sammlung_per_name.py`): `get_collection_contents`,
  `search_wlo_within_collection`, `browse_collection_tree`, `get_compendium_text` und
  `get_collection_overview` bekommen `collection` und das Fach dazu (`discipline`; bei der Suche
  in einer Sammlung `collectionDiscipline`, weil `discipline` dort die Inhalte filtert). Die
  Kennung ist dann keine Pflicht mehr. Die direkten Werkzeuge bekommt so nur die Agent-Schleife
  (Vorgabe) angeboten.
- **Themenbaum-Modul:** `ui_themenbaum` nimmt `collection` mit `discipline`. Die Überschrift ist
  der Titel der gewählten Sammlung. Die KI erfährt Kennung, Titel und Pfad der Wahl. Bei einem
  mehrdeutigen Titel bekommt sie die Kandidaten (Kennung, Titel, Pfad) und ruft das Modul mit der
  Kennung neu auf. Nennt sie einen Titel, obwohl der Server ihn nicht kennt, bekommt sie einen
  Fehler mit den angebotenen Wegen; das Fach wird dann nicht ersatzweise gezeigt.
- **Kein Raten mehr im Client:** Schrieb die KI einen Namen ins Feld der Kennung, nahm der
  Chatbot bisher den ersten Treffer der Sammlungssuche, im Baum das Fachportal aus der
  Klassifikation. Kennt der Server `collection`, geht der Name jetzt als Titel an ihn (im Baum
  mit dem Fach der Klassifikation) und wird streng aufgelöst (`services/mcp/arg_resolvers.py`).
  Das gilt auf beiden Wegen, auch im Muster-Weg; dort kann jetzt eine Ablehnung mit Kandidaten
  kommen, wo vorher still ein Treffer geraten wurde.
- **Leere Ergebnisse bleiben kurz im Cache**, auch wenn der Server zu einem Titel eine Zeile
  hinter das JSON hängt (`services/mcp/tool_cache.py`).
- **Skill-Hinweis bleibt:** Der Hinweis auf die Anleitungen der Sammlung nimmt die Kennung aus
  `resolvedCollection`, wenn der Aufruf keine trug.
- **Master-Skill** (`docs/skills/`, drei Fassungen): Der Abschnitt M08 nennt den kürzeren Weg nur
  über die Beschreibung des Werkzeugs und keinen Parameternamen.

## Entscheide

- **Fähigkeitsabfrage statt Schalter.** Gegen den alten Server lehnt jeder Aufruf mit Titel ab
  oder zeigt etwas anderes. Ein Schalter wäre ein Deploy-Schritt mehr, der vergessen wird.
  Dieselbe Abfrage trägt später N2 und N4.
- **Der Master-Skill nennt `collection` nicht.** In der Probe nahm das Modell den Parameter sonst
  auch dann, wenn das Werkzeug ihn nicht anbot, und gab nach zwei Fehlversuchen auf (1 von 2
  Läufen). Mit dem neutralen Wortlaut: 4 von 4 Läufen richtig, mit und ohne Angebot.
- **Das Fach reist nie als `subject` mit dem Titel.** Ein Server ohne `collection` zeigte sonst
  still das Fachportal statt der Sammlung.
- **Kandidaten als Text an die KI, kein Auswahlfeld.** Die KI wählte in 4 von 4 mehrdeutigen
  Läufen den richtigen Kandidaten. Ein Auswahlfeld (`ui_entscheidung`) erst, wenn sich in der
  Praxis zeigt, dass sie falsch wählt.
- **Titel und Pfade sind Fremdtext.** Kandidaten und gewählte Sammlung baut der Chatbot aus dem
  strukturierten Teil der Antwort (dem JSON am Anfang), nicht aus den Zeilen des Servers. Die
  Kennung steht vorn und kommt aus ihrem eigenen Feld. Titel und Pfad stehen in „…“: ohne
  Anführungszeichen jeder Art, ohne Zeilentrenner und unsichtbare Zeichen, ohne alles in der Form
  einer Kennung (auch mit fremden Trennern oder Vollbreite-Ziffern). Ein Titel hat höchstens 120
  Zeichen, ein Pfadteil 60, ein Pfad sechs Teile (Fach und nächste Eltern bleiben). Klammern und
  Apostroph bleiben. Die Überschrift im Widget ist der Titel, wie er ist. Sonst gilt im Modul
  weiter „kein Text des Servers im Fehlertext“. Ruft die KI eines der fünf Werkzeuge direkt, sieht
  sie die Fehlerantwort des Servers wie bei jedem Werkzeug.
- **Eine unvollständige Suche ist kein Befund.** Meldet der Server keine Kandidaten und zugleich,
  dass seine Sammlungssuche unvollständig war, sagt das Modul der KI genau das, nicht „es gibt
  keine Sammlung mit diesem Titel“. Ein nicht erkanntes Fach wird genannt, ohne seinen Wert.
- **Mit `collection` reist nie ein `subject`**, im Modul und im Client. Ein Server ohne
  `collection` zeigte sonst still das Fachportal; ohne `subject` lehnt er sichtbar ab.
- **Der Stand verfällt.** Nach drei gescheiterten Abfragen in Folge gilt wieder „unbekannt“.
- **Muster-Weg:** Die direkten Werkzeuge bleiben dort ohne das Angebot, die Muster-Seeds sagen
  weiter „erst suchen, dann Kennung“. Nennt ein Muster `ui_themenbaum`, bekommt es dort dasselbe
  Angebot wie der Agent. Ersetzt die Kurzfassung ein Ergebnis (Kasten-Modus), bleibt der Satz zur
  gewählten Sammlung stehen (`domain/tool_result_redaction.py`).
- **Nicht umgesetzt:** Die Studio-Übersicht der Werkzeuge zeigt die Beschreibungen ohne den Satz
  zum Titel (die Prompt-Vorschau zeigt ihn). Führt ein zweiter eingetragener MCP-Server ein
  WLO-Werkzeug, das der erste nicht listet, fragt die Fähigkeitsabfrage trotzdem nur den ersten.

## Gemessen mit dem echten Modell

`gpt-6-luna`, echte Werkzeugdefinitionen, Kurzfassung des Master-Skills, Antworten vom lokalen
neuen MCP:

| Frage | Werkzeugrunden vorher | jetzt |
|---|---|---|
| „Was gibt es unter Optik in Physik?“ | 2 (4,0 bis 6,5 s) | 1 (2,6 bis 5,8 s) |
| „Welche Videos zu Linsen gibt es in der Sammlung Optik?“ | 2 | 1 |
| „Was steht im Redaktionstext der Sammlung Zellbiologie zu …?“ | 2 | 1 |
| „Zeig mir die Unterthemen von Mechanik in Physik.“ (gleichnamige) | 2 | 2 |
| „Welche Themen gibt es unter Genetik in Biologie?“ (Titel ungenau) | 2 | 2 |

## Review

Ein unabhängiges Review fand keinen kritischen, 1 schweren, 7 kleinere Befunde und 8
Randnotizen. Behoben sind der schwere, alle kleineren und fünf Randnotizen.

- Schwer: Die Kandidaten kamen aus den gerenderten Zeilen des Servers. Ein Sammlungstitel konnte
  darin eine fremde Kennung, einen falschen Pfad oder eine eigene Zeile vortäuschen. Jetzt siehe
  „Titel und Pfade sind Fremdtext“.
- Kleiner: `subject` reiste im direkten Weg mit dem Titel; das Modul zeigte ohne Angebot still
  das Fach; der Hinweis der Klassifikation ging vor dem Titel; der Stand verfiel nie; leere
  Ergebnisse per Titel standen zu lange im Cache; zwei Aussagen dieser Notiz stimmten nicht.

Ein zweites, enges Review der Nacharbeiten fand nichts Kritisches oder Schweres, 7 kleinere
Befunde und 11 Randnotizen. Behoben: Doppelgänger-Zeichen in Titeln; Kandidaten nur aus dem JSON
am Anfang der Antwort; die JSON-Leser werfen auch bei tief verschachteltem Fremdtext nicht; die
Überschrift behält Klammern und Apostroph; Platzhalter wie „?“ gelten nicht als Titel; kein
Skill-Hinweis an einer Fehlerantwort; unvollständige Suche und nicht erkanntes Fach werden der KI
gesagt; dazu sechs Randnotizen.

Bewusst gelassen:
- Ein Fachportal wird weiter auch per Wortanfang oder Teilwort erkannt („Mathe“ → Mathematik),
  bevor ein Name als Titel gilt. Ob echte Portaltitel dabei einen Sammlungsnamen schlucken, ist
  nicht gemessen.
- Antwortet der Server auf die Fähigkeitsabfrage mit 429 oder 503, zählt das wie ein Ausfall.
- In einem Titel bleiben bis zu 120 Zeichen freier Text. Das ist weniger, als jedes Suchergebnis
  ungerahmt liefert.

## Geprüft

- Backend: volle Suite 10 327 Tests grün (5 übersprungen); neu `tests/test_mcp_sammlung_per_name.py` (Antwortformen wörtlich vom
  neuen Server).
- Client des Chatbots gegen den lokalen neuen MCP: alle fünf Werkzeuge mit Titel, Name im Feld der
  Kennung, mehrdeutig, kein Treffer.
- Ein Fehler fiel dabei auf und ist behoben: Zu einem Titel hängt der Server eine Zeile hinter das
  JSON; das Modul las die Antwort dann nicht mehr.

Nicht geprüft: ein Zug im Chat mit Datenbank und Widget gegen den neuen MCP. Das geht erst, wenn
der Stand auf dem Staging-Server läuft.

## Deploy

- Keine Migration, keine neue Variable, keine Reihenfolge zum MCP. Image neu bauen.
- Master-Skill-Knoten in WLO mit `docs/skills/vorgehen-knapp.md` ersetzen. Der alte Text
  funktioniert weiter, nutzt den kürzeren Weg beim Themenbaum aber seltener.
- Nach dem Deploy des MCP: im Log des Backends steht keine Warnung „MCP-Fähigkeiten: Abfrage
  gescheitert“; „Was gibt es unter Optik in Physik?“ zeigt den Baum der Sammlung Optik.
