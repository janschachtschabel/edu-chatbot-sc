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

/** Ein Fenster-Ersatz, den der Test als `event.source` verwenden kann. Seine
 *  Adresse bekommt es erst nach Discovery und Registrierung (Paket 10, H-3) —
 *  `beiAdresse` sieht sie. */
type FakeFenster = Window & { beiAdresse?: (url: string) => void };

function fakeFenster(): FakeFenster {
  const w: { closed: boolean; close(): void; location?: unknown; beiAdresse?: (url: string) => void } = {
    closed: false,
    close: () => { w.closed = true; },
  };
  w.location = {
    get href() { return ''; },
    set href(url: string) { w.beiAdresse?.(url); },
  };
  return w as unknown as FakeFenster;
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
  fenster: FakeFenster | null,
  antwort?: (state: string) => { quelle: Window | null; data: unknown },
  gesehen: Aufruf[] = [],
) {
  return {
    fetchImpl: fakeFetch(gesehen, {
      '.well-known': DISCOVERY,
      register: { client_id: 'wloc1.abc' },
      token: { access_token: BLOCK },
    }),
    openWindow: () => {
      if (fenster && antwort) {
        fenster.beiAdresse = (url: string) => {
          const state = new URL(url).searchParams.get('state') ?? '';
          const { quelle, data } = antwort(state);
          antworteMitNachricht(quelle, data, 0);
        };
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

  it('öffnet das Fenster sofort im Klick, vor jeder Abfrage (Paket 10, H-3)', async () => {
    // Audit 2026-10-10, H-3: `window.open` stand hinter Discovery, Registrierung und
    // Prüfsumme — die Nutzergeste war bis dahin verbraucht, Safari und Firefox
    // blockten das Fenster.
    const reihenfolge: string[] = [];
    const basis = deps(fakeFenster());
    const lauf = signIn(BASE, RUECKRUF, {
      ...basis,
      fetchImpl: ((...args: Parameters<typeof fetch>) => {
        reihenfolge.push('abfrage');
        return basis.fetchImpl(...args);
      }) as typeof fetch,
      openWindow: (url: string) => {
        reihenfolge.push(`fenster ${url}`);
        return basis.openWindow();
      },
      timeoutMs: 50,
    });
    expect(reihenfolge[0]).toBe('fenster about:blank');   // im selben Takt wie der Klick
    await lauf;
  });

  it('schließt das vorab geöffnete Fenster, wenn es nicht weitergeht', async () => {
    const fenster = fakeFenster();
    const r = await signIn(BASE, RUECKRUF, {
      fetchImpl: fakeFetch([], {}), openWindow: () => fenster, timeoutMs: 50,
    });
    expect(r).toEqual({ ok: false, reason: 'unavailable' });
    expect(fenster.closed).toBe(true);
  });
});

// ── Paket 19, Audit 2026-10-31 N-36 + N-37 ──────────────────────────────────
describe('signIn — Paket 19', () => {
  it('eine unsichere Anmelde-Adresse bricht ab, bevor das Fenster sie bekommt (N-36)', async () => {
    const fenster = fakeFenster();
    const adressen: string[] = [];
    fenster.beiAdresse = (url) => adressen.push(url);
    const r = await signIn(BASE, RUECKRUF, {
      fetchImpl: fakeFetch([], {
        '.well-known': { ...DISCOVERY, authorization_endpoint: 'javascript:alert(document.domain)//' },
        register: { client_id: 'wloc1.abc' },
      }),
      openWindow: () => fenster,
      timeoutMs: 200,
    });
    expect(r).toEqual({ ok: false, reason: 'unavailable' });
    expect(adressen).toEqual([]);
    expect(fenster.closed).toBe(true);
  });

  // N-37: ein geschlossenes Anmeldefenster blieb unbemerkt — fünf Minuten Warten
  // ohne Hinweis.
  it('ein geschlossenes Anmeldefenster heißt „abgebrochen“, nicht Zeitablauf (N-37)', async () => {
    const fenster = fakeFenster();
    const basis = deps(fenster);
    const start = Date.now();
    const r = await signIn(BASE, RUECKRUF, {
      ...basis,
      openWindow: () => {
        fenster.beiAdresse = () => { setTimeout(() => fenster.close(), 5); };
        return fenster;
      },
      timeoutMs: 5_000,
      pollMs: 10,
    });
    expect(r).toEqual({ ok: false, reason: 'cancelled' });
    expect(Date.now() - start).toBeLessThan(2_000);
  });

  it('Rückmeldung und gleich danach geschlossen (Rückruf-Seite) bleibt ein Erfolg (N-37)', async () => {
    const fenster = fakeFenster();
    const basis = deps(fenster, (state) => ({
      quelle: fenster,
      data: { source: 'boerdi-oauth', code: 'mcp_ac_x', state },
    }));
    const r = await signIn(BASE, RUECKRUF, {
      ...basis,
      openWindow: () => {
        const w = basis.openWindow();
        const vorher = fenster.beiAdresse;
        // Wie die echte Rückruf-Seite: erst die Nachricht, dann sofort zu.
        fenster.beiAdresse = (url) => { vorher?.(url); fenster.close(); };
        return w;
      },
      pollMs: 1,
    });
    expect(r.ok).toBe(true);
  });
});
