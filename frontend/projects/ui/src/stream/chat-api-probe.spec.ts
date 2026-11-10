// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * Paket AS-8b (Plan 2026-11-09 §5n, P-1): die Probe der Studio-Vorschau reist als `probe: true` im
 * Rumpf jedes Zuges. Ohne Probe fehlt das Feld ganz — das Backend prüft es nur, wenn es da ist.
 */
function rumpfFetch(gesehen: Record<string, unknown>[]): typeof fetch {
  return (async (_url: string, init: RequestInit) => {
    gesehen.push(JSON.parse(String(init.body)));
    return { ok: true, status: 200, json: async () => ({ content: 'ok' }) } as unknown as Response;
  }) as unknown as typeof fetch;
}

describe('Probe der Studio-Vorschau auf dem Draht (AS-8b)', () => {
  it('ohne Probe kein Feld', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    await api.post('s1', 'hallo');
    expect('probe' in gesehen[0]).toBe(false);
  });

  it('mit Probe in jedem Zug, und wieder aus', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    api.setProbe(true);
    await api.post('s1', 'hallo');
    await api.post('s1', 'noch einmal', undefined, 'ablauf_starten', { ablauf: 'a' });
    expect(gesehen.map((r) => r['probe'])).toEqual([true, true]);
    api.setProbe(false);
    await api.post('s1', 'ohne');
    expect('probe' in gesehen[2]).toBe(false);
  });
});

describe('Gespräch der Studio-Vorschau auf dem Draht (Plan 2026-11-10, TB-E2)', () => {
  it('ohne Vorschau kein Feld; mit Vorschau in jedem Zug, und wieder aus', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    await api.post('s1', 'hallo');
    expect('vorschau' in gesehen[0]).toBe(false);
    api.setVorschau(true);
    await api.post('s1', 'in der Vorschau');
    expect(gesehen[1]['vorschau']).toBe(true);
    expect('probe' in gesehen[1]).toBe(false);   // die Vorschau ist kein Trockenlauf
    api.setVorschau(false);
    await api.post('s1', 'ohne');
    expect('vorschau' in gesehen[2]).toBe(false);
  });
});
