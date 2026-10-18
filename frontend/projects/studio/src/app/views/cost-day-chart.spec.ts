import { describe, expect, it } from 'vitest';

import type { UsageDay } from '../core/usage-api.service';
import { costDayChart } from './cost-day-chart';

const tag = (t: string, amount: string | null, calls = 1, unvollstaendig = false): UsageDay =>
  ({ tag: t, calls, amount, unvollstaendig });

describe('costDayChart (Paket 16, D2)', () => {
  it('eine Säule je Tag, die höchste füllt die Zeichenfläche', () => {
    const c = costDayChart([tag('2026-03-09', '1'), tag('2026-03-10', '4'), tag('2026-03-11', '0', 0)]);
    expect(c.bars).toHaveLength(3);
    expect(c.max).toBe(4);
    const hoechste = c.bars[1];
    expect(hoechste.y).toBe(c.pad);
    expect(hoechste.height).toBe(c.height - 2 * c.pad);
    expect(c.bars[0].height).toBeCloseTo(hoechste.height / 4, 1);
    expect(c.bars[2].height).toBe(0);
    // Gleich breit, in Reihenfolge, ohne Überlappung.
    expect(c.bars[1].x).toBeGreaterThan(c.bars[0].x + c.bars[0].width);
  });

  it('ein Tag mit Zügen, aber ohne Preis bekommt keine Höhe, sondern eine Marke', () => {
    const c = costDayChart([tag('2026-03-09', '2'), tag('2026-03-10', null, 3, true)]);
    expect(c.bars[1].ohnePreis).toBe(true);
    expect(c.bars[1].height).toBe(0);
    expect(c.bars[0].ohnePreis).toBe(false);
  });

  it('ohne einen Cent bleibt die Achse bei null, ohne durch null zu teilen', () => {
    const c = costDayChart([tag('2026-03-09', '0', 0)]);
    expect(c.max).toBe(0);
    expect(c.bars[0].height).toBe(0);
    expect(Number.isFinite(c.bars[0].y)).toBe(true);
  });

  it('gibt einem Tag mit kleinen Kosten mindestens einen Pixel (Review PR #18)', () => {
    const c = costDayChart([tag('2026-03-09', '100'), tag('2026-03-10', '0.001')]);
    expect(c.bars[1].height).toBeGreaterThanOrEqual(1);
    expect(c.bars[1].y).toBeCloseTo(c.height - c.pad - c.bars[1].height, 5);
  });
});
