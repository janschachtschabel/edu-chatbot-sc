// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import { isValidSessionId } from '../session/session-id';
import { bootSession } from './session-boot';

/**
 * Session-Boot (8-4S-e1): die 3-Stufen-Kaskade aus ALT `ngOnInit` (286-305) als
 * pure Funktion — löst/erzeugt die Session-ID und schreibt sie bei `persist` in
 * alle Storages zurück. Die einzelnen Stufen (URL `?bsid=` → Cookie →
 * localStorage) sind bereits in `session-id.spec.ts` gepinnt; hier zählt die
 * Orchestrierung: persist-Gate, Resume-Flag, `viaBsid`-Durchreichung, Write-Back.
 */

const VALID_SID = 'bb-12345678-1234-4123-8123-123456789abc';
const KEY = 'boerdi_session_id';
const CFG = { persist: true, sessionKey: KEY, cookieDomain: '', cookieMaxAge: 2592000 };

function clearCookies(): void {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim();
    if (name) document.cookie = `${name}=; Max-Age=0; Path=/`;
  }
}

describe('bootSession (8-4S-e1) — 3-Stufen-Session-Kaskade', () => {
  beforeEach(() => {
    localStorage.clear();
    clearCookies();
    history.replaceState({}, '', '/');
  });

  it('persist=false: frische valide ID, kein Resume, kein Storage-Write', () => {
    const boot = bootSession({ ...CFG, persist: false });
    expect(isValidSessionId(boot.sessionId)).toBe(true);
    expect(boot).toMatchObject({ resumed: false, viaBsid: false });
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it('persist=true, ?bsid= valid: resumed via bsid + in alle Storages geschrieben', () => {
    history.replaceState({}, '', `/page?bsid=${VALID_SID}`);
    const boot = bootSession(CFG);
    expect(boot).toEqual({ sessionId: VALID_SID, resumed: true, viaBsid: true });
    expect(localStorage.getItem(KEY)).toBe(VALID_SID);
  });

  it('persist=true, localStorage-Treffer: resumed ohne bsid', () => {
    localStorage.setItem(KEY, VALID_SID);
    const boot = bootSession(CFG);
    expect(boot).toEqual({ sessionId: VALID_SID, resumed: true, viaBsid: false });
  });

  it('persist=true, nichts gespeichert: frische ID, kein Resume, wird persistiert', () => {
    const boot = bootSession(CFG);
    expect(isValidSessionId(boot.sessionId)).toBe(true);
    expect(boot).toMatchObject({ resumed: false, viaBsid: false });
    expect(localStorage.getItem(KEY)).toBe(boot.sessionId);
  });
});
