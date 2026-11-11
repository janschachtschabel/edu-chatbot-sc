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
