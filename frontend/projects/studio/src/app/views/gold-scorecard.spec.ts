import { describe, expect, it } from 'vitest';

import { catLabel, flowGroups, hardRate, type GoldPerTurn } from './gold-scorecard';

const turn = (flow: string, no: number, over: Partial<GoldPerTurn> = {}): GoldPerTurn => ({
  flow, title: `Titel ${flow}`, turn: no, message: `m${no}`,
  expected: {}, observed: {},
  checks: { persona: true, intent: true, register: null, structure: true, qr: true, host: null },
  ...over,
});

describe('flowGroups', () => {
  it('keeps the order the run produced and groups by flow', () => {
    const groups = flowGroups([
      turn('GS-1', 1), turn('GS-1', 2), turn('GS-3', 1), turn('GS-1', 3),
    ]);

    expect(groups.map((g) => g.flow)).toEqual(['GS-1', 'GS-3']);
    // A flow whose turns are not contiguous still lands in one group, and the
    // group keeps the position of its FIRST turn.
    expect(groups[0].turns.map((t) => t.turn)).toEqual([1, 2, 3]);
    expect(groups[0].title).toBe('Titel GS-1');
  });

  it('is empty for a run without judged turns', () => {
    expect(flowGroups([])).toEqual([]);
  });
});

describe('hardRate', () => {
  it('counts the five hard categories and leaves host out', () => {
    const entry = {
      title: 'Flow Eins',
      // `persona` is the CATEGORY cell, not the persona id — the backend's dict
      // spread overwrites the id it appears to set (see GoldPerFlow).
      persona: { ok: 2, total: 2 }, intent: { ok: 1, total: 2 },
      register: { ok: 1, total: 1 }, structure: { ok: 0, total: 1 },
      qr: { ok: 2, total: 2 },
      // Soft: reported beside the hard rate, never inside it.
      host: { ok: 0, total: 5 },
    } as unknown as Parameters<typeof hardRate>[0];

    expect(hardRate(entry)).toEqual({ ok: 6, total: 8, rate: 0.75 });
  });

  it('reports no rate rather than 0 when nothing was asserted', () => {
    const entry = {
      persona: { ok: 0, total: 0 }, intent: { ok: 0, total: 0 },
      register: { ok: 0, total: 0 }, structure: { ok: 0, total: 0 },
      qr: { ok: 0, total: 0 },
    } as unknown as Parameters<typeof hardRate>[0];

    // 0/0 is "not measured", and a 0 % would read as "everything failed".
    expect(hardRate(entry)).toEqual({ ok: 0, total: 0, rate: null });
  });

  it('survives a flow entry that is missing categories', () => {
    const entry = { persona: { ok: 1, total: 1 } } as unknown as Parameters<typeof hardRate>[0];

    expect(hardRate(entry)).toEqual({ ok: 1, total: 1, rate: 1 });
  });
});

describe('catLabel', () => {
  it('names the six categories in German', () => {
    expect(catLabel('register')).toBe('Tonalität');
    expect(catLabel('qr')).toBe('Quick-Replies');
    expect(catLabel('host')).toBe('Link-Host');
  });

  it('falls back to the raw key so a new category is visible, not hidden', () => {
    expect(catLabel('brandneu')).toBe('brandneu');
  });
});
