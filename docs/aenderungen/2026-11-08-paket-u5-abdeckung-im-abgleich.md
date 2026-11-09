# Paket U5 — Abdeckung und Lücken im Abgleich (2026-11-08)

Plan: [`plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`](../plans/2026-11-08-pakete-m1-u4-u5-u3-5.md), E-7. Baut auf M1
(Zählen) und U4 (Abgleich) auf.

## Was sich ändert

Der Abgleich kann jetzt auch zeigen, **wie viel Material es zu jedem Punkt des Entwurfs in ganz WLO gibt**, und
welche Punkte Lücken sind.

- **Parameter `abdeckung: true`:** Der Dienst zählt nach dem Abgleich mit M1 (`count_wlo_content_matches`, ohne
  LLM, höchstens 60 Punkte der Ebenen 1 und 2).
- **Je Punkt:** „N Treffer in ganz WLO“. Bei höchstens 2 Treffern steht das Etikett **„Lücke“** als Wort. Was sich
  nicht zählen ließ, heißt „nicht gezählt“.
- **Abschnitt „Lücken (n)“:** aufklappbar, offen, wenn es Lücken gibt. Je Lücke stehen bis zu zwei Beispiele als
  Links (über `host.link`). Der Hinweis sagt, dass die Zahlen für ganz WLO gelten, nicht nur für die Sammlung.
- **Fach oder Bildungsstufe unbekannt** (alle Punkte `unresolved_filter`): Modul und Quittung sagen es, statt
  Nullen zu zeigen.
- **Quittung an die KI:** die Zahl der gezählten Punkte und der Lücken, keine Titel.
- **Textfassung:** zusätzlich die Lücken mit ihrer Trefferzahl (Titel entschärft).
- **Nur mit angebotener Zählung:** Der Dienst bekommt die in diesem Zug angebotenen Werkzeuge
  (`Umgebung.verfuegbar`, Agent- und Muster-Weg). Fehlt `count_wlo_content_matches`, etwa gesperrt bei
  persönlichen Daten, gibt es den Abgleich trotzdem; die Punkte tragen `gesperrt`, und Quittung und Modul sagen
  es.
- **Gleichzeitig:** Die Zählung läuft parallel zum Lesen der Sammlung. Sie endet spätestens kurz vor der Frist des
  Laufs (`frist`); scheitert das Lesen, wird sie abgebrochen.
- Ohne Antwort beim Zählen steht der Abgleich trotzdem da; die Punkte tragen `keine_antwort`, und es heißt
  „kam nicht zustande“, nicht „keine Lücken“.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 2 hoch, 5 klein, 4 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Eine fehlgeschlagene Zählung sah aus wie „keine Lücken“ (Quittung „0 davon Lücken“, Modul „mehr als 2 Treffer“). | Summe mit `ungezaehlt`. Bei 0 gezählt heißt es „kam nicht zustande“, sonst „N von M gezählt“. |
| „Lücke“ neben „Vorhanden · 42 Inhalte“ in derselben Zeile. | Keine Lücke, wenn die zugeordnete Sammlung schon mehr als 2 Inhalte hat. |
| Eine doppelte Kennung gab mehreren Zeilen dieselben Zahlen. | Nur die erste Zeile je Kennung. |
| Sammlung und Zählung liefen nacheinander, ohne die Frist des Laufs. | Parallel; Zählung bis kurz vor der Frist. |
| Eine gesperrte Zählung nahm den ganzen Abgleich weg. | `dienst.braucht` nur noch `browse_collection_tree`; die Zählung hängt an `Umgebung.verfuegbar`. |
| Das Etikett im Abschnitt war eine nackte Zahl. | „N Treffer“. |
| Ein geschätzter Filter wirkte sicher. | „(Fach oder Stufe geschätzt)“ an der Zeile. |
| Der Abschnitt sprang beim Neuzeichnen wieder auf. | Der Klappzustand bleibt. |
| Über 60 Punkten fielen späte Punkte der Ebene 1 weg; die Grenze 2 stand fest im Text. | Erst die Ebene 1; die Grenze kommt aus den Daten (`luecke_bis`). |
| Die Textfassung schwieg bei fehlgeschlagener Zählung und nannte keinen Rest. | „ließen sich nicht zählen“, „… und N weitere“. |
| Testlücken | Tests für alle Punkte oben. |

Offen: Der Lücken-Abschnitt nennt bei Ebene 2 den Elternpunkt nicht. Die Blockgröße steigt im schlimmsten Fall um
etwa 60 kB.

## Geändert

- `ui-strukturabgleich/manifest.json`:
  - Parameter `abdeckung`;
  - Eingabe `zeilen[].abdeckung` / `abdeckung_fehlt` und `abdeckung` (Summe);
  - zweites Beispiel.
- `ui_module/dienst_strukturabgleich.py`: Zählung parallel (`_zaehlung_starten`/`_abwarten`),
  `_abdeckung_eintragen`, Quittung und Textfassung.
- `ui_module/aufruf.Umgebung.verfuegbar`; gesetzt in `services/agent_loop.py` und `services/tool_loop_module.py`.
- `services/abdeckung.py`: beim Deckel erst die Ebene 1.
- Element: Trefferzeile, Etikett „Lücke“, Abschnitt „Lücken“; Texte de/en, Stil.
- erzeugt: `manifeste.json`, `register.generated.ts`.
- Tests, die die Modul-Menge festschreiben: `test_agent_prompt_preview.py`, `test_ui_modul_schalter.py`.

## Tests

- `backend/tests/test_strukturabgleich_u4.py`:
  - Abdeckung je Punkt samt Lücken, Beispielen und Fehlstellen;
  - ohne `abdeckung` wird nicht gezählt;
  - Filter unbekannt;
  - Zählung ohne Antwort (der Abgleich bleibt);
  - Angebot nur mit beiden Werkzeugen.
- `ui-strukturabgleich.element.spec.ts`: Trefferzeile, Etikett „Lücke“, Abschnitt mit Link, ohne Abdeckung kein
  Abschnitt, Filter unbekannt, keine Lücken.

## Betrieb

Widget, Backend und Studio neu bauen. Keine Migration.
