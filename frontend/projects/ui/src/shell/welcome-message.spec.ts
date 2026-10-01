import { describe, expect, it } from 'vitest';

import { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { WelcomeContext, WelcomeMessage } from './welcome-message';

/**
 * Feste Startnachricht (2026-10-01 aus `lifecycle.ts` gelöst). Die Anzeige selbst
 * pinnt `lifecycle.spec`; hier der Austausch beim Sprachwechsel (Paket 1, T2):
 * bis dahin blieb die deutsche Begrüßung stehen, obwohl die Oberfläche englisch war.
 */
const ZEIT = new Date(0);

function make(over: Partial<WelcomeContext> = {}) {
  const zustand = { gruss: 'Hallo', chips: ['A'], user: false };
  let msgs: ChatMessage[] = [];
  let n = 0;
  const ctx: WelcomeContext = {
    greeting: () => zustand.gruss,
    startReplies: () => zustand.chips,
    showWelcome: () => true,
    t: createTranslator(DE, DE),
    addBotMessage: (content, _laedt, _karten, quickReplies) => {
      const id = `m${++n}`;
      msgs = [...msgs, { id, sender: 'bot', content, quickReplies, timestamp: ZEIT }];
      return id;
    },
    updateMessages: (f) => { msgs = f(msgs); },
    hasUserMessages: () => zustand.user,
    ...over,
  };
  return {
    wm: new WelcomeMessage(ctx), zustand,
    msgs: () => msgs, setMsgs: (m: ChatMessage[]) => { msgs = m; },
  };
}

describe('WelcomeMessage.relocalize (Paket 1, T2)', () => {
  it('tauscht die Startnachricht samt Chips, solange sie allein steht', () => {
    const { wm, zustand, msgs } = make();
    wm.show();
    zustand.gruss = 'Hello';
    zustand.chips = ['B'];
    wm.relocalize();
    expect(msgs().map((m) => [m.content, m.quickReplies])).toEqual([['Hello', ['B']]]);
  });

  it('nach der ersten Frage bleibt der Verlauf, wie er ist', () => {
    const { wm, zustand, msgs } = make();
    wm.show();
    zustand.user = true;
    zustand.gruss = 'Hello';
    wm.relocalize();
    expect(msgs().map((m) => m.content)).toEqual(['Hallo']);
  });

  it('steht schon mehr als die Startnachricht da (etwa ein Tour-Schritt), bleibt alles', () => {
    const { wm, zustand, msgs, setMsgs } = make();
    wm.show();
    setMsgs([...msgs(), { id: 'tour', sender: 'bot', content: 'Tour', timestamp: ZEIT }]);
    zustand.gruss = 'Hello';
    wm.relocalize();
    expect(msgs().map((m) => m.content)).toEqual(['Hallo', 'Tour']);
  });

  it('der Kontext-Gruß des Backends bleibt stehen — ihn speichert der Server', () => {
    const { wm, zustand, msgs, setMsgs } = make();
    setMsgs([{ id: 'ctx', sender: 'bot', content: 'Du bist auf …', timestamp: ZEIT }]);
    zustand.gruss = 'Hello';
    wm.relocalize();
    expect(msgs().map((m) => m.content)).toEqual(['Du bist auf …']);
  });

  it('ohne show-welcome gibt es nichts zu tauschen', () => {
    const { wm, zustand, msgs } = make({ showWelcome: () => false });
    wm.show();
    zustand.gruss = 'Hello';
    wm.relocalize();
    expect(msgs()).toEqual([]);
  });
});
