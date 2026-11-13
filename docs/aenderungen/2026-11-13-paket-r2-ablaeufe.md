# Paket R2: Abläufe, Restpunkte (2026-11-13)

Plan [`2026-11-12-restpakete-ablaeufe-kestra-ui.md`](../plans/2026-11-12-restpakete-ablaeufe-kestra-ui.md),
Abschnitt R2, Entscheid R-E3.

## Was

- **R2-a Direktstart in der Studio-Liste:** Die Liste der Abläufe nennt „KI (startet direkt)“, wenn
  am Auslöser `agent` `modus: direkt` steht. Bisher sah man das erst im Dokument. Neues Feld
  `AblaufZeile.direkt`.
- **R2-b Voraussetzung `dokument_lesen`:** Ein Ablauf, der ein Dokument liest, braucht das Recht
  „Dokument im Chat“ (Studio, Datei-Upload) für diese Person.
  - Fehlt nur die Anmeldung (Lesen nur für Angemeldete), gilt derselbe Satz wie bei `anmeldung`,
    auch der Hinweis unter der Antwort.
  - Ist Lesen ganz aus, kommt ein eigener Satz und nie „melde dich an“.
  - Das Angebot unter der Begrüßung (Auslöser `seite`) steht nur, wenn jeder lesen darf.
  - Der Seed „aus einem Dokument“ trägt die Voraussetzung. Die Fassung bleibt gleich, denn
    Voraussetzungen gehören nicht zu den Schritten.
  - Neu ist `ausloeser.fehlt(ablauf)` (`anmeldung`, `dokument_lesen`, `unbekannt` oder `None`).
- **R2-c `ablauf_unbestimmt`:** Bestätigt der MCP die Anmeldung beim Laden des Verlaufs nicht
  binnen 1 s, fehlte der Stand, und es ging kein Seiten-Ping hinaus. Jetzt trägt die letzte Antwort
  `ui.ablauf_unbestimmt`, und das Widget pingt einmal. Ohne wartenden Lauf antwortet das Backend
  leer.
- **R2-d Vorgang nach der Anmeldung:** Ein anonym begonnener Vorgang geht nach der Anmeldung auf die
  Person über, wie das Dokument seit TB-E1.
  - Das gilt nur für den Vorgang des Verweises derselben Sitzung und nur für einen offenen.
  - Ein abgeschlossener oder fremder Vorgang bleibt, wie er ist.
- **R2-e Steuer-Knöpfe übersteht jeder Deckel:** „Stand prüfen“, „Auftrag abbrechen“, „Vorschau
  erneut zeigen“, „Ablauf abbrechen“ (Freigabe), „Neues Vorhaben“, „Plan fortsetzen“, „Weiter im
  Ablauf“ und die Wahl-Chips.
  - Das gilt auch ohne gesperrten Lauf, an allen vier Deckeln: Anzeige-Regeln, Muster/Gastgeber,
    Anmelde-Chips, Pillen.
  - Vorschläge bleiben gedeckelt: Text-Chips, „Ablauf starten“ der KI, „Arbeitsstand löschen“.
  - Bewusst geändert: Bisher galt der Deckel ohne Sperre auch für die Auftrags-Knöpfe (K2b).
- **R2-f Ein „ja“ ist eine Nachricht:** Das „ja“ zu einer Freigabe speicherte zwei
  Assistenten-Nachrichten (Einlösen und Fortgang des Laufs), live war es eine Blase. Jetzt hängt der
  Lauf Text und UI-Blöcke an die eben gespeicherte Antwort (`an_letzte_antwort_anhaengen`). Die
  Sitzungssperre hält andere Züge fern.
- **R2-g Moderation `closed`:** Steuer-Aktionen ohne Text der Person laufen auch, wenn die
  Moderation ausfällt (Entscheid R-E3). Sonst säße die Person fest.
  - Betroffen: „Stand prüfen“, die Abbrüche, „Vorschau erneut zeigen“, „Neues Vorhaben“,
    „Arbeitsstand löschen“.
  - „Weiter“, eine Wahl und ein Start bleiben gesperrt: Sie führen zur KI oder tragen Freitext.
- **R2-h:**
  - Verdrängen in `vorgaenge.anlegen` sperrt die Opfer erst in derselben Reihenfolge wie
    `dokument_teile_entfernen` (nach Kennung) und löscht dann. Sonst drohte eine Verklemmung.
  - `Teil` gibt es nur noch einmal (`arbeitsstand_teile`).

## Review R2 und Behebung

Unabhängiges Review: 2 MAJOR, 6 MINOR, 5 NIT, alle behoben.

- **MAJOR 1:** Die Marke `ablauf_unbestimmt` wurde nie verbraucht. Nach einem leeren Ping pingte das
  Widget bei jeder SPA-Navigation erneut und unterdrückte den Kontext-Gruß. Jetzt gilt sie für einen
  Ping je Nachricht (`UnbestimmtMarke`).
- **MAJOR 2:** Im Pfad „nur vorbereitet“ stand im Verlauf „Weiter geht's.“, live aber „Die Änderung
  ist vorbereitet …“. Jetzt ist dieser Satz der Text des Laufs.
- **MINOR 3:** Angehängt wird nur an eine Antwort desselben Zuges (Trace-ID). Sonst hinge der Text
  an der Vorschau des vorigen Zuges, wenn das Speichern des Einlösens scheiterte.
- **MINOR 4:** Die angehängte Nachricht bekommt die Zugakte neu, mit allem, was der Lauf danach tat.
- **MINOR 5:** Die Sätze nach dem Einlösen (Konflikt, abgebrochen, Fehler) und nach „Plan
  fortsetzen“ stehen jetzt auch im Verlauf. „Plan fortsetzen“ hängt ebenfalls an.
- **MINOR 6:** Die Übernahme R2-d läuft auch beim Laden des Verlaufs. Sonst fehlte die Leiste gleich
  nach der Anmeldung bis zum nächsten Zug.
- **MINOR 7:** Die Studio-Testfälle werten alle Voraussetzungen wie im Betrieb aus, also
  `ausloeser.fehlt(person=angemeldet)`.
- **MINOR 8:** Ein Test belegt, dass der Vorgang einer anderen Sitzung nie übergeht.
- **NIT 9–12:** Docstrings (Grenze je Person, Modul-Text), Konstanten-Test der Steuer-Aktionen,
  Studio-Hinweis zu `dokument_lesen`.
- **NIT 13:** offene Befunde nachgezogen (Paket R5).

Hinweis zum Datenschutz: Wer eine Sitzung per Link (`bsid`) übernimmt und sich anmeldet, bekommt
den offenen anonymen Vorgang dieser Sitzung. Das ist dieselbe Regel wie beim Dokument (TB-E1).

## Entscheide

- R-E3 (Moderation `closed`) und R-E4 (`/api/ui/*` ohne Sperre: so gewollt) aus dem Plan.

## Tests

- `test_r2b_voraussetzung_dokument.py`, `test_r2e_steuer_knoepfe.py`,
  `test_r2h_vorgaenge_sperre.py`, `test_r2d_vorgang_nach_anmeldung_pg.py` (Postgres).
- Dazu Tests in `test_ablauf_dokumente.py` (R2-a), `test_ablauf_leiste_endpunkte.py` (R2-c),
  `test_paket_s_zug.py` und `test_db_sessions_pg.py` (R2-f), `test_preflight_node.py` (R2-g).
- Nachgezogen: `test_tw4_seeds.py` (`fehlt` statt `erfuellt`), `test_ablauf_auftrag_abbruch.py`
  (Deckel ohne Sperre), `test_publikum.py` (Vertrag).
- Widget: `seiten-ping.spec.ts`. Studio: `ablaeufe-seite.spec.ts`.

## Verträge

`AblaufZeile.direkt`, `UiInfo.ablauf_unbestimmt`, Wahl `dokument_lesen` an `voraussetzungen` (Zeilen
in `docs/api/bewusste-vertragszusaetze.md`).

## Deploy

Keine Migration. Image neu bauen, `import-config --werksabgleich` (Seed „aus einem Dokument“).
