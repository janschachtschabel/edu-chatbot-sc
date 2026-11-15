# Widget-Bündel in einer Hülle (2026-11-15)

Befund des Reviews zur Anmeldung aus der WLO-Sitzung
([`2026-11-15-anmeldung-aus-der-sitzung.md`](2026-11-15-anmeldung-aus-der-sitzung.md)):
Das Widget-Bündel lief auf der Gastseite ohne Hülle.

## Was war

- Der Angular-Builder (`@angular/build:application`) schreibt `main.js` als ES-Modul: Alle
  Deklarationen stehen auf oberster Ebene. Ein anderes Ausgabeformat kennt er nicht.
- Das Backend liefert die Datei unverändert als klassisches Skript aus
  (`<script src="…/widget/boerdi-widget.js" defer>`). Dort gehört die oberste Ebene der
  Gastseite.
- Gemessen im Browser: rund 2 000 Namen des Bündels hingen am `window` der Gastseite (777 `var`,
  1 228 Funktionen; kein `let`, `const` oder `class`).
- Folgen:
  - Jedes Skript der Seite konnte die Funktion rufen, die den Zugangsblock liest, auch den
    Block aus der WLO-Sitzung, der nur im Arbeitsspeicher liegt.
  - Namen stießen zusammen. Das Bündel belegte unter anderem `$`. Eine Seite mit `let $`
    brach das Bündel ganz (`Identifier '$' has already been declared`); eine Seite mit
    `window.$` (jQuery) verlor ihren Wert.
  - Ein doppelt eingebundenes Skript endete in einem Angular-Fehler (`NG0201`).

## Was sich ändert

- **Bau:** `npm run build:widget` hat einen dritten Schritt. `scripts/build-widget-huelle.mjs`
  setzt `dist/widget/browser/main.js` in eine sofort aufgerufene Pfeilfunktion.
  - Die Hülle ändert nur die Sichtbarkeit der Namen. `this` bleibt, was es war; das Bündel
    läuft weiter im nachlässigen Modus (kein `"use strict"`).
  - Geschrieben wird nur ein Ergebnis, das die Prüfung besteht. Ein zweiter Lauf ändert nichts.
  - Dockerfile und CI rufen `npm run build:widget` und bekommen die Hülle damit von selbst.
    Wer `ng run widget:build-widget` direkt ruft, bekommt ein Bündel ohne Hülle; die Prüfung
    unten meldet das.
- **Bau-Test:** `scripts/check-widget-huelle.mjs` (`npm run check:huelle`, in CI, auch am Ende
  von `npm run budget`). Auf oberster Ebene dürfen nur sofort aufgerufene Funktionsausdrücke
  stehen, davor höchstens Direktiven. Geprüft werden das Bündel und die Nachlade-Module.
- **E2E:** `e2e/embed.spec.ts`, „das Bündel legt keine Namen im Fenster der Gastseite an“. Der
  Test vergleicht die Eigenschaften von `window` vor dem Laden und nach dem Öffnen des Panels.
- **Nachlade-Module:** unverändert. esbuild baut sie schon mit `format: 'iife'`.

## Geprüft vor der Änderung

- **Globale Namen:** Nichts verlässt sich darauf. Durchgesehen: Nachlade-Module (eigene
  Bündel, Verbindung nur über Custom Elements), `oauth-callback.html`, `edu-sharing-demo.html`,
  die E2E-Tests, die Demo-Seiten des Backends, das Beispiel-Plugin. Das Studio lädt das Widget
  aus dem Workspace, nicht aus dem Bündel.
- **Digest im Backend:** `api/widget.py` rechnet je Anfrage `sha256` über die Bytes der Datei.
  Mit der Hülle wechselt die gehashte Adresse einmal, wie bei jedem neuen Bau.
- **Budget:** Die Hülle kostet 13 Byte. `check-widget-budget.mjs` misst nach der Hülle, das
  Budget des Angular-Builders davor.

## Grenzen

- **Hygiene, kein Schutz.** Ein Skript der Seite kann `fetch` oder `XMLHttpRequest` umbiegen
  und den Zugangsblock aus der Kopfzeile lesen, oder die Tauschstelle selbst rufen. R6 in
  [`mcp-und-anmeldung.md`](../mcp-und-anmeldung.md) gilt weiter.
- **Der E2E-Test deckt das Hauptbündel bis zum geöffneten Panel.** Nachlade-Module lädt er
  nicht. Die prüft nur der Bau-Test; sie laufen im strikten Modus.
- **Die Prüfung lässt sich mit einer eigens gebauten Eingabe täuschen:** V8 liest `<!--` in
  einem klassischen Skript als Zeilenkommentar, der TypeScript-Parser nicht. In der Ausgabe
  von esbuild kommt die Zeichenfolge nur in Texten und Mustern vor.

## Preis

Die Hülle kostet beim kalten Laden Zeit. Gemessen vom Review im Chromium ohne Oberfläche,
31 Läufe, Laden bis zum definierten Element:

| Bündel | Median | Minimum |
|---|---|---|
| ohne Hülle | 78,7 ms | 68,2 ms |
| Pfeil-Hülle (wie gebaut) | 100,3 ms | 86,1 ms |
| `function`-Hülle | 95,6 ms | 83,6 ms |

Das sind rund 15 bis 25 ms auf einem Entwicklerrechner. Pfeil und `function` liegen im
Rauschen. Die Ursache ist nicht belegt; jedes Bündel in dieser Form zahlt den Preis.

## Gemessen

- Vorher: Bau-Test rot mit 1 600 Anweisungen auf oberster Ebene; E2E-Test rot mit 2 007 neuen
  Namen am Fenster (Bündel vom 14.11.).
- Nachher: Bau-Test grün für das Bündel und fünf Module; E2E-Test grün mit null neuen Namen.
- `npm run e2e`: 118 von 118 grün.
- Budget: 668,97 kB roh von 700 (95,6 %), 194,72 kB gzip von 210 (92,7 %).
- Skript-Tests: 16 von 16 (`build-widget-huelle.test.mjs`, `check-widget-huelle.test.mjs`).
- ESLint auf den geänderten Dateien ohne Meldung.
- Der E2E-Lauf fuhr den Quellstand von 13:35 Uhr. `session/*` wurde danach im Paket
  „Anmeldung aus der WLO-Sitzung“ weiter geändert; vor dem Upload gehört ein neuer Lauf dazu.

## Review

Unabhängiges Review nach der Umsetzung: kein kritischer, schwerer oder mittlerer Befund.

| Nr. | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | klein | Die Zahl der Namen stand mit drei Werten in vier Dateien. | Überall „rund 2 000“. |
| 2 | klein | `check:huelle` war grün, wenn der Ordner der Module fehlte. | Fehlender Ordner ist ein Fehler; die Ausgabe nennt die Zahl der Module. |
| 3 | klein | Der Kommentar der Prüfung sagte dem E2E-Test mehr zu, als er misst. | Kommentar eingeengt; steht oben unter „Grenzen“. |
| 4 | klein | Die Hülle kostet beim kalten Laden 15 bis 25 ms. | Nicht behoben, hier und im Bau-Skript festgehalten. |
| 5 | Hinweis | Lücke des Parsers bei `<!--`. | Im Kopf der Prüfung benannt. |
| 6 | Hinweis | Die Doku nannte nur `fetch`; der Block reist auch per `XMLHttpRequest` (Upload). | Im Bau-Skript und hier ergänzt; die Doku-Dateien des Pakets „Anmeldung aus der WLO-Sitzung“ zieht dessen Sitzung nach. |
| 7 | Hinweis | Der Nachschritt hängt nur am npm-Skript. | `check:huelle` läuft jetzt auch in `npm run budget`. |
| 8 | Hinweis | Das Angular-Budget misst 13 Byte weniger als das eigene. | Satz in `check-widget-budget.mjs`. |
| 9 | Hinweis | Kein Test für „ohne `use strict`“; eine Generator-Hülle bestand die Prüfung. | Beides ergänzt, je mit Test. |
| 10 | Hinweis | `frontend/README.md` nannte beim Budget noch 420/140 kB; `ui-module.md` beschrieb den Bau ohne den dritten Schritt. | Beides nachgezogen. |

Das Review bestätigte außerdem im Browser: Das Widget startet mit `defer` im `<head>`, am Ende
des `<body>` und als `type="module"`; die Hülle ist byte-gleich mit dem Textumschlag des
ungehüllten Bündels.

## Dateien

- Neu: `frontend/scripts/build-widget-huelle.mjs`, `build-widget-huelle.test.mjs`,
  `check-widget-huelle.mjs`, `check-widget-huelle.test.mjs`.
- Geändert: `frontend/package.json` (`build:widget`, `check:huelle`, `budget`),
  `.github/workflows/ci.yml` (zwei Schritte), `frontend/e2e/embed.spec.ts` (ein Test),
  `frontend/scripts/check-widget-budget.mjs` (Kommentar), `frontend/README.md`,
  `docs/ui-module.md`.
- Doku des Pakets „Anmeldung aus der WLO-Sitzung“ (Plan, R6, Antwort an den MCP-Entwickler,
  offene Befunde, Kommentar in `mcp-access.ts`): auf „in einer Hülle, Hygiene und kein Schutz“
  gestellt.

## Deploy

- Image neu bauen. Keine Migration, kein `import-config`, keine neue Einstellung.
- Die gehashte Adresse des Bündels wechselt von selbst.
- Das lokale Beispiel-Plugin (`examples/chrome-plugin/vendor/boerdi-widget.js`, nicht
  eingecheckt) trägt ein altes Bündel ohne Hülle; nach dem Deploy neu holen.
