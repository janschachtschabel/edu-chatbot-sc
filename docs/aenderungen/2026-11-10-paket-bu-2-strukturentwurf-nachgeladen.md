# Paket BU-2 — `ui_strukturentwurf` als nachgeladenes Element (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5i (Entscheide BU-d … BU-g).

**Was sich ändert:** Für die Person nichts. Der Strukturentwurf sieht gleich aus und bedient sich
gleich. Er lädt aber erst beim ersten Entwurfsblock als eigenes Bündel nach (wie `ui_upload`,
`ui_strukturabgleich`, `ui_fortschritt`), statt immer im Widget zu stecken.

**Geändert:**
- **Modul** (`ui-module/src/ui-strukturentwurf/`): `laden: "bei_bedarf"`. Die Angular-Komponente
  (`.component.ts/.html`) ist ersetzt durch das Custom Element `boerdi-ui-strukturentwurf`:
  - `entwurf-zustand.ts`: Zustand und Bearbeitung, 1:1 aus der Komponente, ohne DOM. Die
    Bearbeitungen geben einen Fokuswunsch zurück.
  - `entwurf-zeichnen.ts`: die Teile als DOM. Der Baum wird je Punkt **abgeglichen**
    (`BaumZeichner`), nicht neu gebaut. Ein Eintrag bleibt dasselbe Element, sonst ersetzte der
    Fokus beim Mausdruck den Eintrag und der Klick fiele ins Leere; Vorleser sagten den Eintrag nach
    jedem Aufklappen neu an.
  - `ui-strukturentwurf.element.ts`: Eigenschaften nach dem Element-Vertrag, Ereignisse an einer
    Stelle (focus/blur/input im Einfangen), Fokus-Rückholung über `id` bzw. `data-fokus`, Vormerken.
    Während ein Feld bearbeitet wird, bleibt das Detailfeld stehen (Cursor, Eingabemethode).
    `beschaeftigt` schaltet nur den Übernehmen-Knopf. Die Statuszeile bleibt dasselbe Element.
  - `entwurf-symbole.ts`: die zwei Symbole als eigene Konstanten (gleich `ICONS`, per Spec geprüft).
    Ein Import von `ICONS` zöge alle Symbole ins Bündel.
  - `ui-strukturentwurf.element.scss` (vorher `.component.scss`), ergänzt um die Bereiche
    (`display: contents`) und `[hidden]`.
- **Stile nachgeladener Module** (`scripts/module-register.mjs`): Eine `ui-<name>.element.scss`
  wird mit dem dart-sass des Projekts zu `ui-<name>.stil.generated.ts` (`STIL`, eingecheckt).
  `--pruefen` (CI) und ein lokales `build:widget` melden einen veralteten Stand. Der Entwurf teilt damit weiter `_baum/_baum.scss`
  mit dem Themenbaum. Ein Nachbau als Zeichenkette wie beim Upload liefe auseinander.
- **Ansage** (`_baum/ansage-kern.ts`, neu): Die Regel der Statuszeile ist jetzt rahmenlos (gleicher
  Text → leeren, 100 ms, neu setzen). `BaumAnsage` (Themenbaum) ist nur noch die Hülle mit Signal,
  ihr Verhalten bleibt gleich.
- **Tests:**
  - Die Spec der Komponente gilt am Element weiter (`ui-strukturentwurf.element.spec.ts`: dieselben
    Fälle über `shadowRoot`; Tastendrücke mit `composed: true` wie echte).
  - Dazu kommen Fälle für die neue DOM-Strategie: Statuszeile bleibt, Mausklick nach Fokus, Feld
    bleibt beim Tippen, `beschaeftigt` ohne Neuzeichnen, Schlagwort-Feld nach dem Verlassen, Symbole,
    zweites Definieren.
  - Die Shell-Spec `chat-shell-strukturentwurf.spec.ts` definiert das Element vorab und ersetzt den
    Lader; Platzhalter, Element und Vormerken laufen wie im Widget.
  - `module-register.test.mjs` prüft die Stil-Erzeugung.
- **Doku:** `docs/ui-module.md` (Tabelle, §2.5 SCSS) und das README des Moduls.

**Wirkung:**
- `main.js` sinkt von 677,1 auf **645,2 kB roh** und von 195,1 auf **187,4 kB gzip**. Es liegt damit
  unter der Warnschwelle von 190 kB und unter Angulars eigener Budget-Warnung von 650 kB.
- Das neue Bündel `ui-strukturentwurf.<hash>.js` hat 31 kB roh / 10,6 kB gzip.
- Alle nachgeladenen Module zusammen: 36,5 von 60 kB gzip.

**Prüfung:**
- Vitest: ui-module 341, ui 1275, widget 93, studio 2116.
- Playwright e2e 103/103, darunter `strukturentwurf.spec.ts` (Tastatur, Esc, 320 px, getippte
  Nachricht) und die Upload-Fälle.
- `module-register.test` 16, `build-nachlade-module.test` 4, `check-module-budget.test` 4,
  `module:register --pruefen` aktuell.
- Backend-Tests mit Manifest-Bezug: 483.
- ESLint sauber.

**Review (10.11., unabhängig; BU-1 und BU-2 zusammen):** 0 kritisch, 1 schwer, 4 mittel, 3 klein.
Alle Befunde sind behoben, jeder mit Test.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Das Detailfeld blieb bei jedem Neuzeichnen stehen, solange ein Feld aktiv war. Nach „Rückgängig“ (Klick ohne Fokuswechsel, etwa Tippen auf iOS) zeigte es den alten Wert, und der nächste Tastendruck hob das Rückgängig still auf. | schwer | Stehen bleibt es nur beim eigenen Tippen und beim Neusetzen ohne neuen Stand. Sonst wird es aus dem Stand neu gebaut. Spec-Fall. |
| 2 | Der Fokuswunsch nach „Übernehmen“ hing, wenn die Shell die Antwort ablehnte. Eine spätere Statuszeile (veraltet) hätte dem Eingabefeld den Fokus genommen. Die Sperre las den Spiegel statt live `host.beschaeftigt()`. | mittel | Der Wunsch gilt nur dem nächsten Kontext. Die Sperre prüft wieder live. Zwei Spec-Fälle. |
| 3 | dart-sass setzt im komprimierten Modus bei Nicht-ASCII ein BOM vor das CSS, im `<style>` wird es Teil des ersten Selektors (latent). | mittel | `charset: false`. Test. |
| 4 | `sass` war nur transitiv über `@angular/build` vorhanden. | mittel | `devDependency` `sass` 1.104.1 (exakt, wie `@angular/build`). Im Lockfile ändert sich nur die Wurzel. |
| 5 | Es fehlten Fälle für die heiklen Zeichenwege. Das E2E tippte nicht Taste für Taste und prüfte den Fokus auf der Statuszeile nicht. | mittel | Spec-Fälle: Rückgängig bei fokussiertem Feld, Neusetzen beim Tippen (Feld, Wert, Cursor bleiben), kein hängender Fokuswunsch. E2E: Tippen mit dem Cursor in der Mitte, `toBeFocused` auf der Statuszeile. |
| 6 | Eine unbekannte `quelle` zeigte „Entwurf (KI)“, die Komponente zeigte nichts. | klein | Rückfall leer. Spec-Fall. |
| 7 | `zahl` (BU-1) ergab bei einem Wert, der auf Null rundet, „-0.00“, `DecimalPipe` gibt „0.00“. | klein | Ein auf Null gerundeter Wert wird ohne Vorzeichen ausgegeben. Spec-Fall. |
| 8 | Ein lokales `build:widget` prüfte nicht, ob der erzeugte Stil zur SCSS passt (nur die CI tat es). | klein | `build-nachlade-module.mjs` bricht bei veraltetem Stil ab. Von Hand geprüft: Exit 1 mit altem, 0 mit aktuellem Stil. |

Dazu der Hinweis des Prüfers, dass das Rundungsskript für das Logo Zahlen ohne Trenner verschmelzen
könnte. Es betrifft das heutige Logo nicht; im Logo-Kopf steht jetzt eine Warnung für künftige
Updates.

**Prüfung nach den Behebungen:**
- Vitest: ui-module 346, ui 1275, widget 93, studio 2116.
- E2E 103/103.
- `module-register.test` 17, die übrigen Skript-Tests grün, `--pruefen` aktuell.
- ESLint sauber.
- Budget: 645,2 kB roh / 187,4 kB gzip; Modul 10,6 kB gzip.

**Deploy:** Widget-Bündel neu bauen. Das Dockerfile baut das Frontend und kopiert
`dist/widget-module` mit (Z. 115). Keine Migration, keine neue Variable.
