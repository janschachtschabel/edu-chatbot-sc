# Paket 4c: Rest aus den Reviews

Stand 2026-10-08. Die Reviews zu Paket 4b haben vier Punkte gefunden, die älter als das Paket sind und keinen Entscheid brauchen (Befundliste §5, „Aus dem zweiten Review von Paket 4b“, und der C6-Folgepunkt aus Paket 4). Dieses Paket nimmt sie.

Es baut auf PR #12 (`paket-4b-folgebefunde`) auf, der noch offen ist. Hochgeladen wird es als gestapelter Branch, siehe Abschnitt Abschluss.

**Nicht drin:**
- Der größere Studio-Rest nach Z2: 3d Ordner-Bereiche, 4c Reiter mit Zählern, die Architektur-Referenz (Betriebsmodi-Plan §9.3). Er bekommt ein eigenes Paket.
- Die Anzeige der *wirksamen* Bereiche je Muster (Audit F13). Sie bräuchte den Bereichskatalog im Formular; B2 macht nur den Unterschied „nicht gesetzt“ und „leer“ sichtbar.

## Aufgaben

### Phase A · Backend
Schritt 0: `/better-coding-workflow` neu laden.

- **A1 · URL-Import ohne markitdown.**
  - `convert_url_to_markdown` lädt `markitdown` außerhalb des `try` (`services/rag/ingest.py:153`). Fehlt das Paket im Image, wird der Import eine 500.
  - Umsetzung: Wie beim Datei-Weg wird daraus ein `Umwandlungsfehler` mit „(ImportError)“, bevor etwas abgerufen wird.
  - Test zuerst: `sys.modules['markitdown'] = None`, URL-Import. Erwartet wird der Typ, der Text, und dass kein Abruf passiert.
- **A2 · Ein Wert, der kein JSON ist.**
  - `json.dumps` läuft in `put`/`put_many` vor dem Schreiben und außerhalb von `als_bereichsfehler` (`services/config_store.py:229`, `:254`). Ein ungequotetes YAML-Datum in einem Bereich ohne Modell (Rohtext, Sicherung, Seed) wird eine 500 ohne Bereich.
  - Umsetzung: `als_json(area, data, ganzer_vorgang=…)` neben `als_bereichsfehler` in `services/config_conflict.py`. `TypeError`/`ValueError` werden zu `BereichNichtSpeicherbar`, wie in A4 mit dem ganzen Vorgang, wenn mehr als ein Bereich betroffen ist.
  - Die Meldung nennt beide Fälle: „etwa ein Nullzeichen oder ein Datum ohne Anführungszeichen“ (de/en). Das Log nennt statt des SQLSTATE die Art des Fehlers, nie den Inhalt.
  - Tests zuerst:
    - ohne Datenbank für `als_json`;
    - mit Datenbank für `PUT /api/config/file` auf `01-base/rag-retrieval` (Bereich ohne Modell) mit `stand: 2026-10-08`: 400 mit Bereich, nichts geschrieben.

### Phase B · Studio
Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` neu laden.

- **B1 · MCP-Abgleich ohne Werkzeuge.**
  - Meldet ein Server kein Werkzeug, hört man nur „nicht in der Liste“ bzw. den Abgleich. Der sichtbare Satz „Der Server ist erreichbar, meldet aber kein Werkzeug.“ wird nicht angesagt.
  - Umsetzung: `abgleichAnsage` stellt diesen Satz voran.
  - Test zuerst: neue Adresse, keine Werkzeuge. Die Region sagt beide Sätze.
- **B2 · Nicht gesetzt oder leer** (Listen, die `null` erlauben: `sources`, `rag_areas`, `tools` u. a.).
  - Heute zeigen „nie gesetzt“ (es gilt die Vorgabe, bei `rag_areas` alle Bereiche) und „leer“ (ausdrücklich keine) dasselbe: „Noch keine Einträge.“ Wer den letzten Eintrag entfernt, schaltet die Vorgabe ab, ohne es zu sehen.
  - Umsetzung: Eine kleine Komponente unter dem Listenkopf.
    - Nicht gesetzt: Sie sagt „Nicht gesetzt – es gilt die Vorgabe.“
    - Gesetzt: Sie bietet „Vorgabe wiederherstellen“ (setzt `null`). Die Chip-Liste zeigt „Noch keine Einträge.“ nur, wenn die Liste gesetzt und leer ist.
  - Eigene Komponente, weil `schema-field.component.ts` (311) und seine Vorlage (296) schon an der Grenze stehen.
  - Tests zuerst:
    - Komponente;
    - Feld mit `null`, mit `[]` und mit Einträgen;
    - nach dem Entfernen des letzten Eintrags steht der Knopf da;
    - „Vorgabe wiederherstellen“ setzt `null`.

### Abschluss
- Volle Suiten (Backend, Frontend zweimal, E2E), lint, `check:*`.
- Ein frischer Prüfer liest den Diff.
- Befundliste: Erledigtes streichen.
- Upload: Branch `paket-4c-rest-aus-den-reviews`, gestapelt auf `paket-4b-folgebefunde`, solange #12 offen ist; danach auf main umstellen. Den Merge macht der Nutzer.

## Log

### A1 · erledigt
- `convert_url_to_markdown` lädt `markitdown` jetzt im `try`. Fehlt das Paket, kommt wie beim Datei-Weg ein `Umwandlungsfehler` „(ImportError)“, mit Log-Eintrag und ohne Abruf.
- Test vorher rot (`ModuleNotFoundError` aus `ingest.py:153`); danach grün, beide RAG-Testdateien 59 passed.

### A2 · erledigt
- `als_json(area, data, ganzer_vorgang=…)` steht in `services/config_conflict.py` neben `als_bereichsfehler`. `put` und `put_many` nutzen es, `config_store.py` braucht `json` nicht mehr. `TypeError`/`ValueError` werden zu `BereichNichtSpeicherbar`; bei mehr als einem Bereich gilt der ganze Vorgang als verworfen, wie in A4.
- Die Meldung nennt beide Fälle (de/en): „etwa ein Nullzeichen oder ein Datum ohne Anführungszeichen“. Das Log nennt ohne SQLSTATE die Art des Fehlers (`… not storable (TypeError)`), nie den Inhalt; mit SQLSTATE bleibt die Zeile wie in R2-3.
- **Tests vorher rot (3):**
  - ohne Datenbank: `als_json` (Importfehler) und die Log-Ursache (`SQLSTATE ?` statt `TypeError`);
  - mit Datenbank: `PUT /api/config/file` auf `01-base/rag-retrieval` mit `stand: 2026-10-08` endete im `TypeError`. Jetzt 400 mit Bereich, nichts geschrieben.
- Gegenprobe ohne das Abfangen: genau der neue Test rot. Die sechs Konfig-Testdateien: 136 passed.

### B1 · erledigt
- `abgleichAnsage` stellt „Der Server ist erreichbar, meldet aber kein Werkzeug.“ voran, wenn die Liste leer ist, wie im sichtbaren Block.
- Test vorher rot (nur „nicht in der Liste“), danach 25/25.

### B2 · erledigt, mit zwei Abweichungen vom Plan-Wortlaut
- **Abweichung 1, nur wo es zählt:** Gezeigt wird der Zustand nicht an allen Listen, die `null` erlauben, sondern nur dort, wo `null` etwas anderes heißt als `[]`.
  - Gemessen sind das `sources` (ohne Angabe `["mcp"]`, `PatternDef`) und `rag_areas` (ohne Angabe alle Bereiche).
  - Bei `tools`, `precondition_slots`, `forbidden_phrases`, `anti_patterns` und `positive_markers` heißt ein fehlender Schlüssel dasselbe wie `[]`; dort wäre die Zeile Rauschen. (`null` dagegen wies `PatternDef` dort ab, siehe Review unten.)
  - Gesteuert wird das wie `Primary()` über einen Modell-Hinweis: `Vorgabe()` → `x-vorgabe`. Der Wächter `tests/test_config_vorgabe_hint.py` hält genau diese zwei Felder fest. Die Schema-Fixture des Studios ist neu erzeugt (zwei Zeilen).
- **Abweichung 2, keine eigene Komponente:** Sie hätte `schema-form.scss` einbinden müssen, das wäre eine weitere kompilierte Kopie im Bündel. Die Zeile steht direkt im Listen-Zweig von `schema-field` (Vorlage danach genau 300 Zeilen).
- **Verhalten:**
  - Eine dauerhafte Status-Region sagt „Nicht gesetzt – es gilt die Vorgabe.“, solange nichts gesetzt ist.
  - Der Knopf „Vorgabe wiederherstellen“ steht immer da. Mit `aria-disabled` statt `disabled` behält er den Fokus und wirkt nur, wenn gesetzt; gestrichelt, damit „ohne Wirkung“ nicht nur an der Farbe hängt.
  - „Noch keine Einträge.“ steht nur noch bei einer gesetzten, leeren Liste.
- **Tests vorher rot:**
  - Abbilder: `vorgabe` an `sources`/`rag_areas`, nicht an `tools`;
  - Formular: nicht gesetzt, leer, wiederherstellen, ohne Wirkung, ohne Hinweis nichts.
  - Gegenproben: Hinweis nicht gelesen → 4 rot; Wache im Knopf entfernt → 1 rot.

### Review mit frischem Blick (2026-10-08)
Ein frischer Prüfer las den ganzen Diff. Er fand einen kritischen Befund, zwei kleine und drei Kleinigkeiten. Alle sind am Code bestätigt und behoben.

- **R-1 · kritisch: „Vorgabe wiederherstellen“ schrieb `null`, und `sources: null` legte die Musterwahl lahm.**
  - Das Speichern nimmt `null` an (`PatternFrontmatter`), die Laufzeit nicht (`PatternDef.sources: list[str]`). `load_patterns()` prüft alle Muster in einem Zug.
  - Folgen: Ein Klick und Speichern an einem Muster mit `sources` hätte jeden Zug mit Musterwahl abbrechen lassen, im Muster-Modus also jeden Zug, im Agent-Modus die Krisen- und Drohungs-Züge.
  - Nachgestellt ohne Datenbank: `_pattern_from_dict({"sources": None})` und `{"tools": None}` warfen `ValidationError`; ein fehlender Schlüssel ergab die Vorgabe. `rag_areas: None` ging, deshalb fiel es an `rag_areas` nicht auf.
  - **Behoben an zwei Stellen:**
    - Studio: Der Knopf entfernt den Schlüssel (`remove`), statt `null` zu schreiben.
    - Laufzeit: `_pattern_from_dict` liest `null` wie einen fehlenden Schlüssel, außer bei Feldern, deren Vorgabe selbst `None` ist (`output_mode`, `quick_replies_max`, `rag_areas`). Damit fällt auch ein älterer Fehler weg: Ein `tools:` ohne Wert im Rohtext oder in einer Sicherung legte dieselbe Musterwahl lahm.
  - **Tests vorher rot:**
    - das Formular erwartet `{}` statt `{rag_areas: null}`;
    - `null` ergibt die Vorgabe (`sources` `["mcp"]`, `tools` `[]`);
    - ein Wächter: Jedes Feld, das das Speichern als `null` annimmt, lädt die Laufzeit.
- **R-2 · Ablauf in einer Instanz:** Ein neuer Test geht von gesetzt über leer zurück zur Vorgabe und hält fest, dass die Status-Region dasselbe Element bleibt; nur dann wird das Zurücksetzen angesagt.
- **R-3 · falsche Behauptung im Wächter:** Dort stand „`None` ist dasselbe wie `[]`“; das galt nur für den fehlenden Schlüssel. Wächter, Plan und `Vorgabe()`-Docstring sind berichtigt.
- **Kleinigkeiten:**
  - Die ersten Zeilen der Docstrings von `BereichNichtSpeicherbar` und des Handlers nennen jetzt beide Ursachen.
  - Der Zähler „(0)“ in der Legende steht nur noch bei einer gesetzten Liste, nicht neben „es gilt die Vorgabe“ (Test ergänzt).
  - Ein doppelter Satz in §5 der Befundliste ist gestrichen.
- **Älter als 4c**, in die Befundliste übernommen: `PUT /api/config/patterns` macht aus `sources: []` „nicht gesetzt“ (API-Vertrag), und die Umwandlungsfehler sind fest deutsch.

### Abschluss (2026-10-08)
- **Backend:**
  - Vor dem Review: 5193 passed, 4 skipped.
  - Nach den Review-Korrekturen: 5186 passed, 13 skipped.
    - Die 9 zusätzlichen Auslassungen sind `tests/test_guide_mode_endpoint.py`. Sein Tor `dev_db_ready()` gab beim Einsammeln nach 3 s auf, während parallel die Tests einer anderen Sitzung liefen. Einzeln danach: 9 passed, 1 skipped (der übliche, „ALT-Backend nicht erreichbar“).
    - Zusammen 5195 = 5193 + 2 neue Tests. Das stille Überspringen steht als älterer Befund in der Befundliste.
  - `ruff` ist sauber, der OpenAPI-Vertrag unverändert.
- **Frontend:**
  - ui 867, widget 71, studio 1390 (nach dem Review je zweimal).
  - lint und alle `check:*` grün; der Studio-Build hat keine Warnung.
  - E2E 50 (vor dem Review; die Korrekturen berühren nur Studio-Dateien).
- **Upload:** Branch `paket-4c-rest-aus-den-reviews`, gestapelt auf `paket-4b-folgebefunde` (PR #12). Den Merge macht der Nutzer.
- **Docker:** Auf Wunsch des Nutzers läuft nur, woran gearbeitet wird. Der Testcontainer ist gestoppt, nicht gelöscht.
