import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';
import type { OffenerVorgang } from './fortsetzen';

/**
 * Paket K2a in der Hülle: ein angemeldetes Widget fragt nach wartenden Vorgängen in anderen
 * Gesprächen, zeigt den Hinweis, wechselt auf Klick und fragt bei einem wartenden Auftrag gleich
 * „Stand prüfen“; ohne Anmeldung fragt es nicht, nach dem Abmelden ist der Hinweis weg.
 */

const DORT = 'bb-87654321-4321-4321-8321-cba987654321';
const VORGANG: OffenerVorgang = {
  titel: 'Lesen', ablauf: 'lesen', status: 'wartet_auftrag', session_id: DORT,
  geaendert: '2026-11-07T09:30:00Z',
};

function fakeApi(liste: OffenerVorgang[] = [VORGANG]) {
  return {
    offeneVorgaenge: vi.fn(async () => liste),
    loadHistory: vi.fn(async () => []),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false), warteAufAnmeldung: vi.fn(),
  };
}

function make() {
  const f = TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  }).createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  const c = f.componentInstance;
  c.sessionId = 'bb-12345678-1234-4123-8123-123456789abc';
  return { f, c };
}

async function ruhe(): Promise<void> {
  TestBed.tick();
  await new Promise((r) => setTimeout(r, 0));
}

describe('ChatShellComponent — Gespräch fortsetzen (K2a)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('fragt nur mit Anmeldung und zeigt dann den Hinweis', async () => {
    const { f, c } = make();
    const api = fakeApi();
    (c as any)._api = api;
    (c as any)._hasAccessBlock.set(false);
    await ruhe();
    expect(api.offeneVorgaenge).not.toHaveBeenCalled();
    f.detectChanges();
    // Review K2a, Befund 5: die Live-Region steht schon leer im DOM, nur ihr Inhalt kommt dazu.
    const ort = f.nativeElement.querySelector('.fortsetzen-ort') as HTMLElement;
    expect(ort.getAttribute('role')).toBe('status');
    expect(ort.querySelector('.fortsetzen-hinweis')).toBeNull();
    (c as any)._hasAccessBlock.set(true);
    await ruhe();
    expect(api.offeneVorgaenge).toHaveBeenCalledWith(c.sessionId);
    f.detectChanges();
    const hinweis = ort.querySelector('.fortsetzen-hinweis') as HTMLElement;
    expect(hinweis.textContent).toContain('„Lesen“');
  });

  it('Fortsetzen wechselt das Gespräch und fragt beim wartenden Auftrag nach dem Stand', async () => {
    const { c } = make();
    const api = fakeApi();
    (c as any)._api = api;
    const senden = vi.spyOn(c, 'sendMessage').mockImplementation(async () => undefined);
    c.fortsetzen.angebot.set(VORGANG);
    await c.onFortsetzen();
    expect(c.sessionId).toBe(DORT);
    expect(api.loadHistory).toHaveBeenCalledWith(DORT, 20);
    expect(senden).toHaveBeenCalledWith(DE['fortsetzen.pruefen'], 'ablauf_auftrag_pruefen', { ablauf: 'lesen' });
    expect(c.fortsetzen.angebot()).toBeNull();
  });

  it('wartet die Person selbst, wird nur gewechselt', async () => {
    const { c } = make();
    (c as any)._api = fakeApi();
    const senden = vi.spyOn(c, 'sendMessage').mockImplementation(async () => undefined);
    c.fortsetzen.angebot.set({ ...VORGANG, status: 'wartet_person' });
    await c.onFortsetzen();
    expect(c.sessionId).toBe(DORT);
    expect(senden).not.toHaveBeenCalled();
  });

  it('Schließen und eine abgewiesene Anmeldung nehmen den Hinweis weg', async () => {
    const { f, c } = make();
    (c as any)._api = fakeApi();
    c.fortsetzen.angebot.set(VORGANG);
    f.detectChanges();
    (f.nativeElement.querySelector('.fortsetzen-hinweis__zu') as HTMLButtonElement).click();
    f.detectChanges();
    expect(f.nativeElement.querySelector('.fortsetzen-hinweis')).toBeNull();
    c.fortsetzen.angebot.set(VORGANG);
    (c as any)._anmeldungAbgewiesen();
    expect(c.fortsetzen.angebot()).toBeNull();
  });

  it('fragt nicht, solange ein Zug läuft', async () => {
    const { c } = make();
    const api = fakeApi();
    (c as any)._api = api;
    c.isLoading.set(true);
    (c as any)._hasAccessBlock.set(true);
    await ruhe();
    expect(api.offeneVorgaenge).not.toHaveBeenCalled();
    c.isLoading.set(false);
    await ruhe();
    expect(api.offeneVorgaenge).toHaveBeenCalledTimes(1);
  });

  // Review K2a, Befund 2/8: ein neues Gespräch (oder ein neuer Block) fragt neu, das alte Angebot geht.
  it('ein Neustart verwirft das Angebot und fragt für das neue Gespräch', async () => {
    const { c } = make();
    const api = fakeApi();
    (c as any)._api = api;
    (c as any)._hasAccessBlock.set(true);
    await ruhe();
    expect(api.offeneVorgaenge).toHaveBeenCalledTimes(1);
    api.offeneVorgaenge.mockResolvedValueOnce([]);
    c.restart();
    expect(c.fortsetzen.angebot()).toBeNull();
    await ruhe();
    expect(api.offeneVorgaenge).toHaveBeenCalledTimes(2);
    expect(api.offeneVorgaenge).toHaveBeenLastCalledWith(c.sessionId);
  });
});
