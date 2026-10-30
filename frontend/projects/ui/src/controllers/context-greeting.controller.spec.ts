import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { ContextGreetingContext, ContextGreetingController } from './context-greeting.controller';

/**
 * Charakterisierung des ContextGreetingControllers — Verbatim-Port aus ALT
 * (nur integrativ gedeckt). Gepinnt: stiller Ping (kein User-/Loading-Bubble),
 * env `page_event=context_open` + page_context, Render nur bei Inhalt,
 * Ping-Guard, resetForNewPage, Loading-Guard, Fehler-Schlucken.
 */
interface Calls {
  bot: Array<{ id: string; content: string; loading?: boolean; rest: unknown[] }>;
  scroll: string[];
  debug: unknown[];
  loading: boolean[];
}

function makeCtx(over: Partial<ContextGreetingContext> = {}): { ctx: ContextGreetingContext; calls: Calls } {
  const calls: Calls = { bot: [], scroll: [], debug: [], loading: [] };
  let loading = false;
  let n = 0;
  const ctx: ContextGreetingContext = {
    sendMessage: over.sendMessage ?? (async () => makeResp()),
    pageContext: over.pageContext ?? (() => ({})),
    sessionId: over.sessionId ?? (() => 'bb-1'),
    isLoading: over.isLoading ?? (() => loading),
    setLoading: (v) => {
      loading = v;
      calls.loading.push(v);
    },
    addBotMessage: (c, isLoading, ...rest) => {
      const id = 'b' + ++n;
      calls.bot.push({ id, content: c, loading: isLoading, rest });
      return id;
    },
    removeMessage: () => {},
    setScrollTarget: (id) => calls.scroll.push(id),
    setLatestDebug: (d, ui) => calls.debug.push([d, ui]),
  };
  return { ctx, calls };
}

function makeResp(fields: Partial<ChatResponse> = {}): ChatResponse {
  return {
    session_id: 's', content: 'Willkommen zurück', cards: [], follow_up: '', quick_replies: [],
    debug: null, ui: { pattern: 'CTX:collection' }, page_action: null, pagination: null, ...fields,
  } as ChatResponse;
}

describe('ContextGreetingController', () => {
  it('sendContextPing: stiller Ping (env context_open + page_context), Render bei Inhalt', async () => {
    let sent: { msg: string; env: any } | null = null;
    const { ctx, calls } = makeCtx({
      pageContext: () => ({ nodeType: 'collection', nodeId: 'c1' }),
      sendMessage: async (msg, env) => {
        sent = { msg, env };
        return makeResp({ content: 'Hallo auf der Sammlung' });
      },
    });
    await new ContextGreetingController(ctx).sendContextPing();

    expect(sent!.msg).toBe('[context-open]');
    expect(sent!.env).toEqual({ page_event: 'context_open', page_context: { nodeType: 'collection', nodeId: 'c1' } });
    // Kein Loading-Bubble (stiller Hintergrund-Ping), aber echte Antwort gerendert
    expect(calls.bot.length).toBe(1);
    expect(calls.bot[0]).toMatchObject({ content: 'Hallo auf der Sammlung', loading: false });
    expect(calls.scroll.length).toBe(1);
    // Paket 18C/D: `ui` an Position 5 — das CTX-Muster entscheidet beim Wiederherstellen über die Startnachricht.
    expect(calls.bot[0].rest[2]).toEqual({ pattern: 'CTX:collection' });
    expect(calls.debug).toEqual([[null, { pattern: 'CTX:collection' }]]);
    expect(calls.loading).toEqual([true, false]);
  });

  it('leere Antwort (kein content, keine QR) → NICHT gerendert, Loading trotzdem getoggelt', async () => {
    const { ctx, calls } = makeCtx({ sendMessage: async () => makeResp({ content: '  ', quick_replies: [] }) });
    await new ContextGreetingController(ctx).sendContextPing();
    expect(calls.bot.length).toBe(0);
    expect(calls.loading).toEqual([true, false]);
  });

  it('Ping-Guard: zweiter Aufruf No-Op; resetForNewPage erlaubt erneut', async () => {
    let n = 0;
    const { ctx } = makeCtx({ sendMessage: async () => (n++, makeResp({ content: 'x' })) });
    const c = new ContextGreetingController(ctx);
    await c.sendContextPing();
    await c.sendContextPing(); // Guard
    expect(n).toBe(1);
    c.resetForNewPage();
    await c.sendContextPing();
    expect(n).toBe(2);
  });

  it('isLoading → No-Op (kein sendMessage)', async () => {
    let sent = false;
    const { ctx } = makeCtx({ isLoading: () => true, sendMessage: async () => ((sent = true), makeResp()) });
    await new ContextGreetingController(ctx).sendContextPing();
    expect(sent).toBe(false);
  });

  it('sendMessage wirft → still geschluckt, Loading false', async () => {
    const { ctx, calls } = makeCtx({ sendMessage: async () => { throw new Error('x'); } });
    await new ContextGreetingController(ctx).sendContextPing();
    expect(calls.bot.length).toBe(0);
    expect(calls.loading).toEqual([true, false]);
  });
});

// Paket 3, T6 (Review 2026-10-03): der Ping gehört der Sitzung, in der er begann.
describe('ContextGreetingController nach einem Neustart', () => {
  it('kein Rendern, keine Freigabe, gemeldet als nicht gerendert', async () => {
    let sitzung = 'bb-1';
    const { ctx, calls } = makeCtx({
      sessionId: () => sitzung,
      sendMessage: async () => { sitzung = 'bb-2'; return makeResp({ content: 'Hallo Seite' }); },
    });
    const gerendert = await new ContextGreetingController(ctx).sendContextPing();
    expect(gerendert).toBe(false);
    expect(calls.bot.length).toBe(0);
    expect(calls.loading).toEqual([true]);
  });
});

// ── Paket 18E: Spur in der Konsole — die Fehlerart, nie der Text ─────────────
const MARKE = 'KANARIE7Q';
const ausgabe = (spy: { mock: { calls: unknown[][] } }): string =>
  spy.mock.calls.flat().map(String).join(' ');

describe('Paket 18E: Spur des stillen Pings', () => {
  afterEach(() => vi.restoreAllMocks());

  it('ein gescheiterter Ping steht auf DEBUG, ohne Text', async () => {
    const debug = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const { ctx } = makeCtx({ sendMessage: async () => { throw new Error(MARKE); } });
    await new ContextGreetingController(ctx).sendContextPing();
    expect(debug).toHaveBeenCalledTimes(1);
    expect(ausgabe(debug)).toContain('Error');
    expect(ausgabe(debug)).not.toContain(MARKE);
  });
});
