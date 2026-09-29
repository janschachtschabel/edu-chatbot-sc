import { describe, expect, it } from 'vitest';

import { confusionTable, patternKpis, toolComplianceRows } from './pattern-panels';

/** So sieht `summary.classification_metrics` eines Muster-Gold-Laufs aus
 *  (gekürzt aus eval-5c14bfc268fa, 2026-09-27). */
const GOLD_MUSTER: Record<string, unknown> = {
  judged_turns: 41,
  pattern_match_score_distribution: { 0: 0, 1: 3, 2: 38 },
  engine_pattern_judge_ok_rate: 0.927,
  llm_engine_match_rate: 1,
  llm_hint_present_count: 39,
  tool_compliance_rate: 0.85,
  tool_compliance_total: 20,
  persona_correct_rate: null,
  persona_total_judged: 0,
  intent_correct_rate: null,
  intent_total_judged: 0,
  pattern_confusion_llm_vs_engine: { M06: { M06: 10 }, M04: { M04: 11, M05: 1 } },
  tool_compliance_per_pattern: {
    M05: { ok: 4, total: 4 }, M06: { ok: 10, total: 10 }, M10: { ok: 0, total: 3 },
  },
};

describe('patternKpis (ST-7d)', () => {
  it('zählt einen Muster-Treffer ab „passend" (Judge ≥ 1) und nennt „voll passend" dazu', () => {
    const muster = patternKpis(GOLD_MUSTER).find((k) => k.key === 'pattern')!;
    expect(muster.value).toBe(1);        // 41 bewertet, keiner mit 0
    expect(muster.basis).toBe(41);
    expect(muster.sub).toBe(0.927);
  });

  it('trägt Hinweis = Endwahl, Werkzeugtreue, Persona und Intent mit ihrer Basis', () => {
    const k = Object.fromEntries(patternKpis(GOLD_MUSTER).map((kpi) => [kpi.key, kpi]));
    expect([k['hint'].value, k['hint'].basis]).toEqual([1, 39]);
    expect([k['tools'].value, k['tools'].basis]).toEqual([0.85, 20]);
    // Gold-Flows v2 geben kein Persona-/Intent-Soll vor — nicht gemessen, nicht 0.
    expect(k['persona'].value).toBeNull();
    expect(k['intent'].value).toBeNull();
  });

  it('kennt ohne Judge keine Muster-Trefferquote', () => {
    const muster = patternKpis({ judged_turns: 0 }).find((k) => k.key === 'pattern')!;
    expect(muster.value).toBeNull();
  });

  it('übersteht fremde Werte, statt NaN zu zeigen', () => {
    const kpis = patternKpis({ judged_turns: 'viele', tool_compliance_rate: 'hoch' });
    expect(kpis.every((kpi) => kpi.value === null || Number.isFinite(kpi.value))).toBe(true);
  });
});

describe('confusionTable (ST-7d)', () => {
  it('sortiert Zeilen und Spalten und markiert die Diagonale', () => {
    const tafel = confusionTable(GOLD_MUSTER['pattern_confusion_llm_vs_engine'])!;
    expect(tafel.rows).toEqual(['M04', 'M06']);
    expect(tafel.cols).toEqual(['M04', 'M05', 'M06']);
    expect(tafel.cells[0]).toEqual([
      { n: 11, diagonal: true }, { n: 1, diagonal: false }, { n: 0, diagonal: false },
    ]);
  });

  it('ist leer, wenn nichts gezählt wurde', () => {
    expect(confusionTable({})).toBeNull();
    expect(confusionTable(undefined)).toBeNull();
    expect(confusionTable('kaputt')).toBeNull();
  });
});

describe('toolComplianceRows (ST-7d)', () => {
  it('stellt die häufigsten Muster zuerst und rechnet die Quote', () => {
    expect(toolComplianceRows(GOLD_MUSTER)).toEqual([
      { pattern: 'M06', ok: 10, total: 10, rate: 1 },
      { pattern: 'M05', ok: 4, total: 4, rate: 1 },
      { pattern: 'M10', ok: 0, total: 3, rate: 0 },
    ]);
  });
});
