import { describe, expect, it, vi } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * Paket 10 (Kurzaudit 2026-10-10, S-4): mit `ticket` tauscht das Widget beim Laden
 * das Ticket gegen einen Zugangsblock — asynchron, und erst wenn die Anmelde-Adresse
 * aus der Konfiguration da ist. Was davor hinausging (Kontext-Ping, Auftrag der
 * Gastseite, ein schneller Klick), lief anonym. Jetzt warten Züge auf den Tausch.
 */
function antwortendesFetch() {
  return vi.fn(async () => new Response(
    JSON.stringify({ content: 'ok', session_id: 's' }), { status: 200 }));
}

describe('ChatApiClient — wartet auf die Anmeldung (Paket 10, S-4)', () => {
  it('schickt erst, wenn der Tausch fertig ist', async () => {
    const fetchImpl = antwortendesFetch();
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    let fertig!: () => void;
    client.warteAufAnmeldung(new Promise<void>((resolve) => { fertig = resolve; }));

    const antwort = client.post('s', 'hallo');
    await Promise.resolve();
    await Promise.resolve();
    expect(fetchImpl).not.toHaveBeenCalled();

    fertig();
    await antwort;
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('ohne Tausch geht es sofort', async () => {
    const fetchImpl = antwortendesFetch();
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    await client.post('s', 'hallo');
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
