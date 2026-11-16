// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import type { AblaufStand } from '../grouping/message-types';
import { ABLAUF_SEITE_MERKER, merkerNachStand, setzeAblaufSeiteMerker } from './ablauf-seite-merker';

const stand = (status: string): AblaufStand => ({ id: 'fuehrung', titel: 'Führung', nr: 2, von: 5, status, teile: [] });

describe('ablauf-seite-merker (Plan 2026-11-15, WF-5)', () => {
  afterEach(() => localStorage.clear());

  it('wartet ein Lauf auf eine Seite, ist der Merker an', () => {
    expect(merkerNachStand(stand('wartet_seite'), true)).toBe(true);
    // auch, bevor überhaupt eine Serverantwort da ist (der Stand kommt dann aus dem Verlauf)
    expect(merkerNachStand(stand('wartet_seite'), false)).toBe(true);
  });

  it('ein anderer Stand oder ein beendeter Lauf nehmen ihn — aber erst nach einer Serverantwort', () => {
    expect(merkerNachStand(stand('wartet_wahl'), true)).toBe(false);
    expect(merkerNachStand(null, true)).toBe(false);
    // Neu geladene Seite, Verlauf noch nicht da: nichts ändern, sonst klappte das Widget zu
    expect(merkerNachStand(null, false)).toBeNull();
  });

  it('setzt und löscht den Merker im localStorage', () => {
    setzeAblaufSeiteMerker(true);
    expect(localStorage.getItem(ABLAUF_SEITE_MERKER)).toBe('1');
    setzeAblaufSeiteMerker(false);
    expect(localStorage.getItem(ABLAUF_SEITE_MERKER)).toBeNull();
  });
});
