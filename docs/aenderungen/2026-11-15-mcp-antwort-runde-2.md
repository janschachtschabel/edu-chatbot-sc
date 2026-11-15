# Der Chatbot am MCP-Stand vom 14.11.2026 abends (2026-11-15)

Plan [`2026-11-15-mcp-antwort-runde-2.md`](../plans/2026-11-15-mcp-antwort-runde-2.md), Pakete
MR-1 bis MR-4. Anlass ist die zweite Antwort des MCP-Entwicklers zu den Sammlungsstrukturen; sie
nennt auch, was sein Audit für einen Client geändert hat.

Der Stand ist nicht bereitgestellt. Die Änderungen verhindern, dass der Chatbot nach dem
Deploy des MCP falsch reagiert. Am heutigen Server ändert sich wenig, siehe „Was sich schon
am heutigen Server ändert“.

## MR-1: Ablehnung des Repositorys nach dem Ja

Lehnt das Repository beim Schreiben ab (fehlendes Recht, Ziel nicht gefunden, anderes „Nein“),
meldet der neue Stand das als `forbidden`, `not_found` oder `refused` mit „nichts geschrieben,
neue Vorschau nötig“. Der Chatbot legte dann von selbst neu vor und schrieb: „Die Freigabe war
nicht mehr gültig … bestätige sie bitte erneut.“ Die neue Vorschau gelang, das nächste Ja
scheiterte wieder, und den Grund sah die Person nie.

- **Jetzt:** Die Person liest „WLO hat die Änderung abgelehnt“ mit dem Grund.
- **Von selbst neu vorgelegt** wird nur noch, wenn der Schlüssel nicht mehr gilt: abgelaufen,
  andere Angaben, oder der Datensatz hat sich seit der Vorschau geändert (ME-1). In jedem
  anderen Fall liest die Person den Grund und bittet selbst noch einmal.
- **Der Grund** ist ein Satz des Chatbots, deutsch und englisch. Den Text des Servers bekommt die
  Person nicht, wenn er die Antwort des Repositorys trägt („HTTP 400: …“) oder den Namen eines
  internen Abrufs („getCollectionContents failed: 503“).
- **Neue Sätze:** kein Recht (`forbidden`), nicht in dieser Sammlung (`not_in_collection`), Ziel
  nicht gefunden, „angenommen, aber nichts gespeichert“ (`not_stored`), „so nicht angenommen“,
  „ließ sich gerade nicht prüfen, bitte mich gleich noch einmal darum“ (`not_checked`,
  `unreadable`, `upstream_error` ohne ein „Nein“ des Repositorys).
- **Plan-Werkzeug:** Ein Unfall im Server nach dem Ja (`internal_error`, `upstream_error` ohne
  `outcomeOpen`) heißt „Ausgang offen, Plan fortsetzen“ statt „es wurde nichts geändert“.
- **Sammlung angelegt, aber nicht bestätigt** (`wlo_create_collection` mit `recordExists`): eigener
  Satz statt „der Datensatz … zum Beispiel die Datei“.
- **Im Ablauf:** Eine Ablehnung führt den Lauf zu `bei_fehler`. Vorher wartete er nach der neuen
  Vorschau auf ein weiteres Ja.

## MR-2: Ausfälle beim Lesen

- **Volltext:** `text_unreadable` (das Repository hat nicht geantwortet) hat einen eigenen Satz
  und bleibt nur kurz im Cache. Die Beschreibung für die KI nennt den Grund.
- **Verwandte Inhalte:** Eine Antwort mit `siblingsUnread` bleibt nur kurz im Cache.
- **Themenseiten:** `internal_error` (ein Fehler im MCP selbst) gilt als Ausfall, nicht als „noch
  leer oder nicht freigegeben“.
- **Themenbaum:** `internal_error` wird nicht wiederholt.

## MR-3: Grenz-Hinweise des Servers erreichen die KI

Der neue Stand sagt, wenn eine Antwort an einer Grenze endet: nur ein Teil des Baums durchsucht,
nur die ersten 100 Inhalte, die Trefferzahl nur eine Ober- oder Untergrenze. Diese Sätze stehen
hinter dem JSON-Umschlag und fielen der Kürzung für die KI zum Opfer. Die KI las dann etwa
`{"total":0,"results":[]}` und sagte „keine Sammlung gefunden“.

- Jede Zeile, die hinter dem Umschlag am Zeilenanfang mit „Hinweis: “ beginnt, reist jetzt mit
  (mit den Ausfall-Sätzen zusammen höchstens fünf, ein Ausfall zuerst), im Agent- und im
  Muster-Weg. Eingerückte Zeilen zählen
  nicht: Dort hängt der Server den Skill-Katalog einer Sammlung an, mit fremden Titeln.
- Die Kennzeichen `scanCapped` und `totalIsUpperBound` bleiben in der gekürzten Sicht.
- Die Beschreibung der Baumliste schickt die KI für ein Fachportal nicht mehr zur Kennung: Der
  Server löst es jetzt über seinen Titel auf.

## MR-4: Ablage

Ließ sich nach einem offenen Ausgang nicht klären, ob die Vorgangsdatei da ist (`not_checked`),
meldet der Chatbot „später noch einmal“ (503) statt „abgewiesen“ (422).

## Was sich schon am heutigen Server ändert

- `not_stored` nach dem Ja (etwa ein Feld ohne Recht): Ablehnung mit Grund statt neuer Vorschau.
- `forbidden` hat einen Satz („fehlt das Recht“); vorher nur „abgelehnt“.
- Eine Ablehnung mit „nichts geschrieben, neue Vorschau nötig“ wird nur noch neu vorgelegt,
  wenn der Schlüssel nicht mehr galt (ME-1). `upstream_error` mit „nichts geschrieben“ zeigt
  jetzt einen Grund statt einer neuen Vorschau.
- Die Beschreibung der Baumliste (gilt erst, wenn der Server sie führt).
- Zeilen „Hinweis: …“ hinter einem JSON-Umschlag reisen zur KI.

## Gemessen

Am lokal gestarteten neuen Stand (anonym, nur lesend, gegen Staging):

- `list_collection_tree` mit `collection: "Physik"` löst das Fachportal auf.
- `search_wlo_collections` ohne Treffer: `scanCapped: true` und der Satz dazu; nach der Kürzung
  steht beides in der Sicht der KI, in beiden Wegen.
- `get_collection_contents` rekursiv bei `skipCount` 400: `contentsCut`, `totalIsLowerBound`,
  `skipLimitReached` und zwei Sätze; beide reisen mit.
- `search_wlo_within_collection`: `truncated`, `collectionTotal`; der Satz ist dort kursiv
  gesetzt (`_Hinweis: …_`) und wird trotzdem erkannt.
- `get_wlo_content_text`: Die Hinweiszeile vor dem Fremdtext steht nur im Markdown-Text und als
  Feld `note` im JSON-Text; das Feld `text` bleibt sauber.

Auffällig: An Staging meldet derzeit jede Inhaltssuche `incomplete: true` („hat nicht
(vollständig) geantwortet“). Das steht in der Antwort an den Entwickler.

## Review

Zwei unabhängige Reviews.

**Erstes Review:** 1 schwerer, 5 mittlere, 4 kleine Punkte. Behoben:

1. **`not_stored` wurde weiter neu vorgelegt (schwer).** Es ist ein Urteil: Das Repository hat
   angenommen und nichts gespeichert, meist fehlt das Recht. Das war dieselbe Schleife, die MR-1
   beseitigen sollte, am häufigsten Schreibwerkzeug. Jetzt eine Ablehnung mit eigenem Satz.
2. **Mittlere:**
   - `changed_since_preview` (Volltext: der Datensatz hat sich seit der Vorschau geändert) fiel
     durch MR-1 auf „abgelehnt“ ohne Grund. Es wird wieder neu vorgelegt.
   - Hinter dem JSON-Umschlag steht nicht nur Text des Servers: Der Skill-Katalog einer Sammlung
     trägt eingerückte Zeilen „Titel: Beschreibung“. Ein Skill namens „Hinweis“ wäre als Satz
     des Servers zur KI gelangt. Eingerückte Zeilen zählen nicht mehr.
   - Ein zweites Format interner Fehlertexte („… failed: 503 Service Unavailable“) erreichte
     die Person. Auf Englisch fehlte der Grund, wo es einen eigenen Satz gibt.
   - Die Antwort an den Entwickler nannte Codes, die sein Stand so nicht sendet.
3. **Kleine:** ein kursiver Ausfall-Satz käme doppelt; ein Volltext wurde zweimal gelesen.

**Zweites Review** (nach der Nachbesserung): 3 schwere, 7 mittlere, 8 kleine Punkte. Die
schweren hingen an einem Zweig, den das erste Review erst nahegelegt hatte: „WLO blieb ohne
Urteil, also neu vorlegen“.

1. **Schwer:**
   - Volltext: Ein abgelehnter Upload (4xx) kommt beim MCP als `upstream_error` mit „nichts
     geschrieben“. Neu vorlegen lief in eine Schleife mit dem Satz „WLO hat gerade nicht
     geantwortet“.
   - Herausnehmen: `not_checked` kommt auch dauerhaft, bei einer Sammlung mit mehr Einträgen,
     als der MCP durchsucht. Dieselbe Schleife.
   - Die Antwort an den Entwickler beschrieb genau diese Schleife als „für uns in Ordnung“.

   Behoben: Der Zweig ist gestrichen. Neu vorgelegt wird nur, wenn der Schlüssel nicht mehr
   gilt (ME-1); alles andere zeigt seinen Grund. Beide Stellen stehen als Bitte in der Antwort
   an den Entwickler.
2. **Mittlere, behoben:** Lese-Ausfälle vor dem Schreiben (`unreadable` …) hatten keinen Grund;
   ein Unfall im Server nach dem Ja eines Plans hieß „nichts geändert“; die Antwort an den
   Entwickler war an drei Stellen ungenau.
3. **Kleine, behoben:** nur ein JSON-Objekt gilt als Umschlag; mit Ausfall-Sätzen zusammen
   reisen jetzt fünf statt drei Sätze mit; zwei überholte Kommentare; Tests mit Drahtformen,
   die der Server nicht sendet.

Bewusst so gelassen:

- `forbidden` sagt immer „fehlt das Recht“, auch wenn es am Ziel (einer Sammlung) fehlt.
- Der Satz zu `text_unreadable` sagt „gleich noch einmal“; die Antwort steht 30 Sekunden im
  Cache.
- Eigene Sätze des MCP zu `refused` erreichen die Person auf Deutsch wörtlich; einige nennen
  Werkzeuge und Parameter (bestand schon).
- `not_checked` heißt auf Englisch immer „gleich noch einmal“, auch im seltenen dauerhaften
  Fall.
- `plan_expired` und `plan_mismatch` beim Einlösen heißen „von WLO kam keine Antwort“ mit „Plan
  fortsetzen“ (bestand schon).

## Geprüft

- Backend: volle Suite 10 561 Tests grün, 5 übersprungen, 1 Zeit-Kippler außerhalb der Änderung (`test_loadtest_anfragen`, allein grün; steht in den offenen Punkten); neu `tests/test_mcp_antwort_runde2.py`, angepasst
  `tests/test_mcp_wiederholung_s3.py`, `tests/test_mcp_vertrag_m2.py` und
  `tests/test_mcp_nach_audit.py` (sie schrieben das alte Verhalten fest).

Nicht geprüft: jeder Schreibweg am neuen Stand (braucht dessen Deploy und eine Anmeldung).

## Deploy

- Keine Migration, keine neue Variable, kein `import-config`. Image neu bauen.
- Reihenfolge zum MCP: egal.
