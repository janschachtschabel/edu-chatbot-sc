import { describe, expect, it } from 'vitest';

import type { UiBlock } from '@boerdi/ui-module';

import type { ChatMessage } from '../grouping/message-types';
import { Vormerkungen } from './vormerkungen';

/** Paket U2 (T-10): der vorgemerkte Stand geht mit der nächsten getippten Nachricht mit. */
function entwurf(block_id: string, status: UiBlock['status'] = 'offen'): UiBlock {
  return { block_id, modul: 'ui_strukturentwurf', version: 1, art: 'abfragen', daten: {}, text: '', status };
}

function bot(id: string, bloecke: UiBlock[]): ChatMessage {
  return { id, sender: 'bot', content: '', timestamp: new Date(0), ui: { ui_bloecke: bloecke } };
}

describe('Vormerkungen', () => {
  it('liefert den jüngsten Stand eines offenen Blocks', () => {
    const v = new Vormerkungen();
    v.setzen({ nachrichtId: 'm1', blockId: 'b1', daten: { stand: 1 } });
    v.setzen({ nachrichtId: 'm1', blockId: 'b1', daten: { stand: 2 } });
    expect(v.fuerZug([bot('m1', [entwurf('b1')])])).toEqual({ nachrichtId: 'm1', blockId: 'b1', daten: { stand: 2 } });
  });

  it('nichts, wenn der Block nicht mehr offen ist oder fehlt', () => {
    const v = new Vormerkungen();
    v.setzen({ nachrichtId: 'm1', blockId: 'b1', daten: { stand: 1 } });
    expect(v.fuerZug([bot('m1', [entwurf('b1', 'veraltet')])])).toBeNull();
    expect(v.fuerZug([bot('m2', [entwurf('b1')])])).toBeNull();
  });

  it('null nimmt die Vormerkung zurück; von zwei offenen gewinnt die zuletzt gesetzte', () => {
    const v = new Vormerkungen();
    const msgs = [bot('m1', [entwurf('b1')]), bot('m2', [entwurf('b2')])];
    v.setzen({ nachrichtId: 'm2', blockId: 'b2', daten: { b: 2 } });
    v.setzen({ nachrichtId: 'm1', blockId: 'b1', daten: { b: 1 } });
    expect(v.fuerZug(msgs)?.blockId).toBe('b1');
    v.setzen({ nachrichtId: 'm1', blockId: 'b1', daten: null });
    expect(v.fuerZug(msgs)?.blockId).toBe('b2');
  });
});
