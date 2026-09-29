import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import type { EngineComparison, EngineSummary } from '../core/eval-profile';
import {
  formatDecimal, formatMoney, formatPercent, formatSeconds, formatWhole,
} from '../core/format';
import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { Translate } from '../i18n/studio-language.service';
import { type CompareFormat, compareRows, engineColumns } from './compare-rows';

const NBSP = '\u00a0';

const übersetzer = (locale: 'de' | 'en'): Translate => {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  return (key, params) => i18n.t(key, params);
};

const format = (locale: string): CompareFormat => ({
  decimal: (v) => formatDecimal(locale, v),
  percent: (v, digits) => formatPercent(locale, v, digits),
  seconds: (ms) => formatSeconds(locale, ms),
  whole: (v) => formatWhole(locale, v),
  money: (amount, currency) => formatMoney(locale, amount, currency),
});

const QUALITY = {
  hard_rate: 0.95, hard_passed: 95, hard_total: 100,
  axes: {
    auftrag_erfuellt: 1.4, intent_fit: 1.8, persona_tone: 1.1,
    info_quality: 1.5, safety: 2, pattern_match: null,
  },
};

function summary(over: Partial<EngineSummary> = {}): EngineSummary {
  return {
    runs: 3,
    quality: QUALITY,
    hard_rate_runs: [0.93, 0.95, 0.97],
    determinism: {
      turns_compared: 40, check_agreement: 0.8, tool_jaccard: 0.85,
      text_similarity: 0.72, judge_spread: 0.31,
    },
    speed: { p50_ms: 12340, p95_ms: 21800, over_30s: 0.05, over_90s: 0 },
    cost: {
      turns_with_usage: 40, prompt: 62821, cached: 55462, completion: 927,
      cost_per_turn: 0.0018, cost_total: 0.21, price_unavailable: [],
    },
    robustness: { turns: 126, chat_errors: 0, judge_failed: 1, empty: 0, fallback: 2 },
    safe: { ...QUALITY, hard_rate: 1 },
    frei: { ...QUALITY, hard_rate: 0.9, axes: { ...QUALITY.axes, auftrag_erfuellt: 1.2 } },
    ...over,
  };
}

function vergleich(engines: Record<string, EngineSummary>): EngineComparison {
  return { engines, rules: {}, currency: 'USD', conditions: [], runs: [], warnings: [] };
}

const zeile = (rows: ReturnType<typeof compareRows>, key: string) =>
  rows.find((row) => row.key === key)!;

describe('engineColumns (ST-7c)', () => {
  it('stellt die Muster-Maschine vor die Agent-Schleife, Fremdes ans Ende', () => {
    expect(engineColumns({ agent: 1, pattern: 1 })).toEqual(['pattern', 'agent']);
    expect(engineColumns({ x: 1, hybrid: 1, agent: 1 })).toEqual(['agent', 'hybrid', 'x']);
  });
});

describe('compareRows (ST-7c)', () => {
  const de = übersetzer('de');

  it('trägt die Kennzahlen des K0-Berichts in fester Reihenfolge', () => {
    const rows = compareRows(vergleich({ pattern: summary() }), ['pattern'], format('de-DE'), de);
    expect(rows.map((row) => row.key)).toEqual([
      'runs', 'hardRate',
      'axis.auftrag_erfuellt', 'axis.intent_fit', 'axis.persona_tone',
      'axis.info_quality', 'axis.safety', 'axis.pattern_match',
      'agreement', 'toolJaccard', 'textSimilarity', 'judgeSpread',
      'speed', 'over30', 'over90', 'tokens', 'costPerTurn', 'robustness', 'safe', 'frei',
    ]);
    expect(zeile(rows, 'axis.auftrag_erfuellt').label).toBe('Judge: Auftrag erfüllt');
  });

  it('formatiert jede Zelle in der Sprache der Oberfläche', () => {
    const rows = compareRows(vergleich({ pattern: summary() }), ['pattern'], format('de-DE'), de);
    const zelle = (key: string) => zeile(rows, key).cells[0];
    expect(zelle('runs')).toBe('3');
    expect(zelle('hardRate')).toBe(`95${NBSP}% (93${NBSP}%–97${NBSP}%)`);
    expect(zelle('axis.persona_tone')).toBe('1,1');
    expect(zelle('agreement')).toBe(`80${NBSP}%`);
    expect(zelle('toolJaccard')).toBe('0,85');
    expect(zelle('speed')).toBe(`12,3${NBSP}s / 21,8${NBSP}s`);
    expect(zelle('over30')).toBe(`5${NBSP}%`);
    expect(zelle('tokens')).toBe('62.821 / 55.462 / 927');
    expect(zelle('costPerTurn')).toBe(`0,0018${NBSP}$`);
    expect(zelle('robustness')).toBe('0 / 1 / 0 / 2');
    expect(zelle('frei')).toBe(`90${NBSP}% / 1,2`);
  });

  it('zeigt Ungemessenes als „–", nie als 0', () => {
    const rows = compareRows(vergleich({
      agent: summary({
        runs: 1, hard_rate_runs: [0.95],
        determinism: {
          turns_compared: 0, check_agreement: null, tool_jaccard: null,
          text_similarity: null, judge_spread: null,
        },
        cost: { ...summary().cost, cost_per_turn: null, cost_total: null,
                price_unavailable: ['gpt-6-luna'] },
      }),
    }), ['agent'], format('de-DE'), de);
    const zelle = (key: string) => zeile(rows, key).cells[0];
    // Ein Lauf hat keine Spanne und keine Wiederholung.
    expect(zelle('hardRate')).toBe(`95${NBSP}%`);
    expect(zelle('agreement')).toBe('–');
    expect(zelle('axis.pattern_match')).toBe('–');
    expect(zelle('costPerTurn')).toBe('–');
  });

  it('erklärt die Wiederholungs-Kennzahlen, die sonst niemand deuten kann', () => {
    const rows = compareRows(vergleich({ pattern: summary() }), ['pattern'], format('de-DE'), de);
    expect(zeile(rows, 'agreement').hint).toContain('Wiederholungen');
    expect(zeile(rows, 'toolJaccard').hint).toContain('1 = gleich');
    expect(zeile(rows, 'runs').hint).toBeUndefined();
  });

  it('stellt eine Zelle je Maschine, in der Reihenfolge der Spalten', () => {
    const rows = compareRows(
      vergleich({ agent: summary({ runs: 2 }), pattern: summary({ runs: 3 }) }),
      ['pattern', 'agent'], format('de-DE'), de);
    expect(zeile(rows, 'runs').cells).toEqual(['3', '2']);
  });

  it('spricht Englisch', () => {
    const rows = compareRows(
      vergleich({ pattern: summary() }), ['pattern'], format('en-GB'), übersetzer('en'));
    expect(zeile(rows, 'runs').label).toBe('Runs');
    expect(zeile(rows, 'speed').cells[0]).toBe(`12.3${NBSP}s / 21.8${NBSP}s`);
    expect(rows.map((row) => row.label).join(' ')).not.toMatch(/[äöüß]/);
  });
});
