# Befund 2026-10-08: Die Schreib-Abnahme verfällt am unsichtbaren Kontext-Ping

Stand 2026-10-08. Gemeldet vom Nutzer (Staging, Agent-Modus, mit WLO-Konto angemeldet). Behoben am selben Tag. Die Ursache ist durch Nachstellung belegt; die Bestätigung aus dem Staging-Log steht aus (siehe „Offen“).

## Befund

- Auftrag: eine Wikipedia-Seite zur Optik erschließen und in die Sammlung „Optik“ aufnehmen.
- Die Erschließung klappte, der Knoten `f5410fbd…` liegt im Staging-Repositorium.
- Die Aufnahme kam nie über die Vorschau hinaus. Auf „dann füge den Inhalt der Sammlung hinzu“ kam die Vorschau zu `wlo_add_to_collection` mit der Bitte „Bitte bestätigen Sie mit ‚Zum Aufnehmen bestätigen‘“. Auf genau diese Antwort folgte wieder nur eine Vorschau.
- Das Modell erklärte es selbst mit einem fehlenden `confirmToken` im Werkzeug. Das ist Absicht: Das Modell sieht und setzt den Schlüssel nie (`domain/write_confirm`); eingelöst wird im Vorlauf, deterministisch, wenn die Person zustimmt.
- Der Verlauf nennt die Knoten-ID „aus dem Seitenkontext“. Das Widget lief also mit Seitenkontext (Browser-Erweiterung bzw. Einbettung).

## Ursache

- `graph/nodes/setup` ruft in **jedem** Zug `services/write_approval.discard_stale_approval`. Ist der Zug keine glatte Zustimmung, verwirft es den offenen Vorgang und speichert das sofort (Audit 2026-09-29, Review Paket 2: „Bestätigen kann nur die Antwort direkt auf die Vorschau“).
- Das Widget schickt zwei Züge von sich aus. Beide laufen über `POST /api/chat` durch `setup`:
  - den **Kontext-Ping** `[context-open]` (`page_event`), beim ersten Laden, bei jeder URL-Änderung der Gastseite (`host-bridges._checkUrlChange`), bei `replaceContext` der Browser-Erweiterung und bei jedem Neu-Initialisieren;
  - den **Tour-Tick** `[tour-tick]` (`tour_action: tick`), bei jedem Seitenaufruf mit gesetztem Tour-Flag oder über einen `?bsid=`-Link (`shell/lifecycle.ts`).
- Ihre Antwort zeigt das Widget nur, wenn sie Inhalt hat (`context-greeting.controller.ts`, `tour.controller.ts`). Eine schon begrüßte Seite und ein Tick ohne laufende Tour bleiben stumm.
- Folge: Zwischen Vorschau und „Zum Aufnehmen bestätigen“ lag ein Zug, den die Person nie gesehen hat. Er verwarf den Vorgang in der Datenbank. Der Vorlauf fand danach nichts mehr zum Einlösen, und der Agent (`write_mode: propose`) konnte nur eine neue Vorschau holen.
- **Belegt** durch die Nachstellung über drei Züge (`tests/test_abnahme_nach_kontext_ping.py`): Ohne Ping wird ausgeführt. Mit stummem Ping dazwischen kommen zwei Vorschau-Aufrufe und keine Ausführung, genau das Bild im Verlauf.
- **Geprüft und ausgeschlossen:**
  - der Vorschautext des MCP-Servers: Er trägt den Schlüssel im Format, das `extract_confirm_token` liest (`previewReply`, `referenceHandler`);
  - die Zustimmung: „Zum Aufnehmen bestätigen“ besteht `is_affirmation` (Stamm „bestatigen“);
  - das Kennzeichen des Aufrufers: Der Zugangsblock liegt im `sessionStorage`, kein Auffrischen;
  - der Werkzeug-Zwischenspeicher: Die Kurationswerkzeuge sind ausgenommen (`_TOOL_CACHE_BLOCKLIST`).
- **Nicht ausgeschlossen, aber im Log unterscheidbar:** Kommt die Zustimmung nach mehr als zehn Minuten, ist der Schlüssel abgelaufen (`is_expired`, 600 s), und es folgt dasselbe Bild. Dann fehlt im Log die Zeile „verworfen“ (siehe „Offen“).

## Änderung

- `domain/hintergrund_zug.py` (neu): die eine Definition dessen, was das Widget von sich aus schickt. Es gibt `ist_kontext_ping`, `ist_tour_tick` und `ist_hintergrund_anfrage`; eine Tour-Aktion geht vor. Gelesen von `setup`, `api/chat`, `context_greeting` und `tour` (Konstante `TOUR_TICK`).
- `graph/nodes/setup.py`: `_hintergrund_zug(req, session_state)`.
  - Während einer laufenden Tour ist kein Zug Hintergrund. Der Tick wird zum Tour-Schritt, der Ping je nach Schritt zur Gruppenantwort oder zum Ende der Tour. Die Tour schreibt nur `tour_state`, also verfällt der Vorgang wie bisher sofort.
- `services/write_approval.discard_stale_approval(…, hintergrund=)`: Ein Hintergrund-Zug nimmt den Vorgang nur aus dem Zug, schreibt nichts und loggt „ruht — Hintergrund-Zug“.
- **Ein Hintergrund-Zug endet jetzt nur auf zwei Arten** (Review, Befund 1):
  - stumm: Dann schreibt niemand, und die Antwort der Person trifft den Vorgang an.
  - mit einer gespeicherten Begrüßung: Die schreibt `entities` samt Verfall zurück.
  - Dafür enden alle Fehlerwege stumm:
    - `api/chat`: Eine Ausnahme ergibt bei Ping und Tick eine leere Antwort ohne Eintrag im Verlauf statt der Fehlerblase. Die Widget-Controller wollten Ping-Fehler ohnehin still schlucken.
    - `context_greeting`: Ein Gruß, dessen Speichern scheitert, bleibt stumm. Wirft die Begrüßung, endet der Ping leer, statt `[context-open]` durch den gewöhnlichen Zug zu schicken.
- **Unverändert:** Eine sichtbare Begrüßung, ein Tour-Schritt, eine Direkt-Aktion oder jede andere Nachricht lassen den Vorgang verfallen, wie bisher.

## Tests

- `tests/test_abnahme_nach_kontext_ping.py` (neu, 6 Tests, echte Anmeldung über den Zugangsblock):
  - über die Knoten `setup` → `tour` → `context_greeting` → `preflight` → `respond_agent`:
    - Gegenprobe ohne Ping;
    - unsichtbarer Kontext-Ping;
    - Tour-Tick ohne Tour;
    - sichtbare Begrüßung einer neuen Seite: Es wird nichts ausgeführt, der Verfall steht in der Zeile;
  - über den kompilierten Graphen (`build_turn_graph`/`run_turn`, samt `page_context_enrich`), Review-Befund 2:
    - stummer Ping: kein Schreibvorgang, danach wird eingelöst;
    - Begrüßung: Der Verfall steht in der Zeile.
- `tests/test_hintergrund_zug.py` (neu): die drei Prädikate samt Normalisierung und Vorrang der Tour-Aktion.
- `tests/test_setup_node.py`: 6 Fälle, parametrisiert. Ping und Tick ohne Tour schreiben nichts. Ping und Tick während einer Tour sowie ein unbekanntes Ereignis verwerfen sofort.
- `tests/test_write_approval.py`: `hintergrund=True` nimmt den Vorgang aus dem Zug, ohne zu schreiben.
- `tests/test_chat_endpoint.py`: Ping und Tick scheitern stumm, ohne Eintrag im Verlauf.
- `tests/test_context_greeting.py`:
  - ein ungespeicherter Gruß bleibt stumm;
  - eine Ausnahme beim Ping endet leer, ohne Ping läuft der Zug weiter wie bisher.
- **Gegenproben:**
  - Ohne den Fix fallen genau die 6 neuen „bleibt stehen“-Tests.
  - Ohne die Tour-Bedingung fallen genau die 2 Tour-Wächter.
  - Ohne (a), (b) oder (c) aus dem Review fallen genau deren 4 Tests.

## Verifikation

- Betroffene Bereiche: `pytest tests/test_hintergrund_zug.py tests/test_abnahme_nach_kontext_ping.py tests/test_chat_endpoint.py tests/test_context_greeting.py tests/test_setup_node.py tests/test_write_approval.py tests/test_tour_node.py tests/test_agent_schreib_abnahme.py tests/test_graph_build.py`, 195 passed.
- `ruff check .`: sauber.
- Volle Suite (`uv run pytest -q`, Endstand): 5229 passed, 4 skipped in 24:27. Die vier Skips sind die übliche Zahl; kein Modul fiel am Datenbank-Tor still aus.

## Review mit frischem Blick

Ein Prüfer, Ergebnis: 1 MAJOR, 1 MINOR, 4 NITs. Alle Befunde sind gegen den Quelltext geprüft und behoben.

- **Befund 1 (MAJOR), behoben:** Ein Hintergrund-Zug konnte sichtbar enden, ohne `entities` zu schreiben. Drei Wege:
  - (a) Fehlerblase des Endpunkts;
  - (b) Gruß trotz Speicherfehler;
  - (c) Ausnahme in der Begrüßung, danach der gewöhnliche Zug.

  Ein „ok“ nach so einer Nachricht hätte den Vorgang eingelöst. Auf `main` war das ausgeschlossen. Behoben wie unter „Änderung“.
- **Befund 2 (MINOR), behoben:** Die Nachstellung lief über die Knoten von Hand. Dazu kommen die zwei Tests über den kompilierten Graphen.
- **NITs, behoben:**
  - genauere Begründung und `isinstance`-Wache in `_hintergrund_zug`;
  - eine Logzeile im Hintergrund-Zweig;
  - Docstrings (`is_expired`, „direkt vorigen Zugs der Person“);
  - ein gemeinsames Modul statt doppelter Ereignisnamen.
- **Vorbefunde, nicht angefasst** (`graph/nodes/tour.py`):
  - **P1:** Ein Ping bei serverseitig laufender Tour wird zur Gruppenantwort, und `[context-open]` landet als Nachricht im Verlauf. Oder er beendet die Tour. Nur das Tour-Flag im Widget verhindert das.
  - **P2:** Die Tour-Auslöser werden als Teilstring auch gegen `[context-open]` geprüft. Eine im Studio gepflegte Phrase wie „open“ startete die Tour aus einem Ping.

## Offen

- **Bestätigung auf Staging (Nutzer).**
  - Im Backend-Log steht, wenn es diese Ursache war, direkt nach der Vorschau und vor der Zustimmung: `offener Vorgang für wlo_add_to_collection verworfen — dieser Zug ist keine Antwort auf die Vorschau`.
  - Fehlt die Zeile und lagen mehr als zehn Minuten zwischen Vorschau und Zustimmung, war es die Frist.
  - Nach dem Deploy denselben Ablauf wiederholen. Ein Ping dazwischen steht dann als `offener Vorgang für … ruht — Hintergrund-Zug` im Log.
- **Beim Deploy:** nur das Backend-Image. Keine Migration, das Widget ist unverändert.
- **Nebenbefund, nicht untersucht:** Der Gatekeeper-Skill der Sammlung „Optik“ ließ sich laut Verlauf mit der gelieferten Knoten-ID nicht abrufen (`get_skill`).

## Log

- 2026-10-08: Ursache nachgestellt (rot), Fix in `setup`/`write_approval`, Einheitstests, Gegenproben.
- 2026-10-08: Review mit frischem Blick. Befund 1 (a–c), Befund 2 und die NITs behoben, je Test zuerst rot, Gegenproben.
- 2026-10-08: Volle Suite grün (5229 passed, 4 skipped), `ruff` sauber.
