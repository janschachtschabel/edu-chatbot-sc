import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AnmeldeFrist, HINWEIS_VORLAUF_MS, TAUSCH_NACHLAUF_MS } from './anmelde-frist';
import {
  clearSignedOut, isSignedOut, markSignedOut, MCP_SIGNED_OUT_STORAGE_KEY,
} from './mcp-access';

/** Plan 2026-11-07 (R1/CB-9): Ticket nach dem Ablauf neu tauschen, sonst vorher hinweisen. */
describe('AnmeldeFrist', () => {
  const JETZT = Date.parse('2026-11-07T12:00:00Z');
  const IN_STUNDE = '2026-11-07T13:00:00.000Z';

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function frist(ticketWeg: boolean) {
    const wege = { ticketWeg: () => ticketWeg, neuTauschen: vi.fn(), hinweisen: vi.fn(),
      jetzt: () => JETZT };
    return { f: new AnmeldeFrist(wege), wege };
  }

  it('tauscht das Ticket erst nach dem Ablauf neu', () => {
    const { f, wege } = frist(true);
    f.planen(IN_STUNDE);
    vi.advanceTimersByTime(3_600_000);
    expect(wege.neuTauschen).not.toHaveBeenCalled();
    vi.advanceTimersByTime(TAUSCH_NACHLAUF_MS);
    expect(wege.neuTauschen).toHaveBeenCalledTimes(1);
    expect(wege.hinweisen).not.toHaveBeenCalled();
  });

  it('weist ohne Ticket zehn Minuten vorher hin', () => {
    const { f, wege } = frist(false);
    f.planen(IN_STUNDE);
    vi.advanceTimersByTime(3_600_000 - HINWEIS_VORLAUF_MS - 1);
    expect(wege.hinweisen).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(wege.hinweisen).toHaveBeenCalledTimes(1);
  });

  it('plant dieselbe Frist nur einmal und vergisst sie auf Wunsch', () => {
    const { f, wege } = frist(false);
    f.planen(IN_STUNDE);
    f.planen(IN_STUNDE);
    f.vergessen();
    vi.advanceTimersByTime(4_000_000);
    expect(wege.hinweisen).not.toHaveBeenCalled();
  });

  it('übergeht leere und unlesbare Fristen', () => {
    const { f, wege } = frist(true);
    f.planen(null);
    f.planen('kein Datum');
    vi.advanceTimersByTime(10 ** 8);
    expect(wege.neuTauschen).not.toHaveBeenCalled();
  });

  it('weist bei einer schon vergangenen Frist nicht mehr hin — das übernimmt der 401-Weg', () => {
    const { f, wege } = frist(false);
    f.planen('2026-11-07T11:00:00.000Z');
    vi.advanceTimersByTime(10 ** 7);
    expect(wege.hinweisen).not.toHaveBeenCalled();
  });
});

describe('Abmelde-Merker (R2)', () => {
  afterEach(() => sessionStorage.removeItem(MCP_SIGNED_OUT_STORAGE_KEY));

  it('steht nach dem Abmelden und fällt mit einer neuen Anmeldung', () => {
    expect(isSignedOut()).toBe(false);
    markSignedOut();
    expect(isSignedOut()).toBe(true);
    clearSignedOut();
    expect(isSignedOut()).toBe(false);
  });
});
