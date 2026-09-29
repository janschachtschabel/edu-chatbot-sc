/**
 * The rows of the engine comparison (ST-7c) — K0-1's report table as data.
 *
 * Pure, like `gold-scorecard.ts`: which number goes into which row, and how a
 * missing one looks, is the part that would silently lie if it drifted, so it
 * is tested without a DOM. The row order follows the K0 report
 * (`evals/engine_matrix_report.py`) so the Studio and the files on disk read
 * the same way.
 *
 * A value the backend did not measure is `–`, never 0: one run has no spread
 * and no repeat agreement, a model without a price has no cost. Separators and
 * ranges are typography, not text, and stay out of the catalogue.
 */
import { JUDGE_AXES, type EngineComparison, type EngineSummary } from '../core/eval-profile';
import type { StudioFormat } from '../i18n/studio-format.service';
import type { Translate } from '../i18n/studio-language.service';

export type CompareFormat = Pick<StudioFormat, 'decimal' | 'percent' | 'seconds' | 'whole' | 'money'>;

export interface CompareRow {
  readonly key: string;
  readonly label: string;
  /** What a number means where the label alone does not say it. */
  readonly hint?: string;
  /** One cell per column, in the order of the columns. */
  readonly cells: readonly string[];
}

const ENGINE_ORDER = ['pattern', 'agent', 'hybrid'];
const DASH = '–';
const SEP = ' / ';
/** Enough places for any cost per turn; `toFixed` never writes "1e-7". */
const MONEY_PLACES = 12;
/** Rows whose number needs a sentence: the four that only repeats can give. */
const HINTED = new Set(['agreement', 'toolJaccard', 'textSimilarity', 'judgeSpread']);

/** The columns: pattern engine first, then the agent loop, anything else after. */
export function engineColumns(engines: Readonly<Record<string, unknown>>): string[] {
  const rank = (engine: string): number => {
    const index = ENGINE_ORDER.indexOf(engine);
    return index === -1 ? ENGINE_ORDER.length : index;
  };
  return Object.keys(engines).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

export function compareRows(
  comparison: EngineComparison, columns: readonly string[],
  fmt: CompareFormat, t: Translate,
): CompareRow[] {
  const summaries = columns.map((engine) => comparison.engines[engine]);
  const pct = (v: number | null): string => (v === null ? DASH : fmt.percent(v, 0));
  const dec = (v: number | null): string => (v === null ? DASH : fmt.decimal(v));
  const sec = (v: number | null): string => (v === null ? DASH : fmt.seconds(v));
  const num = (v: number | null): string => (v === null ? DASH : fmt.whole(Math.round(v)));
  const row = (
    key: string, cell: (s: EngineSummary) => string, label?: string,
  ): CompareRow => ({
    key,
    label: label ?? t(`evalCompare.row.${key}`),
    hint: HINTED.has(key) ? t(`evalCompare.hint.${key}`) : undefined,
    cells: summaries.map(cell),
  });

  const hardRate = (s: EngineSummary): string => {
    const value = pct(s.quality.hard_rate);
    const runs = s.hard_rate_runs.filter((r): r is number => r !== null);
    if (runs.length < 2 || s.quality.hard_rate === null) return value;
    return `${value} (${pct(Math.min(...runs))}–${pct(Math.max(...runs))})`;
  };
  const cost = (s: EngineSummary): string => {
    const perTurn = s.cost.cost_per_turn;
    return perTurn === null || !comparison.currency
      ? DASH : fmt.money(perTurn.toFixed(MONEY_PLACES), comparison.currency);
  };

  return [
    row('runs', (s) => fmt.whole(s.runs)),
    row('hardRate', hardRate),
    ...JUDGE_AXES.map((axis) => row(
      `axis.${axis}`, (s) => dec(s.quality.axes[axis] ?? null),
      t('evalCompare.row.axis', { axis: t(`evalProfile.axis.${axis}`) }))),
    row('agreement', (s) => pct(s.determinism.check_agreement)),
    row('toolJaccard', (s) => dec(s.determinism.tool_jaccard)),
    row('textSimilarity', (s) => dec(s.determinism.text_similarity)),
    row('judgeSpread', (s) => dec(s.determinism.judge_spread)),
    row('speed', (s) => `${sec(s.speed.p50_ms)}${SEP}${sec(s.speed.p95_ms)}`),
    row('over30', (s) => pct(s.speed.over_30s)),
    row('over90', (s) => num(s.speed.over_90s)),
    row('tokens', (s) => [s.cost.prompt, s.cost.cached, s.cost.completion].map(num).join(SEP)),
    row('costPerTurn', cost),
    row('robustness', (s) => [s.robustness.chat_errors, s.robustness.judge_failed,
                              s.robustness.empty, s.robustness.fallback].map(num).join(SEP)),
    row('safe', (s) => pct(s.safe.hard_rate)),
    row('frei', (s) => `${pct(s.frei.hard_rate)}${SEP}${dec(s.frei.axes['auftrag_erfuellt'] ?? null)}`),
  ];
}
