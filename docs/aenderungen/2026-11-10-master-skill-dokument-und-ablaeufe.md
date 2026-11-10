# Master-Skill-Kurzfassung: Dokument-Weg und Abläufe (2026-11-10)

Datei: `docs/skills/vorgehen-knapp.md`. Diese Kurzfassung wird in den WLO-Knoten
`535cabca-47e4-4cbf-9cab-ca47e40cbf4e` übertragen; das macht der Nutzer im md-editor.

**Warum:**
- Der Knoten (Stand 10.11.) hatte die Regeln aus U2/U3-5 noch nicht: Themenbaum-Entwurf, Upload,
  Abgleich, Bestand gegen Entwurf.
- Die Probe vom 10.11. zeigte, dass die KI das Upload-Feld in einem von drei Läufen nur beschrieb.
- Seit dem Nutzer-Entscheid vom 10.11. gehen Lesen und Entwerfen ohne Anmeldung.
- Die Abläufe der Redaktion (Plan 2026-11-09, AS-5) erscheinen als Werkzeuge `ablauf-…`, im
  Master-Skill fehlten sie.

**Geändert (Abschnitt „Oberfläche ansteuern“):**
- **Ordner oder Lehrplan:**
  - Die KI zeigt das Feld, statt es nur zu beschreiben, und nennt Ordner oder Dokument (Lehrplan
    als PDF oder Word).
  - Nach dem Lesen (`[DOKUMENT DER PERSON]`) entwirft sie mit `ui_strukturentwurf` und
    `aus_dokument: true`.
  - Lesen und Entwerfen gehen ohne Anmeldung; erst das Übertragen nach WLO braucht sie.
- **Abläufe (neu):**
  - Passt ein Werkzeug `ablauf-…`, schlägt die KI den Ablauf vor (höchstens einen je Zug), statt
    seine Schritte nachzubauen. Unter der Antwort erscheint ein Knopf, dazu ein Satz.
  - Läuft ein Ablauf (`[ABLAUFSCHRITT — …]`), bleibt die KI bei seinem Schritt und dessen
    Werkzeugen. Getippte Fragen beantwortet sie, und der Ablauf wartet.

**Wächter:** In `tests/test_master_skill_vorlage.py` gilt die Upload-Regel im neuen Wortlaut, dazu
kommt `test_knapp_dokument_weg_und_ablaeufe`. Alle drei Fassungen (Vorlage, Editor, fett) sind
grün: 167 Tests.

**Nach dem Übertragen:** `uv run python scripts/check_master_skill.py` prüft den Knoten gegen
dieselben Wächter. Danach können die Golden-Läufe GV-UI-13/14 laufen (startet der Nutzer).
