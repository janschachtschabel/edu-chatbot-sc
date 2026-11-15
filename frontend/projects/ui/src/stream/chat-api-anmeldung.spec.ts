// @vitest-environment jsdom
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

describe('ChatApiClient — Wache vor dem Zug (Plan 2026-11-15, SA-13)', () => {
  it('gilt auch für Abrufe, die kein Zug sind — sie tragen denselben Block', async () => {
    // Review 2026-11-15: „Meine Vorgänge“, Verlauf, Ablage und Löschen gingen sonst ungeprüft
    // mit dem Block einer Person hinaus, die auf der Seite nicht mehr angemeldet ist.
    const fetchImpl = vi.fn(async () => new Response('[]', { status: 200 }));
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    const wache = vi.fn(async () => undefined);
    client.zugWache = wache;

    await client.eigeneVorgaenge('s').catch(() => undefined);
    expect(wache).toHaveBeenCalledTimes(1);
    await client.vorgangLoeschen('s', 'bb-1').catch(() => undefined);
    expect(wache).toHaveBeenCalledTimes(2);
  });

  it('JEDER Abruf, der den Block trägt, läuft durch die Wache', async () => {
    // Ein Abruf, der an der Wache vorbeigeht, trüge den Block einer Person hinaus, die auf der
    // Seite nicht mehr angemeldet ist. Die Liste ist vollständig — ein neuer Abruf gehört dazu.
    const abrufe: [string, (c: ChatApiClient) => Promise<unknown>][] = [
      ['stream', (c) => c.stream('s', 'hallo', () => undefined)],
      ['post', (c) => c.post('s', 'hallo')],
      ['themenbaumZweig', (c) => c.themenbaumZweig('s', 'knoten')],
      ['dokumentHochladen', (c) => (c.dokumentHochladen as (...a: unknown[]) => Promise<unknown>)(
        's', new File(['x'], 'x.txt'), {})],
      ['ablageSchritt', (c) => (c.ablageSchritt as (...a: unknown[]) => Promise<unknown>)('s', {})],
      ['auftragStand', (c) => c.auftragStand('s', 'ablauf', 'k1')],
      ['offeneVorgaenge', (c) => c.offeneVorgaenge('s')],
      ['wiederkehr', (c) => (c.wiederkehr as (...a: unknown[]) => Promise<unknown>)('s', { ablauf: 'a', kuerzel: 'k' })],
      ['eigeneVorgaenge', (c) => c.eigeneVorgaenge('s')],
      ['vorgangLoeschen', (c) => c.vorgangLoeschen('s', 'bb-1')],
      ['fetchHistory', (c) => c.fetchHistory('s', 20)],
    ];
    for (const [name, abruf] of abrufe) {
      const fetchImpl = vi.fn(async () => new Response('{}', { status: 200 }));
      const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
      const folge: string[] = [];
      fetchImpl.mockImplementation(async () => { folge.push('netz'); return new Response('{}', { status: 200 }); });
      client.zugWache = async () => { folge.push('wache'); };
      // Nicht auf das Ende warten (der Upload geht über `XMLHttpRequest`): die Wache läuft zuerst.
      await Promise.race([abruf(client).catch(() => undefined), new Promise((r) => setTimeout(r, 50))]);
      expect(folge[0], name).toBe('wache');
    }
  });

  it('merkt sich den Block, mit dem der Zug hinausging', async () => {
    const fetchImpl = antwortendesFetch();
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    sessionStorage.setItem('boerdi.mcp-access', 'wlo2.QUJD-_x=.aXY.Y3Q');
    try {
      await client.post('s', 'hallo');
      expect(client.letzterZugBlock).toBe('wlo2.QUJD-_x=.aXY.Y3Q');
    } finally {
      sessionStorage.clear();
    }
    await client.post('s', 'hallo');
    expect(client.letzterZugBlock).toBeNull();
  });

  it('eine Wache, die wirft, hält den Zug nicht auf', async () => {
    const fetchImpl = antwortendesFetch();
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    client.zugWache = async () => { throw new Error('kaputt'); };
    await client.post('s', 'hallo');
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('läuft vor jedem Zug, nach dem Warten auf die Anmeldung', async () => {
    const fetchImpl = antwortendesFetch();
    const client = new ChatApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    const folge: string[] = [];
    let fertig!: () => void;
    client.warteAufAnmeldung(new Promise<void>((resolve) => { fertig = resolve; })
      .then(() => { folge.push('anmeldung'); }));
    let wacheFertig!: () => void;
    client.zugWache = () => new Promise<void>((resolve) => {
      folge.push('wache');
      wacheFertig = resolve;
    });

    const antwort = client.post('s', 'hallo');
    fertig();
    await vi.waitFor(() => expect(folge).toEqual(['anmeldung', 'wache']));
    expect(fetchImpl, 'der Zug wartet auf die Wache').not.toHaveBeenCalled();

    wacheFertig();
    await antwort;
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
