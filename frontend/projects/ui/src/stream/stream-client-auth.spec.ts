// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import { clearAccessBlock, writeAccessBlock } from '../session/mcp-access';
import { postChat, streamChat } from './stream-client';

/**
 * C5-b: Der Zugangsblock muss auf **beiden** Wegen ans Backend kommen — im
 * Strom und im Rückfall-POST. Eigene Datei mit jsdom, weil `stream-client.spec`
 * in der Node-Umgebung läuft und dort kein `sessionStorage` existiert.
 *
 * Gepinnt wird, was auf dem Draht landet, nicht welche Funktion gerufen wurde:
 * die halb verdrahtete Fassung (Strom ja, Rückfall nein) wäre sonst grün — und
 * genau die fällt erst auf, wenn ein Stream abbricht.
 */

const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';

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

beforeEach(() => {
  sessionStorage.clear();
});

describe('Zugangsblock auf dem Draht', () => {
  it('reist im Strom mit', async () => {
    writeAccessBlock(BLOCK);
    const gesehen: Record<string, string>[] = [];
    await streamChat({
      url: '/api/chat/stream',
      body: {},
      onEvent: () => undefined,
      fetchImpl: aufzeichnendesFetch(gesehen, true),
    });
    expect(gesehen[0]['WLO-Access-Block']).toBe(BLOCK);
    // Die Bestands-Kopfzeilen dürfen dabei nicht verloren gehen.
    expect(gesehen[0]['Content-Type']).toBe('application/json');
    expect(gesehen[0]['Accept']).toBe('text/event-stream');
  });

  it('reist im Rückfall-POST mit', async () => {
    writeAccessBlock(BLOCK);
    const gesehen: Record<string, string>[] = [];
    await postChat({
      url: '/api/chat',
      body: {},
      fetchImpl: aufzeichnendesFetch(gesehen, false),
    });
    expect(gesehen[0]['WLO-Access-Block']).toBe(BLOCK);
    expect(gesehen[0]['Content-Type']).toBe('application/json');
  });

  it('ohne Anmeldung geht gar keine solche Kopfzeile raus', async () => {
    clearAccessBlock();
    const gesehen: Record<string, string>[] = [];
    await postChat({
      url: '/api/chat',
      body: {},
      fetchImpl: aufzeichnendesFetch(gesehen, false),
    });
    expect('WLO-Access-Block' in gesehen[0]).toBe(false);
  });
});
