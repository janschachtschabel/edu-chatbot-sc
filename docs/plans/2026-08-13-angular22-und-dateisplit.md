# Plan: Angular-22-Migration + Zerlegung der fünf größten Backend-Dateien

**Datum:** 2026-08-13 · **Auslöser:** Audit 2026-08-12 (F-2-Rest: Dev-Baum-CVEs nur per
Major-Sprung behebbar; F-8: 47 Dateien über der ≤300-Zeilen-Regel) · **Status:** Paket A
geprüft und freigegeben, Paket B braucht eine Entscheidung (siehe §B.2).

---

## Paket A — Angular 21.2.19 → 22

### A.0 Warum

Der Dev-Baum trägt 6 CVEs (3 moderate, 3 high), alle über `@angular-devkit/build-angular`.
Sie werden nicht ausgeliefert, aber der einzige Fix ist der Major-Sprung. Dazu kommen die
Verbesserungen von v22 (OnPush als Default, TypeScript 6, stabile Signal Forms).

### A.1 Risikoprüfung — Ergebnis: **grün, mit drei Restrisiken**

Breaking-Change-Liste aus dem offiziellen CHANGELOG (angular/angular, 22.0.0), Abgleich gegen
`frontend/projects/**` ohne Spec-Dateien:

| Breaking Change (v22) | Treffer bei uns | Bewertung |
|---|---:|---|
| `ComponentFactoryResolver` / `ComponentFactory` entfernt | **0** | — |
| `createNgModuleRef()` entfernt | **0** | — |
| `ChangeDetectorRef.checkNoChanges()` entfernt | **0** | — |
| `provideRoutes()` entfernt | **0** | — |
| Hammer.js-Integration entfernt | **0** | — |
| HTTP: XHR-Upload-Fortschritt entfernt (`reportProgress`) | **0** | — |
| `withFetch()` entfernt (Fetch ist Default) | **0** | — |
| `CanMatchFn`: `currentSnapshot` jetzt Pflicht | **0** | — |
| `TitleStrategy.getResolvedTitleForRoute()` Rückgabetyp | **0** | — |
| Forms `min`/`max` ohne String-Werte | **0** | — |
| Animationen (`@angular/animations`, Leave-Animations) | **0** | — |
| `appRef.bootstrap` zweites Argument | **0** | — |
| `data-`-Attribute binden keine Inputs/Outputs mehr | **0** | 2 Treffer sind CSS-Selektor-**Strings** in `page-context-detector.ts:244,248`, keine Template-Bindings |
| **OnPush wird Default** (`Default` → `Eager` umbenannt) | **65 von 66** Komponenten setzen `changeDetection` bereits explizit | Die eine Ausnahme ist `studio/…/quality-logs.harness.ts` — ein **Test-Harness**, keine ausgelieferte Komponente |
| `paramsInheritanceStrategy` Default `emptyOnly` → `always` | **0** (nicht gesetzt) | Studio-Routen sind flach (ein Slug je Ansicht), Vererbung greift nicht |

**Umgebung:**

| Anforderung v22 | Unser Stand | |
|---|---|---|
| Node ≥ 22 | lokal v22.14 · `Dockerfile: node:22-slim` · `ci.yml: node-version: 22` | ✅ |
| TypeScript ≥ 6.0 | **`~5.9.0`** → muss auf `~6.0.0` | ⚠️ mitzuziehen |
| `typescript-eslint` mit TS 6 | 8.67.0 peert `typescript >=4.8.4 <6.1.0` | ✅ deckt 6.0.3 |
| `angular-eslint` v22 | 22.1.0 verfügbar, peert `@angular/cli >=22 <23` | ✅ |
| Verfügbarkeit | core 22.1.1 · material/cdk 22.1.2 · cli/build 22.1.3 | ✅ |
| Test-Builder | bereits `@angular/build:unit-test` (Vitest) | ✅ kein Karma→Vitest-Umbau nötig |

**Die drei Restrisiken** — nicht vorab entscheidbar, nur durch den Lauf:

1. **Neue Template-Diagnosen.** v22 aktiviert `optionalChainNotNullable` und
   `nullishCoalescingNotNullable`: ein `?.` oder `??` auf einem Ausdruck, der gar nicht
   nullable ist, wird gemeldet. Bei uns: **36×** `?.` und **9×** `??` in Templates. Erwartung:
   einige Meldungen, jede einzeln zu prüfen (echte Redundanz entfernen, sonst Typ schärfen).
2. **Semantik von `?.` geändert.** `a?.b` liefert jetzt `undefined` statt `null`, wie in
   TypeScript. Wo wir im Template gegen `null` vergleichen, kann sich Verhalten ändern. Die
   Migration kann Ausdrücke in `$safeNavigationMigration()` einpacken; **das wollen wir nicht**
   dauerhaft — lieber die wenigen Stellen richtig lesen.
3. **Bundle-Größe.** v22 schaltet die Chunk-Optimierung standardmäßig ein
   (`NG_BUILD_OPTIMIZE_CHUNKS`). Das Budget-Gate steht bei 528,09 kB / 600 kB (88,0 %) — es
   kann in beide Richtungen ausschlagen. §5.5 ist ein hartes Gate.

**Zusätzlich mitzuziehen (kein Angular-Thema, aber derselbe Lauf):** TypeScript 5.9 → 6.0 hat
eigene Breaking Changes. Der Typecheck des Workspace ist die Prüfung.

### A.2 Vorgehen

Kein `npm audit fix --force`, kein `--legacy-peer-deps`. `ng update` fährt die offiziellen
Migrationen (u.a. die, die `ChangeDetectionStrategy.Eager` nachträgt).

**Rollback:** `frontend/package.json` + `frontend/package-lock.json` vor dem Start sichern.
Beide sind versioniert, die Rücknahme ist ein Datei-Restore + `npm ci`. Kein DB-Anteil, keine
Migrationen — Paket A ist vollständig zurücknehmbar.

### A.3 Aufgaben

**A1 — Sicherung + Vorlauf.** `package.json`/`package-lock.json` in den Scratchpad kopieren.
Ausgangsstand festhalten: `npm test` (757/56/925), `npm run lint`, `npm run budget`.
*Prüfung:* die vier Zahlen stehen fest, bevor irgendetwas wandert.

**A2 — TypeScript 6.** `typescript` auf `~6.0.0`. `npx tsc -p …--noEmit` je Projekt.
*Prüfung:* Typecheck grün oder Liste der TS-6-Befunde; jeden einzeln bewerten, nicht
pauschal `any`-en.

**A3 — `ng update @angular/core@22 @angular/cli@22`.** Migrationen laufen lassen, Ausgabe
vollständig lesen und protokollieren (welche Migration was angefasst hat).
*Prüfung:* `npm ls @angular/core` = 22.x; die Migration hat `Eager` NUR dort ergänzt, wo
vorher kein `changeDetection` stand (erwartet: 1 Datei, der Test-Harness).

**A4 — `ng update @angular/material@22`** (zieht `@angular/cdk` mit).
*Prüfung:* `npm ls @angular/material @angular/cdk` = 22.x.

**A5 — `angular-eslint` auf 22.** *Prüfung:* `npm run lint` Exit 0.

**A6 — Diagnosen abarbeiten.** Die Meldungen aus A2/A3 (Template-Diagnosen, `?.`-Semantik)
einzeln lesen und beheben. **Keine** `$safeNavigationMigration()`-Wrapper stehen lassen.
*Prüfung:* `npm run build:widget` und `ng build studio` ohne Fehler und ohne neue Warnungen.

**A7 — Volle Abnahme.** `npm run lint` · `npm test` (757/56/925 unverändert) ·
`check:tokens`/`check:a11y`/`check:radii` · `npm run licenses` (Verteilung unverändert) ·
`npm run budget` (§5.5) · `npm audit --omit=dev` (0) · `npm audit` (Dev-Funde weg?).
*Prüfung:* alle Gates grün; Bundle-Zahl im Bericht festhalten.

**A8 — Doku nachziehen.** Audit-Dokument §4a: Dev-Baum-CVEs erledigt oder Rest benennen.
Spec-§2 (Stack) auf Angular 22 / TS 6.

### A.4 Durchführung — **abgeschlossen 2026-08-13, alle Gates grün**

**Der eine harte Stopper war die Umgebung, nicht der Code:** Angular CLI 22 verlangt Node
**≥ 22.22.3** (oder 24.15 / 26.0) — deutlich strenger als das „Node 22+" der Doku. Lokal lief
22.14.0, und `ng update` bricht davor ab, ohne irgendetwas anzufassen. Nutzer hat 22.23.2
installiert. Seither ist die Anforderung als `engines.node` in `frontend/package.json`
festgeschrieben, damit der nächste nicht in dieselbe Wand läuft. CI (`node-version: 22`) und
`Dockerfile` (`node:22-slim`) ziehen jeweils das neueste 22.x und waren nie betroffen.

Gefahren wurde ein einziger `ng update`-Lauf über alle vier Pakete gemeinsam
(`@angular/core@22 @angular/cli@22 @angular/material@22 angular-eslint@22`) — einzeln
scheiterte er an der Peer-Bindung von `angular-eslint@21` auf `@angular/cli <22`. Kein
`--force`, kein `--legacy-peer-deps`.

**Was die Migrationen taten — und was davon bleiben durfte:**

| Migration | Wirkung | Entscheidung |
|---|---|---|
| `ChangeDetectionStrategy.Eager` nachtragen | 10 Dateien: 9 Specs + 1 Test-Harness, **keine Produktivkomponente** | **Wieder entfernt.** Die Test-Doubles laufen auf dem neuen OnPush-Default — 925 Studio-Tests unverändert grün. Das Opt-out war überflüssig, und die neue Regel `prefer-on-push-component-change-detection` hätte es sonst als 11 Lint-Fehler angemahnt. |
| `$safeNavigationMigration()`-Wrapper | 2 Ausdrücke in `overview.component.html` | **Entfernt.** `ago()`/`exact()` nehmen bereits `string \| null \| undefined` — die Migration hatte die Signatur nicht geprüft. |
| Neue Diagnosen stilllegen (`nullishCoalescingNotNullable`, `optionalChainNotNullable`) | 5 tsconfigs auf `"suppress"` | **Wieder aktiviert.** Mit voll scharfen Prüfungen bauen Widget und Studio sauber: **null Befunde** bei 36 `?.` und 9 `??`. Die Unterdrückung war reine Vorsicht. |
| `provideHttpClient(withXhr())` ergänzen | 44 Dateien (1 Produktiv-Config + 43 Specs) | **Belassen.** Verhaltenserhaltend; der Wechsel auf den neuen Fetch-Default ist eine eigene Entscheidung, kein Migrations-Nebenprodukt. **Offen als Nachlauf.** |

**Zusätzlich nötig:** TypeScript 6 meldet `baseUrl` als abgekündigt (TS5101). Statt des
Silencers `ignoreDeprecations` trägt `tsconfig.json` jetzt `paths` **ohne** `baseUrl` — seit
TS 4.1 lösen die Einträge relativ zur tsconfig auf, die Werte haben dafür ein `./` bekommen.

**Der eigentliche Gewinn kam am Schluss und war kein Versionssprung:** `npm audit` meldete nach
der Migration weiterhin 7 Dev-Funde, und npm schlug als „Fix" eine Rückstufung auf
`@angular-devkit/build-angular@0.1002.1` (v10-Stand) vor. Ursache: das Paket stand noch in den
devDependencies, **wird aber von keinem einzigen Target referenziert** (alle Builder kommen aus
`@angular/build`). Es schleppte den kompletten Legacy-webpack-Stapel mit — webpack-dev-server,
sockjs, less, image-size, uuid — und mit ihm alle Funde. Entfernt statt hochgestuft.

**Abnahme (alle nach dem letzten Eingriff gemessen):**

| Gate | Ergebnis |
|---|---|
| `npm run lint` | Exit 0 |
| `npm test` | **757 / 56 / 925** — identisch zu Angular 21 |
| `ng build studio` · `npm run build:widget` | beide sauber |
| Diagnosen `nullish…`/`optionalChain…` | **aktiv**, 0 Befunde |
| `npm run budget` | raw 536,75 kB / 600 (89,5 %) · gzip 156,33 kB / 175 (89,3 %) — §5.5 gehalten (von 88,0/88,1 %) |
| `check:tokens` / `check:a11y` / `check:radii` | alle grün |
| Lizenz-Gate | unverändert erlaubt (MIT 15 · MPL/Apache 1 · BSD-2 1 · Apache-2.0 1 · 0BSD 1) |
| `npm audit` **und** `--omit=dev` | **0 vulnerabilities** |

**Noch offen / bewusst nicht getan:** ein Live-Test des
Embeds gegen `element-api.ts:26` — der einzige Griff in nicht-öffentliches Angular-API
(`_ngElementStrategy.componentRef.instance`, trägt die 6 JS-Methoden des Custom Elements).
Die Unit-Tests dazu sind grün, aber ein echter Browser-Lauf (`npm run e2e`) gehört vor den
Deploy. Playwright startet der Nutzer.

**Der `withXhr()`-Nachlauf — nachgemessen 2026-08-13, Ergebnis: Nutzer-Entscheid, nicht
Aufräumarbeit.** Die „44 Dateien" zerfallen in zwei sehr ungleiche Hälften:

* **42 Spec-Dateien** — und **alle 42** registrieren zusätzlich `provideHttpClientTesting()`.
  Dort ist `withXhr()` wirkungslos: das Test-Backend ersetzt den echten Transport vollständig.
* **2 Nicht-Spec-Dateien** — `studio/app/app.config.ts` (die einzige ausgelieferte Stelle) und
  `quality-logs.harness.ts` (Test-Harness). Der Widget-Baum nutzt `provideHttpClient`
  **gar nicht** und ist nicht betroffen.

Daraus folgt das Unangenehme: `withXhr()` zu entfernen ist eine **Ein-Zeilen-Änderung am
Produktivpfad, die keine Prüfung im Workspace verifizieren kann** — jede Spec, die HTTP
anfasst, kurzschließt genau den Transport, um den es geht. Grün nach dem Entfernen bewiese
nichts. Der Wechsel auf den Fetch-Default löst heute auch kein Problem: der SSE-Strom läuft
ohnehin über rohes `fetch` (nicht über `HttpClient`), Upload-Fortschritt nutzt niemand
(`reportProgress`: 0 Treffer). Deshalb **belassen**. Wenn er kommen soll, gehört ein
manueller Durchgang durch Studio-Anmeldung, Snapshot-Download und Datei-Ingest dazu —
kein Suitenlauf.

---

## Paket B — Zerlegung der fünf größten Backend-Dateien

### B.1 Befund: nur zweieinhalb der fünf lassen sich **sicher** zerlegen

Die Struktur (AST-Auszug, Top-Level-Definitionen mit Zeilenzahl) sagt, was möglich ist:

| Datei | Zeilen | Struktur | Zerlegbar? |
|---|---:|---|---|
| `services/eval_service.py` | 861 | **25 kleine Funktionen** (größte 99) | ✅ **voll** — echte Verantwortungs-Nähte |
| `services/mcp/tool_defs.py` | 765 | Konstante `TOOL_DEFINITIONS` (553) + 3 kleine Helfer | ✅ **voll** — Daten nach Werkzeug-Familie trennen |
| `services/tool_loop.py` | 1141 | `_assemble_messages` (333) · `_run_tool_loop` (685) · `_max_iterations_fallback` (45) | ⚠️ **halb** — zwei Funktionen sind verschiebbar, danach bleiben ~730 Z. |
| `services/turn_links.py` | 872 | **eine** Funktion `_finalize_links_and_metas` (772) | ❌ **keine Naht** |
| `services/widget_postprocess.py` | 768 | **eine** Funktion `_postprocess_response_for_widget_modes` (706) | ❌ **keine Naht** |

**Warum das zählt.** Bei den letzten dreien ist „Zerlegen" kein Verschieben, sondern das
**Auseinandernehmen einer einzelnen Funktion**. Das heißt:

- Es ist ein **Rewrite, kein Extract.** Die Workflow-Regel ist ausdrücklich
  „Extraktion verschiebt Code, sie schreibt ihn nicht um".
- Es bricht die **Fidelity-Zusage**: genau diese drei Funktionen sind Voll-verbatim-Ports aus
  ALT und wurden per **AST-Gate** gegen die Vorlage abgenommen (Spec-Log: `_run_tool_loop`
  „AST-Gate 206 verschachtelte Stmts nach sanktionierten Transforms, 24 Pins";
  `_assemble_messages` „AST 29/29"). Nach einer Zerlegung ist dieser Abgleich nicht mehr
  fahrbar — der Prüfmechanismus für die Paritätszusage entfällt.
- Es trifft die **heißesten Pfade** der Anwendung: die Werkzeug-Schleife und die
  Widget-Nachbereitung laufen in jedem Zug.

Der Fahrplan des Audits sagt zu F-8 ausdrücklich „**nach** dem Cutover, und zuerst die Regel
in der Spec um die Port-Ausnahme ergänzen". Der Befund hier stützt das für drei der fünf.

### B.2 Zu entscheiden

Für `turn_links.py`, `widget_postprocess.py` und den 685-Zeilen-Rumpf von `_run_tool_loop`:
**jetzt zerlegen (Rewrite, Fidelity-Gate entfällt) oder bis nach dem Cutover warten?**
Empfehlung: warten. Die beiden sicheren Zerlegungen liefern schon 1.626 Zeilen Überhang-Abbau
ohne jedes Risiko.

### B.3 Aufgaben — die sicheren Zerlegungen

Grundregel für jede: **behaviour-preserving**. Code wird verschoben, nicht umgeschrieben;
Aufrufstellen und Importe werden angepasst, Logik nicht angefasst. Vor und nach jedem Schnitt
läuft die volle Suite; die Fassade behält ihre öffentlichen Namen, damit kein Test und kein
Aufrufer nachgezogen werden muss (Tests patchen laut Modul-Docstring teils **auf dem Modul** —
die Re-Exports müssen also stehen bleiben).

**B1 — `eval_service.py` (861 → 4 Module).** Schnitt nach Verantwortung:
- `eval/queries.py` — `list_runs`, `get_run`, `get_trends` (99), `list_gold_flows`,
  `list_personas_and_intents`, `pattern_usage_stats` (71) ≈ 235 Z.
- `eval/cost.py` — `estimate_cost` (37), `estimate`, `_compute_target_turns` ≈ 60 Z.
- `eval/mutations.py` — `delete_run`, `delete_runs`, `clear_eval_quality_logs`,
  `_ensure_no_running_run`, `_finalize_run` ≈ 110 Z.
- `eval_service.py` (Fassade + Läufe) — `start_generative_run`, `_execute_generative_run`,
  `start_golden_eval_run`, `_execute_golden_run`, `_progress_writer` ≈ 310 Z.
*Prüfung:* volle Suite unverändert; `grep` belegt, dass jeder öffentliche Name weiterhin aus
`eval_service` importierbar ist.

**B2 — `mcp/tool_defs.py` (765 → 3 Module).** `TOOL_DEFINITIONS` (553 Z. reine Daten) nach
Familie trennen — Suche / Lesen / Vokabular —, analog zum schon bestehenden
`tool_defs_curation.py`; die Validierer (`validate_tool_args`, `_clamp_bound_violations`,
`_export_non_empty`) nach `mcp/tool_args.py`. Die Fassade `tool_defs.py` setzt die Liste
wieder zusammen und re-exportiert.
*Prüfung:* volle Suite; der bestehende **Wächter** (Registry-Deckung gegen `TOOL_DEFINITIONS`)
muss weiter greifen — er ist der beste Beleg, dass die Liste vollständig geblieben ist.

**B3 — `tool_loop.py` (1141 → ~730 + 380).** `_assemble_messages` (333) nach
`services/tool_loop_messages.py`, `_max_iterations_fallback` (45) nach
`services/tool_loop_fallback.py`; `tool_loop.py` importiert und re-exportiert beide.
*Prüfung:* volle Suite, insbesondere `test_tool_loop.py`; die Pins der beiden Funktionen
laufen unverändert. **Ergebnis ehrlich benennen:** 730 Z. sind weiterhin über der Regel.

**Erwartetes Ergebnis Paket B:** Überhang von 8.289 auf ca. **6.663** Zeilen; die Zahl der
Dateien über 300 steigt (mehr, kleinere Module) — das ist der Sinn der Regel, nicht ihr
Verstoß.

### B.4 Durchführung — **abgeschlossen 2026-08-13, Suite unverändert**

Baseline vor dem ersten Schnitt: **3207 passed, 4 skipped**. Nach jedem der drei Schnitte
dieselbe Zahl. `ruff check src/ tests/` durchgehend sauber.

**Zwei Annahmen des Plans hielten der Prüfung nicht stand.**

*Erstens:* „die Fassade behält ihre öffentlichen Namen, damit kein Test nachgezogen werden
muss" — das gilt nur für öffentliche Namen. Die Tests patchen **sechs private Helfer** im
Namensraum `eval_service` (`_ensure_no_running_run`, `_spawn_background`, `_finalize_run`,
`_load_golden_runner`, `load_gold_flows`, `list_personas_and_intents`). Ein Patch wirkt dort,
wo der **Aufrufer** wohnt, nicht wo die Fassade re-exportiert. Der Schnitt richtet sich
deshalb nach der Patch-Fläche, und 18 `monkeypatch`-Ziele wurden auf das Modul umgezogen, das
den Aufruf jetzt enthält — mechanisch, kein einziges Assert verändert.

*Zweitens:* B2 sollte `TOOL_DEFINITIONS` „nach Werkzeug-Familien" zerlegen. Das ist **keine
Verschiebung, sondern eine Verhaltensänderung**: die Familien liegen nicht zusammenhängend,
eine Gruppierung sortiert die Liste um — und die Reihenfolge geht so in den Prompt
(`response_tool_selection` reicht `list(TOOL_DEFINITIONS)` durch; deren Docstring hält fest,
dass eine frühere Reihenfolge-Änderung „zwei fremde Tests kippte"). Der Literal bleibt darum
ganz. Zerlegt wurde stattdessen entlang der Frage, die die beiden Hälften beantworten:
`tool_defs` sagt WELCHE Werkzeuge es gibt, `tool_args` wie ein Aufruf gültig aussieht — genau
die Trennung, die `client.py` schon vorlebte (es importierte ausschliesslich die Argument-Seite).
Belegt per SHA256 des serialisierten Katalogs vor und nach dem Schnitt: **identisch**
(`8e6d9c69…`, 26 Werkzeuge).

| Datei | vorher | nachher | neue Module |
|---|---|---|---|
| `services/eval_service.py` | 860 | **77** (reine Fassade) | `eval/`: `cost` 96 · `queries` 254 · `mutations` 71 · `run_store` 98 · `generative_run` 226 · `golden_run` 177 |
| `services/mcp/tool_defs.py` | 764 | **572** (nur noch der Katalog) | `mcp/tool_args.py` 210 |
| `services/tool_loop.py` | 1140 | **760** (nur noch `_run_tool_loop`) | `tool_loop_messages.py` 362 · `tool_loop_fallback.py` 64 |

Nebenbefund beim Verschieben: `_RUNNER_PATH` in `golden_run.py` musste von `parents[4]` auf
`parents[5]` — eine Ebene tiefer. Geprüft, dass sie weiterhin auf `evals/run_golden.py` zeigt.

**Ehrlich zum Ergebnis:** der Überhang im Backend sinkt von 8.335 auf **7.265** Zeilen
(−1.070, −13 %), die Zahl der Dateien über 300 bleibt bei **48**. Drei Dateien liegen weiter
darüber, jede aus einem benennbaren Grund:

* `tool_loop.py` (760) — `_run_tool_loop` ist **eine** Funktion mit 685 Zeilen, AST-Gate-
  abgenommen („206 verschachtelte Stmts, 24 Pins"). Weiter zerlegen hiesse umschreiben.
* `tool_loop_messages.py` (362) — dasselbe für `_assemble_messages` (333 Z., AST 29/29). Das
  Modul kann nicht kleiner werden als die Funktion, die es enthält.
* `tool_defs.py` (572) — ein geordneter Daten-Literal, siehe oben.

Das ist kein Rest, den man noch „aufräumen" könnte, sondern die Grenze, die der Nutzer-
Entscheid „nur die sicheren zwei(einhalb)" bewusst gezogen hat.

### B.5 Nachtrag — Wächter für die Katalog-Reihenfolge (2026-08-13)

Der SHA256-Abgleich aus B2 war ein Einmal-Werkzeug von mir: er belegte, dass *dieser* Schnitt
die Reihenfolge nicht angetastet hat, schützt aber nichts gegen den nächsten Eingriff. Und
geschützt war sie durch **nichts** — alle bestehenden Prüfungen auf `TOOL_DEFINITIONS`
arbeiten mit `set(...)` oder `len(...)` und sind gegen eine Umsortierung blind.

`tests/test_mcp_tool_defs.py` hält die Namensfolge jetzt als Liste fest
(`test_tool_definitions_order_is_pinned`, 26 Einträge). Der Pin schlägt **absichtlich** auch
bei einem neuen Werkzeug an: wer eines ergänzt, soll die Einfügeposition bewusst wählen und
hier nachtragen, statt sie dem Zufall des Anhängens zu überlassen.

Nachgewiesen, dass er greift — nicht nur, dass er grün ist: bei vertauschten Nachbarn schlägt
er an, bei einem angehängten Werkzeug schlägt er an, im Ist-Zustand ist er grün. Suite danach
**3208 passed, 4 skipped** (ein Test mehr, sonst unverändert).

### B.6 Nachtrag — die Regel ehrlich machen (2026-08-13)

Der Audit-Fahrplan nennt zu F-8 eine Voraussetzung: „**zuerst** die Regel in der Spec um die
Port-Ausnahme ergänzen, dann zerlegen". Die war offen — und der Grund steht in der Regel
selbst. Spec-§0.7 sagte: „beim Portieren großer Alt-Module direkt am Verantwortlichkeits-
Schnitt splitten (*die Alt-Zerlegung gibt die Schnitte bereits vor*)". Genau diese Klammer
trifft bei `turn_links` und `widget_postprocess` nicht zu: ALT hat dort **eine** Funktion,
es gibt keinen vorgegebenen Schnitt. Die Regel war also nicht nur unvollständig, ihre
Begründung war für einen Teil des Bestands falsch.

§0.7 trägt jetzt die Ausnahme mit drei Bedingungen — Überhang aus EINER Funktion/EINEM
Literal · Marker im Docstring · kein Wachstumsfreibrief — und einem **Verfallsdatum**: sie
erlischt mit dem Cutover, weil dann das AST-Gate nicht mehr bindet.

Das Wort dafür musste nicht erfunden werden. `Fidelity-Port-Ausnahme` stand bereits in zwei
Frontend-Dateien (`ui/debug/debug-panel.component.ts`, `ui/grouping/result-grouping.ts`); im
Backend gab es null Treffer. Übernommen statt neu erfunden, und auf die fünf Backend-Dateien
angewandt, die die Ausnahme beanspruchen.

**Was das bringt:** `grep -r "Fidelity-Port-Ausnahme"` liefert jetzt die vollständige Liste —
**5 Backend, 2 Frontend**. Damit zerfallen die 48 Backend-Dateien über 300 Zeilen erstmals in
**5 begründete Ausnahmen** und **43 unentschiedene Schuld**; vorher war beides von außen
ununterscheidbar. Die größten unentschiedenen sind damit auch benannt: `domain/canvas/types.py`
684 · `services/guide_qr_injector.py` 647 · `services/turn_persist.py` 621 ·
`services/page_context.py` 596 · `services/mcp/arg_resolvers.py` 595.

**Die Ironie ehrlich benannt:** die Begründungen kosten je 4–5 Zeilen, der Überhang steigt
dadurch von 7.265 auf **7.286**. Das ist der richtige Tausch — eine unbegründete Ausnahme
ist teurer als 21 Zeilen Text —, aber es ist ein Aufschlag und kein Abbau.

---

## Reihenfolge

Paket A zuerst und **allein** — eine Framework-Migration und eine Backend-Umstrukturierung im
selben Arbeitsgang wären beim Bisektieren eines Fehlers nicht mehr trennbar. Paket B
anschließend, Aufgabe für Aufgabe, jede mit voller Suite davor und danach.
