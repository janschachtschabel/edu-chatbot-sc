import { describe, expect, it } from 'vitest';

import { latencyChart } from './loadtest-chart';
import { type StageResult } from '../core/loadtest-api.service';

function stage(concurrency: number, p50: number, p95: number, errors = 0): StageResult {
  return {
    concurrency, requests: 8, ok: 8 - errors, errors, error_kinds: [],
    p50_s: p50, p95_s: p95, max_s: p95, mean_s: p50, duration_s: 10, rps: 0.8, by_kind: {},
  };
}

describe('latencyChart', () => {
  it('spreads the stages across the plot in order', () => {
    const chart = latencyChart([stage(1, 2, 3), stage(2, 3, 5), stage(4, 6, 11)], 20);
    const xs = chart.points.map((p) => p.x);
    expect(xs[0]).toBeLessThan(xs[1]);
    expect(xs[1]).toBeLessThan(xs[2]);
    expect(xs[0]).toBe(chart.pad);
    expect(xs[2]).toBe(chart.width - chart.pad);
  });

  it('centres a single stage instead of dividing by zero', () => {
    // ALT divided by `stages.length - 1`; one stage produced NaN coordinates
    // and SVG silently drew nothing.
    const chart = latencyChart([stage(1, 2, 3)], 20);
    expect(chart.points[0].x).toBe(chart.width / 2);
    expect(Number.isFinite(chart.points[0].y95)).toBe(true);
    expect(chart.p95Line).not.toContain('NaN');
  });

  it('puts a higher latency higher up the chart', () => {
    const chart = latencyChart([stage(1, 2, 3), stage(2, 4, 12)], 20);
    expect(chart.points[1].y95).toBeLessThan(chart.points[0].y95);
    expect(chart.points[0].y95).toBeLessThan(chart.points[0].y50);
  });

  it('keeps a latency above the threshold inside the drawing area', () => {
    // The scale follows the worst p95, not the threshold, so a run that blows
    // past the limit still has its knee on screen.
    const chart = latencyChart([stage(1, 2, 3), stage(8, 30, 90)], 20);
    for (const p of chart.points) {
      expect(p.y95).toBeGreaterThanOrEqual(0);
      expect(p.y95).toBeLessThanOrEqual(chart.height);
    }
    expect(chart.thresholdY).toBeGreaterThan(chart.points[1].y95);
  });

  it('carries the numbers the labels need', () => {
    const chart = latencyChart([stage(4, 6, 11, 2)], 20);
    expect(chart.points[0]).toMatchObject({ concurrency: 4, p95: 11, errors: 2 });
    expect(chart.thresholdS).toBe(20);
  });

  it('survives a run with no finished stage yet', () => {
    const chart = latencyChart([], 20);
    expect(chart.points).toEqual([]);
    expect(chart.p95Line).toBe('');
    expect(Number.isFinite(chart.thresholdY)).toBe(true);
  });
});
