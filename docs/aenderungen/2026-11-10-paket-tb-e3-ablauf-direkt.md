# Paket TB-E3: Die KI startet einen Ablauf direkt (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md` §4, Gruppe E. Das war bisher offen als AS-5c.
Grundlage ist der Nutzer-Entscheid N4: „Ja, wie ein Werkzeug oder weil es im Ablauf dokumentiert
ist. Meist wird die Aktion durch einen Button im Ablauf ausgelöst, wenn User zum nächsten Schritt
starten.“

**Entscheid zum Weg** (selbst getroffen, dokumentiert): Der Treiber schreibt nicht mitten in die
Antwort der KI.

- Ein direkt startender Ablauf bekommt **denselben Knopf** wie ein Vorschlag (`__action__|…|ablauf_starten|{…, "start_quelle": "ki"}`).
- Die Antwort nennt ihn zusätzlich in `ui.direkt_start`, und das Widget drückt ihn nach dem Zug
  selbst.
- So laufen Preflight, Sicherheitsprüfung, die Bremse „läuft schon“ und die Herkunft `ki` der
  Angaben unverändert, ohne zweiten Startweg.
- Die Person sieht die Antwort mit dem Knopf und dann den Start, wie bei einem Klick.

**Umsetzung:**

- **Konfiguration:** Am Auslöser `agent` gibt es `modus: direkt` (Studio „direkt“/„direct“; das
  Bereichsschema ist neu exportiert).
- **Prüfung** (`pruefung`):
  - `direkt` nur am Auslöser `agent`, sonst kommt der Befund „Modus gibt es nicht“.
  - Bei einem Ablauf, der schreibt, kommt der neue Befund `direkt_schreibt`.
- **Wann ein Ablauf schreibt:** `werkzeuge.ablauf_schreibt` (schreibendes Werkzeug, Auftrag, Upload) ist
  jetzt **eine** Regel. Vorschlag (Erlaubnis der Einbettung) und Prüfung nutzen sie gemeinsam.
- **Vorschlag** (`vorschlag`):
  - Ein direkter Ablauf quittiert mit `QUITTUNG_DIREKT`: „startet gleich nach deiner Antwort von
    selbst; sag in einem Satz, was passiert“.
  - `direkt_knopf` liefert den Knopf eines direkten Vorschlags. Ein schreibender Ablauf startet nie
    direkt.
- **Zusammenstellung** (`turn_assembly`): Sie merkt den Direktknopf (`_ablauf_direkt`, nur für diesen
  Zug).
- **Antwort** (`turn_persist`): `ui.direkt_start` wird gesetzt, aber **nur**, wenn der Knopf nach der
  letzten Kürzung noch unter den Schnellantworten steht. Unter einer offenen Frage oder unter Chips
  des Gastgebers entsteht kein Knopf und damit auch kein Start. `antwort_fuer` reicht das Feld durch.
- **Widget** (`chat-shell._direktStarten`):
  - Es drückt den Knopf nur live (`_onResult`, nie aus dem Verlauf).
  - Nur, wenn er unter den Schnellantworten steht und `ablauf_starten` auslöst.
  - Der Knopf wartet in der Reihe der Gastgeber-Aufträge, bis dieser Zug geladen ist.

**Bremsen:**
- höchstens ein Vorschlag je Zug (wie bisher);
- keine Ablauf-Werkzeuge, solange ein Lauf am KI-Schritt steht;
- der neue Start fragt wie jeder KI-Knopf nach, bevor er einen laufenden Lauf ersetzt (Marke `ki`).

Eine Schleife gibt es nicht: Während des Laufs bietet die KI keine Abläufe an, und danach braucht
es eine neue Nachricht der Person.

**Review** (unabhängig): 1 MAJOR, 7 MINOR, 1 NIT. Der Kern ist sicher: Kein schreibender Ablauf
startet direkt, und der Direktstart kann nicht mehr als ein Klick.

- **MAJOR:** Die Werkzeugbeschreibung sagte auch bei `direkt` „startet nichts … Knopf“. Ein Modell
  hätte dann einen Knopf angekündigt, und der Ablauf wäre von selbst gelaufen. Jetzt: „Starte für
  die Person …“ mit eigenem Schluss („startet gleich nach deiner Antwort von selbst“).
- **MINOR:** Die Muster-Schleife zählte einen angenommenen Direktvorschlag als abgewiesen. Jetzt
  `ist_quittung`.
- **MINOR:** Ein KI-Schritt mit `ui_upload` oder einem schreibenden Werkzeug in `agent.werkzeuge`
  zählt jetzt als schreibend.
- **MINOR:** Die Nachbearbeitung für das Widget kann den Knopf nach `turn_persist` noch streichen.
  Deshalb prüft `antwort_fuer` `direkt_start` an der API-Grenze ein zweites Mal.
- **MINOR:** Der Direktstart steht vorn in der Warteschlange, vor schon wartenden Aufträgen der
  Gastseite. Die Warnung beim Sitzungswechsel ist neutral formuliert.
- **NIT:** `direkt` an einem anderen Auslöser hat einen eigenen Befund („nur am Auslöser agent“).
- **Bewusst so gelassen** (Befund 7): Der automatische Klick erscheint wie ein Klick als Blase mit dem
  Titel des Ablaufs. Die KI kündigt den Start im Satz davor an (Quittung, Beschreibung), die Blase
  dokumentiert den Schritt. Eine eigene Kennzeichnung wäre ein neuer Vertrag; das bleibt offen.
- **Bewusst so gelassen** (Befund 6): Kommt die Antwort aus dem Verlauf statt live (Rückfall), fehlt
  `direkt_start`. Es startet dann nichts, und der Knopf bleibt sichtbar.
- **Tests dazu:**
  - Backend: 5 Fälle (Beschreibung, `nimm_an`, Upload im KI-Schritt, API-Grenze, Befundtext).
  - Widget: 1 Fall (Reihenfolge, mit Gegenprobe rot).

**Vertrag:** `UiInfo.direkt_start` (string oder null), nur live (`bewusste-vertragszusaetze.md`).

**Prüfung:**
- Backend: `test_ablauf_direkt.py` (8 Fälle), zuerst rot.
- Mit `test_ablauf_vorschlag`, `test_ablauf_werkzeuge_*`, `test_turn_assembly`,
  `test_respond_agent` und `test_ablauf_pruefung`: 248 grün.
- Widget: `chat-shell-direkt-start.spec.ts` (3 Fälle), zuerst rot.
- `ng test`: ui 1390, widget 98 und studio 2144 grün.
- ruff ist sauber, das Bereichsschema ohne Abweichung.
