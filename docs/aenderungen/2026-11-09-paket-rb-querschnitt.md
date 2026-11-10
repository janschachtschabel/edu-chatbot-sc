# Querschnitts-Review RB-1…RB-3 (2026-11-09)

Ein übergreifender Blick auf die drei Pakete mit den Restbefunden
(`…-paket-rb1-restbefunde.md`, `…-rb2-typnamen.md`, `…-rb3-gastseite-verlauf.md`). Geprüft
wurden die Wechselwirkungen, die Vorbereitung für AS-5, die Stimmigkeit der Doku und die
Risiken beim Deploy. Ergebnis: 0 kritisch, 1 schwer, 5 klein, 3 Kleinigkeiten. Alle Befunde sind
behoben oder als Vorarbeit für AS-5 eingetragen.

Ohne Befund blieben:
- ein älteres Widget an einem neueren Backend und umgekehrt (`ChatRequest` und `UiInfo` lassen
  unbekannte Felder durch);
- alte Läufe ohne `start_quelle` (sie bekommen kein Recht);
- alte Nachrichten ohne Merker;
- die OpenAPI-Exporte, die Bereichsschemas und der Katalog `ablauf_werkzeuge`.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Die Herkunft „Gastseite“ folgte allein aus vorhandenen Startdaten. Ein Vorschlagsknopf der KI mit Daten (AS-5) bekäme so still die Rechte aus Option 2. Heute ist das nicht auslösbar. | schwer | `zug.starten` stellt die Herkunft nur **positiv** fest: `quelle: "gastseite"` (die Widget-API schickt es immer) oder die Marke `start_quelle` am Knopf „Neu starten“, den nur ein Start der Gastseite erzeugt. Nie aus `from_host`. Tests: Daten ohne Quelle, `from_host` ohne Quelle, Rundlauf über „Neu starten“. |
| 2 | Die Simulation setzt die Herkunft fest auf Gastseite; ein KI-Start ließe sich nicht treu simulieren. | klein | Als Vorarbeit für AS-5 in Plan §5f eingetragen (`AblaufTest` braucht eine Herkunft). |
| 3 | Die Prüfung ließ die Ausnahme auch ohne den Auslöser „Gastseite“ zu. Im Betrieb ging der Schritt dann still zu `bei_fehler`. | klein | Die Ausnahme gilt nur mit dem Auslöser `extern`, sonst kommt der Befund `mcp_teil`, dessen Text das jetzt nennt. |
| 4 | Der Verlauf-Abruf hat keine Frist. | klein | Wie im Review RB-3, Befund 1 (Frist 15 s). |
| 5 | Die Notiz AS-4b führte die Befunde 4 und 5 noch als offen. | klein | Dort auf „behoben in RB-3“ gesetzt. |
| 6 | „R1–R3“ kollidierte mit den Anforderungen R1–R5 im Plan und mit R1/R2 des MCP-Plans. | klein | Die Pakete heißen RB-1…RB-3, auch in Dateinamen und Tests. |
| 7 | Die Statuszeile des Plans stand noch auf „als Nächstes AS-4“. | Kleinigkeit | Nachgezogen. |
| 8 | RB-1 sagte, die Lücke „Rechtsprüfung 2000 Zeichen“ sei geschlossen. | Kleinigkeit | „verkleinert“: `message` hat keine Obergrenze. |
| 9 | Drei Merker heißen „von der Gastseite“, mit verschiedener Wirkung: `quelle` (Bremse), `start_quelle` (Recht), `from_host` (Anzeige). | Kleinigkeit | Der Docstring von `zug.starten` sagt: nie aus `from_host` ableiten. Ein Test belegt es. |
