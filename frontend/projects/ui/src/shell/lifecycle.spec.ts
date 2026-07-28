// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ContextGreetingController } from '../controllers/context-greeting.controller';
import { TourController } from '../controllers/tour.controller';
import { LifecycleContext, ShellLifecycle } from './lifecycle';

/**
 * Shell-Lifecycle (8-4S-e4): die Orchestrierung aus ALT `ngOnInit`/`showGreeting`/
 * `restart`/`resetSession`/`updateContext`/`onSpaContextChange` (+ Resume-/Tour-
 * Tick-/Kontext-Ping-Sequenzierung) hinter einem `LifecycleContext`. Die Bausteine
 * (session-boot/scroll-follow/history-restore/Controller) sind einzeln gepinnt;
 * hier zählt die Verdrahtung: Boot-Verzweigung (Resume vs. Begrüßung), Input-
 * Overrides, Storage-Seiteneffekte, Ping-/Tick-Gates.
 */

const VALID_SID = 'bb-12345678-1234-4123-8123-123456789abc';
const KEY = 'boerdi_session_id';

interface Rec {
  speech: boolean[]; parsedPC: Record<string, any>[]; sessionIds: string[];
  viaBsid: boolean[]; messages: unknown[]; latestDebug: unknown[]; bots: unknown[][]; scroll: number;
}

function makeCtx(overrides: Partial<LifecycleContext> = {}): {
  ctx: LifecycleContext; rec: Rec; tour: any; cg: any; api: any;
} {
  const rec: Rec = { speech: [], parsedPC: [], sessionIds: [], viaBsid: [], messages: [], latestDebug: [], bots: [], scroll: 0 };
  let pc: Record<string, any> = {};
  let sid = '';
  const tour = { isTourFlagSet: vi.fn(() => false), sendTourTick: vi.fn(async () => {}) };
  const cg = { resetForNewPage: vi.fn(), sendContextPing: vi.fn(async () => {}) };
  const api = { setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => true), loadHistory: vi.fn(async () => []) };
  const ctx: LifecycleContext = {
    api: () => api as never,
    apiUrl: () => '', pageContextInput: () => '', persistSession: () => false,
    sessionKey: () => KEY, sessionCookieDomain: () => '', sessionCookieMaxAge: () => 2592000,
    greeting: () => '', startReplies: () => [],
    sessionId: () => sid, setSessionId: (id) => { sid = id; rec.sessionIds.push(id); },
    resumedViaBsid: () => false, setResumedViaBsid: (v) => { rec.viaBsid.push(v); },
    parsedPageContext: () => pc, setParsedPageContext: (c) => { pc = c; rec.parsedPC.push(c); },
    setSpeechEnabled: (v) => { rec.speech.push(v); },
    setMessages: (m) => { rec.messages.push(m); },
    updateMessages: () => { /* Restore-QR-Strip separat gepinnt */ },
    addUserMessage: () => { /* nur im Restore relevant */ },
    addBotMessage: (...a: unknown[]) => { rec.bots.push(a); return 'id'; },
    setLatestDebug: (d) => { rec.latestDebug.push(d); },
    tour: tour as unknown as TourController,
    contextGreeting: cg as unknown as ContextGreetingController,
    scrollToLatest: () => { rec.scroll++; },
    ...overrides,
  };
  return { ctx, rec, tour, cg, api };
}

describe('ShellLifecycle (8-4S-e4)', () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState({}, '', '/');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('init: apiUrl→setBaseUrl, Speech-Probe, pageContext-Parse, frische Session, Nicht-Resume → Begrüßung', async () => {
    const { ctx, rec, api } = makeCtx({
      apiUrl: () => 'https://api.example',
      pageContextInput: () => '{"page_kind":"home"}',
    });
    new ShellLifecycle(ctx).init();
    await Promise.resolve(); await Promise.resolve();
    expect(api.setBaseUrl).toHaveBeenCalledWith('https://api.example');
    expect(rec.parsedPC[0]).toEqual({ page_kind: 'home' });
    expect(rec.sessionIds[0]).toMatch(/^bb-/);
    expect(api.loadHistory).not.toHaveBeenCalled();
    expect(rec.bots.length).toBe(1);
    expect(rec.speech).toEqual([true]);
  });

  it('init: kaputter pageContext-String → { raw }', () => {
    const { ctx, rec } = makeCtx({ pageContextInput: () => '{kaputt' });
    new ShellLifecycle(ctx).init();
    expect(rec.parsedPC[0]).toEqual({ raw: '{kaputt' });
  });

  it('init: persist + gespeicherte Session → Resume-Pfad (loadHistory statt direkter Begrüßung)', async () => {
    localStorage.setItem(KEY, VALID_SID);
    const { ctx, api } = makeCtx({ persistSession: () => true });
    new ShellLifecycle(ctx).init();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(api.loadHistory).toHaveBeenCalledWith(VALID_SID, 20);
  });

  it('init: laufende Tour (Flag) → Tour-Tick beim Boot', () => {
    vi.useFakeTimers();
    const { ctx, tour } = makeCtx();
    tour.isTourFlagSet.mockReturnValue(true);
    new ShellLifecycle(ctx).init();
    vi.runAllTimers();
    expect(tour.sendTourTick).toHaveBeenCalled();
  });

  it('showGreeting: greeting/startReplies-Inputs überschreiben die Defaults', () => {
    const { ctx, rec } = makeCtx({ greeting: () => 'Moin', startReplies: () => ['A'] });
    new ShellLifecycle(ctx).showGreeting();
    expect(rec.bots[0]).toEqual(['Moin', false, undefined, ['A']]);
  });

  it('showGreeting: leere Inputs → Default-Text (Boerdi) + 4 Default-Replies', () => {
    const { ctx, rec } = makeCtx();
    new ShellLifecycle(ctx).showGreeting();
    expect(String(rec.bots[0][0])).toContain('Boerdi');
    expect((rec.bots[0][3] as string[]).length).toBe(4);
  });

  it('restart: neue Session persistiert, Messages/Debug geleert, Begrüßung', () => {
    const { ctx, rec } = makeCtx();
    new ShellLifecycle(ctx).restart();
    expect(rec.sessionIds[0]).toMatch(/^bb-/);
    expect(localStorage.getItem(KEY)).toBe(rec.sessionIds[0]);
    expect(rec.messages[0]).toEqual([]);
    expect(rec.latestDebug[0]).toBeNull();
    expect(rec.bots.length).toBe(1);
  });

  it('resetSession: localStorage geräumt + neu geschrieben, Reset-Begrüßung', () => {
    localStorage.setItem(KEY, 'old-value');
    const { ctx, rec } = makeCtx();
    new ShellLifecycle(ctx).resetSession();
    expect(rec.sessionIds[0]).toMatch(/^bb-/);
    expect(localStorage.getItem(KEY)).toBe(rec.sessionIds[0]);
    expect(rec.messages[0]).toEqual([]);
    expect(rec.bots[0][0]).toBe('Hallo! Wie kann ich dir helfen?');
  });

  it('updateContext: merged in den bestehenden Seitenkontext', () => {
    const { ctx, rec } = makeCtx();
    const lc = new ShellLifecycle(ctx);
    lc.updateContext({ a: 1 });
    lc.updateContext({ b: 2 });
    expect(rec.parsedPC[rec.parsedPC.length - 1]).toEqual({ a: 1, b: 2 });
  });

  it('onSpaContextChange: ersetzt Kontext, resetForNewPage, adressierbar → Kontext-Ping', () => {
    vi.useFakeTimers();
    const { ctx, cg, rec } = makeCtx();
    new ShellLifecycle(ctx).onSpaContextChange({ collection_id: 'c1' });
    expect(rec.parsedPC[0]).toEqual({ collection_id: 'c1' });
    expect(cg.resetForNewPage).toHaveBeenCalled();
    vi.runAllTimers();
    expect(cg.sendContextPing).toHaveBeenCalled();
  });

  it('onSpaContextChange: nicht adressierbar → kein Ping', () => {
    vi.useFakeTimers();
    const { ctx, cg } = makeCtx();
    new ShellLifecycle(ctx).onSpaContextChange({ page_kind: 'home' });
    vi.runAllTimers();
    expect(cg.sendContextPing).not.toHaveBeenCalled();
  });
});
