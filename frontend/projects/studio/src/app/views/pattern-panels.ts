/**
 * The pattern panels of a run (ST-7d): shaping `summary.classification_metrics`
 * for the Studio — pure, like `gold-scorecard.ts`.
 *
 * The backend has written these figures since P7 (`services/eval/metrics.py`);
 * ALT showed them as key figures, confusion matrices and tool compliance per
 * pattern, NEU did not show them at all. They describe how the pattern engine
 * classifies and picks — for an agent run there is nothing to show.
 *
 * The summary is free-form JSON, so every value is read defensively: a
 * missing or foreign value becomes "not measured", never NaN on the page.
 */

export interface PatternKpi {
  readonly key: 'pattern' | 'hint' | 'tools' | 'persona' | 'intent';
  /** 0…1, or `null` when the run did not measure it. */
  readonly value: number | null;
  /** How many turns the value rests on. */
  readonly basis: number;
  /** Only for `pattern`: the share the judge rated fully fitting. */
  readonly sub?: number | null;
}

export interface ConfusionCell {
  readonly n: number;
  readonly diagonal: boolean;
}

export interface ConfusionTable {
  readonly rows: readonly string[];
  readonly cols: readonly string[];
  readonly cells: readonly (readonly ConfusionCell[])[];
}

export interface ToolComplianceRow {
  readonly pattern: string;
  readonly ok: number;
  readonly total: number;
  readonly rate: number | null;
}

type Json = Readonly<Record<string, unknown>>;

function record(value: unknown): Json {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Json : {};
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function rate(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * The key figures, as ALT showed them — all as hit rates, so they can stand
 * side by side. A pattern "hit" is a judge rating of at least 1 (fitting); 0
 * means "clearly the wrong pattern". The strict "fully fitting" (2) rides along
 * as `sub` instead of competing as a second headline.
 */
export function patternKpis(metrics: Json): readonly PatternKpi[] {
  const judged = count(metrics['judged_turns']);
  const misses = count(record(metrics['pattern_match_score_distribution'])['0']);
  return [
    { key: 'pattern', value: judged ? (judged - misses) / judged : null, basis: judged,
      sub: rate(metrics['engine_pattern_judge_ok_rate']) },
    { key: 'hint', value: rate(metrics['llm_engine_match_rate']),
      basis: count(metrics['llm_hint_present_count']) },
    { key: 'tools', value: rate(metrics['tool_compliance_rate']),
      basis: count(metrics['tool_compliance_total']) },
    { key: 'persona', value: rate(metrics['persona_correct_rate']),
      basis: count(metrics['persona_total_judged']) },
    { key: 'intent', value: rate(metrics['intent_correct_rate']),
      basis: count(metrics['intent_total_judged']) },
  ];
}

/** A confusion matrix `{expected: {got: n}}` as rows × columns, or `null`
 *  when nothing was counted. */
export function confusionTable(data: unknown): ConfusionTable | null {
  const matrix = record(data);
  const rows = Object.keys(matrix).sort();
  const cols = [...new Set(rows.flatMap((row) => Object.keys(record(matrix[row]))))].sort();
  if (rows.length === 0 || cols.length === 0) return null;
  return {
    rows,
    cols,
    cells: rows.map((row) => cols.map((col) => ({
      n: count(record(matrix[row])[col]), diagonal: row === col,
    }))),
  };
}

/** Tool compliance per pattern, the most frequent first. */
export function toolComplianceRows(metrics: Json): readonly ToolComplianceRow[] {
  return Object.entries(record(metrics['tool_compliance_per_pattern']))
    .map(([pattern, cell]) => {
      const ok = count(record(cell)['ok']);
      const total = count(record(cell)['total']);
      return { pattern, ok, total, rate: total ? ok / total : null };
    })
    .sort((a, b) => b.total - a.total || a.pattern.localeCompare(b.pattern));
}
