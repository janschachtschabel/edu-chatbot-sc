# Paket TB-T1: Antworten und Materialien erreichen den Themenbaum (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md`, Gruppe T. Grundlage ist der Auftrag N15: die
Kernfragen aus dem Gestaltungsleitfaden und dem Klick-Prototyp sollen den Entwurf eingrenzen, und
der Themenbaum aus Inhalten soll die Metadaten der hochgeladenen Materialien nutzen.

## Umsetzung

- **Wahl als Teil:**
  - `schreibt` gibt es jetzt auch an einer `nachricht` mit Schnellantworten. Die gewählte Option
    schreibt ihr **deutsches** Label (sonst die Kennung) als Text-Teil, in jeder Sprache gleich
    (`treiber.wahl_wert`, nach dem Review). So verzweigt `wenn_wert` sprachfest, und die
    Simulation zeigt in jeder Studio-Sprache denselben Weg.
  - In der Kennzeile steht „Wahl: <Label>“. Das ist Text der Redaktion, nie eine Eingabe der
    Person.
  - Heißt der Teil wie der Freitext des Schritts, ergeben Wahl und Tippen denselben Teil. Eine
    Wahl leert ihn dann nicht.
  - Heißen sie verschieden, leert jede Antwort die andere aus einem früheren Durchgang. Eine
    Wahl leert den Freitext, wie bisher, ein Freitext leert die Wahl, das ist neu.
  - Die Teile gelten schon für die Schritte desselben Zuges, so wie beim Freitext.
  - **Prüfung:** `schreibt` an einer Nachricht ohne Schnellantworten ist ein Befund
    (`wahl_schreibt`).
  - **Weitere Stellen:** Typtabelle (`typen.schritt_ausgaben`: TEXT), Datensicht der Testfälle
    (`option`), Studio-Hinweis de/en, Bereichsschema und OpenAPI neu exportiert.
  - **Bewusst nicht:** Freitext wird nicht in den `hinweis` eines Agent-Schritts eingesetzt. Das
    wäre ein Einfallstor für Anweisungen. Die KI sieht die Antworten im Verlauf und die Teile in
    der Arbeitsstands-Zeile.
- **`ui_strukturentwurf` mit `aus_inhalten`:**
  - **Manifest:** neuer Parameter `aus_inhalten`, `manifeste.json` neu erzeugt.
  - **Datenquelle:** Der Dienst liest den Teil `metadaten` selbst aus dem Vorgang
    (`metadaten.TEIL`, fest wie `draft` für `vorlage`). Er nimmt ihn nie aus den Argumenten.
  - **Umwandlung:** `metadaten.als_dokument` macht daraus ein `DokumentStand` im Format
    `wlo-inhalte`. Jedes Material wird ein Abschnitt mit Titel, Beschreibung, Schlagworten,
    Fächern, Stufen und Art.
  - **Wiederverwendung:** Danach läuft alles über den Weg von `aus_dokument`. Ebene 2 liest die
    Auszüge der zugeordneten Materialien, mit Moderation, Fundstelle und Deckeln.
  - **Eigene Aufforderung für Ebene 1** (`prompt.oben_aus_inhalten`): Die Materialien werden
    thematisch gruppiert, statt der Ordnung eines Dokuments zu folgen. Die Punkte heißen nach
    dem Thema, nicht nach Dateinamen.
  - **Moderation:** Übersicht und Anfang der Materialliste gehen vor Ebene 1 durch die
    Moderation, wie ein Dokument beim Hochladen. Gibt es kein Urteil, entscheidet
    `MODERATION_FAILURE_MODE`. Ebene 2 moderiert die Auszüge wie bisher.
  - **Fehler für die KI:** `keine_inhalte` (der Teil fehlt oder hat eine andere Form),
    `inhalte_ausschluss` (nicht zusammen mit `vorlage` oder `aus_dokument`, geprüft vor jedem
    Lesen), `abgewiesen` und `pruefung_fehlt`.
  - Im Manifest steht unter `wann` ein Fall für `aus_inhalten`.
  - `quelle` bleibt `dokument`. Eine eigene Quelle bräuchte eine Änderung am Widget, und die
    Bedeutung „aus Unterlagen der Person“ trifft zu.

## Review (unabhängig) und Behebung

3 MAJOR, 6 MINOR, 5 NIT.

- **MAJOR 1:** Bei `aus_inhalten` gingen Titel und Beschreibungen ohne Moderation an Ebene 1.
  - Grund: Beim Dokument deckt das die Moderation beim Hochladen ab, hier fehlte der Schritt.
  - Jetzt prüft `metadaten.moderationstext` die Übersicht und die ersten 4000 Zeichen vorher.
  - Tests: beanstandet, und ohne Urteil im geschlossenen Ausfallmodus.
- **MAJOR 2:** Der Wert hing von der Sprache ab. `wenn_wert` verzweigte für englische Personen
  anders, und die Simulation folgte der Studio-Sprache. Jetzt ist der Wert immer das deutsche
  Label. Treiber, Datensicht und Simulation nutzen dieselbe Regel (`wahl_wert`).
- **MAJOR 3:** Ein Freitext ließ eine frühere Wahl anderen Namens stehen. Jetzt leert er sie,
  das ist die Gegenrichtung zu AS-3, Befund 3. Tests decken die Schleife ab, mit und ohne frühere
  Wahl.
- **MINOR 4:** `als_dokument` prüft jetzt `format` und die Listentypen. Eine Zeichenkette als
  Fächerliste wird nicht mehr in Zeichen zerlegt.
- **MINOR 5:** Ob die Wahl einen Teil schreibt, gilt nur an `nachricht`. Ein verdecktes
  `schreibt` an `modul` unterdrückt das Leeren nicht mehr.
- **MINOR 6:** `_einpassen` kürzt vor dem Weglassen auch die Listen. Weggelassene Materialien
  stehen in `fehlend`.
- **MINOR 7:** Neuer Hinweis `metadaten_teil`, wenn `metadaten_lesen` nicht unter `metadaten`
  schreibt.
- **MINOR 8:** Die Planzeile TB-T1 nennt die Abweichung (keine Platzhalter im Hinweis).
- **MINOR 9:** Tests:
  - gleicher Name;
  - Schleife;
  - Sprache;
  - Datensicht;
  - Auszug eines Materials;
  - Moderation;
  - Ausschlusstext;
  - Hinweis.
- **NITs:**
  - Kommentar wieder an seinem Code;
  - Datensicht nutzt `wahl_wert`;
  - genauerer Befundtest;
  - Ausschluss vor dem Lesen der Vorlage;
  - `wann` im Manifest.
- **Nicht geändert:** Die Beschriftung „Entwurf (aus Dokument)“ bleibt auch für Materialien,
  weil `quelle: dokument` gewählt ist. Die Frage, ob Strukturdateien (`rolle: struktur`) die
  Gliederung vorgeben sollen, steht unter „Grenzen“.

## Prüfung

- **Neue Tests:** `test_tb_t1_antworten_und_inhalte.py` mit 9 Fällen, zuerst rot; nach dem
  Review 19. Zusammen mit TB-F2 sind es 31 grün.
- Nach dem Review lief der breite Satz (ablauf, strukturentwurf, ui_modul, Schema, OpenAPI,
  Config, Seeds, Werk) mit 2444 grün. ui-module: 348 grün.
- **Backend:** ablauf, strukturentwurf, ui_modul, Schema, OpenAPI und Config: 1936 grün.
  - `test_ablauf_studio_k2c1` erwartet jetzt `nachricht` bei `schreibt`.
  - `strukturentwurf_dokument` liest `format` per `getattr`, weil die Test-Attrappen kein
    `format` haben.
- **Frontend:** Studio 2144 grün, ui-module 348 grün.
- ruff ist sauber.

## Grenzen

- Der Teil heißt fest `metadaten`. Ein Ablauf muss das Ergebnis von `metadaten_lesen` unter
  diesem Namen schreiben. Der Seed tut das.
- `als_dokument` nimmt auch Strukturdateien (`rolle: struktur`, etwa einen Lehrplan) als
  Material. Ob sie die Gliederung vorgeben sollen, ist offen und gehört zu TB-4.
- Englische Personen sehen in `{teil.zweck}` das deutsche Label. Das ist der Preis des
  sprachfesten Werts, und die Seeds setzen den Wert nicht in Texte ein.
- Ebene 1 sieht nur die Titel (≤ 8000 Zeichen Übersicht) und den Anfang (1500 Zeichen). Bei
  50 Materialien reicht das für die Titel; die Beschreibungen sieht erst Ebene 2.
