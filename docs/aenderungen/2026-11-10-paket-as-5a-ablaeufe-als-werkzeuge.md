# Paket AS-5a: Abläufe als Werkzeuge der KI im Agent-Modus (2026-11-10)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5g
(D1, E2-Zusatz des Nutzers: „ein Ablauf soll auch wie ein Werkzeug im Chat auslösbar sein“).
Die Entscheide A5-1 bis A5-8 habe ich nach dem Nutzerauftrag vom 09.11. selbst getroffen; sie stehen
mit Begründung im Plan.

Keine Migration, keine neue Variable. Das Studio- und das Backend-Image müssen neu gebaut werden
(Bereichsschema: `AblaufTest.quelle`).

## Was sich ändert

- **Ein Werkzeug je Ablauf:** Jeder aktive Ablauf mit dem Auslöser „KI schlägt vor“ (`agent`),
  dessen Voraussetzungen erfüllt sind, ist im Agent-Zug ein eigenes Werkzeug `ablauf-<id>`.
  - Höchstens 6 je Zug, die Beschreibung höchstens 600 Zeichen (Titel, `wann`, `nicht_wann`).
  - Die Parameter sind das Startschema (`startdaten.werkzeug_schema`): `text` → `string` mit
    `maxLength`, `nodeid` → `string` mit UUID-`pattern`, `zahl` → `number`, `ja_nein` →
    `boolean`, Pflichtfelder → `required`, die Beschreibung in der Sprache des Zugs (Rückfall
    `de`).
  - Das Sammelwerkzeug `ablauf_vorschlagen` (A2a) entfällt.
- **Name `ablauf-<id>`:** `ablauf__<id>` gälte als Werkzeug eines Fremdservers
  (`fremdwerkzeug.ist_fremd`). Ablauf-Kennungen enthalten nie `-`.
- **Vorschlag statt Start:** Die Schleife ruft nichts. `vorschlag.merken` prüft die Angaben wie
  jeden Start (`startdaten.pruefen`) und merkt den Vorschlag (einmal je Zug).
  - Passen die Angaben nicht, sind sie zu lang (über 2000 Zeichen) oder ist der Ablauf unbekannt,
    erfährt es das Modell, und es gibt keinen Knopf.
  - Die Quittung verlangt, Ablauf **und** Angaben in einem Satz zu nennen.
- **Der Knopf:** `__action__|<Titel>|ablauf_starten|{"ablauf": id, "start": {…}, "start_quelle": "ki"}`.
  Ohne Angaben bleibt er wie bisher `{"ablauf": id}`. Die bloße Kennung aus einer Sitzung vor dem
  Deploy ergibt weiter den Knopf.
- **`zug.starten`:** Startdaten nimmt jetzt auch ein Ablauf mit dem Auslöser `agent`, über
  `ausloeser.nimmt_daten`. Daten mit `start_quelle: "ki"` bekommen die Herkunft `ki`. Eine
  andere Angabe ergibt keine Herkunft. **Nur** die Gastseite (`quelle: "gastseite"` oder ihr Knopf
  „Neu starten“) trägt die Rechte aus Option 2. Eine `nodeid` der KI geht nie an ein lesendes
  Werkzeug, der Schritt geht dann zu `bei_fehler`.
- **Auslöser:** Ein Ablauf mit Pflichtfeldern ist für `agent` vorschlagbar, denn die KI bringt die
  Daten. Für Wendung und Modul bleibt er ausgeblendet.
- **Prüfung:**
  - Mit dem Auslöser `agent` ist jedes Startfeld ohne Beschreibung ein Befund
    (`start_beschreibung`), denn die Beschreibung ist die Anleitung für die KI.
  - `start_pflicht`/`start_pflicht_ausloeser` behandeln `agent` wie `extern`.
- **Simulation:** `AblaufTest.quelle` (`gastseite` | `ki`, Vorgabe `gastseite`).
  - Daten brauchen den passenden Auslöser.
  - Die Rechte gibt es nur mit `gastseite` (Querschnitts-Review RB, Befund 2).
- **Studio:** Hinweise zu den Startdaten nennen die KI. Am Testfall gibt es das Feld „Herkunft der
  Startdaten“ (DE/EN).

## Nicht in AS-5a

- **AS-5b:** Muster-Modus (ein Muster nennt `ablauf-<id>` in `tools:`).
- **AS-5c:** `direkt` (Start ohne Knopf).

## Tests

- **Neu:** `tests/test_ablauf_werkzeuge_ki.py` (18 Tests). Er deckt ab:
  - Schema, Sprache, Grenzen und den Vorschlag trotz Pflichtfeldern;
  - die Schleife (Merken, ungültige Daten, einmal je Zug, zu lang);
  - den Knopf mit `start_quelle: "ki"`;
  - den Zug (KI-Daten ohne Rechte, ein bloßer Knopf-Ablauf nimmt keine Daten, eine fremde
    Herkunftsangabe wird nicht übernommen);
  - die Prüfung (Beschreibung) und die Simulation (Herkunft `ki`).
- **Angepasst:**
  - `test_ablauf_vorschlag.py` und `test_respond_agent.py` laufen auf der neuen Schnittstelle.
  - In `test_ablauf_startdaten.py` hielt `test_andere_ausloeser_mit_pflichtfeldern_…` fest, dass
    die KI nie Daten bringt. Das ändert A5-4 bewusst; Wendung und Modul bleiben ausgeschlossen.
- **Gezielt** (ablauf, agent, respond, turn_assembly, quick replies, Startdaten, OpenAPI,
  Bereichsschemas, Kataloge, i18n, Restbefunde, Wahl): 1460 grün, 1 angepasst. Ruff ohne Befund.
  Studio: 2116 grün. OpenAPI und Bereichsschemas sind neu exportiert.

## Deploy-Hinweis

`start_beschreibung` ist ein sperrender Befund. Ein schon gespeicherter Ablauf mit dem Auslöser
`agent` und Startfeldern ohne Beschreibung lässt sich nach dem Deploy erst wieder speichern oder
testen, wenn die Beschreibungen nachgetragen sind. Im Werk betrifft das keinen Ablauf:
`sammlungsstruktur` hat kein Startschema.

## Review (unabhängig, 2026-11-10)

Ergebnis: 0 kritisch, 0 schwer, 6 klein, 2 Kleinigkeiten. Bestätigt wurde: Daten der KI kommen
auf keinem Weg zur Herkunft „gastseite“. Das Safety-Gate prüft sie wie Daten der Gastseite. Der
Name `ablauf-<id>` bleibt unter 64 Zeichen. Ein nicht angebotener Name fällt vorher heraus. Alte
Sitzungen und alte Testfälle tragen weiter. Alle Befunde sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Ein Ablauf **nur** mit dem Auslöser `agent` nahm `quelle: "gastseite"` an und bekam damit die Rechte der Gastseite. | klein | Die Herkunft „gastseite“ gibt es nur mit dem Auslöser `extern` (`zug.starten`). Test. |
| 2 | Nach `respond_to_user` war ein Vorschlag mit Angaben noch möglich. Die Antwort stand dann schon fest, ein Satz zu den Angaben fehlte (A5-8). | klein | Nach der Antwort nur noch ein Vorschlag ohne Angaben, sonst „schon geantwortet“. Test. |
| 3 | `ist_ablauf_werkzeug` prüfte nur das Präfix. Ein Fremdserver namens `ablauf-…` ergäbe `ablauf-x__suche`. | klein | Zusätzlich kein Fremdwerkzeug (`ist_fremd`), und die Kennung hat die Form einer Ablauf-Kennung. Test. |
| 4 | Gekürzt wurde erst am Ende. `nicht_wann` und der Schlusssatz („startet nichts …“) konnten abfallen. | klein | Titel und Schlusssatz bleiben ganz; `wann` und `nicht_wann` teilen sich den Rest je zur Hälfte. Test. |
| 5 | Dieselben falschen Angaben ließen sich bis zur Iterationsgrenze wiederholen. | klein | Derselbe abgewiesene Vorschlag zweimal ist Stillstand (`no_progress`), wie beim Ergebnis. Test. |
| 6 | Prompt-Vorschau und Werkzeug-Übersicht zählten die Ablauf-Werkzeuge nicht mit. | klein | Die Vorschau zählt sie. Die Übersicht bleibt bewusst ohne sie: Sie listet schaltbare MCP- und Modul-Werkzeuge, Abläufe schaltet die Seite „Abläufe“. |
| 7 | Veraltete Texte (`_aktive`, `zug.starten`, `Ausloeser.art`, `start_pflicht_ausloeser`). Falsche Angaben hießen „Das Ergebnis passt nicht“. | Kleinigkeit | Texte nachgezogen; eigener Text `ANGABEN_FALSCH`. |
| 8 | Ab dem siebten aktiven `agent`-Ablauf schweigt das System. Der sperrende Befund `start_beschreibung` fehlte in der Notiz. | Kleinigkeit | Hinweis `agent_zu_viele` beim Prüfen (keine Sperre). Der Deploy-Hinweis steht oben. |

Beim Beheben fand Ruff, dass die neue lokale Variable `quittung` die gleichnamige importierte
Funktion in `run_agent_loop` überdeckt hätte. Sie heißt jetzt `ablauf_antwort`.
