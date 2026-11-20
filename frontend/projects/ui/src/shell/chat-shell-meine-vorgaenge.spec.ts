import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ICONS } from '../icons/icons';
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

async function make(angemeldet = true, liste: EigenerVorgang[] = [V],
  vorbereiten?: (api: ReturnType<typeof fakeApi>) => void) {
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
  api.eigeneVorgaenge.mockImplementation(async () => liste);
  vorbereiten?.(api);
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
    expect(k.getAttribute('aria-label')).toMatch(/^Meine Vorgänge/);
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

/**
 * Paket D2 (Plan 2026-11-20, E-D2): eigenes Symbol, Zahl der offenen Vorgänge anderer Gespräche
 * (dieselbe Liste wie im Panel, im Hintergrund geholt) und eine Markierung, solange hier ein
 * Auftrag läuft — beides mit Text im Namen des Knopfs, nicht nur als Bild oder Farbe.
 */
describe('ChatShellComponent — Meine Vorgänge: Symbol, Zahl, Markierung (D2)', () => {
  const pfad = (svg: string) => svg.match(/ d="([^"]+)"/)![1];
  const vieleVorgaenge = (n: number): EigenerVorgang[] => Array.from({ length: n }, (_, i) => ({
    ...V, id: `0a1b2c3d-0000-4000-8000-${String(i + 1).padStart(12, '0')}`, titel: `V${i + 1}`,
  }));
  const zahl = (f: { nativeElement: HTMLElement }) =>
    f.nativeElement.querySelector('.btn-vorgaenge__zahl') as HTMLElement | null;

  beforeEach(() => sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY));
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
    TestBed.resetTestingModule();
  });

  it('eigenes Symbol — nicht der Kreispfeil des Neustarts', async () => {
    const { knopf } = await make();
    expect(pfad(ICONS.vorgaenge)).not.toBe(pfad(ICONS.refresh));
    expect(knopf()!.innerHTML).toContain(pfad(ICONS.vorgaenge));
    expect(knopf()!.innerHTML).not.toContain(pfad(ICONS.refresh));
  });

  it('holt die Liste beim Öffnen im Hintergrund und zeigt ihre Zahl — mit Text im Namen', async () => {
    const { f, api, knopf } = await make();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(1));
    f.detectChanges();
    await f.whenStable();
    expect(zahl(f)?.textContent?.trim()).toBe('1');
    expect(zahl(f)?.getAttribute('aria-hidden')).toBe('true');
    expect(knopf()!.getAttribute('aria-label')).toBe('Meine Vorgänge – 1 offen');
    expect(knopf()!.getAttribute('title')).toBe('Meine Vorgänge – 1 offen');
  });

  it('ab zehn „9+“ am Knopf, die genaue Zahl im Namen', async () => {
    const { f, knopf } = await make(true, vieleVorgaenge(12));
    await vi.waitFor(() => { f.detectChanges(); expect(zahl(f)).not.toBeNull(); });
    expect(zahl(f)!.textContent?.trim()).toBe('9+');
    expect(knopf()!.getAttribute('aria-label')).toBe('Meine Vorgänge – 12 offen');
  });

  it('ohne offene Vorgänge kein Abzeichen und der schlichte Name', async () => {
    const { f, api, knopf } = await make(true, []);
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalled());
    f.detectChanges();
    await f.whenStable();
    expect(zahl(f)).toBeNull();
    expect(knopf()!.getAttribute('aria-label')).toBe('Meine Vorgänge');
  });

  it('nach dem Öffnen des Panels fragt der Hintergrund nicht noch einmal (ein Abruf je Anlass)', async () => {
    const { f, api, knopf } = await make();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(1));
    knopf()!.click();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(2));   // das Panel lädt frisch
    f.detectChanges();
    await f.whenStable();
    expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(2);
  });

  it('markiert den Knopf, solange hier die Eingabe auf einen Auftrag wartet', async () => {
    const { f, c, knopf } = await make(true, []);
    expect(knopf()!.classList).not.toContain('btn-vorgaenge--hier');
    c.eingabeGesperrt.set(true);
    f.detectChanges();
    expect(knopf()!.classList).toContain('btn-vorgaenge--hier');
    expect(knopf()!.getAttribute('aria-label')).toBe('Meine Vorgänge – hier läuft ein Auftrag');
  });

  it('markiert ihn, wenn der Lauf dieses Gesprächs auf einen Auftrag wartet (Ablauf-Stand)', async () => {
    const { f, c, knopf } = await make(true, []);
    (c as any)._store.messages.update((m: unknown[]) => [...m, {
      id: 'b1', sender: 'bot', content: 'läuft', timestamp: new Date(),
      ui: { ablauf: { id: 'a', titel: 'A', nr: 1, von: 2, status: 'wartet_auftrag', teile: [] } },
    }]);
    f.detectChanges();
    expect(knopf()!.classList).toContain('btn-vorgaenge--hier');
  });
});

describe('ChatShellComponent — Meine Vorgänge, Review Paket D', () => {
  beforeEach(() => sessionStorage.removeItem(MCP_ACCESS_STORAGE_KEY));
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
    TestBed.resetTestingModule();
  });

  it('4: erst „Gespräch fortsetzen“, dann die Zahl — nacheinander, nicht zugleich', async () => {
    let freigeben: (v: never[]) => void = () => undefined;
    const { api } = await make(true, [V], (a) => a.offeneVorgaenge.mockImplementation(
      () => new Promise<never[]>((r) => { freigeben = r; })));
    await vi.waitFor(() => expect(api.offeneVorgaenge).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(api.eigeneVorgaenge, 'wartet auf die erste Antwort').not.toHaveBeenCalled();
    freigeben([]);
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(1));
  });

  it('5: nach dem Neustart wird die Zahl neu geholt — aus der zweiten Antwort', async () => {
    const { f, c, api, knopf } = await make();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(1));
    const alt = c.sessionId;
    api.eigeneVorgaenge.mockResolvedValueOnce([V, { ...V, id: '0a1b2c3d-0000-4000-8000-000000000002', titel: 'Zwei' }]);
    c.restart();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(2));
    expect(c.sessionId).not.toBe(alt);
    expect(api.eigeneVorgaenge).toHaveBeenLastCalledWith(c.sessionId);
    await vi.waitFor(() => {
      f.detectChanges();
      expect(knopf()!.getAttribute('aria-label')).toBe('Meine Vorgänge – 2 offen');
    });
  });

  it('5: „Fortsetzen“ in der Liste holt die Zahl für das neue Gespräch', async () => {
    const { c, api } = await make();
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenCalledTimes(1));
    await c.onVorgangFortsetzen(V);
    expect(c.sessionId).toBe(DORT);
    await vi.waitFor(() => expect(api.eigeneVorgaenge).toHaveBeenLastCalledWith(DORT));
  });
});
