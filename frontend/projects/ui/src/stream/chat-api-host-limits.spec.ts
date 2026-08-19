// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatApiClient } from './chat-api';

/**
 * Was die Einbettung ANZEIGT und ERLAUBT, auf dem Draht (Paket O, 2026-08-18).
 *
 * Der Befund, der das Paket ausloest: `inline-result-grouping` war ein REINES
 * Frontend-Attribut — es entschied ueber die Darstellung und erreichte das
 * Modell nie. Gepinnt wird deshalb der RUMPF, nicht der Aufruf: nur er beweist,
 * dass die Angabe wirklich hinuebergeht.
 *
 * Zweite Zusage: was auf Vorgabe steht, wird NICHT gesendet. Ein leeres Feld ist
 * keine Aussage — und im Backend erzeugt jede Abweichung Prompt-Text, den ein
 * versehentlich mitgeschickter Vorgabewert bezahlen wuerde.
 */

/** fetchImpl, das den gesendeten Rumpf festhaelt. */
function rumpfFetch(gesehen: Record<string, unknown>[]): typeof fetch {
  return (async (_url: string, init: RequestInit) => {
    gesehen.push(JSON.parse(String(init.body)));
    return { ok: true, status: 200, json: async () => ({ content: 'ok' }) } as unknown as Response;
  }) as unknown as typeof fetch;
}

function umgebung(rumpf: Record<string, unknown>): Record<string, unknown> {
  return rumpf['environment'] as Record<string, unknown>;
}

describe('Grenzen der Einbettung auf dem Draht', () => {
  it('sendet nichts davon, solange niemand etwas gesagt hat', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    await api.post('s1', 'hallo');
    const env = umgebung(gesehen[0]);
    expect(env['inline_result_grouping']).toBeUndefined();
    expect(env['tool_mode']).toBeUndefined();
    expect(env['forced_quick_replies']).toBeUndefined();
  });

  it('traegt die fehlende Gruppierung mit — gerade weil sie `false` ist', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    api.setInlineResultGrouping(false);
    await api.post('s1', 'hallo');
    expect(umgebung(gesehen[0])['inline_result_grouping']).toBe(false);
  });

  it('traegt den Werkzeug-Modus mit', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    api.setToolMode('read-only');
    await api.post('s1', 'hallo');
    expect(umgebung(gesehen[0])['tool_mode']).toBe('read-only');
  });

  it('traegt erzwungene Chips mit und behaelt sie ueber Zuege', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    api.setQuickReplies(['Passt', 'Passt nicht']);
    await api.post('s1', 'eins');
    await api.post('s1', 'zwei');
    expect(umgebung(gesehen[0])['forced_quick_replies']).toEqual(['Passt', 'Passt nicht']);
    expect(umgebung(gesehen[1])['forced_quick_replies']).toEqual(['Passt', 'Passt nicht']);
  });

  it('gibt die Chips mit einer leeren Liste wieder frei', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    api.setQuickReplies(['Passt']);
    api.setQuickReplies([]);
    await api.post('s1', 'hallo');
    expect(umgebung(gesehen[0])['forced_quick_replies']).toBeUndefined();
  });

  it('wirft leere Chips weg, kuerzt aber keinen Text', async () => {
    const gesehen: Record<string, unknown>[] = [];
    const api = new ChatApiClient({ fetchImpl: rumpfFetch(gesehen) });
    const lang = 'Zeig mir alles zu diesem Thema, sortiert nach Eignung fuer Klasse 8';
    api.setQuickReplies(['  ', lang]);
    await api.post('s1', 'hallo');
    // Der Chip-TEXT ist die Nachricht, die der Klick sendet — ein gekuerzter
    // Chip schickte eine andere Frage, als er verspricht.
    expect(umgebung(gesehen[0])['forced_quick_replies']).toEqual([lang]);
  });
});
