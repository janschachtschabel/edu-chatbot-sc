// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * Review U1-d1, Befund 8 (Plan §3.4): Das Widget meldet, welche UI-Module es zeigen kann
 * (`environment.ui_module`). Das Backend bietet ein Modul-Werkzeug nur dann an — ein älteres
 * Widget ohne Meldung bekommt keins. Gepinnt wird der Rumpf, nicht der Aufruf.
 */
function rumpfFetch(gesehen: Record<string, unknown>[]): typeof fetch {
  return (async (_url: string, init: RequestInit) => {
    gesehen.push(JSON.parse(String(init.body)));
    return { ok: true, status: 200, json: async () => ({ content: 'ok' }) } as unknown as Response;
  }) as unknown as typeof fetch;
}

async function umgebung(einrichten: (api: ChatApiClient) => void): Promise<Record<string, unknown>> {
  const gesehen: Record<string, unknown>[] = [];
  const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
  einrichten(api);
  await api.post('s1', 'hallo');
  return gesehen[0]['environment'] as Record<string, unknown>;
}

describe('Module des Widgets auf dem Draht', () => {
  it('ohne Meldung kein Feld', async () => {
    expect((await umgebung(() => undefined))['ui_module']).toBeUndefined();
    expect((await umgebung((api) => api.setUiModule([])))['ui_module']).toBeUndefined();
  });

  it('trägt die Namen des Registers mit, sortiert', async () => {
    const env = await umgebung((api) => api.setUiModule(['ui_linkbox', 'ui_entscheidung']));
    expect(env['ui_module']).toEqual(['ui_entscheidung', 'ui_linkbox']);
  });

  it('nur gültige Namen, höchstens 50 — sonst lehnte das Backend den ganzen Zug ab', async () => {
    const viele = Array.from({ length: 60 }, (_, i) => `ui_m${String(i).padStart(2, '0')}`);
    const env = await umgebung((api) => api.setUiModule(['Kaputt', 'ui_x', ...viele]));
    const namen = env['ui_module'] as string[];
    expect(namen.length).toBe(50);
    expect(namen.every((n) => /^ui_[a-z0-9_]{2,40}$/.test(n))).toBe(true);
  });
});
