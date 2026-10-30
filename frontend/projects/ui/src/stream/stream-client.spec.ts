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

  // Token-Streaming (Plan 2026-10-01, T18): ein `text_delta` ist ein benanntes
  // Ereignis — eine lange, gestreamte Antwort läuft nicht in den Stillstand.
  it('Stale-Watchdog: text_delta-Rahmen zählen als Fortschritt', async () => {
    vi.useFakeTimers();
    const enc = new TextEncoder();
    const stueck = (text: string, pos: number) =>
      enc.encode(`event: text_delta\ndata: ${JSON.stringify({ text, pos })}\n\n`);
    const seen: string[] = [];
    const p = streamChat({
      url: 'x',
      body: {},
      onEvent: (e) => seen.push(e.event),
      fetchImpl: abortableFetch((controller) => {
        setTimeout(() => controller.enqueue(stueck('Hal', 0)), 60);
        setTimeout(() => controller.enqueue(stueck('lo', 3)), 120);
        setTimeout(() => {
          controller.enqueue(enc.encode('event: result\ndata: {"content":"Hallo"}\n\n'));
          controller.close();
        }, 180);
      }),
      idleMs: 90,
      staleMs: 100,
    });
    await vi.advanceTimersByTimeAsync(185);   // länger als staleMs, aber nie 100 ohne Rahmen
    await expect(p).resolves.toEqual({ content: 'Hallo' });
    expect(seen).toEqual(['text_delta', 'text_delta']);
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

// ── Paket 7 (P1): Kennungen im error-Rahmen und der Status am POST-Fehler ─────
describe('Fehler mit Kennung (Paket 7)', () => {
  it('ein error-Rahmen mit code wird zum StreamServerError mit dieser Kennung', async () => {
    const body = 'event: connected\ndata: {}\n\n'
      + 'event: error\ndata: {"message": "internal error", "code": "session_busy"}\n\n';
    const fetchImpl = (() => Promise.resolve(new Response(body, { status: 200 }))) as typeof fetch;
    await expect(streamChat({ url: 'x', body: {}, onEvent: () => undefined, fetchImpl }))
      .rejects.toMatchObject({ name: 'StreamServerError', code: 'session_busy' });
  });

  it('ein error-Rahmen OHNE code ist ebenso ein Bescheid des Servers (`internal`)', async () => {
    // Review Paket 7, C-1: ein nackter `Error` sah aus wie ein Transportabbruch —
    // das Widget fragte daraufhin 90 s den Verlauf nach einer Antwort ab, die der
    // gescheiterte Zug nie gespeichert hat.
    const body = 'event: connected\ndata: {}\n\n'
      + 'event: error\ndata: {"message": "internal error"}\n\n';
    const fetchImpl = (() => Promise.resolve(new Response(body, { status: 200 }))) as typeof fetch;
    await expect(streamChat({ url: 'x', body: {}, onEvent: () => undefined, fetchImpl }))
      .rejects.toMatchObject({ name: 'StreamServerError', code: 'internal', message: 'internal error' });
  });

  it('die Fehlernummer des Rahmens reist mit (Paket 18C/D)', async () => {
    const body = 'event: connected\ndata: {}\n\n'
      + 'event: error\ndata: {"message": "internal error", "nummer": "4711abcdef01"}\n\n';
    const fetchImpl = (() => Promise.resolve(new Response(body, { status: 200 }))) as typeof fetch;
    await expect(streamChat({ url: 'x', body: {}, onEvent: () => undefined, fetchImpl }))
      .rejects.toMatchObject({ name: 'StreamServerError', code: 'internal', nummer: '4711abcdef01' });
  });

  it('eine Fehlernummer außerhalb des Zeichenvorrats der Trace-ID wird nicht übernommen', async () => {
    // Die Nummer landet als Text in der Blase — nur, was eine Trace-ID sein kann.
    const body = 'event: error\ndata: {"message": "x", "nummer": "<b>1</b>"}\n\n';
    const fetchImpl = (() => Promise.resolve(new Response(body, { status: 200 }))) as typeof fetch;
    await expect(streamChat({ url: 'x', body: {}, onEvent: () => undefined, fetchImpl }))
      .rejects.toMatchObject({ name: 'StreamServerError', nummer: '' });
  });

  it('ein Fehlerrahmen geht einem Abbruch danach vor (Paket 9)', async () => {
    // Review Paket 7 (NIT): riss die Verbindung NACH dem Bescheid, warf der
    // Lesefehler ihn weg — das Widget fragte dann im Verlauf nach.
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          'event: connected\ndata: {"history": true, "after_id": 1}\n\n'
          + 'event: error\ndata: {"message": "internal error"}\n\n'));
      },
      pull(controller) {
        controller.error(new TypeError('network error'));
      },
    });
    const resp = { ok: true, status: 200, body: stream } as unknown as Response;
    await expect(streamChat({
      url: 'x', body: {}, onEvent: () => undefined, fetchImpl: fetchReturning(resp),
    })).rejects.toMatchObject({ name: 'StreamServerError', code: 'internal' });
  });

  it('ein empfangenes Ergebnis geht einem Abbruch danach vor (Review Paket 9)', async () => {
    // Ein Proxy, der nach dem letzten Rahmen die Verbindung zurücksetzt, warf das
    // Ergebnis weg — das Widget fragte dann im Verlauf nach oder schickte die Frage
    // ein zweites Mal.
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          'event: connected\ndata: {}\n\nevent: result\ndata: {"content": "ok"}\n\n'));
      },
      pull(controller) {
        controller.error(new TypeError('network error'));
      },
    });
    const resp = { ok: true, status: 200, body: stream } as unknown as Response;
    await expect(streamChat<{ content: string }>({
      url: 'x', body: {}, onEvent: () => undefined, fetchImpl: fetchReturning(resp),
    })).resolves.toEqual({ content: 'ok' });
  });

  it('liest auch CRLF-Zeilenenden, selbst über Chunk-Grenzen hinweg (Paket 10)', async () => {
    // Audit 2026-10-10, L-7: getrennt wurde nur an `\n\n` — ein Proxy, der auf
    // `\r\n` umschreibt, ließ den Strom bis zur Frist ohne ein einziges Ereignis.
    const events: string[] = [];
    const resp = sseResponse([
      'event: connected\r\ndata: {}\r\n\r',
      '\nevent: result\r\ndata: {"content": "ok"}\r\n\r\n',
    ]);
    const out = await streamChat<{ content: string }>({
      url: 'x', body: {}, onEvent: (e) => events.push(e.event), fetchImpl: fetchReturning(resp),
    });
    expect(out.content).toBe('ok');
    expect(events).toEqual(['connected']);
  });

  it('postChat gibt den HTTP-Status am Fehler mit', async () => {
    const fetchImpl = (() => Promise.resolve(new Response('{}', { status: 409 }))) as typeof fetch;
    await expect(postChat({ url: 'x', body: {}, fetchImpl }))
      .rejects.toMatchObject({ status: 409, message: 'Chat error: 409' });
  });
});


// ── Paket 18E: Spur in der Konsole — die Fehlerart, nie der Text ─────────────
const MARKE = 'KANARIE7Q';
const ausgabe = (spy: { mock: { calls: unknown[][] } }): string =>
  spy.mock.calls.flat().map(String).join(' ');

describe('Paket 18E: ein Fehler im eigenen Listener', () => {
  afterEach(() => vi.restoreAllMocks());

  it('bricht den Strom nicht ab und steht als console.error da, ohne Text', async () => {
    const fehler = vi.spyOn(console, 'error').mockImplementation(() => {});
    const resp = sseResponse([
      'event: phase\ndata: {"step":"assess"}\n\n',
      'event: result\ndata: {"content":"Hallo"}\n\n',
    ]);
    const result = await streamChat({
      url: 'x', body: {}, fetchImpl: fetchReturning(resp),
      onEvent: () => { throw new TypeError(MARKE); },
    });
    expect(result).toEqual({ content: 'Hallo' });
    expect(fehler).toHaveBeenCalledTimes(1);
    expect(ausgabe(fehler)).toContain('TypeError');
    expect(ausgabe(fehler)).not.toContain(MARKE);
  });

  it('meldet ihn einmal je Strom, nicht je Ereignis (Review 18E-2)', async () => {
    const fehler = vi.spyOn(console, 'error').mockImplementation(() => {});
    const delta = 'event: text_delta\ndata: {"text":"x"}\n\n';
    const resp = sseResponse([delta, delta, delta, 'event: result\ndata: {"content":"ok"}\n\n']);
    await streamChat({
      url: 'x', body: {}, fetchImpl: fetchReturning(resp),
      onEvent: () => { throw new TypeError(MARKE); },
    });
    expect(fehler).toHaveBeenCalledTimes(1);
  });
});

describe('Paket 18F: 429 mit Wartezeit', () => {
  it('der Strom trägt Status und Wartezeit aus Retry-After', async () => {
    const resp = {
      ok: false, status: 429, body: null,
      headers: { get: (k: string) => (k === 'Retry-After' ? '42' : null) },
    } as unknown as Response;
    let fehler: { status?: number; retryAfterMs?: number; name?: string } = {};
    try {
      await streamChat({ url: 'x', body: {}, onEvent: () => {}, fetchImpl: fetchReturning(resp) });
    } catch (e) {
      fehler = e as typeof fehler;
    }
    expect(fehler.name).toBe('StreamHttpError');
    expect(fehler.status).toBe(429);
    expect(fehler.retryAfterMs).toBe(42_000);
  });

  it('der POST ebenso', async () => {
    const resp = {
      ok: false, status: 429,
      headers: { get: (k: string) => (k === 'Retry-After' ? '7' : null) },
    } as unknown as Response;
    let fehler: { status?: number; retryAfterMs?: number } = {};
    try {
      await postChat({ url: 'x', body: {}, fetchImpl: fetchReturning(resp) });
    } catch (e) {
      fehler = e as typeof fehler;
    }
    expect(fehler.status).toBe(429);
    expect(fehler.retryAfterMs).toBe(7_000);
  });
});
