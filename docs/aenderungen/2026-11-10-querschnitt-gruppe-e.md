# Querschnitts-Review Gruppe E (TB-E1…E4) — Befunde behoben (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md`. Nach den vier Einzelreviews lief ein
unabhängiges Review über alle vier Pakete. Ergebnis: 1 MAJOR, 4 MINOR, 4 NIT.

**Ohne Befund geprüft:**
- Der Direktstart läuft in einer Probe als Trockenlauf.
- Kein schreibender Ablauf startet direkt, also gibt es keine Kollision mit dem Dokument-Besitz.
- Migration 0022 passt zum Modell.
- Verträge, TS-Typen und i18n stimmen überein.
- Formeln erscheinen im Verlauf und im Inhaltsrahmen wie live.

| Befund | Behebung |
|---|---|
| **MAJOR:** Der Ablauf-Treiber (`platzhalter._MARKDOWN`) und der Strukturabgleich (`_md`) maskierten Klammern als `\(` und `\[`. Seit TB-E4 wurde „Brüche (Klasse 6)“ im festen Ablauf-Text so zu kursivem MathML. | Beide maskieren `( ) [ ]` (der Treiber auch `$`) jetzt als Entität (`&#40;` …). `marked` zeigt sie als Zeichen, die Formel-Erkennung greift nicht. Das Vorlesen (`ohneMarkdownEscapes`) löst genau diese fünf Entitäten auf. Tests: Treiber, Strukturabgleich, Renderer, Vorlesen. |
| **MINOR:** Der Studio-Referenz fehlte das Attribut `vorschau`. | Eintrag und Text (de/en) ergänzt; der Test erwartet 39 Attribute samt `vorschau`. |
| **MINOR:** Die Budget-Zahlen liefen auseinander (CI-Schritt, Spezifikation §5.5, Doku). | Überall 700 / 210 / 200; Messstand 192,4 kB gzip / 661,0 kB roh. |
| **MINOR:** Plan und offene Befunde waren veraltet (AS-5c „zurückgestellt“, Plan nannte `entities._probe` und `direkt: true`). | Nachgezogen. Die Abweichungen vom Plan sind dort benannt. |
| **MINOR:** Die Formel-Regel stand nur in der Kurzfassung und ungeschützt. Druck und Vorlesen gaben LaTeX roh aus. | Die Regel steht in allen drei Fassungen des Master-Skills, der Wächter `test_formeln_stehen_als_latex_in_den_begrenzern` hält sie fest. Das Druckfenster nimmt Formeln wie das Widget heraus und setzt sie im DOM ein. Das Vorlesen liest `1/2 · x` statt `\frac{1}{2}\cdot x` (`texAlsText`). |
| **NIT:** Die Ablauf-Übersicht im Studio zeigt `direkt` nicht. | Offen (die Liste liefert nur die Art), vermerkt in `offene-befunde-und-todo.md`. |
| **NIT:** Die Probe kann `direkt` eines ausgeschalteten Ablaufs nicht über die KI testen. | In `ablaeufe.md` vermerkt. |
| **NIT:** Die Vertragsnotiz und ein Kommentar waren unvollständig. | Ergänzt. |
| **NIT:** `purge_all` ohne Qualitätszeilen lässt Vorschau-Zeilen wieder als Betrieb zählen. | Als Grenze in der Notiz zu TB-E2 vermerkt. |

**Für den Nutzer:** Der Master-Skill-Knoten in WLO braucht die neue Formel-Regel.
`scripts/check_master_skill.py` meldet ihn deshalb mit 22 von 23 Regeln. Das ist erwartet, bis der
Knoten nachgezogen ist.

**Prüfung:**
- Backend: Treiber- und Strukturabgleich-Tests 53, Master-Skill-Wächter 173 grün; ruff sauber.
- Frontend:
  - `ng test ui`: 1415, `studio`: 2144, `widget`: 98 grün.
  - ESLint sauber.
  - Bündel: 192,4 kB gzip / 661,0 kB roh, Budget eingehalten. Angular warnt beim Rohwert ab 660 kB
    (nur Warnung).
