/**
 * Chat-Transport-Primitive für das Widget — Verbatim-Port des ALT
 * `ApiService.sendMessageStream` / `sendMessage` SSE-Kerns
 * (services/api.service.ts). Die REQUEST-Formung (environment: page_context/
 * device/locale/guide_mode …) + der konkrete `ChatResponse`-Typ bleiben bei
 * der Chat-Shell (8-4), wo das volle Message-Modell landet — `streamChat`
 * liefert das `result`-Payload generisch (`T`), der Aufrufer castet.
 *
 * Testbar: `fetchImpl` ist injizierbar (Default `globalThis.fetch`), so
 * fährt die SSE-/Watchdog-Logik ohne Live-Backend unter Vitest.
 */

/** Server-Sent-Event-Payload aus POST /api/chat/stream. `event` = SSE-Name
 *  (`connected`/`phase`/`text_delta`/`result`/`error`), `data` = geparstes
 *  JSON (oder `{ raw }` bei Nicht-JSON). Verbatim aus ALT. */
export interface ChatStreamEvent {
  event: string;
  data: any;
}

/** Stale-Abbruch: 100 s lang kein BENANNTES Server-Event (connected/phase/
 *  result/error). Der Aufrufer zeigt eine ehrliche Meldung statt still auf
 *  POST /chat zu fallen (was die Wartezeit verdoppeln würde). Klasse statt
 *  ALTs `Error`+`err.name=` — `.name`-Kontrakt identisch, zusätzlich
 *  `instanceof`-fähig. */
export class StreamStaleError extends Error {
  constructor(message = 'Stream stale: keine Server-Events seit 100 s') {
    super(message);
    this.name = 'StreamStaleError';
  }
}

/**
 * Parst EINEN SSE-Block (Zeilen zwischen zwei Leerzeilen) in `{event, data}`.
 * Kommentar-/Keepalive-Zeilen (`: …`) und Leerzeilen werden ignoriert;
 * mehrere `data:`-Zeilen mit `\n` gejoint; Nicht-JSON → `{ raw: <text> }`;
 * ohne `event:` → `'message'`. Verbatim aus ALT `dispatchBlock`.
 */
export function parseSseBlock(rawBlock: string): ChatStreamEvent {
  let evtName = 'message';
  const dataLines: string[] = [];
  for (const ln of rawBlock.split('\n')) {
    if (!ln || ln.startsWith(':')) continue; // Keepalive-/Kommentar-Zeilen
    if (ln.startsWith('event:')) {
      evtName = ln.slice(6).trim();
    } else if (ln.startsWith('data:')) {
      dataLines.push(ln.slice(5).trim());
    }
  }
  const dataStr = dataLines.join('\n');
  let parsed: any = {};
  if (dataStr) {
    try {
      parsed = JSON.parse(dataStr);
    } catch {
      parsed = { raw: dataStr };
    }
  }
  return { event: evtName, data: parsed };
}

export interface StreamChatOptions {
  /** Voll-URL des Stream-Endpoints (Shell baut sie aus baseUrl + `/chat/stream`). */
  url: string;
  /** JSON-Body (session_id/message/environment …) — von der Shell geformt. */
  body: unknown;
  /** Bekommt JEDES Nicht-result/-error-Event (connected/phase/text_delta). */
  onEvent: (evt: ChatStreamEvent) => void;
  /** Injizierbar für Tests; Default `globalThis.fetch`. */
  fetchImpl?: typeof fetch;
  /** Idle-Byte-Watchdog (B9), Default 90 s. */
  idleMs?: number;
  /** Stale-Named-Event-Watchdog (B10), Default 100 s. */
  staleMs?: number;
}

/**
 * SSE-Streaming-Variante von POST /api/chat/stream. Ruft `onEvent` für jedes
 * `connected`/`phase`/`text_delta`-Event; löst mit dem `result`-Payload (`T`)
 * auf; wirft bei `error`-Event, Stream-Abbruch oder fehlendem `result`.
 *
 * Watchdogs (Verbatim-Kontrakt aus ALT):
 *   - B9 Idle 90 s: jede Byte-Lieferung resettet; ohne Bytes → AbortError →
 *     der Aufrufer fällt auf seinen Fehlerpfad (bzw. POST /chat).
 *   - B10 Stale 100 s: nur BENANNTE Events resetten; sonst → StreamStaleError
 *     (der Aufrufer fällt NICHT auf POST /chat, um die Wartezeit nicht zu
 *     verdoppeln). 100 s = Backend-LLM_READ_TIMEOUT 75 s + SDK-Retry-Puffer.
 */
export async function streamChat<T = unknown>(opts: StreamChatOptions): Promise<T> {
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch;
  const idleMs = opts.idleMs ?? 90_000;
  const staleMs = opts.staleMs ?? 100_000;

  const abort = new AbortController();
  let watchdog: ReturnType<typeof setTimeout> | null = null;
  let staleTimer: ReturnType<typeof setTimeout> | null = null;
  let staleFired = false;
  const armWatchdog = () => {
    if (watchdog) clearTimeout(watchdog);
    watchdog = setTimeout(() => abort.abort(), idleMs);
  };
  const armStale = () => {
    if (staleTimer) clearTimeout(staleTimer);
    staleTimer = setTimeout(() => {
      staleFired = true;
      abort.abort();
    }, staleMs);
  };
  const clearTimers = () => {
    if (watchdog) clearTimeout(watchdog);
    if (staleTimer) clearTimeout(staleTimer);
  };
  armWatchdog();
  armStale();

  let resp: Response;
  try {
    resp = await fetchImpl(opts.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(opts.body),
      signal: abort.signal,
    });
  } catch (e) {
    clearTimers();
    throw staleFired ? new StreamStaleError() : e;
  }
  if (!resp.ok || !resp.body) {
    clearTimers();
    throw new Error(`Chat stream error: ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult: T | null = null;
  let streamError: Error | null = null;

  const dispatch = (rawBlock: string) => {
    const evt = parseSseBlock(rawBlock);
    if (evt.event === 'result') {
      finalResult = evt.data as T;
    } else if (evt.event === 'error') {
      streamError = new Error(evt.data?.message || 'stream error');
    } else {
      try {
        opts.onEvent(evt);
      } catch {
        /* never break the stream on a listener throw */
      }
    }
    // B10: nur benannte Events zählen als Server-Fortschritt.
    if (evt.event !== 'message') armStale();
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      armWatchdog(); // B9: jede Daten-Lieferung resettet den Idle-Timer
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (block.trim()) dispatch(block);
      }
    }
  } catch (e) {
    throw staleFired ? new StreamStaleError() : e;
  } finally {
    clearTimers();
  }
  // Trailing-Block (Server schloss ohne finales \n\n).
  if (buffer.trim()) dispatch(buffer);

  if (streamError) throw streamError;
  // Verbatim wie ALT: `!finalResult` (nicht `=== null`) — ein result-Event mit
  // falsy Payload gilt ebenfalls als „kein Ergebnis". Real immer ein Objekt.
  if (!finalResult) throw new Error('Stream ended without a result event');
  return finalResult;
}

export interface PostChatOptions {
  /** Voll-URL des non-stream Endpoints (Shell baut sie aus baseUrl + `/chat`). */
  url: string;
  body: unknown;
  fetchImpl?: typeof fetch;
}

/**
 * Non-streaming Fallback POST /api/chat — die Shell nutzt ihn, wenn der Stream
 * mit einem NICHT-stale Fehler abbricht. Verbatim-Port des ALT
 * `ApiService.sendMessage`-Transports (ohne die environment-Formung).
 */
export async function postChat<T = unknown>(opts: PostChatOptions): Promise<T> {
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch;
  const resp = await fetchImpl(opts.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts.body),
  });
  if (!resp.ok) throw new Error(`Chat error: ${resp.status}`);
  return resp.json() as Promise<T>;
}
