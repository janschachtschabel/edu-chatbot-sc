# Paket AS-8c — Handbuch und Beispiel „Sammlung prüfen“ (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` D7 und §5n.

- **Handbuch `docs/ablaeufe.md`**, neue Kapitel:
  - Bausteine (Schritttypen, Teile, Platzhalter, Auslöser);
  - Beispiel „Sammlung aus Ordnern“ (`06-ablaeufe/sammlungsstruktur`);
  - Beispiel „Sammlung prüfen“;
  - Testen (Felder eines Testfalls, Antwortform eines Moduls);
  - Im Widget ausprobieren (Trockenlauf, gespeicherte Fassung, Etikett).

  Das Kapitel Führungen bleibt.
- **Neuer Seed `06-ablaeufe/sammlung_pruefen`**, ausgeschaltet. Er schreibt nichts in WLO:
  1. Ordner erfassen;
  2. Entwurf (Dienst);
  3. Lücken zählen (`abdeckung_zaehlen`);
  4. eine Verzweigung nach Wert (`gezaehlt` größer 0, sonst `ohne_zahlen`; ein Ausfall liefert 0);
  5. Entwurf mit Platzhaltern zeigen;
  6. eine Verzweigung nur mit `sonst`, die über den Fehlerweg springt;
  7. KI-Schritt mit zwei Werkzeugen (`search_wlo_all`, `ui_strukturabgleich`).

  Fünf Testfälle; der Entwurf entsteht darin echt aus der Ordnerstruktur. Nach dem
  Querschnitts-Review AS-8 umgebaut (Befunde 1 und 2, `…-querschnitt-as-8.md`).
- **Neuer Test `tests/test_ablauf_beispiele.py`:** Jedes Beispiel in `seeds/06-ablaeufe` besteht
  „Prüfen“, ist aus, und seine eigenen Testfälle laufen grün (5 Fälle).

**Prüfung:** alle Tests, die die Seeds lesen (61 Dateien), 1230 grün.

**Deploy:** `import-config` (neuer Seed), sonst nichts.
