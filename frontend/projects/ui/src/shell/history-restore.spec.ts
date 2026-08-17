import { describe, expect, it } from 'vitest';

import { ChatMessage } from '../grouping/message-types';
import { HistoryMessage } from '../stream/chat-api';
import { HistoryRestoreContext, restoreHistory } from './history-restore';

/**
 * History-Restore (8-4S-e3): der Resume-Render aus ALT `restoreHistory`
 * (chat.component.ts:347-399) als kontext-getriebene Funktion. Gepinnt: leere
 * History → nur Begrüßung; nicht-leer → Begrüßung prepend + deren Quick-Replies
 * strippen (nur der frische Chat-Anfang ist klickbar) + user/assistant rendern
 * (Cards/WebLinks/QueryMetas/Debug mitrestoren) + ans Ende scrollen; leere
 * Content-Zeilen überspringen.
 */

interface Recorder {
  greeting: number;
  update: number;
  users: string[];
  bots: unknown[][];
  scroll: number;
  loadArgs: { sid: string; limit: number } | null;
  strippedHead: ChatMessage | null;
}

function makeCtx(history: HistoryMessage[]): { ctx: HistoryRestoreContext; rec: Recorder } {
  const rec: Recorder = {
    greeting: 0, update: 0, users: [], bots: [], scroll: 0, loadArgs: null, strippedHead: null,
  };
  const ctx: HistoryRestoreContext = {
    loadHistory: async (sid, limit) => { rec.loadArgs = { sid, limit }; return history; },
    sessionId: () => 'bb-sess',
    showGreeting: () => { rec.greeting++; },
    updateMessages: (updater) => {
      rec.update++;
      const head: ChatMessage = { id: 'g', sender: 'bot', content: 'hi', quickReplies: ['a', 'b'], timestamp: new Date() };
      rec.strippedHead = updater([head, { id: 'x', sender: 'user', content: 'q', timestamp: new Date() }])[0];
    },
    addUserMessage: (c) => { rec.users.push(c); },
    addBotMessage: (...args: unknown[]) => { rec.bots.push(args); return 'id'; },
    scrollToLatest: () => { rec.scroll++; },
  };
  return { ctx, rec };
}

describe('restoreHistory (8-4S-e3)', () => {
  it('leere History → nur Begrüßung, kein Render/Scroll; loadHistory mit sessionId+limit 20', async () => {
    const { ctx, rec } = makeCtx([]);
    await restoreHistory(ctx);
    expect(rec.loadArgs).toEqual({ sid: 'bb-sess', limit: 20 });
    expect(rec.greeting).toBe(1);
    expect(rec.update).toBe(0);
    expect(rec.users).toEqual([]);
    expect(rec.bots).toEqual([]);
    expect(rec.scroll).toBe(0);
  });

  it('nicht-leer: Begrüßung prepend + QR-Strip + user/assistant-Render + Scroll ans Ende', async () => {
    const history: HistoryMessage[] = [
      { role: 'user', content: 'Frage' },
      {
        role: 'assistant', content: 'Antwort',
        cards: [{ id: 'c' }], debug: { x: 1 },
        webLinks: [{ title: 'T', url: 'u' }], queryMetas: [{ search_url: 's', search_term: 't' } as never],
      },
    ];
    const { ctx, rec } = makeCtx(history);
    await restoreHistory(ctx);

    expect(rec.greeting).toBe(1);
    expect(rec.update).toBe(1);
    expect(rec.strippedHead?.quickReplies).toBeUndefined(); // Greeting-QRs gestrippt
    expect(rec.users).toEqual(['Frage']);
    // ALT: addBotMessage(content, false, cards, undefined, debug, undefined, queryMetas, webLinks)
    expect(rec.bots[0]).toEqual([
      'Antwort', false, [{ id: 'c' }], undefined, { x: 1 }, undefined,
      [{ search_url: 's', search_term: 't' }], [{ title: 'T', url: 'u' }],
    ]);
    expect(rec.scroll).toBe(1);
  });

  it('leere Content-Zeilen werden übersprungen; nicht-Array cards/webLinks/queryMetas → undefined', async () => {
    const history: HistoryMessage[] = [
      { role: 'user', content: '   ' },                       // leer nach trim → skip
      { role: 'assistant', content: 'A', cards: 'nope' as never }, // cards kein Array → undefined
    ];
    const { ctx, rec } = makeCtx(history);
    await restoreHistory(ctx);
    expect(rec.users).toEqual([]);
    expect(rec.bots[0]).toEqual(['A', false, undefined, undefined, undefined, undefined, undefined, undefined]);
  });
  /**
   * Befund 2026-08-17 (Browser-Plugin der Kollegen, ohne Sidebar-API):
   * Beim ersten Laden mit Seitenkontext ist die Kontext-Begruessung der Opener —
   * `_greetOnFirstLoad` laesst die statische Startnachricht dann bewusst aus
   * (Ansatz C: genau EINE Eroeffnung). Wird das Widget beim Seitenwechsel neu
   * eingehaengt, lief hier trotzdem `showGreeting()` und schob eine
   * Startnachricht davor, die es im Verlauf nie gab.
   */
  it('Verlauf beginnt mit einer Kontext-Begruessung → KEINE Startnachricht davor', async () => {
    const history: HistoryMessage[] = [
      { role: 'assistant', content: 'Du bist auf de.wikipedia.org …', debug: { pattern: 'CTX:external' } },
      { role: 'user', content: 'Was kannst du?' },
      { role: 'assistant', content: 'Einiges.' },
    ];
    const { ctx, rec } = makeCtx(history);
    await restoreHistory(ctx);
    expect(rec.greeting).toBe(0);
    expect(rec.update).toBe(0);          // nichts zu strippen, es gibt keinen prepend
    expect(rec.bots.length).toBe(2);     // Kontext-Begruessung + Antwort bleiben
    expect(rec.scroll).toBe(1);
  });

  // Nur der Opener entscheidet: wer das Gespraech mit einer Frage begonnen hat,
  // hat die Startnachricht gesehen — auch wenn spaeter eine Seite gewechselt wurde.
  it('Kontext-Begruessung MITTEN im Verlauf → Startnachricht bleibt', async () => {
    const history: HistoryMessage[] = [
      { role: 'user', content: 'Frage' },
      { role: 'assistant', content: 'Du bist auf de.wikipedia.org …', debug: { pattern: 'CTX:external' } },
    ];
    const { ctx, rec } = makeCtx(history);
    await restoreHistory(ctx);
    expect(rec.greeting).toBe(1);
  });

  it('Tour-Opener ist KEINE Kontext-Begruessung → Startnachricht bleibt', async () => {
    const history: HistoryMessage[] = [
      { role: 'assistant', content: 'Willkommen zur Tour', debug: { pattern: 'TOUR:step1' } },
    ];
    const { ctx, rec } = makeCtx(history);
    await restoreHistory(ctx);
    expect(rec.greeting).toBe(1);
  });
});
