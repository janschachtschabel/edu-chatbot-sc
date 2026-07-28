import { describe, expect, it } from 'vitest';

import { effectiveProfile, parseStages, type ProfileDraft } from './loadtest-profile';

const BASE: ProfileDraft = {
  stagesText: '1, 2, 4',
  requestsPerStage: 8,
  thresholdS: 20,
  mix: { wissen: 2, suche: 1 },
};

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
    const p = effectiveProfile(draft({ stagesText: '1, 2, 4, 8' }));
    expect(p.stages).toEqual([1, 2, 4, 8]);
    expect(p.totalRequests).toBe(32);
    expect(p.problem).toBe('');
    expect(p.adjustments).toEqual([]);
  });

  it('caps the concurrency of a stage and says so', () => {
    const p = effectiveProfile(draft({ stagesText: '8, 64' }));
    expect(p.stages).toEqual([8, 32]);
    expect(p.adjustments.join(' ')).toContain('32');
  });

  it('drops stages past the sixth and says so', () => {
    const p = effectiveProfile(draft({ stagesText: '1,2,3,4,5,6,7,8', requestsPerStage: 1 }));
    expect(p.stages).toHaveLength(6);
    expect(p.totalRequests).toBe(6);
    expect(p.adjustments.join(' ')).toContain('6 Stufen');
  });

  it('refuses a profile that exceeds the total-request limit', () => {
    const p = effectiveProfile(draft({ stagesText: '1,2,4,8,16,32', requestsPerStage: 60 }));
    expect(p.totalRequests).toBe(360);
    expect(p.problem).toContain('200');
  });

  it('refuses an empty stage list with an example', () => {
    expect(effectiveProfile(draft({ stagesText: '' })).problem).toContain('Mindestens eine Stufe');
  });

  it('refuses a mix whose weights are all zero', () => {
    const p = effectiveProfile(draft({ mix: { wissen: 0, suche: 0 } }));
    expect(p.problem).toContain('Mix');
    expect(p.mix).toEqual({});
  });

  it('sends only the categories that carry weight', () => {
    const p = effectiveProfile(draft({ mix: { wissen: 2, suche: 0, lernpfad: 1 } }));
    expect(p.mix).toEqual({ wissen: 2, lernpfad: 1 });
  });

  it('survives a cleared number field instead of sending NaN', () => {
    const p = effectiveProfile(draft({ requestsPerStage: Number.NaN, thresholdS: Number.NaN }));
    expect(p.requestsPerStage).toBe(1);
    expect(p.thresholdS).toBe(1);
    expect(p.totalRequests).toBe(3);
    expect(p.problem).toBe('');
  });
});
