import { describe, expect, it } from 'vitest';

import { rateChart, scoreChart } from './trend-chart';

const P = (value: number) => ({ run_id: 'r', created_at: '', value });

describe('rateChart', () => {
  it('spans the full plot width across the points', () => {
    const c = rateChart([P(0), P(0.5), P(1)]);
    const xs = c.points.map((p) => p.x);
    expect(xs[0]).toBe(c.pad);
    expect(xs[2]).toBe(c.width - c.pad);
    expect(xs[1]).toBeGreaterThan(xs[0]);
    expect(xs[1]).toBeLessThan(xs[2]);
  });

  it('puts a single point in the middle instead of dividing by zero', () => {
    // The loadtest chart had exactly this bug: `length - 1` as a divisor put
    // every coordinate at NaN, which SVG renders as nothing at all.
    const c = rateChart([P(0.4)]);
    expect(c.points[0].x).toBe(c.pad + (c.width - 2 * c.pad) / 2);
    expect(Number.isNaN(c.points[0].y)).toBe(false);
  });

  it('maps a rate of 0 to the baseline and 1 to the top', () => {
    const c = rateChart([P(0), P(1)]);
    expect(c.points[0].y).toBe(c.height - c.pad);
    expect(c.points[1].y).toBe(c.pad);
  });

  it('uses a fixed 0..1 axis so two series stay comparable', () => {
    // Auto-scaling each series to its own max would make a 2 % series look
    // identical to a 90 % one.
    const flat = rateChart([P(0.02), P(0.03)]);
    expect(flat.points[0].y).toBeGreaterThan(flat.height * 0.7);
  });

  it('emits a polyline string and keeps the raw values for the label', () => {
    const c = rateChart([P(0.25), P(0.75)]);
    expect(c.line.split(' ')).toHaveLength(2);
    expect(c.points.map((p) => p.value)).toEqual([0.25, 0.75]);
  });

  it('reads pattern series that carry `rate` instead of `value`', () => {
    const c = rateChart([{ run_id: 'r', created_at: '', rate: 0.5, ok: 1, total: 2 }]);
    expect(c.points[0].value).toBe(0.5);
  });

  it('treats a point without any number as zero rather than NaN', () => {
    const c = rateChart([{ run_id: 'r', created_at: '' }]);
    expect(c.points[0].value).toBe(0);
    expect(Number.isNaN(c.points[0].y)).toBe(false);
  });

  it('has no points for an empty series', () => {
    const c = rateChart([]);
    expect(c.points).toEqual([]);
    expect(c.line).toBe('');
  });
});

describe('scoreChart', () => {
  const R = (avg: number | null) => ({
    id: 'r', created_at: '', mode: 'golden', config_slug: '',
    total_turns: 1, avg_score: avg,
  });

  it('scales to the highest score present, not to a fixed 1.0', () => {
    // Judge totals are 0..1 in practice but the axis must not clip a run that
    // scores above the others; the top point always sits on the top edge.
    const c = scoreChart([R(0.2), R(0.6)]);
    expect(c.points[1].y).toBe(c.pad);
  });

  it('skips runs without a score instead of plotting them as zero', () => {
    // A run whose score is null was never judged — drawing it at 0 would read
    // as "scored terribly".
    const c = scoreChart([R(0.5), R(null), R(0.7)]);
    expect(c.points).toHaveLength(2);
    expect(c.points.map((p) => p.value)).toEqual([0.5, 0.7]);
  });

  it('is empty when no run carries a score', () => {
    const c = scoreChart([R(null)]);
    expect(c.points).toEqual([]);
    expect(c.line).toBe('');
  });
});
