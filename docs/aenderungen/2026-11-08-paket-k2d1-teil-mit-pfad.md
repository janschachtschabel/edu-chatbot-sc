# Paket K2d-1 — Ein Verweis auf eine Stelle im Teil: `$teil` mit `pfad` (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2d,
Teil K2d-1.

## Was sich ändert

- Ein Schritt kann jetzt einen Teil eines Teils nehmen:
  - `{"$teil": "volltext", "pfad": "outputs.markdown"}`. Ein Auftrag legt sein Ergebnis als
    `{outputs, dateien, warnungen}` ab; mit dem Pfad bekommt der nächste Schritt nur den Text statt des ganzen
    Ergebnisses.
  - **Pfad:** Schlüssel oder Listenstellen (Ziffern ab 0, ohne führende Null), mit Punkt getrennt, höchstens
    acht Glieder aus Buchstaben, Ziffern, `_` und `-`. Beispiel: `outputs.seiten.0.text`.
  - **`null` an der Stelle gilt als fehlend** (wie ein fehlender Teil): ein Schritt bekommt nie `null` statt eines
    Werts. `0`, `""` und `false` sind Werte.
  - **Fehlt die Stelle,** fehlt der Teil wie ein unbekannter (`volltext.outputs.markdown`). Ein Werkzeug wird dann
    nicht gerufen; der Lauf folgt `bei_fehler`.
  - Nur `$teil` und ein Text als `pfad` bilden den Verweis. Mit weiteren Schlüsseln, oder wenn `pfad` kein Text
    ist, bleibt der Wert, wie er ist.
- **Wo der Verweis gilt:** überall, wo `$teil` gilt. Das sind:
  - Argumente von Werkzeug- und Auftragsschritten;
  - `daten` eines Modulschritts, auch als ganzer Wert (`daten: {"$teil": "huelle", "pfad": "entwurf"}`, die Stelle
    muss ein Objekt sein);
  - Werkzeuge der KI (dieselbe Funktion `teil_verweise.einsetzen`).
- **Freigabe und Grenze:**
  - Wer einen Teil bekommen darf, entscheidet weiter der Name des Teils (`teil_verweise.darf`). Ein lesendes
    Werkzeug bekommt ihn auch über einen Pfad nicht.
  - Die Grenze von 64 kB an ein Werkzeug der KI gilt für die gewählte Stelle. Ein großes Ergebnis kann so in
    kleinen Stücken weitergehen.
- **Prüfung beim Speichern (und „Prüfen“ im Studio):** Neu ist ein Befund, wenn der Pfad keine gültige Form hat
  („Schritt w: Pfad 'a..b' in Teil 'structure' hat keine gültige Form …“). Ob die Stelle beim Lauf entsteht, weiß
  erst der Lauf; die B-API nennt kein Schema der Ausgaben.
- **Studio, Tabelle „Argumente“:** In einer Teil-Zeile steht der Pfad mit Punkt hinter dem Namen,
  `volltext.outputs.markdown`. Ein Name eines Teils hat keinen Punkt; das erste Glied ist also der Teil, der Rest
  der Pfad. Ein Hinweis unter der Tabelle sagt das. Ein ganzer Verweis mit Pfad (`daten`) steht wie ohne Pfad nur
  in der JSON-Box.

## Geändert

- `services/teil_verweise.py`:
  - `verweis()` (Name und Pfad), `stelle()`, `bezeichnung()`, `PFAD`;
  - `einsetzen` wählt die Stelle und meldet `name.pfad`.
- `services/ablauf/treiber.py`: `_daten` nimmt einen ganzen Verweis mit Pfad.
- `services/ablauf/pruefung.py`: `_verweise` über `verweis()`, Befund `pfad`. `pruefung_texte.py`: Text `pfad`
  (de/en).
- Studio:
  - `schema-form/teil-werte.ts`: `istTeil` mit `pfad`; Teil-Zeile ↔ `name.pfad`.
  - `teil-werte.component.ts`: der Hinweis.
  - `i18n/catalogue/area-editor.ts`: `teilWerte.pfadHinweis`.

## Bewusst so

- Die KI erfährt vom Pfad nichts. Ihre Kennzeile `[ARBEITSSTAND …]` nennt weiter `{"$teil": "<name>"}`, denn der
  Pfad ist für Abläufe gedacht. Eine Änderung der Kennzeile träfe den Cache-Teil des Systemprompts.
- Technisch nimmt `einsetzen` den Pfad auch von der KI an. Sie kommt so in Stücken bis 64 kB auch an Teile über
  64 kB; die Freigabe hängt weiter am Namen, der Merkposten der Abnahme ist insgesamt gedeckelt (256 kB).
- K2c-3 hielt `{$teil, pfad}` als JSON-Zeile. Seit K2d-1 ist es ein Verweis, in der Tabelle als Teil-Zeile; ein
  Test dazu wurde bewusst umgestellt.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 0 mittel, 5 Kleinigkeiten und ein Hinweis. Behoben:

| Befund | Behebung |
|---|---|
| `PFAD` (und schon vorher `NAME`) endeten auf `$` — ein Zeilenumbruch am Ende ging durch die Prüfung, der Lauf fand die Stelle nicht. | `\Z` statt `$`. |
| `null` an der Stelle galt als fehlend, undokumentiert. | Bewusst so, dokumentiert und getestet (`0`, `""`, `false` sind Werte). |
| `seiten.01` und `seiten.1` trafen dieselbe Stelle. | Listenstellen ohne führende Null. |
| Studio: `{"$teil": "volltext.outputs"}` (ungültiger Name) sah aus wie ein Verweis mit Pfad und wurde beim nächsten Schreiben still einer. | Ein Name mit Punkt bleibt JSON-Zeile. |
| Testlücken | Tests für falsche Werte, führende Nullen, Zeilenumbruch, fehlende Stelle im vorhandenen Teil, ganze `daten` ohne Objekt an der Stelle, Name mit Punkt im Studio. |
| Hinweis: die KI kann den Pfad technisch nutzen. | Unter „Bewusst so“ ergänzt. |

## Zweites Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 0 mittel, 3 klein, 4 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| `argumente` als ganzer Verweis (`{"$teil": …, "pfad": …}`) setzt der Treiber nie ein — der Schritt bekäme den Verweis wörtlich, die Prüfung schwieg. | Befund `argumente_ganz` (ein ganzer Verweis geht nur bei `daten`). |
| Die Prüfung suchte 32 Ebenen tief, der Treiber setzt nur bis `TIEFE` (6) ein. | Befund `zu_tief` für Verweise tiefer als `TIEFE`. |
| Eine Teil-Zeile mit Umbruch in Name oder Pfad stand im einzeiligen Feld und verlor ihn beim Bearbeiten. | Sie bleibt eine JSON-Zeile (wie Texte mit Umbruch). |
| Befunde gaben lange Pfade/Namen ungekürzt in die 422-Antwort. | Name auf 40, Pfad auf 80 Zeichen gekürzt. |
| Der Befundtext nannte die erlaubten Zeichen nicht. | Text nennt Glieder, Zeichen und 64 Zeichen je Glied (de/en). |
| Docstrings `TeilWerte`/`daten` und Testkopf ohne `pfad` bzw. zu weit. | Nachgezogen. |
| Der Pfad-Hinweis war nicht mit den Teil-Eingaben verbunden. | `aria-describedby` zeigt auf den Hinweis. |
| Testlücken | Tests für beide neuen Befunde, Kürzung, Pfad in `daten`, `volltext.` (leerer Pfad), Umbruch. |

## Tests

- neu `backend/tests/test_teil_pfad_k2d1.py`:
  - Stelle in Objekt und Liste;
  - fehlende Stelle;
  - ungültige Form;
  - was kein Verweis ist;
  - Grenze und Freigabe;
  - der Treiber in Argumenten und ganzen `daten`;
  - der Befund der Prüfung.
- Bestehend grün: `test_teil_verweise`, `test_ablauf_treiber`, `test_ablauf_pruefung`, `test_ablauf_studio_k2c1`
  (Goldfassung unverändert), `test_i18n_messages`.
- Studio: `teil-werte.spec.ts`, mit dem Rundlauf `name.pfad` ↔ Verweis und was JSON bleibt.

## Betrieb

Nichts außer dem gewohnten Bau von Backend und Studio. Keine Migration; bestehende Abläufe ändern ihre Fassung
nicht.
