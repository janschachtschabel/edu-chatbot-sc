import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { Translate } from '../i18n/studio-language.service';
import {
  catLabel, flowGroups, hardCats, hardRate, type GoldPerTurn,
} from './gold-scorecard';

const turn = (flow: string, no: number, over: Partial<GoldPerTurn> = {}): GoldPerTurn => ({
  flow, title: `Titel ${flow}`, turn: no, message: `m${no}`,
  expected: {}, observed: {},
  checks: { register: null, structure: true, tools_any: true, qr: true, host: null },
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

describe('hardCats', () => {
  // GV5: die harte Menge kommt aus dem BERICHT selbst (alles außer dem
  // weichen `host`) — so rendert dieselbe Scorecard gespeicherte v1-Läufe
  // (persona/intent…) und v2-Läufe (register/structure/tools_any/qr), ohne
  // eine Versions-Weiche zu pflegen.
  it('derives the hard set from the report and drops soft host', () => {
    expect(hardCats({ categories: ['register', 'structure', 'tools_any', 'qr', 'host'] }))
      .toEqual(['register', 'structure', 'tools_any', 'qr']);
  });

  it('keeps stored v1 runs readable', () => {
    expect(hardCats({ categories: ['persona', 'intent', 'register', 'structure', 'qr', 'host'] }))
      .toEqual(['persona', 'intent', 'register', 'structure', 'qr']);
  });

  it('is empty without metrics', () => {
    expect(hardCats(undefined)).toEqual([]);
    expect(hardCats(null)).toEqual([]);
  });
});

describe('hardRate', () => {
  const V2 = ['register', 'structure', 'tools_any', 'qr'] as const;

  it('counts the hard categories and leaves host out', () => {
    const entry = {
      title: 'Flow Eins', zielgruppe: 'P-LEH',
      register: { ok: 1, total: 1 }, structure: { ok: 0, total: 1 },
      tools_any: { ok: 2, total: 2 }, qr: { ok: 2, total: 2 },
      // Soft: reported beside the hard rate, never inside it.
      host: { ok: 0, total: 5 },
    } as unknown as Parameters<typeof hardRate>[0];

    expect(hardRate(entry, V2)).toEqual({ ok: 5, total: 6, rate: 0.833 });
  });

  it('reports no rate rather than 0 when nothing was asserted', () => {
    const entry = {
      register: { ok: 0, total: 0 }, structure: { ok: 0, total: 0 },
      tools_any: { ok: 0, total: 0 }, qr: { ok: 0, total: 0 },
    } as unknown as Parameters<typeof hardRate>[0];

    // 0/0 is "not measured", and a 0 % would read as "everything failed".
    expect(hardRate(entry, V2)).toEqual({ ok: 0, total: 0, rate: null });
  });

  it('survives a flow entry that is missing categories', () => {
    const entry = { register: { ok: 1, total: 1 } } as unknown as Parameters<typeof hardRate>[0];

    expect(hardRate(entry, V2)).toEqual({ ok: 1, total: 1, rate: 1 });
  });
});

describe('catLabel', () => {
  // Der Übersetzer kommt als Parameter herein, wie bei `describeApiError` und
  // `renderCard`: bis C1-d4b2 standen die sechs Namen als fertige Texte in
  // einer Modul-Konstante und froren damit die Sprache ein, die beim Laden des
  // Moduls gerade galt.
  // Über `I18n` wie in `i18n/en.spec.ts` — derselbe Weg, den das Studio im
  // Betrieb nimmt; der Kern muss seinen Übersetzer-Bauer nicht öffentlich
  // machen.
  const übersetzer = (locale: 'de' | 'en'): Translate => {
    const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
    i18n.setLocale(locale);
    return (key, params) => i18n.t(key, params);
  };
  const de = übersetzer('de');
  const en = übersetzer('en');

  it('names the categories in the active language', () => {
    expect(catLabel('register', de)).toBe('Tonalität');
    expect(catLabel('qr', de)).toBe('Quick-Replies');
    expect(catLabel('host', de)).toBe('Link-Host');
    expect(catLabel('tools_any', de)).toBe('Werkzeug-Soll');

    expect(catLabel('register', en)).toBe('Register');
    expect(catLabel('qr', en)).toBe('Quick replies');
    expect(catLabel('host', en)).toBe('Link host');
    expect(catLabel('tools_any', en)).toBe('Required tool');
  });

  it('falls back to the raw key so a new category is visible, not hidden', () => {
    // Erlaubnisliste statt `'evalDetail.cat.' + category`: ein zusammengesetzter
    // Schlüssel gäbe hier „evalDetail.cat.brandneu" als Beschriftung aus.
    expect(catLabel('brandneu', de)).toBe('brandneu');
  });
});
