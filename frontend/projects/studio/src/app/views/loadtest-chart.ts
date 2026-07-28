/**
 * Geometry for the latency-vs-concurrency chart (9-5e) — pure, so the shape can
 * be tested without a DOM.
 *
 * The chart answers the one question the view exists for: up to how many
 * parallel users does p95 stay under the threshold. The stage table carries the
 * same numbers; the line is what makes the knee visible.
 *
 * ALT computed these coordinates inline in JSX with `stages.length - 1` in a
 * divisor — a single-stage run divided by zero and put every point at NaN,
 * which SVG renders as nothing at all.
 */
import { type StageResult } from '../core/loadtest-api.service';

const WIDTH = 560;
const HEIGHT = 220;
const PAD = 44;

export interface ChartPoint {
  readonly x: number;
  readonly y50: number;
  readonly y95: number;
  readonly concurrency: number;
  readonly p95: number;
  readonly errors: number;
}

export interface LatencyChart {
  readonly width: number;
  readonly height: number;
  readonly pad: number;
  readonly points: readonly ChartPoint[];
  /** `polyline` point lists. */
  readonly p50Line: string;
  readonly p95Line: string;
  readonly thresholdY: number;
  readonly thresholdS: number;
}

export function latencyChart(
  stages: readonly StageResult[], thresholdS: number,
): LatencyChart {
  const maxY = Math.max(thresholdS, ...stages.map((s) => s.p95_s), 1) * 1.15;
  const plotWidth = WIDTH - 2 * PAD;

  const xAt = (index: number): number =>
    // A single stage sits in the middle instead of dividing by zero.
    stages.length < 2 ? PAD + plotWidth / 2 : PAD + (index / (stages.length - 1)) * plotWidth;
  const yAt = (value: number): number => HEIGHT - PAD - (value / maxY) * (HEIGHT - 2 * PAD);

  const points = stages.map((stage, index) => ({
    x: round(xAt(index)),
    y50: round(yAt(stage.p50_s)),
    y95: round(yAt(stage.p95_s)),
    concurrency: stage.concurrency,
    p95: stage.p95_s,
    errors: stage.errors,
  }));

  return {
    width: WIDTH,
    height: HEIGHT,
    pad: PAD,
    points,
    p50Line: points.map((p) => `${p.x},${p.y50}`).join(' '),
    p95Line: points.map((p) => `${p.x},${p.y95}`).join(' '),
    thresholdY: round(yAt(thresholdS)),
    thresholdS,
  };
}

/** Two decimals is below a pixel and keeps the emitted path readable. */
function round(value: number): number {
  return Math.round(value * 100) / 100;
}
