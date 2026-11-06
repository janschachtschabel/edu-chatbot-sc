# Paket A1: Abläufe — Definition im Studio, lokaler Treiber, Start per Knopf (2026-11-05)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §4, §9.
Baut auf V1/V2 auf ([`2026-11-05-paket-v1-vorgang-kern.md`](2026-11-05-paket-v1-vorgang-kern.md),
[`2026-11-05-paket-v2-datenuebergabe.md`](2026-11-05-paket-v2-datenuebergabe.md)).

## Was entsteht

Die Redaktion definiert im Studio **Abläufe**: feste Abfolgen von Schritten, deren Daten als Teile im
Vorgang der Person liegen. Ein Ablauf startet per Knopf (Direktaktion `ablauf_starten {ablauf: <id>}`),
läuft ohne Sprachmodell durch die Schritte, hält an jedem Modul an und setzt fort, sobald die Person
**diesen** Block beantwortet. Der Lauf steht im Vorgang (`akte.lauf`) und überlebt so Neuladen und
Sitzungswechsel der angemeldeten Person (Rückgabe des jüngsten Vorgangs aus V1).

- **Schrittarten:** `nachricht` (Text), `modul` (UI-Modul mit Daten, wartet auf die Antwort),
  `werkzeug` (Dienst `strukturentwurf_aus_ordnern` oder ein lesendes WLO-Werkzeug; Ergebnis als Teil
  unter `schreibt`), `verzweigung` (Regeln `wenn_teil`/`wenn_gewaehlt` → `dann`, zuletzt `sonst`), `ende`.
- **Daten:** `{"$teil": "<name>"}` in `daten`/`argumente` liest einen Teil; in `daten` darf der ganze Block
  ein Verweis sein (`daten: {$teil: draft}`).
- **Sicher speichern:** Das Studio weist einen Ablauf ab, den der Treiber nicht sicher ausführen kann —
  doppelte Kennungen, fehlende Ziele, kein Ende, unbekannte Module oder Werkzeuge, schreibende Werkzeuge,
  falsche Teilnamen, Schleifen ohne wartenden Schritt, 0 oder mehr als 40 Schritte (400 mit Befunden).
- **Grenzen im Lauf:** höchstens 25 Schritte je Zug (die Prüfung hält jeden Weg darunter); die Fassung
  (Streuwert der Schritte) steht im Lauf — ändert die Redaktion die Schritte oder schaltet den Ablauf aus,
  wird ein wartender Lauf `abgebrochen`, und die Antwort geht den gewöhnlichen Weg. Werkzeugsperren der
  Sicherheitsprüfung gelten auch für die Schritte; lesende WLO-Werkzeuge bekommen keine Teile.
- **Mitgeliefert:** Ablauf `sammlungsstruktur` (aus): Ordner erfassen (`ui_upload`) → Entwurf
  (`strukturentwurf_aus_ordnern`) → Themenbaum bearbeiten (`ui_strukturentwurf`) → Ende; ohne Unterordner
  ein eigenes Ende.

Heute wirkt nur der Auslöser `knopf`. `agent` (KI schlägt vor), `modul` und `wenn_teil` sind im Modell
und in der Prüfung vorhanden und kommen mit A2.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Modell | `domain/config_models/ablauf.py`: `AblaufArea`, `Schritt`, `Weiter`, `Ausloeser`, `AblaufKatalogArea`; Bereich `06-ablaeufe/katalog` in `AREA_MODELS`, `area_effects` (voll/voll), Liste der neuen Bereiche |
| Backend | `services/ablauf/pruefung.py` (Prüfung beim Speichern), `treiber.py` (lokaler Treiber: `starten`, `weiter`, `fassung`), `werkzeuge.py` (erlaubte Dienste und lesende WLO-Werkzeuge), `zug.py` (Katalog laden, Vorgang/Lauf festhalten, Antwort bauen) |
| Backend | `graph/nodes/preflight.py`: Direktaktion `ablauf_starten` und Fortsetzen, wenn die Antwort zum offenen Block gehört — beide hinter der Sicherheitsprüfung |
| Backend | `services/vorgaenge.lauf_setzen`; `arbeitsstand.kennzeile` nennt `Ablauf X: Schritt Y (status)` |
| Backend | `api/config_guards.py`: `_assert_ablaeufe_ausfuehrbar`; `i18n`: `action.ablauf.*`, `ablaeufe.ungueltig` (DE/EN) |
| Seed | `seeds/06-ablaeufe/katalog.yaml` |
| Studio | Abschnitt „Abläufe“ auf der Seite „UI-Module“; Feld- und Auswahltexte `fields-ablaeufe.ts` (DE/EN); Schema-Fixture neu (35 Bereiche) |

## Tests

Neu: `test_ablauf_pruefung` (gültiger Ablauf, Schemafehler, Befunde je Regel, Schleife, Auslöser,
Speicher-Prüfung im Studio, Schrittzahl), `test_ablauf_treiber` (Durchlauf, Warten, Verzweigung,
Fehlerweg, Fassungswechsel, Schrittgrenze), `test_ablauf_zug` (Seed besteht die Prüfung, Start zeigt das
erste Modul und hält den Lauf, Fortsetzen bis zum Entwurf, fremde Antwort gehört nicht zum Lauf,
ausgeschaltet, Voraussetzung Anmeldung); ergänzt: `test_vorgaenge` (`lauf_setzen`),
Studio `schema-to-fields.spec` (35 Bereiche, drei rohe JSON-Felder).

Läufe: Backend 8314 grün (nach den Review-Fixes), Studio 1967, ui-module 225, ui 1157, widget 76; ruff
und eslint sauber.

## Review A1 (2026-11-05, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 3 MAJOR, 10 MINOR, 1 NIT. Geprüft und in Ordnung: kein Weg zu schreibenden
Werkzeugen (Prüfung **und** Treiber), Fortsetzen nur mit eigenem Vorgang und offenem Block,
`ablauf_starten` erst nach der Sicherheitsprüfung.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Der Hauptknopf von `ui_upload` (`ordner_als_entwurf`) ging in die Ordner-Aktion statt an den Lauf — der mitgelieferte Ablauf kam nie über „erfassen“ hinaus | Preflight prüft den Lauf zuerst, Ordner-Aktion nur ohne wartenden Lauf | `test_der_ordner_knopf_im_lauf_setzt_den_ablauf_fort`, `test_ohne_lauf_bleibt_der_ordner_knopf_beim_ordner_weg`, `test_der_ordner_knopf_setzt_den_lauf_fort` |
| 2 | MAJOR | Werkzeugsperren der Sicherheitsprüfung galten nicht für `werkzeug`-Schritte | `blocked_tools` → `Umgebung.gesperrt`; gesperrt = kein Ergebnis → `bei_fehler` | `test_ablauf_starten_gibt_die_werkzeugsperren_weiter`, `test_ein_gesperrtes_werkzeug_liefert_nichts` |
| 3 | MAJOR | Die Prüfung ließ Definitionen durch, die der Treiber anders ausführt oder die immer scheitern | Regeln nur und Pflicht bei `verzweigung`; jede Bedingung mit `dann`, `sonst` genau einmal zuletzt; jeder Schritt erreichbar; kein Auslaufen ohne `ende`; längster Weg bis zum Halt ≤ 25 | `test_befunde_aus_dem_review` (6 Fälle), `test_mehr_schritte_ohne_halt…`, `test_ein_halt_teilt_die_kette` |
| 4 | MINOR | Rückfall auf den Moduldienst rief auch den LLM-Dienst (`ui_strukturentwurf`); Studio-Schalter „aktiv“ nicht beachtet | Rückfall nur für Module ohne Modell (`MODUL_DIENST_OHNE_MODELL` = `ui_upload`); feste Daten werden beim Speichern gegen den Vertrag geprüft; ausgeschaltetes Modul → kein Block | `test_ein_modul_mit_modell_dienst…`, `test_ein_ausgeschaltetes_modul…`, Prüfungsfall „passen nicht“ |
| 5 | MINOR | Ausschalten hielt wartende Läufe nicht an; Fassung hing an Titel/Schalter, alte Läufe blieben still stehen | Fassung nur über die Schritte; `wartet_auf` bricht einen Lauf ab, der nicht mehr kann (`abgebrochen`, Verweis aktualisiert) | `test_titel_und_schalter_aendern_die_fassung_nicht`, `test_nach_geaenderten_schritten…`, `test_ein_ausgeschalteter_ablauf_bricht…` |
| 6 | MINOR | `uebernehmen` vor der Entscheidung des Treibers → doppelt gespeichert, wenn er ablehnt | `treiber.kann_weiter` vor `uebernehmen` | (in 5 enthalten: nichts gespeichert, `fortsetzen` → `None`) |
| 7 | MINOR | Nach dem erneuten Lesen konnte ein inzwischen bewegter Lauf überschrieben werden | offener Block nach dem Lesen erneut geprüft → Konflikt-Hinweis | `test_ein_inzwischen_bewegter_lauf…` |
| 8 | MINOR | Unbekannte Voraussetzung (Rohansicht) fiel still weg | Prüfung weist ab; Start gilt dann als nicht erfüllt | `test_unbekannte_voraussetzung_und_modus…`, `test_eine_unbekannte_voraussetzung_startet_nicht` |
| 9 | MINOR | Teile (Ordnernamen, Dokument) konnten an `search_wlo_all` gehen | Prüfung weist `$teil` an lesenden WLO-Werkzeugen ab; Treiber wendet `teil_verweise.darf` an | Prüfungsfall „keine Teile“, `test_ein_lesendes_werkzeug_bekommt_keine_teile` |
| 10 | MINOR | Sperre `pg_advisory_xact_lock` (`anlegen`) offen während der Werkzeugaufrufe | Treiber rechnet vor `anlegen` | `test_ein_fehler_des_treibers…` (kein Vorgang angelegt) |
| 11 | MINOR | Fehlerhinweis fehlte neben Texten, „Weiter geht's“ am Ende, Schrittgrenze ohne Log, Treiberfehler → 500 | Hinweis immer bei Fehler, `action.ablauf.fertig`, Warnung an der Grenze, Treiber gefangen | `test_texte_und_fehlerhinweis_zusammen`, `test_die_schrittgrenze_endet_mit_fehler`, `test_ein_fehler_des_treibers…` |
| 12 | MINOR | Deutsche Befunde in englischer Meldung | Befunde je Sprache (`pruefe(ablauf, lang)`), auch doppelte IDs | `test_befunde_in_der_sprache_des_studios` |
| 13 | MINOR | Testlücken (Preflight, Fassungswechsel, Schrittgrenze, andere Person) | ergänzt | `test_eine_andere_person_setzt_den_lauf_nicht_fort`, `test_ablauf_starten_bei_hohem_risiko…` u. a. |
| 14 | NIT | `gewaehlt` als Text wurde in Zeichen zerlegt; `modus` ohne Muster | nur Listen von Texten; unbekannter Modus = Befund | `test_eine_wahl_ist_nur_eine_liste_von_texten` |
