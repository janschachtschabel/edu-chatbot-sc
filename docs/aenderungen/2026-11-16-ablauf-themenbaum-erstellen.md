# Ablauf „Themenbaum erstellen“ (2026-11-16)

Plan `docs/plans/2026-11-16-themenbaum-generisch.md`, Pakete TG-4 bis TG-6 (G-E2, G-E6 bis G-E10).
Anlass war die Sackgasse „Themenbaum · aus Ordnern“ mit losen Dateien und der Wunsch nach einem
Ablauf mit Leitfragen für alle Grundlagen.

## Was neu ist

### Ein Ablauf für alle Grundlagen (TG-6)

`06-ablaeufe/themenbaum` („Themenbaum erstellen“), ab Werk an, ohne Voraussetzung:

Stand nach der Review-Behebung (unten): erst die Grundlage und ihre Daten, dann die Fragen,
die dort wirken, dann der Entwurf.

1. **Bereitgestelltes zuerst.** Liegt im Vorgang schon ein lesbares Dokument, Ordner mit
   Unterordnern oder Dateien mit Namen, fragt er „Ja, verwenden / Anderes wählen / Ohne Führung“.
   Sonst „Ja, neue Struktur mit Unterstützung / Ohne Führung“.
2. **Grundlage:** getippt das Thema; sonst „Ein Dokument mit Gliederung, etwa ein Lehrplan“,
   „Meine Ordner“ oder „Meine Dateien“.
3. **Daten je Grundlage:**
   - Dokument → das gelesene Strukturdokument (auch mehrere), sonst das Upload-Feld mit
     „Einzeldatei als Struktur“.
   - Ordner → Upload-Feld → `strukturentwurf_aus_ordnern` → Prüfpunkt („Ordner sind dein
     Ausgangspunkt …“) → „So lassen“ oder „Mit deinen Angaben verfeinern“. Übertragen im Feld nach
     WLO: erst Rückfrage, Kestra-Metadaten und `metadaten_lesen`, dann der Entwurf mit node_ids.
     Ohne Unterordner → Weg Dateien.
   - Dateien → „Gründlich über WLO (einige Minuten)“ oder „Nur die Dateinamen“, wenn der ganze
     WLO-Weg geht (`bereit.wlo_erschliessen`); sonst ein Satz und die Dateinamen
     (`inhalte_aus_dateien`). Gründlich: übertragen → Rückfrage → Kestra-Auftrag → `metadaten_lesen`.
4. **Fragen**, jede mit Freitext: wofür, für wen bzw. Stufe, Soll oder Ist (nur Dateien), Umfang,
   Hinweise — auf dem Ordner-Weg nur nach „verfeinern“.
5. **Entwurf** im KI-Schritt der Grundlage (`aus_dokument`, `aus_inhalten`, ohne Flag beim Thema,
   `vorlage` beim Verfeinern der Ordner).
6. **Ende** mit gespeichertem Entwurf und nächsten Schritten als Text. Jeder Fehlerweg bietet
   „Nochmal“, „Andere Grundlage“ bzw. „Frei weiter“.

Die KI-Schritte tragen die Regeln der Wissenssammlung als `vorgaben` (5 bis 15 oben, 3 bis 20
darunter, keine Einzelkinder, keine Facetten als Punkte, Ordner sind Herkunft, Soll/Ist).
Wendungen: alle der vier alten Abläufe (drei Text-Auslöser). Auslöser außerdem Knopf und KI
(direkt). 40 Schritte, 20 Selbsttests (alle Zweige, Kestra-Ergebnis attrappiert).

### Die vier alten Abläufe

`themenbaum_aus_thema`, `themenbaum_aus_dokument`, `themenbaum_aus_inhalten` und
`sammlungsstruktur` sind ab Werk **aus**, im Kopf „abgelöst durch themenbaum“, nicht gelöscht.
Ihre Enden nach einem Fehler bieten jetzt „Nochmal“ und „Frei weiter“ (neue Prüfung, siehe unten);
ebenso „Sammlung prüfen“ bei Ordnern ohne Unterordner.

### Werkzeug `inhalte_aus_dateien` (TG-4, G-E9)

Ein Ablauf-Dienst ohne Sprachmodell und ohne Netz: aus dem Teil `struktur` (die Auswahl mit Dateien)
ein Teil `metadaten` im Format `wlo.metadaten@1`.

- Nur Dateien mit Rolle `inhalt`. Je Eintrag `i`, kein `node_id`; die `block_id` der Auswahl reist
  mit.
- Titel aus dem Dateinamen: ohne Endung, `_` und `-` als Leerzeichen, an der Wortgrenze auf 80
  Zeichen gekürzt.
- Beschreibung: „Ordner: Physik 7 / Mechanik“.
- Der Teil bleibt unter 60 000 Bytes (erst Pfade kürzen, dann weglassen, dann Titel kürzen, zuletzt
  Einträge vom Ende; deren Zahl steht in `ausgelassen`).
- Eingetragen in `werkzeuge.DIENSTE`, `typen.DIENST_AUSGABE`/`DIENST_EINGABE`, im Studio-Katalog
  (automatisch) und im Hinweis des Felds „Werkzeug“. Die Prüfung meldet wie bei `metadaten_lesen`,
  wenn der Teil nicht `metadaten` heißt.
- Die Namen gehen erst im Strukturentwurf an ein Modell; dort prüft die Moderation Übersicht und
  Anfang wie bei Metadaten aus WLO.

### Feste Zuordnung Teile → Auftrag (TG-5, G-E8)

Neues Feld `agent.vorbelegen` (Vorgabe `None`, ändert keine Fassung). Ist es an, belegen die
Antworten **dieses Laufs** die Argumente von `ui_strukturentwurf` vor
(`services/ablauf/vorbelegung`):

| Teil | Argument |
|---|---|
| `umfang` | `tiefe`/`anzahl_oben`: kompakt 1/6, mittel 2/10, ausführlich 3/12 (Label oder Schlüsselwort im Text; sonst eine Zeile „Umfang: …“) |
| `stufe` | `bildungsstufe` (Grundschule → Primarstufe usw.; „Allgemein“ setzt nichts; getippter Text bleibt) |
| `thema` | `thema` |
| `zweck`, `publikum`, `soll_ist`, `hinweise` | je eine Zeile in `hinweise` |

**Vorrang:** Ein Argument, das die KI selbst setzt, geht vor — so kann die Person im Gespräch
umentscheiden. Die KI sieht in `[VORBELEGT — …]`, welche Argumente der Ablauf setzt (nur Namen und
Zahlen), und gibt sie nur bei einer Änderung an. Die Hinweise werden zusammengeführt (Ablauf zuerst,
dann die der KI, höchstens 600 Zeichen). Die Werte sind wie in `[ABLAUFDATEN]` entschärft.

## Weitere Änderungen

- **Dienst `bereitgestellt`** meldet zusätzlich `art` (`dokument`, `ordner`, `dateien` oder `null`),
  `name` (je Sprache, etwa „die Ordner „Physik““) und `wlo_ablage`.
  - **Entscheid:** „Gründlich über WLO“ erkennt der Ablauf an `bereit.wlo_ablage` = die
    Systemfelder des Upload-Dienstes (`dienst_upload.schalter()["ablage_in_wlo"]`: Studio-Schalter,
    MCP führt die Stapel-Ablage, persönliche Anmeldung). In der Simulation gilt die Anmeldung des
    Testfalls.
- **Prüfung:**
  - **Neuer Hinweis „Ende ohne Ergebnis“** (`services/ablauf/stumme_enden`): ein `ende` ohne
    `ausstieg`, das ein Lauf ohne Ergebnis und ohne Wahl der Person erreichen kann. Ergebnis heißt:
    KI-Schritt, Auftrag, Freigabe, Ankunft auf einer Seite (auch `wenn_seite`) oder ein Modul,
    dessen Antwort mehr als Bereitstellung schreibt; eine Regel `wenn_teil` auf so einen Teil
    (etwa `draft`) zählt mit. Ein Hinweis, kein Befund — eigene ältere Abläufe speichern weiter.
    Ein Test hält alle Seeds frei davon.
  - **Aufträge und `metadaten_lesen` ohne Voraussetzung „Anmeldung“** sind erlaubt, wenn der Schritt
    einen Ersatzweg (`bei_fehler`) hat. Ohne Anmeldung startet kein Auftrag und `metadaten_lesen`
    liest nichts — der Schritt nimmt dann `bei_fehler`.
  - **Direktstart:** Ein Auftrag, vor dem auf jedem Weg direkt eine Rückfrage steht, zählt für
    `modus: direkt` nicht als „schreibt selbst“ (`werkzeuge.ablauf_schreibt_ungefragt`, wie TW-6
    beim Upload-Feld). Der frische Vorgang beim Start (N14) bleibt für jeden Ablauf mit Auftrag.
- **Leiste:** `fortschritt` zählt jede Kante einmal (mehrere Regeln mit demselben Ziel
  vervielfachten die Wege, das Besuchsbudget reichte nicht).
- **Umlenkung (TW-6):** `ui_strukturentwurf` ohne Grundlage lenkt auf Abläufe ohne Upload; gibt es
  keinen, auf Abläufe mit Upload, die ihn nutzen („Themenbaum erstellen“).
- **Rahmen nach dem Lesen:** „einen Themenbaum daraus“ erscheint auch, wenn der Ablauf ein Dokument
  über ein Upload-Feld mit „Einzeldatei als Struktur“ liest (statt nur mit Voraussetzung
  `dokument_lesen`).
- **Master-Skill** (`docs/skills/vorgehen-knapp.md`): nennt „Themenbaum erstellen“ statt der vier
  alten Abläufe.
- **Studio:** Feldtexte für `agent.vorbelegen` (de/en); Hinweis zum Feld „Werkzeug“ nennt
  `bereitgestellt` und `inhalte_aus_dateien`; Schema-Fixture und OpenAPI neu erzeugt.

## Umstieg und Deploy

1. Backend- und Studio-Image neu bauen (keine Migration).
2. `boerdi import-config --werksabgleich`:
   - legt `06-ablaeufe/themenbaum` an (an) und schaltet die vier alten Abläufe aus — **laufende
     Läufe der alten Abläufe brechen beim nächsten Zug ab** (die Fassung ändert sich). Die Person
     startet „Themenbaum erstellen“ neu; bereitgestellte Ordner, Dateien und Dokumente übernimmt er.
   - Anlagen mit **eigener Fassung** eines alten Ablaufs behalten sie (der Abgleich arbeitet je
     Bereich). Ist ein alter Ablauf dort weiter an, kollidieren seine Wendungen mit denen von
     „Themenbaum erstellen“ (Hinweis im Studio; es gilt die längere Wendung). Empfehlung: im Studio
     ausschalten.
3. Master-Skill (`vorgehen-knapp.md`) gleichzeitig übertragen — sonst nennt er Abläufe, die aus
   sind.
4. Für den gründlichen Weg: Ablage in WLO an (ab Werk), Flow `edusharing.chatbot/node-metadata-write`
   freigegeben (ab Werk), Person angemeldet. Fehlt etwas, fragt der Ablauf nicht und nimmt die
   Dateinamen.

## Tests

- `tests/test_tg4_inhalte_aus_dateien.py`, `tests/test_tg5_vorbelegung.py`,
  `tests/test_tg6_themenbaum.py` (Seed, Zweige, kein stummes Ende über alle Seeds, Direktstart,
  Leiste nur vorwärts, Umlenkung, Rahmen).
- Angepasst: `test_ablauf_beispiele` (ab Werk an: nur `themenbaum`), `test_tw4_seeds` (Wendungen →
  `themenbaum`), `test_tg2_bereit_und_verwirft` (neue Felder), `test_tb_f2_metadaten_lesen`
  (Ersatzweg genügt), `test_ui_upload` (WLO-Weg im neuen Ablauf).

## Offen

- Durchtest gegen die Wegwerf-DB mit echtem Modell, MCP und Kestra (TG-7).
- Die Leiste rechnet „längster Weg“: Auf einem Rückweg („Nochmal“) steht ein Schritt wieder an
  seiner Stelle, und `m` passt sich nach der Verzweigung an (etwa „9 von 19“ → „10 von 10“ beim
  Thema).

## Review-Behebung (Review TG-4–6, 16.11.)

4 MAJOR, 8 MINOR, 6 NIT und 1 Fehler der vollen Suite, alle behoben. Teile des Abschnitts oben sind
damit überholt: Der Ablauf fragt jetzt **erst die Grundlage und ihre Daten, dann die Fragen**.

- **0 (Suite)** und **10 (Leiste):** Ein Lauf zählt seine Halte (`lauf.halte`, im Sitzungsverweis
  mitgeführt). „Schritt n von m“: n = Halte, m = n − 1 + die meisten Halte ab hier. Werkzeuge,
  Dienste, Verzweigungen und Nachrichten ohne Wahl zählen nicht, ebenso keine Frage, die nur eine
  andere wiederholt. Läufe von vorher (ohne `halte`) rechnen weiter über den längsten Weg. Der
  Sprung lag nicht am Besuchsbudget, sondern am Maß „längster Weg“ in einem verzweigten Graphen.
- **MAJOR 1:** Für den Direktstart zählt nur eine echte Rückfrage vor dem Auftrag — eine Wahl mit
  mindestens einer Option, die nicht zum Auftrag führt, ohne Freitext dorthin — oder eine Freigabe
  (`werkzeuge._ehrlich_gefragt`).
- **MAJOR 2:** Ein schreibender Ablauf beginnt nur dann in einem frischen Vorgang, wenn dort eine
  Ablage, ein Metadaten-Lauf oder ein offener Lauf liegt (`zug._frisch_noetig`). Freie Arbeit samt
  Entwurf bleibt; N14 (keine alte Ablage an den Flow) bleibt gewahrt.
- **MAJOR 3:** An Fragen mit Freitext treffen Synonyme nur als ganze Wörter (`treiber.wahl_aus_text`;
  die Führung ohne Freitext bleibt beim Teilwort). Riskante Synonyme („Inhalte“, „Systematik“) sind
  gestrichen. `ohne_daten` bietet „Andere Grundlage“.
- **MAJOR 4:** Auf dem Ordner-Weg keine Fragen vor dem Entwurf. Nach dem Prüfpunkt „So lassen“ oder
  „Mit deinen Angaben verfeinern“ (dann Zweck, Stufe, Umfang, Hinweise und ein KI-Schritt mit
  `vorlage: true`). Soll oder Ist nur bei Dateien. „Für wen“ und „Stufe“ sind eine Frage.
- **MINOR 5:** `tiefe`/`anzahl_oben` gelten nur zusammen; `""` löscht `bildungsstufe` bzw.
  `hinweise` (die Zeile `[VORBELEGT]` sagt es).
- **MINOR 6:** Die Hinweise der Person bekommen den übrigen Platz bis 600 Zeichen.
- **MINOR 7:** Der Metadaten-Auftrag nimmt nur Inhalte (`rolle: inhalt`).
- **MINOR 8:** „Gründlich über WLO“ nur bei `bereit.wlo_erschliessen`: Ablage im Feld UND ein
  startbarer Auftrag (`auftrag_zug.starter`) UND der Flow freigegeben (`client.erlaubt`). Sonst nimmt
  der Ablauf die Dateinamen.
- **MINOR 9:** „Anderes wählen“ verwirft `bereit` nicht mehr.
- **MINOR 11:** Vorsätze der Hinweiszeilen und `[VORBELEGT]` je Sprache; die englischen `vorgaben`
  nennen die deutschen Werte der Antworten.
- **MINOR 12:** Tests für Muster-Weg, „Anderes wählen → Dateien“, unlesbares Dokument (Zug),
  Synonym-Fehltreffer und nicht freigegebenen Flow.
- **NIT 13:** Erschließen auf dem Ordner-Weg über das Übertragen im Upload-Feld (vor dem Entwurf;
  dann erst Metadaten, dann der Entwurf mit node_ids). Nach dem Prüfpunkt keine eigene Frage — dafür
  war kein Platz, und es bräuchte ein zweites Auswählen im Feld.
- **NIT 14–18:** Texte zum schnellen Weg ehrlich („nur die Dateinamen“, ohne Übertragen für
  Anonyme), getippte Grundlage ist das Thema (keine zweite Frage), Verneinung im Umfang, „nein“ bei
  Hinweisen, einfachere Begriffe, Titel aus Dateinamen je Sprache.

**Umstieg zusätzlich:** Laufende Läufe von „Themenbaum erstellen“ aus einem Staging vor dieser
Behebung brechen beim Werksabgleich ab (die Fassung ändert sich).

## Zweites Review TG-4–6 (16.11.), behoben

2 MAJOR, 5 MINOR, 3 NIT (A–I).

- **A — Freitext geht vor:** An Fragen mit Freitext trifft ein Synonym oder Label nur, wenn der
  ganze getippte Text ihm gleicht (Satzzeichen am Rand zählen nicht). „Keine Atomphysik“, „Nein,
  aber bitte Lernfeld 3 ausführlich“, „Passt nicht, bitte verfeinern“, „nicht gründlich, schnell“
  sind freie Antworten. Neues Feld `synonyme_im_satz` (Vorgabe aus, nur `nachricht`): die Frage
  ordnet Sätze einer Option zu — ganze Wörter, nicht hinter „kein/nicht/ohne“, mehrere Optionen
  getroffen → Freitext. Nur die Grundlage trägt es. Studio: Feld mit Hinweis im Schritt-Editor.
- **B — Leiste:** Für `m` fallen nur **Kanten** von Wahl- oder Fehlerschritten auf frühere Schritte
  weg, nicht ganze Schritte; die des Schritts, an dem der Lauf hält, bleiben. Auf dem Hauptweg steigt
  `m` nie, und `n` < `m` bis zum letzten Halt (Test über alle drei Seeds).
- **C — Direktstart:** Eine Rückfrage vor dem Auftrag zählt nur, wenn eine andere Option ein Ende
  erreicht, ohne über den Auftrag zu gehen.
- **D — Grundlage:** Wortformen ergänzt (Dokumente, Lehrpläne, Curricula, PDFs, Kerncurriculums,
  Bildungsplans, Materialien, Unterlagen, my documents/files/folders). „Dateien und Ordner
  (Informatik)“ und „Ich habe keinen Lehrplan, Thema Optik“ sind Themen. „Andere Grundlage“ auch nach
  einem fehlgeschlagenen Entwurf (`ohne_entwurf`).
- **E — Vorbelegung:** `bildungsstufe` nur für bekannte Labels, sonst die Zeile „Für wen/Stufe: …“.
  Eine getippte Grundlage (kein Label der Frage) wird `thema`. Die toten Zuordnungen `publikum` und
  `thema` sind weg.
- **F — kein Verlust ohne Klick:** Schlösse der Direktstart den Vorgang (Ablage, Metadaten-Lauf oder
  offener Lauf darin), bleibt es ein Vorschlag mit Knopf.
- **G — „Nochmal auswählen“** nach `aus_ordnern` ohne Ergebnis: mit erfassten Ordnern wieder
  `aus_ordnern`, mit nur bereitgestellten Ordnern das Upload-Feld.
- **H — Ablage der jetzigen Auswahl:** Zu den Metadaten geht es nur, wenn `ablage.block_id` gleich
  `struktur.block_id` ist (neu: `wenn_wert.wert` darf eine Stelle `{teil.…}` sein). Eine Ablage aus
  einem früheren Feld führt nicht mehr in den Metadaten-Auftrag. Die Simulation gibt simulierten
  Upload-Feldern eine feste `block_id` (`simulationuiupload`).
- **I — Platz für die KI:** In `hinweise` bleiben bis zu 150 Zeichen für die Wünsche aus dem
  Gespräch; gekürzt werden zuerst die Zeilen des Ablaufs.

Tests: `tests/test_tg6_review2.py` (neu), `tests/test_tg5_vorbelegung.py` angepasst.

## Nachprüfung TG-4–6 (16.11.), behoben

1 MAJOR, 5 MINOR, 2 NIT. Teile von „Zweites Review“ (A, D) sind damit überholt.

- **MAJOR 1 — Knopf-Fragen ohne Freitext:** Einstieg, „So lassen“/„verfeinern“, „Gründlich über
  WLO“/„Nur die Dateinamen“, Soll oder Ist, die Rückfrage vor Kestra und die drei Auswege nehmen
  keinen Freitext und tragen keine Synonyme. Getippter Text, der kein Label ist („Passt so“, „Ja“,
  „Ja, gründlich“), bekommt einmal „Bitte wähle einen der Knöpfe.“ mit denselben Chips. Freitext
  bleibt bei Grundlage, wofür, Stufe, Umfang und Hinweise.
- **MINOR 2 — Verneinung im Satzteil:** nur bis zum nächsten Komma, Semikolon oder Punkt; auch das
  Wort direkt dahinter zählt („Lehrplan nicht, Ordner“ → Ordner). „nicht nur Lehrplan“ ist das
  Dokument („nicht nur“ bejaht).
- **MINOR 3 — mehrdeutige Grundlage:** „Dateien aus meinem Ordner“, „meine PDF-Dateien“, „Ordner mit
  Unterlagen“ sind weder Wahl noch Thema. Die Grundlage fragt nach („Meinst du deine Ordner, deine
  Dateien oder ein Dokument? …“) und wartet. `kein_treffer` neben Freitext ist erlaubt, wenn die
  Frage `synonyme_im_satz` trägt.
- **MINOR 4 — Synonyme an der Zustimmung:** Eine Antwort mit Synonymen, die zu einem schreibenden
  Flow führt, zählt nicht als Rückfrage; die Prüfung meldet sie (de/en).
- **MINOR 5 — Wert als Stelle in der Prüfung:** `{teil.…}` im Wert wird wie die Quelle geprüft
  (Form, geschrieben, vorher); `{teil.` mit falscher Form ist ein Befund; keine Zahl nötig. Im
  Studio: Platzhalter „Wert oder {teil.name.pfad}“ und dieselbe Formprüfung.
- **MINOR 6 / NIT 7 — Leisten-Test:** prüft jetzt auch den Hauptweg ab `einstieg`; heißt
  „m steigt nie“.
- **NIT 8:** „Nein danke“, „nein, danke“ und „no thanks“ heißen „keine Hinweise“.

Selbsttests mit den gemessenen Sätzen in „Ordner, anonym, so lassen“, „Ordner mit Angaben
verfeinern“ und den beiden gründlichen Datei-Fällen. Tests: `tests/test_tg6_nachpruefung.py` (neu),
angepasst `test_tg6_review2`, `test_tg6_themenbaum`; Studio `weiter-regeln.spec.ts`.
