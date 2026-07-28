import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ChatApiClient, _extractPageContextFromUrl, detectDevice,
} from './chat-api';

/**
 * Charakterisierung des ChatApiClient (8-4S-d0) — Port des ALT-`ApiService`-
 * Request-/Transport-Layers (api.service.ts:296-470,650-686), den der
 * Stream-Client (8-3) bewusst der Shell überließ. Gepinnt: die reine
 * page_context-URL-Extraktion (5 Pfad-Muster + Query-Precedence), die
 * Device-Schwellen, baseUrl-Normalisierung + `window.BOERDI_API_URL`-Override,
 * die environment-Formung (Override-vor-Ambient) und das Body-/URL-Mapping von
 * `stream`/`post` (inkl. action/action_params-Gates), verifiziert über ein
 * injiziertes `fetchImpl`.
 */

/** Response-artige mit SSE-ReadableStream (Muster stream-client.spec). */
function sseResponse(chunks: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const enc = new TextEncoder();
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
  return { ok: true, status: 200, body: stream } as unknown as Response;
}

function jsonResponse(payload: unknown): Response {
  return { ok: true, status: 200, json: async () => payload } as unknown as Response;
}

/** fetchImpl, das die Requests aufzeichnet und eine feste Response liefert. */
function capturingFetch(resp: Response): { fetchImpl: typeof fetch; calls: Array<{ url: string; body: any }> } {
  const calls: Array<{ url: string; body: any }> = [];
  const fetchImpl = (async (url: unknown, init?: { body?: unknown }) => {
    calls.push({ url: String(url), body: init?.body ? JSON.parse(String(init.body)) : undefined });
    return resp;
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

/** Wie capturingFetch, aber ohne Body-JSON-Parse (für FormData-Requests). */
function capturingFetchRaw(
  resp: Response,
): { fetchImpl: typeof fetch; calls: Array<{ url: string; method?: string; body: any; signal?: AbortSignal }> } {
  const calls: Array<{ url: string; method?: string; body: any; signal?: AbortSignal }> = [];
  const fetchImpl = (async (url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method, body: init?.body, signal: init?.signal ?? undefined });
    return resp;
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

function blobResponse(blob: Blob): Response {
  return { ok: true, status: 200, blob: async () => blob } as unknown as Response;
}

describe('_extractPageContextFromUrl', () => {
  const ctx = (u: string) => _extractPageContextFromUrl(new URL(u));

  it('Basis: immer widget:true', () => {
    expect(ctx('https://host/')).toEqual({ widget: true });
  });

  it('Query-Params q/node/collection', () => {
    expect(ctx('https://host/?q=mathe')).toMatchObject({ search_query: 'mathe' });
    expect(ctx('https://host/?node=n1')).toMatchObject({ node_id: 'n1' });
    expect(ctx('https://host/?collection=c1')).toMatchObject({ collection_id: 'c1' });
  });

  it('Pfad-Muster render/sammlung/material', () => {
    expect(ctx('https://host/edu-sharing/components/render/abc12345-de')).toMatchObject({ node_id: 'abc12345-de' });
    expect(ctx('https://host/sammlung/S1')).toMatchObject({ collection_id: 'S1' });
    expect(ctx('https://host/material/M1')).toMatchObject({ node_id: 'M1' });
  });

  it('Themenseite/Fachportal setzen page_type + Slugs', () => {
    expect(ctx('https://host/themenseite/klima')).toMatchObject({ topic_page_slug: 'klima', page_type: 'themenseite' });
    expect(ctx('https://host/fachportal/mathe/algebra')).toMatchObject({
      subject_slug: 'mathe', topic_page_slug: 'algebra', page_type: 'fachportal',
    });
  });

  it('Query-Precedence: ?node schlägt /material-Pfad (`!ctx.node_id`-Guard)', () => {
    expect(ctx('https://host/material/M1?node=N1')).toMatchObject({ node_id: 'N1' });
  });
});

describe('detectDevice', () => {
  const setWidth = (w: number) => Object.defineProperty(window, 'innerWidth', { value: w, configurable: true });
  afterEach(() => setWidth(1024));

  it('Viewport-Schwellen mobile/tablet/desktop', () => {
    setWidth(500);
    expect(detectDevice()).toBe('mobile');
    setWidth(800);
    expect(detectDevice()).toBe('tablet');
    setWidth(1300);
    expect(detectDevice()).toBe('desktop');
  });
});

describe('ChatApiClient', () => {
  afterEach(() => {
    delete (window as any).BOERDI_API_URL;
    vi.restoreAllMocks();
  });

  it('post: URL /api/chat + Body (session_id/message/environment) + action/action_params-Gates', async () => {
    const { fetchImpl, calls } = capturingFetch(jsonResponse({ content: 'ok', session_id: 's' }));
    const client = new ChatApiClient({ fetchImpl });

    await client.post('sess', 'Frage', undefined, 'browse_collection', { collection_id: 'c' });
    expect(calls[0].url).toBe('/api/chat');
    expect(calls[0].body).toMatchObject({
      session_id: 'sess', message: 'Frage', action: 'browse_collection', action_params: { collection_id: 'c' },
    });
    expect(calls[0].body.environment.page_context).toMatchObject({ widget: true });
    expect(typeof calls[0].body.environment.session_duration).toBe('number');

    // Ohne action/actionParams → Keys fehlen.
    await client.post('sess', 'Zwei');
    expect(calls[1].body.action).toBeUndefined();
    expect(calls[1].body.action_params).toBeUndefined();
  });

  it('post: env-Overrides schlagen die Ambient-Werte (|| bzw. ??)', async () => {
    const { fetchImpl, calls } = capturingFetch(jsonResponse({ content: 'ok', session_id: 's' }));
    const client = new ChatApiClient({ fetchImpl });

    await client.post('s', 'm', {
      page: '/x', page_context: { custom: 1 }, device: 'mobile', locale: 'fr-FR',
      referrer: 'ref', guide_mode: false, host: 'h.de', tour_action: 'start', page_event: 'context_open',
    });
    expect(calls[0].body.environment).toMatchObject({
      page: '/x', page_context: { custom: 1 }, device: 'mobile', locale: 'fr-FR',
      referrer: 'ref', guide_mode: false, host: 'h.de', tour_action: 'start', page_event: 'context_open',
    });
  });

  it('setGuideEnv landet in environment.guide_mode/host (host lowercased/trimmed)', async () => {
    const { fetchImpl, calls } = capturingFetch(jsonResponse({ content: 'ok', session_id: 's' }));
    const client = new ChatApiClient({ fetchImpl });
    client.setGuideEnv(true, '  WirLernenOnline.DE  ');

    await client.post('s', 'm');
    expect(calls[0].body.environment.guide_mode).toBe(true);
    expect(calls[0].body.environment.host).toBe('wirlernenonline.de');
  });

  it('setBaseUrl: trailing slash weg + /api angehängt (idempotent)', async () => {
    const { fetchImpl, calls } = capturingFetch(jsonResponse({ content: 'ok', session_id: 's' }));
    const client = new ChatApiClient({ fetchImpl });

    client.setBaseUrl('https://api.example/');
    await client.post('s', 'm');
    expect(calls[0].url).toBe('https://api.example/api/chat');

    client.setBaseUrl('https://api.example/api'); // bereits /api → unverändert
    await client.post('s', 'm');
    expect(calls[1].url).toBe('https://api.example/api/chat');
  });

  it('Konstruktor übernimmt window.BOERDI_API_URL als Basis', async () => {
    (window as any).BOERDI_API_URL = 'https://runtime.host';
    const { fetchImpl, calls } = capturingFetch(jsonResponse({ content: 'ok', session_id: 's' }));
    const client = new ChatApiClient({ fetchImpl });

    await client.post('s', 'm');
    expect(calls[0].url).toBe('https://runtime.host/api/chat');
  });

  it('stream: URL /api/chat/stream, onEvent für phase, löst mit ChatResponse', async () => {
    const resp = sseResponse([
      'event: phase\ndata: {"step":"route"}\n\n',
      'event: result\ndata: {"content":"Hallo","session_id":"s1"}\n\n',
    ]);
    const { fetchImpl, calls } = capturingFetch(resp);
    const client = new ChatApiClient({ fetchImpl });
    const events: string[] = [];

    const out = await client.stream('sess', 'Frage', (e) => events.push(e.event), undefined, 'act');
    expect(calls[0].url).toBe('/api/chat/stream');
    expect(calls[0].body).toMatchObject({ session_id: 'sess', message: 'Frage', action: 'act' });
    expect(events).toEqual(['phase']);
    expect(out).toMatchObject({ content: 'Hallo', session_id: 's1' });
  });
});

describe('ChatApiClient speech transport (8-4S-d-β)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('getSpeechEnabled: /speech/status, enabled!==false → true, explizit false → false', async () => {
    const t = capturingFetchRaw(jsonResponse({ enabled: true }));
    expect(await new ChatApiClient({ fetchImpl: t.fetchImpl }).getSpeechEnabled()).toBe(true);
    expect(t.calls[0].url).toBe('/api/speech/status');

    const f = capturingFetchRaw(jsonResponse({ enabled: false }));
    expect(await new ChatApiClient({ fetchImpl: f.fetchImpl }).getSpeechEnabled()).toBe(false);

    const missing = capturingFetchRaw(jsonResponse({})); // Feld fehlt → optimistisch true
    expect(await new ChatApiClient({ fetchImpl: missing.fetchImpl }).getSpeechEnabled()).toBe(true);
  });

  it('getSpeechEnabled: nicht-ok ODER fetch-Fehler → optimistisch true', async () => {
    const notOk = capturingFetchRaw({ ok: false, status: 503 } as unknown as Response);
    expect(await new ChatApiClient({ fetchImpl: notOk.fetchImpl }).getSpeechEnabled()).toBe(true);

    const throwing = (async () => { throw new Error('offline'); }) as unknown as typeof fetch;
    expect(await new ChatApiClient({ fetchImpl: throwing }).getSpeechEnabled()).toBe(true);
  });

  it('transcribe: POST FormData(audio+language=de) an /speech/transcribe → data.text', async () => {
    const { fetchImpl, calls } = capturingFetchRaw(jsonResponse({ text: 'hallo welt' }));
    const client = new ChatApiClient({ fetchImpl });
    const blob = new Blob(['x'], { type: 'audio/webm' });

    const text = await client.transcribe(blob);
    expect(text).toBe('hallo welt');
    expect(calls[0].url).toBe('/api/speech/transcribe');
    expect(calls[0].method).toBe('POST');
    expect(calls[0].body).toBeInstanceOf(FormData);
    expect((calls[0].body as FormData).get('language')).toBe('de');
    expect((calls[0].body as FormData).get('audio')).toBeInstanceOf(Blob);
  });

  it('transcribe: nicht-ok → wirft "Transcription failed"', async () => {
    const { fetchImpl } = capturingFetchRaw({ ok: false, status: 500 } as unknown as Response);
    await expect(new ChatApiClient({ fetchImpl }).transcribe(new Blob(['x'])))
      .rejects.toThrow('Transcription failed');
  });

  it('synthesize: POST FormData(text+voice=nova) an /speech/synthesize, reicht signal durch → Blob', async () => {
    const out = new Blob(['audio'], { type: 'audio/mpeg' });
    const { fetchImpl, calls } = capturingFetchRaw(blobResponse(out));
    const client = new ChatApiClient({ fetchImpl });
    const ac = new AbortController();

    const blob = await client.synthesize('Guten Tag', ac.signal);
    expect(blob).toBe(out);
    expect(calls[0].url).toBe('/api/speech/synthesize');
    expect(calls[0].method).toBe('POST');
    expect((calls[0].body as FormData).get('text')).toBe('Guten Tag');
    expect((calls[0].body as FormData).get('voice')).toBe('nova');
    expect(calls[0].signal).toBe(ac.signal);
  });

  it('synthesize: nicht-ok → wirft "Synthesis failed"', async () => {
    const { fetchImpl } = capturingFetchRaw({ ok: false, status: 500 } as unknown as Response);
    await expect(new ChatApiClient({ fetchImpl }).synthesize('x'))
      .rejects.toThrow('Synthesis failed');
  });
});

describe('ChatApiClient history transport (8-4S-e-0)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('loadHistory: GET /sessions/<sid>/messages?limit=, hebt debug._web_links/_query_metas auf Top-Level', async () => {
    const payload = [
      { role: 'user', content: 'Frage' },
      {
        role: 'assistant', content: 'Antwort', cards: [{ id: 'c1' }],
        debug: { _web_links: [{ title: 'T', url: 'https://x' }], _query_metas: [{ search_url: 'u', search_term: 't' }] },
      },
    ];
    const { fetchImpl, calls } = capturingFetchRaw(jsonResponse(payload));
    const out = await new ChatApiClient({ fetchImpl }).loadHistory('sess id', 20);

    expect(calls[0].url).toBe('/api/sessions/sess%20id/messages?limit=20');
    expect(out).toHaveLength(2);
    expect(out[1]).toMatchObject({
      role: 'assistant', content: 'Antwort', cards: [{ id: 'c1' }],
      webLinks: [{ title: 'T', url: 'https://x' }],
      queryMetas: [{ search_url: 'u', search_term: 't' }],
    });
  });

  it('loadHistory: _type_focus überstimmt stale _web_links → webLinks:[]', async () => {
    const payload = [{ role: 'assistant', content: 'A', debug: { _type_focus: true, _web_links: [{ title: 'X', url: 'u' }] } }];
    const { fetchImpl } = capturingFetchRaw(jsonResponse(payload));
    const out = await new ChatApiClient({ fetchImpl }).loadHistory('s');
    expect(out[0].webLinks).toEqual([]);
  });

  it('loadHistory: nicht-ok ODER Nicht-Array ODER Fehler → []', async () => {
    const notOk = capturingFetchRaw({ ok: false, status: 404 } as unknown as Response);
    expect(await new ChatApiClient({ fetchImpl: notOk.fetchImpl }).loadHistory('s')).toEqual([]);

    const nonArray = capturingFetchRaw(jsonResponse({ oops: true }));
    expect(await new ChatApiClient({ fetchImpl: nonArray.fetchImpl }).loadHistory('s')).toEqual([]);

    const throwing = (async () => { throw new Error('offline'); }) as unknown as typeof fetch;
    expect(await new ChatApiClient({ fetchImpl: throwing }).loadHistory('s')).toEqual([]);
  });

  it('loadHistory: Default-Limit 20; eigenes Limit wird durchgereicht', async () => {
    const { fetchImpl, calls } = capturingFetchRaw(jsonResponse([]));
    const client = new ChatApiClient({ fetchImpl });
    await client.loadHistory('s');
    await client.loadHistory('s', 5);
    expect(calls[0].url).toBe('/api/sessions/s/messages?limit=20');
    expect(calls[1].url).toBe('/api/sessions/s/messages?limit=5');
  });
});
