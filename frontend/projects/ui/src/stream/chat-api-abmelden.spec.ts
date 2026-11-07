import { afterEach, describe, expect, it, vi } from 'vitest';

import { MCP_ACCESS_HEADER, MCP_ACCESS_STORAGE_KEY } from '../session/mcp-access';
import { ChatApiClient } from './chat-api';

/**
 * Plan 2026-11-07 (R2/CB-9): „Abmelden“ beendet den Zugang am MCP-Server. Das Backend widerruft
 * (`POST /api/auth/abmelden`); der Block reist ausdrücklich mit, weil die Shell ihn gleich danach
 * aus dem Speicher löscht.
 */
describe('ChatApiClient.abmelden', () => {
  afterEach(() => sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY));

  it('schickt den Block an das Backend und liest das Ergebnis', async () => {
    const fetchImpl = vi.fn(async (_url: string, _init: RequestInit) => new Response(
      JSON.stringify({ widerrufen: true, erreicht: true }), { status: 200 }));
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(await client.abmelden('wlo2.block')).toBe(true);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('/api/auth/abmelden');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)[MCP_ACCESS_HEADER]).toBe('wlo2.block');
  });

  it('auch wenn der Speicher schon leer ist', async () => {
    sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY);
    const fetchImpl = vi.fn(async (_url: string, _init: RequestInit) => new Response(
      JSON.stringify({ widerrufen: false, erreicht: true }), { status: 200 }));
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(await client.abmelden('wlo2.block')).toBe(false);
    expect((fetchImpl.mock.calls[0][1].headers as Record<string, string>)[MCP_ACCESS_HEADER])
      .toBe('wlo2.block');
  });

  it('wirft nie', async () => {
    const fetchImpl = vi.fn(async () => { throw new TypeError('offline'); });
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    expect(await client.abmelden('wlo2.block')).toBe(false);
  });
});
