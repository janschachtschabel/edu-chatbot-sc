import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatStreamEvent, parseSseBlock, postChat, streamChat, StreamStaleError } from './stream-client';

/**
 * Charakterisierung des Chat-Stream-Transports — Verbatim-Port des ALT
 * `ApiService.sendMessageStream`/`sendMessage`-SSE-Kerns. `fetchImpl` wird
 * injiziert; ein echter `ReadableStream` liefert die SSE-Blöcke. Erwartungen
 * aus dem ALT-Quelltext abgeleitet.
 */

/** Baut eine Response-artige mit einem ReadableStream aus SSE-Text-Chunks. */
function sseResponse(chunks: string[], init: { ok?: boolean; status?: number } = {}): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const enc = new TextEncoder();
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
  return { ok: init.ok ?? true, status: init.status ?? 200, body: stream } as unknown as Response;
}

/** fetchImpl, das eine feste Response liefert. */
function fetchReturning(resp: Response): typeof fetch {
  return (async () => resp) as unknown as typeof fetch;
}

describe('parseSseBlock', () => {
  it('extrahiert event + JSON-data, ignoriert Keepalive-/Kommentar-Zeilen', () => {
    expect(parseSseBlock('event: phase\ndata: {"step":"assess"}')).toEqual({
      event: 'phase',
      data: { step: 'assess' },
    });
    expect(parseSseBlock(': keepalive')).toEqual({ event: 'message', data: {} });
    expect(parseSseBlock('event: connected\ndata: {}')).toEqual({ event: 'connected', data: {} });
  });

  it('joint mehrere data-Zeilen mit \\n; Nicht-JSON → { raw }', () => {
    expect(parseSseBlock('event: x\ndata: {"a":1}\ndata: garbage').data).toEqual({ raw: '{"a":1}\ngarbage' });
    expect(parseSseBlock('data: nope').data).toEqual({ raw: 'nope' });
  });
});

describe('streamChat', () => {
  it('ruft onEvent für connected/phase und löst mit dem result-Payload', async () => {
    const events: ChatStreamEvent[] = [];
    const resp = sseResponse([
      'event: connected\ndata: {}\n\n',
      'event: phase\ndata: {"step":"route"}\n\n',
      'event: result\ndata: {"content":"Hallo","session_id":"s1"}\n\n',
    ]);
    const result = await streamChat<{ content: string; session_id: string }>({
      url: '/api/chat/stream',
      body: { message: 'hi' },
      onEvent: (e) => events.push(e),
      fetchImpl: fetchReturning(resp),
    });
    expect(events.map((e) => e.event)).toEqual(['connected', 'phase']);
    expect(events[1].data).toEqual({ step: 'route' });
    expect(result).toEqual({ content: 'Hallo', session_id: 's1' });
  });

  it('wirft bei error-Event mit der Server-Message', async () => {
    const resp = sseResponse(['event: error\ndata: {"message":"boom"}\n\n']);
    await expect(
      streamChat({ url: 'x', body: {}, onEvent: () => {}, fetchImpl: fetchReturning(resp) }),
    ).rejects.toThrow('boom');
  });

  it('wirft bei nicht-ok Response', async () => {
    const resp = sseResponse([], { ok: false, status: 502 });
    await expect(
      streamChat({ url: 'x', body: {}, onEvent: () => {}, fetchImpl: fetchReturning(resp) }),
    ).rejects.toThrow('Chat stream error: 502');
  });

  it('wirft wenn der Stream ohne result-Event endet', async () => {
    const resp = sseResponse(['event: phase\ndata: {"step":"x"}\n\n']);
    await expect(
      streamChat({ url: 'x', body: {}, onEvent: () => {}, fetchImpl: fetchReturning(resp) }),
    ).rejects.toThrow('Stream ended without a result event');
  });

  it('flusht den Trailing-Block ohne finales \\n\\n', async () => {
    const resp = sseResponse(['event: result\ndata: {"content":"ok"}']); // kein \n\n
    const result = await streamChat<{ content: string }>({
      url: 'x',
      body: {},
      onEvent: () => {},
      fetchImpl: fetchReturning(resp),
    });
    expect(result).toEqual({ content: 'ok' });
  });
});

describe('streamChat Watchdogs (fake timers)', () => {
  afterEach(() => vi.useRealTimers());

  /** Stream, der `signal.abort` in einen Stream-Error übersetzt (wie fetch). */
  function abortableFetch(onStart: (controller: ReadableStreamDefaultController<Uint8Array>) => void): typeof fetch {
    return (async (_url: unknown, init: any) => {
      const signal: AbortSignal = init.signal;
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          signal.addEventListener('abort', () =>
            controller.error(new DOMException('aborted', 'AbortError')),
          );
          onStart(controller);
        },
      });
      return { ok: true, status: 200, body: stream } as unknown as Response;
    }) as unknown as typeof fetch;
  }

  it('Idle-Watchdog: keine Bytes → Abbruch, aber KEIN StreamStaleError', async () => {
    vi.useFakeTimers();
    const p = streamChat({
      url: 'x',
      body: {},
      onEvent: () => {},
      fetchImpl: abortableFetch(() => {
        /* never enqueue */
      }),
      idleMs: 90,
      staleMs: 100,
    });
    const assertion = expect(p).rejects.not.toBeInstanceOf(StreamStaleError);
    await vi.advanceTimersByTimeAsync(95);
    await assertion;
  });

  it('Stale-Watchdog: Keepalives halten Idle offen, aber 100 s ohne benanntes Event → StreamStaleError', async () => {
    vi.useFakeTimers();
    const enc = new TextEncoder();
    const p = streamChat({
      url: 'x',
      body: {},
      onEvent: () => {},
      fetchImpl: abortableFetch((controller) => {
        controller.enqueue(enc.encode(': ka\n\n')); // t=0 → resettet Idle, NICHT Stale
        setTimeout(() => controller.enqueue(enc.encode(': ka\n\n')), 50); // t=50 → Idle → 140
      }),
      idleMs: 90,
      staleMs: 100,
    });
    const assertion = expect(p).rejects.toBeInstanceOf(StreamStaleError);
    await vi.advanceTimersByTimeAsync(105); // Stale feuert bei 100 vor Idle (140)
    await assertion;
  });
});

describe('postChat', () => {
  it('POST → json bei ok', async () => {
    const resp = { ok: true, status: 200, json: async () => ({ content: 'x' }) } as unknown as Response;
    const out = await postChat<{ content: string }>({ url: '/api/chat', body: {}, fetchImpl: fetchReturning(resp) });
    expect(out).toEqual({ content: 'x' });
  });

  it('wirft bei nicht-ok', async () => {
    const resp = { ok: false, status: 500 } as unknown as Response;
    await expect(postChat({ url: 'x', body: {}, fetchImpl: fetchReturning(resp) })).rejects.toThrow('Chat error: 500');
  });
});
