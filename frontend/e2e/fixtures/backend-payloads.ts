/**
 * Canned backend payloads for the E2E smokes — the *only* thing these tests
 * stub out. Everything above the network boundary (element definition, shadow
 * DOM, page-context detection, SSE parsing, rendering, focus) is the real
 * built bundle.
 *
 * Shapes are taken from the types the widget actually consumes, so a backend
 * contract change surfaces here rather than as a mystery E2E failure:
 *   - guide-mode:  `parseGuideModeConfig` (ui/widget/guide-mode-config.ts)
 *   - chat result: `ChatResponse` (ui/grouping/message-types.ts)
 *   - SSE frames:  `parseSseBlock` (ui/stream/stream-client.ts)
 */

/** `GET /api/config/guide-mode` — Studio-maintained welcome + trusted hosts. */
export function guideModeConfig(overrides: Record<string, unknown> = {}) {
  return {
    trusted_domains: ['host.test'],
    header_nav: [{ id: 'nav1', label: 'Fachportale', url: 'https://host.test/fachportale', new_tab: false }],
    welcome: {
      greeting: 'Moin! Ich bin BOERDi.',
      quick_replies: ['Was kannst du?', 'Zeig mir die Seite'],
      tour_reply: 'Zeig mir die Seite',
    },
    ...overrides,
  };
}

/** A single WLO card (only the fields the tile renders are filled in). */
export function card(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    node_id: 'n-1',
    title: 'Bruchrechnen üben',
    description: 'Interaktive Übungen zum Bruchrechnen.',
    disciplines: ['Mathematik'],
    educational_contexts: ['Sekundarstufe I'],
    keywords: [],
    learning_resource_types: [],
    url: 'https://host.test/material/n-1',
    wlo_url: 'https://host.test/material/n-1',
    preview_url: '',
    license: 'CC_BY',
    publisher: 'WLO',
    node_type: 'ccm:io',
    topic_pages: [],
    link: 'https://host.test/material/n-1',
    ...overrides,
  };
}

/**
 * Ein vollständig gefülltes `debug`-Feld — alle Zweige des Debug-Panels an.
 *
 * Nötig für den Kontrast-Durchgang (U4d): die beiden Bedeutungsfarben des
 * Panels (`.debug-warn`, `.debug-ok`) hängen an `state_transition.plausible`
 * und `llm_engine_match`, die Balkenfarben an einer Parallel-Gruppe im Trace.
 * Ohne diese Felder rendert das Panel sie nie — und ein Kontrast-Gate misst
 * genau das nicht, was nicht im Bild steht.
 */
export function debugInfo(overrides: Record<string, unknown> = {}) {
  return {
    persona: 'schueler',
    intent: 'suche',
    state: 'exploring',
    turn_type: 'normal',
    signals: ['lp_intent'],
    pattern: 'M06',
    entities: { thema: 'Bruchrechnen' },
    tools_called: ['search_wlo_all'],
    phase1_eliminated: [],
    phase2_scores: {},
    phase3_modulations: {},
    // Die beiden Flaggen absichtlich GEGENLÄUFIG: `plausible: true` rendert
    // `.debug-ok`, `llm_engine_match: false` rendert `.debug-warn`. So stehen
    // beide Bedeutungsfarben gleichzeitig im Bild.
    state_transition: { prev: 'greeting', next: 'exploring', plausible: true, expected_next_likely: ['deepening'] },
    pattern_id_hint: 'M07',
    llm_engine_match: false,
    context: { page: 'start', device: 'desktop', turn_count: 2 },
    trace: [
      { step: 'classify', label: 'Klassifikation', duration_ms: 900 },
      {
        step: 'retrieve',
        label: 'Suche',
        duration_ms: 1200,
        data: {
          parallel: true,
          tasks: [
            { name: 'wlo', label: 'WLO-Suche', started_at_ms: 0, duration_ms: 900 },
            { name: 'rag', label: 'RAG', started_at_ms: 100, duration_ms: 400 },
          ],
        },
      },
    ],
    ...overrides,
  };
}

/** A `result`-event payload. Defaults are a plain text answer. */
export function chatResponse(overrides: Record<string, unknown> = {}) {
  return {
    session_id: 'bb-11111111-2222-3333-4444-555555555555',
    content: 'Alles klar.',
    cards: [],
    follow_up: '',
    quick_replies: [],
    debug: { pattern: 'M01', intent: 'greeting' },
    page_action: null,
    pagination: null,
    ...overrides,
  };
}

function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/**
 * Full SSE body for one turn: the same frame sequence the backend emits
 * (connected → phase → text_delta* → result). Sent in one chunk — the parser
 * splits on blank lines, so chunk boundaries are irrelevant to it.
 */
export function sseBody(response: Record<string, unknown>): string {
  const content = String(response['content'] ?? '');
  const half = Math.ceil(content.length / 2);
  return [
    frame('connected', { session_id: response['session_id'] }),
    frame('phase', { step: 'wlo_search' }),
    frame('text_delta', { delta: content.slice(0, half) }),
    frame('text_delta', { delta: content.slice(half) }),
    frame('result', response),
  ].join('');
}
