// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * G1 — der unsichtbare Rahmen der Gastanwendung auf dem Draht.
 *
 * Gepinnt wird, was FÄHRT: `setHostInstruction` allein sagt nichts darüber, ob
 * der Satz auch im Rumpf landet, und die beiden Eigenschaften, die ihn brauchbar
 * machen, sind gerade die unsichtbaren — dass er nach EINEM Zug verbraucht ist
 * und dass ein dazwischenfunkender Ping ihn NICHT aufisst.
 */

/** fetchImpl, das die gesendeten Rümpfe festhält (nicht-strömend, wie
 *  `chat-api-engine.spec.ts` es für den Rückfall-POST tut). */
function aufzeichnendesFetch(rumpfe: any[]): typeof fetch {
  return (async (_url: string, init: RequestInit) => {
    rumpfe.push(JSON.parse(String(init.body)));
    return { ok: true, status: 200, json: async () => ({ content: 'ok' }) } as unknown as Response;
  }) as unknown as typeof fetch;
}

const anweisung = (rumpf: any) => rumpf.environment.host_instruction;

describe('host_instruction auf dem Draht', () => {
  it('reist am nächsten Zug mit', async () => {
    const rumpfe: any[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(rumpfe) });
    api.setHostInstruction('Du bist in der Redaktionsumgebung.');
    await api.post('s1', 'hallo');
    expect(anweisung(rumpfe[0])).toBe('Du bist in der Redaktionsumgebung.');
  });

  it('ist danach verbraucht — der übernächste Zug fährt ohne', async () => {
    const rumpfe: any[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(rumpfe) });
    api.setHostInstruction('Einmalig.');
    await api.post('s1', 'erste');
    await api.post('s1', 'zweite');
    expect(anweisung(rumpfe[0])).toBe('Einmalig.');
    expect(anweisung(rumpfe[1])).toBeUndefined();
  });

  it('wird von einem Kontext-Ping NICHT aufgebraucht', async () => {
    // Der Ping ist ein Zug, den die Gastanwendung nicht gemeint hat. Ohne diese
    // Ausnahme fräße ein zufällig dazwischenkommender Ping den Rahmen auf, und
    // die Eingabe der Person liefe ohne — ein Fehler, der nur sporadisch
    // aufträte und deshalb teuer zu finden wäre.
    const rumpfe: any[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(rumpfe) });
    api.setHostInstruction('Für die Person, nicht für den Ping.');
    await api.post('s1', '', { page_event: 'context_open' });
    await api.post('s1', 'echte Frage');
    expect(anweisung(rumpfe[0])).toBeUndefined();
    expect(anweisung(rumpfe[1])).toBe('Für die Person, nicht für den Ping.');
  });

  it('ohne Anweisung steht das Feld gar nicht im Rumpf', async () => {
    // Ein leeres Feld wäre eine Aussage über eine Absicht, die niemand hat —
    // dieselbe Linie wie beim `result_schema` daneben.
    const rumpfe: any[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(rumpfe) });
    await api.post('s1', 'hallo');
    expect('host_instruction' in rumpfe[0].environment).toBe(false);
  });

  it('Leerraum löscht einen gesetzten Rahmen wieder', async () => {
    const rumpfe: any[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(rumpfe) });
    api.setHostInstruction('erst gesetzt');
    api.setHostInstruction('   ');
    await api.post('s1', 'hallo');
    expect(anweisung(rumpfe[0])).toBeUndefined();
  });
});
