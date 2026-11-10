# Paket AS-Ub: die Ablauf-Leiste im Widget (2026-11-10)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5h
(D10, E5, U-6, U-7). Das Backend dazu liefert [`…-paket-as-ua-leiste-backend.md`](2026-11-10-paket-as-ua-leiste-backend.md).

Keine Migration, keine neue Variable. Das Widget-Bündel muss neu gebaut werden
(`scripts/build-widget`), danach im Browser einmal hart neu laden.

## Was sich ändert

- **Ablauf-Leiste** (`boerdi-ablauf-leiste`, `ui/src/shell/ablauf-leiste.component.ts`): Sie
  steht über dem Hinweis „Gespräch fortsetzen“ und dem Eingabefeld, solange im Gespräch ein
  Lauf nicht beendet ist.
  - **Inhalt:** der Titel, „Schritt n von m“ und der Status in Worten („wartet auf dich“,
    „Auftrag läuft“, „wartet auf deine Freigabe“ …; ein unbekannter Status zeigt nur den
    Schritt).
  - **„Abbrechen“:** schickt die Direktaktion `ablauf_abbrechen`. Das Backend fragt nach, bevor
    es den Lauf samt Auftrag beendet. Gesperrt, solange ein Zug läuft.
  - **„Später fortsetzen“ (U-6):** klappt die Leiste zu einer Zeile zusammen („… wartet — hier
    geht es weiter, wenn du so weit bist“) mit „Zeigen“. Ein anderer Ablauf erscheint wieder
    aufgeklappt.
  - **„Gesammelte Daten (n)“:** als natives `<details>`, je Teil Name und Kurztext.
- **Stand:** aus `ui.ablauf` der jüngsten Bot-Antwort, live und nach dem Neuladen. Fehlt er dort,
  ist der Lauf beendet und die Leiste verschwindet.
- **KI-Etikett (U-7):** „KI-generierte Antwort“ entfällt an Nachrichten mit `ui.fester_text`
  (Treiber-Texte, feste Hinweise des Ablaufs).
- **Barrierefreiheit:**
  - Die Leiste ist eine benannte Region („Laufender Ablauf“).
  - Der Stand ist eine höfliche Live-Region: Ein neuer Schritt wird angesagt, ohne zu
    unterbrechen.
  - Echte Knöpfe, mindestens 32 px hoch, mit sichtbarem Fokus.
  - Logische Abstände (RTL), Umbruch bei schmaler Breite.
  - Nur M3-Systemtoken, Übergang nur ohne `prefers-reduced-motion`.
- **Texte:** `ablauf.leiste.*` auf DE und EN.

## Grenzen

- **Budget des Widget-Bündels:** 199,93 kB gzip bei einer harten Grenze von 200 kB.
  - Die Warnschwelle (190) war schon seit K1b überschritten (192,31 kB).
  - **Vor dem nächsten Widget-Paket** muss das Bündel kleiner werden, etwa indem große oder
    seltene Teile nachgeladen werden. Eingetragen in den offenen Befunden (§1).

## Tests

- `ablauf-leiste.component.spec.ts` (8 Tests). Er deckt ab:
  - ohne Stand nichts;
  - Region, Titel, Schritt und Status (DE/EN); unbekannter Status;
  - Abbrechen als Ereignis, gesperrt während eines Zugs;
  - Später/Zeigen; ein neuer Ablauf erscheint wieder offen;
  - gesammelte Daten mit und ohne Teile.
- `chat-shell-ablauf-leiste.spec.ts` (3 Tests): Stand aus der jüngsten Antwort samt Ausblenden;
  KI-Etikett nur an nicht festen Texten; „Abbrechen“ schickt `ablauf_abbrechen`.
- **Gesamt:** ui 1263, widget 93 grün; ESLint ohne Befund; `npm run budget` eingehalten (siehe
  oben).

## Review (unabhängig, 2026-11-10; Code und Barrierefreiheit)

Ergebnis: 0 kritisch, 2 schwer, 6 klein, 3 Kleinigkeiten. Bestätigt wurde:
- Region, Ansage nur bei geändertem Text, Kontrast (hell etwa 7,5:1, dunkel etwa 5,6:1).
- Zielgrößen, RTL, reduzierte Bewegung.
- Doppelklick auf „Abbrechen“ ist sicher.

Alle Befunde sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Jede lokale Bot-Blase (Hinweise, Fehler, Anmeldung, „gespeichert“) galt als jüngste Antwort; die Leiste verschwand mitten im Lauf. | schwer | Nur Serverantworten zählen (sie tragen `ui`, lokale Blasen nie). Dazu hängt das Backend den Stand auch an Fehlerblasen (AS-Ua, Befund 7). Test mit Hinweisblase und eigener Nachricht danach. |
| 2 | „Später fortsetzen“/„Zeigen“ standen in getrennten Zweigen; der geklickte Knopf verschwand und der Fokus fiel auf `body`. | schwer | Ein Umschaltknopf mit `aria-expanded`, der im DOM bleibt. Test prüft `document.activeElement`. |
| 3 | Die Pause hing nur an der Ablauf-Kennung: Derselbe Ablauf, neu gestartet, erschien zugeklappt. | klein | Ein Effekt setzt die Pause zurück, sobald kein Stand da ist oder ein anderer Ablauf kommt. Erst war `linkedSignal` geplant; der neue Test zeigte, dass es das Ende nie sieht, weil das Template die Pause ohne Stand nicht liest. Test. |
| 4 | Das Backend hängte den Stand an die letzte Antwort, auch an eine leere, die das Widget nicht wiederherstellt. | klein | Nur an eine Antwort mit Text oder UI-Blöcken. Tests im Backend und im Widget (Wiederherstellung). |
| 5 | Technische Teilnamen („draft“) in der Liste. | klein | Nur der lesbare Kurztext. |
| 6 | Lange Texte liefen bei 320 px über; viele Teile schoben den Chat weg. | klein | `overflow-wrap: anywhere`, Liste höchstens 40 % der Höhe mit eigenem Scrollen. |
| 7 | „Abbrechen“ über dem Eingabefeld war mehrdeutig. | klein | „Ablauf abbrechen“ / „Cancel workflow“, gleich wie die Blase. |
| 8 | Testlücken (lokale Blasen, Wiederherstellung, Ansage bei Schrittwechsel, Fokus; der Etikett-Test zählte nur). | klein | Ergänzt; der Etikett-Test prüft die einzelne Blase. |
| 9 | Fest verdrahtetes „·“. | Kleinigkeit | Schlüssel `ablauf.leiste.stand` („{schritt}, {status}“). |
| 10 | „im Gespräch“ sagte wenig. | Kleinigkeit | „die KI ist dran“ / „the AI is working“. |
| 11 | Ein gesperrtes „Abbrechen“ war nur an der Farbe erkennbar; die Transition war wirkungslos. | Kleinigkeit | Deckkraft und gestrichelter Rand; Transition entfernt. |

**Nicht geprüft (gehört in die Browser-Abnahme):** Tastatur von Hand, 200 % Zoom, Screenreader.

## Zweites Review AS-Ua/AS-Ub nach der Behebung (unabhängig, 2026-11-10)

Anlass waren vier schwere Befunde aus den beiden ersten Reviews. Ergebnis: 0 kritisch, 0 schwer,
6 klein, 5 Kleinigkeiten. Bestätigt wurde: Alle früheren Behebungen sind korrekt umgesetzt, jeder
Serverweg trägt `ui`, und nach einem Abbruch bleibt kein Stand stehen. Alle Befunde sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Die Rückfrage „Ablauf abbrechen?“ bot nur „Ja“. Schon der Klick verwirft die offene Abnahme samt Chips des wartenden Schritts. | klein | Die Rückfrage bietet den Weg zurück an: „Weiter im Ablauf“, „Vorschau erneut zeigen“, die Wahl-Chips oder „Stand prüfen“, in der Reihenfolge von `turn_assembly`. Test. |
| 2 | „Neu starten“ desselben Ablaufs ging ohne Zwischenstand ohne Lauf; die Leiste blieb zugeklappt. | klein | Laufmarke `start` je Lauf (`treiber.starten`, im Verweis, als `ui.ablauf.lauf`); die Pause gilt nur diesem Lauf. Tests in Backend und Widget. |
| 3 | Der Knopf wechselte Beschriftung **und** `aria-expanded` („Später fortsetzen, erweitert“). | klein | Die Beschriftung sagt den Zustand; `aria-expanded` entfällt. |
| 4 | Die Verdrahtung des Stands war an den Endpunkten nicht getestet. | klein | `test_ablauf_leiste_endpunkte.py`: POST, Strom, Fehlerblase, Verlauf. |
| 5 | Nach einem Strom-Abbruch nimmt das Widget die erste Antwort nach der Frage, der Stand hing nur an der letzten. | klein | Der Stand hängt an allen wiederhergestellten Antworten nach der letzten Frage. Test. |
| 6 | Der Verlauf rechnete den Titel aus der Sprache des Browsers, nicht des Widgets. | klein | Der Verlauf-Abruf schickt `Accept-Language` mit der Sprache des Widgets (CORS-unbedenklich). Test. |
| 7 | `{start.…}` ohne Herkunft galt als fest. | Kleinigkeit | Fest nur mit Startdaten der Gastseite. Test. |
| 8 | Privater Helfer `freigabe_zug._plan_offen` über die Modulgrenze. | Kleinigkeit | Öffentlicher Name `plan_offen`. |
| 9 | Endstatus doppelt (`fortschritt`, `zug`). | Kleinigkeit | Eine Konstante `treiber.BEENDET`. |
| 10 | Nach gescheitertem Speichern fragte die Fehlerblase die Datenbank ein zweites Mal. | Kleinigkeit | Kein zweiter Versuch. Test. |
| 11 | Eine Kennung, die am Ende des gekürzten Kurztexts abgeschnitten war, blieb als Bruchstück stehen. | Kleinigkeit | Auch Bruchstücke am Ende fallen weg. Test. |

**Ebenfalls angepasst:** `test_ablauf_zug.py` hält den Verweis exakt fest und kennt jetzt die
Marke `start`.

**Prüfung nach dem zweiten Review (10.11.):** Die volle Backend-Suite zeigt 9533 bestanden,
5 übersprungen (22:35 min). Im Frontend sind ui 1269, widget 93 und studio 2116 grün, ESLint und
ruff sauber.
