# Strukturdokumente (auch mehrere) und Ordner mit Inhalten (2026-11-16)

Anlass: Datenmodell des Nutzers vom 16.11. (Plan `docs/plans/2026-11-16-themenbaum-generisch.md`,
Abschnitt „Datenmodell“) und seine Wünsche „aus einem oder mehreren Strukturdokumenten“ und
„enthaltene Inhalte werden erschlossen oder/und gemerkt“. Pakete TG-3d, TG-3e und TG-3f des Plans;
noch ohne unabhängiges Review.

## Was sich ändert

### TG-3e: bis zu fünf Strukturdokumente je Sitzung (anonym)

- **Migration 0023** (`0023_dokumente_je_sitzung.py`): `dokument_uploads.session_id` ist nicht mehr
  eindeutig (Postgres-Name der Eindeutigkeit aus 0017: `dokument_uploads_session_id_key`), sondern
  nur indiziert (`ix_dokument_uploads_session_id`). Der Rückweg behält je Sitzung das jüngste
  Dokument und legt die Eindeutigkeit wieder an.
- **`services/dokumente/ablage.py`:** `MAX_JE_SITZUNG = 5`. `speichern` legt das neue an und löscht
  nur, was über der Grenze liegt (das älteste), samt seinem Teil in Vorgängen
  (`vorgaenge.dokument_teile_entfernen`). Zwei Uploads derselben Sitzung zugleich zählen nacheinander
  (Sperre `pg_advisory_xact_lock` je Sitzung). Neu: `alle_lesbaren`, `alle_fuer_aufrufer` (der eine
  Leseweg des Zugs; eine angemeldete Person übernimmt vorher alle anonym gelesenen derselben
  Sitzung). `aktuelles`/`fuer_aufrufer` liefern das jüngste — der Leseweg von vorher.
- **`POST /api/ui/dokumente`:** je Dokument ein Aufruf; Grenzen und Bremsen unverändert je Aufruf
  (fünf Dokumente zählen fünfmal im Fenster der Sitzung, Vorgabe 30 je Minute). Der Konflikt 409
  `laeuft_schon` entsteht nicht mehr aus zwei gleichzeitigen Uploads.
- **Übertragen nach WLO:** die Freigabe nimmt bis zu fünf Einträge mit Rolle `struktur` (vorher
  einer; das MCP begrenzt die Zahl nicht).
- **Upload-Feld** (`upload-rollen.ts`, `upload-baum.ts`): bis zu fünf Dateien mit Rolle
  „Strukturdokument“. Ein weiteres verdrängt keins mehr; ein sechstes ist im Auswahlfeld gesperrt.
  „Lesen lassen“ liest alle markierten nacheinander (`upload-dokument-ablauf.ts`), Fortschritt und
  Fehler nennen das Dokument („Dokument 2 von 3 wird hochgeladen … 40 %“, „„B.pdf“: Keine Verbindung
  zum Server.“). Nach einem Fehler: „Noch einmal versuchen“ (dasselbe Dokument, die schon gelesenen
  bleiben) und „Ohne dieses weiter“ (lässt es aus). Geantwortet wird einmal.
- **Antwort von `ui_upload`:** `dokument` bleibt das erste gelesene; bei mehreren kommt `dokumente`
  (2–5, gleiche Form) dazu. `zahlen.strukturdokumente` bis 5, `strukturdokument` ist das erste
  markierte. Das Backend prüft: `dokument` = erstes aus `dokumente`, keine doppelte Kennung, nicht
  mehr gelesen als markiert. Mit einem Dokument ist die Antwort wie vorher.
- **Rahmen an die KI:** bei mehreren „Bereit: 2 gelesene Strukturdokumente …“ und je Dokument eine
  Zeile mit Befund; die ersten Überschriften gedeckelt auf acht. Nie Text.

### TG-3d: Teil `strukturdokument` und der Leser

- **Teil `strukturdokument`** (`wlo.strukturdokumente@1`, `services/dokumente/strukturdokument_teil`):
  `{"dokumente": [{name, quelle, ref}]}` — Quelle `chatbot` mit `ref: dokument:<id>`, Quelle `wlo` mit
  `ref: <node_id>`. Höchstens zehn Einträge. Nie Text.
  - **Nach dem Lesen** schreibt ihn die Antwort von `ui_upload` (`teile_aus_antwort`); der Server
    bestätigt jeden Eintrag gegen die lesbaren Dokumente der Sitzung und nimmt deren Namen
    (`arbeitsstand._strukturdokumente_bestaetigt`). Die `chatbot`-Einträge ersetzen die vorigen, die
    `wlo`-Einträge bleiben.
  - **Nach der Ablage** schreibt `ablage/vorgang_teil.speichern` ihn mit: jeder abgelegte Knoten mit
    Rolle `struktur` (auch aus `frueher`) wird ein `wlo`-Eintrag; nur, wenn sich etwas ändert.
  - In `BEREITSTELLUNG`: ein neuer Ablaufstart nimmt ihn mit (auch die WLO-Verweise, obwohl `ablage`
    nach N14 nicht mitgeht).
  - `document` bleibt als Rückwärts-Teil (erstes gelesenes Dokument).
  - Datenschutz: Löscht die Person ein Dokument, verfällt es oder ersetzt es ein sechstes, geht sein
    Eintrag mit (`vorgaenge.dokument_teile_entfernen`; der Aufbewahrungslauf räumt verwaiste Einträge).
    Ist der letzte weg, geht der Teil.
  - Studio-Typname „Strukturdokumente“ / „Structure documents“.
- **Leser** (`services/dokumente/strukturdokument.py`): `text(eintrag)` liefert den Markdown-Text je
  Quelle — `chatbot` aus `dokument_uploads` (nur dieselbe Sitzung, derselbe Aufrufer), `wlo` über das
  MCP-Werkzeug `get_wlo_content_text` (nur lesend, ohne Cache, bis 200 000 Zeichen). `staende()` gibt
  die Dokumente mit Gliederung; ein Volltext aus WLO wird dafür wie beim Hochladen gegliedert
  (`dokument_gliederung`). `im_vorgang()` ergänzt Knoten mit Rolle `struktur` aus `ablage`, die im
  Teil noch fehlen.
- **Lader** (`dokumente/stand.lader`): mit Vorgang gelten die Einträge des Teils `strukturdokument`,
  sonst alle lesbaren Dokumente der Sitzung. Ein Dokument aus WLO braucht den Schalter
  „Dokument im Chat“ nicht (gelesen wird im Repositorium), ein Sitzungsdokument schon.
- **Moderation:** Ein Volltext aus WLO sah beim Lesen keine Moderation. Der Stand trägt `ungeprueft`;
  `ui_strukturentwurf` prüft Gliederung und Anfang vor Ebene 1 (`_ebene_eins_pruefen`, wie bei
  `aus_inhalten`). Auszüge für Ebene 2 prüft er wie immer.

### TG-3e: Generator aus mehreren Dokumenten

- `dokument_gliederung.zusammenfuehren`: je Dokument ein Abschnitt oberster Ebene (`d1`, Titel =
  Name, im Text `# Name`), seine Abschnitte eine Ebene tiefer mit Präfix (`d1-a3`), Stellen
  verschoben — Auszüge und Unterabschnitte gelten unverändert.
- `dokumente/stand.vereint`: mehrere Stände → einer; der Anfang ist je Dokument ein Stück, insgesamt
  höchstens 1500 Zeichen. Die Übersicht zeigt eine Ebene mehr (bis Ebene 4), gedeckelt auf 8000
  Zeichen insgesamt; Auszug je Punkt höchstens 6000 insgesamt.
- Eigene Aufgabe für Ebene 1 (`strukturentwurf_prompt._MEHRERE`): Dokumente werden keine Punkte,
  dasselbe Ordnungselement aus mehreren Dokumenten wird ein Punkt mit den Kennungen aus allen.
- Fundstelle „Dokument › Abschnitt“ (auf 120 Zeichen). Das Schema von `ui_strukturentwurf` nimmt
  `abschnitte` mit Präfix (`d1`, `d1-a3`).
- **Mit einem Dokument bleibt alles wie vorher** (Stand, Aufforderung, Kennungen, Fundstelle).

### Dienst `bereitgestellt`

- Neu: `strukturdokumente: [{name, lesbar}]` (aus dem Teil, dazu Knoten aus `ablage`) und
  `lesbare_strukturdokumente` (Zahl, für `wenn_wert`). Ein Sitzungsdokument ist lesbar, wenn es zu
  den lesbaren der Sitzung gehört; ein Knoten in WLO gilt als lesbar.
- `dokument.lesbar` prüft gegen alle lesbaren Dokumente (`DienstKontext.dokument_ids`), nicht mehr
  nur das jüngste — mit mehreren ist das erste gelesene nicht das jüngste. Aus demselben Grund
  bestätigt `arbeitsstand._dokument_bestaetigt` gegen alle lesbaren.
- Kurzbeschreibung nennt „n Strukturdokumente“ ab zwei.

### TG-3f: Ordnerstruktur mit Inhalten

- **`strukturentwurf_aus_ordnern`** (`ui_module/strukturentwurf_ordner.py`): liegt der Teil `struktur`
  zu denselben Ordnern vor (verglichen ohne Dateien), liest der Dienst ihn statt `structure`. Je
  Punkt `inhalte: [{i, name, node_id?}]` — die Dateien mit Rolle `inhalt` seines Ordners.
  - **Gemerkt** (auch anonym): `i` und Dateiname.
  - **Erschlossen:** `node_id` aus `ablage` (über `i`, nur `stored`), wenn die Ablage beim Entwurf schon
    vorliegt. Die Metadaten liegen im Teil `metadaten` unter derselben `i`.
  - Ordner unter der dritten Ebene fallen weg, ihre Dateien gehen an den tiefsten Punkt darüber.
    Dateien direkt in der Wurzel haben keinen Punkt. Höchstens 500 Inhalte im Entwurf (`gekuerzt`).
- **Entwurfsformat** (`ui_module/strukturentwurf.py`, Manifest): optionales Feld `inhalte` je Punkt
  (`$defs.inhalt`: `i`, `name` ≤ 120 Zeichen, eine Zeile, `node_id` optional), Eingabe und Antwort.
  `HOECHSTENS_INHALTE = 500` im ganzen Entwurf. Entwürfe ohne `inhalte` gelten weiter.
- **`ui_strukturentwurf`:** zeigt je Punkt „3 Dateien“ / „3 files“ hinter dem Titel, als
  Beschreibung des Baumeintrags (`aria-describedby`, zusammen mit „Unterthemen fehlen noch“). Keine
  Namen, kein Bearbeiten der Inhalte. Umbenennen, Verschieben, Ein- und Ausrücken lassen sie am Punkt,
  Löschen nimmt sie mit.
- **Ausgabe an die KI:** Kompaktfassung „- Mechanik (3 Dateien)“ — nie Dateinamen; `[ARBEITSSTAND]`
  nennt wie bisher nur die Kurzbeschreibung des Teils. Ein zu großer gemerkter Entwurf verliert mit
  den Texten auch die `inhalte` (sie stehen im Teil `draft`).

## Rückwärts

- Antworten mit einem Dokument (offenes Widget mit altem Bündel) bleiben gültig und ergeben wie
  bisher `document` — dazu jetzt `strukturdokument` mit einem Eintrag.
- Vorgänge ohne Teil `strukturdokument`: der Lader nimmt alle lesbaren Dokumente der Sitzung (mit
  einem Dokument genau das von vorher).
- Laufende Abläufe lesen `document` und `structure` unverändert. Der Ablauf „aus Ordnern“ bekommt
  jetzt Entwürfe mit `inhalte`, wenn der Teil `struktur` vorliegt.
- Entwürfe ohne `inhalte` und mit Kennungen `aN` bleiben gültig.

## Geprüft

- **Backend:** neu `test_tg3de_strukturdokumente.py` (19), `test_tg3f_ordner_inhalte.py` (13),
  `test_migration_dokumente_je_sitzung.py` (2, Postgres); erweitert `test_dokument_ablage.py`
  (Postgres: fünf je Sitzung, Anmeldung übernimmt alle, Eintrag in `strukturdokument` geht mit dem
  Dokument, Aufbewahrungslauf), `test_dokument_stand.py` (Leser, Lader, Zusammenführen),
  `test_ablage_rolle_w4.py` (bis fünf Strukturdokumente in der Freigabe). Angepasst an die neue
  Regel: `test_arbeitsstand`, `test_tg3a_struktur_auswahl`, `test_tg2_bereit_und_verwirft`,
  `test_ablauf_querschnitt_asd`, `test_ablauf_zug` (je die erwartete Teil-Liste).
  `pytest -k "dokument or strukturentwurf or upload or ablauf or arbeitsstand or vorgang or ablage or
  restbefunde or migration or ordner or seed or bereit or tg3"`: 1934 bestanden. ruff sauber.
- **Frontend:** `ui-module` 422, `studio` 2156, `ui` 1513 Specs grün (neu: Rollen bis fünf, Lesen
  nacheinander, Fehler je Dokument, „Ohne dieses weiter“, englisch; Zahl der Dateien am Punkt,
  Inhalte beim Bearbeiten, Manifest). ESLint sauber.
- **Playwright** (`npm run build:widget`): `upload-erfassen`, `upload-uebertragen`,
  `upload-und-fortschritt` — 13 grün, darunter neu „zwei Strukturdokumente nacheinander“.
- **Drift:** Manifeste neu erzeugt (`module:register`), OpenAPI und Bereichs-Schemas unverändert.
- **Nicht geprüft:** die ganze Backend-Suite; der WLO-Weg des Lesers gegen das echte MCP und
  Repositorium (nur mit Attrappen der Drahtform von `get_wlo_content_text`); ein Chat-Smoke mit
  echtem Modell (Ebene 1 aus mehreren Dokumenten).

## Review-Behebung (16.11., Review TG-3d–f samt R3)

1 MAJOR, 8 MINOR, NITs und 1 Fehler der vollen Suite. Einzelheiten und Feinentscheide stehen im
Plan unter „Review TG-3d–f (samt R3, 16.11.) — behoben“.

- **Suite:** Der Leser loggt nur feste Gründe, keinen Servertext.
- **M1 (MAJOR):** Wer anonym liest und sich dann anmeldet, behält die Dokumente. Der Leser nimmt
  `ablage.alle_fuer_aufrufer` (mit Übernahme) und filtert nach den Kennungen des Teils.
- **MINOR 1, Namen als Hinweis:**
  - Krisen- und Drohungsmuster in Ordner- und Dateinamen (und in unbearbeiteten Titeln) sperren
    nicht; der Upload bleibt.
  - Bei einem Krisenmuster hängt die Antwort die Hilfsnummern an: „Falls dich das Thema gerade
    selbst betrifft: … 0800 111 0 111, 0800 111 0 222 oder 116 123.“
  - Im Sicherheitsprotokoll steht `crisis_signal_in_names` bzw. `threat_signal_in_names`, ohne
    Namen. Das gilt in jeder Stufe, auch „regex“.
  - Krisensätze in der Nachricht sperren wie bisher.
- **MINOR 2:** Die Sitzungsdokumente werden vor dem MCP festgeschrieben. Die WLO-Volltexte laufen
  parallel (höchstens 3) mit einer Gesamtfrist von 30 s.
- **MINOR 3:** Fehlt ein Volltext, sagt das die Quittung an die KI („Volltext noch nicht erzeugt,
  später erneut“). Gibt es nur WLO-Dokumente und keins hat Text, meldet der Dienst den Fehlercode
  `volltext_fehlt`.
- **MINOR 4:** Bei der Grenze von zehn kommt der aktuelle Stapel vor `frueher`.
- **MINOR 5:** Vor dem Verdrängen gehen die abgelaufenen Dokumente. Ein erneutes Hochladen
  desselben Dokuments (gleicher Name, gleiche Größe, derselbe Aufrufer) ersetzt das alte. Gezählt
  wird je Aufrufer.
- **MINOR 6:** `quality_logs.data.message` ohne Namen.
- **MINOR 7:** Kuratierende Werkzeuge bekommen `draft` ohne `inhalte`.
- **MINOR 8:** Die node_ids im Entwurf kommen nur aus der gebundenen Ablage, nie vom Client.
- **Geprüft:**
  - Neu: `test_review_tg3def.py` (17) und `test_review_tg3def_pg.py` (Postgres, 4: M1,
    Verdrängung, erneutes Hochladen, zwei gleichzeitige `speichern`).
  - Angepasst: `test_dokument_stand.py` (neuer Leseweg, Gründe, ohne Anmeldung kein Lesen),
    `test_ablauf_zug.py` (Attrappe nimmt den Merker).
  - `pytest -k "dokument or strukturentwurf or upload or ablauf or arbeitsstand or vorgang or ablage
    or restbefunde or migration or ordner or seed or bereit or tg3 or safety or preflight or log or
    quality or turn"`: 3029 bestanden, 0 Fehler. ruff sauber.
  - Studio 2156 Specs grün (Hinweis zur Sicherheitsstufe). ESLint sauber.
  - Keine Drift.
  - Widget und Module sind in dieser Runde nicht geändert, darum kein Playwright.

## Nachprüfung (16.11.)

1 MAJOR, 3 MINOR, 4 NIT. Einzelheiten stehen im Plan unter „Nachprüfung TG-3d–f — behoben“.

- **MAJOR 1:** Die Blase eines Felds („Ordner „…“ erfasst“, „Dokument „…“ lesen lassen“,
  „Entwurf „…“ übernommen“) zitiert den Namen. Gemessen ergab „Ordner „Suizid-Prävention“ erfasst“
  M01: Die Krisenantwort kam, und es wurde nichts gespeichert. Jetzt werden bekannte Namen in der
  Blase vor Regex-Gate und Rechtsprüfung neutral („…“). Es gibt einen Hinweis mit Hilfsnummern,
  keine Sperre, und die Teile werden gespeichert. Ein selbst getippter Krisensatz in
  Anführungszeichen sperrt weiter, auf Englisch ebenso.
- **MINOR 2:** Ein Entwurf aus Ordnern trägt `quelle_block` (die Auswahl, aus der er stammt).
  node_ids kommen nur aus der Ablage derselben Auswahl, sonst aus dem zuletzt gespeicherten Entwurf.
  Ein neuer Ordner im selben Vorgang ändert einen alten Entwurf nicht.
- **MINOR 3:** Als erneutes Hochladen gilt nur gleicher Text im selben Feld. Zwei verschiedene
  Dokumente gleichen Namens und gleicher Größe bleiben beide.
- **MINOR 4:** `volltext_fehlt` sagt je nach Grund „später“, „bitte anmelden“ oder „kein Zugriff“.
- **NIT:**
  - `strukturdokument.text()` ist gestrichen.
  - Abgelaufene Sitzungsdokumente nennt die KI-Zeile („bitte neu lesen lassen“).
  - Namen mit Muster ohne Moderation stehen im Sicherheitsprotokoll, ohne Namen.
  - Ein Kommentar ist berichtigt.
- **Geprüft:**
  - Neu: `test_nachpruefung_tg3def.py` (15) und ein Postgres-Fall in `test_review_tg3def_pg.py`
    (Dubletten).
  - Angepasst: `test_review_tg3def.py` (Entwurf mit `quelle_block`), `test_dokument_stand.py`
    (ohne `text()`).
  - `pytest -k "dokument or strukturentwurf or upload or arbeitsstand or vorgang or ablage or tg3
    or safety or preflight or assess or log or quality"`: 1526 bestanden, 0 Fehler. ruff sauber.
  - `ui-module` 426 Specs grün (`quelle_block` geht zurück, Manifest); ESLint sauber.
  - Playwright `strukturentwurf` und `upload-erfassen`: 11 grün.
  - OpenAPI ohne Drift. Die Bereichs-Schemas zeigen Drift (`vorbelegen` im Ablauf-Modell) — sie
    stammt aus dem parallelen Bau von TG-4 bis TG-6, nicht aus diesem Paket; nicht neu erzeugt.

## Deploy

- **Migration 0023** einspielen (`alembic upgrade head`). Ohne sie scheitert jedes zweite Dokument
  einer Sitzung an der alten Eindeutigkeit (409 bzw. 500). Der Rückweg (`downgrade 0022`) löscht je
  Sitzung alle Dokumente außer dem jüngsten.
- Image neu bauen (Widget-Bündel, nachgeladene Module `ui-upload` und `ui-strukturentwurf`, Studio).
  Danach im Browser neu laden: die alten Bündel sind cachebar.
- Keine neue Variable. Kein Werksabgleich nötig (kein Seed geändert).
