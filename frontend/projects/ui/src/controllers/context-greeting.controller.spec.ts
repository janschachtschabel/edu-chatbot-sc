import { describe, expect, it } from 'vitest';

import { ChatResponse, DebugInfo } from '../grouping/message-types';
import { ContextGreetingContext, ContextGreetingController } from './context-greeting.controller';

/**
 * Charakterisierung des ContextGreetingControllers — Verbatim-Port aus ALT
 * (nur integrativ gedeckt). Gepinnt: stiller Ping (kein User-/Loading-Bubble),
 * env `page_event=context_open` + page_context, Render nur bei Inhalt,
 * Ping-Guard, resetForNewPage, Loading-Guard, Fehler-Schlucken.
 */
interface Calls {
  bot: Array<{ id: string; content: string; loading?: boolean }>;
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
    isLoading: over.isLoading ?? (() => loading),
    setLoading: (v) => {
      loading = v;
      calls.loading.push(v);
    },
    addBotMessage: (c, isLoading) => {
      const id = 'b' + ++n;
      calls.bot.push({ id, content: c, loading: isLoading });
      return id;
    },
    removeMessage: () => {},
    setScrollTarget: (id) => calls.scroll.push(id),
    setLatestDebug: (d) => calls.debug.push(d),
  };
  return { ctx, calls };
}

function makeResp(fields: Partial<ChatResponse> = {}): ChatResponse {
  return {
    session_id: 's', content: 'Willkommen zurück', cards: [], follow_up: '', quick_replies: [],
    debug: { pattern: 'M17' } as DebugInfo, page_action: null, pagination: null, ...fields,
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
    expect(calls.debug.length).toBe(1);
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
