import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UiBlock } from '@boerdi/ui-module';

import type { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Paket U2 (Plan 2026-11-04, T-10; Review U2 Frontend, Befund 5 und 11): eine getippte Nachricht
 * nimmt den vorgemerkten Stand eines offenen Strukturentwurfs mit — Eingabefeld und Schnellantwort
 * ja, Karten- und Direktaktionen sowie Aufträge des Gastgebers nicht. Kam der Zug nicht an, ist der
 * Entwurf wieder offen.
 */
const DE_T = createTranslator(DE, DE);

const ENTWURF: UiBlock = {
  block_id: 'e0000001', modul: 'ui_strukturentwurf', version: 1, art: 'abfragen', status: 'offen',
  daten: { titel: 'Optik', quelle: 'ki', knoten: [{ id: 'k1', titel: 'Licht' }, { id: 'k2', titel: 'Farben' }] },
  text: 'Entwurf',
};
const ANTWORT = { session_id: 's', content: 'Gut.', cards: [], quick_replies: [], ui: {} } as never;

async function make() {
  TestBed.configureTestingModule({ imports: [ChatShellComponent], providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(ChatShellComponent);
  const c = f.componentInstance;
  f.componentRef.setInput('translate', DE_T);
  f.detectChanges();
  const s = (c as unknown as { _store: { set: (m: ChatMessage[]) => void; addBotMessage: (...a: unknown[]) => string } })._store;
  s.set([]);
  s.addBotMessage('Hier ist ein Entwurf.', false, [], undefined, { ui_bloecke: [ENTWURF] });
  f.detectChanges();
  await f.whenStable();                                     // das Modul merkt seinen Stand vor
  const api = (c as unknown as { _api: { stream: unknown; post: unknown } })._api;
  const stream = vi.fn(async () => ANTWORT);
  api.stream = stream;
  return { c, f, api, stream };
}

const status = (c: ChatShellComponent) =>
  c.messages().flatMap((m) => m.ui?.ui_bloecke ?? []).map((b) => b.status);
const uiAntwort = (stream: ReturnType<typeof vi.fn>) => (stream.mock.calls[0] as unknown[])[6] as
  { block_id: string; daten: Record<string, unknown> } | undefined;

describe('ChatShellComponent — Strukturentwurf nimmt getippte Nachrichten mit (U2)', () => {
  beforeEach(() => TestBed.resetTestingModule());

  it('Eingabefeld: der Stand geht als ui_antwort mit, der Block ist beantwortet', async () => {
    const { c, stream } = await make();
    c.userInput.set('Bitte vertiefen');
    void c.sendMessage();
    expect(uiAntwort(stream)?.block_id).toBe('e0000001');
    expect(uiAntwort(stream)?.daten).toMatchObject({ uebernommen: false, bearbeitet: false });
    expect(status(c)).toEqual(['beantwortet']);
  });

  it('Schnellantwort (Text): ebenso', async () => {
    const { c, stream } = await make();
    void c.sendMessage('Passt so');
    expect(uiAntwort(stream)?.block_id).toBe('e0000001');
  });

  it('Karten- und Direktaktion: nichts geht mit, der Entwurf veraltet', async () => {
    const { c, stream } = await make();
    void c.sendMessage('Inhalte', 'browse_collection', { collection_id: 'x' });
    expect(uiAntwort(stream)).toBeUndefined();
    expect(status(c)).toEqual(['veraltet']);
  });

  it('Befund 5: ein Auftrag des Gastgebers nimmt den Entwurf nicht mit', async () => {
    const { c, stream } = await make();
    void c.startTask('Fasse die Seite zusammen');
    expect(stream).toHaveBeenCalledTimes(1);
    expect(uiAntwort(stream)).toBeUndefined();
  });

  it('kam der Zug nicht an, ist der Entwurf wieder offen', async () => {
    const { c, f, api } = await make();
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    api.stream = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));
    api.post = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));
    void c.sendMessage('Bitte vertiefen');
    expect(status(c)).toEqual(['beantwortet']);
    await vi.waitFor(() => expect(c.isLoading()).toBe(false));
    await f.whenStable();
    expect(status(c)).toEqual(['offen']);
  });
});
