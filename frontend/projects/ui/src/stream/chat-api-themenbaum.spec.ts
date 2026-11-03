// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import { clearAccessBlock, writeAccessBlock } from '../session/mcp-access';
import { ChatApiClient } from './chat-api';

/**
 * Paket U1-h (Plan §18): Unterthemen eines Knotens im Themenbaum — `POST /api/ui/themenbaum/zweig`.
 * Kein Zug: nur Sitzung, Knoten und der Modus der Einbettung gehen auf den Draht, dazu der
 * Zugangsblock wie bei jedem Zug (der Zweig sieht, was der Baum sah).
 */
interface Gesehen { url: string; init: RequestInit }

function antwortFetch(gesehen: Gesehen[], antwort: { ok: boolean; status: number; json?: unknown }): typeof fetch {
  return (async (url: string, init: RequestInit) => {
    gesehen.push({ url, init });
    return {
      ok: antwort.ok, status: antwort.status, headers: new Headers(),
      json: async () => antwort.json,
    } as unknown as Response;
  }) as unknown as typeof fetch;
}

afterEach(() => clearAccessBlock());

describe('ChatApiClient.themenbaumZweig', () => {
  it('schickt Sitzung, Knoten und Modus und gibt die Daten zurück', async () => {
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, { ok: true, status: 200, json: { daten: { knoten: [] } } }) });
    api.setBaseUrl('https://boerdi.example');
    api.setToolMode('read-only');

    await expect(api.themenbaumZweig('bb-1', 'bbbb-2222')).resolves.toEqual({ knoten: [] });

    const [{ url, init }] = gesehen;
    expect(url).toBe('https://boerdi.example/api/ui/themenbaum/zweig');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ session_id: 'bb-1', node_id: 'bbbb-2222', tool_mode: 'read-only' });
  });

  it('ohne Modus kein Feld; der Zugangsblock reist mit', async () => {
    const block = `wlo2.${'A'.repeat(40)}`;
    expect(writeAccessBlock(block)).toBe(true);
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, { ok: true, status: 200, json: { daten: { knoten: [] } } }) });
    await api.themenbaumZweig('bb-1', 'bbbb-2222');
    expect(JSON.parse(String(gesehen[0].init.body))).toEqual({ session_id: 'bb-1', node_id: 'bbbb-2222' });
    const koepfe = gesehen[0].init.headers as Record<string, string>;
    expect(koepfe['WLO-Access-Block']).toBe(block);
  });

  it('ein Fehler trägt den Status (403 heißt: nochmal hilft nicht)', async () => {
    const api = new ChatApiClient({ fetchImpl: antwortFetch([], { ok: false, status: 403 }) });
    await expect(api.themenbaumZweig('bb-1', 'bbbb-2222')).rejects.toMatchObject({ status: 403 });
  });

  it('eine Antwort ohne Daten-Objekt ist ein Fehler, keine leere Liste', async () => {
    const api = new ChatApiClient({ fetchImpl: antwortFetch([], { ok: true, status: 200, json: { daten: 'x' } }) });
    await expect(api.themenbaumZweig('bb-1', 'bbbb-2222')).rejects.toThrow();
  });
});
