# Paket Q1: Upload und automatisches Abholen — Befunde des Querschnitts-Reviews (2026-11-06)

Grundlage: [`../audits/2026-11-06-querschnitts-review.md`](../audits/2026-11-06-querschnitts-review.md),
Plan [`../plans/2026-11-06-querschnitts-befunde.md`](../plans/2026-11-06-querschnitts-befunde.md) (Q1).
Nutzer: „wie empfohlen vorgehen und alle Befunde beheben“.

## Was sich für die Person ändert

- **Ein getipptes Wort bricht keine Übertragung mehr ab (M2).** Datei und Abschluss gehören zum Stapel des
  Blocks (Prüf-Kürzel und `block_id` im Teil `ablage`), nicht mehr zur offenen Frage. Wird der Block mitten
  im Senden „nur lesen“, läuft der Stapel sichtbar weiter (Fortschritt, Anhalten, Ergebnis) — nur ohne
  „Im Chat weitermachen“; abgeschlossen wird er dann von selbst.
- **„Unklar“ heilt beim zweiten Senden (M3).** Hatte das MCP nicht geantwortet, wird die Datei beim nächsten
  Versuch erneut eingelöst; das MCP nennt dann den wahren Stand. Ein vom MCP gemeldetes „unklar“ bleibt
  endgültig.
- **Das automatische Abholen von `ui_fortschritt` stört kein anderes Modul (M1).** Es schickt
  `automatisch: true`; Backend und Widget schließen dabei keine offene Frage. Bringt das Ergebnis selbst eine
  neue Frage, gilt die alte als veraltet (das Backend kennt eine je Sitzung) — ein laufender Stapel läuft
  trotzdem zu Ende.
- **Zwei Fenster überschreiben sich nicht.** Ein neues Vorbereiten ersetzt keinen offenen Stapel mit
  abgelegten Dateien, solange dessen Freigabe gilt (409 `stapel_offen`, eigener Satz); danach bleiben dessen
  abgelegte Einträge als `frueher` im Teil. Kommt das Ergebnis einer Datei, nachdem ein anderer Stapel den
  Teil übernommen hat, landet es dort als `frueher` statt im fremden Eintrag.
- Die Größe je Datei wird schon beim Vorbereiten geprüft; der Datenschutz-Satz nennt das Übertragen, wenn es
  angeboten ist; eine geschlossene Frage antwortet nicht mehr nachträglich.
- Barrierefreiheit: Ansagen nur an Meilensteinen (erste, jede zehnte, letzte Datei), Fehlerzeilen ohne
  `role="alert"` (angesagt einmal über die bleibende Status-Zeile), der Fokus fällt beim Wechsel auf „nur
  lesen“ nie auf `body`, ein ruhiger Balken bei reduzierter Bewegung (beide Module), die Datei-Eingaben
  überstehen jeden Zug (ein offener Dateidialog verliert nichts mehr).

## Entscheide

- **Abholen und Schreib-Abnahme (Review Q1, Befund 1):** abweichend vom Plan verfällt eine offene Abnahme
  beim automatischen Abholen — die Antwort ist sichtbar, und die Regel „eine Abnahme gilt nur für den direkt
  folgenden Zug“ bleibt so ohne Ausnahme. Nur das Schließen der offenen Frage entfällt.
- **Eine offene Frage je Sitzung (Review Q1, Befund 5):** bleibt so; das Widget zieht nach.
- **Wortschatz `layout`:** der Teil und die Antwort von `vorbereiten` sprechen `ordner`/`flach`; das Widget
  versteht weiter `folder`.

## Was sich im Code ändert

| Bereich | Änderung |
|---|---|
| `api/ui_ablage.py` | `_sitzung(frage=)` + `_anmeldung`; `vorbereiten` drosselt vor der Anmeldung, prüft `max_mb`, `stapel_offen`, speichert mit Rückruf; `datei`/`abschluss` an Stapel und Block gebunden; `ohne_antwort`; `_stand_festhalten` an Stapel und Eintrag der Anfrage gebunden |
| `services/ablage/vorgang_teil.py` | `layout`, `block_id`, `erstellt`, `haelt_noch`, `frueher`/`mit_frueher`, `ohne_antwort` |
| `services/arbeitsstand.py`, `services/vorgaenge.py` | `teile_speichern(neu=)` rechnet in jedem Versuch unter einer Zeilensperre (`vorgaenge.sperren`, `FOR UPDATE`) |
| `graph/nodes/setup.py`, `domain/hintergrund_zug.py`, `services/ui_antwort.py` | `ist_automatisches_abholen`: offene Frage bleibt, Abnahme verfällt |
| `services/ablage/mcp_ablage.py`, `services/dokumente/umwandlung.py` | totes `timeout` weg; Schreiben/Löschen im Thread, Verzeichnis vorher (räumt auch bei Abbruch auf) |
| Widget (`ui`) | `sendMessage(…, {fragenOffen})`, `runCardAction(fragenOffen)`, `auftragAbholen` mit `automatisch: true`, neue Frage im Ergebnis schließt die alte; `modulAntworten` nur für offene Blöcke; `nachladen.ts` erlaubt ein Pfad-Präfix der API |
| Modul `ui_upload` | „nur lesen“ mit Stapel, Abschluss ohne Antwortknopf, Eingaben einmal, Ansagen, Datenschutz-Satz, `fehlerSatz`/`dokumentFehlerSatz` (typgeprüfte DE/EN-Gleichheit, `Object.hasOwn`), Rückfallname je Sprache, ruhiger Balken |
| Modul `ui_fortschritt` | ruhiger Balken bei reduzierter Bewegung |
| Doku | `bewusste-vertragszusaetze.md` (Nachtrag Ablage), Host-Brücke ist keine Sicherheitsgrenze |

Bündel: Haupt-Bündel unverändert über der Warnschwelle (Grenze 200 kB); `ui-upload` 16,9 kB gzip,
`ui-fortschritt` 3,8 kB (zusammen 20,7 kB, Grenze 60).

## Tests

Backend: `test_ui_ablage_api.py` (Abschnitte Q1 und Review Q1: Zug mitten im Stapel, fremder Block, „ohne
Antwort“ heilt, MCP-„unklar“ bleibt, `stapel_offen`, `frueher`, Größe, Drossel vor Anmeldung, `flach`,
Stapelwechsel mitten in einer Datei, Abschluss eines fremden Stapels), `test_arbeitsstand_neuberechnung.py`
(Sperre, Neuberechnung je Versuch), `test_vorgang_teil.py` (neu), `test_automatisches_abholen.py` (neu),
`test_setup_node.py` (Abholen: Frage bleibt, Abnahme verfällt und wird geschrieben).
Frontend: Element-Specs (nur lesen mit Stapel, Abschluss, Fokus, Eingaben, Datenschutz, keine
`role="alert"`, Layout-Wortschatz), `ansageFaellig`, `fehlerSatz`, Shell (geschlossener Block), Controller
(automatisch, neue Frage schließt die alte), `nachladen.spec` (Präfix); E2E `upload-und-fortschritt.spec.ts`
(neu: Abholen während einer Übertragung, ruhiger Balken), `fortschritt.spec.ts`.

Läufe: ui-module 300, ui 1177, Studio 1969, Widget 76, E2E 102 (Upload/Fortschritt fünffach 55/55);
eslint, ruff und die Wächter sauber. Backend siehe Paket Q2 (gemeinsamer Lauf).

Hinweis zur Reihenfolge: bei FE-2, FE-7 und dem Byte-Test der Aufträge lag der Test nicht vor der Änderung
rot vor (zugleich geschrieben); ihr Rot ist am alten Code nachvollzogen, nicht gelaufen.

## Review Q1 (unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 1 MAJOR, 5 MINOR, 5 NIT. Gehalten: Sicherheit von `datei`/`abschluss` ohne Frage
(Sitzung, Anmeldung, Besitz, Kürzel, Block), Regex ohne ReDoS, DE/EN-Gleichheit, Savepoint-Ablauf, Ansagen.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | MAJOR | Abnahme verfiel je nach Weg mal, mal nicht | Abholen verwirft sie immer (sichtbarer Zug); nur die Frage bleibt — Test durch `setup` |
| 2 | MINOR | Rückrufe nicht an den Stapel gebunden (zweiter Tab) | Stapel/Eintrag der Anfrage; fremder Teil → `frueher`; `vorbereiten` prüft unter der Sperre erneut |
| 3 | MINOR | Fenster zwischen Lesen und `_speichern` | Zeilensperre, Neuberechnung in jedem Versuch |
| 4 | MINOR | „nur lesen“ schloss den Stapel nie ab → 30 min `stapel_offen` | Abschluss ohne Antwortknopf; Satz nennt den Ausweg |
| 5 | MINOR | neue Frage im Abholergebnis ersetzt die alte im Backend, nicht im Widget | Widget zieht nach |
| 6 | MINOR | Testlücken (Rückrufe liefen nie, `haelt_noch`, `_frueher`, `setup`) | ergänzt |
| 7 | NIT | `frueher` eines abgeschlossenen Stapels ging verloren | wird immer geerbt |
| 8 | NIT | Abbruch während des Schreibens ließ das Temp-Verzeichnis liegen | Verzeichnis vor dem Thread |
| 9 | NIT | JSDoc an falscher Stelle | verschoben |
| 10 | NIT | `constructor` als Code traf den Prototyp | `Object.hasOwn` |
| 11 | NIT | Doku zu Hintergrund-Zügen, Änderungsnotiz | nachgezogen (`ui_antwort`, `hintergrund_zug`, diese Notiz) |
