# Upload 2026-11-11: Themenbaum-Abläufe zuerst, Wissen aus dem Leitfaden (TW-1 … TW-5)

Plan [`plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`](../plans/2026-11-11-themenbaum-ausloesen-und-wissen.md).
Anlass: Rückmeldung nach dem Update auf `9bbce3c`.

- „Themenbaum aus einem Thema“ startete das UI-Modul direkt, nicht den Ablauf.
- Der Themenbaum aus einer Lehrplan-PDF übernahm beliebige Bereiche statt der Lernfelder.
- Im Upload-Modul stand „Befund senden“.
- Die Liste der Abläufe im Studio brach die Titel um.

## Was

| Commit (Paket) | Inhalt | Notiz |
|---|---|---|
| Fix Studio-Liste | Titel der Liste│Editor-Seiten brechen nicht mehr buchstabenweise um. | `2026-11-10-fix-studio-seitenliste.md` |
| TW-1 | Wissen im Generator: Regeln aus dem Leitfaden in `strukturentwurf_prompt`, Ordnungselemente eines Dokuments (Lernfelder …) als obere Ebene, nie genau ein Unterpunkt. | `2026-11-11-paket-tw-1-generator-wissen.md` |
| TW-2 | `vorgaben` am KI-Schritt eines Ablaufs gehen an den Generator des Moduls (Agent- und Muster-Weg). | `…-tw-2-ablauf-vorgaben.md` |
| TW-3 | Abläufe zuerst: im Werkzeug-Angebot vor den UI-Modulen, längste Wendung gewinnt, Startknopf am KI-Schritt, „Weiter“ übersteht die Deckel. | `…-tw-3-ablaeufe-zuerst.md` |
| TW-4 | Seeds: Einstieg „mit Fragen / gleich entwerfen / ohne Ablauf“, neuer Ablauf „Themenbaum · aus einem Dokument“ (Modul-Auslöser auf das Strukturdokument), Ausstieg mit „Doch mit Ablauf“. | `…-tw-4-seeds.md` |
| TW-5 | „Befund senden“ heißt „Senden“. | `…-tw-5-beschriftung.md` |
| Querschnitt TW | Querschnitts-Review (5 MAJOR) und zweites, unabhängiges Review (2 MAJOR) behoben. | `2026-11-11-querschnitt-gruppe-tw.md` |
| Doku | Plan, offene Befunde, diese Notiz. | — |

Dateien, an denen mehrere Pakete arbeiteten, stehen im Commit ihres letzten Paketes.

## Prüfung vor dem Upload

- **Tests:**
  - Backend: alle Testdateien, die geänderte Module berühren, mit 4202 grün.
  - Frontend: ui-module 348, Studio 2144 grün.
- **Wächter:** ruff (ganzes `backend`), `npm run lint` und `check:*` sauber.
- **Chat-Smoke** (lokal, gpt-6-luna, Wegwerf-DB):
  - „Aus einem Thema“ von der Wendung über die Fragen und den Startknopf bis zum Entwurf;
  - „Ohne Ablauf“ bietet „Doch mit Ablauf“, und die nächste Wendung startet den Ablauf nicht neu
    (Marke gespeichert);
  - eine freie Bitte („Gliederung zur Photosynthese“) entwirft noch direkt. Das ändert erst der
    nachgezogene Master-Skill-Knoten.
- Die volle Suite läuft in der CI.

## Deploy

1. Keine Migration. Image neu bauen: Backend, Studio und Widget-Module haben sich geändert.
   Danach im Browser hart neu laden.
2. `boerdi import-config --werksabgleich` ausführen. Das bringt den neuen Seed
   `themenbaum_aus_dokument` (aus) und hebt unberührte Abläufe auf die neue Werksfassung.
3. **Achtung:** Wer „aus einem Thema“ oder „aus Inhalten“ seit dem 10.11. im Studio eingeschaltet
   hat, hat sie damit angepasst. Der Werksabgleich lässt sie stehen. Unter Sicherung → „Werk und
   eigene Fassung“ auf die Werksfassung umschalten und danach wieder einschalten.
4. Die gewünschten Themenbaum-Abläufe im Studio unter „Abläufe“ einschalten.
5. **Master-Skill-Knoten in WLO nachziehen:** die Abschnitte „Bestand oder Entwurf“ und
   „Abläufe“ aus `docs/skills/vorgehen-knapp.md`. Ohne das entwirft die KI eine freie Bitte weiter
   direkt, statt den Ablauf zu starten.

## Offen

Siehe `offene-befunde-und-todo.md`, Eintrag „Themenbaum-Abläufe zuerst“: Grenzen der Wendungen,
Vorgaben nur am KI-Schritt, das Thema aus einem Wendungs-Start, die Strukturprüfung (TB-4).

## Nachtrag: Rückmeldung nach dem Test (11.11.)

„ich will einen themenbaum zu einem thema erstellen“ startete den Ablauf nicht. Die KI fragte per
Auswahlfeld nach dem Thema, regelkonform nach M03 („nur ein Platzhalter → eine Frage nach dem
Thema“).

- **Wendung:** „themenbaum zu einem thema“ startet „aus einem Thema“ ohne die KI.
- **Master-Skill** (`vorgehen-knapp.md`): Ein passender Ablauf geht der Platzhalter-Frage vor, in
  „Reihenfolge der Prüfung“ (Punkt 8) und in M03 („Ablauf zuerst“). Er fragt das Thema selbst ab.
  Ein Wächter in `test_master_skill_vorlage` hält die Regel.
- Den WLO-Knoten zieht der Nutzer mit der ganzen Datei nach.


## Nachtrag 2: „Themenbaum mit Dateien“ und Werkszustand (11.11.)

„Themenbaum mit Dateien“ startete den Ablauf nicht. Gründe:

- Die Abläufe waren im Studio aus (Werkszustand), damit unsichtbar für Wendung und KI.
- Keine Wendung kannte „mit … Dateien“.
- „Aus eigenen Inhalten“ verlangt eine Anmeldung. Ohne sie wurde der Ablauf stumm übergangen.

Behebung:

- **Werkszustand (Nutzer-Entscheid):** Im Seed an sind „aus Ordnern“, „aus einem Thema“ und „aus
  einem Dokument“. Sie schreiben nichts. „Aus eigenen Inhalten“ bleibt aus: eingeschaltet ohne
  freigeschalteten Flow sperrte die Prüfung (`auftrag_frei`) den Werksabgleich.
- **Wendungen:** „themenbaum mit meinen dateien“, „themenbaum mit dateien“, „themenbaum aus
  dateien“.
- **Ohne Anmeldung (Nutzer-Entscheid „Hinweis + weiterhelfen“):** Passt die Wendung zu einem
  Ablauf, dem die Anmeldung fehlt, bekommt die KI die Zeile `[ABLAUF OHNE ANMELDUNG — …]`. Sie sagt
  es in einem Satz und hilft ohne den Ablauf weiter, in beiden Maschinen
  (`zug.anmelde_zeile`).

## Nachtrag 3: Studio — Wechsel nach abgewiesenem Speichern (11.11.)

Gemeldet: Nach „Speichern“ ließ sich nicht mehr zwischen Abläufen wechseln.

- **Nachgestellt** im Browser gegen eine Wegwerf-DB:
  - „Aus eigenen Inhalten“ einschalten und speichern: Die Prüfung weist ab, weil der Flow nicht in
    `B_API_JOBS_FLOWS` steht. Der Stand bleibt also ungespeichert.
  - Der Wechsel ist dann absichtlich gesperrt, damit nichts verloren geht. Der Hinweis dazu stand
    aber unter dem langen Formular. Wer in der Liste klickte, sah ihn nicht.
- **Behebung** (`group-section`):
  - Der gesperrte Wechsel fragt jetzt in der Liste selbst (`role="alert"`) mit „Verwerfen und
    wechseln“ und „Hier bleiben“.
  - Verwerfen stellt den gespeicherten Stand her und öffnet den gewählten Eintrag.
- **Speichern ohne Fehler:** Hier verschwindet der Vermerk „Ungespeichert“ wie bisher. Das ist im
  Browser für „aus einem Thema“ geprüft.
- **Test:** `group-section.component.spec`.
