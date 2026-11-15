// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import {
  MCP_ACCESS_STORAGE_KEY, clearAccessBlock, holdAccessBlock, readAccessBlock, sessionBlockOwner,
  writeAccessBlock,
} from './mcp-access';
import {
  readSessionPerson, runSessionLogin, sessionLoginTarget, type SessionLoginContext,
} from './session-login';

const ORIGIN = 'https://repository.example.org';
const URL_ = `${ORIGIN}/edu-sharing/services/wlo-mcp/auth/session`;
const ICH = `${ORIGIN}/edu-sharing/rest/iam/v1/people/-home-/-me-`;
const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';

interface Antwort { status?: number; body?: unknown; roh?: string }
interface Ruf { url: string; init: RequestInit }

/** Antworten je Adresse, der Reihe nach; sammelt nebenbei, was wohin ging. */
function fetchStub(plan: Record<string, (Antwort | 'netzfehler')[]>): { rufe: Ruf[]; impl: typeof fetch } {
  const rufe: Ruf[] = [];
  const rest = Object.fromEntries(Object.entries(plan).map(([k, v]) => [k, [...v]]));
  const impl = (async (url: unknown, init?: RequestInit) => {
    rufe.push({ url: String(url), init: init ?? {} });
    const antwort = rest[String(url)]?.shift();
    if (antwort === undefined) throw new Error(`unerwarteter Abruf: ${String(url)}`);
    if (antwort === 'netzfehler') throw new TypeError('failed to fetch');
    return new Response(antwort.roh ?? JSON.stringify(antwort.body ?? {}), {
      status: antwort.status ?? 200,
      headers: { 'content-type': antwort.roh === undefined ? 'application/json' : 'text/html' },
    });
  }) as typeof fetch;
  return { rufe, impl };
}

const person = (authorityName: string): Antwort => ({ body: { person: { authorityName } } });
const getauscht = (over: Record<string, unknown> = {}): Antwort =>
  ({ body: { ok: true, block: BLOCK, authority: 'lehrerin', displayName: 'Lea Lehrerin', ...over } });

function ctx(impl: typeof fetch, over: Partial<SessionLoginContext> = {}): SessionLoginContext {
  return { sessionUrl: () => URL_, origin: () => ORIGIN, fetchImpl: impl, warten: async () => undefined, ...over };
}

beforeEach(() => {
  sessionStorage.clear();
  clearAccessBlock();
});

describe('sessionLoginTarget', () => {
  it('nimmt die Adresse auf der Herkunft der Seite und leitet den Wer-bin-ich-Pfad ab', () => {
    expect(sessionLoginTarget(URL_, ORIGIN)).toEqual({
      exchangePath: '/edu-sharing/services/wlo-mcp/auth/session',
      identityPath: '/edu-sharing/rest/iam/v1/people/-home-/-me-',
    });
    expect(sessionLoginTarget(`  ${URL_} `, `${ORIGIN}/`), 'Leerraum und Schrägstrich am Ende').not.toBeNull();
  });

  it('auf einer anderen Seite gilt der Weg nicht', () => {
    expect(sessionLoginTarget(URL_, 'https://wirlernenonline.de')).toBeNull();
    expect(sessionLoginTarget(URL_, 'http://repository.example.org'), 'anderes Schema').toBeNull();
    expect(sessionLoginTarget(URL_, 'https://repository.example.org:8443'), 'anderer Port').toBeNull();
    expect(sessionLoginTarget(URL_, 'null'), 'Seite ohne Herkunft').toBeNull();
    expect(sessionLoginTarget('', ORIGIN)).toBeNull();
  });

  it('lässt sich nicht auf einen anderen Pfad der Seite lenken', () => {
    const nein = [
      `${ORIGIN}/edu-sharing/rest/node/v1/nodes/-home-/abc`,           // endet nicht auf /auth/session
      `${ORIGIN}/auth/session`,                                        // ohne Wurzel des Repositorys
      `${ORIGIN}/edu-sharing/auth/session?next=/x`,                    // Abfrage
      `${ORIGIN}/edu-sharing/auth/session#x`,                          // Anker
      `${ORIGIN}/edu-sharing/%2e%2e/auth/session`,                     // steigt auf: ohne Wurzel
      `${ORIGIN}/edu-sharing/%61uth/session`,                          // Kodierung
      `${ORIGIN}/edu-sharing/auth/session;x=1`,                        // Pfad-Parameter
      `${ORIGIN}/edu-sharing/auth/session/`,                           // etwas angehängt
      // Rückstrich: der Browser läse `/x/auth/session`, mit der Wurzel `x` — deshalb gilt der
      // geschriebene Wert, nicht seine Deutung.
      `${ORIGIN}\\x/auth/session`,
      `${ORIGIN}/x/../edu-sharing/auth/session`,                       // Punkt-Stufe vor der Wurzel
      `${ORIGIN}/./edu-sharing/auth/session`,
      `${ORIGIN}:/edu-sharing/auth/session`,                           // leerer Port
      'https:repository.example.org/edu-sharing/auth/session',         // ohne Schrägstriche
      'HTTPS://repository.example.org/edu-sharing/auth/session',       // Schema groß
      'https://@repository.example.org/edu-sharing/auth/session',      // leerer Benutzerteil
      'https://repository_x.example.org/edu-sharing/auth/session',     // Unterstrich im Host
      `${ORIGIN}/edu-sharing/a.b/auth/session`,                        // Punkt in einer Stufe
      `${ORIGIN}/edu-sharing//auth/session`,                           // leere Stufe
      `https://nutzer:geheim@repository.example.org/edu-sharing/auth/session`,
      '/edu-sharing/services/wlo-mcp/auth/session',                    // ohne Herkunft: nicht prüfbar
      '//repository.example.org/edu-sharing/auth/session',
      'javascript:alert(1)',
    ];
    for (const url of nein) expect(sessionLoginTarget(url, ORIGIN), url).toBeNull();
  });

  it('geprüft wird, was dasteht: der Pfad muss so geschrieben sein, wie der Browser ihn liest', () => {
    // Punkt-Stufen löste der Browser auf; das Backend lehnt sie ab, das Widget ebenso.
    expect(sessionLoginTarget(`${ORIGIN}/edu-sharing/x/../auth/session`, ORIGIN)).toBeNull();
    expect(sessionLoginTarget(`${ORIGIN}/edu-sharing/auth/\tsession`, ORIGIN), 'Tabulator').toBeNull();
    // Der Vorgabe-Port darf dastehen: die Herkunft ist dieselbe.
    expect(sessionLoginTarget(`${ORIGIN}:443/edu-sharing/auth/session`, ORIGIN)?.exchangePath)
      .toBe('/edu-sharing/auth/session');
  });
});

describe('runSessionLogin', () => {
  it('fragt erst, wer da ist, tauscht dann und hält den Block nur im Arbeitsspeicher', async () => {
    const stub = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht()] });
    const ergebnis = await runSessionLogin(ctx(stub.impl));

    expect(ergebnis).toEqual({ outcome: 'done', displayName: 'Lea Lehrerin', authority: 'lehrerin' });
    expect(readAccessBlock()).toBe(BLOCK);
    expect(sessionBlockOwner(), 'der Block trägt, für wen er gilt')
      .toEqual({ authority: 'lehrerin', displayName: 'Lea Lehrerin' });
    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY), 'nicht im Web-Speicher').toBeNull();
    expect(stub.rufe.map((r) => r.url)).toEqual([ICH, URL_]);
    const [ich, tausch] = stub.rufe;
    expect(ich!.init.credentials).toBe('same-origin');
    expect(ich!.init.redirect, 'keiner Umleitung folgen').toBe('error');
    expect(ich!.init.method ?? 'GET').toBe('GET');
    expect(tausch!.init.method).toBe('POST');
    expect(tausch!.init.credentials).toBe('same-origin');
    expect(tausch!.init.redirect, 'keiner Umleitung folgen').toBe('error');
    expect(tausch!.init.body).toBe('{}');
    expect(new Headers(tausch!.init.headers).get('content-type')).toBe('application/json');
    expect(new Headers(tausch!.init.headers).has('authorization'), 'nie zusammen mit dem Cookie').toBe(false);
  });

  it('auf einer anderen Seite geht keine Anfrage hinaus', async () => {
    const stub = fetchStub({});
    const ergebnis = await runSessionLogin(ctx(stub.impl, { origin: () => 'https://wirlernenonline.de' }));
    expect(ergebnis.outcome).toBe('off');
    expect(stub.rufe.length).toBe(0);
  });

  it('ein Gast wird nicht getauscht', async () => {
    const stub = fetchStub({ [ICH]: [person('esguest')] });
    expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('no-session');
    expect(stub.rufe.length, 'nur die Frage, kein Tausch').toBe(1);
    expect(readAccessBlock()).toBeNull();
  });

  it('antwortet die Seite nicht wie ein Repository, wird nicht getauscht', async () => {
    for (const antwort of [{ status: 404 }, { status: 500 }, { roh: '<html>' }, { body: { person: {} } }, 'netzfehler'] as const) {
      const stub = fetchStub({ [ICH]: [antwort] });
      expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('unreachable');
      expect(stub.rufe.length).toBe(1);
    }
  });

  it('nennt der Tausch eine andere Person als die Seite, wird der Block verworfen', async () => {
    const stub = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht({ authority: 'jemand-anders' })] });
    expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('mismatch');
    expect(readAccessBlock()).toBeNull();
  });

  it('ohne genannte Person gilt der Tausch nicht', async () => {
    const stub = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht({ authority: undefined })] });
    expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('mismatch');
    expect(readAccessBlock()).toBeNull();
  });

  it('übersetzt die Antworten der Tauschstelle in je ein Wort', async () => {
    const faelle: [Antwort, string][] = [
      [{ status: 400, body: { error: 'keine Sitzung' } }, 'no-session'],
      [{ status: 403, body: { code: 'origin_not_allowed' } }, 'not-allowed'],
      [{ status: 404, body: { error: 'aus' } }, 'unavailable'],
      [{ status: 415 }, 'rejected'],
      [{ status: 500 }, 'rejected'],
      // Ohne den eingehängten Pfad antwortet manches Repository mit seiner Startseite.
      [{ roh: '<!doctype html><html></html>' }, 'unavailable'],
      [{ body: { ok: false } }, 'rejected'],
    ];
    for (const [antwort, wort] of faelle) {
      const stub = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [antwort] });
      expect((await runSessionLogin(ctx(stub.impl))).outcome, JSON.stringify(antwort)).toBe(wort);
      expect(readAccessBlock()).toBeNull();
    }
  });

  it('503 ist kein Urteil: einmal warten und erneut', async () => {
    const wartezeiten: number[] = [];
    const warten = async (ms: number) => { wartezeiten.push(ms); };
    const einmal = fetchStub({
      [ICH]: [person('lehrerin')],
      [URL_]: [{ status: 503, body: { code: 'upstream_unreachable', retryAfter: 2 } }, getauscht()],
    });
    expect((await runSessionLogin(ctx(einmal.impl, { warten }))).outcome).toBe('done');
    expect(wartezeiten).toEqual([2000]);

    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');
    const zweimal = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [{ status: 503 }, { status: 503 }] });
    expect((await runSessionLogin(ctx(zweimal.impl, { warten }))).outcome).toBe('unreachable');
    expect(readAccessBlock(), 'ein vorhandener Block bleibt').toBe('wlo2.YWx0.aXY.Y3Q');
  });

  it('429 nennt eine Wartezeit: einmal warten und erneut, dann abgelehnt', async () => {
    const wartezeiten: number[] = [];
    const warten = async (ms: number) => { wartezeiten.push(ms); };
    const einmal = fetchStub({
      [ICH]: [person('lehrerin')],
      [URL_]: [{ status: 429, body: { code: 'too_many_logins', retryAfter: 3 } }, getauscht()],
    });
    expect((await runSessionLogin(ctx(einmal.impl, { warten }))).outcome).toBe('done');
    expect(wartezeiten).toEqual([3000]);

    const zweimal = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [{ status: 429 }, { status: 429 }] });
    expect((await runSessionLogin(ctx(zweimal.impl, { warten }))).outcome).toBe('rejected');
  });

  it('ein hängender Abruf endet an der Frist', async () => {
    // Ohne Frist bliebe der Tausch für immer „laufend“, und jeder spätere Anlass hinge an ihm.
    const haengt = ((_url: unknown, init?: RequestInit) => new Promise<Response>((_, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Frist', 'TimeoutError')));
    })) as typeof fetch;
    expect((await runSessionLogin(ctx(haengt, { fristMs: 20 }))).outcome).toBe('unreachable');

    const nurTausch = (async (url: unknown, init?: RequestInit) => {
      if (String(url) === ICH) return new Response(JSON.stringify({ person: { authorityName: 'lehrerin' } }));
      return haengt(url as string, init);
    }) as typeof fetch;
    expect((await runSessionLogin(ctx(nurTausch, { fristMs: 20 }))).outcome).toBe('unreachable');
  });

  it('ein Netzfehler beim Tausch wirft nicht', async () => {
    const stub = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: ['netzfehler'] });
    expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('unreachable');
  });

  it('was kein Block ist, landet nicht im Speicher', async () => {
    const stub = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht({ block: 'Bearer abc' })] });
    expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('store-failed');
    expect(readAccessBlock()).toBeNull();
  });

  it('die Person der Seite ersetzt einen mitgebrachten Block, ein Fehlschlag lässt ihn stehen', async () => {
    writeAccessBlock('wlo2.YWx0.aXY.Y3Q');
    const nein = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [{ status: 400 }] });
    await runSessionLogin(ctx(nein.impl));
    expect(readAccessBlock()).toBe('wlo2.YWx0.aXY.Y3Q');

    const ja = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht()] });
    await runSessionLogin(ctx(ja.impl));
    expect(readAccessBlock()).toBe(BLOCK);
    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY), 'der alte Block liegt nicht mehr im Web-Speicher').toBeNull();
  });

  it('ein Block aus der Sitzung einer früheren Person fällt weg, sobald die Seite jemand anderen zeigt', async () => {
    // Review 2026-11-15: die Gastseite baut das Widget neu, der Block der vorigen Instanz liegt
    // noch im Arbeitsspeicher. Zeigt die Seite jetzt einen Gast oder jemand anderen, gehört er
    // nicht mehr hierher — auch wenn der neue Tausch scheitert.
    const LEA = { authority: 'lehrerin', displayName: 'Lea Lehrerin' };
    holdAccessBlock(BLOCK, LEA);
    await runSessionLogin(ctx(fetchStub({ [ICH]: [person('esguest')] }).impl));
    expect(readAccessBlock(), 'Gast').toBeNull();

    holdAccessBlock(BLOCK, LEA);
    await runSessionLogin(ctx(fetchStub({ [ICH]: [person('redakteur')], [URL_]: [{ status: 500 }] }).impl));
    expect(readAccessBlock(), 'andere Person, Tausch gescheitert').toBeNull();

    // Dieselbe Person, Tausch gescheitert: der Block bleibt.
    holdAccessBlock(BLOCK, LEA);
    await runSessionLogin(ctx(fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [{ status: 500 }] }).impl));
    expect(readAccessBlock()).toBe(BLOCK);

    // Keine Antwort des Repositorys ist kein Urteil.
    await runSessionLogin(ctx(fetchStub({ [ICH]: ['netzfehler'] }).impl));
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('der Anzeigename wird gekürzt und fehlt, wenn er keiner ist', async () => {
    const lang = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht({ displayName: ` ${'x'.repeat(200)} ` })] });
    expect((await runSessionLogin(ctx(lang.impl))).displayName.length).toBe(80);
    const keiner = fetchStub({ [ICH]: [person('lehrerin')], [URL_]: [getauscht({ displayName: 7 })] });
    expect((await runSessionLogin(ctx(keiner.impl))).displayName).toBe('');
  });
});

describe('readSessionPerson', () => {
  it('nennt die Person der Seite, auch den Gast', async () => {
    expect(await readSessionPerson(ctx(fetchStub({ [ICH]: [person('lehrerin')] }).impl))).toBe('lehrerin');
    expect(await readSessionPerson(ctx(fetchStub({ [ICH]: [person('esguest')] }).impl))).toBe('esguest');
  });

  it('ohne Antwort des Repositorys gibt es keine Aussage — auch kein „Gast“', async () => {
    for (const antwort of [{ status: 500 }, { status: 403 }, { roh: '<html>' }, { body: {} }, 'netzfehler'] as const) {
      expect(await readSessionPerson(ctx(fetchStub({ [ICH]: [antwort] }).impl))).toBeNull();
    }
  });

  it('401 heißt „niemand angemeldet“ — ein Repository ohne Gast-Zugang sagt es so', async () => {
    // Gemessen an Staging (mit `DisableGuest`): 401, ohne `WWW-Authenticate`. Als „keine Aussage“
    // gelesen, fiele das Abmelden dort nie auf.
    expect(await readSessionPerson(ctx(fetchStub({ [ICH]: [{ status: 401 }] }).impl))).toBe('esguest');
    const stub = fetchStub({ [ICH]: [{ status: 401 }] });
    expect((await runSessionLogin(ctx(stub.impl))).outcome).toBe('no-session');
    expect(stub.rufe.length, 'kein Tausch').toBe(1);
  });

  it('die Frist greift auch ohne `AbortSignal.timeout` (ältere Browser)', async () => {
    const eigen = Object.getOwnPropertyDescriptor(AbortSignal, 'timeout');
    Object.defineProperty(AbortSignal, 'timeout', { value: undefined, configurable: true });
    try {
      const haengt = ((_url: unknown, init?: RequestInit) => new Promise<Response>((_, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Frist', 'AbortError')));
      })) as typeof fetch;
      expect(await readSessionPerson(ctx(haengt, { fristMs: 20 }))).toBeNull();
    } finally {
      if (eigen) Object.defineProperty(AbortSignal, 'timeout', eigen);
    }
  });

  it('auf einer anderen Seite fragt sie nicht', async () => {
    const stub = fetchStub({});
    expect(await readSessionPerson(ctx(stub.impl, { origin: () => 'https://wirlernenonline.de' }))).toBeNull();
    expect(stub.rufe.length).toBe(0);
  });
});
