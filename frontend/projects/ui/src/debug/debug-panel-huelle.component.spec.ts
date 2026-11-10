import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

// Im Widget lädt das Element sein eigenes Bündel; hier ist es vorab definiert.
import '../nachgeladen/ui-debug-panel/ui-debug-panel.element';
import type { DebugInfo, UiInfo } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { DebugPanelHuelleComponent } from './debug-panel-huelle.component';

/**
 * Paket BU-3: die Hülle des nachgeladenen Debug-Panels in der Shell — lädt das Bündel erst, wenn das
 * Panel zu sehen sein soll (Schalter an und etwas zu zeigen), reicht dann bei jeder Änderung
 * Debug-Block, `ui`, Schalter und Übersetzer weiter und sagt es in einem Satz, wenn das Laden scheitert.
 */
const DEBUG = {
  persona: 'p', intent: 'i', state: 's', turn_type: 'normal', signals: [], pattern: 'M06', entities: {},
  tools_called: [], phase1_eliminated: [], phase2_scores: {}, phase3_modulations: {},
} as unknown as DebugInfo;

async function make(lader: (modul: string) => Promise<void>) {
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(DebugPanelHuelleComponent);
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('nachladen', lader);
  f.componentRef.setInput('debug', null);
  f.componentRef.setInput('ui', null);
  f.componentRef.setInput('show', false);
  f.detectChanges();
  await f.whenStable();
  const panel = () => (f.nativeElement as HTMLElement).querySelector('boerdi-ui-debug-panel')
    ?.shadowRoot?.querySelector('.debug-panel') ?? null;
  return { f, panel };
}

afterEach(() => TestBed.resetTestingModule());

describe('DebugPanelHuelleComponent', () => {
  it('lädt nichts, solange der Schalter aus ist oder nichts zu zeigen ist', async () => {
    const lader = vi.fn(async () => undefined);
    const { f } = await make(lader);
    f.componentRef.setInput('debug', DEBUG);
    await f.whenStable();
    f.componentRef.setInput('debug', null);
    f.componentRef.setInput('show', true);
    await f.whenStable();
    expect(lader).not.toHaveBeenCalled();
  });

  it('Schalter an mit Debug-Block: lädt einmal das Bündel und zeigt das Panel; Änderungen kommen an', async () => {
    const lader = vi.fn(async () => undefined);
    const { f, panel } = await make(lader);
    f.componentRef.setInput('debug', DEBUG);
    f.componentRef.setInput('show', true);
    await vi.waitFor(() => expect(panel()).not.toBeNull());
    expect(lader).toHaveBeenCalledWith('ui_debug_panel');
    expect(panel()!.textContent).toContain('M06');
    f.componentRef.setInput('debug', { ...DEBUG, pattern: 'M09' } as DebugInfo);
    await f.whenStable();
    expect(panel()!.textContent).toContain('M09');
    f.componentRef.setInput('show', false);
    await f.whenStable();
    expect(panel()).toBeNull();
    f.componentRef.setInput('show', true);
    await f.whenStable();
    expect(lader).toHaveBeenCalledTimes(1);
  });

  it('ohne Debug-Block, aber mit ui: die Zusammenfassung, übersetzt', async () => {
    const { f, panel } = await make(async () => undefined);
    f.componentRef.setInput('ui', { pattern: 'M05', tools_called: [] } as UiInfo);
    f.componentRef.setInput('show', true);
    await vi.waitFor(() => expect(panel()).not.toBeNull());
    expect(panel()!.textContent).toContain(DE['debug.onlyInStudio']);
  });

  it('scheitert das Laden, steht ein Satz statt des Panels', async () => {
    const { f } = await make(async () => { throw new Error('netz'); });
    f.componentRef.setInput('debug', DEBUG);
    f.componentRef.setInput('show', true);
    await vi.waitFor(() =>
      expect((f.nativeElement as HTMLElement).textContent).toContain(DE['debug.ladeFehler']));
  });
});

describe('DebugPanelHuelleComponent — Review BU-3', () => {
  it('Befund 3: nach einem Fehler versucht Aus und wieder An es erneut', async () => {
    let mal = 0;
    const lader = vi.fn(async () => { if (++mal === 1) throw new Error('netz'); });
    const { f, panel } = await make(lader);
    f.componentRef.setInput('debug', DEBUG);
    f.componentRef.setInput('show', true);
    await vi.waitFor(() => expect((f.nativeElement as HTMLElement).textContent).toContain(DE['debug.ladeFehler']));
    f.componentRef.setInput('show', false);
    await f.whenStable();
    f.componentRef.setInput('show', true);
    await vi.waitFor(() => expect(panel()).not.toBeNull());
    expect(lader).toHaveBeenCalledTimes(2);
  });

  it('Befund 5: Laden und Fehler sagt eine ständige Statuszeile an', async () => {
    let fertig: () => void = () => undefined;
    const lader = vi.fn(() => new Promise<void>((_ok, nein) => { fertig = () => nein(new Error('netz')); }));
    const { f } = await make(lader);
    const zeile = () => (f.nativeElement as HTMLElement).querySelector('[role="status"]');
    expect(zeile()).not.toBeNull();                          // schon vor dem Laden im DOM
    f.componentRef.setInput('debug', DEBUG);
    f.componentRef.setInput('show', true);
    await f.whenStable();
    expect(zeile()!.textContent?.trim()).toBe(DE['debug.laedt']);
    fertig();
    await vi.waitFor(() => { f.detectChanges(); expect(zeile()!.textContent?.trim()).toBe(DE['debug.ladeFehler']); });
  });

  it('Befund 7: ohne Lader kein Versuch und keine Anzeige', async () => {
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const f = TestBed.createComponent(DebugPanelHuelleComponent);
    f.componentRef.setInput('translate', createTranslator(DE, DE));
    f.componentRef.setInput('debug', DEBUG);
    f.componentRef.setInput('show', true);
    f.detectChanges();
    await f.whenStable();
    expect((f.nativeElement as HTMLElement).querySelector('boerdi-ui-debug-panel')).toBeNull();
    expect((f.nativeElement as HTMLElement).textContent?.trim()).toBe('');
  });
});
