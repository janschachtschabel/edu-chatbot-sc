// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Plan 2026-11-10, TB-E3 (Nutzer-Entscheid N4): die KI startet einen Ablauf direkt. Das Backend
 * setzt den Knopf wie beim Vorschlag und nennt ihn in `ui.direkt_start`; das Widget drückt ihn nach
 * dem Zug selbst — derselbe Weg wie ein Klick (Direktaktion `ablauf_starten`). Nur ein Knopf, der
 * unter den Schnellantworten steht, und nur live (der Verlauf startet nie etwas).
 */

const KNOPF = '__action__|Baum|ablauf_starten|{"ablauf":"baum","start_quelle":"ki"}';

function make(): ChatShellComponent {
  TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  });
  const f = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  return f.componentInstance;
}

function fakeApi(erste: Partial<ChatResponse>) {
  const danach = { content: 'Los.', session_id: 's1', cards: [], quick_replies: [] };
  let n = 0;
  return {
    stream: vi.fn(async (..._args: unknown[]) =>
      (n++ === 0 ? { ...danach, ...erste } : danach) as unknown as ChatResponse),
    post: vi.fn(async () => danach as unknown as ChatResponse),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false),
    loadHistory: vi.fn(async () => []), warteAufAnmeldung: vi.fn(),
  };
}

describe('ChatShellComponent — Ablauf direkt starten (TB-E3)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('drückt den Knopf aus ui.direkt_start nach dem Zug selbst', async () => {
    const c = make();
    const api = fakeApi({ content: 'Ich starte den Ablauf.', quick_replies: [KNOPF, 'Mehr'],
                          ui: { direkt_start: KNOPF } as never });
    (c as any)._api = api;
    await c.sendMessage('Bau mir einen Themenbaum');
    TestBed.tick();
    await vi.waitFor(() => expect(api.stream).toHaveBeenCalledTimes(2));
    expect(api.stream.mock.calls[1][4]).toBe('ablauf_starten');
    expect(api.stream.mock.calls[1][5]).toEqual({ ablauf: 'baum', start_quelle: 'ki' });
  });

  it('nicht, wenn der Knopf nicht unter den Schnellantworten steht', async () => {
    const c = make();
    const api = fakeApi({ quick_replies: ['Mehr'], ui: { direkt_start: KNOPF } as never });
    (c as any)._api = api;
    await c.sendMessage('Hallo');
    TestBed.tick();
    await new Promise((r) => setTimeout(r, 0));
    expect(api.stream).toHaveBeenCalledTimes(1);
  });

  it('nicht für einen Knopf, der keinen Ablauf startet', async () => {
    const fremd = '__action__|Löschen|loeschen|{}';
    const c = make();
    const api = fakeApi({ quick_replies: [fremd], ui: { direkt_start: fremd } as never });
    (c as any)._api = api;
    await c.sendMessage('Hallo');
    TestBed.tick();
    await new Promise((r) => setTimeout(r, 0));
    expect(api.stream).toHaveBeenCalledTimes(1);
  });

  it('Review TB-E3, Befund 5: der Direktstart kommt vor einem wartenden Auftrag der Gastseite',
    async () => {
      const c = make();
      const api = fakeApi({ quick_replies: [KNOPF], ui: { direkt_start: KNOPF } as never });
      (c as any)._api = api;
      const zug = c.sendMessage('Bau mir einen Themenbaum');
      const auftrag = c.startTask('Auftrag der Seite');      // wartet hinter dem laufenden Zug
      await zug;
      TestBed.tick();
      await auftrag;
      await vi.waitFor(() => expect(api.stream).toHaveBeenCalledTimes(3));
      expect(api.stream.mock.calls[1][4]).toBe('ablauf_starten');
    });
});
