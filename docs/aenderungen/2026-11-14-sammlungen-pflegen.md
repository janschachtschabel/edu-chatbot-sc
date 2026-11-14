# Sammlungen pflegen: Stapel, Umhängen, Reihenfolge, Vorschläge (2026-11-14)

Plan [`2026-11-14-sammlungsstruktur-werkzeuge.md`](../plans/2026-11-14-sammlungsstruktur-werkzeuge.md),
Paket SW-3. Baut auf SW-1 und SW-2 auf
([Notiz](2026-11-14-sammlungsbaum-lesen-und-metadaten.md)).

Der MCP-Server kennt die Werkzeuge ab dem Stand „Sammlungsstrukturen“ (14.11.2026); der
bereitgestellte führt sie nicht. Bis er es tut, ändert sich im Chat nichts.

## Die sieben Werkzeuge

| Werkzeug | Was es tut | Bestätigung |
|---|---|---|
| `wlo_submit_contents` | bis zu 200 Materialien zur Prüfung einreichen | eine für alle (Plan) |
| `wlo_remove_from_collections` | bis zu 200 Verweise aus Sammlungen nehmen | eine für alle (Plan) |
| `wlo_delete_collections` | bis zu 200 **leere** Sammlungen löschen | eine für alle (Plan) |
| `wlo_move_collection` | eine Sammlung samt Teilbaum umhängen | einfach |
| `wlo_order_collection` | Reihenfolge der Untersammlungen oder der Inhalte setzen | einfach |
| `wlo_list_collection_proposals` | Vorschläge an eine Sammlung lesen | keine, liest nur |
| `wlo_decide_collection_proposal` | einen Vorschlag annehmen oder ablehnen | einfach |

Dazu an den vorhandenen Einsortier-Werkzeugen:

- **Umsortieren:** `removeFrom` je Paar an `wlo_add_to_collections`. Erst wird aufgenommen, dann
  aus der Quelle genommen.
- **Vorschlagen:** Wo die Anmeldung an einer Sammlung nur lesen darf, schlägt der Server vor,
  statt aufzunehmen. Die Beschreibung sagt der KI: Vorgeschlagen ist nicht aufgenommen.

## Wie sie eingebunden sind

- **Im Katalog** (`services/mcp/tool_defs_curation.py`, Entscheid SE-2): Bestätigung, Pläne
  („Plan fortsetzen“), Argumentmodelle und Cache-Sperre greifen damit von selbst.
- **Angeboten nur, wenn der Server sie führt** (`services/mcp/sammlungspflege.py`): Agent und
  Muster fragen das je Werkzeug ab. Ein Aufruf an einen Server ohne sie endete im Fehler.
- **Umsortieren an einem älteren Server lehnt der Client ab.** Der Server nähme auf und ließe das
  Material still in der Quelle liegen; die KI meldete „umsortiert“.
- **Lesemodus einer Einbettung:** nur `wlo_list_collection_proposals` bleibt erlaubt.
- **Abläufe:** `wlo_delete_collections` ist dort ausgeschlossen, wie jedes Löschen (SE-3). Die
  anderen lassen sich in einem Schritt mit Freigabe rufen. Abläufe fragen nicht, ob der Server
  ein Werkzeug führt: An einem älteren Server endet so ein Schritt in einer Ablehnung ohne
  Grund („WLO hat die Änderung abgelehnt“) und geht zu `bei_fehler`.
- **Nach dem Ja:** Die neuen Ablehnungen (`is_original`, `already_proposed`,
  `no_pending_proposal`, `no_change`) haben eigene Sätze für die Person, deutsch und englisch.
  `proposal_not_marked` (aufgenommen, Markierung des Vorschlags offen) hat einen eigenen Satz
  statt „der Datensatz ist angelegt“.
- **Studio:** Auf der Seite „Werkzeuge“ tragen die sieben den Grund „Server führt das Werkzeug
  nicht“, solange es so ist. Am MCP-Server tragen sie Schalter; die Warnung „fehlt am Server“
  gilt für sie nicht.
- **Muster M18** nennt die Werkzeuge mit dem Zusatz „nur wenn angeboten“ und dem Einzelweg als
  Rückfall. **Master-Skill** ohne Werkzeugnamen: Stapel-Werkzeug nehmen, wenn angeboten;
  „vorgeschlagen“ ist nicht „aufgenommen“; vor dem Umhängen die Rechte nennen.

## Gemessen

Am neuen Stand des Servers (lokal gestartet, anonym, nur lesend): Alle sieben stehen in
`tools/list`. Pflichtfelder und Parameter unserer Definitionen decken sich mit seinen Schemata;
nur `confirmToken` und `continuationToken` bieten wir der KI bewusst nicht an. Die drei
Plan-Werkzeuge sind genau die, die bei ihm einen `continuationToken` führen;
`wlo_list_collection_proposals` ist als lesend gekennzeichnet.

## Nicht geprüft

Jede Vorschau und jedes Schreiben: Das braucht eine Anmeldung am neuen Stand, also dessen Deploy
auf Staging. Die Status je Eintrag (`moved`, `proposed`, `not_empty`, `order_not_set` …) kommen
als Text des Servers bei KI und Person an. Der Chatbot selbst liest aus einer Plan-Antwort nur
`complete`, `continuationToken` und `expiresAt`; ein Ablauf zusätzlich, ob jeder Eintrag
`failed` oder `not_stored` ist (dann gilt der Schritt als gescheitert). Lauter `proposed` gilt
als erledigt: Die Vorschau hat gesagt, dass vorgeschlagen wird.

## Review

Ein unabhängiges Review fand 1 schweren, 6 mittlere und 4 kleine Punkte. Behoben:

1. **Falscher Satz nach dem Annehmen eines Vorschlags (schwer).** Meldet der Server
   `proposal_not_marked` (aufgenommen, Markierung offen), las die Person „Der Datensatz ist
   angelegt … lege ihn nicht noch einmal an“. Angelegt wurde nichts. Jetzt ein eigener Satz.
2. **Mittlere:**
   - Ein bestätigter Umsortier-Plan wurde lokal abgelehnt und verworfen, wenn der Stand des
     Servers gerade unbekannt war (Neustart, drei gescheiterte Abfragen). Aufrufe mit einem
     Schlüssel des Servers lehnt der Client nicht mehr ab.
   - Die neuen Ablehnungen hatten keinen Satz für die Person.
   - In einem Ablauf galt „nicht eingereicht“ (`not_stored`) als Erfolg.
   - `removeFrom` an der falschen Stelle fiel still weg; jetzt lehnt der Client ab.
   - Die Beschreibung von `wlo_delete_collections` sagt jetzt, dass „leer“ heißt: nichts, was
     diese Anmeldung sehen kann.
3. **Kleine:** `order` steht nicht mehr mit Wert im Log; M18 nennt den Leseschritt vor dem
   Ordnen und Zurücknehmen.

Bewusst so gelassen: Lauter `proposed` in einem Ablauf gilt als erledigt (die Vorschau hat es
gesagt). Abläufe prüfen nicht, ob der Server ein Werkzeug führt.

## Geprüft

- Backend: volle Suite 10 488 Tests grün (5 übersprungen); neu `tests/test_mcp_sammlungspflege.py`, angepasst die Wächter über den
  Kuratier-Katalog.

## Deploy

- Keine Migration, keine neue Variable, keine Reihenfolge zum MCP. Image neu bauen.
- `import-config --werksabgleich` (Werkzeugliste des MCP-Servers, Muster M18);
  Master-Skill-Knoten in WLO mit `docs/skills/vorgehen-knapp.md` ersetzen.
