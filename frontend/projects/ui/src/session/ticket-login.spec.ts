// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import { readAccessBlock, writeAccessBlock } from './mcp-access';
import { runTicketLogin, type TicketLoginContext } from './ticket-login';

const TICKET = 'TICKET_c001d00dfeedface0123456789abcdef01234567';
const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';
const BASE = 'https://mcp.example.org';

/** Antwort-Stub; sammelt nebenbei, was wohin ging. */
function fetchStub(
  antwort: { status?: number; body?: unknown } | 'netzfehler',
): { calls: { url: string; body: string }[]; impl: typeof fetch } {
  const calls: { url: string; body: string }[] = [];
  const impl = (async (url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), body: String(init?.body ?? '') });
    if (antwort === 'netzfehler') throw new TypeError('failed to fetch');
    return new Response(JSON.stringify(antwort.body ?? {}), {
      status: antwort.status ?? 200,
      headers: { 'content-type': 'application/json' },
    });
  }) as typeof fetch;
  return { calls, impl };
}

function ctx(over: Partial<TicketLoginContext> = {}): TicketLoginContext {
  return { ticket: () => TICKET, mcpAuthBase: () => BASE, ...over };
}

beforeEach(() => sessionStorage.clear());

describe('runTicketLogin', () => {
  it('tauscht das Ticket an der Anmelde-Herkunft und legt den Block ab', async () => {
    const stub = fetchStub({ body: { ok: true, block: BLOCK, authority: 'lehrerin' } });
    const ausgang = await runTicketLogin(ctx({ fetchImpl: stub.impl }));
    expect(ausgang).toBe('done');
    expect(readAccessBlock()).toBe(BLOCK);
    expect(stub.calls[0]?.url).toBe(`${BASE}/auth/ticket`);
    expect(JSON.parse(stub.calls[0]!.body)).toEqual({ ticket: TICKET });
  });

  it('ohne Ticket oder ohne Anmelde-Adresse passiert gar nichts', async () => {
    const stub = fetchStub({ body: {} });
    expect(await runTicketLogin(ctx({ ticket: () => '  ', fetchImpl: stub.impl }))).toBe('no-ticket');
    expect(await runTicketLogin(ctx({ mcpAuthBase: () => '', fetchImpl: stub.impl }))).toBe('unavailable');
    expect(stub.calls.length, 'kein Netzverkehr für nichts').toBe(0);
  });

  it('404 heisst „diese Anlage gibt keine Blöcke aus", nicht „abgelehnt"', async () => {
    // Ohne WLO_AUTH_PRIVATE_KEY existiert der Endpunkt nicht — eine
    // Betriebsentscheidung, dieselbe Bedeutung wie eine leere Anmelde-Adresse.
    const stub = fetchStub({ status: 404, body: { error: 'aus' } });
    expect(await runTicketLogin(ctx({ fetchImpl: stub.impl }))).toBe('unavailable');
    expect(readAccessBlock()).toBeNull();
  });

  it('ein abgelehntes Ticket räumt einen vorhandenen Block NICHT weg', async () => {
    // Die Seite kann ein abgelaufenes Ticket im Template haben; eine bestehende
    // Anmeldung (z.B. über das Fenster) darf daran nicht sterben.
    writeAccessBlock(BLOCK);
    const stub = fetchStub({ status: 400, body: { error: 'abgelaufen' } });
    expect(await runTicketLogin(ctx({ fetchImpl: stub.impl }))).toBe('rejected');
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('ein gültiges Ticket ERSETZT einen vorhandenen Block — die Seite benennt, wer hier ist', async () => {
    writeAccessBlock(BLOCK);
    const neuer = 'wlo2.bmV1.aXY.Y3Q';
    const stub = fetchStub({ body: { ok: true, block: neuer } });
    expect(await runTicketLogin(ctx({ fetchImpl: stub.impl }))).toBe('done');
    expect(readAccessBlock()).toBe(neuer);
  });

  it('Netzfehler und Serverschrott enden in einem Wort, nie in einer Zusage', async () => {
    expect(await runTicketLogin(ctx({ fetchImpl: fetchStub('netzfehler').impl }))).toBe('unreachable');
    // ok:true, aber der „Block" ist keiner: der Form-Wächter der Ablage greift.
    const schrott = fetchStub({ body: { ok: true, block: 'Bearer kaputt\r\n' } });
    expect(await runTicketLogin(ctx({ fetchImpl: schrott.impl }))).toBe('store-failed');
    expect(readAccessBlock()).toBeNull();
    // ok fehlt → der Server hat entschieden, nicht wir.
    const ohneOk = fetchStub({ body: { block: BLOCK } });
    expect(await runTicketLogin(ctx({ fetchImpl: ohneOk.impl }))).toBe('rejected');
  });

  it('die Basis darf mit Schrägstrichen enden, der Pfad bleibt derselbe', async () => {
    const stub = fetchStub({ body: { ok: true, block: BLOCK } });
    await runTicketLogin(ctx({ mcpAuthBase: () => `${BASE}//`, fetchImpl: stub.impl }));
    expect(stub.calls[0]?.url).toBe(`${BASE}/auth/ticket`);
  });
});
