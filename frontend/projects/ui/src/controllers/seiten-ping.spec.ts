import { describe, expect, it, vi } from 'vitest';

import type { ChatResponse } from '../grouping/message-types';
import type { ContextGreetingContext } from './context-greeting.controller';
import { SEITEN_PING, SeitenPing, seitenPingNoetig, UnbestimmtMarke } from './seiten-ping';

/**
 * AS-7b (Plan 2026-11-09 §5m, F-4): wartet eine Führung auf die Ankunft, schickt das Widget nach dem
 * Seitenaufruf einen unsichtbaren Ping. Eine Antwort erscheint nur mit Inhalt (die Seite passt).
 */
function ctx(antwort: Partial<ChatResponse> | Error, laedt = false) {
  const nachrichten: string[] = [];
  const c = {
    sendMessage: vi.fn(async () => {
      if (antwort instanceof Error) throw antwort;
      return { session_id: 's', content: '', quick_replies: [], ...antwort } as ChatResponse;
    }),
    pageContext: () => ({}),
    sessionId: () => 'bb-1',
    isLoading: vi.fn(() => laedt),
    setLoading: vi.fn(),
    addBotMessage: vi.fn((inhalt: string) => { nachrichten.push(inhalt); return 'm1'; }),
    removeMessage: vi.fn(),
    setScrollTarget: vi.fn(),
    setLatestDebug: vi.fn(),
  } satisfies ContextGreetingContext;
  return { c, nachrichten };
}

describe('SeitenPing (AS-7b)', () => {
  it('schickt den Ping als Hintergrund-Zug und zeigt die Antwort mit Inhalt', async () => {
    const { c, nachrichten } = ctx({ content: 'Angekommen.', quick_replies: ['x'] });
    expect(await new SeitenPing(c).senden()).toBe(true);
    expect(c.sendMessage).toHaveBeenCalledWith('[ablauf-seite]', { page_event: SEITEN_PING });
    expect(nachrichten).toEqual(['Angekommen.']);
    expect(c.setLoading).toHaveBeenLastCalledWith(false);
  });

  it('eine leere Antwort (Seite passt nicht) zeigt nichts', async () => {
    const { c, nachrichten } = ctx({ content: '' });
    expect(await new SeitenPing(c).senden()).toBe(false);
    expect(nachrichten).toEqual([]);
  });

  it('nur einmal je Seitenaufruf, und nicht während eines Zugs', async () => {
    const { c } = ctx({ content: 'x' });
    const ping = new SeitenPing(c);
    await ping.senden();
    expect(await ping.senden()).toBe(false);
    expect(c.sendMessage).toHaveBeenCalledTimes(1);
    const laeuft = ctx({ content: 'x' }, true);
    expect(await new SeitenPing(laeuft.c).senden()).toBe(false);
    expect(laeuft.c.sendMessage).not.toHaveBeenCalled();
  });

  it('ein Fehler bleibt still', async () => {
    const { c, nachrichten } = ctx(new Error('Netz'));
    expect(await new SeitenPing(c).senden()).toBe(false);
    expect(nachrichten).toEqual([]);
    expect(c.setLoading).toHaveBeenLastCalledWith(false);
  });
});

describe('seitenPingNoetig (R2-c)', () => {
  it('pingt bei wartet_seite und bei einem unbestimmten Stand, sonst nicht', () => {
    const stand = (status: string) => ({ id: 'a', titel: 'A', nr: 1, von: 2, status, teile: [] });
    expect(seitenPingNoetig(stand('wartet_seite'), false)).toBe(true);
    expect(seitenPingNoetig(null, true)).toBe(true);
    expect(seitenPingNoetig(stand('wartet_wahl'), true)).toBe(false);
    expect(seitenPingNoetig(null, false)).toBe(false);
  });
});

describe('UnbestimmtMarke (Review R2, Befund 1)', () => {
  it('gilt für EINEN Ping je markierter Nachricht — danach nicht mehr, eine neue Marke wieder', () => {
    const marke = new UnbestimmtMarke();
    expect(marke.gilt(null)).toBe(false);
    expect(marke.gilt('m1')).toBe(true);
    marke.verbrauchen('m1');
    expect(marke.gilt('m1')).toBe(false);                 // keine Pings bei jeder Navigation
    expect(marke.gilt('m2')).toBe(true);                  // neuer Verlauf, neue Marke
  });
});
