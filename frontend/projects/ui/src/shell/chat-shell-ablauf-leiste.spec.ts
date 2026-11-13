// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import type { AblaufStand, ChatResponse } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Paket AS-Ub: die Shell zeigt die Ablauf-Leiste aus dem Stand der jüngsten Bot-Antwort
 * (``ui.ablauf``, AS-Ua), lässt das Etikett „KI-generierte Antwort“ an festen Texten weg
 * (``ui.fester_text``) und schickt „Abbrechen“ als Direktaktion ``ablauf_abbrechen``.
 */

const STAND: AblaufStand = { id: 'probe', titel: 'Probe', nr: 1, von: 3, status: 'laeuft', teile: [] };

function bauen() {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ imports: [ChatShellComponent], providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('persistSession', false);
  f.componentRef.setInput('showWelcome', 'false');
  f.detectChanges();                       // ngOnInit — danach erst den Verlauf setzen
  const c = f.componentInstance;
  const store = (c as unknown as { _store: { set: (m: unknown[]) => void; addBotMessage: (...a: unknown[]) => string } })._store;
  store.set([]);
  return { f, c, store };
}

describe('ChatShellComponent — Ablauf-Leiste (AS-Ub)', () => {
  it('der Stand kommt aus der jüngsten Bot-Antwort; ohne Stand dort keine Leiste', () => {
    const { f, c, store } = bauen();
    store.addBotMessage('Los.', false, [], undefined, { ablauf: STAND, fester_text: true });
    f.detectChanges();
    expect(c.ablaufStand()).toEqual(STAND);
    expect((f.nativeElement as HTMLElement).querySelector('.ablauf-leiste')).not.toBeNull();
    store.addBotMessage('Fertig.', false, [], undefined, {});
    f.detectChanges();
    expect(c.ablaufStand()).toBeNull();
    expect((f.nativeElement as HTMLElement).querySelector('.ablauf-leiste')).toBeNull();
  });

  it('lokale Blasen (Hinweis, Fehler) und die eigene Nachricht lassen die Leiste stehen', () => {
    const { f, c, store } = bauen();
    store.addBotMessage('Los.', false, [], undefined, { ablauf: STAND });
    store.addBotMessage('Bitte melde dich an.');            // lokal: ohne ui (Review AS-Ub, Befund 1)
    (c as unknown as { _store: { addUserMessage: (t: string) => void } })._store.addUserMessage('Hallo');
    f.detectChanges();
    expect(c.ablaufStand()).toEqual(STAND);
  });

  it('feste Texte tragen kein Etikett „KI-generiert“, andere schon', () => {
    const { f, store } = bauen();
    store.addBotMessage('Fester Text.', false, [], undefined, { fester_text: true });
    store.addBotMessage('Antwort der KI.', false, [], undefined, {});
    f.detectChanges();
    const blasen = [...(f.nativeElement as HTMLElement).querySelectorAll('.bot-bubble')];
    const mit = (b: Element) => b.querySelector('.ai-notice') !== null;
    const fest = blasen.find((b) => b.textContent?.includes('Fester Text.'))!;
    const ki = blasen.find((b) => b.textContent?.includes('Antwort der KI.'))!;
    expect(mit(fest)).toBe(false);
    expect(mit(ki)).toBe(true);
  });

  it('„Abbrechen“ schickt die Direktaktion', async () => {
    const { c } = bauen();
    const resp = { content: 'Wirklich?', session_id: 's', cards: [], quick_replies: [] } as unknown as ChatResponse;
    const api = (c as unknown as { _api: { stream: ReturnType<typeof vi.fn> } })._api;
    api.stream = vi.fn(async () => resp);
    c.onAblaufAbbrechen();
    await vi.waitFor(() => expect(api.stream).toHaveBeenCalled());
    const [, nachricht, , , aktion, params] = api.stream.mock.calls[0] as unknown[];
    expect(aktion).toBe('ablauf_abbrechen');
    expect(nachricht).toBe('Ablauf abbrechen');
    expect(params).toEqual({});                 // ohne Stand keine Marke
  });

  it('„Abbrechen“ schickt die Marke des angezeigten Laufs mit (Review 13.11.)', async () => {
    const { f, c, store } = bauen();
    store.addBotMessage('Los.', false, [], undefined, { ablauf: { ...STAND, lauf: 'ab12cd34' } });
    f.detectChanges();
    const resp = { content: 'Der Ablauf ist abgebrochen.', session_id: 's', cards: [], quick_replies: [] } as unknown as ChatResponse;
    const api = (c as unknown as { _api: { stream: ReturnType<typeof vi.fn> } })._api;
    api.stream = vi.fn(async () => resp);
    c.onAblaufAbbrechen();
    await vi.waitFor(() => expect(api.stream).toHaveBeenCalled());
    const [, , , , aktion, params] = api.stream.mock.calls[0] as unknown[];
    expect(aktion).toBe('ablauf_abbrechen');
    expect(params).toEqual({ lauf: 'ab12cd34' });
  });
});
