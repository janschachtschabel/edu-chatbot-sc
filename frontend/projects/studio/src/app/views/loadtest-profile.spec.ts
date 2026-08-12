import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { Translate } from '../i18n/studio-language.service';
import { effectiveProfile, parseStages, type ProfileDraft } from './loadtest-profile';

const BASE: ProfileDraft = {
  stagesText: '1, 2, 4',
  requestsPerStage: 8,
  thresholdS: 20,
  mix: { wissen: 2, suche: 1 },
};

// Der Übersetzer kommt als Parameter herein, wie bei `describeApiError` und
// `catLabel`: bis C1-d4e1 standen die sechs Sätze dieses Moduls als deutsche
// Vorlagen im Code und froren damit die Sprache ein.
const übersetzer = (locale: 'de' | 'en'): Translate => {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  return (key, params) => i18n.t(key, params);
};
const de = übersetzer('de');
const en = übersetzer('en');

const draft = (over: Partial<ProfileDraft>): ProfileDraft => ({ ...BASE, ...over });

describe('parseStages', () => {
  it('reads a comma-separated list the way a person writes one', () => {
    expect(parseStages(' 1,2 , 4,8 ')).toEqual([1, 2, 4, 8]);
  });

  it('drops what is not a positive number instead of producing NaN', () => {
    // ALT ran parseInt over the same text and kept NaN out of the array, but
    // its requests-per-stage field had no such guard: an emptied number input
    // became NaN, the warning read "NaN echte Chat-Requests", and the POST body
    // carried `null`.
    expect(parseStages('1, abc, 0, -3, 4,,')).toEqual([1, 4]);
  });
});

describe('effectiveProfile', () => {
  it('reports what will run, not what was typed', () => {
    const p = effectiveProfile(de, draft({ stagesText: '1, 2, 4, 8' }));
    expect(p.stages).toEqual([1, 2, 4, 8]);
    expect(p.totalRequests).toBe(32);
    expect(p.problem).toBe('');
    expect(p.adjustments).toEqual([]);
  });

  it('caps the concurrency of a stage and says so', () => {
    const p = effectiveProfile(de, draft({ stagesText: '8, 64' }));
    expect(p.stages).toEqual([8, 32]);
    expect(p.adjustments.join(' ')).toContain('32');
  });

  it('drops stages past the sixth and says so', () => {
    const p = effectiveProfile(de, draft({ stagesText: '1,2,3,4,5,6,7,8', requestsPerStage: 1 }));
    expect(p.stages).toHaveLength(6);
    expect(p.totalRequests).toBe(6);
    expect(p.adjustments.join(' ')).toContain('6 Stufen');
  });

  it('refuses a profile that exceeds the total-request limit', () => {
    const p = effectiveProfile(de, draft({ stagesText: '1,2,4,8,16,32', requestsPerStage: 60 }));
    expect(p.totalRequests).toBe(360);
    expect(p.problem).toContain('200');
  });

  it('refuses an empty stage list with an example', () => {
    const p = effectiveProfile(de, draft({ stagesText: '' }));
    expect(p.problem).toContain('Mindestens eine Stufe');
  });

  it('says all of it in the active language', () => {
    // Beide Satzarten des Moduls in einem Fall: die stille Korrektur und die
    // Ablehnung. Ohne Übersetzer standen sie auf Deutsch neben einer englischen
    // Oberfläche.
    const p = effectiveProfile(en, draft({ stagesText: '1,2,3,4,5,6,7,8', requestsPerStage: 60 }));
    expect(p.adjustments.join(' ')).toContain('Only the first 6 stages');
    expect(p.problem).toContain('Profile too large');
    expect(effectiveProfile(en, draft({ stagesText: '' })).problem)
      .toContain('At least one stage');
  });

  it('refuses a mix whose weights are all zero', () => {
    const p = effectiveProfile(de, draft({ mix: { wissen: 0, suche: 0 } }));
    expect(p.problem).toContain('Mix');
    expect(p.mix).toEqual({});
  });

  it('sends only the categories that carry weight', () => {
    const p = effectiveProfile(de, draft({ mix: { wissen: 2, suche: 0, lernpfad: 1 } }));
    expect(p.mix).toEqual({ wissen: 2, lernpfad: 1 });
  });

  it('survives a cleared number field instead of sending NaN', () => {
    const p = effectiveProfile(de, draft({ requestsPerStage: Number.NaN, thresholdS: Number.NaN }));
    expect(p.requestsPerStage).toBe(1);
    expect(p.thresholdS).toBe(1);
    expect(p.totalRequests).toBe(3);
    expect(p.problem).toBe('');
  });
});
