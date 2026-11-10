# Paket AS-Da: Auswahl aus einem Teil (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D8 (R1) und §5e.

## Was sich ändert

- **Ein Verweis kann auswählen:**
  `{"$teil": "ablage", "liste": "inhalte", "wo": {"rolle": "struktur", "stand": "stored"}, "feld": "node_id"}`
  ergibt die nodeIds aller abgelegten Strukturdokumente, etwa für die Eingabe `structure_node_ids`
  eines Flows. Dafür braucht es keinen eigenen Dienst. Die Teile:
  - `liste`: der Pfad zur Liste im Teil, statt `pfad`. Beide zusammen sind ungültig.
  - `wo`: höchstens 5 Bedingungen Pfad → Wert. Ein Eintrag passt, wenn alle genau gleich sind,
    auch im Typ: `true` ist nicht `1`, `"1"` nicht `1`; Zahlen gelten als Zahl, also `1.0` = `1`.
    `null` passt nur, wo `null` steht, nicht wo die Stelle fehlt. Nur Objekte in der Liste können
    passen.
  - `feld`: der Pfad im Eintrag. Einträge ohne das Feld fallen weg. Ohne `feld` ist das Ergebnis die
    gefilterten Einträge selbst.
  - Das Ergebnis ist immer eine Liste, auch eine leere; eine leere Auswahl ist keine Lücke. Ist die
    Stelle keine Liste, fehlt der Wert wie bei einem fehlenden Teil (dann `bei_fehler`).
- **Wo es gilt:** überall, wo `$teil` gilt. Im Ablauf sind das `daten` und `argumente`, im Treiber
  und in der Simulation, bei der KI über `teil_verweise.einsetzen`. Wer einen Teil bekommen darf,
  entscheidet weiter sein Name (`darf`). Lesende WLO-Werkzeuge bekommen nie einen Teil, auch keine
  Auswahl.
- **Prüfung:**
  - Die Form von `liste`, `wo` und `feld` wird geprüft.
  - Neu ist ein Befund für jedes Objekt mit `$teil`, das kein gültiger Verweis ist. Es bliebe sonst
    still als wörtlicher Wert im Argument stehen; das galt vorher auch für Tippfehler wie `"pfaad"`.
- **Studio:** Eine Auswahl steht in der Tabelle „Argumente“ als JSON. Der Hinweis am Feld nennt die
  Form, auf Deutsch und Englisch. Ein eigener Editor folgt, wenn die Form sich bewährt hat.

## Wo

- `backend/src/boerdi/services/teil_verweise.py`: `ist_auswahl`, `auswahl_fehler`, `aufloesen`,
  `verweis` erkennt die Auswahl, `einsetzen` nutzt `aufloesen`.
- `services/ablauf/treiber.py` (`_daten`), `services/ablauf/pruefung.py` (`_auswahl`,
  `_kaputte_verweise`), `pruefung_texte.py`.
- Studio: `i18n/catalogue/fields-ablaeufe.ts`.

## Tests

- `backend/tests/test_teil_auswahl.py`:
  - Filter mit Feld, ohne Feld und ohne `wo`;
  - leere Auswahl;
  - keine Liste an der Stelle;
  - genauer Typvergleich;
  - lesendes MCP-Werkzeug bekommt nichts;
  - gültige Auswahl;
  - sechs kaputte Formen.
- 1546 gezielte Backend-Tests grün (Teile, Abläufe, Vorgang, Werkzeuge, KI, Simulation, Verträge); Studio-Texttests grün.

## Betrieb

Keine Migration, keine neue Variable, kein Vertrag geändert (Argumente sind freies JSON). Ein
bestehender Ablauf mit einem kaputten `$teil`-Objekt bekommt jetzt einen Befund. Der mitgelieferte
Ablauf hat keines.

## Review (2026-11-09)

Ein frischer Reviewer fand 0 hoch, 3 klein und 3 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| Eine Auswahl als ganze `daten` eines Modul-Schritts ergibt eine Liste. Der Schritt meldete „fehlt“ und lief jedes Mal in `bei_fehler`, die Prüfung schwieg, und das Studio zeigte die Auswahl als Tabelle mit den Zeilen „$teil“, „liste“ und „feld“. | Neuer Befund `daten_auswahl`. Im Studio ist jedes Objekt mit `$teil` keine Tabelle (Tests). |
| `wo: {k: null}` passte auch auf Einträge ohne `k` und auf Texte oder Zahlen in der Liste. | „Fehlt“ und „steht `null`“ bleiben getrennt, und nur Objekte passen (Test). |
| Testlücken | Neu getestet: der Anwendungsfall (Auftrag bekommt `structure_node_ids` als Liste), eine zu große Auswahl an ein Werkzeug der KI, `wo` mit `null`, Zahlen. Der irreführend benannte Test ist umbenannt. |
| Kleinigkeiten | Eine kaputte `liste` meldet sich einmal statt zweimal. Zahlen werden als Zahl verglichen (`1.0` = `1`, `True` bleibt nicht `1`). Der Kommentar in `teil-werte.ts` ist nachgezogen. |

Prüfung: 1513 gezielte Backend-Tests grün; `test_teil_auswahl.py` 19 grün; Studio 170/170 grün.
