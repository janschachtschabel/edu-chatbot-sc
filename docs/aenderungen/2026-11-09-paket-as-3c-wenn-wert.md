# Paket AS-3c: Bedingung `wenn_wert` (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D4 und §5d.

## Was sich ändert

- **Neue Bedingung `wenn_wert`:** Eine Regel der Verzweigung kann eine Stelle eines Teils vergleichen.
  Sie hat drei Angaben:
  - `quelle`: `teil.<name>` oder `teil.<name>.<pfad>`.
  - `vergleich`:
    - `vorhanden` / `leer`: Es gibt etwas, also nicht `null`, kein leerer Text, keine leere Liste und
      kein leeres Objekt.
    - `gleich`: Als Zahl, wenn die Stelle eine echte Zahl ist und der Wert eine; sonst als Text,
      ohne Rücksicht auf Groß- und Kleinschreibung, Leerraum am Rand und Unicode-Form. Zwei Texte wie
      `"01067"` und `"1067"` bleiben verschieden. Ja/nein oder true/false gilt für Wahrheitswerte.
    - `enthaelt`: Teil eines Texts, ein Element einer Liste (genau, ohne Großschreibung) oder ein
      Schlüssel eines Objekts.
    - `groesser` / `kleiner`: Nur wenn beide Seiten Zahlen sind; Komma und Punkt sind beide erlaubt.
      Sonst greift die Regel nicht.
  - `wert`: der Vergleichswert, bei `vorhanden` und `leer` leer.
- **Zahlen** sind exakt (`Decimal`). Als Text gilt nur die Form `-12`, `1,5` oder `1.5`; `nan`, `inf`,
  `1e3` und `1_000` sind keine Zahlen. Sehr große Zahlen laufen nicht über.
- **Startdaten** (`start.…`, Plan D4) kommen mit AS-4, wie bei den Platzhaltern.
- **Grenze:** Ein lesendes WLO-Werkzeug liefert Text. Ein Pfad in sein Ergebnis findet deshalb nichts,
  `enthaelt` auf den ganzen Teil schon. Pfade wirken in Teilen aus Diensten, Aufträgen, Modulen und
  Freitext.
- **`wenn_wert` steht allein:** Er darf nicht zusammen mit `wenn_teil` oder `wenn_gewaehlt` stehen.
  Die bestehende Kombination `wenn_teil` + `wenn_gewaehlt` bleibt erlaubt, damit gespeicherte Abläufe
  gültig bleiben.
- **Prüfung:**
  - Die Quelle hat die richtige Form.
  - Der Teil entsteht auf einem Weg vor der Verzweigung, wie bei den Platzhaltern aus AS-3b.
  - Ein Wert steht da, wo der Vergleich einen braucht, und fehlt bei `vorhanden` und `leer`.
  - Bei `groesser` und `kleiner` ist der Wert eine Zahl.
  - Ein unbekannter Vergleich ist ein Modellfehler (422).
- **Fassung:** Das Feld hat die Vorgabe `None`, bestehende Abläufe behalten ihre Fassung.
- **Studio:**
  - **Regel-Editor:** Er hat die Bedingung „Wert vergleichen“ mit Quelle (Vorschläge `teil.<name>`
    aus den Teilen des Ablaufs), Vergleich und Wert. Der Wert erscheint nur, wo der Vergleich ihn
    braucht. Halbe Regeln, also eine fehlende Quelle oder ein fehlender Wert, sperren das Speichern.
  - **JSON:** Ein Vergleich mit fremden Feldern und zwei Bedingungen bleiben JSON.
  - **Schrittfolge und Ablaufbild:** Sie zeigen den Vergleich als Text.

## Wo

- **Backend:**
  - `domain/config_models/ablauf.py` (`WennWert`, `Weiter.wenn_wert`);
  - `services/ablauf/vergleich.py` (neu): `quelle`, `zahl`, `vergleiche`, `greift`;
  - `services/ablauf/treiber.py` (`_waehle`);
  - `services/ablauf/pruefung.py` (`_regeln`, `_wenn_wert`), `pruefung_texte.py`.
- **Studio:**
  - `schema-form/weiter-regeln.ts`, `weiter-editor.component.ts`;
  - `ablauf-folge.ts`, `ablauf-schrittfolge.component.ts`, `ablauf-bild.ts`;
  - `_sf-meldungen.scss`;
  - Texte in `i18n/catalogue/ablaeufe-seite.ts`.
- **Verträge:** `docs/api/openapi-v1.json`, `area-schemas.fixture.ts`, Zeile in `bewusste-vertragszusaetze.md`.

## Tests

- **Backend:** `tests/test_ablauf_wenn_wert.py` deckt ab:
  - 15 Vergleichsfälle durch den Treiber;
  - Befunde (Quelle, unbekannter Teil, fehlender, überflüssiger und kein Zahl-Wert);
  - Modellfehler, zwei Bedingungen, Fassung;
  - Simulation mit Text-Ergebnis.
- **Studio:** neue Blöcke in `weiter-regeln.spec.ts` (Lesen, Schreiben, Fehler, JSON-Fälle) und
  `weiter-editor.component.spec.ts` (Bedienung).
- **Ergebnis:** Backend 962 gezielte Tests grün; Studio 170/170 grün; eslint, Tokens und a11y sauber.

## Betrieb

Keine Migration, keine neue Variable. Das Image neu bauen (Widget, Studio, Backend).

## Review (2026-11-09)

Ein frischer Reviewer fand 0 hoch, 7 klein und 2 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| `float()` nahm `nan`, `inf`, `1e3` und `1_000` an. Ein riesiger `int` warf `OverflowError`, und der Lauf blieb an der Verzweigung hängen. | Text gilt nur in der strengen Zahlenform, gerechnet wird exakt mit `Decimal`; kein Überlauf, kein NaN. Prüfung und Treiber nutzen dieselbe Funktion. |
| Bei `gleich` waren `"01067"` und `"1067"` gleich, ebenso Ziffernfolgen über 2^53. | Der Zahlenweg gilt nur, wenn die Stelle eine echte Zahl ist; zwei Texte bleiben Texte. `Decimal` rechnet exakt. |
| Ein unbekannter Vergleich öffnete den Editor; die Auswahl zeigte „ist gleich“, der Wert ging beim Bearbeiten verloren. | Die Regel bleibt JSON (Test). |
| Das Studio sperrte eine Quelle ohne gültige Form und einen Nicht-Zahl-Wert bei größer und kleiner nicht; erst der Server lehnte ab. | Neue Fehlerarten `quelleForm` und `zahl` am Feld, mit `aria-invalid` (Tests). |
| Schrittfolge und Bild zeigten Rohschlüssel wie „groesser“, auch auf Englisch. | Die Teile kommen getrennt und werden übersetzt zusammengesetzt, etwa `teil.x ist größer als „10“` (Test). |
| Beim Wechsel der Bedingung wurde der Wert falsch umgedeutet. | „Teil vorhanden: x“ wird zu „Wert vergleichen: teil.x ist vorhanden“ und zurück; sonst wird der Wert geleert (Test). |
| Testlücken | Neu getestet sind Komma, Objekt-Schlüssel, `None`, PLZ, große Zahlen, `inf`/`nan`, Listen wie `gleich` und ein Teil, der erst nach der Verzweigung entsteht. Die Fassung wird gegen einen festen Wert geprüft. |
| Kleinigkeiten | Quelle mit `\Z` statt `$`. Wahrheitswerte nehmen auch true und false. Listen-Elemente werden wie `gleich` verglichen. Text wird in Unicode-NFC verglichen. Die Teil-Vorschläge zählen `schreibt` nur an Werkzeug und Auftrag, wie die Prüfung. |

Prüfung: `test_ablauf_wenn_wert.py` 39 grün, Studio 170/170 grün, eslint sauber.

## Querschnitts-Review AS-3 (2026-11-09)

Nach AS-3a bis 3c hat ein zweiter, frischer Reviewer über alle drei Teilpakete und ihren Anschluss an den Bestand geschaut. Er fand 2 hoch, 3 klein und 3 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| Hoch: Die Wahl-Chips wurden nach `turn_assembly` doch noch gekürzt. Das geschah im Widget-Nachlauf (Werk: `max_count: 2`), in `turn_persist` und durch die Anmelde-Chips. Von 3 bis 8 Optionen kamen im Werk nur 2 an. | `domain/wahl_knopf.py` erkennt die Chips (`ablauf_wahl`). Ausgenommen sind sie in `begrenze_pillen`, bei `max_count: 0`, in `inject_auth_qr`, im Widget-Nachlauf (wie die Auftrags-Knöpfe aus K2b) und vor den Facetten (`wahl_zuerst`). Tests: `tests/test_ablauf_wahl_deckel.py`. |
| Hoch: Die Simulation nahm getippten Text immer als Freitext, der Betrieb erkennt aber ein Label als Wahl. Ein grüner Test sagte so einen anderen Weg voraus. | `wahl_aus_text` steht jetzt im Treiber; Zug und Simulation nutzen dieselbe Funktion (Tests mit und ohne Freitext). |
| Eine Wahl ließ den Freitext eines früheren Durchgangs stehen; Verzweigung und Platzhalter sahen ihn weiter. | Gab es einen früheren Freitext, wird der Teil bei der Wahl leer (Test). Ohne früheren entsteht kein leerer Teil. |
| `offene-befunde-und-todo.md` hatte keinen Deploy-Eintrag für AS-1 bis AS-3, und die Notizen widersprachen sich (Bild oder Bündel). | Ein Eintrag in §4. Die Notizen sagen einheitlich „Image neu bauen (Widget, Studio, Backend)“. |
| Freitext liegt im Vorgang, auch wenn `logging.messages` aus ist. | In Notiz AS-3a (Datenschutz) und im Deploy-Hinweis festgehalten. Das Verhalten bleibt, denn der Text ist Arbeitsstand der Person und geht mit dem Vorgang. |
| Kleinigkeiten | Gleiche Labels sind ein Befund. Plan und Feldhinweise sind nachgezogen (`wenn_wert`, „Chips der Wahl bleiben“, „keine Platzhalter in Labels“, höchstens 8 Optionen). Die Teil-Vorschläge im Studio enthalten keine Teile aus Modul-Manifesten; die Prüfung kennt sie und sperrt nichts falsch. |

Prüfung: volle Backend-Suite vor den Behebungen 9280 passed, 5 skipped. Nach den Behebungen: volle Backend-Suite 9289 passed, 5 skipped; Studio 170/170 grün.
