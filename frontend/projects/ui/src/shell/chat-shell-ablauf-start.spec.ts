// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * AS-4b (Plan 2026-11-09 §5f, E2 A): `startAblauf(id, daten?)` — die Gastseite startet einen
 * Ablauf mit Startdaten. Ein Zug mit der Direktaktion `ablauf_starten` und `{ablauf, start}`, als
 * Auftrags-Blase des Gastgebers (ehrlich sichtbar, wie `startTask`). Die Daten prüft das Backend
 * (`services/ablauf/startdaten`); hier nur: eine gültige Kennung und ein reines Objekt.
 */

const RESP = { content: 'Los.', session_id: 's1', cards: [], quick_replies: [] } as unknown as ChatResponse;

function make(): ChatShellComponent {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  return f.componentInstance;
}

function fakeApi() {
  return {
    stream: vi.fn(async (..._args: unknown[]) => RESP),
    post: vi.fn(async () => RESP),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false),
    loadHistory: vi.fn(async () => []), warteAufAnmeldung: vi.fn(),
  };
}

describe('ChatShellComponent — startAblauf (AS-4b)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('schickt ablauf_starten mit Kennung und Startdaten, als Blase des Gastgebers', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;

    await c.startAblauf('sammlung_pflegen', { sammlung: 'a-b', neu: true });

    const [, nachricht, , , aktion, params] = api.stream.mock.calls[0] as unknown[];
    expect(aktion).toBe('ablauf_starten');
    expect(params).toEqual({ ablauf: 'sammlung_pflegen', start: { sammlung: 'a-b', neu: true },
      quelle: 'gastseite' });
    const blase = c.messages()[0];
    expect(blase.fromHost).toBe(true);
    // Review PR #51 (Widget, Befund 5): die Blase nennt keine technische Kennung
    expect(blase.content).toBe('Ablauf starten');
    expect(blase.content).not.toContain('sammlung_pflegen');
    expect(nachricht).toBe(blase.content);
  });

  it('ohne Daten nur die Kennung', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    await c.startAblauf('baum');
    expect(api.stream.mock.calls[0][5]).toEqual({ ablauf: 'baum', quelle: 'gastseite' });
  });

  it('leere Daten zählen als keine (Review AS-4b, Befund 9)', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    await c.startAblauf('baum', {});
    expect(api.stream.mock.calls[0][5]).toEqual({ ablauf: 'baum', quelle: 'gastseite' });
  });

  it('zu große Daten starten nichts und warnen ohne Werte (Befunde 7, 13)', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    await c.startAblauf('baum', { geheim: 'x'.repeat(20_000) });
    await c.startAblauf('baum', Object.fromEntries(Array.from({ length: 21 }, (_, i) => [`k${i}`, i])));
    expect(api.stream).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledTimes(2);
    expect(String(warn.mock.calls[0])).not.toContain('geheim');
  });

  it('auch der POST-Rückfall trägt Aktion und Parameter', async () => {
    const c = make();
    const api = fakeApi();
    api.stream.mockRejectedValue(new Error('kein Strom'));
    (c as any)._api = api;
    await c.startAblauf('baum', { x: 1 });
    const aufruf = api.post.mock.calls[0] as unknown[];
    expect(aufruf).toContain('ablauf_starten');
    expect(aufruf).toContainEqual({ ablauf: 'baum', start: { x: 1 }, quelle: 'gastseite' });
  });

  it('Auftrag und Ablauf während eines Zugs gehen in ihrer Reihenfolge ab', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    c.isLoading.set(true);
    const erst = c.startTask('Zuerst der Auftrag.');
    const dann = c.startAblauf('baum');
    c.isLoading.set(false);
    TestBed.tick();
    await erst;
    TestBed.tick();
    await dann;
    expect(api.stream.mock.calls.map((z) => z[4] ?? 'text')).toEqual(['text', 'ablauf_starten']);
  });

  it('eine ungültige Kennung oder Daten, die kein Objekt sind, starten nichts', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    await c.startAblauf('Nicht gültig');
    await c.startAblauf('');
    await c.startAblauf('baum', ['liste'] as unknown as Record<string, unknown>);
    await c.startAblauf('baum', 'text' as unknown as Record<string, unknown>);
    expect(api.stream).not.toHaveBeenCalled();
    expect(c.messages()).toEqual([]);
  });

  it('Daten gehen als reines JSON hinaus (keine Funktionen, keine Prototypen)', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    await c.startAblauf('baum', { a: 1, f: () => 1, d: new Date(0) } as unknown as Record<string, unknown>);
    expect(api.stream.mock.calls[0][5]).toEqual({
      ablauf: 'baum', start: { a: 1, d: '1970-01-01T00:00:00.000Z' }, quelle: 'gastseite' });
  });

  it('während eines laufenden Zugs wartet der Start und geht danach ab', async () => {
    const c = make();
    const api = fakeApi();
    (c as any)._api = api;
    c.isLoading.set(true);

    const erledigt = c.startAblauf('baum', { x: 1 });
    expect(api.stream).not.toHaveBeenCalled();

    c.isLoading.set(false);
    TestBed.tick();
    await erledigt;
    expect(api.stream).toHaveBeenCalledTimes(1);
    expect(api.stream.mock.calls[0][4]).toBe('ablauf_starten');
  });

  it('die Markierung des Gastgebers gilt nur für den einen Zug', async () => {
    const c = make();
    (c as any)._api = fakeApi();
    await c.startAblauf('baum');
    await c.sendMessage('und jetzt ich');
    expect(c.messages()[2].fromHost).toBeFalsy();
  });
});
