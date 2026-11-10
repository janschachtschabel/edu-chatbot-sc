# Paket AS-5b: Ablauf-Werkzeuge im Muster-Modus (2026-11-10)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5g
(A5-6, D1: „in beiden Modi“). Vorgänger: [`…-paket-as-5a-ablaeufe-als-werkzeuge.md`](2026-11-10-paket-as-5a-ablaeufe-als-werkzeuge.md).

Keine Migration, keine neue Variable, kein neues Schema. Das Backend-Image muss neu gebaut werden.

## Was sich ändert

- **Muster:** Ein Muster darf `ablauf-<id>` in `tools:` nennen. Das Studio bietet die Namen im
  Katalog `tools` an, samt Titel: alle Abläufe mit dem Auslöser „KI schlägt vor“.
- **Trennung:** `phase3_modulate` trennt die Namen von den MCP-Werkzeugen und legt sie unter
  `ablauf_werkzeuge` ab, wie die UI-Module. Pflicht-Prüfung (A1) und Kuratier-Absicht lesen weiter
  nur MCP-Namen. Ein Ablauf-Werkzeug ist also nie Pflicht.
- **Angebot:** Die Werkzeugauswahl bietet ein genanntes Ablauf-Werkzeug nur an, wenn der Ablauf
  vorschlagbar ist (aktiv, Auslöser `agent`, Voraussetzungen erfüllt). Es sind dieselben Werkzeuge
  wie im Agent-Modus, ihre Beschreibung steht in der Sprache des Zugs. Bei fehlendem Pflicht-Slot
  (Degradation) fallen sie weg wie alle Werkzeuge.
- **Schleife des Musters:** Ein Aufruf läuft virtuell in der Vorrunde (`vorschlag.nimm_an`), wie
  ein UI-Modul. Es wird nur angeboten, was angeboten ist. Die Angaben werden geprüft wie jeder
  Start. Der Vorschlag kommt in den `session_state`. Den Knopf setzt die Zusammenstellung wie im
  Agent-Modus, mit `start_quelle: "ki"`.
- **A5-8 im Muster-Modus:** Steht `respond_to_user` in derselben Runde, gibt es keinen Vorschlag
  mit Angaben (`NEBEN_DER_ANTWORT`). Ohne Angaben ist er möglich.
- **Aufbau:** Die Namensregel (`PRAEFIX`, `ist_ablauf_werkzeug`, `kennung`) und der Schlüssel
  `ablauf_werkzeuge` liegen jetzt rein in `domain/ablauf_werkzeug.py`. Auch `domain/pattern_engine`
  braucht sie, ohne von `services` abzuhängen. `services/ablauf/vorschlag` reicht sie weiter.

## Tests

- **Neu:** `tests/test_ablauf_werkzeuge_muster.py` (9 Tests). Er deckt ab:
  - Trennung samt „kein Pflichtwerkzeug“;
  - Angebot: genannt und vorschlagbar, nicht genannt, Degradation;
  - Schleife: Vorschlag ohne MCP und mit Quittung, falsche Angaben, nicht angeboten, neben der
    Antwort;
  - Katalog.
- **Angepasst:** `test_generate.py` hält das neue Schlüsselwort `sprache` der Auswahl fest.
- **Gezielt** (Muster, Werkzeugschleife, Auswahl, Erzeugung, Kataloge, Abläufe, Agent,
  Zusammenstellung, OpenAPI, Bereichsschemas): 1773 grün, 1 angepasst. Ruff ohne Befund.

## Review AS-5b (unabhängig, 2026-11-10)

Ergebnis: 0 kritisch, 1 schwer, 5 klein, 3 Kleinigkeiten. Bestätigt wurde:
- Der Knopf erscheint im Muster-Pfad (derselbe `session_state`), und der Schlüssel wird stets
  entfernt.
- Ablauf-Aufrufe gelangen nie in die Hauptschleife, `tools_called` oder `outcomes`.
- A1 und die Kuratier-Absicht sehen die Namen nicht.
- Es gibt keinen Importzyklus.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | `werkzeuge()` kürzte auf 6, bevor nach den Namen des Musters gefiltert wurde. Ein genannter Ablauf ab Platz 7 fiel still weg. | schwer | `werkzeuge(lang, nur=…)` filtert vor der Kürzung. Tests mit 7 Abläufen (Agent und Muster). |
| 2 | Ein Ablauf-Werkzeug galt als erzwingbar: ohne Antwort-Werkzeug zwang die erste Runde einen Vorschlag. | klein | Wie die UI-Module nie erzwingbar. Test. |
| 3 | Brach der Zug nach einem gemerkten Vorschlag ab, stand der Knopf unter der Fehlerblase. | klein | Der Fehlerpfad im Muster-Knoten räumt `SITZUNG_KEY` ab. Test, nachweislich rot ohne die Behebung. Der Agent-Weg setzte ihn auch unter dem Ersatzsatz „agent.failed“: Jetzt nur bei eigenem Text des Modells (A5-8) und nie unter dem Ersatzsatz. Test. |
| 4 | Das Werkzeug wurde auch angeboten, wo kein Knopf erscheinen kann (Chips des Gastgebers, Muster ohne Schnellantworten). Die Quittung versprach einen Knopf. | klein | Kein Angebot bei Chips des Gastgebers (beide Modi), bei `quick_replies_mode: none` und am KI-Schritt. Test. |
| 5 | Kein Stillstands-Schutz im Muster. | klein | Derselbe abgewiesene Vorschlag zweimal: Die Ablauf-Werkzeuge gehen für den Rest des Zugs weg. Test. |
| 6 | Testlücken (Durchstich bis zum Knopf, ohne Angaben neben der Antwort, `MAX_JE_ZUG`). | klein | Tests ergänzt, darunter ein echter Durchstich in `test_turn_assembly.py`. |
| 7 | `ablauf-*` zählte in der Diagnose `parallel-mcp-round` mit. | Kleinigkeit | Ausgenommen. |
| 8 | Keine Spur eines Vorschlags im Muster-Pfad. | Kleinigkeit | Logzeile je Aufruf: Name und angenommen oder abgewiesen, ohne Angaben. |
| 9 | Import in der Funktion; irreführendes `__all__`. | Kleinigkeit | Das `__all__` ist ersetzt durch markierte Re-Exporte. Der Import in `phase3_modulate` bleibt bewusst lokal, wie der UI-Modul-Import daneben. |

## Querschnitts-Review AS-5a/5b (unabhängig, 2026-11-10)

Ergebnis: 0 kritisch, 1 schwer, 7 klein, 2 Kleinigkeiten (Befund 3 = AS-5b-Review, Befund 1).
Bestätigt wurde:
- Die Rechte aus Option 2 setzt nur der Treiber, und zwar nur bei „gastseite“.
- Ein gefälschtes `start_quelle: "ki"` bringt nur weniger Rechte.
- Das Safety-Gate prüft `start` unabhängig von der Herkunft.
- Die Simulation verhält sich wie der Betrieb.
- Exporte und i18n stimmen.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Ein KI-Vorschlagsknopf umging die Bremse. Er ersetzte einen laufenden Lauf ohne Rückfrage und beendete dabei einen wartenden Auftrag samt B-API-Job. | schwer | Jeder KI-Knopf trägt `start_quelle: "ki"`, auch ohne Angaben. `zug.starten` bremst dafür wie für die Gastseite: Bei gleichem Start „läuft schon“, sonst die Rückfrage „Neu starten“. Der Knopf „Neu starten“ behält die Herkunft `ki`. Test mit Rundlauf. |
| 2 | Im Muster-Modus wurden Ablauf-Werkzeuge auch am KI-Schritt eines Laufs angeboten. | klein | `generate_response(ohne_ablaeufe=bool(_ki))`. |
| 3 | Kürzen vor Filtern. | klein | Siehe AS-5b-Review, Befund 1. |
| 4 | Im Agent-Modus hing A5-8 von der Reihenfolge ab ([Vorschlag, Antwort] wurde angenommen). | klein | Die Runde wird vorab geprüft (`runde_mit_antwort`). Test mit umgekehrter Reihenfolge. |
| 5 | Der Fehlerpfad im Muster ließ den Vorschlag stehen. | klein | Siehe AS-5b-Review, Befund 3. |
| 6 | `tool_mode` (Erlaubnis der Einbettung) filterte Ablauf-Werkzeuge nicht. | klein | **Entscheid:** Ohne `full` keine Abläufe, die schreiben (schreibendes Werkzeug, Auftrag, Upload), als Werkzeug der KI, in beiden Modi. Knopf und Gastseite bleiben unverändert: Das sind Gesten der Person bzw. des Gastgebers. Tests. |
| 7 | Die Studio-Texte erklärten `ablauf-<id>` in `tools:` nicht; der Hinweis zu `wann` war veraltet; der Katalog zeigte inaktive Abläufe ohne Kennzeichnung. | klein | Feldtexte DE/EN ergänzt. Im Katalog „(aus)“ an inaktiven Abläufen. Test. |
| 8 | Doku: die Sperre durch `start_beschreibung` fehlte im Deploy-Eintrag; AS-5c und das Etikett-Thema waren nicht an ihrem Platz. | klein | Deploy-Eintrag ergänzt, AS-5c in §6 der offenen Befunde, das Etikett-Thema in der AS-U-Zeile des Plans. |
| 9 | `start_quelle: "gastseite"` ohne `ersetzt` gab bei einem `extern`-Ablauf die Rechte. | Kleinigkeit | Die Marke gilt nur zusammen mit `ersetzt` (dem Knopf „Neu starten“). Test. |
| 10 | Ein Vorschlag neben einer Frage wurde angenommen, der Knopf fiel dann still weg. | Kleinigkeit | In beiden Modi vorab geprüft: neben einer Frage keine Annahme. Tests. |

Wegen der zwei schweren Befunde folgt ein zweites, unabhängiges Review derselben Lieferung.

## Zweites Review AS-5a/5b nach der Behebung (unabhängig, 2026-11-10)

Ergebnis: 0 kritisch, 0 schwer, 5 klein, 2 Kleinigkeiten.

Bestätigt wurde, dass beide schweren Befunde korrekt behoben sind. Die Bremse für KI-Knöpfe ist in
allen Fällen durchgespielt, auch der Rundlauf „Neu starten“, und eine Schleife ist nicht möglich.
Die Behebungen brachten keinen neuen schweren Fehler. Alle Befunde sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | `tool_mode` wurde bei der Prüfung auf bekannte Werte nicht normalisiert. `"READ-ONLY"` ergab „voll“, während `erlaubt` lesend rechnet. | klein | Gleiche Normalisierung wie `host_capabilities.erlaubt`. Parametrisierter Test (Groß- und Kleinschreibung, Leerraum, `curate`, unbekannt, leer). |
| 2 | Scheiterte der LLM-Aufruf einer späteren Runde, gab die Muster-Schleife die Fehlerblase zurück, ohne zu werfen. Der Vorschlag blieb stehen. | klein | Der Fehlerweg der Schleife räumt Vorschlag und Frage ab. Test, bei dem die zweite Runde scheitert. |
| 3 | Die Abweisung „neben der Antwort“ liest das Modell nie, ein Vorschlag mit Angaben ging still verloren. | klein | Die Werkzeugbeschreibung sagt: „Mit Angaben: rufe das Werkzeug allein auf und antworte erst nach der Quittung.“ Eine Logzeile zählt die Verluste ohne Inhalt. Test. |
| 4 | Testlücken an der Bremse und an `tool_mode`. | klein | Tests: derselbe KI-Start ergibt „läuft schon“; ein KI-Knopf ohne Angaben gegen einen wartenden Auftrag ergibt die Rückfrage samt „Stand prüfen“, ohne Abbruch; `tool_mode` in allen Formen. |
| 5 | Der Studio-Text sagte „ohne Schreibrecht“, gemeint ist „nicht full“ (auch `curate`); der KI-Schritt fehlte. | klein | DE/EN korrigiert. |
| 6 | `runde_mit_frage` zählte auch nicht angebotene Fragen. | Kleinigkeit | Nur angebotene. |
| 7 | Zerrissener Docstring. | Kleinigkeit | Zusammengezogen. |

**Vorbefunde, mit erledigt:** Zwei veraltete Kommentare in `chat-shell.component.ts` (`startAblauf`,
`quelle`) sind nachgezogen.

**Vorbefund, offen:** Wartet ein Lauf an einer Wahl mit 4 oder mehr Chips, schneidet
`anhaengen(…, alle=True)` den Ablauf-Knopf ab, während das Werkzeug weiter angeboten wird. Das ist
selten und gehört zu AS-U (Knopf-Ordnung). Eingetragen in den offenen Befunden.

**Beim Beheben:** Der Log-Wächter (`test_log_ohne_inhalt`) beanstandete die neue Logzeile, weil ihre
Argumente die Variable `text` enthielten. Der Grund steht jetzt vorher in einer eigenen Variable.

**Volle Suite nach allen Behebungen (10.11.):** 9500 bestanden, 5 übersprungen.
