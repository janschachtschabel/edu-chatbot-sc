# Paket TW-1: Der Generator kennt den Leitfaden (2026-11-11)

Plan `plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`, Entscheid E1. Grundlage ist der
Gestaltungsleitfaden „Themenbäume“ (vom Nutzer am 11.11. eingefügt).

## Umsetzung (`services/strukturentwurf_prompt.py`)

- **Systemteil jeder Aufforderung** (obere Ebene, Unterthemen, aus Dokument, aus Inhalten):
  - eine Ordnungslogik, Geschwister gleicher Art und Form;
  - oben 5 bis 15 Punkte, darunter 3 bis 12 oder keine, nie genau einen Unterpunkt;
  - der Test „ist ein“ oder „ist Teil von“;
  - Titel mit 1 bis 4 Wörtern, Schlüsselwort zuerst, kein „Sonstiges“;
  - Klassenstufen, Niveaus, Jahreszahlen, Formate, Materialarten, Methoden, Kompetenzen,
    Zielgruppen und Arbeitsstände sind keine Punkte; höchstens in `keywords`.
- **Aufforderung aus dem Dokument:**
  - Die obere Ebene tragen die inhaltlichen Ordnungselemente: Lernfelder, Themenfelder,
    Inhaltsbereiche, Module, fachliche Kapitel. Sie werden ohne Nummern („LF 3“) benannt.
  - Ausgeschlossen sind Vorwort, Einleitung, Leitgedanken, Kompetenzmodell und -bereiche,
    Basiskonzepte, Leistungsbewertung, Hinweise zur Umsetzung, Stundentafel, rechtliche Hinweise,
    Verzeichnis, Impressum, Literatur und Anhang.
  - Fachbegriffe sind Kandidaten für Unterpunkte, Kompetenzen und Kontexte nicht.
- **`zahl_unterthemen`:** Meldet das Modell genau 1 Unterpunkt, wird der Punkt ein Blatt, denn
  der Leitfaden verbietet Einzelkinder.

## Prüfung

- `test_tw1_generator_wissen.py`: 3 Fälle, zuerst rot.
- **Angepasst:** In `test_strukturentwurf_dienst.py` meinte `unterthemen: 1` in 6 Testdaten „hat
  Unterthemen“. Seit der Regel ist es 2, die Absicht der Tests bleibt gleich.
- Strukturentwurf-Tests: 44 grün; nach dem Review mit TW-2/TW-3 und TB-T1: 85 grün; ruff sauber.

## Review (unabhängig) und Behebung

1 MAJOR, 7 MINOR, 2 NIT.

- **MAJOR 1:** „Je Lernfeld ein Punkt“ stieß auf „höchstens `anzahl_oben`“, und der Dienst
  schnitt bei `anzahl_oben` ab. Ein Lehrplan mit 13 Lernfeldern hätte drei verloren.
  - **Aufforderung:** Aus einem Dokument wird je Ordnungselement ein Punkt, nichts
    zusammengelegt. `anzahl_oben` gilt nur ohne solche Ordnung.
  - **Dienst:** Im Dokumentmodus schneidet er erst beim Deckel `HOECHSTENS_OBEN` (30) ab.
  - **Test:** 13 Lernfelder bleiben 13.
- **MINOR 2:** Systemteil und Code widersprachen sich bei 2 Unterpunkten.
  - Der Systemteil sagt jetzt: keine oder 2 bis 12, möglichst 3 oder mehr, nie genau einen.
  - Der Dienst ruft ohne vorhandene Unterpunkte nie für weniger als 2 auf, auch nicht, wenn nur
    noch 1 Platz frei ist.
- **MINOR 3 und 7:**
  - Die Spannen sind ein Richtwert. Nennt die Aufgabe eine Zahl oder gibt die Quelle eine
    Ordnung vor, gilt diese.
  - „Erfinde keine Punkte, nur um eine Zahl zu erreichen.“
- **MINOR 4:** Verlangt `hinweise` ausdrücklich eine Planungsordnung (Schuljahr, Halbjahr, Reihe),
  folgt der Generator ihr. Der Leitfaden erlaubt sie für persönliche Sammlungen von Lehrenden.
- **MINOR 5:** Facetten sind keine Punkte, „sofern sie nicht selbst das Thema sind“, etwa bei
  Medienkompetenz oder Methoden.
- **MINOR 6:** In der Beruflichen Bildung ordnen Lernfelder bzw. berufliche Handlungen die
  obere Ebene.
- **MINOR 8:** Weitere Tests:
  - `zahl_unterthemen` parametrisiert (bool, negativ, Text, Deckel);
  - Richtwert in oben, Dokument und Inhalten;
  - Ausnahmen und Berufsbildung.
- **NIT 10:** „Stationen einer Unterrichtsreihe“ ist aus dem Einleitungssatz gestrichen (eine
  Ordnungslogik).
- **NIT 9, nicht geändert:** Die Attrappen in `test_strukturentwurf_dienst` liefern weiter ein
  Kind. Die Ergebnisprüfung ist TB-4, die Tests prüfen den Ablauf, nicht die Form.

## Grenzen

- Die Regeln sind Bitten an das Modell. Eine Prüfung des Ergebnisses im Code (Tiefe, Breite,
  Einzelkinder als Warnung) bleibt TB-4.
