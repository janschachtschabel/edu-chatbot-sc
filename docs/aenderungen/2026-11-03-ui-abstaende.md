# Änderungsnotiz — Senkrechte Abstände der UI-Module

Stand 2026-11-03 · nur Frontend (Stile der UI-Module + E2E-Messungen), kein Backend

**Warum:** Rückmeldung zum Entscheidungs-Modul im Widget: „bei den widgets sollte der abstand vom
text (Frage) zur ersten Option etwa so groß sein wie von Option 1 zu Option 2 - prüfe die
vertikalen abstände bei den ui widgets.“ Die Frage klebte an der ersten Möglichkeit, die
Möglichkeiten standen weit auseinander.

**Wie gemessen:** neuer Messer `frontend/e2e/fixtures/abstaende.ts` — sichtbarer Weißraum zwischen
Textzeilen (Glyphen-Kanten je Textknoten über `Range.getClientRects()`), nicht der Abstand der
Zeilen-Boxen. Toleranz „etwa gleich“: 3 px. Je Modul ein Test „Rhythmus“ im bestehenden E2E-Spec,
Entscheidung, Themenbaum und Linkbox zusätzlich bei 320 px Breite. Alle Werte in px, Chromium,
gleich bei 1280 und 320 px (Ausnahme vermerkt).

| Modul | Strecke | vorher | nachher |
|---|---|---|---|
| `ui_entscheidung` Einzelwahl | Frage → 1. Möglichkeit | **5,3** | 15,3 |
| | Möglichkeit → Möglichkeit | **25** | 16 |
| `ui_entscheidung` Mehrfach + Hinweise + Freitext | Frage → Anleitung | 1,3 | 7,3 |
| | Anleitung → 1. Möglichkeit | 11,5 | 15,5 |
| | Möglichkeit (mit Hinweis) → Möglichkeit | **11** | 15 |
| | letzte Möglichkeit → „Eigene Ergänzung“ | **27** | 16 |
| | Label → Feld / Feld → Knopf | 7,5 / 8 | 7,5 / 8 |
| `ui_themenbaum` | Überschrift → 1. Eintrag / Eintrag → Eintrag (auch Eltern ↔ Kind) | 14,1 / 15 | unverändert |
| | Höhe Knöpfe / Link „In WLO öffnen“ | **32 / 42** | 32 / 32 |
| | Zielname → Knöpfe | 12,4 (320 px: 7,4) | 7,4 |
| `ui_inhaltsrahmen` | Titel → Inhalt (Linkbox daneben: 9,7) | **16,9** | 7,8 |
| `ui_linkbox` | Überschrift → 1. Link / Link → Link | 9,7 / 6,1 | unverändert |
| `ui_trefferliste` | Sammlungs-Box wie Linkbox; Material-Box Überschrift → 1. / Treffer → Treffer | 9,7 / 6,1; 12,1 / 11 | unverändert |

## Was sich ändert

| Modul | Ursache | Änderung |
|---|---|---|
| Entscheidung | Die Frage ist eine `<legend>` — kein Flex-Kind des Fieldsets, der `gap` (6 px) griff unter ihr nicht. Die Zeilen hatten `min-block-size: 32px` im `content-box`-Modell (Zeile also 40 px), einzeilige Möglichkeiten standen dadurch weiter auseinander als solche mit Hinweis | `legend`: `margin-block-end: 6px`; Möglichkeiten-Liste: `margin-block-start: 2px` (ihr Zeilenabstand auch vor der ersten). Zeile: `box-sizing: border-box`, Polster 6 px statt 4 px, Untergrenze 24 px (WCAG 2.5.8) — Zeilenhöhe gemessen 31 px statt 40 px (einzeilig), mit Hinweis 47,4 px |
| Themenbaum | Der Link „In WLO öffnen“ (`<a>`) rechnete `min-block-size` im `content-box`-Modell, `<button>` im `border-box`-Modell (Browser-Vorgabe) | `.ui-themenbaum__knopf`: `box-sizing: border-box` |
| Inhaltsrahmen | Der Markdown kommt per `[innerHTML]` ohne `_ngcontent`-Attribut — **keine** der Inhaltsregeln griff (auch nicht „erstes Kind ohne Rand oben“). Der Browser-Rand der Liste (1em) schob den Inhalt unter die Kopfzeile; Überschriften standen in Browsergröße (h1 26 px) | Inhaltsregeln unter `::ng-deep` (wie `ui/src/markdown/_markdown-content.scss`). **Sichtbare Folge über den Abstand hinaus:** Überschriften als fette Zeile (1,06em), Absätze/Listen mit 0,3em statt 1em Rand, Listen-Einzug 1,3em statt 40 px, `code`/Zitat/Link wie in der Datei vorgesehen — so, wie die Stile es seit dem ALT-Port beschreiben |
| Linkbox, Trefferliste | Die Überschrift stand 3,6 px lockerer als die Links untereinander — Rand unter der Überschrift 4 px im geteilten Partial `ui/src/grouping/_result-group.scss` | Entscheid des Nutzers (2026-11-03): Rand 4 → 2 px. Trifft Linkbox, Trefferboxen und Schwimmlinien gleich. Der Test prüft wieder streng ±3 px, Linkbox und Trefferbox gleich |

Studio-Vorschau: zeigt dieselben Komponenten, ändert sich also mit.

**Entschieden (Nutzer, 2026-11-03):** Überschrift → erster Link auch in den Trefferboxen angleichen —
`margin-bottom` von `.result-group__heading` 4 → 2 px im Partial (erwartet 7,7 / 6,1,
Material-Box 10,1 / 11); trifft alle Trefferboxen, Schwimmlinien und die Linkbox gleich.

## Prüfung

E2E neu: 10 Tests „Rhythmus“ (4 `entscheidung`, 2 `themenbaum`, 2 `linkbox`, 1 `trefferliste`,
1 `inhaltsrahmen`), vor der Änderung 9 rot (Trefferliste grün, nur Messung). Die zwei
Linkbox-Tests prüfen streng ±3 px (vorher rot mit 9,7 / 6,1, nach dem Partial-Entscheid grün). Ganzer Lauf
79 bestanden, die Rhythmus-Tests mit `--repeat-each 10` 100 bestanden; nach dem Partial-Entscheid erneut 79 bestanden, Rhythmus `--repeat-each 5` 50 bestanden, `ng test ui` 1101 bestanden. `ng test ui-module` 93
bestanden; eslint auf den berührten Dateien sauber; `check:tokens`, `check:a11y`,
`check:contrast`, `check:radii` sauber. Bündel 615,38 kB roh / 179,94 kB gzip (Budget eingehalten).

## Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Widget | Bündel neu bauen und ausliefern (`npm run build:widget`; Kopien neu verteilen) | |
| Backend, Datenbank, Umgebung | nichts | |
