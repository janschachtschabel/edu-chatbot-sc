import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Turn-Maschinerie der Chat-Shell (8-4S-d2a): das Wiring, mit dem die Shell den
 * `SendMessageContext` (8-4S-c) baut + die Erfolgs-Seiteneffekte (`onResult`)
 * verdrahtet. Gepinnt: sendMessage produziert User+Bot-Bubble über das LIVE
 * `_api` (mit `sessionId` gebunden), Stale-freier POST-Fallback, und onResult
 * setzt latestDebug + feuert das query-meta-Event + dispatcht die page_action.
 * NICHT erneut getestet: der runSendMessage-Lebenszyklus selbst (8-4S-c-Spec)
 * und die Context-Delegation (8-4S-d1-Spec).
 */

const RESP = {
  content: 'Antwort', session_id: 's1', debug: { pattern: 'M06' },
  query_metas: [{ query: 'mathe', total_count: 3 }], page_action: { action: 'canvas', payload: { n: 1 } },
  cards: [], quick_replies: [],
} as unknown as ChatResponse;

function make(): ChatShellComponent {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  return TestBed.createComponent(ChatShellComponent).componentInstance;
}

/** Fake-API, das stream/post aufzeichnet und RESP liefert. `streamRejects`
 *  erzwingt den POST-Fallback-Pfad. */
function fakeApi(opts: { streamRejects?: Error } = {}) {
  return {
    stream: vi.fn(async (_sid: string, _msg: string, onEvent: (e: any) => void) => {
      if (opts.streamRejects) throw opts.streamRejects;
      onEvent({ event: 'phase', data: { step: 'wlo_search' } });
      return RESP;
    }),
    post: vi.fn(async () => RESP),
  };
}

describe('ChatShellComponent — Turn-Maschinerie (8-4S-d2a)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sendMessage: User+Bot-Bubble, _api.stream mit LIVE sessionId, isLoading am Ende false', async () => {
    const c = make();
    c.sessionId = 'sess-x';
    const api = fakeApi();
    (c as any)._api = api;

    await c.sendMessage('hallo');

    const msgs = c.messages();
    expect(msgs.map(m => [m.sender, m.content])).toEqual([['user', 'hallo'], ['bot', 'Antwort']]);
    expect(c.isLoading()).toBe(false);
    expect(api.stream.mock.calls[0][0]).toBe('sess-x'); // sessionId gebunden
    expect(api.stream.mock.calls[0][1]).toBe('hallo');
  });

  it('onResult: latestDebug gesetzt, query-meta-Event gefeuert, page_action dispatcht', async () => {
    const c = make();
    (c as any)._api = fakeApi();
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    const onPageAction = vi.fn();
    c.onPageAction = onPageAction;

    await c.sendMessage('frag');

    expect(c.latestDebug()).toEqual({ pattern: 'M06' });
    const qm = dispatchSpy.mock.calls.find(([e]) => (e as CustomEvent).type === 'badboerdi:query-meta');
    expect(qm).toBeTruthy();
    expect((qm![0] as CustomEvent).detail).toEqual({ queries: RESP.query_metas });
    expect(onPageAction).toHaveBeenCalledWith({ action: 'canvas', payload: { n: 1 } });
  });

  it('Stream-Fehler (non-stale) → stiller POST-Fallback, Bot-Bubble erscheint', async () => {
    const c = make();
    const api = fakeApi({ streamRejects: new Error('proxy down') });
    (c as any)._api = api;
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    await c.sendMessage('hallo');

    expect(api.post).toHaveBeenCalledTimes(1);
    expect(c.messages().map(m => m.sender)).toEqual(['user', 'bot']);
    expect(c.messages()[1].content).toBe('Antwort');
  });

  it('leere Eingabe / laufender Turn → no-op (Guard)', async () => {
    const c = make();
    (c as any)._api = fakeApi();
    await c.sendMessage('');            // leer
    expect(c.messages()).toEqual([]);
    c.isLoading.set(true);
    await c.sendMessage('x');           // Turn läuft
    expect(c.messages()).toEqual([]);
  });
});
