// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import { readAccessBlock } from './mcp-access';
import { discoverEndpoints, exchangeCode, registerClient, signIn } from './mcp-oauth';

const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';
const BASE = 'https://mcp.example';

const DISCOVERY = {
  issuer: BASE,
  authorization_endpoint: `${BASE}/oauth/authorize`,
  token_endpoint: `${BASE}/oauth/token`,
  registration_endpoint: `${BASE}/oauth/register`,
  code_challenge_methods_supported: ['S256'],
  token_endpoint_auth_methods_supported: ['none'],
};

interface Aufruf {
  url: string;
  init: RequestInit;
}

/** fetchImpl, das je Adress-Muster antwortet und die Aufrufe festhält. */
function fakeFetch(gesehen: Aufruf[], antworten: Record<string, unknown>): typeof fetch {
  return (async (url: string, init: RequestInit = {}) => {
    gesehen.push({ url, init });
    const treffer = Object.keys(antworten).find((k) => url.includes(k));
    if (!treffer) return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
    return {
      ok: true,
      status: 200,
      json: async () => antworten[treffer],
    } as unknown as Response;
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  sessionStorage.clear();
});

describe('discoverEndpoints', () => {
  it('liest das Discovery-Dokument der Wurzel', async () => {
    const gesehen: Aufruf[] = [];
    const d = await discoverEndpoints(BASE, {
      fetchImpl: fakeFetch(gesehen, { '.well-known': DISCOVERY }),
    });
    expect(gesehen[0].url).toBe(`${BASE}/.well-known/oauth-authorization-server`);
    expect(d?.token_endpoint).toBe(`${BASE}/oauth/token`);
  });

  it('gibt null statt zu werfen, wenn der Betrieb OAuth gar nicht anhat', async () => {
    // Ohne WLO_AUTH_PRIVATE_KEY antworten diese Adressen mit 404 (AUTH.md §8).
    // Das ist kein Fehler, sondern „hier gibt es keine Anmeldung" — die
    // Oberfläche darf den Knopf dann einfach nicht anbieten.
    const d = await discoverEndpoints(BASE, { fetchImpl: fakeFetch([], {}) });
    expect(d).toBeNull();
  });
});

describe('registerClient', () => {
  it('meldet sich als öffentlicher Client an, ohne Geheimnis', async () => {
    const gesehen: Aufruf[] = [];
    const id = await registerClient(
      DISCOVERY.registration_endpoint,
      'https://chat.example/widget/oauth-callback.html',
      { fetchImpl: fakeFetch(gesehen, { register: { client_id: 'wloc1.abc' } }) },
    );
    expect(id).toBe('wloc1.abc');
    const koerper = JSON.parse(gesehen[0].init.body as string);
    expect(koerper.redirect_uris).toEqual(['https://chat.example/widget/oauth-callback.html']);
    expect(koerper.token_endpoint_auth_method).toBe('none');
    expect(koerper.grant_types).toEqual(['authorization_code']);
  });
});

describe('exchangeCode', () => {
  it('legt den code_verifier vor und KEIN Client-Geheimnis', async () => {
    const gesehen: Aufruf[] = [];
    const token = await exchangeCode(
      {
        tokenEndpoint: DISCOVERY.token_endpoint,
        clientId: 'wloc1.abc',
        code: 'mcp_ac_x',
        codeVerifier: 'VERIFIER',
        redirectUri: 'https://chat.example/widget/oauth-callback.html',
      },
      { fetchImpl: fakeFetch(gesehen, { token: { access_token: BLOCK } }) },
    );
    expect(token).toBe(BLOCK);

    const felder = new URLSearchParams(gesehen[0].init.body as string);
    expect(felder.get('grant_type')).toBe('authorization_code');
    expect(felder.get('code_verifier')).toBe('VERIFIER');
    expect(felder.get('code')).toBe('mcp_ac_x');
    // Ein öffentlicher Client hat keins — und würde es hier verraten.
    expect(felder.get('client_secret')).toBeNull();
  });
});

// ── signIn: der ganze Vorgang, mit einem Attrappen-Fenster ────────────────

/** Ein Fenster-Ersatz, den der Test als `event.source` verwenden kann. */
function fakeFenster(): Window {
  const w = { closed: false, close: () => undefined };
  return w as unknown as Window;
}

function antworteMitNachricht(quelle: Window | null, data: unknown, verzoegerung = 0): void {
  setTimeout(() => {
    window.dispatchEvent(
      new MessageEvent('message', { data, source: quelle as Window & typeof globalThis }),
    );
  }, verzoegerung);
}

const RUECKRUF = 'https://chat.example/widget/oauth-callback.html';

/**
 * Baut die Abhängigkeiten. `antwort` bekommt den ECHTEN `state` aus der
 * Fenster-Adresse — nur so prüft der Test die state-Bindung wirklich; mit einem
 * erfundenen Wert wäre er auch dann grün, wenn die Bindung fehlt.
 */
function deps(
  fenster: Window | null,
  antwort?: (state: string) => { quelle: Window | null; data: unknown },
  gesehen: Aufruf[] = [],
) {
  return {
    fetchImpl: fakeFetch(gesehen, {
      '.well-known': DISCOVERY,
      register: { client_id: 'wloc1.abc' },
      token: { access_token: BLOCK },
    }),
    openWindow: (url: string) => {
      if (antwort) {
        const state = new URL(url).searchParams.get('state') ?? '';
        const { quelle, data } = antwort(state);
        antworteMitNachricht(quelle, data, 0);
      }
      return fenster;
    },
    timeoutMs: 200,
  };
}

describe('signIn', () => {
  it('legt den Block ab, wenn das Fenster mit passendem state antwortet', async () => {
    const fenster = fakeFenster();
    const r = await signIn(
      BASE,
      RUECKRUF,
      deps(fenster, (state) => ({
        quelle: fenster,
        data: { source: 'boerdi-oauth', code: 'mcp_ac_x', state },
      })),
    );
    expect(r.ok).toBe(true);
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('verwirft eine Antwort mit FALSCHEM state', async () => {
    // Ohne diese Bindung könnte ein untergeschobener Code eine fremde
    // Anmeldung in diese Sitzung holen (CSRF auf den Anmeldevorgang).
    const fenster = fakeFenster();
    const r = await signIn(
      BASE,
      RUECKRUF,
      deps(fenster, () => ({
        quelle: fenster,
        data: { source: 'boerdi-oauth', code: 'mcp_ac_x', state: 'FALSCH' },
      })),
    );
    expect(r.ok).toBe(false);
    expect(readAccessBlock()).toBeNull();
  });

  it('nimmt keine Nachricht aus einem FREMDEN Fenster an', async () => {
    // Sonst könnte jedes andere Skript der Gastgeberseite einen Code
    // unterschieben — auch mit richtigem state, wenn es ihn mitgelesen hat.
    const fenster = fakeFenster();
    const fremd = fakeFenster();
    const r = await signIn(
      BASE,
      RUECKRUF,
      deps(fenster, (state) => ({
        quelle: fremd,
        data: { source: 'boerdi-oauth', code: 'BOESE', state },
      })),
    );
    expect(r).toEqual({ ok: false, reason: 'timeout' });
    expect(readAccessBlock()).toBeNull();
  });

  it('meldet eine Ablehnung als solche, nicht als Panne', async () => {
    const fenster = fakeFenster();
    const r = await signIn(
      BASE,
      RUECKRUF,
      deps(fenster, (state) => ({
        quelle: fenster,
        data: { source: 'boerdi-oauth', error: 'access_denied', state },
      })),
    );
    expect(r).toEqual({ ok: false, reason: 'denied' });
  });

  it('sagt ehrlich Bescheid, wenn der Betrieb keine Anmeldung anbietet', async () => {
    // Ohne WLO_AUTH_PRIVATE_KEY antwortet die Discovery mit 404 (AUTH.md §8).
    const r = await signIn(BASE, RUECKRUF, {
      fetchImpl: fakeFetch([], {}),
      openWindow: () => fakeFenster(),
      timeoutMs: 50,
    });
    expect(r).toEqual({ ok: false, reason: 'unavailable' });
  });

  it('meldet ein blockiertes Anmeldefenster als eigenen Fall', async () => {
    // Ohne Nutzergeste blockt der Browser das Fenster — der Mensch sieht sonst
    // nur, dass „nichts passiert".
    const r = await signIn(BASE, RUECKRUF, deps(null));
    expect(r).toEqual({ ok: false, reason: 'popup-blocked' });
  });
});
