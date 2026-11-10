import { describe, expect, it, vi } from 'vitest';

import { verlaufAbrufen } from './history-transport';

/** Zweites Review AS-U, Befund 6: der Verlauf kommt in der Sprache des Widgets (Titel der Leiste). */
describe('verlaufAbrufen — Sprache', () => {
  const antwort = () => ({ ok: true, json: async () => [] }) as unknown as Response;

  it('schickt die Sprache des Widgets als Accept-Language', async () => {
    const doFetch = vi.fn(async () => antwort());
    await verlaufAbrufen(doFetch as unknown as typeof fetch, '/api', 'bb-1', 20, undefined, 'en');
    const [, optionen] = doFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect((optionen.headers as Record<string, string>)['Accept-Language']).toBe('en');
  });

  it('Querschnitts-Review Q-1: der Zugangsblock reist mit (der Verweis gehört der Person)', async () => {
    const doFetch = vi.fn(async () => antwort());
    await verlaufAbrufen(doFetch as unknown as typeof fetch, '/api', 'bb-1', 20, undefined, 'de',
                         { 'WLO-Access-Block': 'wloBlock' });
    const [, optionen] = doFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(optionen.headers).toEqual({ 'Accept-Language': 'de', 'WLO-Access-Block': 'wloBlock' });
  });

  it('ohne Sprache und Signal ein schlichter Abruf', async () => {
    const doFetch = vi.fn(async () => antwort());
    await verlaufAbrufen(doFetch as unknown as typeof fetch, '/api', 'bb-1', 20);
    expect(doFetch.mock.calls[0]).toHaveLength(1);
  });
});

describe('ChatApiClient.fetchHistory — Zugangsblock (Q-1)', () => {
  it('angemeldet: der gespeicherte Block geht mit; abgemeldet: keiner', async () => {
    const { ChatApiClient } = await import('./chat-api');
    const { MCP_ACCESS_STORAGE_KEY } = await import('../session/mcp-access');
    const doFetch = vi.fn(async () => ({ ok: true, json: async () => [] }) as unknown as Response);
    const api = new ChatApiClient({ fetchImpl: doFetch as unknown as typeof fetch });
    sessionStorage.setItem(MCP_ACCESS_STORAGE_KEY, 'wloBlockDerPerson');
    try {
      await api.fetchHistory('bb-1', 20);
      const [, mit] = doFetch.mock.calls[0] as unknown as [string, RequestInit];
      expect((mit.headers as Record<string, string>)['WLO-Access-Block']).toBe('wloBlockDerPerson');
    } finally {
      sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY);
    }
    await api.fetchHistory('bb-1', 20);
    const ohne = doFetch.mock.calls[1] as unknown as [string, RequestInit?];
    expect((ohne[1]?.headers as Record<string, string> | undefined)?.['WLO-Access-Block']).toBeUndefined();
  });
});

describe('ChatApiClient.fetchHistory — wartet auf die Anmeldung (Z-1)', () => {
  it('ein laufender Ticket-Tausch hält den Abruf an, bis er endet', async () => {
    const { ChatApiClient } = await import('./chat-api');
    const doFetch = vi.fn(async () => ({ ok: true, json: async () => [] }) as unknown as Response);
    const api = new ChatApiClient({ fetchImpl: doFetch as unknown as typeof fetch });
    let fertig: () => void = () => undefined;
    api.warteAufAnmeldung(new Promise<void>((r) => { fertig = r; }));
    const abruf = api.fetchHistory('bb-1', 5);
    await Promise.resolve();
    expect(doFetch).not.toHaveBeenCalled();
    fertig();
    await abruf;
    expect(doFetch).toHaveBeenCalledTimes(1);
  });
});
