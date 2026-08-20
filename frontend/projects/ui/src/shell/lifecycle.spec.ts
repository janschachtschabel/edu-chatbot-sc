// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ContextGreetingController } from '../controllers/context-greeting.controller';
import { TourController } from '../controllers/tour.controller';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { LifecycleContext, ShellLifecycle, shouldSendContextPing } from './lifecycle';

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
    greeting: () => '', startReplies: () => [], showWelcome: () => true,
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
    t: createTranslator(DE, DE),
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

  // ── `show-welcome="false"` — der leere Chat (Nutzer-Entscheid 2026-08-14) ──
  // Eine Einbettung, die den Chat selbst anmoderiert (Browser-Plugin,
  // edu-sharing-Seite), will keine zweite Begrüßung obendrauf. Der Schalter
  // betrifft NUR diese statische Startnachricht — die Kontext-Begrüßung des
  // Backends hat ihren eigenen Weg und bleibt unberührt.

  it('showWelcome=false: showGreeting schweigt — kein leerer Platzhalter', () => {
    const { ctx, rec } = makeCtx({ showWelcome: () => false, greeting: () => 'Moin' });
    new ShellLifecycle(ctx).showGreeting();
    expect(rec.bots.length).toBe(0);
  });

  it('showWelcome=false: auch restart und resetSession bleiben stumm', () => {
    // Sonst wäre der Chat nur beim ERSTEN Laden leer und ab dem ersten
    // Neustart wieder begrüßt — ein Zustand, den niemand erklären kann.
    const { ctx, rec } = makeCtx({ showWelcome: () => false });
    const lc = new ShellLifecycle(ctx);
    lc.restart();
    lc.resetSession();
    expect(rec.bots.length).toBe(0);
    expect(rec.messages).toEqual([[], []]);   // geleert wird trotzdem
  });

  it('showWelcome=false hält den Erstaufruf leer, ohne den Kontext-Ping zu unterdrücken', async () => {
    const { ctx, rec, cg } = makeCtx({
      showWelcome: () => false,
      pageContextInput: () => ({ page_kind: 'collection', collection_id: 'abc' }),
    });
    cg.sendContextPing.mockResolvedValue(false);   // Ping antwortet leer
    new ShellLifecycle(ctx).init();
    await Promise.resolve(); await Promise.resolve();
    expect(cg.sendContextPing).toHaveBeenCalledWith('context_open_initial');
    expect(rec.bots.length).toBe(0);
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

  it('die Rückfall-Begrüßungen und die vier Einstiegs-Chips kommen aus dem Übersetzer (C1-b4)', () => {
    const en = createTranslator({
      'greeting.default': 'Hi, glad you are here!',
      'greeting.reset': 'Hello! How can I help?',
      'greeting.reply.aiAge': 'How do I bring my content into the AI age?',
      'greeting.reply.search': 'I am looking for content on a topic.',
      'greeting.reply.tour': 'Guide me through the website.',
      'greeting.reply.about': 'What is WissenLebtOnline?',
    }, DE);
    const { ctx, rec } = makeCtx({ t: en });
    const lc = new ShellLifecycle(ctx);

    lc.showGreeting();
    expect(rec.bots[0][0]).toBe('Hi, glad you are here!');
    expect(rec.bots[0][3]).toEqual([
      'How do I bring my content into the AI age?',
      'I am looking for content on a topic.',
      'Guide me through the website.',
      'What is WissenLebtOnline?',
    ]);

    lc.resetSession();
    expect(rec.bots[1][0]).toBe('Hello! How can I help?');
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
    // `subject` (Fachportal) wird erkannt, bleibt aber bewusst stumm — der
    // eindeutige Fall für „nicht adressierbar".
    new ShellLifecycle(ctx).onSpaContextChange({ page_kind: 'subject' });
    vi.runAllTimers();
    expect(cg.sendContextPing).not.toHaveBeenCalled();
  });
});

// ── Aufgabe 8: welche Seiten überhaupt einen Ping wert sind ─────────────────
// Wichtig und nicht offensichtlich: `home`/`external` setzt der Erkenner NIE —
// die entscheidet das Backend am Hostnamen. Eine Widget-Liste, die einfach die
// begrüßbaren Backend-Arten spiegelte, pingte auf einer fremden Seite also nie
// und liesse das Backend gar nicht erst zu Wort kommen. Die Bedingung hier
// lautet deshalb „könnte begrüßbar sein", nicht „ist begrüßbar".

describe('shouldSendContextPing', () => {
  it('Sammlung, Inhalt, Themenseite — wie bisher', () => {
    expect(shouldSendContextPing({ page_kind: 'collection' })).toBe(true);
    expect(shouldSendContextPing({ page_kind: 'content' })).toBe(true);
    expect(shouldSendContextPing({ page_kind: 'topic' })).toBe(true);
    expect(shouldSendContextPing({ collection_id: 'c1' })).toBe(true);
    expect(shouldSendContextPing({ node_id: 'n1' })).toBe(true);
  });

  it('Suche nur mit Begriff — ohne bleibt das Backend ohnehin stumm', () => {
    expect(shouldSendContextPing({ page_kind: 'search', search_query: 'Optik' })).toBe(true);
    expect(shouldSendContextPing({ page_kind: 'search' })).toBe(false);
  });

  it('nicht eingeordnete Seite mit Hostnamen — hier entscheidet das Backend', () => {
    expect(shouldSendContextPing({ page_kind: 'other', page_host: 'beispiel.org' })).toBe(true);
    expect(shouldSendContextPing({ page_host: 'wirlernenonline.de' })).toBe(true);
  });

  it('ohne Hostnamen kann das Backend nichts entscheiden → kein Ping', () => {
    expect(shouldSendContextPing({ page_kind: 'other' })).toBe(false);
    expect(shouldSendContextPing({})).toBe(false);
  });

  it('Fachportal bleibt bewusst draussen', () => {
    expect(shouldSendContextPing({ page_kind: 'subject', page_host: 'wirlernenonline.de' })).toBe(false);
  });
});

// ── Aufgabe 9: genau EINE Nachricht beim ersten Laden ───────────────────────
// Ansatz C aus dem Plan: die Begrüßung wird zurückgestellt, bis der Ping
// antwortet. Hat er Inhalt, IST er die Begrüßung; sonst kommt die normale.
// Verworfen wurden (A) die Begrüßung bei erkannter Seite zu unterdrücken —
// fällt der Ping aus, gäbe es GAR KEINE — und (B) sie zu zeigen und danach zu
// ersetzen: sichtbares Flackern und kurz eine falsche Zeile im Verlauf.

describe('ShellLifecycle: Begrüßung beim ersten Laden', () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState({}, '', '/');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  async function boot(overrides: Partial<LifecycleContext> = {}) {
    const made = makeCtx(overrides);
    new ShellLifecycle(made.ctx).init();
    for (let i = 0; i < 5; i++) await Promise.resolve();
    return made;
  }

  it('erkannte Seite + Ping mit Inhalt ⇒ genau eine Nachricht, und zwar die Kontextmeldung', async () => {
    const { ctx, rec, cg } = makeCtx({ pageContextInput: () => '{"page_kind":"collection"}' });
    // `true` heisst: der Regler hat die Kontextmeldung selbst gerendert.
    cg.sendContextPing.mockResolvedValue(true);
    new ShellLifecycle(ctx).init();
    for (let i = 0; i < 5; i++) await Promise.resolve();
    expect(cg.sendContextPing).toHaveBeenCalledWith('context_open_initial');
    expect(rec.bots.length).toBe(0);  // KEINE zusätzliche Standard-Begrüßung
  });

  it('Ping ohne Inhalt ⇒ die normale Begrüßung', async () => {
    const { rec } = await boot({ pageContextInput: () => '{"page_kind":"collection"}' });
    expect(rec.bots.length).toBe(1);
  });

  it('Ping-Fehler ⇒ die normale Begrüßung (nie gar keine)', async () => {
    const { ctx, rec } = makeCtx({ pageContextInput: () => '{"page_kind":"collection"}' });
    (ctx.contextGreeting as any).sendContextPing = vi.fn(async () => { throw new Error('offline'); });
    new ShellLifecycle(ctx).init();
    for (let i = 0; i < 5; i++) await Promise.resolve();
    expect(rec.bots.length).toBe(1);
  });

  it('nicht erkannte Seite ⇒ die normale Begrüßung, ohne Ping', async () => {
    const { rec, cg } = await boot();
    expect(cg.sendContextPing).not.toHaveBeenCalled();
    expect(rec.bots.length).toBe(1);
  });

  it('laufende Tour ⇒ normale Begrüßung, kein Kontext-Ping (kollidierte über isLoading)', async () => {
    const made = makeCtx({ pageContextInput: () => '{"page_kind":"collection"}' });
    made.tour.isTourFlagSet.mockReturnValue(true);
    new ShellLifecycle(made.ctx).init();
    for (let i = 0; i < 5; i++) await Promise.resolve();
    expect(made.cg.sendContextPing).not.toHaveBeenCalled();
    expect(made.rec.bots.length).toBe(1);
  });
});

// ── X1 (2026-08-20, wp-test live): die Tour besitzt ihren ganzen Load ───────
// Der Abschluss-Tick löscht das Tour-Flag; wurde der Besitz erst NACH dem Tick
// geprüft, feuerte der Kontext-Ping im selben Load — und direkt hinter „Fast
// geschafft" stand „diese Seite gehört nicht zu WLO".
describe('ShellLifecycle — Tour besitzt den Load (X1)', () => {
  afterEach(() => { vi.useRealTimers(); localStorage.clear(); });

  it('Resume: der Abschluss-Tick löscht das Flag — trotzdem kein Kontext-Ping in diesem Load', async () => {
    vi.useFakeTimers();
    localStorage.setItem(KEY, VALID_SID);
    const made = makeCtx({
      persistSession: () => true,
      parsedPageContext: () => ({ page_host: 'wp-test.wirlernenonline.de' }),
    });
    let flag = true;
    made.tour.isTourFlagSet.mockImplementation(() => flag);
    made.tour.sendTourTick.mockImplementation(async () => { flag = false; });
    new ShellLifecycle(made.ctx).init();
    await vi.runAllTimersAsync();
    expect(made.tour.sendTourTick).toHaveBeenCalled();
    expect(made.cg.sendContextPing).not.toHaveBeenCalled();
  });

  it('onSpaContextChange: laufende Tour → Kontext ersetzt, aber kein Ping', () => {
    vi.useFakeTimers();
    const { ctx, cg, rec, tour } = makeCtx();
    tour.isTourFlagSet.mockReturnValue(true);
    new ShellLifecycle(ctx).onSpaContextChange({ collection_id: 'c1' });
    expect(rec.parsedPC[0]).toEqual({ collection_id: 'c1' });
    vi.runAllTimers();
    expect(cg.sendContextPing).not.toHaveBeenCalled();
  });
});
