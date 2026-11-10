# Paket BU-3 — Debug-Panel als nachgeladenes Element (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5i (BU-3) und §5j („Ud-5 neu“).

**Anlass:** „Meine Vorgänge“ (AS-Ud) kostete +3,15 kB gzip und hob das Widget auf 190,6 kB, also
über die Warnschwelle. Die Liste bleibt im Hauptbündel; dafür wird das Debug-Panel nachgeladen. Es
ist für jede angemeldete Person unnötig, nur Redaktion und Entwicklung nutzen es.

**Für die Person:** nichts Neues. Wer den Debug-Schalter einschaltet, bekommt das Panel wie vorher;
es lädt beim ersten Mal kurz nach. Scheitert das Laden (Netz, Sicherheitsregeln der Seite), steht
ein Satz da (`debug.ladeFehler`, de/en).

**Geändert:**
- **Widget-Teile ohne Manifest:** Unter `frontend/projects/ui/src/nachgeladen/ui-<name>/` gibt es eine
  zweite Quelle für nachgeladene Elemente. Sie sind kein UI-Modul: kein KI-Werkzeug, nicht im
  Register.
  - `scripts/build-nachlade-module.mjs` baut sie wie die Module (gleicher Index, SRI, Pfad
    `/widget/module/`) und weist einen doppelten Namen ab.
  - `scripts/module-register.mjs` erzeugt auch ihren Stil (`ui-<name>.stil.generated.ts`), mit
    derselben `--pruefen`-Prüfung.
- **Element** `boerdi-ui-debug-panel` (`nachgeladen/ui-debug-panel/`):
  - `debug-abschnitte.ts` und `debug-sicherheit.ts` bauen die sechs Abschnitte als DOM. Zeilen und
    Texte sind wie im früheren Template, Fremdtext steht immer als Text.
  - `ui-debug-panel.element.ts` hat die Eigenschaften `debug`, `ui`, `show` und `uebersetzen`.
    Der Name ist nicht `translate`, das ist schon ein Attribut jedes HTML-Elements.
  - `ui-debug-panel.element.scss` ist der Stil der früheren Komponente.
- **Hülle** `debug/debug-panel-huelle.component.ts` (gleicher Selektor `boerdi-debug-panel`): Sie lädt
  erst, wenn das Panel zu sehen sein soll (Schalter an und Debug-Block oder `ui`), und nur einmal;
  danach reicht sie jede Änderung an dasselbe Element weiter.
- `debug/debug-panel.component.*` entfällt. Die Spec gilt am Element weiter: 17 Fälle, dazu 3 neue
  (zweites Definieren, Neuzeichnen, Fremdtext bleibt Text). `public-api` exportiert die Hülle.
- **Doku:** `docs/ui-module.md` §2.5 (Widget-Teile).

**Wirkung:** `main.js` sinkt von 190,6 auf **186,9 kB gzip** (644,6 kB roh). Das Bündel
`ui-debug-panel` hat 3,8 kB gzip; alle nachgeladenen Teile zusammen haben 40,3 von 60 kB.

**Prüfung:**
- Vitest: ui 1316, ui-module 346, widget 93, studio 2116.
- Element-Spec 20, Hüllen-Spec 4.
- Playwright 107/107, darunter das Kontrast-E2E, das das Debug-Feld in Hell und Dunkel misst (jetzt
  im nachgeladenen Element).
- Skript-Tests: `module-register` 18, `build-nachlade-module` 6, `check-module-budget` 4;
  `--pruefen` aktuell.
- ESLint sauber.

**Deploy:** Widget-Bündel neu bauen (das Dockerfile kopiert `dist/widget-module` mit). Keine Migration.

**Review (10.11., unabhängig):** 0 kritisch, 1 schwer, 6 mittel, 4 klein. Alle sind behoben oder
bewusst entschieden.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Fehlende Werte erschienen als „undefined“ oder „null“, Angular gab leeren Text aus. Häufig bei `phase3_modulations: {}` (Tour, Begrüßung, Fehlerpfade). | schwer | Helfer `txt()` wie Angulars Interpolation an allen Template-Literalen; der `title` der Balken bleibt wie zuvor. Spec: das Panel enthält nie „undefined“ oder „null“. |
| 2 | Im Dev-Server ist der Nachlade-Index leer, das Panel meldete dort einen irreführenden Grund. | mittel | Der Fehlersatz nennt keinen Grund mehr und sagt, dass Aus/An es erneut versucht. Der Dev-Server-Fall steht in `docs/ui-module.md` §2.5 und im Kopf der Hülle. |
| 3 | Nach einem Ladefehler blieb das Panel bis zum Neuladen der Seite tot. | mittel | Ausschalten setzt den Fehler zurück, das nächste Einschalten lädt neu. Spec. |
| 4 | Vier Setter zeichneten viermal, und die Box wurde je Zug ersetzt (Scroll-Lage weg). | mittel | Sammel-Setter `setze()`; die Box bleibt dasselbe Element. Spec. |
| 5 | Laden und Fehler wurden Vorlesern nicht angesagt. | mittel | Ständige Statuszeile (`role="status"`, `debug.laedt` / `debug.ladeFehler`). Spec. |
| 6 | Ein kaputter Block (`null` in einer Liste) warf im Setter, das Panel zeigte den alten Zug. | mittel | `zeichne` fängt ab, leert das Panel und warnt in der Konsole. Spec. |
| 7 | Testlücken. | mittel | Fälle für fehlende Werte, Wiederholung, Statuszeile, Lader `null`, `title` der Balken und `role="note"`. Ein Bündel, das das Element nicht definiert, ist in Vitest nicht verlässlich nachzustellen (geteilte Registry bei `isolate: false`); der Zweig ist gelesen und einfach. |
| 8 | Ohne Gesamtdauer entstanden riesige Balken-Maße (alt: NaN, vom Browser verworfen). | klein | Ohne endliche Dauer werden keine Maße gesetzt. Spec. |
| 9 | Ein Leerzeichen nach „Degradation:“, das Angular weggelassen hatte. | klein | Bewusst so gelassen (lesbarer). |
| 10 | Umweg über `classList.add`. | klein | Klasse direkt. |
| 11 | `widgetTeile` stand in beiden Skripten. | klein | Aus `module-register.mjs` exportiert, im Bau-Skript importiert. |

**Nachtrag zu AS-Ud:** Die ständige Statuszeile von „Meine Vorgänge“ war leer mit `display: none`
versteckt. Das nimmt sie aus dem Zugänglichkeitsbaum; sie ist jetzt leer nur noch ohne Abstand.

**Prüfung nach den Behebungen:**
- Vitest ui 1324; Element-Spec 25, Hüllen-Spec 7.
- Playwright 107/107.
- Skript-Tests 18 / 6 / 4.
- ESLint sauber.
- Budget 186,9 kB gzip, Panel-Bündel 3,9 kB.
