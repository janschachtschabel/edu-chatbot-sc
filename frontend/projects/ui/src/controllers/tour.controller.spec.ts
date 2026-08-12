import { beforeEach, describe, expect, it } from 'vitest';

import { ChatResponse, DebugInfo } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { TourContext, TourController, TOUR_START_LABEL } from './tour.controller';

/**
 * Charakterisierung des TourControllers — Verbatim-Port aus ALT (dort nur
 * integrativ über chat.component.spec gedeckt). Gepinnt: Start-/Tick-Sequenz
 * (User-Bubble, sendMessage-Env, Flag-Pflege, Render nur bei Inhalt),
 * Loading-Guard, Fehlerpfad, applyTourState, tourEnv, localStorage-Flag.
 */
interface Calls {
  user: string[];
  bot: Array<{ id: string; content: string; loading?: boolean; rest: unknown[] }>;
  removed: string[];
  scroll: string[];
  debug: unknown[];
  loading: boolean[];
}

function makeCtx(over: Partial<TourContext> = {}): { ctx: TourContext; calls: Calls } {
  const calls: Calls = { user: [], bot: [], removed: [], scroll: [], debug: [], loading: [] };
  let loading = false;
  let n = 0;
  const ctx: TourContext = {
    sendMessage: over.sendMessage ?? (async () => makeResp()),
    pageContext: over.pageContext ?? (() => ({})),
    isLoading: over.isLoading ?? (() => loading),
    setLoading: (v) => {
      loading = v;
      calls.loading.push(v);
    },
    addUserMessage: (c) => calls.user.push(c),
    addBotMessage: (c, isLoading, ...rest) => {
      const id = 'b' + ++n;
      calls.bot.push({ id, content: c, loading: isLoading, rest });
      return id;
    },
    removeMessage: (id) => calls.removed.push(id),
    setScrollTarget: (id) => calls.scroll.push(id),
    setLatestDebug: (d) => calls.debug.push(d),
    t: over.t ?? createTranslator(DE, DE),
  };
  return { ctx, calls };
}

function makeResp(fields: Partial<ChatResponse> = {}): ChatResponse {
  return {
    session_id: 's', content: 'Hallo', cards: [], follow_up: '', quick_replies: [],
    debug: { pattern: 'TOUR:1' } as DebugInfo, page_action: null, pagination: null,
    tour: { active: true, step: 's1', group: 'g' }, ...fields,
  } as ChatResponse;
}

describe('TourController', () => {
  beforeEach(() => localStorage.clear());

  it('startTour: User-Bubble + sendMessage(start) + Flag + Render + Loading-Toggle', async () => {
    let sentEnv: any = null;
    const { ctx, calls } = makeCtx({
      sendMessage: async (_m, env) => {
        sentEnv = env;
        return makeResp({ content: 'Willkommen' });
      },
    });
    await new TourController(ctx).startTour();

    expect(calls.user).toEqual([TOUR_START_LABEL]);
    expect(sentEnv).toEqual({ tour_action: 'start' });
    expect(localStorage.getItem('boerdi_tour_active')).toBe('1');
    // Loading-Bubble entfernt, echte Antwort gerendert
    expect(calls.removed.length).toBe(1);
    expect(calls.bot.some((b) => b.content === 'Willkommen')).toBe(true);
    expect(calls.debug.length).toBe(1);
    expect(calls.loading).toEqual([true, false]);
  });

  it('startTour: bei isLoading → No-Op (kein sendMessage, keine User-Bubble)', async () => {
    let sent = false;
    const { ctx, calls } = makeCtx({ isLoading: () => true, sendMessage: async () => ((sent = true), makeResp()) });
    await new TourController(ctx).startTour();
    expect(sent).toBe(false);
    expect(calls.user).toEqual([]);
  });

  it('startTour: sendMessage wirft → Loading-Bubble weg + Fehler-Bubble + Loading false', async () => {
    const { ctx, calls } = makeCtx({ sendMessage: async () => { throw new Error('x'); } });
    await new TourController(ctx).startTour();
    expect(calls.removed.length).toBe(1);
    expect(calls.bot.some((b) => b.content.includes('konnte gerade nicht gestartet werden'))).toBe(true);
    expect(calls.loading).toEqual([true, false]);
  });

  it('die Fehler-Bubble kommt aus dem Übersetzer (C1-b4)', async () => {
    const en = createTranslator({ 'error.tourStart': 'Sorry, the tour could not be started.' }, DE);
    const { ctx, calls } = makeCtx({
      t: en, sendMessage: async () => { throw new Error('x'); },
    });
    await new TourController(ctx).startTour();
    expect(calls.bot.some((b) => b.content === 'Sorry, the tour could not be started.')).toBe(true);
    // Der gesendete Text bleibt deutsch: er ist die Anweisung ans Backend/Modell,
    // kein Oberflächentext (C1-Entscheid „Sprachdirektive im Prompt").
    expect(calls.user).toEqual([TOUR_START_LABEL]);
  });

  it('sendTourTick: sendMessage(tick) + Render bei Inhalt; zweiter Aufruf No-Op (Guard)', async () => {
    let calls2 = 0;
    let sentEnv: any = null;
    const { ctx, calls } = makeCtx({
      sendMessage: async (_m, env) => {
        calls2++;
        sentEnv = env;
        return makeResp({ content: 'Schritt 2' });
      },
    });
    const tc = new TourController(ctx);
    await tc.sendTourTick();
    await tc.sendTourTick(); // Guard: _tourTicked
    expect(calls2).toBe(1);
    expect(sentEnv).toEqual({ tour_action: 'tick' });
    expect(calls.bot.some((b) => b.content === 'Schritt 2')).toBe(true);
  });

  it('sendTourTick: leere Antwort (kein content, keine QR) → NICHT gerendert', async () => {
    const { ctx, calls } = makeCtx({ sendMessage: async () => makeResp({ content: '   ', quick_replies: [] }) });
    await new TourController(ctx).sendTourTick();
    expect(calls.removed.length).toBe(1); // Loading-Bubble weg
    // Nur die Loading-Bubble wurde je hinzugefügt, keine echte Antwort
    expect(calls.bot.every((b) => b.loading === true)).toBe(true);
  });

  it('applyTourState: aktive Tour → Flag "1"; fehlende Tour → Flag gelöscht', () => {
    const { ctx } = makeCtx();
    const tc = new TourController(ctx);
    tc.applyTourState(makeResp({ tour: { active: true, step: 's', group: 'g' } }));
    expect(tc.isTourFlagSet()).toBe(true);
    tc.applyTourState(makeResp({ tour: null }));
    expect(tc.isTourFlagSet()).toBe(false);
  });

  it('tourEnv: page_context nur bei nicht-leerem Kontext', () => {
    const empty = new TourController(makeCtx({ pageContext: () => ({}) }).ctx);
    expect(empty.tourEnv('start')).toEqual({ tour_action: 'start' });
    const full = new TourController(makeCtx({ pageContext: () => ({ nodeId: 'n1' }) }).ctx);
    expect(full.tourEnv('tick')).toEqual({ tour_action: 'tick', page_context: { nodeId: 'n1' } });
  });
});
