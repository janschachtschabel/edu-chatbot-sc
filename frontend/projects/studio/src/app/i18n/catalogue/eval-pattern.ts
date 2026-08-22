/**
 * Die Pattern-Nutzung (C1-d4b3) — die dritte und letzte Ansicht der Evaluation
 * mit eigenem Teil, nach `evaluation.ts` (Hülle + Lauf-Liste) und
 * `eval-detail.ts` (Lauf-Detail). Der Schnitt läuft entlang der Ansicht.
 *
 * NICHT hier, und zwar aus je einem eigenen Grund:
 *
 *  - **Der Name der Ansicht.** Er steht seit C1-d4b1 als `eval.tab.pattern` im
 *    Reiter der Hülle. Ein zweiter Eintrag mit demselben Wortlaut wäre eine
 *    Doppelung, die `en.spec.ts` bauartbedingt NICHT fände: der Test vergleicht
 *    Deutsch gegen Englisch je Schlüssel, nie Schlüssel gegeneinander.
 *  - **Die drei Texte der Balken-Tabelle** (`bars.*`, `label.unclassified`).
 *    `QualityBarsComponent` steht in drei Ansichten an sieben Stellen und
 *    übersetzt sie selbst; sie wohnen deshalb in `shared.ts`.
 *  - **„Aktualisieren"** und sein Ladezustand: `action.refresh` /
 *    `action.refreshing`, ebenfalls aus `shared.ts`.
 *
 * **Zwei Sätze tragen Auszeichnung mitten im Satz** (C1-d4b2): der Einstieg
 * nennt die Tabelle `quality_logs`, und die Summenzeile hebt die Anzahl hervor.
 * Die Summenzeile braucht dafür `richPlural()` — Mehrzahl UND Auszeichnung,
 * und zwar in dieser Reihenfolge, damit ein eingesetzter Wert keine
 * Auszeichnung erzeugen kann.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_PATTERN: CataloguePart = {
  de: {
    // ── Einstieg ────────────────────────────────────────────────────
    'evalPattern.intro':
      'Gezählt aus `quality_logs`, also unabhängig vom Eval-Motor: hier stehen '
      + 'echte Turns genauso wie Eval-Turns. Der Bereich entscheidet, welche '
      + 'Frage die Zahlen beantworten.',

    // ── Filter ──────────────────────────────────────────────────────
    'evalPattern.scope.label': 'Bereich',
    'evalPattern.scope.all': 'alle Turns',
    'evalPattern.scope.eval': 'nur Eval-Läufe',
    'evalPattern.scope.production': 'nur echte Nutzung',
    'evalPattern.since.label': 'Ab Datum',
    'evalPattern.since.hint': 'leer = das ganze Log',
    // Feedback 2026-08-22: AGENT/HYBRID sind Maschinen-Marker, keine Muster —
    // der Umschalter trennt die Betriebsarten, client-seitig.
    'evalPattern.engine.label': 'Betriebsart',
    'evalPattern.engine.all': 'alle Betriebsarten',
    'evalPattern.engine.muster': 'nur Muster (M01–M20)',
    'evalPattern.engine.agent': 'nur Agent-Schleife',
    'evalPattern.engine.hybrid': 'nur Hybrid',
    'evalPattern.engine.none':
      'Keine Turns dieser Betriebsart im gewählten Bereich.',

    // ── Zustand ─────────────────────────────────────────────────────
    'evalPattern.empty':
      'Noch keine Turns in diesem Bereich. Ein Chat oder ein Eval-Lauf füllt '
      + 'das Log; ein „Ab Datum" in der Zukunft leert es auch.',

    // ── Summenzeile ─────────────────────────────────────────────────
    /** Zwei Anzahlen in einem Satz, jede mit eigener Mehrzahl. Die innere
     *  steht deshalb als fertige Wortgruppe in `{combos}` — dieselbe Bauart
     *  wie `evalRuns.ask.filtered`, wo der Filtername eingesetzt wird. */
    'evalPattern.total.one': '*{count} Turn* in {combos}.',
    'evalPattern.total.other': '*{count} Turns* in {combos}.',
    'evalPattern.combos.one': '{count} Kombination aus Pattern, Intent und Persona',
    'evalPattern.combos.other': '{count} Kombinationen aus Pattern, Intent und Persona',

    // ── Verteilungen ────────────────────────────────────────────────
    'evalPattern.bars.pattern': 'Turns je Pattern',
    'evalPattern.bars.intent': 'Turns je Intent',

    // ── Matrix (ALT-Auswertung, Feedback 2026-08-22) ────────────────
    'evalPattern.matrix.caption':
      'Turns je Pattern × Persona — wer löst welches Verhalten aus. Zeilen '
      + 'und Spalten nach Turn-Summe sortiert.',
    'evalPattern.matrix.sum': 'Summe',

    // ── Tabelle ─────────────────────────────────────────────────────
    'evalPattern.table.caption':
      'Jede Kombination einzeln, häufigste zuerst. Die Konfidenz ist der '
      + 'Mittelwert der Turns dieser Kombination.',
    'evalPattern.col.pattern': 'Pattern',
    'evalPattern.col.intent': 'Intent',
    'evalPattern.col.persona': 'Persona',
    'evalPattern.col.turns': 'Turns',
    'evalPattern.col.confidence': 'Ø Konfidenz',
  },

  en: {
    'evalPattern.intro':
      'Counted from `quality_logs`, so independently of the eval engine: real '
      + 'turns sit here alongside eval turns. The scope decides which question '
      + 'the numbers answer.',

    'evalPattern.scope.label': 'Scope',
    'evalPattern.scope.all': 'all turns',
    'evalPattern.scope.eval': 'eval runs only',
    'evalPattern.scope.production': 'real usage only',
    'evalPattern.since.label': 'From date',
    'evalPattern.since.hint': 'empty = the whole log',
    'evalPattern.engine.label': 'Mode',
    'evalPattern.engine.all': 'all modes',
    'evalPattern.engine.muster': 'patterns only (M01-M20)',
    'evalPattern.engine.agent': 'agent loop only',
    'evalPattern.engine.hybrid': 'hybrid only',
    'evalPattern.engine.none': 'No turns of this mode in the chosen scope.',

    'evalPattern.empty':
      'No turns in this scope yet. A chat or an eval run fills the log; a '
      + '“from date” in the future empties it as well.',

    'evalPattern.total.one': '*{count} turn* in {combos}.',
    'evalPattern.total.other': '*{count} turns* in {combos}.',
    'evalPattern.combos.one': '{count} combination of pattern, intent and persona',
    'evalPattern.combos.other': '{count} combinations of pattern, intent and persona',

    'evalPattern.bars.pattern': 'Turns per pattern',
    'evalPattern.bars.intent': 'Turns per intent',

    'evalPattern.matrix.caption':
      'Turns per pattern and persona — who triggers which behaviour. Rows and '
      + 'columns sorted by turn total.',
    'evalPattern.matrix.sum': 'Total',

    'evalPattern.table.caption':
      'Every combination on its own, most frequent first. The confidence is '
      + 'the average over the turns of that combination.',
    'evalPattern.col.pattern': 'Pattern',
    'evalPattern.col.intent': 'Intent',
    'evalPattern.col.persona': 'Persona',
    'evalPattern.col.turns': 'Turns',
    'evalPattern.col.confidence': 'Avg confidence',
  },
};
