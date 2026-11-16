# Datenmodell: Auswahl mit Dateien, feste Nummer, Metadaten bis 500 (2026-11-16)

Anlass: Datenmodell des Nutzers vom 16.11. (Grafik „Übergabe an den Chatbot“, Plan
`docs/plans/2026-11-16-themenbaum-generisch.md`, Abschnitt „Datenmodell“):

> Ordnerstrukturen bleiben erhalten, mit den Dateinamen bzw. node_ids je Ordner, damit sich beides
> verknüpfen lässt.

Pakete TG-3a, TG-3b und TG-3c des Plans; noch ohne unabhängiges Review. TG-3d bis TG-3f folgen in
einem eigenen Paket.

## Was sich ändert

### TG-3a: Teil `struktur` (`wlo.auswahl@1`)

- **Upload-Feld:** Jede Antwort (`erfasst`, `dokument`, `uebertragen`) trägt den vollen Ordnerbaum
  mit den Dateien je Ordner (`dateiliste`). Je Datei:
  - `i`: die feste Nummer in der Auswahl (Stelle in der nach Pfad sortierten Erfassung). Sie bleibt
    gleich, wenn die Person Rollen ändert;
  - Name (eine Zeile, höchstens 120 Zeichen), Endung (kleingeschrieben, leer ohne Endung), Größe,
    Rolle (`inhalt`, `struktur`, `ignorieren`).
  - Systemdateien (`.DS_Store`, `Thumbs.db` …) fehlen, wie im Baum der Ansicht. Binärdaten nie.
- **Grenzen:** höchstens 500 Dateien (wie bisher, Warnung `zu_viele`). Ein Datei- oder Ordnername
  über 120 Zeichen wird gekürzt und gemeldet: neue Warnung `namen_gekuerzt` („Namen über 120
  Zeichen sind gekürzt.“ / „Names longer than 120 characters are shortened.“).
- **Manifest:** `$defs.datei`, `dateiliste` an jeder der neun Ordnerebenen (nicht Pflicht),
  `namen_gekuerzt` in den Warnungen, `vorgang.schreibt` = `structure`, `struktur`, `document`.
  Beschreibung: „Zurück kommen Ordner- und Dateinamen mit Zahlen (du siehst nur eine
  Zusammenfassung), nie Inhalte.“ Ein Beispiel trägt Dateien.
- **Backend:**
  - `teile_aus_antwort` schreibt den Teil `struktur` (`{struktur, zahlen, warnungen}`) und weiter
    `structure` als abgeleitete Sicht nur mit Ordnern. Bestehende Abläufe und
    `strukturentwurf_aus_ordnern` laufen unverändert.
  - Kurzbeschreibung des Teils: „12 Dateien in 3 Ordnern, davon 1 Strukturdokument“ (gezählt wird,
    was nicht ignoriert ist; „ohne Ordner“ bei losen Dateien).
  - `struktur` steht in `BEREITSTELLUNG`: Beim Start eines Ablaufs geht er mit in den neuen
    Vorgang.
  - Die Antwortform prüft zusätzlich: höchstens 500 Dateien über alle Ordner, jede Nummer `i` nur
    einmal, nicht mehr Dateien mit Rolle `struktur` als `zahlen.strukturdokumente`. Dateinamen werden wie Ordnernamen zu einer Zeile normalisiert.
  - **Die KI** sieht im Rahmen `[ORDNER …]` nur „Dateien: 12 Dateien in 3 Ordnern, davon 1
    Strukturdokument. Ihre Namen liegen im Vorgang (Teil struktur), nicht hier.“ Keine Liste.
  - **Sicherheitsprüfung:** Sie liest die Dateinamen (Text der Person) als Letztes im Vorsatz,
    gedeckelt auf 3000 Zeichen wie die Ordner-Übersicht. Der Vorsatz bleibt so unter rund 13 000
    Zeichen, weit im ganz geprüften Teil der Moderation (8 Abschnitte zu 4000 Zeichen) — 500 lange
    Namen schieben die Nachricht nicht in die nur teilweise geprüfte Mitte.
  - Dateinamen kommen nicht ins Log (Test über Prüfung, Teile und Rahmen).
  - Dienst `bereitgestellt` meldet zusätzlich `dateien` (nicht ignoriert) und `inhaltsdateien`
    (Rolle `inhalt`) aus dem Teil `struktur`; ohne ihn beide 0. Die Kurzbeschreibung nennt „n
    Dateien“.
  - Typ `wlo.auswahl@1` in `services/ablauf/typen` (`AUSWAHL`, `MODUL_TEILE`).
- **Ablauf „Themenbaum · aus Ordnern“:** „Andere wählen“ verwirft jetzt `structure` und
  `struktur` — sonst bliebe die Auswahl mit den Dateien der abgelehnten Ordner liegen
  (`bereitgestellt` zählte sie). Die Fassung des Seeds ändert sich damit (wie schon mit TG-2).
- **Studio:** Typname „Auswahl mit Dateien“ / „Selection with files“ (Sicht „Daten“).
- **Datenschutzsatz im Feld** (Nutzer-Entscheid G-E1), vier Fassungen je nach Angebot, alle mit
  „Ordner- und Dateinamen gehen an den Chat“ / „Folder and file names go to the chat“, dazu wie
  bisher, wann das Strukturdokument hochgeladen wird und wann Dateien an WLO gehen.
- `docs/ui-module.md`, `docs/ablaeufe.md` und `ui-upload/README.md` mitgezogen.

### TG-3b: feste Nummer `i` in der Ablage

- Der Vertrag mit dem MCP zählt nach der Stelle: `wlo_prepare_file_batch` nummeriert `entries`
  0…n−1 (`curation-batch.ts`), `wlo_store_batch_file` nimmt diese Stelle. Daran ändert sich nichts.
- Die Freigabe des Widgets trägt je Eintrag zusätzlich `i` (`AblageEintrag.i`), die Nummer der
  Datei in der Auswahl — nicht die Stelle in der gefilterten Übertragungsliste (eine zu große Datei
  oder eine unbekannte Art fehlt dort).
- Das Backend (`Eintrag.i`, eindeutig, sonst 422) merkt sich `i` je Eintrag im Teil `ablage`
  (`vorgang_teil.aus_plan`, Feld `i` neben `index`). An das MCP geht `i` nicht.
- Damit sind Ordner (Teil `struktur`) und node_id (Teil `ablage`) über `i` verknüpft. Das schließt
  T1 / `ablage_zuordnen` in `docs/offene-befunde-und-todo.md`.

### TG-3c: Teil `metadaten`

- Je Node `lizenz`: das Feld `license` von `get_nodes_details` (lesbare Bezeichnung aus
  `ccm:commonlicense_key`, etwa „CC BY-SA“), auf 60 Zeichen; leer ohne Angabe.
- Je Node `i` aus dem Eintrag in `ablage` (`null` bei einem Stapel ohne Nummern).
- Gelesen in Blöcken zu 50 (Grenze von `get_nodes_details`), nacheinander, bis 500 Nodes (vorher
  50). Ein gescheiterter Block hält an; der Rest steht in `fehlend`. Scheitert schon der erste,
  entsteht wie bisher kein Teil. **Praktisch** sind es höchstens 200 je Stapel: so viele Einträge
  nimmt eine Freigabe der Ablage (`api/ui_ablage.Vorbereiten`, `max_length=200`); 500 erreicht nur
  ein Teil `ablage` mit früheren Stapeln (`frueher`).
- Der ganze Teil bleibt samt `fehlend` unter 60 000 Bytes (unter `teil_verweise.MAX_BYTES`). Gekürzt
  wird in dieser Reihenfolge: Beschreibung auf 100 und leer, Listen auf 2 und leer, Titel auf 80,
  leere Felder weglassen, zuletzt Inhalte vom Ende nach `fehlend`. Der Leser des Entwurfs
  (`als_dokument`) nimmt auch die verdichtete Form.

## Rückwärts

- **Antworten ohne `dateiliste`** (ein offenes Widget mit altem Bündel) bleiben gültig. Sie
  ergeben wie bisher nur den Teil `structure`; `bereitgestellt` meldet dann 0 Dateien.
- **Freigaben ohne `i`** (altes Bündel) gehen wie bisher; der Eintrag in `ablage` hat dann kein `i`.
- Laufende Abläufe lesen `structure` unverändert. Nur der Seed „aus Ordnern“ ändert sich
  (`verwirft`); er ist mit TG-2 ohnehin neu, `import-config --werksabgleich` wie dort.
- Bestehende Teile `metadaten` ohne `lizenz`/`i` bleiben lesbar (`get`).

## Geprüft

- **Backend:** gezielt `test_tg3a_struktur_auswahl.py` (neu, 17), `test_tb_f2_metadaten_lesen.py`
  (TG-3c: Lizenz, `i`, Blöcke, Abbruch, Kürzung bei 500 vollen Nodes, kleine Teile ungekürzt),
  `test_ui_ablage_api.py` (TG-3b: gefilterte Auswahl ergibt `i` 0 und 2, ohne `i`, doppelt → 422),
  `test_tg2_bereit_und_verwirft.py`, `test_ablauf_zug.py` (Start übernimmt `struktur` in den neuen
  Vorgang), `test_ui_upload.py`, `test_arbeitsstand.py`,
  `test_restbefunde_rb2.py`. Dazu `pytest -k "upload or ablauf or ordner or dokument or seed or
  ui_modul or arbeitsstand or vorgang or metadaten or ablage or restbefunde"`: 1852 bestanden, 1 übersprungen; nach der Änderung am Seed „aus Ordnern“ dazu `-k "seed or werksabgleich or sammlungsstruktur or verwirft or datenfluss"`: 296 bestanden.
  ruff sauber.
- **Frontend:** `ui-module` 410, `studio` 2156, `ui` 1513 Specs grün. Neu: Dateien je Ordner mit
  `i`, `i` stabil bei Rollenwechsel, Endungen, `namen_gekuerzt`, 500 Dateien, Datenschutzsatz,
  Manifest (`dateiliste` an allen neun Ebenen, `struktur`), gefilterte Freigabe trägt `i` 1 und 2.
  ESLint sauber.
- **Playwright** (`npm run build:widget`): `upload-erfassen`, `upload-uebertragen`,
  `upload-und-fortschritt` — 12 grün (Antwort mit `dateiliste`, nie `%PDF`; Freigabe mit `i`).
- **Drift:** Manifeste neu erzeugt (`module:register`); OpenAPI neu erzeugt (nur `Eintrag.i`),
  danach ohne Drift; Bereichs-Schemas unverändert.
- **Nicht geprüft:** die ganze Backend-Suite, ein Chat-Smoke (ob die KI mit der Zusammenfassung gut
  fragt), `metadaten_lesen` gegen das echte MCP mit mehr als 50 Nodes.

## Review-Behebung (16.11., nach TG-3d–f)

Review TG-3a–c: 1 MAJOR, 4 MINOR, 2 NIT. Entscheide im Plan unter „Review TG-3a–c (16.11.)“.

- **R3-1 (MAJOR), Namen nur an die Moderation:**
  - Vorher lief das Regex-Gate über die Datei- und Ordnernamen. Eine Datei „Suizid-Prävention.pdf“
    ergab high/M01: Krisenantwort, keine Teile gespeichert, und `preflight` schrieb den Prüftext
    samt Namen nach `quality_events`.
  - Jetzt trennt `antwort.sicherheits_teile` freien Text und Namen (`PruefText`). Das Regex-Gate
    sieht nur den freien Text. Die Namen gehen über `assess_safety(…, nur_moderation=…)` an die
    Moderation (zuerst, wie vorher) und an die Injection-Muster (nur `medium`), nicht an die
    Rechtsprüfung.
  - Ins Protokoll kommt `antwort.protokoll_text`: der freie Text, mit einer Auswahl im Zug ohne
    zitierte Namen der Blase („Ordner „…“ erfasst“). Das gilt für `preflight` und
    `build._log_turn_safety`.
  - Welche Antwort nur Namen trägt, sagt `Form.sicherheit_nur_namen`: `ui_upload` immer,
    `ui_strukturentwurf` nur unbearbeitet (dann stammen die Titel aus Ordnern, WLO oder der KI;
    bearbeitete Titel können Sätze der Person sein und gehen weiter durch alle Stufen).
  - Mit der Stufe „regex“ (ohne Moderation) prüft die Namen nur noch die Injection-Muster — eine
    Entscheidung der Redaktion beim Wählen der Stufe.
  - **Überholt durch Review TG-3d–f, MINOR 1:** Namen laufen wieder durch die Krisen- und
    Drohungsmuster, aber nur als Hinweis ohne Sperre — der Upload bleibt, die Antwort trägt die
    Hilfsnummern, im Protokoll steht der Grund `crisis_signal_in_names` bzw.
    `threat_signal_in_names` ohne Namen. Das gilt in jeder Stufe, auch „regex“. Notiz
    `2026-11-16-strukturdokumente-und-ordnerinhalte.md`.
- **R3-4, ausgeschlossene Dateien ohne Namen:** `dateiliste`-Einträge mit Rolle `ignorieren`
  tragen nur `i`, Endung, Größe, Rolle. Das Schema (`$defs.datei`, `if/then/else`) verlangt den
  Namen sonst und verbietet ihn bei `ignorieren`. Ein Bündel von vorher verliert ihn in
  `upload_antwort.rueckwaerts` vor der Prüfung — die Antwort bleibt gültig.
- **R3-2, `struktur` und `ablage` binden:**
  - Der Teil `struktur` trägt die `block_id` der Auswahl, der Teil `metadaten` die seiner Ablage.
  - `arbeitsstand_teile.gebunden` verknüpft `struktur` und `ablage` nur bei gleicher `block_id`;
    `strukturentwurf_aus_ordnern` setzt `node_id` nur dann.
  - `grund` weist eine Nummer `i` ab, die nicht kleiner als `zahlen.dateien` ist.
- **R3-3:** `struktur` geht nicht mehr pauschal an kuratierende Werkzeuge
  (`teil_verweise.NUR_UEBER_LIEST`), nur an Module, die ihn unter `vorgang.liest` nennen.
  `document` und `strukturdokument` bleiben frei (nur Namen gelesener Dokumente und Verweise).
- **R3-5:** `verwirft` nimmt die Alias-Partner mit (`typen.ALIAS_PAARE`: `structure` ↔ `struktur`,
  `document` ↔ `strukturdokument`). Die Seeds bleiben unverändert.
- **NIT:** Ein Dateiname nur aus Leerzeichen wird „(ohne Namen)“ / „(no name)“, statt die Antwort
  zu kippen. Kopf von `upload_antwort.py`, Lizenz-Beispiel „CC BY-SA“, „bis 500“ (praktisch 200 je
  Stapel) korrigiert.
- **Geprüft:**
  - Backend: neu `test_r3_review_tg3abc.py` (19) und `test_r3_struktur_gross_pg.py` (Postgres:
    Teil `struktur` über 8 KB in der Ablage, ganz gelesen, beim Start mitgenommen). Angepasst:
    `test_preflight_node`, `test_tg3a_struktur_auswahl`, `test_tg2_bereit_und_verwirft`,
    `test_tg3f_ordner_inhalte`.
  - `pytest -k "dokument or strukturentwurf or upload or ablauf or arbeitsstand or vorgang or ablage
    or restbefunde or migration or ordner or seed or bereit or tg3 or safety or preflight"`:
    2232 bestanden. ruff sauber.
  - Frontend: `ui-module` 424, `studio` 2156, `ui` 1513 Specs grün; ESLint sauber.
  - Playwright: drei Upload-Specs, 13 grün.
  - Keine Drift.

## Deploy

- Image neu bauen (Widget-Bündel und nachgeladenes Modul ändern sich). Keine Migration, keine neue
  Variable. Danach im Browser neu laden: das alte Modul-Bündel ist cachebar.
- Bis dahin schicken offene Widgets die alte Form (siehe „Rückwärts“).
