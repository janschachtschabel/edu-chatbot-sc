// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * Paket K1b: der Stand eines Ablauf-Auftrags für `ui_fortschritt` — `POST /api/ui/auftrag/stand`.
 * Kein Zug: Sitzung, Ablauf und das Kürzel des Auftrags gehen auf den Draht (nie eine Job-ID).
 */
interface Gesehen { url: string; init: RequestInit }

function antwortFetch(gesehen: Gesehen[], antwort: { ok: boolean; status: number; json?: unknown }): typeof fetch {
  return (async (url: string, init: RequestInit) => {
    gesehen.push({ url, init });
    return { ok: antwort.ok, status: antwort.status, headers: new Headers(), json: async () => antwort.json } as unknown as Response;
  }) as unknown as typeof fetch;
}

describe('ChatApiClient.auftragStand', () => {
  it('schickt Sitzung, Ablauf und Kürzel und gibt den Stand zurück', async () => {
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, { ok: true, status: 200, json: { stand: 'laeuft' } }) });
    api.setBaseUrl('https://boerdi.example');
    await expect(api.auftragStand('bb-1', 'lesen', '0123456789ab')).resolves.toEqual({ stand: 'laeuft' });
    const [{ url, init }] = gesehen;
    expect(url).toBe('https://boerdi.example/api/ui/auftrag/stand');
    expect(JSON.parse(String(init.body))).toEqual({ session_id: 'bb-1', ablauf: 'lesen', kuerzel: '0123456789ab' });
  });

  it('ein Fehler trägt den Status', async () => {
    const api = new ChatApiClient({ fetchImpl: antwortFetch([], { ok: false, status: 409 }) });
    await expect(api.auftragStand('bb-1', 'lesen', '0123456789ab')).rejects.toMatchObject({ status: 409 });
  });

  it('ein unbekannter Stand ist ein Fehler, kein „fertig“', async () => {
    const api = new ChatApiClient({ fetchImpl: antwortFetch([], { ok: true, status: 200, json: { stand: 'irgendwas' } }) });
    await expect(api.auftragStand('bb-1', 'lesen', '0123456789ab')).rejects.toThrow();
  });
});
