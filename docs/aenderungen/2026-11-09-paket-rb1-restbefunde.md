# Paket RB-1: Restbefunde im Backend und Entscheid zu AS-4a, Befund 10 (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5f.
Offene Punkte aus den Reviews zu AS-D bis AS-4 und zu P1 (Stand in `offene-befunde-und-todo.md` §4).

Keine Migration, keine neue Variable. Das Studio- und das Backend-Image müssen neu gebaut werden,
weil sich das Bereichsschema geändert hat (Katalog an `Schritt.werkzeug`).

## Entscheid AS-4a, Befund 10: Option 2

Eine Kennung aus den Startdaten der Gastseite darf an ein lesendes WLO-Werkzeug. Das ist eine
schmale Ausnahme von „lesende Werkzeuge bekommen keine Teile“:

- **Was:** Nur ein Feld vom Typ `nodeid` aus `start`, als **ganzes Argument**:
  `{$teil: start, pfad: <feld>}`. Keine Auswahl, kein tieferer Pfad, keine anderen Teile.
- **Wohin:** Nur an lesende WLO-Werkzeuge (`werkzeuge.LESENDE_MCP`), nie an Werkzeuge eines
  Fremdservers.
- **Woher:** Nur, wenn die Startdaten von der Gastseite kamen (`lauf.start_quelle = "gastseite"`,
  gesetzt in `zug.starten`, wenn Daten von außen kamen). Ab AS-5 kommen Startdaten der KI hinzu;
  die bekommen eine eigene Quelle und dürfen das nicht.
- **Wie geprüft:**
  - Im Lauf setzt `treiber._start_kennungen` den Wert nur ein, wenn er eine UUID ist.
  - Fehlt er oder ist er keine UUID, fehlt das Argument, und der Schritt geht zu `bei_fehler`.
  - Die Prüfung (`pruefung._ohne_start_kennungen`) nimmt nur diese Form von `mcp_teil` aus. Ihr
    Text nennt die Ausnahme.
- **Warum vertretbar:** `startdaten.pruefen` hat den Wert als UUID geprüft. Es ist kein Inhalt aus
  dem Arbeitsstand, also gibt es keinen Kanal für Gesprächsdaten zum MCP. Das lesende Werkzeug
  prüft die Rechte am Knoten selbst.
- Neu in `services/ablauf/startdaten.py`: `QUELLE_GASTSEITE`, `kennungsfelder`,
  `kennung_verweis`, `ist_kennung`. Die Simulation setzt die Quelle, wenn der Test `start` trägt.

## Weitere Befunde

| Befund | Herkunft | Lösung |
|---|---|---|
| Die Rechtsstufe sah nur `message[:2000]`, also nicht die hinteren Startdaten einer Direktaktion. | Nachprüfung Querschnitt AS-4 | `safety/legal._ZEICHEN = 8000`. Der Prüftext einer Direktaktion trägt bis zu 7000 Zeichen. Gewöhnliche Nachrichten sind kürzer, die Kosten wachsen nur mit langen Texten. |
| `umwandlung._wartende` sank bei einem Abbruch des Aufrufers sofort, obwohl der Kindprozess seinen Platz bis zur Frist hielt. Damit galt „höchstens 3“ nicht streng. | Review 2 zu P1 (vorbestehend) | Der Lauf ist ein eigenes Future mit dem Done-Callback `_lauf_vorbei`. Erst dieser senkt den Zähler, löscht das Verzeichnis und holt eine Ausnahme ab. Gewartet wird über `asyncio.shield`. |
| Der Kommentar an `auftraege/dateien.FRIST_S` sagte „wie beim Upload“ (dort 60 s, hier 30 s). | Review 2 zu P1 | Der Kommentar nennt den Grund: Alle Dateien eines Auftrags teilen sich `GESAMT_FRIST_S`. |
| Die Argumentnamen eines Dienstes wurden nicht geprüft. Ein Tippfehler fiel erst im Lauf auf (`bei_fehler`). | Querschnitts-Review AS-D | `typen.DIENST_EINGABE` ist zugleich die Liste aller Argumente je Dienst (alle Pflicht). Neue Befunde `dienst_argument` (unbekannt, mit der Liste der erwarteten) und `dienst_argument_fehlt`. |
| `werkzeug` war im Studio ein freies Feld. | Querschnitts-Review AS-D | Neuer Katalog `ablauf_werkzeuge` in `/api/config/choices`: Dienste, lesende WLO-Werkzeuge und die freigebbaren schreibenden. Er ist offen wie jeder Katalog, also nur eine Vorschlagsliste. Das Feld trägt `x-catalog`. |
| Drei gleich gebaute Verweissuchen mit verschiedener Tiefe (`typen.verweise`, `pruefung._verweise_mit_tiefe`/`_mit_wert`) und `teil_verweise._hat_verweis`. | Querschnitts-Review AS-D, Befund 6 (Rest) | Ein Wanderer `teil_verweise.alle_verweise(wert, bis=…, tiefe=…)` liefert Name, Pfad, Objekt und Tiefe. Die bisherigen Funktionen sind dünne Hüllen darum, das Verhalten ist gleich. Die Suchen nach kaputten Verweisen und Auswahlen bleiben eigene Wanderer, weil sie anderes suchen. |

## Tests

`tests/test_restbefunde_rb1.py` deckt ab: Rechtsstufe mit langem Text, Zähler nach Abbruch,
Dienst-Argumente, Katalog samt Schema und die Grenzen des Wanderers. Option 2 deckt
`tests/test_ablauf_startdaten.py` ab: nur die Gastseite, nur eine UUID, nur ein ganzes Argument,
nur ein lesendes Werkzeug, Prüfung und Simulation.

Gezielte Läufe: Option 2 41 grün. Ablauf, Teil-Verweise, Restbefunde, Startdaten, Kataloge und
Bereichsschemas: 555 grün. Ruff ohne Befund. OpenAPI und Bereichsschemas sind neu exportiert.

## Review (unabhängig, 2026-11-09)

Ergebnis: 0 kritisch, 0 schwer, 3 klein, 2 Kleinigkeiten. Das Review hat die Grenze von
Option 2 bestätigt: Nur eine geprüfte UUID der Gastseite erreicht ein lesendes WLO-Werkzeug, nie
ein Fremdwerkzeug, auch nicht über Folgezüge, „Neu starten“ oder die Simulation. Alle Befunde sind
behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Wird der Aufrufer abgebrochen, während der Lauf noch auf den Platz wartet, wandelte er danach trotzdem um (verworfene Arbeit auf dem einzigen Platz). | klein | `im_kindprozess(abgesagt=…)`: `wandle` setzt das Ereignis bei Abbruch und Frist. Ist es gesetzt, wenn der Platz frei wird, startet kein Kindprozess, und der Platz ist gleich wieder frei. |
| 2 | Die Naht `zug.starten` → `start_quelle` war ungetestet, ebenso Folgezug, Simulation, Auswahl und Fremdwerkzeug. | klein | Tests in `test_ablauf_startdaten.py`: Herkunft nur bei Daten von außen, ein Knopf ohne Daten hat keine, die Kennung gilt im Folgezug (gespeicherter Lauf), die Simulation setzt sie ein, Auswahl und `srv__…` werden abgewiesen. |
| 3 | Der Zählertest nutzte feste Wartezeiten; Frist und Fehler im Lauf waren ungetestet. | klein | Ausführer mit `asyncio.Event`, drei Fälle (Abbruch, Frist, Fehler ohne liegengebliebene Ausnahme) und der Fall aus Befund 1. |
| 4 | Die Modulköpfe von `treiber`, `pruefung` und `teil_verweise` nannten die Ausnahme nicht. | Kleinigkeit | Je ein Halbsatz mit Verweis auf `_start_kennungen`. |
| 5 | Der Kommentar nannte 7000 statt etwa 7400 Zeichen. Die Grenze gilt für jede Nachricht. | Kleinigkeit | Zahl samt Rechnung korrigiert. **Entscheid:** Die 8000 gelten bewusst für alle Nachrichten. Damit verkleinert sich auch die alte Lücke „Rechtsprüfung sieht nur 2000 Zeichen“ (offene Befunde, Paket 18); ganz geschlossen ist sie nicht, weil `message` keine Obergrenze hat. Mehrkosten nur bei langen Texten, höchstens rund 2000 Token je Zug. |

Außerhalb des Umfangs (vorbestehend): Startet kein Kindprozess, wirft `wandle` weiter, obwohl
der Modulkopf „nie geworfen“ sagt. Das ist ein Fehler des Servers (500) und so gewollt
(Review Paket 9); den Modulkopf lasse ich unverändert.
