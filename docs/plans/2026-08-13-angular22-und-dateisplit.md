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

---

## Reihenfolge

Paket A zuerst und **allein** — eine Framework-Migration und eine Backend-Umstrukturierung im
selben Arbeitsgang wären beim Bisektieren eines Fehlers nicht mehr trennbar. Paket B
anschließend, Aufgabe für Aufgabe, jede mit voller Suite davor und danach.
