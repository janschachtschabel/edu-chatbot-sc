# Querschnitts-Review Gruppen F/T: TB-F1, TB-F2, TB-T1, TB-T2 (2026-11-10)

Ein unabhängiges Review über die vier Pakete und ihr Zusammenspiel. Das Ergebnis: 0 CRITICAL,
2 MAJOR, 6 MINOR und eine Sammel-NIT. Alle Befunde sind behoben oder als bewusste Grenze vermerkt.

## Befunde und Behebung

- **MAJOR 1: Eine veraltete Ablage oder ein leerer Stapel erreichte den schreibenden Flow.**
  - **Ursache:** `wenn_teil: ablage` prüft nur, ob es den Teil gibt. Eine Ablage aus freier
    Arbeit oder aus einem früheren Lauf desselben Ablaufs blieb im Vorgang stehen. Mit „erfasst“
    liefen deshalb alte nodeIds in den Flow, bei einem Stapel ohne abgelegte Datei ging
    `node_ids: []` hinaus.
  - **(a) Frischer Vorgang:** Ein Ablauf, der ins Repositorium schreibt (`ablauf_schreibt`:
    Upload, Auftrag, schreibendes Werkzeug), beginnt beim Start per Knopf, Text oder KI immer in
    einem frischen Vorgang. Der alte wird geschlossen, ein wartender Auftrag darin endet bei der
    B-API nach dem Festschreiben. Der Modul-Auslöser bleibt, denn er hat sein Ziel schon
    vorbereitet (`starten_mit(frisch=False)`). Das steht in `ablauf/zug.py`.
  - **(b) Leere Auswahl:** Ergibt ein Argument aus einer Auswahl (`liste`) nichts, startet der
    Auftrag nicht. Es geht weiter mit `bei_fehler` (`treiber._leere_auswahl`).
  - **(c) Seed-Testfall:** „Übertragen, aber nichts abgelegt“ geht über `metadaten_fehlt` zu
    `ohne_metadaten` und dann zu „Beenden“.
  - **Tests:**
    - freie Arbeit mit Ablage → neuer Vorgang;
    - Neustart desselben schreibenden Ablaufs → neuer Vorgang;
    - leere Auswahl startet nichts.
  - **Angepasster Test:** Der Konflikttest zum Ersetzen eines Auftrags deckt jetzt zwei Fälle
    ab. Scheitert das Schließen des alten Vorgangs, startet nichts und nichts endet. Scheitert
    das Festhalten, endet der eben gestartete Job.
- **MAJOR 2: Still gekappt bei 50.** Ein Stapel hat bis zu 200 Dateien, `metadaten_lesen` las
  die ersten 50 und schwieg über den Rest. Jetzt steht der Rest in `fehlend`. Die Notizen nennen
  die richtige Grenze, und das fehlende Limit je Job steht in den offenen Befunden.
- **MINOR 3: Ein Lesefehler nach dem Flow war eine Sackgasse.** `ohne_metadaten` ist jetzt eine
  Nachricht mit „Nochmal lesen“ und „Beenden“.
- **MINOR 4: Die Rückfrage nannte 3 von 8 Feldern.** Jetzt nennt sie alle acht. Damit das geht,
  ist der Schritttext im Studio ein mehrzeiliges Feld (`Textarea`). Bereichsschema und OpenAPI
  sind neu exportiert.
- **MINOR 5: `auftrag_rueckfrage` war wirkungslos.** Jede frühere Wahl genügte. Jetzt muss auf
  jedem Weg direkt vor dem schreibenden Auftrag eine Wahl stehen, deren Antwort zu ihm führt,
  oder eine Freigabe (`pruefung._direkt_gefragt`). Zwei Tests: eine frühere Wahl ergibt einen
  Befund, eine Wahl direkt davor nicht.
- **MINOR 6: `frueher` wurde gelesen, aber nicht vom Flow verarbeitet.** `metadaten_lesen`
  nimmt jetzt nur den jetzigen Stapel, wie der Flow.
- **MINOR 7: „Wofür“ wirkte nicht.** Die Hinweise beider Seeds geben jetzt „Zweck und Wünsche
  als hinweise“ weiter.
- **MINOR 8: Doku.**
  - Probe-Hinweis in der T2-Notiz: „aus eigenen Inhalten“ endet in der Probe in `ohne_ablage`.
  - Der veraltete Satz zu K18 ist berichtigt.
  - Die offenen Punkte F/T und die Deploy-Schritte stehen in `offene-befunde`.
  - Der Plan hat eine Statusmarke, und das ersetzte Design ist gekennzeichnet.
  - Die Grenzen aus §5b stehen in `ablaeufe.md`.
- **NITs:**
  - Der Studio-Hinweis zum Werkzeug nennt `metadaten_lesen`.
  - Die Doku sagt genau, was die KI sieht: Wahl mit Wert in der Zeile, Freitext nur im Verlauf.
  - `language: de` steht als offener Punkt in den offenen Befunden.
  - Die Auswirkung von „Weiter“ vor der Antwort steht in `ablaeufe.md`.

## Prüfung

- **Neue und angepasste Tests:**
  - `test_querschnitt_vorgang` (2 neu);
  - `test_ablauf_auftrag` (1 angepasst, 1 neu);
  - `test_tb_f1_flow_identitaet` (3 neu);
  - `test_tb_f2_metadaten_lesen` (1 neu, 1 angepasst).
- **Simulation:** Die Seeds haben 8 Testfälle, alle grün. Der Wächter
  `test_config_textarea_hints` ist grün.
- **Studio:** 2144 grün.
- **Backend:** Der breite Satz lief mit 2768 grün und 1 übersprungen. Er umfasst ablauf,
  strukturentwurf, ui_modul, Schema, OpenAPI, Config, Seeds, Werk, Vorgang, Auftrag, Upload und
  Ablage. ruff ist sauber.

## Bewusst nicht geändert

- **Freitext-Werte in der Arbeitsstands-Zeile.** Das ist eine Datenschutz-Entscheidung aus
  Befund 11 von AS-3a. Der Verlauf trägt sie.
- **`X-Edu-User-Id` bei Abfrage, Abbruch und Datei.** Das wird erst gemessen, der Punkt steht in
  den offenen Befunden.
