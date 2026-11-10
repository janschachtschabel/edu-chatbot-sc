# Paket RB-2: Typen in der Sicht „Daten“ mit Namen (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5e
(Sicht „Daten“). Befund: Querschnitts-Review AS-D, Kleinigkeit.

Keine Migration, keine neue Variable. Das Studio-Image muss neu gebaut werden.

## Was sich ändert

- Die Spalte „Typ“ zeigt einen Namen statt der Kennung. Beispiele: „Sammlungsstruktur“ statt
  `wlo.sammlungsstruktur@1`, „Startdaten“, „Abgelegte Dateien“, „Angelegte Sammlungen“.
- Ein Werkzeugergebnis ohne eigenen Typ (`<werkzeug>@1`) heißt „Ergebnis von <werkzeug>“.
- Ein unbekannter Typ zeigt weiter seine Kennung, es geht also nichts verloren.
- Die Kennungen stehen im `title` der Zelle, damit Fachleute sie weiter sehen.
- Die Namen gibt es auf Deutsch und Englisch (`ablaufDaten.typName.*`, `ablaufDaten.typErgebnis`).

**Entscheid:** Die Namen stehen im Studio (`TYP_NAMEN` in `ablauf-daten.component.ts`), nicht im
Backend. Das ist reine Anzeige mit Rückfall auf die Kennung, und die Prüfung braucht sie nicht. Eine
zweite Typtabelle mit Logik entsteht dadurch nicht. Damit die Liste nicht hinter dem Backend
zurückbleibt, prüft ein Wächter im Backend (`tests/test_restbefunde_rb2.py`), dass jeder Typ aus
`services/ablauf/typen.py` dort einen Namen hat.

## Tests

- `ablauf-daten.component.spec.ts`: Namen, Werkzeugergebnis, unbekannte Kennung, `title`, und
  jeder Typ hat Deutsch und Englisch.
- `en.spec.ts`: „Text“ ist als gleiches Wort zugelassen.
- `test_restbefunde_rb2.py`: der Drift-Wächter.

## Review

Gemeinsam mit RB-3 reviewt (0 kritisch, 0 schwer); für RB-2 galten die Befunde 4–6 und 8.
Tabelle und Behebungen in [`…-paket-rb3-gastseite-verlauf.md`](2026-11-09-paket-rb3-gastseite-verlauf.md).
