// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import {
  buildAuthorizeUrl,
  codeChallenge,
  createCodeVerifier,
  createState,
  readCallbackParams,
} from './oauth-pkce';

describe('createCodeVerifier', () => {
  it('hält sich an RFC 7636 §4.1 — 43–128 Zeichen aus dem unreservierten Vorrat', () => {
    const v = createCodeVerifier();
    expect(v.length).toBeGreaterThanOrEqual(43);
    expect(v.length).toBeLessThanOrEqual(128);
    expect(/^[A-Za-z0-9\-._~]+$/.test(v)).toBe(true);
  });

  it('liefert bei jedem Aufruf einen anderen Wert', () => {
    expect(createCodeVerifier()).not.toBe(createCodeVerifier());
  });
});

describe('codeChallenge', () => {
  it('trifft den Testvektor aus RFC 7636 Anhang B', async () => {
    // Gegen den offiziellen Vektor gepinnt, NICHT gegen die eigene Ausgabe:
    // ein selbst erzeugter Erwartungswert würde jede Base64url-Verwechslung
    // (+/ statt -_, Füllzeichen) mitbestätigen statt sie zu finden.
    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
    expect(await codeChallenge(verifier)).toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  });

  it('erzeugt base64url ohne Füllzeichen', async () => {
    const c = await codeChallenge(createCodeVerifier());
    expect(/^[A-Za-z0-9\-_]+$/.test(c)).toBe(true);
    expect(c).not.toContain('=');
  });
});

describe('createState', () => {
  it('ist lang genug, um nicht geraten zu werden, und jedes Mal neu', () => {
    const s = createState();
    expect(s.length).toBeGreaterThanOrEqual(43);
    expect(s).not.toBe(createState());
  });
});

describe('buildAuthorizeUrl', () => {
  const opts = {
    authorizationEndpoint: 'https://mcp.example/oauth/authorize',
    clientId: 'wloc1.abc',
    redirectUri: 'https://chat.example/widget/oauth-callback.html',
    state: 'STATE',
    codeChallenge: 'CHALLENGE',
    scope: 'wlo',
  };

  it('trägt alle Pflichtfelder des Codeflusses', () => {
    const u = new URL(buildAuthorizeUrl(opts));
    expect(u.origin + u.pathname).toBe('https://mcp.example/oauth/authorize');
    expect(u.searchParams.get('response_type')).toBe('code');
    expect(u.searchParams.get('client_id')).toBe('wloc1.abc');
    expect(u.searchParams.get('redirect_uri')).toBe(opts.redirectUri);
    expect(u.searchParams.get('state')).toBe('STATE');
    expect(u.searchParams.get('scope')).toBe('wlo');
  });

  it('verlangt S256 — „plain" beweist nichts', () => {
    // Der Server unterstützt laut Discovery ausschliesslich S256; „plain"
    // wäre auch dort, wo es ginge, nur die Zeichenkette aus der URL.
    const u = new URL(buildAuthorizeUrl(opts));
    expect(u.searchParams.get('code_challenge')).toBe('CHALLENGE');
    expect(u.searchParams.get('code_challenge_method')).toBe('S256');
  });
});

describe('readCallbackParams', () => {
  it('liest Code und state aus der Rückkehr-URL', () => {
    expect(readCallbackParams('?code=mcp_ac_x&state=S')).toEqual({
      code: 'mcp_ac_x',
      state: 'S',
      error: null,
    });
  });

  it('meldet eine Ablehnung als Fehler, nicht als leeren Code', () => {
    // Wer „ablehnen" wählt, bekommt access_denied — das darf nicht als
    // „irgendwas ging schief" enden, sondern ist eine bewusste Entscheidung.
    const r = readCallbackParams('?error=access_denied&error_description=Nein');
    expect(r.error).toBe('access_denied');
    expect(r.code).toBeNull();
  });

  it('gibt bei leerer Rückkehr überall null — kein halber Zustand', () => {
    expect(readCallbackParams('')).toEqual({ code: null, state: null, error: null });
  });
});
