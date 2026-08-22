/**
 * Die Ansicht „Lasttest" (C1-d4e1) — Formular, Lauf-Liste, Lauf-Panel und die
 * Sätze des reinen Profil-Moduls.
 *
 * **Ein Teil, weil es EIN Panel ist:** `loadtest-run.component` wird unten in
 * `loadtest.component` hinein gerendert, nicht neben sie. Dieselbe Lage wie
 * Übersicht/Diagnose (C1-d4d1) und Logs/Turn-Detail (C1-d4d2). Die Präfixe
 * unterscheiden trotzdem, wo ein Text steht.
 *
 * **Vier Anzahlen, die bis hierher fest in der Mehrzahl standen** — Requests,
 * Fehler, Messpunkte und Stufen. Alle vier können 1 sein: das Backend deckelt
 * nichts nach unten, und ein Lauf, der kürzer ist als der Abtast-Takt von
 * 0,5 s, liefert genau einen Messpunkt. Sie stehen als eigene Wortgruppen da
 * und werden in die Sätze eingesetzt, statt jeden Satz zu verdoppeln.
 *
 * **Die Nutzer-Anzahl beugt das Adjektiv mit:** „bis 1 gleichzeitigen Nutzer"
 * gegen „bis 4 gleichzeitige Nutzer". Deshalb steht dort der GANZE Satz je
 * Form und nicht eine eingesetzte Wortgruppe — dieselbe Lage wie bei
 * `qualFlow.days` (C1-d4d2), nur eine Wortart weiter.
 *
 * **Was NICHT hier steht:** die Brotkrume (`nav.group.auswertung`) und der
 * Titel (`view.lasttest.label`) kommen aus `views.ts`; `action.cancel`,
 * `action.confirmDelete`, `action.refresh*` und der Zustands-Streifen aus
 * `shared.ts`.
 *
 * **Drei Sätze tragen Auszeichnung** (`*so*` → `<strong>`): das Kosten-Band
 * und die zwei Urteile des Lauf-Panels. Geteilt wird der Katalog-Text, dann
 * eingesetzt — die eingesetzte Zahl kann keine Auszeichnung erzeugen.
 */
import type { CataloguePart } from './catalogue-part';

export const LOADTEST: CataloguePart = {
  de: {
    // ── Wortgruppen für die Sätze weiter unten ──────────────────────
    'lt.requests.one': '{count} Request',
    'lt.requests.other': '{count} Requests',
    /** Deutsch beugt „Fehler" nicht; Englisch schon. Die zwei Formen stehen
     *  also für die andere Sprache da — genau der Fall, für den `plural()`
     *  gebaut ist. */
    'lt.errors.one': '{count} Fehler',
    'lt.errors.other': '{count} Fehler',
    'lt.samples.one': '{count} Messpunkt',
    'lt.samples.other': '{count} Messpunkte',
    'lt.stageCount.one': '{count} Stufe',
    'lt.stageCount.other': '{count} Stufen',

    // ── Formular ────────────────────────────────────────────────────
    'lt.intro':
      'Skalierbarkeits-Selbsttest: gemischte Abfragen mit steigender Parallelität gegen '
      + 'die eigene Pipeline — Latenz und Fehler je Stufe.',
    'lt.profile.legend': 'Profil',
    'lt.stages': 'Stufen — Parallelität, kommagetrennt',
    'lt.stages.hint': 'höchstens {stages} Stufen, je bis {concurrency} parallel',
    'lt.requests': 'Requests pro Stufe',
    'lt.threshold': 'p95-Schwelle für „stabil" (Sekunden)',
    // Review-Befund 7: Engine je Lauf — agent/hybrid haben ein anderes
    // Runden-Profil, ohne Wahl galten die Zahlen nur für die Vorgabe.
    'lt.engine.legend': 'Maschine (Engine)',
    'lt.engine.default': 'Server-Vorgabe',
    'lt.engine.hint':
      'Jeder Zug des Laufs fährt mit dieser Engine — die Kapazitätszahlen '
      + 'gelten nur für die gewählte Maschine.',
    'lt.mix.legend': 'Abfrage-Mix — Gewichte 0 bis 10',
    'lt.mix.label': 'Mix-Kategorien',

    'lt.cost.requests.one': '{count} echte Chat-Anfrage',
    'lt.cost.requests.other': '{count} echte Chat-Anfragen',
    'lt.cost':
      '*Kosten und Last:* dieser Lauf feuert *{requests}* (LLM + MCP) — Stufen {stages} '
      + '× {perStage}. Lernpfad-Anteile sind die teuersten. Es läuft immer nur ein Test '
      + 'gleichzeitig.',
    'lt.adjust':
      'Das Backend passt das Profil an: {changes} Oben steht bereits, was tatsächlich '
      + 'läuft.',
    'lt.busy': 'Lauf {id} ist noch unterwegs — solange startet kein zweiter.',
    'lt.start': 'Lasttest starten',
    'lt.starting': 'Startet …',
    'lt.started': 'Lasttest {id} gestartet.',

    // ── Lauf-Liste ──────────────────────────────────────────────────
    'lt.runs': 'Läufe',
    'lt.runs.empty': 'Noch kein Lasttest gelaufen. Oben ein Profil wählen und starten.',
    'lt.delete': 'Löschen',
    /** Zugänglicher Name desselben Knopfs — die Liste trägt ihn je Zeile
     *  gleichlautend. Beginnt mit dem sichtbaren Wort (WCAG 2.5.3). */
    'lt.deleteFor': 'Löschen — Lauf {id}',
    'lt.confirm':
      'Diesen Lauf mit allen Messwerten löschen? Das lässt sich nicht rückgängig machen.',
    'lt.deleting': 'Wird gelöscht …',
    'lt.deleted': 'Lauf {id} gelöscht.',
    'lt.status.running': 'läuft',
    'lt.status.completed': 'abgeschlossen',
    'lt.status.failed': 'fehlgeschlagen',
    'lt.summary.none': 'keine stabile Stufe',
    'lt.summary.stable': 'stabil bis {count} parallel',
    'lt.summary.peak': 'Spitze {value} MB',

    // ── Lauf-Panel ──────────────────────────────────────────────────
    'ltRun.label': 'Lauf',
    'ltRun.title': 'Auswertung {id}',
    'ltRun.progress': '— Stufe {done} von {total} fertig',
    'ltRun.profile':
      'Stufen {stages} · {requests} je Stufe · Mix {mix} · p95-Schwelle {threshold} s',
    /** Der ganze Satz je Form: „bis 1 gleichzeitigen Nutzer" gegen „bis 4
     *  gleichzeitige Nutzer" — die Beugung sitzt im Adjektiv, nicht am
     *  Substantiv, und keine Wortgruppe könnte sie mitbringen. */
    'ltRun.stable.one':
      '*Stabil bis {count} gleichzeitigen Nutzer* (keine Fehler, p95 ≤ {threshold} s).',
    'ltRun.stable.other':
      '*Stabil bis {count} gleichzeitige Nutzer* (keine Fehler, p95 ≤ {threshold} s).',
    'ltRun.unstable':
      '*Schon die erste Stufe verfehlte die Schwelle* — Profil oder Schwelle prüfen.',
    'ltRun.totals': '{requests}, {errors}.',
    'ltRun.peaks': 'Spitze: {rss} MB Speicher, {cpu} % CPU ({samples}, alle 0,5 s).',
    'ltRun.noSamples':
      'Keine Messpunkte aufgezeichnet — der Lauf war kürzer als ein Abtast-Intervall.',
    'ltRun.processNote':
      'Gemessen wird der *Backend-Prozess*. Bleibt seine CPU niedrig, während p95 mit der '
      + 'Parallelität steigt, liegt die Grenze beim Upstream (LLM, MCP) — nicht bei der '
      + 'eigenen Maschine.',

    'ltRun.chart.caption': 'Antwortlatenz gegen Parallelität',
    'ltRun.chart.alt': 'Latenzverlauf über {stages}; die Werte stehen in der Tabelle darunter.',
    'ltRun.chart.threshold': 'p95-Schwelle {seconds} s',
    /** Legende UND Spaltenkopf lesen denselben Schlüssel: es ist dasselbe
     *  Perzentil, zweimal benannt. */
    'ltRun.p50': 'p50',
    'ltRun.p95': 'p95',
    'ltRun.legend.limit': 'Schwelle',

    'ltRun.table.caption': 'Ergebnis je Stufe',
    'ltRun.col.concurrency': 'parallel',
    'ltRun.col.requests': 'Requests',
    'ltRun.col.ok': 'OK',
    'ltRun.col.errors': 'Fehler',
    'ltRun.col.max': 'max',
    'ltRun.col.rps': 'RPS',
    'ltRun.col.byKind': 'p95 je Kategorie',
    'ltRun.noStage': 'Keine abgeschlossene Stufe — der Lauf endete, bevor eine Stufe fertig war.',

    // ── Reines Profil-Modul ─────────────────────────────────────────
    // Die drei Korrekturen und die drei Ablehnungen aus `loadtest-profile.ts`.
    // Ihre Zahlen sind Konstanten des Backends (6/32/60/200) — eine
    // Einzahl-Form könnte hier nie greifen und stünde nur als totes Gewicht da.
    'ltProfile.adjust.stages': 'Nur die ersten {count} Stufen laufen.',
    'ltProfile.adjust.concurrency': 'Parallelität ist bei {count} gedeckelt.',
    'ltProfile.adjust.requests': 'Höchstens {count} Requests pro Stufe.',
    'ltProfile.problem.noStage': 'Mindestens eine Stufe nötig — z. B. „1, 2, 4".',
    'ltProfile.problem.tooBig':
      'Profil zu groß: {total} Requests gesamt (Limit {limit}). Stufenzahl oder Requests '
      + 'pro Stufe reduzieren.',
    'ltProfile.problem.emptyMix':
      'Der Mix darf nicht leer sein — mindestens eine Kategorie braucht ein Gewicht.',
  },

  en: {
    'lt.requests.one': '{count} request',
    'lt.requests.other': '{count} requests',
    'lt.errors.one': '{count} error',
    'lt.errors.other': '{count} errors',
    'lt.samples.one': '{count} sample',
    'lt.samples.other': '{count} samples',
    'lt.stageCount.one': '{count} stage',
    'lt.stageCount.other': '{count} stages',

    'lt.intro':
      'Scalability self-test: mixed queries at rising concurrency against our own '
      + 'pipeline — latency and errors per stage.',
    'lt.profile.legend': 'Profile',
    'lt.stages': 'Stages — concurrency, comma-separated',
    'lt.stages.hint': 'at most {stages} stages, each up to {concurrency} in parallel',
    'lt.requests': 'Requests per stage',
    'lt.threshold': 'p95 threshold for "stable" (seconds)',
    'lt.engine.legend': 'Engine',
    'lt.engine.default': 'Server default',
    'lt.engine.hint':
      'Every turn of the run uses this engine — the capacity numbers only '
      + 'hold for the chosen machine.',
    'lt.mix.legend': 'Query mix — weights 0 to 10',
    'lt.mix.label': 'Mix categories',

    'lt.cost.requests.one': '{count} real chat request',
    'lt.cost.requests.other': '{count} real chat requests',
    'lt.cost':
      '*Cost and load:* this run fires *{requests}* (LLM + MCP) — stages {stages} × '
      + '{perStage}. Learning-path shares are the most expensive. Only one test ever runs '
      + 'at a time.',
    'lt.adjust':
      'The backend adjusts the profile: {changes} What is shown above is what will '
      + 'actually run.',
    'lt.busy': 'Run {id} is still under way — no second one starts until it is done.',
    'lt.start': 'Start load test',
    'lt.starting': 'Starting …',
    'lt.started': 'Load test {id} started.',

    'lt.runs': 'Runs',
    'lt.runs.empty': 'No load test has run yet. Pick a profile above and start it.',
    'lt.delete': 'Delete',
    'lt.deleteFor': 'Delete — run {id}',
    'lt.confirm': 'Delete this run and all its measurements? This cannot be undone.',
    'lt.deleting': 'Deleting …',
    'lt.deleted': 'Run {id} deleted.',
    'lt.status.running': 'running',
    'lt.status.completed': 'completed',
    'lt.status.failed': 'failed',
    'lt.summary.none': 'no stable stage',
    'lt.summary.stable': 'stable up to {count} in parallel',
    'lt.summary.peak': 'peak {value} MB',

    'ltRun.label': 'Run',
    'ltRun.title': 'Analysis {id}',
    'ltRun.progress': '— stage {done} of {total} done',
    'ltRun.profile':
      'Stages {stages} · {requests} per stage · mix {mix} · p95 threshold {threshold} s',
    'ltRun.stable.one':
      '*Stable up to {count} concurrent user* (no errors, p95 ≤ {threshold} s).',
    'ltRun.stable.other':
      '*Stable up to {count} concurrent users* (no errors, p95 ≤ {threshold} s).',
    'ltRun.unstable':
      '*Even the first stage missed the threshold* — check the profile or the threshold.',
    'ltRun.totals': '{requests}, {errors}.',
    'ltRun.peaks': 'Peak: {rss} MB memory, {cpu} % CPU ({samples}, every 0.5 s).',
    'ltRun.noSamples':
      'No samples recorded — the run was shorter than one sampling interval.',
    'ltRun.processNote':
      'What is measured is the *backend process*. If its CPU stays low while p95 rises '
      + 'with concurrency, the limit is upstream (LLM, MCP) — not on this machine.',

    'ltRun.chart.caption': 'Response latency against concurrency',
    'ltRun.chart.alt': 'Latency curve across {stages}; the values are in the table below.',
    'ltRun.chart.threshold': 'p95 threshold {seconds} s',
    'ltRun.p50': 'p50',
    'ltRun.p95': 'p95',
    'ltRun.legend.limit': 'Threshold',

    'ltRun.table.caption': 'Result per stage',
    'ltRun.col.concurrency': 'parallel',
    'ltRun.col.requests': 'Requests',
    'ltRun.col.ok': 'OK',
    'ltRun.col.errors': 'Errors',
    'ltRun.col.max': 'max',
    'ltRun.col.rps': 'RPS',
    'ltRun.col.byKind': 'p95 per category',
    'ltRun.noStage': 'No completed stage — the run ended before a stage finished.',

    'ltProfile.adjust.stages': 'Only the first {count} stages run.',
    'ltProfile.adjust.concurrency': 'Concurrency is capped at {count}.',
    'ltProfile.adjust.requests': 'At most {count} requests per stage.',
    'ltProfile.problem.noStage': 'At least one stage is needed — e.g. "1, 2, 4".',
    'ltProfile.problem.tooBig':
      'Profile too large: {total} requests in total (limit {limit}). Reduce the number '
      + 'of stages or the requests per stage.',
    'ltProfile.problem.emptyMix':
      'The mix must not be empty — at least one category needs a weight.',
  },
};
