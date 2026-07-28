// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import {
  CORE_TRUSTED_DOMAINS,
  buildTrustedDomains,
  externalLinkWarning,
  isTrustedHost,
  mergeTrustedDomains,
  normalizeTrustedDomain,
  withBsid,
} from './trusted-host';

const VALID_SID = 'bb-12345678-1234-4123-8123-123456789abc';

describe('isTrustedHost', () => {
  it('matches exact host and subdomains, case-insensitively', () => {
    const list = ['openeduhub.net'];
    expect(isTrustedHost('openeduhub.net', list)).toBe(true);
    expect(isTrustedHost('redaktion.openeduhub.net', list)).toBe(true);
    expect(isTrustedHost('REDAKTION.OpenEduHub.net', list)).toBe(true);
  });

  it('treats "*.example.com" and "example.com" as equivalent', () => {
    expect(isTrustedHost('a.example.com', ['*.example.com'])).toBe(true);
    expect(isTrustedHost('example.com', ['*.example.com'])).toBe(true);
  });

  it('does not confuse an adjacent or suffixed domain for a subdomain', () => {
    expect(isTrustedHost('notopeneduhub.net', ['openeduhub.net'])).toBe(false);
    expect(isTrustedHost('openeduhub.net.evil.com', ['openeduhub.net'])).toBe(false);
  });

  it('returns false for an empty host or an empty trusted list', () => {
    expect(isTrustedHost('', ['openeduhub.net'])).toBe(false);
    expect(isTrustedHost('openeduhub.net', [])).toBe(false);
  });
});

describe('normalizeTrustedDomain', () => {
  it('trims, lowercases, strips protocol + wildcard, and cuts the path', () => {
    expect(normalizeTrustedDomain('  HTTPS://*.Example.com/foo/bar ')).toBe('example.com');
    expect(normalizeTrustedDomain('http://localhost:4200')).toBe('localhost:4200');
  });
});

describe('mergeTrustedDomains', () => {
  it('keeps backend entries first, appends attribute entries additively, dedups', () => {
    const merged = mergeTrustedDomains(['openeduhub.net'], 'localhost, *.nip.io openeduhub.net');
    expect(merged).toEqual(['openeduhub.net', 'localhost', 'nip.io']);
  });
});

describe('buildTrustedDomains (V5 unified list)', () => {
  it('always includes the core WLO domains, plus backend and attribute entries', () => {
    const list = buildTrustedDomains(['redaktion.example.net'], 'localhost');
    for (const core of CORE_TRUSTED_DOMAINS) {
      expect(list).toContain(core);
    }
    expect(list).toContain('redaktion.example.net');
    expect(list).toContain('localhost');
  });

  it('dedups a core domain against backend/attribute duplicates', () => {
    const list = buildTrustedDomains(['openeduhub.net'], 'openeduhub.net');
    expect(list.filter((d) => d === 'openeduhub.net')).toHaveLength(1);
  });
});

describe('externalLinkWarning', () => {
  const list = ['openeduhub.net'];

  it('warns for an untrusted external host', () => {
    expect(externalLinkWarning('https://evil.example/page', list)).toBe('Achtung! Externe URL.');
  });

  it('is silent for a trusted host, same-origin, or empty input', () => {
    expect(externalLinkWarning('https://redaktion.openeduhub.net/x', list)).toBe('');
    expect(externalLinkWarning(window.location.origin + '/foo', list)).toBe('');
    expect(externalLinkWarning('', list)).toBe('');
  });
});

describe('withBsid', () => {
  const list = ['openeduhub.net'];

  it('appends the session id to a trusted http(s) URL', () => {
    const out = withBsid('https://redaktion.openeduhub.net/x', VALID_SID, list);
    expect(new URL(out).searchParams.get('bsid')).toBe(VALID_SID);
  });

  it('leaves untrusted, non-http, invalid-session, and pre-tagged URLs unchanged', () => {
    expect(withBsid('https://evil.example/x', VALID_SID, list)).toBe('https://evil.example/x');
    expect(withBsid('mailto:a@b.de', VALID_SID, list)).toBe('mailto:a@b.de');
    expect(withBsid('https://redaktion.openeduhub.net/x', 'not-a-session', list)).toBe(
      'https://redaktion.openeduhub.net/x',
    );
    const pre = 'https://redaktion.openeduhub.net/x?bsid=' + VALID_SID;
    expect(withBsid(pre, VALID_SID, list)).toBe(pre);
  });

  it('returns an empty string for empty input', () => {
    expect(withBsid('', VALID_SID, list)).toBe('');
  });
});
