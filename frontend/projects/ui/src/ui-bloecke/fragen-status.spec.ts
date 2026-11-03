import { describe, expect, it } from 'vitest';

import type { UiBlock } from '@boerdi/ui-module';

import type { ChatMessage } from '../grouping/message-types';
import { alsBeantwortet, offeneFragenSchliessen, wiederOffen } from './fragen-status';

/**
 * Paket U1-d1: der Zustand abfragender Blöcke im Widget. Der Server schließt die offene Frage mit
 * jedem Zug der Person; das Widget zieht sofort nach, statt erst nach dem Neuladen (dort leitet
 * der Verlauf denselben Zustand ab).
 */
function frage(block_id: string, status: UiBlock['status'] = 'offen'): UiBlock {
  return { block_id, modul: 'ui_entscheidung', version: 1, art: 'abfragen', daten: {}, text: '', status };
}

function bot(id: string, bloecke: UiBlock[]): ChatMessage {
  return { id, sender: 'bot', content: '', timestamp: new Date(0), ui: { ui_bloecke: bloecke } };
}

const ANZEIGE: UiBlock = { block_id: 'b0000009', modul: 'ui_linkbox', version: 1, art: 'anzeigen',
  daten: {}, text: '', status: 'nur_anzeige' };

describe('alsBeantwortet', () => {
  it('setzt genau den Block der Nachricht auf beantwortet, mit Antwort', () => {
    const msgs = [bot('m1', [frage('b0000001')]), bot('m2', [frage('b0000001')])];
    const neu = alsBeantwortet(msgs, 'm2', 'b0000001', { gewaehlt: ['a'] });
    expect(neu[0]).toBe(msgs[0]);                       // unberührt, gleiche Identität
    expect(neu[1].ui!.ui_bloecke![0]).toMatchObject({ status: 'beantwortet', antwort: { gewaehlt: ['a'] } });
  });

  it('lässt einen schon geschlossenen Block, wie er ist', () => {
    const msgs = [bot('m1', [frage('b0000001', 'veraltet')])];
    expect(alsBeantwortet(msgs, 'm1', 'b0000001', { gewaehlt: ['a'] })[0]).toBe(msgs[0]);
  });
});

describe('wiederOffen (Review U1-d1)', () => {
  it('macht die lokal beantwortete Frage wieder offen, ohne Antwort', () => {
    const msgs = alsBeantwortet([bot('m1', [frage('b0000001')])], 'm1', 'b0000001', { gewaehlt: ['a'] });
    const block = wiederOffen(msgs, 'm1', 'b0000001')[0].ui!.ui_bloecke![0];
    expect(block.status).toBe('offen');
    expect(block.antwort ?? null).toBeNull();
  });

  it('lässt veraltete und fremde Blöcke, wie sie sind', () => {
    const msgs = [bot('m1', [frage('b0000001', 'veraltet')]), bot('m2', [frage('b0000002', 'beantwortet')])];
    expect(wiederOffen(msgs, 'm1', 'b0000001')).toBe(msgs);
    expect(wiederOffen(msgs, 'm1', 'b0000002')).toBe(msgs);
  });
});

describe('offeneFragenSchliessen', () => {
  it('macht jede noch offene Frage veraltet — anzeigende und beantwortete bleiben', () => {
    const beantwortet = { ...frage('b0000002', 'beantwortet'), antwort: { gewaehlt: ['x'] } };
    const msgs = [bot('m1', [frage('b0000001'), ANZEIGE]), bot('m2', [beantwortet]),
      { id: 'u1', sender: 'user', content: 'x', timestamp: new Date(0) } as ChatMessage];
    const neu = offeneFragenSchliessen(msgs);
    expect(neu[0].ui!.ui_bloecke!.map((b) => b.status)).toEqual(['veraltet', 'nur_anzeige']);
    expect(neu[1]).toBe(msgs[1]);
    expect(neu[2]).toBe(msgs[2]);
  });

  it('ohne offene Frage bleibt die Liste dieselbe', () => {
    const msgs = [bot('m1', [ANZEIGE])];
    expect(offeneFragenSchliessen(msgs)).toBe(msgs);
  });
});
