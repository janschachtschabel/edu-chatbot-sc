/**
 * Die Evaluation (C1-d4b): die Reiter-Hülle und die Lauf-Liste.
 *
 * Die drei Reiter-Beschriftungen standen bis hierher als fertige Sätze in einer
 * Modul-Konstante `TABS` — der siebte eingefrorene Konstanten-Fall nach
 * `CONFIRM_LEAVE`, dem Routen-Titel, `PREVIEW_CONTEXT_KINDS`, `SOURCES`,
 * `curated-views.ts` und `overview-cards.ts`.
 *
 * NICHT hier: die Wörter, die keiner Ansicht gehören — „Abbrechen",
 * „Aktualisieren" und „Ja, löschen" kommen aus `shared.ts`. Die Lauf-Liste ist
 * die dritte Ansicht, die nach ihnen greift; „Ja, löschen" ist bei dieser
 * Gelegenheit von zwei Kopien (`snapshots.confirmDeleteYes`, `rag.confirmYes`)
 * auf einen Eintrag zusammengezogen worden, statt eine dritte anzulegen.
 *
 * Das Lauf-DETAIL wohnt in `eval-detail.ts`, die Pattern-Nutzung in
 * `eval-pattern.ts` — die Evaluation hat fünf Ansichten, und ein Teil für alle
 * wäre mit C1-d4c über 400 Zeilen lang. Die drei Status-Wörter unten lesen
 * aber BEIDE Lauf-Ansichten, über `views/eval-status.ts`.
 *
 * `eval.tab.pattern` ist mehr als eine Reiter-Beschriftung: die Ansicht selbst
 * liest ihn seit C1-d4b3 als Überschrift und als Substantiv des
 * Zustands-Streifens. Ein eigener Eintrag mit demselben Wortlaut wäre eine
 * Doppelung, die `en.spec.ts` bauartbedingt nicht fände — der Test vergleicht
 * Deutsch gegen Englisch je Schlüssel, nie Schlüssel gegeneinander.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const EVALUATION: CataloguePart = {
  de: {
    // ── Hülle ───────────────────────────────────────────────────────
    'eval.label': 'Evaluation',
    'eval.tab.laeufe': 'Läufe',
    'eval.tab.trends': 'Trends',
    'eval.tab.pattern': 'Pattern-Nutzung',

    // ── Lauf-Liste: Leiste ──────────────────────────────────────────
    'evalRuns.filter.label': 'Status',
    'evalRuns.filter.all': 'alle Status',
    'evalRuns.filter.done': 'fertige',
    'evalRuns.filter.failed': 'fehlgeschlagene',
    'evalRuns.filter.running': 'laufende',
    'evalRuns.deleteAll': 'Alle Läufe löschen',
    'evalRuns.deleteFiltered': 'Gefilterte Läufe löschen',
    'evalRuns.clearLogs': 'Eval-Quality-Logs löschen',

    // ── Rückfragen und Vollzugsmeldungen ────────────────────────────
    'evalRuns.ask.run': 'Lauf {id} endgültig löschen?',
    'evalRuns.ask.logs':
      'Alle Quality-Logs löschen, die Eval-Läufe geschrieben haben? Echte '
      + 'Chat-Turns bleiben unberührt.',
    'evalRuns.ask.all': 'ALLE Eval-Läufe löschen — auch die laufenden?',
    /** `{label}` ist der Name des gewählten Filters, übersetzt und in der
     *  Stellung, die die Sprache ihm gibt. */
    'evalRuns.ask.filtered': 'Alle {label} Eval-Läufe löschen?',
    'evalRuns.done.run': 'Lauf {id} gelöscht.',
    'evalRuns.done.logs': '{count} Eval-Quality-Logs gelöscht.',
    'evalRuns.done.runs.one': '{count} Lauf gelöscht.',
    'evalRuns.done.runs.other': '{count} Läufe gelöscht.',

    // ── Zustand der Liste ───────────────────────────────────────────
    'evalRuns.list': 'Eval-Läufe',
    'evalRuns.empty':
      'Noch kein Eval-Lauf. Starte unten einen Gold-Flow-Lauf — der ist '
      + 'deterministisch und prüft feste Gesprächsabläufe.',
    /** Mehrzahl über `plural()`: bis C1-d4b stand hier `{n} Läufe` fest, und
     *  ein einzelner Lauf las sich „1 Läufe" — schon einsprachig falsch. */
    'evalRuns.count.one': '{count} Lauf · neueste zuerst',
    'evalRuns.count.other': '{count} Läufe · neueste zuerst',
    'evalRuns.live': 'ein Lauf ist aktiv, die Liste aktualisiert sich selbst',

    // ── Eine Zeile ──────────────────────────────────────────────────
    'evalRuns.status.running': 'läuft',
    'evalRuns.status.done': 'fertig',
    'evalRuns.status.failed': 'fehlgeschlagen',
    'evalRuns.progress': '{done} von {total} Turns',
    'evalRuns.result': '{turns} Turns · Ø Score {score}',
    'evalRuns.noConfig': 'ohne Konfigurations-Kennung',
    'evalRuns.personas': '{count} Personas',
    'evalRuns.intents': '{count} Intents',
    'evalRuns.delete': 'Löschen',
    /** Zugänglicher Name desselben Knopfs — jede Zeile trägt dasselbe
     *  sichtbare Wort. Beginnt damit (WCAG 2.5.3 „Label in Name"), wie
     *  `async.retryFor`. */
    'evalRuns.deleteFor': 'Löschen — Lauf {id}',
    'evalRuns.deleteBlocked': 'Ein laufender Lauf kann nicht gelöscht werden',
  },

  en: {
    'eval.label': 'Evaluation',
    'eval.tab.laeufe': 'Runs',
    'eval.tab.trends': 'Trends',
    'eval.tab.pattern': 'Pattern usage',

    'evalRuns.filter.label': 'Status',
    'evalRuns.filter.all': 'all statuses',
    'evalRuns.filter.done': 'completed',
    'evalRuns.filter.failed': 'failed',
    'evalRuns.filter.running': 'in flight',
    'evalRuns.deleteAll': 'Delete all runs',
    'evalRuns.deleteFiltered': 'Delete filtered runs',
    'evalRuns.clearLogs': 'Delete eval quality logs',

    'evalRuns.ask.run': 'Delete run {id} for good?',
    'evalRuns.ask.logs':
      'Delete every quality log an eval run wrote? Real chat turns stay '
      + 'untouched.',
    'evalRuns.ask.all': 'Delete ALL eval runs — including the ones in flight?',
    'evalRuns.ask.filtered': 'Delete all {label} eval runs?',
    'evalRuns.done.run': 'Run {id} deleted.',
    'evalRuns.done.logs': '{count} eval quality logs deleted.',
    'evalRuns.done.runs.one': '{count} run deleted.',
    'evalRuns.done.runs.other': '{count} runs deleted.',

    'evalRuns.list': 'Eval runs',
    'evalRuns.empty':
      'No eval run yet. Start a gold-flow run below — it is deterministic and '
      + 'checks fixed conversations.',
    'evalRuns.count.one': '{count} run · newest first',
    'evalRuns.count.other': '{count} runs · newest first',
    'evalRuns.live': 'a run is in flight, the list refreshes itself',

    'evalRuns.status.running': 'running',
    'evalRuns.status.done': 'done',
    'evalRuns.status.failed': 'failed',
    'evalRuns.progress': '{done} of {total} turns',
    'evalRuns.result': '{turns} turns · avg score {score}',
    'evalRuns.noConfig': 'no configuration id',
    'evalRuns.personas': '{count} personas',
    'evalRuns.intents': '{count} intents',
    'evalRuns.delete': 'Delete',
    'evalRuns.deleteFor': 'Delete — run {id}',
    'evalRuns.deleteBlocked': 'A run in flight cannot be deleted',
  },
};
