import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatStreamEvent } from '../stream/stream-client';
import { SendMessageContext, VerlaufNachfrage, runSendMessage } from './send-message';

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
    debug: null, ui: { pattern: 'M06' }, page_action: null, pagination: null, ...over,
  } as ChatResponse;
}

interface Bot { id: string; content: string; isLoading?: boolean; rest: unknown[]; }
interface Rec {
  ctx: SendMessageContext;
  users: string[]; bots: Bot[]; removed: string[]; scroll: string[];
  phases: Array<[string, string]>; results: Array<{ resp: ChatResponse; msg: string }>;
  streamTexts: Array<[string, string, number]>; streamCleared: string[];
  loading: boolean[]; cleared: number; focus: number;
  streamCalls: Array<{ msg: string; env: unknown; action?: string; actionParams?: unknown }>;
  postCalls: Array<{ msg: string; env: unknown; action?: string; actionParams?: unknown }>;
  /** Paket 7 (P2): Fragen, deren Antwort aus dem Verlauf geholt wurde. */
  historyCalls: string[];
  historyOpts: VerlaufNachfrage[];
  /** Was zurück ins Eingabefeld gelegt wurde (Review C-6). */
  inputSet: string[];
  /** Die Person tippt, während der Zug läuft. */
  tippe: (text: string) => void;
  /** Neustart von aussen (resetSession/Neustart-Knopf): neue Sitzungs-ID. */
  setSession: (id: string) => void;
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
  t?: SendMessageContext['t'];
  answerFromHistory?: (msg: string, nachfrage: VerlaufNachfrage) => Promise<ChatResponse | null>;
}

function makeCtx(opts: Opts = {}): Rec {
  const rec: Rec = {
    ctx: null as unknown as SendMessageContext,
    users: [], bots: [], removed: [], scroll: [], phases: [], results: [],
    streamTexts: [], streamCleared: [],
    loading: [], cleared: 0, focus: 0, streamCalls: [], postCalls: [], historyCalls: [],
    historyOpts: [], inputSet: [],
    setSession: () => undefined, tippe: () => undefined,
  };
  let sitzung = 'bb-sitzung-1';
  rec.setSession = (id) => { sitzung = id; };
  let eingabe = opts.input ?? '';
  rec.tippe = (text) => { eingabe = text; };
  let currentLoading = opts.isLoading ?? false;
  let n = 0;
  rec.ctx = {
    currentInput: () => eingabe,
    clearInput: () => { rec.cleared++; eingabe = ''; },
    setInput: (text) => { rec.inputSet.push(text); eingabe = text; },
    sessionId: () => sitzung,
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
    appendStreamText: (loadingId, text, pos) => { rec.streamTexts.push([loadingId, text, pos]); },
    clearStreamText: (loadingId) => { rec.streamCleared.push(loadingId); },
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
    t: opts.t ?? createTranslator(DE, DE),
    answerFromHistory: (msg, nachfrage) => {
      rec.historyCalls.push(msg);
      rec.historyOpts.push(nachfrage);
      return (opts.answerFromHistory ?? (() => Promise.resolve(null)))(msg, nachfrage);
    },
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
    // Paket 18C/D: `ui` statt `debug` an rest[2].
    expect(r.bots[1].rest[2]).toEqual({ pattern: 'M06' });
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

  it('Stale- und Fehler-Bubble kommen aus dem Übersetzer (C1-b4)', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const en = createTranslator(
      { 'error.stale': 'This is taking unusually long.', 'error.generic': 'Sorry, something went wrong.' },
      DE,
    );

    const stale = makeCtx({
      input: '', t: en,
      stream: () => Promise.reject(Object.assign(new Error('stale'), { name: 'StreamStaleError' })),
    });
    await runSendMessage('Frage', undefined, undefined, stale.ctx);
    expect(stale.bots[1].content).toBe('This is taking unusually long.');

    const kaputt = makeCtx({
      input: '', t: en,
      stream: () => Promise.reject(new Error('network')),
      post: () => Promise.reject(new Error('post down')),
    });
    await runSendMessage('Frage', undefined, undefined, kaputt.ctx);
    expect(kaputt.bots[1].content).toBe('Sorry, something went wrong.');
    expect(warn).toHaveBeenCalled();
  });

  it('onEvent: phase-Event → updateLoadingPhase(loadingId, label); null-Label ignoriert', async () => {
    const r = makeCtx({
      input: '',
      formatPhaseLabel: (evt) => (evt.event === 'phase' ? (evt.data?.label ?? null) : null),
      stream: (_msg, onEvent) => {
        onEvent({ event: 'phase', data: { label: 'sucht…' } }); // → updateLoadingPhase
        onEvent({ event: 'connected', data: {} }); // formatPhaseLabel → null → ignoriert
        return Promise.resolve(makeResp());
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    const loadingId = r.bots[0].id;
    expect(r.phases).toEqual([[loadingId, 'sucht…']]);
  });

  // Token-Streaming (Plan 2026-10-01, T15): `text_delta` füllt die Ladeblase;
  // die fertige Antwort ersetzt sie wie bisher.
  it('onEvent: text_delta → appendStreamText(loadingId, text, pos); kaputte Nutzlast ignoriert', async () => {
    const r = makeCtx({
      input: '',
      stream: (_msg, onEvent) => {
        onEvent({ event: 'text_delta', data: { text: 'Hal', pos: 0 } });
        onEvent({ event: 'text_delta', data: { text: 'lo', pos: 3 } });
        onEvent({ event: 'text_delta', data: { t: 'x' } });              // ALT-fremde Form
        onEvent({ event: 'text_delta', data: { text: 'y', pos: '4' } }); // pos keine Zahl
        return Promise.resolve(makeResp({ content: 'Hallo' }));
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    const loadingId = r.bots[0].id;
    expect(r.streamTexts).toEqual([[loadingId, 'Hal', 0], [loadingId, 'lo', 3]]);
    expect(r.phases).toEqual([]);
    expect(r.removed).toEqual([loadingId]);   // die Ladeblase samt Teiltext geht
    expect(r.bots[1].content).toBe('Hallo');  // die fertige Antwort kommt neu
  });

  it('Rückfall auf POST leert den vorläufigen Text, bevor der zweite Weg läuft', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: (_msg, onEvent) => {
        onEvent({ event: 'text_delta', data: { text: 'Hal', pos: 0 } });
        return Promise.reject(new Error('network'));
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.streamCleared).toEqual([r.bots[0].id]);
    expect(r.bots[1].content).toBe('via POST');
    expect(warn).toHaveBeenCalledOnce();
  });
});

describe('Abgelehnte Anfrage: kein zweiter Versuch (Nutzer-Meldung 2026-08-19)', () => {
  /**
   * Gemeldet aus der Einbettung: eine ueberlange ``host_instruction`` ergab am
   * ``/stream``-Endpunkt einen 422 — und der Rueckfall schickte denselben
   * Rumpf sofort an ``/chat``, wo er identisch abgelehnt wurde. Zwei
   * Konsolenfehler, zwei abgelehnte Anfragen, keine Antwort.
   *
   * Der Rueckfall ist fuer „Transport kaputt" und „altes Backend ohne
   * /stream" gedacht. Ein 4xx ist beides nicht: der Server hat verstanden und
   * abgelehnt. Derselbe Rumpf wird auf dem anderen Weg genauso abgelehnt.
   */
  const httpFehler = (status: number) =>
    Object.assign(new Error(`Chat stream error: ${status}`),
                  { name: 'StreamHttpError', status });

  it('422 → KEIN Fallback, eine Fehlerblase, kein zweiter Aufruf', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({ input: '', stream: () => Promise.reject(httpFehler(422)) });
    await runSendMessage('Frage', undefined, undefined, r.ctx);

    expect(r.postCalls).toEqual([]);
    expect(r.bots[1].content).toBe(ERROR_TEXT);
    expect(r.results).toEqual([]);
    expect(r.loading).toEqual([true, false]);
    expect(warn).toHaveBeenCalledOnce();   // EINE Meldung, nicht zwei
  });

  it('429 → ebenfalls kein Fallback (das Limit gilt auf beiden Wegen)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({ input: '', stream: () => Promise.reject(httpFehler(429)) });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.postCalls).toEqual([]);
  });

  it('404 → Fallback BLEIBT: das ist der Fall „altes Backend ohne /stream"', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const postResp = makeResp({ content: 'via POST' });
    const r = makeCtx({
      input: '',
      stream: () => Promise.reject(httpFehler(404)),
      post: () => Promise.resolve(postResp),
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.postCalls).toHaveLength(1);
    expect(r.bots[1].content).toBe('via POST');
  });

  it('500 → Fallback BLEIBT: ein Aussetzer ist auf dem anderen Weg vielleicht weg', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const postResp = makeResp({ content: 'via POST' });
    const r = makeCtx({
      input: '',
      stream: () => Promise.reject(httpFehler(500)),
      post: () => Promise.resolve(postResp),
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.postCalls).toHaveLength(1);
  });
});

// Befundliste §1.4: resetSession() oder der Neustart-Knopf mitten im Zug. Der
// Zug gehört der Sitzung, in der er begann — sein Ausgang darf den frischen
// Verlauf nicht anfassen: keine Blase, kein onResult, kein Laden/Fokus (das
// Freigeben gehört dem Neustart, `lifecycle.ts`), und KEIN POST-Rückfall, der
// die alte Frage unter der neuen Sitzungs-ID noch einmal stellte.
describe('runSendMessage — Neustart mitten im Zug', () => {
  afterEach(() => vi.restoreAllMocks());

  it('die Antwort eines Zugs aus der alten Sitzung wird verworfen', async () => {
    const r: Rec = makeCtx({
      input: '',
      stream: () => { r.setSession('bb-sitzung-2'); return Promise.resolve(makeResp()); },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);

    expect(r.bots.map((b) => b.content)).toEqual(['']);   // nur die Ladeblase vom Start
    expect(r.removed).toEqual([]);
    expect(r.results).toEqual([]);
    expect(r.loading).toEqual([true]);
    expect(r.focus).toBe(0);
  });

  it('scheitert der Stream nach dem Neustart, stellt kein POST die alte Frage neu', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r: Rec = makeCtx({
      input: '',
      stream: () => { r.setSession('bb-sitzung-2'); return Promise.reject(new Error('network')); },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);

    expect(r.postCalls).toEqual([]);
    expect(r.bots.map((b) => b.content)).toEqual(['']);   // auch keine Fehlerblase
    expect(r.loading).toEqual([true]);
    expect(warn).not.toHaveBeenCalled();
  });

  it('auch die Antwort des POST-Rückfalls wird nach einem Neustart verworfen', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r: Rec = makeCtx({
      input: '',
      stream: () => Promise.reject(new Error('network')),
      post: () => { r.setSession('bb-sitzung-2'); return Promise.resolve(makeResp({ content: 'via POST' })); },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);

    expect(r.bots.map((b) => b.content)).toEqual(['']);
    expect(r.results).toEqual([]);
    expect(r.loading).toEqual([true]);
  });
});

// ── Paket 7: Sitzung beschäftigt (P1) und Antwort aus dem Verlauf (P2) ────────
describe('runSendMessage — beschäftigt und Antwort aus dem Verlauf (Paket 7)', () => {
  const BUSY_TEXT = DE['error.busy'];
  const beschaeftigt = () =>
    Object.assign(new Error('session busy'), { name: 'StreamServerError', code: 'session_busy' });
  /** Der Handschlag eines Servers, der die Antwort im Verlauf ablegt. */
  const angenommen = { event: 'connected', data: { history: true, after_id: 3 } } as ChatStreamEvent;

  it('„beschäftigt“ im Strom → eigene Blase, kein POST, kein onResult', async () => {
    const r = makeCtx({ input: '', stream: () => Promise.reject(beschaeftigt()) });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.postCalls).toEqual([]);
    expect(r.bots.at(-1)?.content).toBe(BUSY_TEXT);
    expect(r.results).toEqual([]);
    expect(r.loading.at(-1)).toBe(false);
  });

  it('409 auf dem POST-Rückfall → dieselbe Blase statt der Fehlerblase', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: () => Promise.reject(new Error('network')),
      post: () => Promise.reject(Object.assign(new Error('Chat error: 409'), { status: 409 })),
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.bots.at(-1)?.content).toBe(BUSY_TEXT);
    warn.mockRestore();
  });

  it('Abbruch NACH der Annahme → kein zweiter Versand, die Antwort kommt aus dem Verlauf', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const ausVerlauf = makeResp({ content: 'aus dem Verlauf' });
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => {
        onEvent(angenommen);
        return Promise.reject(new Error('network'));
      },
      answerFromHistory: () => Promise.resolve(ausVerlauf),
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.postCalls).toEqual([]);
    expect(r.historyCalls).toEqual(['Frage']);
    // Review C-4: nur was NACH der letzten bekannten Nachricht gespeichert wurde.
    expect(r.historyOpts[0].nachId).toBe(3);
    expect(r.bots.at(-1)?.content).toBe('aus dem Verlauf');
    expect(r.results).toEqual([{ resp: ausVerlauf, msg: 'Frage' }]);
    warn.mockRestore();
  });

  it('kommt auch aus dem Verlauf nichts, sagt das Widget es ehrlich', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => {
        onEvent(angenommen);
        return Promise.reject(new Error('network'));
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.postCalls).toEqual([]);
    expect(r.bots.at(-1)?.content).toBe(STALE_TEXT);
    expect(r.results).toEqual([]);
    warn.mockRestore();
  });
});

// ── Review Paket 7 (C-1, C-3, C-6, A-7): die Nachfrage im Verlauf ────────────
describe('runSendMessage — Nachfrage im Verlauf (Review Paket 7)', () => {
  const angenommen = { event: 'connected', data: { history: true, after_id: 3 } } as ChatStreamEvent;
  const netz = () => Promise.reject(new Error('network'));
  const busy = () =>
    Object.assign(new Error('session busy'), { name: 'StreamServerError', code: 'session_busy' });

  it('C-1: ein Serverfehler nach der Annahme → sofort die Fehlerblase, keine Nachfrage', async () => {
    // Der gescheiterte Zug hat nichts gespeichert; 90 s Nachfrage endeten in
    // der falschen Blase „dauert ungewöhnlich lange“.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const serverfehler = Object.assign(new Error('internal error'),
      { name: 'StreamServerError', code: 'internal' });
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => { onEvent(angenommen); return Promise.reject(serverfehler); },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.historyCalls).toEqual([]);
    expect(r.postCalls).toEqual([]);
    expect(r.bots.at(-1)?.content).toBe(ERROR_TEXT);
    expect(r.loading.at(-1)).toBe(false);
    warn.mockRestore();
  });

  it('C-6: eine Aktion (Karten-Knopf) wandert bei „beschäftigt“ nicht ins Eingabefeld', async () => {
    // Ihr Text allein liefe als gewöhnliche Nachricht, ohne die Aktion.
    const r = makeCtx({ input: '', stream: () => Promise.reject(busy()) });
    await runSendMessage('Inhalte anzeigen', 'browse_collection', { id: 'c1' }, r.ctx);
    expect(r.inputSet).toEqual([]);
  });

  it('A-7: speichert der Server keinen Verlauf, bleibt der POST-Rückfall', async () => {
    // `privacy-config.logging.messages: false` — im Verlauf käme nie etwas an.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => {
        onEvent({ event: 'connected', data: { history: false, after_id: null } } as ChatStreamEvent);
        return netz();
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.historyCalls).toEqual([]);
    expect(r.postCalls).toHaveLength(1);
    expect(r.bots.at(-1)?.content).toBe('via POST');
    warn.mockRestore();
  });

  it('A-7: ein Handschlag ohne Angabe (älteres Backend) heißt ebenfalls POST', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => { onEvent({ event: 'connected', data: {} } as ChatStreamEvent); return netz(); },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(r.historyCalls).toEqual([]);
    expect(r.postCalls).toHaveLength(1);
    warn.mockRestore();
  });

  it('C-3: die Nachfrage endet mit der Sitzung, in der der Zug begann', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const gesehen: boolean[] = [];
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => { onEvent(angenommen); return netz(); },
      answerFromHistory: (_msg, nachfrage) => {
        gesehen.push(nachfrage.abgebrochen());
        r.setSession('bb-sitzung-2');            // Neustart während der Nachfrage
        gesehen.push(nachfrage.abgebrochen());
        return Promise.resolve(makeResp({ content: 'zu spät' }));
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    expect(gesehen).toEqual([false, true]);
    expect(r.bots.map((b) => b.content)).not.toContain('zu spät');
    warn.mockRestore();
  });

  it('C-6: vor der Nachfrage weicht der Teiltext einem Hinweis in der Ladeblase', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: '',
      stream: (_m, onEvent) => {
        onEvent(angenommen);
        onEvent({ event: 'text_delta', data: { text: 'Die Lin', pos: 0 } } as ChatStreamEvent);
        return netz();
      },
    });
    await runSendMessage('Frage', undefined, undefined, r.ctx);
    const ladeId = r.bots[0].id;
    expect(r.streamCleared).toEqual([ladeId]);
    expect(r.phases).toEqual([[ladeId, DE['phase.fromHistory']]]);
    warn.mockRestore();
  });

  it('C-6: „beschäftigt“ legt die getippte Frage zurück ins Eingabefeld', async () => {
    // Getippt = aus dem Eingabefeld gesendet (Enter/Knopf ruft ohne Text).
    const r = makeCtx({ input: 'Frage', stream: () => Promise.reject(busy()) });
    await runSendMessage(undefined, undefined, undefined, r.ctx);
    expect(r.inputSet).toEqual(['Frage']);
  });

  it('C-6: … aber nicht über das, was die Person inzwischen getippt hat', async () => {
    const r = makeCtx({
      input: 'Frage',
      stream: () => { r.tippe('Neue Frage'); return Promise.reject(busy()); },
    });
    await runSendMessage(undefined, undefined, undefined, r.ctx);
    expect(r.inputSet).toEqual([]);
  });

  it('„veraltet“ legt die getippte Frage zurück ins Eingabefeld (Paket 9)', async () => {
    // Review Paket 7 (NIT): die Blase bittet „stell deine Frage gleich noch
    // einmal“ — wie bei „beschäftigt“ steht sie dann schon im Feld.
    const stale = () => Object.assign(new Error('stale'), { name: 'StreamStaleError' });
    const r = makeCtx({ input: 'Frage', stream: () => Promise.reject(stale()) });
    await runSendMessage(undefined, undefined, undefined, r.ctx);
    expect(r.inputSet).toEqual(['Frage']);
    expect(r.bots.at(-1)?.content).toBe(DE['error.stale']);
  });

  it('„veraltet“ nach vergeblicher Nachfrage legt die Frage ebenfalls zurück (Paket 9)', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const r = makeCtx({
      input: 'Frage',
      stream: (_m, onEvent) => {
        onEvent({ event: 'connected', data: { history: true, after_id: 3 } } as ChatStreamEvent);
        return Promise.reject(new Error('network'));
      },
      answerFromHistory: () => Promise.resolve(null),
    });
    await runSendMessage(undefined, undefined, undefined, r.ctx);
    expect(r.inputSet).toEqual(['Frage']);
    expect(r.bots.at(-1)?.content).toBe(DE['error.stale']);
    warn.mockRestore();
  });

  it('Chip und Gastseiten-Auftrag wandern bei „beschäftigt“ nicht ins Eingabefeld (Paket 9)', async () => {
    // Review Paket 7 (MINOR 25): beide kommen als fertiger Text, nicht aus dem
    // Feld — ein Auftrag der Gastseite stünde sonst ungekürzt als Eingabe da,
    // ein Chip als Satz, den die Person nie getippt hat.
    for (const text of ['Zeig mir Mathe', 'Auftrag der Gastseite '.repeat(400)]) {
      const r = makeCtx({ input: '', stream: () => Promise.reject(busy()) });
      await runSendMessage(text, undefined, undefined, r.ctx);
      expect(r.inputSet).toEqual([]);
      expect(r.bots.at(-1)?.content).toBe(DE['error.busy']);
    }
  });
});
