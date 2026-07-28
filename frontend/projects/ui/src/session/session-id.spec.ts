// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import {
  generateSessionId,
  isValidSessionId,
  readSessionCookie,
  resolvePersistedSessionId,
  writeSessionEverywhere,
} from './session-id';

const VALID_SID = 'bb-12345678-1234-4123-8123-123456789abc';
const KEY = 'boerdi_session_id';

function clearCookies(): void {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim();
    if (name) document.cookie = `${name}=; Max-Age=0; Path=/`;
  }
}

describe('isValidSessionId', () => {
  it('accepts a bb- prefixed uuid within the length bound', () => {
    expect(isValidSessionId(VALID_SID)).toBe(true);
    expect(isValidSessionId('bb-' + '0'.repeat(32))).toBe(true);
  });

  it('rejects wrong prefix, wrong charset, overlength, and non-strings (injection guard)', () => {
    expect(isValidSessionId('evil-tracking-id')).toBe(false);
    expect(isValidSessionId('bb-XYZ!')).toBe(false);
    expect(isValidSessionId('bb-' + 'a'.repeat(90))).toBe(false);
    expect(isValidSessionId(null)).toBe(false);
    expect(isValidSessionId(undefined)).toBe(false);
    expect(isValidSessionId('')).toBe(false);
  });
});

describe('generateSessionId', () => {
  it('produces a valid, bb- prefixed session id', () => {
    const id = generateSessionId();
    expect(id.startsWith('bb-')).toBe(true);
    expect(isValidSessionId(id)).toBe(true);
  });

  it('produces unique ids across calls', () => {
    expect(generateSessionId()).not.toBe(generateSessionId());
  });
});

describe('resolvePersistedSessionId (URL → cookie → localStorage)', () => {
  beforeEach(() => {
    localStorage.clear();
    clearCookies();
    history.replaceState({}, '', '/');
  });

  it('picks the id from ?bsid= and strips only that param from the URL (viaBsid=true)', () => {
    history.replaceState({}, '', `/page?bsid=${VALID_SID}&x=1`);
    const res = resolvePersistedSessionId(KEY);
    expect(res).toEqual({ id: VALID_SID, viaBsid: true });
    const url = new URL(window.location.href);
    expect(url.searchParams.has('bsid')).toBe(false);
    expect(url.searchParams.get('x')).toBe('1');
  });

  it('ignores an invalid ?bsid= and falls through to localStorage', () => {
    history.replaceState({}, '', `/?bsid=evil-tracking-id`);
    localStorage.setItem(KEY, VALID_SID);
    expect(resolvePersistedSessionId(KEY)).toEqual({ id: VALID_SID, viaBsid: false });
  });

  it('falls back to localStorage when no URL id is present', () => {
    localStorage.setItem(KEY, VALID_SID);
    expect(resolvePersistedSessionId(KEY)).toEqual({ id: VALID_SID, viaBsid: false });
  });

  it('returns null when nothing valid is stored', () => {
    expect(resolvePersistedSessionId(KEY)).toEqual({ id: null, viaBsid: false });
  });
});

describe('cookie + storage writers', () => {
  beforeEach(() => {
    localStorage.clear();
    clearCookies();
  });

  it('writeSessionEverywhere always writes localStorage and skips the cookie without a domain', () => {
    writeSessionEverywhere(VALID_SID, { sessionKey: KEY, cookieDomain: '', cookieMaxAge: 2592000 });
    expect(localStorage.getItem(KEY)).toBe(VALID_SID);
  });

  it('readSessionCookie reads a cookie value by name and returns null when absent', () => {
    document.cookie = `${KEY}=${VALID_SID}; Path=/`;
    expect(readSessionCookie(KEY)).toBe(VALID_SID);
    expect(readSessionCookie('nope_absent_key')).toBeNull();
  });
});
