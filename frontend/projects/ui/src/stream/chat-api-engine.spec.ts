// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * Der Maschinen-Umschalter auf dem Draht (2026-08-13).
 *
 * Gepinnt wird, was FÄHRT, nicht welche Methode gerufen wurde — dieselbe Linie
 * wie in `stream-client-auth.spec.ts` und aus demselben Grund: die halb
 * verdrahtete Fassung (Strom ja, Rückfall nein) wäre sonst grün, und sie fiele
 * erst auf, wenn ein Stream abbricht und der Zug still die Maschine wechselt.
 */

const HEADER = 'X-Boerdi-Engine';

/** fetchImpl, das die Kopfzeilen festhält und eine fertige Antwort liefert. */
function aufzeichnendesFetch(gesehen: Record<string, string>[], sse: boolean): typeof fetch {
  return (async (_url: string, init: RequestInit) => {
    gesehen.push({ ...((init.headers ?? {}) as Record<string, string>) });
    if (!sse) {
      return { ok: true, status: 200, json: async () => ({ content: 'ok' }) } as unknown as Response;
    }
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(new TextEncoder().encode('event: result\ndata: {"content":"ok"}\n\n'));
        c.close();
      },
    });
    return { ok: true, status: 200, body } as unknown as Response;
  }) as unknown as typeof fetch;
}

describe('X-Boerdi-Engine auf dem Draht', () => {
  it('reist im Strom mit', async () => {
    const gesehen: Record<string, string>[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(gesehen, true) });
    api.setEngine('agent');
    await api.stream('s1', 'hallo', () => {});
    expect(gesehen[0][HEADER]).toBe('agent');
  });

  it('reist im Rückfall-POST mit', async () => {
    const gesehen: Record<string, string>[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(gesehen, false) });
    api.setEngine('agent');
    await api.post('s1', 'hallo');
    expect(gesehen[0][HEADER]).toBe('agent');
  });

  it('schickt ohne Wahl GAR KEINE Kopfzeile', async () => {
    // Nicht etwa eine leere: das Backend protokolliert einen vorgelegten, aber
    // unbekannten Wert als Warnung — und „keine Wahl getroffen" ist keine
    // Warnung, sondern der Normalfall.
    const gesehen: Record<string, string>[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(gesehen, true) });
    await api.stream('s1', 'hallo', () => {});
    expect(HEADER in gesehen[0]).toBe(false);
  });

  it('normalisiert Grossschreibung und Leerzeichen', async () => {
    // Der Wert kommt aus einem Host-Attribut, das ein Mensch tippt. Das Backend
    // vergleicht kleingeschrieben (`engine_choice.choose_engine`), also passt
    // sich der Client daran an, statt sich auf dessen Nachsicht zu verlassen.
    const gesehen: Record<string, string>[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(gesehen, true) });
    api.setEngine('  Agent ');
    await api.stream('s1', 'hallo', () => {});
    expect(gesehen[0][HEADER]).toBe('agent');
  });

  it('lässt sich zurückstellen', async () => {
    // Das Bedienpult der Demo-Seiten entfernt das Attribut wieder, wenn man
    // „Vorgabe" wählt. Bliebe die Wahl kleben, zeigte die Seite eine Vorgabe an
    // und führe weiter die zuletzt gewählte Maschine.
    const gesehen: Record<string, string>[] = [];
    const api = new ChatApiClient({ fetchImpl: aufzeichnendesFetch(gesehen, true) });
    api.setEngine('agent');
    api.setEngine('');
    await api.stream('s1', 'hallo', () => {});
    expect(HEADER in gesehen[0]).toBe(false);
  });
});
