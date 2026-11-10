import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AblaufStand, ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { MCP_ACCESS_STORAGE_KEY } from '../session/mcp-access';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Zweites Review nach dem Querschnitt (Plan 2026-11-09 §5l):
 * - Z-1: der Verweis eines Laufs gehört der angemeldeten Person — ein Verlauf, der vor der
 *   Anmeldung (neuer Tab, Ticket-Tausch) geholt wurde, kennt ihn nicht. Nach gelungener Anmeldung
 *   holt die Shell den Stand einmal nach; er gilt, bis eine neue Serverantwort kommt.
 * - Z-8: abgemeldet ist die Leiste eines persönlichen Laufs weg (ihr Abbruch liefe anonym ins Leere).
 */
const STAND: AblaufStand = {
  id: 'lesen', titel: 'Lesen', nr: 2, von: 4, status: 'wartet_freigabe', lauf: 'a1', persoenlich: true, teile: [],
};

function make() {
  TestBed.configureTestingModule({ imports: [ChatShellComponent], providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(ChatShellComponent);
  const c = f.componentInstance;
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('persistSession', false);
  const fetchHistory = vi.fn(async () => [
    { role: 'user', content: 'los' },
    { role: 'assistant', content: 'Weiter?', ui: { ablauf: STAND } },
  ]);
  (c as any)._api = {
    fetchHistory, offeneVorgaenge: vi.fn(async () => []), loadHistory: vi.fn(async () => []),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false), warteAufAnmeldung: vi.fn(),
  };
  f.detectChanges();
  const store = (c as unknown as { _store: { set: (m: ChatMessage[]) => void;
    addBotMessage: (...a: unknown[]) => string } })._store;
  return { c, fetchHistory, store };
}

describe('ChatShellComponent — Stand nach der Anmeldung (Z-1) und nach dem Abmelden (Z-8)', () => {
  beforeEach(() => sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY));
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY);
    TestBed.resetTestingModule();
  });

  it('Z-1: nach der Anmeldung holt die Shell den Stand nach und zeigt die Leiste', async () => {
    const { c, fetchHistory } = make();
    (c as any)._hasAccessBlock.set(true);
    expect(c.ablaufStand()).toBeNull();
    await (c as any)._standNachladen();
    expect(fetchHistory).toHaveBeenCalledWith(c.sessionId, 5);
    expect(c.ablaufStand()).toEqual(STAND);
  });

  it('Z-1: eine neue Serverantwort gilt vor dem nachgeladenen Stand', async () => {
    const { c, store } = make();
    (c as any)._hasAccessBlock.set(true);
    await (c as any)._standNachladen();
    store.addBotMessage('Fertig.', false, [], undefined, { pattern: 'ABLAUF' });
    expect(c.ablaufStand()).toBeNull();
  });

  it('Z-1: ein Wechsel des Gesprächs vergisst den nachgeladenen Stand', async () => {
    const { c } = make();
    (c as any)._hasAccessBlock.set(true);
    await (c as any)._standNachladen();
    (c as any)._fortsetzenNeu();
    expect(c.ablaufStand()).toBeNull();
  });

  it('Z-8: abgemeldet keine Leiste für einen persönlichen Lauf; ein Lauf der Sitzung bleibt', () => {
    const { c, store } = make();
    (c as any)._hasAccessBlock.set(true);
    store.addBotMessage('Weiter?', false, [], undefined, { ablauf: STAND });
    expect(c.ablaufStand()).toEqual(STAND);
    (c as any)._hasAccessBlock.set(false);
    expect(c.ablaufStand()).toBeNull();
    store.addBotMessage('Weiter?', false, [], undefined, { ablauf: { ...STAND, persoenlich: false } });
    expect(c.ablaufStand()?.persoenlich).toBe(false);
  });
});
