import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { MCP_ACCESS_STORAGE_KEY } from '../session/mcp-access';
import { ChatShellComponent } from './chat-shell.component';
import type { EigenerVorgang } from './meine-vorgaenge';

/**
 * AS-Ud in der Hülle (Plan 2026-11-09 §5j, Ud-4): der Knopf „Meine Vorgänge“ steht nur bei einer
 * Anmeldung neben dem Anmelde-Knopf, klappt die Liste auf (`aria-expanded`, `aria-controls`),
 * „Fortsetzen“ wechselt das Gespräch wie der Hinweis, Schließen gibt den Fokus an den Knopf zurück,
 * und Abmelden vergisst die Liste.
 */
const HIER = 'bb-12345678-1234-4123-8123-123456789abc';
const DORT = 'bb-87654321-4321-4321-8321-cba987654321';
const V: EigenerVorgang = {
  id: '0a1b2c3d-0000-4000-8000-000000000001', titel: 'Lesen', ablauf: 'lesen',
  status: 'wartet_person', session_id: DORT, geaendert: '2026-11-07T09:30:00Z',
};

function fakeApi() {
  return {
    offeneVorgaenge: vi.fn(async () => []),
    eigeneVorgaenge: vi.fn(async () => [V]),
    vorgangLoeschen: vi.fn(async () => undefined),
    loadHistory: vi.fn(async () => []),
    setResultSchema: vi.fn(), setUiLocale: vi.fn(), setUiModule: vi.fn(), setGuideEnv: vi.fn(),
    setBaseUrl: vi.fn(), getSpeechEnabled: vi.fn(async () => false), warteAufAnmeldung: vi.fn(),
  };
}

async function make(angemeldet = true) {
  const f = TestBed.configureTestingModule({
    imports: [ChatShellComponent],
    providers: [provideZonelessChangeDetection()],
  }).createComponent(ChatShellComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('persistSession', false);
  f.componentRef.setInput('mcpAuthBase', 'https://mcp.example');
  const c = f.componentInstance;
  c.sessionId = HIER;
  const api = fakeApi();
  (c as any)._api = api;
  (c as any)._hasAccessBlock.set(angemeldet);
  f.detectChanges();
  await f.whenStable();
  document.body.appendChild(f.nativeElement);
  const knopf = () => f.nativeElement.querySelector('.btn-vorgaenge') as HTMLButtonElement | null;
  return { f, c, api, knopf };
}

describe('ChatShellComponent — Meine Vorgänge (AS-Ud)', () => {
  beforeEach(() => sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY));
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY);
    document.body.innerHTML = '';
    TestBed.resetTestingModule();
  });

  it('ohne Anmeldung kein Knopf', async () => {
    const { knopf } = await make(false);
    expect(knopf()).toBeNull();
  });

  it('der Knopf klappt die Liste auf und zu und sagt seinen Zustand', async () => {
    const { f, c, api, knopf } = await make();
    const k = knopf()!;
    expect(k.getAttribute('aria-label')).toBe('Meine Vorgänge');
    expect(k.getAttribute('aria-expanded')).toBe('false');
    k.click();
    // das aktuelle Gespräch (der Start legt bei persistSession=false ein neues an)
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledWith(c.sessionId));
    f.detectChanges();
    await f.whenStable();
    expect(k.getAttribute('aria-expanded')).toBe('true');
    const panel = f.nativeElement.querySelector('boerdi-meine-vorgaenge section') as HTMLElement;
    expect(k.getAttribute('aria-controls')).toBe(panel.id);
    expect(panel.textContent).toContain('Lesen');
    k.click();
    f.detectChanges();
    await f.whenStable();
    expect(f.nativeElement.querySelector('boerdi-meine-vorgaenge')).toBeNull();
  });

  it('Schließen im Panel gibt den Fokus an den Knopf zurück', async () => {
    const { f, knopf } = await make();
    knopf()!.click();
    f.detectChanges();
    await f.whenStable();
    (f.nativeElement.querySelector('.meine-vorgaenge__zu') as HTMLButtonElement).click();
    f.detectChanges();
    await f.whenStable();
    expect(f.nativeElement.querySelector('boerdi-meine-vorgaenge')).toBeNull();
    expect(document.activeElement).toBe(knopf());
  });

  it('„Fortsetzen“ schließt die Liste und wechselt auf das Gespräch des Vorgangs', async () => {
    const { f, c, api, knopf } = await make();
    knopf()!.click();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalled());
    f.detectChanges();
    await f.whenStable();
    (f.nativeElement.querySelector('.meine-vorgaenge__los') as HTMLButtonElement).click();
    await vi.waitFor(() => expect(c.sessionId).toBe(DORT));
    expect(api.loadHistory).toHaveBeenCalledWith(DORT, 20);
    expect(c.meineVorgaenge.offen()).toBe(false);
  });

  it('Abmelden vergisst die Liste', async () => {
    const { f, c, knopf } = await make();
    knopf()!.click();
    await vi.waitFor(() => expect(c.meineVorgaenge.liste()).toHaveLength(1));
    (c as any)._anmeldungAbgewiesen();
    f.detectChanges();
    expect([c.meineVorgaenge.offen(), c.meineVorgaenge.liste()]).toEqual([false, []]);
    expect(knopf()).toBeNull();
  });
});

describe('ChatShellComponent — Meine Vorgänge, Review AS-Ud', () => {
  beforeEach(() => sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY));
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
    TestBed.resetTestingModule();
  });

  it('Befund 1: ein Wechsel über den Hinweis „Gespräch fortsetzen“ vergisst die alte Liste', async () => {
    const { c, knopf } = await make();
    knopf()!.click();
    await vi.waitFor(() => expect(c.meineVorgaenge.liste()).toHaveLength(1));
    vi.spyOn(c, 'sendMessage').mockImplementation(async () => undefined);
    c.fortsetzen.angebot.set({ titel: 'X', ablauf: null, status: 'wartet_person', session_id: DORT,
      geaendert: '2026-11-07T09:30:00Z' });
    await c.onFortsetzen();
    expect(c.sessionId).toBe(DORT);
    expect([c.meineVorgaenge.offen(), c.meineVorgaenge.liste()]).toEqual([false, []]);
  });

  it('Befund 7: Löschen verwirft einen Hinweis „Gespräch fortsetzen“ auf genau diesen Vorgang', async () => {
    const { c, knopf } = await make();
    knopf()!.click();
    await vi.waitFor(() => expect(c.meineVorgaenge.liste()).toHaveLength(1));
    c.fortsetzen.angebot.set({ titel: 'Lesen', ablauf: 'lesen', status: 'wartet_person',
      session_id: DORT, geaendert: '2026-11-07T09:30:00Z' });
    expect(await c.meineVorgaenge.loeschen(V.id)).toBe(true);
    expect(c.fortsetzen.angebot()).toBeNull();
  });

  it('Befund 7: „Fortsetzen“ eines wartenden Auftrags fragt danach gleich „Stand prüfen“', async () => {
    const { c } = await make();
    const senden = vi.spyOn(c, 'sendMessage').mockImplementation(async () => undefined);
    await c.onVorgangFortsetzen({ ...V, status: 'wartet_auftrag' });
    expect(c.sessionId).toBe(DORT);
    expect(senden).toHaveBeenCalledWith(DE['fortsetzen.pruefen'], 'ablauf_auftrag_pruefen', { ablauf: 'lesen' });
  });
});
