import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { ChatStreamEvent } from '../stream/stream-client';
import { SendMessageContext, runSendMessage } from './send-message';

/**
 * Charakterisierung des sendMessage-Orchestrators (8-4S-c) — Port des
 * ALT-`sendMessage`-Turn-LIFECYCLE (chat.component.ts:448-569). RE-ARCHITEKTUR:
 * die Erfolgs-Seiteneffekte (Tour/latestDebug/query-meta/page-action/Guides/
 * autoSpeak) sind zu EINEM `onResult(resp, msg)`-Hook zusammengefasst, den die
 * Shell in 8-4S-d/e/g verdrahtet (ALT-Sequenz + Gates dort). Hier gepinnt: die
 * Bubble-Lifecycle (User → Loading → Ergebnis/Fehler), Guards, Stale-Sonderweg
 * (KEIN Fallback), non-stale-Fallback auf POST, onEvent→Phase-Label, isLoading/
 * Fokus-Abschluss.
 */

const STALE_TEXT =
  'Das dauert gerade ungewöhnlich lange — bitte stell deine Frage '
  + 'gleich noch einmal. Falls meine Antwort doch noch fertig '
  + 'geworden ist, findest du sie beim nächsten Öffnen im Verlauf.';
const ERROR_TEXT = 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.';

function makeResp(over: Partial<ChatResponse> = {}): ChatResponse {
  return {
    session_id: 's', content: 'Antwort', cards: [], follow_up: '', quick_replies: [],
    debug: { pattern: 'M06' } as ChatResponse['debug'], page_action: null, pagination: null, ...over,
  } as ChatResponse;
}

interface Bot { id: string; content: string; isLoading?: boolean; rest: unknown[]; }
interface Rec {
  ctx: SendMessageContext;
  users: string[]; bots: Bot[]; removed: string[]; scroll: string[];
  phases: Array<[string, string]>; results: Array<{ resp: ChatResponse; msg: string }>;
  loading: boolean[]; cleared: number; focus: number;
  streamCalls: Array<{ msg: string; env: unknown; action?: string; actionParams?: unknown }>;
  postCalls: Array<{ msg: string; env: unknown; action?: string; actionParams?: unknown }>;
}

interface Opts {
  input?: string;
  isLoading?: boolean;
  env?: unknown;
  stream?: (
    msg: string, onEvent: (evt: ChatStreamEvent) => void, env: unknown,
    action?: string, actionParams?: Record<string, unknown>,
  ) => Promise<ChatResponse>;
  post?: (msg: string, env: unknown, action?: string, actionParams?: Record<string, unknown>) => Promise<ChatResponse>;
  formatPhaseLabel?: (evt: ChatStreamEvent) => string | null;
}

function makeCtx(opts: Opts = {}): Rec {
  const rec: Rec = {
    ctx: null as unknown as SendMessageContext,
    users: [], bots: [], removed: [], scroll: [], phases: [], results: [],
    loading: [], cleared: 0, focus: 0, streamCalls: [], postCalls: [],
  };
  let currentLoading = opts.isLoading ?? false;
  let n = 0;
  rec.ctx = {
    currentInput: () => opts.input ?? '',
    clearInput: () => { rec.cleared++; },
    isLoading: () => currentLoading,
    setLoading: (v) => { currentLoading = v; rec.loading.push(v); },
    addUserMessage: (content) => { rec.users.push(content); },
    addBotMessage: (content, isLoading, ...rest) => {
      const id = 'b' + ++n;
      rec.bots.push({ id, content, isLoading, rest });
      return id;
    },
    removeMessage: (id) => { rec.removed.push(id); },
    updateLoadingPhase: (loadingId, label) => { rec.phases.push([loadingId, label]); },
    setScrollTarget: (id) => { rec.scroll.push(id); },
    focusInput: () => { rec.focus++; },
    pageContextEnv: () => opts.env,
    stream: (msg, onEvent, env, action, actionParams) => {
      rec.streamCalls.push({ msg, env, action, actionParams });
      return (opts.stream ?? (() => Promise.resolve(makeResp())))(msg, onEvent, env, action, actionParams);
    },
    post: (msg, env, action, actionParams) => {
      rec.postCalls.push({ msg, env, action, actionParams });
      return (opts.post ?? (() => Promise.resolve(makeResp({ content: 'via POST' }))))(msg, env, action, actionParams);
    },
    formatPhaseLabel: opts.formatPhaseLabel ?? (() => null),
    onResult: (resp, msg) => { rec.results.push({ resp, msg }); },
  };
  return rec;
}

describe('runSendMessage — Lifecycle', () => {
  afterEach(() => vi.restoreAllMocks());

  it('Guard: kein Text und leeres Input-Feld → nichts passiert', async () => {
    const r = makeCtx({ input: '   ' });
    await runSendMessage(undefined, undefined, undefined, r.ctx);
    expect(r.users).toEqual([]);
    expect(r.loading).toEqual([]);
    expect(r.streamCalls).toEqual([]);
  });

  it('Guard: isLoading true → Turn wird nicht gestartet', async () => {
    const r = makeCtx({ isLoading: true });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.users).toEqual([]);
    expect(r.streamCalls).toEqual([]);
  });

  it('Happy-Path: clearInput → User-Bubble → Loading-Bubble → Ergebnis-Bubble (11-Arg) → onResult → isLoading/Fokus', async () => {
    const resp = makeResp({ content: 'Da', cards: [{ id: 'k' }] as unknown as ChatResponse['cards'], quick_replies: ['q'] });
    const r = makeCtx({ input: '', stream: () => Promise.resolve(resp) });
    await runSendMessage('Hallo', 'act', { p: 1 }, r.ctx);

    expect(r.cleared).toBe(1);
    expect(r.users).toEqual(['Hallo']);
    // Erste Bot-Bubble = Loading, zweite = Ergebnis.
    expect(r.bots[0]).toMatchObject({ content: '', isLoading: true });
    expect(r.bots[1].content).toBe('Da');
    expect(r.bots[1].isLoading).toBe(false);
    // 11-Positionen-Seam: cards/quick_replies an rest[0]/rest[1].
    expect(r.bots[1].rest[0]).toEqual([{ id: 'k' }]);
    expect(r.bots[1].rest[1]).toEqual(['q']);
    // Loading-Bubble wird entfernt, Scroll wandert Loading→Ergebnis.
    expect(r.removed).toEqual([r.bots[0].id]);
    expect(r.scroll).toEqual([r.bots[0].id, r.bots[1].id]);
    // stream mit Message/Action/Params gerufen, KEIN POST-Fallback.
    expect(r.streamCalls).toEqual([{ msg: 'Hallo', env: undefined, action: 'act', actionParams: { p: 1 } }]);
    expect(r.postCalls).toEqual([]);
    // onResult mit (resp, msg); isLoading true→false; Fokus am Ende.
    expect(r.results).toEqual([{ resp, msg: 'Hallo' }]);
    expect(r.loading).toEqual([true, false]);
    expect(r.focus).toBe(1);
  });

  it('Text-Fallback aufs Input-Feld inkl. trim (ALT `text || userInput.trim()`)', async () => {
    const r = makeCtx({ input: '  getippt  ' });
    await runSendMessage(undefined, undefined, undefined, r.ctx);
    expect(r.users).toEqual(['getippt']);
    expect(r.streamCalls[0].msg).toBe('getippt');
  });

  it('Stale: StreamStaleError → Stale-Bubble, KEIN POST-Fallback, kein onResult, isLoading/Fokus', async () => {
    const staleErr = Object.assign(new Error('stale'), { name: 'StreamStaleError' });
    const r = makeCtx({ input: '', stream: () => Promise.reject(staleErr) });
    await runSendMessage('Frage', undefined, undefined, r.ctx);

    expect(r.bots[1].content).toBe(STALE_TEXT);
    expect(r.removed).toEqual([r.bots[0].id]);
    expect(r.scroll).toEqual([r.bots[0].id, r.bots[1].id]);
    expect(r.postCalls).toEqual([]); // NIE Fallback bei Stale
    expect(r.results).toEqual([]);   // kein onResult
    expect(r.loading).toEqual([true, false]);
    expect(r.focus).toBe(1);
  });

  it('Non-stale Stream-Fehler → stiller Fallback auf POST, dann normales Ergebnis + onResult', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const postResp = makeResp({ content: 'via POST' });
    const r = makeCtx({
      input: '',
      stream: () => Promise.reject(new Error('network')),
      post: () => Promise.resolve(postResp),
    });
    await runSendMessage('Frage', 'a', { x: 1 }, r.ctx);

    expect(r.postCalls).toEqual([{ msg: 'Frage', env: undefined, action: 'a', actionParams: { x: 1 } }]);
    expect(r.bots[1].content).toBe('via POST');
    expect(r.results).toEqual([{ resp: postResp, msg: 'Frage' }]);
    expect(warn).toHaveBeenCalledOnce();
  });

  it('Fehler-Pfad: Stream non-stale + POST wirft → Fehler-Bubble, kein onResult, isLoading/Fokus', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: () => Promise.reject(new Error('network')),
      post: () => Promise.reject(new Error('post down')),
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);

    expect(r.bots[1].content).toBe(ERROR_TEXT);
    // Loading-Bubble im try + Fehler-Bubble im catch → beide entfernt? Nein:
    // Loading-Bubble wird im catch entfernt, Fehler-Bubble angehängt.
    expect(r.removed).toEqual([r.bots[0].id]);
    expect(r.scroll).toEqual([r.bots[0].id, r.bots[1].id]);
    expect(r.results).toEqual([]);
    expect(r.loading).toEqual([true, false]);
    expect(r.focus).toBe(1);
    expect(warn).toHaveBeenCalledOnce();
  });

  it('onEvent: phase-Event → updateLoadingPhase(loadingId, label); text_delta + null-Label ignoriert', async () => {
    const r = makeCtx({
      input: '',
      formatPhaseLabel: (evt) => (evt.event === 'phase' ? (evt.data?.label ?? null) : null),
      stream: (_msg, onEvent) => {
        onEvent({ event: 'text_delta', data: { t: 'x' } }); // ignoriert (früher return)
        onEvent({ event: 'phase', data: { label: 'sucht…' } }); // → updateLoadingPhase
        onEvent({ event: 'connected', data: {} }); // formatPhaseLabel → null → ignoriert
        return Promise.resolve(makeResp());
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    const loadingId = r.bots[0].id;
    expect(r.phases).toEqual([[loadingId, 'sucht…']]);
  });
});
