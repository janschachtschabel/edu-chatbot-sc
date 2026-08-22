# frontend — Angular-21-Workspace (zoneless)

Drei Projekte:

| Projekt | Pfad | Rolle |
|---|---|---|
| `ui` | `projects/ui/src` | geteilte Quell-Bibliothek (pfad-gemappt als `@boerdi/ui`, nie publiziert) |
| `widget` | `projects/widget/src` | Custom Element `<boerdi-chat>` + Dev-Harness (P8) |
| `studio` | `projects/studio/src` | Redaktions-SPA, vom Backend unter `/studio` ausgeliefert (P9) |

## Befehle

```bash
npm start          # Widget-Dev-Server auf :4200 (Proxy auf das Backend :8100)
npm run start:studio   # Studio-Dev-Server auf :4300 (gleicher Proxy)
npm run lint       # eslint + angular-eslint (Templates inkl. a11y-Regeln)
npm run check:tokens   # jedes gelesene var(--token) muss definiert sein (s. u.)
npm test           # Unit-Tests: ng test ui && ng test widget && ng test studio
npm run build:widget   # Single-File-Bundle → dist/widget/browser/main.js
npm run build:studio   # Studio-SPA → dist/studio/browser/
npm run budget     # §5.5-Gate: 1 Datei, ≤420 kB raw, ≤140 kB gzip (nur Widget)
npm run e2e        # Playwright gegen das GEBAUTE Bundle
```

### `check:tokens` — warum das ein eigenes Gate ist

Ein `var(--token)` auf einen Namen, den niemand definiert, fällt **nicht** auf
einen Standardwert zurück: die *ganze* Deklaration wird ungültig und verworfen.
`background: var(--st-surface-variant)` rendert dann transparent,
`outline: 2px solid var(--st-focus)` rendert gar keinen Rahmen — ohne Warnung im
Build, im Linter oder in den Tests. Diese Klasse wurde dreimal von Hand gefunden
(`--st-surface-variant` in neun Stylesheets, `--st-mono`, `--st-radius-sm`), also
prüft sie jetzt ein Skript: `scripts/check-tokens.mjs` sammelt alle
`--name:`-Definitionen und alle `var(--name)`-Lesestellen im `projects/`-Baum und
bricht mit Exit 1 ab, sobald eine Lesestelle keine Definition hat. In CI läuft es
als eigener Schritt direkt nach `lint`, damit ein Fehlschlag benennt, welche Regel
gebrochen ist. Das Skript nimmt optional ein Wurzelverzeichnis
(`node scripts/check-tokens.mjs <dir>`), damit die Gate selbst gegen ein Fixture
prüfbar ist — dieselbe Naht wie bei `check-widget-budget.mjs`.

**Bewusste Grenze:** die Definitionen werden über den ganzen Baum gepoolt, nicht
je `@use`-Graph aufgelöst. Das findet „nirgends definiert" (die obige Fehlerklasse)
und nicht „nur in einem Stylesheet definiert, das diese Datei nie lädt".

## Studio

Die SPA läuft unter `/studio` (`baseHref` in `angular.json`) und spricht
ausschließlich mit dem studio-bff auf `/studio/api/*` — Cookie-Gate und
Backend-Key sitzen serverseitig, die SPA kennt keinen Key.

Damit das Backend sie ausliefert, muss `STUDIO_DIST_DIR` auf das Build-Ergebnis
zeigen; fehlt es, wird der Mount übersprungen (Log-Hinweis beim Start, kein
Fehler — Dev und CI laufen ohne Studio-Build):

```bash
STUDIO_DIST_DIR=../frontend/dist/studio/browser uv run uvicorn boerdi.main:app
```

Für die Arbeit an einer View ist `npm run start:studio` bequemer: der Dev-Server
proxyt `/studio/api` und `/api` auf :8100, und Hot-Reload bleibt erhalten.

Neue Views werden in `projects/studio/src/app/studio-views.ts` eingetragen —
diese Registry erzeugt Routen **und** Navigation, damit beide nicht auseinander
laufen können (in ALT taten sie es).

### Generischer Bereichs-Editor (9-3)

„Alle Bereiche“ (`/studio/bereiche`) listet jede Konfigurationsdatei direkt aus
dem Backend; `/studio/bereich/<bereich>` editiert sie — im Formular (aus
`GET /config/schema/{area}` erzeugt) oder im Rohtext (YAML/MD).

Das Formular bearbeitet **eine Kopie des ganzen Dokuments** und schickt es ganz
zurück. Das ist keine Bequemlichkeit: die Bereichsmodelle pinnen nur einen Teil
des Baums (gemessen 357 ungepinnte Pfade in der ALT-Konfiguration), und alles,
was kein Feld anzeigt, muss ein Speichern unverändert überleben. Wer daran
arbeitet:

- `schema-form/schema-to-fields.ts` — rein, Schema → Feldbaum;
- `schema-form/form-value.ts` — rein, unveränderliche Pfad-Operationen;
- `schema-form/schema-form.component.ts` — der einzige Ort, der schreibt.

Nach einer Änderung an einem Bereichsmodell die Test-Fixture neu erzeugen:

```bash
cd backend && uv run python scripts/export_area_schemas.py
```

### Kuratierte Views (9-4)

Die aufgabenbezogenen Konfigurations-Seiten (Begrüßung, Identität & Schutz,
Anzeige …) sind **keine handgeschriebenen Views**, sondern Einträge in
`views/curated-views.ts`: welche Bereiche zu einer Aufgabe gehören, in welcher
Reihenfolge, mit welcher Erklärung. Gerendert werden sie von

- `views/area-section.component` — ein Bereich als `<details>`-Panel; lädt beim
  ersten Öffnen und speichert **nur diesen** Bereich;
- `views/group-section.component` — für `03-patterns` / `04-personas`, wo der
  Schlüssel einen Ordner adressiert: Liste + Editor + „Neu anlegen";
- `views/safety-level.component` — der einzige Sonderregler (§5.6).

**Feld-Reiter im Pattern-Formular (A7).** Ein Pattern-Dokument hat 21
Kopf-Felder plus Anweisungstext; ALT hat sie in fünf Reiter geschnitten, und
diese Gliederung steht als Datentabelle in `views/pattern-field-tabs.ts`
(`feature: 'pattern-tabs'` schaltet sie an). Technisch ist das **ein Ausschnitt,
kein zweites Formular**: `schema-form/pick-fields.ts` reduziert den Feld-Baum
auf die Pfade eines Reiters, `SchemaFormComponent` nimmt sie als
`visiblePaths`. Geschrieben wird weiterhin das ganze Dokument, und der Hinweis
auf unbekannte Schlüssel rechnet weiter über den vollen Baum — sonst meldete
jeder geschlossene Reiter seine eigenen Felder als unbekannt.

Zwei Regeln halten den Schnitt ehrlich: ein Feld, das die Tabelle nicht kennt,
landet im Reiter „Weitere" (ALT ließ drei Felder in **keinem** Reiter und damit
unerreichbar), und ein Reiter ohne Felder wird weggelassen. Ein Feld mit
kaputtem JSON nennt im Sperrhinweis seinen Reiter — sonst suchte man ein
gesperrtes Speichern in fünf Reitern.

Eine neue Seite braucht damit einen Eintrag in `studio-views.ts` (Route + Navi)
und einen in `curated-views.ts` — kein neues Formular. Die Specs prüfen, dass
jeder genannte Bereich existiert, dass Ordner-Bereiche als `kind: 'group'`
markiert sind und dass kein Bereich auf zwei Seiten liegt.

Ein Abschnitt ist entweder ein **Konfigurationsbereich** (`area`) oder ein
**Panel** (`panel`) — Letzteres für alles, was kein Schema-Formular sein kann.
„Wissen" (9-4e) hat drei davon: `rag-areas` (Bereiche + Dokumente aus der DB),
`rag-ingest` (Datei/Webseite/Text einlesen) und `mcp-registry`. Die MCP-Registry
läuft bewusst über `/config/mcp-servers` statt über den generischen
Bereichs-Editor: nur dort reichert das GET die Werkzeug-Beschreibungen des
laufenden Servers an, und nur dort greift der SSRF-Check beim Schreiben.

> Ein neuer `panel`-Wert braucht auch ein `@case` in
> `curated-view.component.html`. Fehlt es, rendert der Abschnitt **gar nichts** —
> auch Überschrift und Hinweis. Eine Spec nagelt das fest.

### Dashboards (9-5)

Die lesenden Views teilen sich zwei Bausteine — wer eine neue baut, nimmt beide:

- `core/async-data.ts` — ein `AsyncData<T>` hält Wert, `loading` und `error`
  einer Leseoperation. Zwei Eigenschaften sind nicht verhandelbar und deshalb
  hier statt in jeder View: ein **fehlgeschlagener Refresh behält den letzten
  guten Wert** (eine leer gewordene Tabelle behauptet, es gebe nichts), und eine
  **Generations-Wache** lässt die neuere Anfrage gewinnen, egal in welcher
  Reihenfolge die Antworten eintreffen.
- `views/async-state.component` — rendert genau die drei Zustände neben „hier
  sind die Daten": lädt / fehlgeschlagen (+ „Erneut versuchen") / leer, in
  dieser Reihenfolge. Der `emptyText` gehört der aufrufenden View, weil nur sie
  weiß, wie etwas hierher kommt.

Die Happy-Path-Tabelle steht daneben im View-Template, nicht im Baustein —
Zustände sind gemeinsam, Spalten nicht.

**Eine View, mehrere Endpunkte:** ein `AsyncData` je Endpunkt, nicht eines für
die ganze Seite. „Safety-Logs" (9-5b) liest Liste und Kennzahlen getrennt, weil
sie getrennt scheitern können — und weil `/safety/stats` serverseitig immer das
ganze Fenster aggregiert, lädt ein Filterwechsel dort nur die Liste neu. Dass
die Zahlen nicht dem Filter folgen, steht als Satz in der View: eine Zahl, die
anders gemeint ist als sie aussieht, muss sich erklären.

**Wenn das Backend still korrigiert, zeigt die View das Korrigierte.** „Lasttest"
(9-5e) ist der einzige Knopf im Studio, der echte LLM- und MCP-Anfragen auslöst,
und `validate_profile` klemmt ohne Rückmeldung (Parallelität > 32, Stufen > 6,
Requests/Stufe > 60). `views/loadtest-profile.ts` rechnet deshalb das **effektive**
Profil und benennt jede Änderung, statt die eingetippten Zahlen zu bestätigen —
sonst kündigt die Oberfläche einen Lauf an, den es so nicht gibt. Die vier Grenzen
sind hier gespiegelt und mit ihrer Quelle kommentiert; kein Endpunkt liefert sie.

Laufende Dinge werden mit einer `setTimeout`-Kette nachgelesen, nicht mit
`setInterval` (eine langsame Antwort darf keine zweite Anfrage stapeln), der
Timer hängt an `DestroyRef`, und ein **fehlgeschlagener Poll wird sichtbar**:
ein stiller `catch` lässt ein totes Backend beliebig lange „läuft" behaupten.

**Eine Kennzahl, die sich nicht ändern kann, wird nicht angezeigt.** In „Analyse"
(9-5c) fehlen drei ALT-Anzeigen, weil die Felder dahinter strukturell konstant
sind: `phase2_scores` trägt seit Welle E v4 genau einen Eintrag, also erreicht
`obs/quality_events.py` seinen `len(...) >= 2`-Zweig nie — `phase2_runner_up` ist
immer `''`, `phase2_score_gap` immer `0.0`, `phase2_winner_score` immer `1.0`.
`/quality/tight-races` filtert auf einen echten Runner-up und kann daher für keine
Datenlage etwas liefern; die API-Klasse hat bewusst **keine** Methode dafür, und
ein Test hält das fest. Eine Kachel mit permanenten 0,000 sieht aus wie eine
Messung — statt sie stillschweigend zu entfernen, sagt ein Satz unter den
Kennzahlen, warum sie fehlt.

**Was nur im Tooltip steht, existiert für Tastatur und Touch nicht.** Die
Routing-Matrix ist die dichteste Fläche im Studio; in ALT war jede Zelle ein
`<td onClick>` (ohne Maus unerreichbar) und die konkurrierenden Patterns standen
ausschließlich in `title=`. Hier ist jede belegte Zelle ein `<button>`, der
Persona, Intent, Gewinner, Anteil, Stichprobenzahl **und** die Alternativen als
Text trägt. Farbe kodiert nichts: ALTs Hash-auf-Farbton (`hsl(hash % 360, …)`)
mal `opacity: 0.55 + 0.45*share` kann weder 3:1 für eine bedeutungstragende
Fläche noch 4,5:1 für den Text darauf halten — und kodierte nur, was in der Zelle
schon geschrieben steht.

**Ein Filter, der bei jedem Tastendruck lädt, lädt meistens umsonst.** ALTs
Quality-View baute ihr `load()` aus den drei Filtertexten und rief es aus einem
`useEffect`: fünf Requests pro Zeichen, davon vier an Endpunkte, die nur `scope`
annehmen. Das Log-Panel benutzt jetzt ein echtes `<form>` — Enter-to-Submit kommt
von der Plattform, ein Debounce-Timer entfällt, und pro Absicht geht genau eine
Anfrage raus. Die Filter selbst liegen in der Hülle, nicht im Panel: ein
Drill-down aus Matrix oder Diagnose muss in denselben Feldern landen, die man
danach bearbeitet.

Tabs: ein Panel-Element liegt **immer** im DOM, weil `aria-controls` auflösen
muss; sein Inhalt entsteht beim ersten Besuch und bleibt dann stehen. ALT war
auch lazy, lud aber bei jedem Tab-Wechsel neu, weil sein Effekt am aktiven Tab
hing.

Zahlen und Datumsangaben laufen über `core/format.ts`. Das Studio registriert
kein `LOCALE_ID`, Angulars `DecimalPipe`/`DatePipe` würden also en-US formatieren
(„0.81", „7/24/2026") — deshalb gibt jede Stelle `de-DE` selbst an, und diese
Konvention liegt jetzt an einem Ort statt in sechs Kopien.

### Diagramme (Lasttest, Evaluation)

Die Geometrie liegt in reinen Funktionen (`views/loadtest-chart.ts`,
`views/trend-chart.ts`), damit sie ohne DOM testbar ist. Zwei Regeln, die aus
Fehlern stammen:

- **Ein einzelner Punkt sitzt in der Mitte**, nicht bei `index / (length - 1)`.
  Bei einer Serie mit einem Eintrag ist dieser Divisor 0, jede Koordinate wird
  `NaN`, und SVG zeichnet dann gar nichts — ein leeres Kästchen ohne Fehler.
- **Raten haben eine feste 0..1-Achse.** Die vier Trend-Diagramme stehen
  nebeneinander, um verglichen zu werden; skaliert jedes auf sein eigenes
  Maximum, sieht eine 2-%-Serie aus wie eine 90-%-Serie. Scores skalieren
  dagegen auf den höchsten vorhandenen Wert, weil ihr Deckel nicht garantiert
  ist.

Ein Wert, der fehlt, wird **nicht** als 0 gezeichnet: ein Lauf ohne
`avg_score` wurde nie bewertet, und ein Punkt auf der Nulllinie behauptet
etwas anderes. Er fehlt im Diagramm und steht als „–" in der Tabelle.

Für Screenreader gilt in beiden Ansichten dieselbe Aufteilung: das `<svg>` ist
`role="img"` mit einer gesprochenen Zusammenfassung (aktueller Wert **und**
Richtung), und die echte `<table>` darunter ist die zugängliche Quelle für jede
Zahl. Das Diagramm ergänzt, es trägt nichts allein.

### Knöpfe, die Geld kosten (Lasttest, Eval-Start)

Zwei Flächen lösen echte LLM- und MCP-Aufrufe aus. Beide folgen denselben
Regeln, und beide sind das Gegenteil eines `confirm()`:

- **Zwei Schritte, nicht einer.** Beim generativen Eval holt der erste Knopf
  („Kosten prüfen") `POST /eval/estimate` und öffnet damit die Rückfrage; erst
  der zweite startet. So ist das Kosten-Band nicht überspringbar und kostet
  genau eine Anfrage — nicht eine je Tastendruck.
- **Die Zahl auf dem Schirm ist die Zahl, die läuft.** Der Lasttest rechnet das
  effektive Profil vor, weil sein Backend still deckelt; der Eval-Start klemmt
  1…10 lokal, weil das Backend dort mit 422 antwortet und kein Feld nennt.
- **Nur einer gleichzeitig.** Beide Backends erlauben einen Lauf und antworten
  sonst 409. Woher der Zustand kommt, ist die Pointe: aus der **Liste**, die
  ohnehin pollt — nicht aus einem zweiten Leser desselben Endpunkts und nicht
  aus dem gerade geöffneten Lauf (ALTs Fehler, siehe 9-5e).
- **Eine gescheiterte Schätzung blockiert den Start nicht**, aber die Rückfrage
  sagt dann „ohne Kostenschätzung" statt einen Preis anzudeuten.

### Evaluation (9-5d, drei Tabs)

`views/evaluation.component` ist die Hülle: **Läufe** (zwei Start-Formulare, die
Liste, das Lauf-Detail), **Trends** und **Pattern-Nutzung**. Die Start-Formulare
sitzen bewusst über der Liste statt in eigenen Tabs — ein Lauf braucht Minuten und
die Liste ist seine einzige Fortschrittsanzeige.

Das Lauf-Detail **pollt nicht**, anders als das Lasttest-Detail: seine Antwort
trägt die vollständigen Transkripte, und die alle paar Sekunden neu zu holen,
um eine Fortschrittszeile zu lesen, würde Megabyte bewegen. Ein laufender Lauf
wird deshalb „Momentaufnahme" genannt und hat einen „Aktualisieren"-Knopf.

Die Gold-Scorecard rechnet nichts nach, was der Server schon liefert
(`golden_metrics.per_flow`); die reine Gruppier- und Quoten-Logik liegt in
`views/gold-scorecard.ts`, damit sie ohne DOM prüfbar ist. „Link-Host" bleibt ein
**weicher** Check und steht neben der harten Quote, nicht darin — eine falsch
gesetzte `REPO_BASE_URL` lässt ihn für jeden Turn scheitern, ohne etwas über den
Bot zu sagen.

### Zwei geteilte Bausteine statt Handkopien (B3, B4)

`views/_visually-hidden.scss` liefert `.sr` für Text, den nur Screenreader lesen —
seit B3 die einzige Kopie der Regel (vorher neunmal in acht Stylesheets, zweimal
davon nicht als Utility-Klasse, sondern direkt auf einem `<thead>` und einem
Hinweis-`<span>`; darum ging das Zählen nach Klassennamen nie auf). Neue
Stylesheets nutzen die Partial (`@use './visually-hidden'`).

`views/tab-bar.component` ist die einzige Reiterleiste; seit B4 nutzt sie auch der
Bereichs-Editor. Dabei kam eine Regel dazu, die vorher niemand brauchte: die
Leiste fokussiert nach einem Pfeiltastendruck **den tatsächlich aktiven** Reiter,
nicht den angefragten. Der Bereichs-Editor **lehnt** den Wechsel bei
ungespeicherten Änderungen ab, und ein fokussierter Reiter mit
`aria-selected="false"` würde einen Panel-Wechsel ansagen, den es nicht gab. Das
passiert in `afterNextRender`, nicht in einem Microtask: `active` ist ein Input und
trägt die Antwort des Aufrufers erst nach der Change Detection.

### Rückfragen sagen sich an (B6)

Jede Inline-Rückfrage („Wirklich löschen?") erscheint **unter** dem Knopf, der sie
ausgelöst hat, und der Fokus wandert nicht mit. Ohne Live-Region erfährt ein
Screenreader also nichts, bevor der zweite Klick die Aktion auslöst
(WCAG 2.2 SC 4.1.3). `role="alert"` trägt deshalb **die Frage, nicht den
Container**: läge es außen, würde jedes Umschalten eines Knopf-Labels auf „Wird
gelöscht …" die ganze Rückfrage erneut vorlesen. Beim generativen Eval-Start ist
es `aria-live="polite"` statt `alert`, weil der Text dort eine Kostenschätzung ist,
die vom Server eintrifft — keine Antwort auf einen Klick.

### Der Lasttest misst keine Ressourcen (B5)

Das Backend hat ALTs psutil-Abtastung nicht portiert (`services/loadtest.py`:
`resource_samples` bleibt `[]`, `_summary` liefert vier Schlüssel). Die Ansicht
zeigte trotzdem „Spitze NaN MB" in der Liste und „Spitzenwerte: NaN MB RSS,
NaN % CPU" im Detail — der Typ `RunSummary` erklärte die Felder als vorhanden, und
die Test-Fixtures erfanden Werte dafür, deshalb fiel es weder dem Compiler noch
der Suite auf. Jetzt nennt die Ansicht, was sie **nicht** messen kann; kommen
CPU/RSS-Werte zurück, kommen Anzeige und Sparkline gemeinsam mit ihnen.

### Übersicht (9-5f, Startseite + Architektur-Referenz)

`views/overview.component` ist die Startseite (`DEFAULT_VIEW`) und hat zwei Tabs —
**Übersicht** und **Architektur & Referenz** —, wie ALTs Home-View. Die
Navigations-Karten sind `<a routerLink>`, keine Knöpfe: Mittelklick und „in neuem
Tab öffnen" funktionieren, und der Screenreader sagt „Link".

Zwei Regeln für die Kacheln:

- **Zahlen nur, wenn gemessen.** Patterns/Personas/Intents/States/Entities/Signale
  kommen aus `GET /config/elements`. Solange nichts geladen ist, steht **keine**
  Zahl da. ALT füllte die Lücke mit `?? 16`, `?? 6`, `?? 8` … — sechs Angaben, die
  wie Messwerte aussahen und beim fehlgeschlagenen Request stehen blieben.
- **Der Werksstand zeigt, was NEU hat.** ALT las `size`, `mtime`, `has_db` und
  `config_files` aus einer Datei; in NEU ist ein Snapshot eine Zeile in
  `config_snapshots` und `GET /config/factory` antwortet
  `{exists, created_at, label}`. Ein wörtlicher Port hätte drei Gedankenstriche
  und ein falsches „0 Configs" gemalt.

Kein Offline-Banner: der Shell-Header pollt `/health` und besitzt diesen Zustand
(`shell/status-indicator.component`); jedes Panel meldet seinen eigenen Fehler.
Auch keine Schnellzugriffs-Leiste — zwei ihrer drei Knöpfe verdoppelten Karten
derselben Seite, der dritte zeigte auf die Sicherung, die seit 9-6 eine eigene
Betriebs-Karte hat.

Die Referenz (`views/architecture-reference.component`) nutzt natives
`<details>`/`<summary>` samt `_section-shell.scss`, statt ALTs `useState(open)`
nachzubauen: tastaturbedienbar, als aufklappbar angekündigt und selbst zugeklappt
von der Seitensuche findbar. Die langen Zeilen liegen in `views/reference-data.ts`.

**Zwei Abschnitte lesen statt behaupten (A5-Rest).** Die Signal-Tabelle kommt aus
`/config/elements` (die Startseite holt die Nutzlast ohnehin und reicht sie
weiter — ein zweiter Request ließe die zwei Hälften einer Seite auseinanderlaufen),
die Material-Typen aus `/config/data/05-canvas/material-types`. Das ist keine
Bequemlichkeit, sondern die Antwort auf einen gemessenen Befund: ALTs abgetippte
Fassungen genau dieser zwei Listen waren gedriftet — vier Signal-Zeilen schlicht
falsch (`effizient` „mittel" statt `kurz`, `vertrauend` „keine Overrides" statt
`empfehlend`/`mittel`, `vergleichend` „sachlich" statt `analytisch`,
`delegierend` „kurz" statt `mittel`/`proaktiv`), fünf weitere ließen eine
gesetzte Flagge weg, und die Material-Liste ließ `Vokabelliste` ganz aus, sodass
zwölf echte Typen unter der Überschrift „Didaktisch (13)" standen.

Ebenfalls am Code geprüft und korrigiert: die „Konfliktregeln" („kürzere Länge
gewinnt") gibt es nicht — `pattern_engine.py` schreibt die Modulationen
nacheinander, das **letzte** Signal gewinnt; `reduce_items_signals` **deckelt**
`max_items` auf 3 statt zu halbieren; der MCP-Server stellt **zwölf** Werkzeuge
bereit, nicht zehn (`query_knowledge` ist der RAG-Einstieg, kein MCP-Werkzeug);
und RAG liegt in Postgres mit pgvector, nicht in SQLite-Vec.

**`widget-contract-data.ts` ist ein Zwilling, kein Kommentar.** Die 19
Host-Attribute von `<boerdi-chat>` stehen dort als Tabelle; die Wahrheit sind die
Inputs von `WidgetComponent`. Der Test
`widget.component.spec.ts → „hat genau diese 19 Host-Attribute"` pinnt den Satz und
nennt diese Datei, wenn er bricht — ein dokumentiertes Attribut, das seinen
Konsumenten nie erreicht, ist hier schon zweimal passiert (`data-position` 8-5,
`inline-result-grouping` 8-7). ALTs Tabelle listete 17 und ließ genau das
kaputte weg. `language` kam mit C1-c dazu.

### Sicherung (9-6, Snapshots + Werksstand + Voll-Backup)

`views/backup.component` ist **eine View, kein Header-Dialog.** ALT hing das an
drei Header-Knöpfe und ein `<div>`-Overlay. Ein originalgetreues Modal hieße
`<dialog>.showModal()` — und jsdom 29.1.1, die Testumgebung des Studios,
implementiert `HTMLDialogElement` mit **ausschließlich** der Eigenschaft `open`:
kein `showModal`, kein `close` (vor der Entscheidung nachgemessen). Gerade die
wertvollen Eigenschaften eines Modals — Fokusfalle, Esc, inerter Hintergrund —
kann ein Stub nicht belegen. Also Route statt Modal: verlinkbar, in der
Seitenleiste auffindbar, ohne handgebaute Fokusfalle. Die Platzierung ist
UI-Idiom, kein Vertrag — dieselbe Kategorie wie `<div onClick>` → `<button>`.

**Was ein Snapshot hier enthält, entscheidet, was die Oberfläche verspricht.**
ALTs Snapshots trugen die SQLite-Datei; deshalb hatte ALT eine Checkbox
„Datenbank einschließen", ein „+ DB"-Abzeichen je Zeile und Warnungen, dass
Sessions, Memory, Quality-Logs und RAG-Chunks ersetzt werden. In NEU packt
`create_snapshot` die Config-Bereiche und sonst nichts (`include_db` wird nie
gesetzt, der Postgres-Dump ist auf P10 vertagt) — alle drei wären falsche
Zusagen und sind nicht portiert. Ein Test prüft das in **beiden** Zuständen,
leer und gefüllt: der Leertext beschreibt, was gesichert wird, und ist genau die
Stelle, an der die Zusage zurückkäme.

Ebenfalls ohne Gegenstück in NEU und deshalb nicht angeboten: ALTs
wipe/merge-Frage (`_apply_config` merged immer) und „Snapshot als Factory
übernehmen" (`save_factory` kennt kein `from_snapshot`, es packt immer den
Live-Stand).

Alles, was etwas zerstört, fragt zurück — inline, wie seit 9-5a überall; die
Rückfrage trägt `role="alert"`, weil sie unter dem Knopf erscheint, der Fokus
nicht wandert und ein Screenreader sonst gar nichts hört. Der einzige Knopf ohne
Rückfrage ist der Download.

**Downloads werden geholt, nicht angesurft.** ALT setzte `window.location.href`;
ein 404 ersetzte damit das ganze Studio durch rohes JSON. `StudioApi.blob()` holt
die Bytes, `core/download.ts` reicht sie an den Browser weiter, und der
Fehlertext des Backends („Kein Factory-Stand gesetzt") landet in der Meldezeile —
dafür wird der Fehler-Body eigens aus dem Blob gelesen.

Neu und geteilt: `core/action-state.ts` (der Schreib-Zwilling zu `AsyncData`:
welche Aktion läuft, was sie gemeldet hat — ein Signal statt `ok`/`error`, damit
„beides gesetzt" nicht darstellbar ist) und `views/_ops-panel.scss` für die drei
Panels.

### Vorschau (9-6, das echte Widget im Studio)

`views/widget-preview.component` bettet `<boerdi-chat>` ein — **das Element aus
diesem Workspace**, dynamisch importiert über `core/widget-element-loader.ts`.
Nicht über `<script src="/widget/boerdi-widget.js">`: diese Backend-Route ist
noch ein P7-Stub (501), und selbst fertig wäre sie das *ausgelieferte* Bündel und
damit die Quelle der Fehlerklasse „Studio neu, Widget alt". Der Import steckt
hinter einer DI-Naht, weil er eine zweite Angular-Anwendung startet
(`createApplication`) — in jsdom nicht zu haben; die Tests ersetzen die Naht.

Vier Attribute weichen bewusst vom Default ab: `auto-context="false"` (sonst
sammelt das Widget Pfad, Titel und DOM-Text der *Studio*-Seite ein und schickt
sie als Besucher-Kontext), `persist-session="false"` (sonst setzte jede Vorschau
das Gespräch von gestern fort), `initial-state="expanded"` und `api-url` = eigene
Herkunft. Das Widget wird **nicht** in einen Rahmen gesperrt: sein `:host` ist
`position: fixed`, ein eigener Enthaltungsblock würde eine Anordnung zeigen, die
es auf keiner echten Seite gibt.

Der Seitenkontext ist ein Formular mit **genau drei** Typen — Themenseite,
Sammlung, Inhaltsseite. Das ist `_GREETABLE_KINDS` aus
`graph/nodes/context_greeting.py`; `subject` und `search` lösen weder Begrüßung
noch Pills aus und stehen deshalb nicht zur Wahl. Übernommen wird beim Absenden,
und jedes Absenden erzeugt das Element neu — der Konfigurations-Boot läuft nur
beim Verbinden.

Preis der Workspace-Naht, gemessen: das Initial-Bündel wächst um **25 kB**
(269,95 → 295,13 kB raw) durch zurückbehaltene Framework-Pfade; Widget-Code
liegt nachweislich nicht darin, das Widget selbst bleibt ein Lazy-Chunk (252 kB).

## E2E

Die Specs in `e2e/` fahren das **ausgelieferte Bundle** in echtem Chromium, nicht
die Quellen. Deshalb gilt:

```bash
npm run build:widget && npm run e2e
```

Ohne vorherigen Build bricht die Suite mit einem Hinweis ab — und nach einer
Quell-Änderung testet ein alter Build weiter das alte Verhalten.

Host-Seite und Backend werden von Playwright selbst ausgeliefert
(`e2e/fixtures/harness.ts`, `page.route`): kein Port, kein Compose, keine
Backend-Instanz. Das erlaubt auch beliebige Seiten-URLs, sodass der
Seitenkontext-Detektor über eine realistische WLO-URL gefahren werden kann.

Einmalig nötig: `npx playwright install chromium`.

Ein voller Lauf gegen `deploy/compose.dev.yml` bleibt eine **Live-Prüfung** —
die Antworten kommen dort aus dem LLM und sind nicht deterministisch.

Spec: [docs/plans/2026-07-10-boerdi-chat-neubau.md](../docs/plans/2026-07-10-boerdi-chat-neubau.md), §5.5 (Widget-Vertrag), §5.6 (Studio), §7 (Architektur).
