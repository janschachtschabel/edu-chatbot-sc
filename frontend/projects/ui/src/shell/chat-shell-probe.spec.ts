import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatShellComponent } from './chat-shell.component';

/**
 * Paket AS-8b (Plan 2026-11-09 §5n, P-10): in der Probe der Studio-Vorschau sagt die Hülle sichtbar,
 * dass nichts geschrieben wird, und führt nie in echte Vorgänge („Meine Vorgänge“, „Gespräch
 * fortsetzen“ — das Backend antwortete dort ohnehin 409 `trockenlauf`).
 */
function fakeApi() {
  return {
    offeneVorgaenge: vi.fn(async () => []),
    eigeneVorgaenge: vi.fn(async () => []),
    vorgangLoeschen: vi.fn(async () => undefined),
    loadHistory: vi.fn(async () => []),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false), warteAufAnmeldung: vi.fn(),
    setProbe: vi.fn(),
  };
}

async function make(probe: boolean) {
  const f = TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  }).createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('persistSession', false);
  f.componentRef.setInput('mcpAuthBase', 'https://mcp.example');
  const c = f.componentInstance;
  const api = fakeApi();
  (c as any)._api = api;
  c.setProbe(probe);
  (c as any)._hasAccessBlock.set(true);           // angemeldet
  f.detectChanges();
  await f.whenStable();
  const el = f.nativeElement as HTMLElement;
  return { f, c, api, el };
}

describe('ChatShellComponent — Probe der Studio-Vorschau (AS-8b)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('zeigt das Etikett und reicht die Probe an den Client', async () => {
    const { el, api } = await make(true);
    const etikett = el.querySelector('.probe-etikett');
    expect(etikett?.textContent?.trim()).toBe(DE['chat.probe']);
    expect(etikett?.getAttribute('role')).toBe('note');
    expect(api.setProbe).toHaveBeenCalledWith(true);
  });

  it('ohne „Meine Vorgänge“ und ohne Frage nach offenen Vorgängen', async () => {
    const { el, api } = await make(true);
    expect(el.querySelector('.btn-vorgaenge')).toBeNull();
    expect(api.offeneVorgaenge).not.toHaveBeenCalled();
  });

  it('ohne Probe kein Etikett, und der Knopf steht wie bisher', async () => {
    const { el } = await make(false);
    expect(el.querySelector('.probe-etikett')).toBeNull();
    expect(el.querySelector('.btn-vorgaenge')).not.toBeNull();
  });
});
