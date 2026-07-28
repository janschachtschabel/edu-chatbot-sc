/**
 * Geometry for the eval trend charts (9-5d) — pure, so the shape is testable
 * without a DOM. Sibling of `loadtest-chart.ts`, same reasoning.
 *
 * Two axis rules, both deliberate:
 *
 * - **rates** use a FIXED 0..1 axis. Auto-scaling each series to its own
 *   maximum would draw a 2 % cache-hit rate exactly like a 90 % one, and these
 *   charts sit next to each other precisely so they can be compared.
 * - **scores** scale to the highest score present. A judge total is 0..1 in
 *   practice, but the number is a sum over five axes and nothing guarantees the
 *   ceiling; clipping would silently hide the best run.
 *
 * A run whose `avg_score` is null was never judged. It is skipped, not plotted
 * at zero — zero reads as "scored terribly", which is a different claim.
 */
import { type EvalTrends, type TrendPoint } from '../core/eval-api.service';

const WIDTH = 260;
const HEIGHT = 96;
const PAD = 8;

export interface TrendPointXY {
  readonly x: number;
  readonly y: number;
  readonly value: number;
  readonly runId: string;
  readonly createdAt: string;
}

export interface TrendChart {
  readonly width: number;
  readonly height: number;
  readonly pad: number;
  readonly points: readonly TrendPointXY[];
  /** `polyline` point list; `''` when there is nothing to draw. */
  readonly line: string;
  /** Upper axis bound — 1 for rates, the series maximum for scores. */
  readonly maxY: number;
}

/** The value a trend point carries: rate series use `rate`, the rest `value`. */
function pointValue(point: TrendPoint): number {
  return point.value ?? point.rate ?? 0;
}

function build(
  values: readonly { value: number; runId: string; createdAt: string }[],
  maxY: number,
): TrendChart {
  const plotWidth = WIDTH - 2 * PAD;
  const plotHeight = HEIGHT - 2 * PAD;
  const points = values.map((entry, index) => ({
    // A single point sits in the middle instead of dividing by zero.
    x: round(values.length < 2
      ? PAD + plotWidth / 2
      : PAD + (index / (values.length - 1)) * plotWidth),
    y: round(HEIGHT - PAD - (maxY > 0 ? entry.value / maxY : 0) * plotHeight),
    value: entry.value,
    runId: entry.runId,
    createdAt: entry.createdAt,
  }));
  return {
    width: WIDTH,
    height: HEIGHT,
    pad: PAD,
    points,
    line: points.map((p) => `${p.x},${p.y}`).join(' '),
    maxY,
  };
}

/** One 0..1 rate series over the run timeline. */
export function rateChart(series: readonly TrendPoint[]): TrendChart {
  return build(
    series.map((point) => ({
      value: pointValue(point),
      runId: point.run_id,
      createdAt: point.created_at,
    })),
    1,
  );
}

/** Average judge score per completed run; unjudged runs are left out. */
export function scoreChart(runs: EvalTrends['runs']): TrendChart {
  const scored = runs
    .filter((run) => run.avg_score !== null)
    .map((run) => ({
      value: run.avg_score as number,
      runId: run.id,
      createdAt: run.created_at,
    }));
  const maxY = Math.max(...scored.map((s) => s.value), 0);
  return build(scored, maxY);
}

/** Two decimals is below a pixel and keeps the emitted path readable. */
function round(value: number): number {
  return Math.round(value * 100) / 100;
}
