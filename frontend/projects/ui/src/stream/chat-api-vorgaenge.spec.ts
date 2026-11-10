// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * AS-Ud: „Meine Vorgänge“ — `POST /api/ui/vorgaenge/liste` und `/loeschen`. Kein Zug; nur Sitzung
 * und Vorgangskennung gehen auf den Draht, die Antwort wird geprüft.
 */
interface Gesehen { url: string; init: RequestInit }

function antwortFetch(gesehen: Gesehen[], antwort: { ok: boolean; status: number; json?: unknown }): typeof fetch {
  return (async (url: string, init: RequestInit) => {
    gesehen.push({ url, init });
    return { ok: antwort.ok, status: antwort.status, headers: new Headers(), json: async () => antwort.json } as unknown as Response;
  }) as unknown as typeof fetch;
}

const SID = 'bb-12345678-1234-4123-8123-123456789abc';
const EINTRAG = {
  id: '0a1b2c3d-0000-4000-8000-000000000001', titel: 'Lesen', ablauf: null, status: 'aktiv',
  session_id: 'bb-87654321-4321-4321-8321-cba987654321', geaendert: '2026-11-07T09:30:00Z',
};

describe('ChatApiClient — Meine Vorgänge', () => {
  it('liste: schickt die Sitzung und gibt nur wohlgeformte Einträge zurück', async () => {
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, {
      ok: true, status: 200, json: { vorgaenge: [EINTRAG, { ...EINTRAG, id: 'kaputt' }] } }) });
    api.setBaseUrl('https://boerdi.example');
    await expect(api.eigeneVorgaenge(SID)).resolves.toEqual([EINTRAG]);
    const [{ url, init }] = gesehen;
    expect(url).toBe('https://boerdi.example/api/ui/vorgaenge/liste');
    // Q-8: die Sprache des Widgets reist mit (Titel eines Ablaufs)
    expect(JSON.parse(String(init.body))).toEqual({ session_id: SID, sprache: 'de' });
  });

  it('loeschen: schickt Sitzung und Kennung; ein Fehler trägt den Status', async () => {
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, { ok: true, status: 200, json: { geloescht: true } }) });
    api.setBaseUrl('https://boerdi.example');
    await expect(api.vorgangLoeschen(SID, EINTRAG.id)).resolves.toEqual({ laeuftWeiter: false });
    expect(gesehen[0].url).toBe('https://boerdi.example/api/ui/vorgaenge/loeschen');
    expect(JSON.parse(String(gesehen[0].init.body))).toEqual({ session_id: SID, vorgang: EINTRAG.id });
    const nein = new ChatApiClient({ fetchImpl: antwortFetch([], { ok: false, status: 404 }) });
    await expect(nein.vorgangLoeschen(SID, EINTRAG.id)).rejects.toMatchObject({ status: 404 });
  });

  it('loeschen: eine Antwort ohne „geloescht“ ist ein Fehler', async () => {
    const api = new ChatApiClient({ fetchImpl: antwortFetch([], { ok: true, status: 200, json: {} }) });
    await expect(api.vorgangLoeschen(SID, EINTRAG.id)).rejects.toThrow();
  });
});

describe('ChatApiClient — Meine Vorgänge, Q-6/Q-8', () => {
  it('englisch eingestellt: sprache en; läuft ein Auftrag weiter, sagt es das Ergebnis', async () => {
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, {
      ok: true, status: 200, json: { vorgaenge: [], geloescht: true, auftrag_laeuft_weiter: true } }) });
    api.setUiLocale('en');
    await api.eigeneVorgaenge(SID);
    expect(JSON.parse(String(gesehen[0].init.body)).sprache).toBe('en');
    await expect(api.vorgangLoeschen(SID, EINTRAG.id)).resolves.toEqual({ laeuftWeiter: true });
  });
});

describe('ChatApiClient.offeneVorgaenge — Sprache (zweites Review, Z-2)', () => {
  it('der Hinweis „Gespräch fortsetzen“ fragt in der Sprache des Widgets', async () => {
    const gesehen: Gesehen[] = [];
    const api = new ChatApiClient({ fetchImpl: antwortFetch(gesehen, { ok: true, status: 200, json: { vorgaenge: [] } }) });
    api.setUiLocale('en-GB');
    await api.offeneVorgaenge(SID);
    expect(JSON.parse(String(gesehen[0].init.body))).toEqual({ session_id: SID, sprache: 'en' });
  });
});
