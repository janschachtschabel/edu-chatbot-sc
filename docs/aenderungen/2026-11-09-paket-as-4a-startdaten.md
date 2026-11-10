# Paket AS-4a: Startdaten und Auslöser „Gastseite“ (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), E2 A und §5f.

## Was sich ändert

- **Startschema:** Ein Ablauf beschreibt unter „Startdaten“ (`start`), was eine Gastseite beim
  Start mitgeben darf. Je Feld gibt es:
  - `name`;
  - `typ`: `text`, `nodeid`, `zahl` oder `ja_nein`;
  - `pflicht`;
  - `beschreibung` je Sprache; in AS-5 wird sie die Beschreibung des Werkzeug-Parameters;
  - `max_zeichen` (nur bei Text).

  Es gibt höchstens 10 Felder. Ohne Startschema bleibt alles wie bisher.
- **Neuer Auslöser `extern` („Gastseite (Widget)“):** Nur ein Ablauf mit diesem Auslöser nimmt
  Startdaten an (`ablauf_starten` mit `action_params.start`). Knopf, Wendung und Modul starten ohne
  Daten. Ein Ablauf mit Pflichtfeldern startet über sie nicht, und die Prüfung meldet das schon
  beim Speichern.
- **Prüfung der Daten** (`services/ablauf/startdaten.py`):
  - unbekannte Felder und falsche Typen werden abgewiesen, Pflichtfelder müssen da sein;
  - Text: Steuer- und Formatzeichen fallen weg, Leerraum wird zusammengezogen, zu lang wird
    abgewiesen;
  - Kennung: eine UUID, ganz;
  - Zahl: endlich, kein Wahrheitswert.

  Fehler kommen als Codes (`pflicht:sammlung`) ohne den Wert. Im Chat steht dann nur
  „Dieser Ablauf braucht passende Startdaten …“ (`action.ablauf.startdaten`). Das Log zählt nur
  die Befunde. Startdaten sind Eingaben, nie Rechte.
- **Teil `start`:** Die geprüften Daten werden vor dem ersten Schritt der Teil `start`
  (`wlo.start@1`).
  - `{start.feld}` im Text liest ihn, gleich `{teil.start.feld}`.
  - `{"$teil": "start", "pfad": "feld"}` geht ohne Sonderweg.
  - Mit Startschema entsteht der Teil immer, notfalls leer.
- **Prüfung des Ablaufs:** neue Befunde für
  - `{start.x}` mit unbekanntem Feld;
  - einen Schritt, der den reservierten Teil `start` schreibt;
  - Pflichtfelder ohne Auslöser `extern`.
- **Simulation:** Ein Testfall trägt Startdaten (`start`). Sie gehen durch dieselbe Prüfung, und
  ungültige sind eine Abweichung („Startdaten abgewiesen: …“).
- **Studio:** Die Abschnitte „Startdaten“ am Ablauf und am Testfall, dazu die Wahl „Gastseite
  (Widget)“ beim Auslöser. Texte auf Deutsch und Englisch.

## Wo

- **Backend:**
  - `domain/config_models/ablauf.py` (`StartFeld`, `AblaufArea.start`, `Ausloeser.art`,
    `AblaufTest.start`);
  - `services/ablauf/startdaten.py` (neu);
  - `typen.py` (`START`, `START_TEIL`, `start_teile`);
  - `treiber.starten(start=…)`, `platzhalter.einsetzen`;
  - `pruefung.py` und `pruefung_texte.py`;
  - `ausloeser.per_extern`, `zug.starten` und `zug.starten_mit`;
  - `simulation.py`, `i18n/bot_text.py`.
- **Studio:** `i18n/catalogue/fields-ablaeufe.ts`, `schema-form/schema-to-fields.spec.ts`
  (`tests[].start` als JSON-Feld).
- **Verträge:** `docs/api/openapi-v1.json`, Bereichsschemas, `bewusste-vertragszusaetze.md`.

## Tests

- `backend/tests/test_ablauf_startdaten.py` (20, vor der Umsetzung geschrieben):
  - Modell und Fassung;
  - Prüfung je Typ, Pflicht, unbekannt, Länge, Steuerzeichen, Form;
  - Teil `start` und Platzhalter;
  - Befunde;
  - Zug mit und ohne `extern`, ungültige Daten;
  - Simulation.
- Ergebnis:
  - Backend: Ablauf-, i18n- und Vertrags-Tests grün (869), ruff sauber.
  - Studio: 171 Dateien / 2113 Tests grün, eslint sauber.

## Betrieb

Keine Migration, keine neue Variable. Das Image neu bauen (Studio, Backend). Bestehende Abläufe
ändern sich nicht: Ohne Startschema bleibt die Fassung gleich.

## Review (Befundhebung)

Unabhängiges Review mit eigenen Proben. Ergebnis: 0 kritisch, 2 schwer, 9 kleiner, 1 Sammelbefund.
Alle behoben bis auf die Entscheidung in Befund 10; Tests in `test_ablauf_startdaten.py`
(jetzt 30).

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Pflichtfelder neben anderen Auslösern: Wendung, Modul und KI-Vorschlag wählten den Ablauf und scheiterten erst beim Start — der Modul-Auslöser nach dem Anlegen eines Vorgangs. | schwer | `ausloeser._aktive` lässt solche Abläufe für alle Arten außer `extern` weg; Befund `start_pflicht_ausloeser` je Auslöser, der nie startet. |
| 2 | Das Safety-Gate einer Direktaktion prüfte nur String-Werte — Text in `start` lief an Moderation und Regex vorbei. | schwer | `_direct_action_safety_text` nimmt die Strings eines dict-Werts eine Ebene tief mit (`start.thema: …`), unter derselben Gesamtkappe. |
| 3 | `\n`/`\t` fielen vor dem Zusammenziehen weg — Wörter klebten. | kleiner | Erst Leerraum zusammenziehen, dann Zeichen entfernen. |
| 4 | Eine Zahl mit 400 Stellen ließ `math.isfinite` werfen; ein einzelnes Surrogat überlebte. | kleiner | Betrag höchstens 2^53; Kategorien `Cs`, `Co`, `Cn` fallen weg. |
| 5 | Wendung und Modul brachten keinen Teil `start` — alte Daten eines früheren Laufs galten weiter. | kleiner | `starten_mit` legt bei Startschema immer einen (notfalls leeren) Teil an. |
| 6 | Doppelte Feldnamen gingen still durch. | kleiner | Befund `start_doppelt`. |
| 7 | Die Sicht „Daten“ kannte `{start.x}` nicht als Leser und kein Beispiel aus `test.start`. | kleiner | `typen.gelesene_teile`, `datensicht._werte`. |
| 8 | `{teil.start.x}` und `$teil: start` mit Pfad wurden nicht gegen das Schema geprüft. | kleiner | Erstes Pfadglied gegen die Felder; Befund `start_feld`. |
| 9 | Die Simulation nahm Startdaten auch ohne `extern` oder mit „Beginnen ab“. | kleiner | Eine Abweichung wie im Betrieb. |
| 10 | Ein Test belegte `$teil: start` an einem lesenden WLO-Werkzeug — das bekommt im Betrieb keine Teile. | kleiner | Test auf ein Modul umgestellt. Entschieden in RB-1 (Option 2): eine `nodeid` der Gastseite darf als ganzes Argument an lesende WLO-Werkzeuge (`aenderungen/…-rb1-restbefunde.md`). |
| 11 | Startdaten gingen ohne Rückfrage in Kestra-Aufträge. | kleiner | Warnung `start_auftrag`, wenn kein Modul, keine Wahl und keine Freigabe davor steht. |
| 12 | Texte: Docstring, Hints (Auslöser, Text), `platzhalter_form`, `max_zeichen` auch bei Zahl. | Kleinigkeit | Nachgezogen; `max_zeichen` nur bei Text (`NurBei`). |

Nach den Behebungen: Backend Ablauf-, Sicherheits-, i18n- und Vertrags-Tests grün (973 + 31),
ruff sauber; Studio 171 / 2113 grün.
