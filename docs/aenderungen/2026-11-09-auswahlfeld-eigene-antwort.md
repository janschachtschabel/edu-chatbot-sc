# Auswahlfeld: „Eigene Antwort“ als eigener Punkt (2026-11-09)

Rückmeldung aus dem Test: Im Auswahlfeld (`ui_entscheidung`) wählte eine Person erst eine Möglichkeit,
überlegte es sich anders und schrieb unten ins Freitextfeld. Die Wahl oben bekam sie nicht mehr weg
und schickte beides. Gewünscht war: Wer unten etwas einträgt, für den gilt das statt der Wahl oben.

## Was sich ändert

- **Ein Punkt der Gruppe statt eines Zusatzfeldes.** Bietet die Frage Freitext an (`freitext: true`),
  steht als letzter Punkt „Eigene Antwort“ (en: „Your own answer“) zum Anklicken, darunter das
  Textfeld. Das Feld ist über `aria-labelledby` nach dem Punkt benannt, der Punkt verweist mit
  `aria-controls` auf das Feld.
- **Einzelwahl:** „Eigene Antwort“ ist ein Radio wie die anderen.
  - Wer ins Feld schreibt, wählt den Punkt, und die Wahl oben springt heraus.
  - Wer danach wieder oben wählt, schickt nur diese Wahl. Der Text bleibt im Feld stehen, geht aber
    nicht mit.
  - Ein Klick auf „Eigene Antwort“ setzt den Fokus ins Feld. „Antworten“ geht erst, wenn dort Text
    steht.
- **Mehrfachwahl:** „Eigene Antwort“ ist eine Checkbox und kommt zur Wahl dazu. Wer sie abhakt,
  schickt den Text nicht mit.
- **Antwort:** `gewaehlt` darf leer sein, wenn nur die eigene Antwort gewählt ist (Manifest
  `antwort.gewaehlt.minItems` 0). Das Backend nimmt eine leere Wahl nur mit Text an
  (`ui_module/antwort.py`, Grund „weder Wahl noch eigene Antwort“).
- **Für die KI** heißt die Zeile im Antwortblock jetzt „Eigene Antwort der Person: …“, statt
  „Ergänzung der Person“. Ohne feste Wahl steht dort „Gewählt: keine der Möglichkeiten“.
- **Statuszeile** eines beantworteten Blocks: „Deine Antwort: Klasse 11“, wenn nur der Text
  gegeben wurde.

Ältere Widgets mit dem alten Bündel schicken weiter Wahl und Text zusammen; das Backend nimmt das
wie bisher an.

## Wo

- `frontend/projects/ui-module/src/ui-entscheidung/`: Komponente, SCSS (Feld eingerückt unter
  den Punkt), Spec, Manifest (`freitext`/`antwort`), README.
- `backend/src/boerdi/ui_module/antwort.py` und `backend/src/boerdi/ui_module/manifeste.json`
  (aus `npm run module:register`).
- Tests:
  - `backend/tests/test_ui_antwort.py`: nur eigene Antwort; leer ohne Text abgewiesen; Block-Text.
  - `backend/tests/test_ui_entscheidung_agent.py`: Wortlaut der Zeile.
  - `backend/tests/test_golden_ui_module.py`: Einzelwahl mit Text, nur eigene Antwort, Prüfung von `waehle`.
  - `frontend/e2e/entscheidung.spec.ts`: Rhythmus mit dem Punkt „Eigene Antwort“; Tastatur
    (Pfeiltasten) über „Eigene Antwort“.
- `evals/ui_module_golden.py`, `evals/run_golden.py`, `evals/README.md`: der Golden-Runner
  antwortet wie das Widget (siehe Review, Befund 2).

## Review (2026-11-09)

Ein frischer Reviewer: 1 hoch, 3 klein, 3 Kleinigkeiten. Alle behoben:

| Befund | Behebung |
|---|---|
| Hoch: Mit den Pfeiltasten auf „Eigene Antwort“ sprang der Fokus ins Textfeld. Danach bewegten die Pfeile nur die Schreibmarke, und die Gruppe war per Tastatur nicht mehr bedienbar (WCAG 3.2.2). | Ins Feld springt der Fokus nur nach einem Klick mit Maus oder Finger (`pointerdown` vor dem Klick). Ein Unit-Test und ein E2E-Test in Chromium decken das ab. |
| Der Golden-Runner schickte bei Einzelwahl Wahl und Text zusammen. Das kann das Widget nicht mehr. | Bei Einzelwahl gewinnt eine passende Möglichkeit, der Text fällt weg (`freitext_verworfen`). Ohne passende Möglichkeit ist der Text allein die Antwort (`eigene_antwort`). `waehle` darf leer sein, wenn ein Text dabei ist. |
| Nur lesend fehlte der Punkt „Eigene Antwort“: Eine reine Textantwort zeigte die Gruppe ohne Haken. | Der Punkt erscheint angehakt, ohne Textfeld. |
| Für Screenreader blieb offen, dass Schreiben „Eigene Antwort“ wählt. | Hinweis nur für Screenreader per `aria-describedby`, auf Deutsch und Englisch. Dazu ein Test: abhaken, dann schreiben hakt wieder an. |
| Ein Kommentar im Backend-Test war veraltet, ein Fall fehlte (leere Wahl mit Text, wenn kein Feld angeboten war). | Kommentar korrigiert, der Fall ergänzt. |
| Die Manifest-Beschreibung „ersetzt die festen Möglichkeiten“ war missverständlich. | Jetzt: „eine Alternative zu den festen Möglichkeiten“. |
| Die Docstrings in `antwort.py` sprachen noch von „Ergänzung“. | Angeglichen. |

Folge für den Golden-Lauf: Bei GV-UI-5 geht der Text nur noch mit, wenn das Modell dort eine
Mehrfachwahl stellt. Bei Einzelwahl gewinnt die Klasse, und der Bericht vermerkt
`freitext_verworfen`.

## Betrieb

Das Modul liegt im Haupt-Bündel des Widgets: das Widget-Bundle neu bauen, das Backend-Image neu
bauen. Es gibt keine Migration und keinen Config-Import.
