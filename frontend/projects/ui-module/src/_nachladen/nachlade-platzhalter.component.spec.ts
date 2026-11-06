// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, type ModulHost } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import { NACHLADE_ZIEL, type NachladeElement, type NachladeZiel } from './element-vertrag';
import { NachladePlatzhalter } from './nachlade-platzhalter.component';

/** Ein Probe-Element, wie es ein nachgeladenes Bündel definieren würde. */
class ProbeElement extends HTMLElement implements NachladeElement {
  daten: Record<string, unknown> = {};
  kontext!: ModulKontext;
  host!: NachladeElement['host'];
  beschaeftigt = false;
}

/** Zählt Zuweisungen und liest beim „Zeichnen“ ein fremdes Signal — wie ein Element, das über die
 *  Host-Brücke `link()` aufruft (dahinter Signale der Shell). */
const FREMD = signal(0);
class ZaehlElement extends HTMLElement {
  hostSetzungen = 0;
  datenSetzungen = 0;
  kontext!: ModulKontext;
  beschaeftigt = false;
  private _host!: NachladeElement['host'];
  set host(h: NachladeElement['host']) { this.hostSetzungen++; this._host = h; }
  get host(): NachladeElement['host'] { return this._host; }
  set daten(_d: Record<string, unknown>) { this.datenSetzungen++; FREMD(); }
  get daten(): Record<string, unknown> { return {}; }
}

beforeAll(() => {
  if (!customElements.get('boerdi-ui-probe')) customElements.define('boerdi-ui-probe', ProbeElement);
  if (!customElements.get('boerdi-ui-zaehl')) customElements.define('boerdi-ui-zaehl', ZaehlElement);
});

function host(): ModulHost {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), link: vi.fn(), aktion: vi.fn(), antworten: vi.fn(),
    vormerken: vi.fn(), zweig: vi.fn(), treffer: vi.fn(), beschaeftigt: vi.fn(() => false),
    markdown: vi.fn((text: string) => `<p>${text}</p>`),
  } as unknown as ModulHost;
}

const KONTEXT: ModulKontext = {
  blockId: 'b1', sprache: 'de', nurLesen: false, antwort: null, schriftSkala: 0.85, anzeigeRegeln: null,
};

async function render(ziel: NachladeZiel, h: ModulHost = host()) {
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      { provide: MODUL_HOST, useValue: h },
      { provide: NACHLADE_ZIEL, useValue: ziel },
    ],
  });
  const f = TestBed.createComponent(NachladePlatzhalter);
  f.componentRef.setInput('daten', { titel: 'Probe' });
  f.componentRef.setInput('kontext', KONTEXT);
  await f.whenStable();
  return f;
}

afterEach(() => TestBed.resetTestingModule());

describe('NachladePlatzhalter (U3-0)', () => {
  it('zeigt „Wird geladen“ mit aria-busy, solange das Bündel lädt', async () => {
    const f = await render({ element: 'boerdi-ui-probe', text: 'Textfassung', laden: () => new Promise(() => {}) });
    const el = f.nativeElement as HTMLElement;
    const lade = el.querySelector('[aria-busy="true"]');
    expect(lade?.textContent).toContain('Wird geladen');
    expect(el.querySelector('boerdi-ui-probe')).toBeNull();
  });

  it('erzeugt nach dem Laden das Element und setzt Daten, Kontext und Host-Brücke', async () => {
    const h = host();
    const f = await render({ element: 'boerdi-ui-probe', text: 'Textfassung', laden: async () => {} }, h);
    await f.whenStable();
    const el = (f.nativeElement as HTMLElement).querySelector('boerdi-ui-probe') as ProbeElement;
    expect(el).toBeTruthy();
    expect(el.daten).toEqual({ titel: 'Probe' });
    expect(el.kontext.blockId).toBe('b1');
    el.host.antworten({ x: 1 }, 'ok');
    expect(h.antworten).toHaveBeenCalledWith({ x: 1 }, 'ok');
    expect((f.nativeElement as HTMLElement).querySelector('[aria-busy="true"]')).toBeNull();
  });

  it('gibt neue Daten und neuen Kontext an dasselbe Element weiter (kein Neuaufbau)', async () => {
    const f = await render({ element: 'boerdi-ui-probe', text: 'T', laden: async () => {} });
    await f.whenStable();
    const vorher = (f.nativeElement as HTMLElement).querySelector('boerdi-ui-probe') as ProbeElement;
    f.componentRef.setInput('daten', { titel: 'Neu' });
    f.componentRef.setInput('kontext', { ...KONTEXT, nurLesen: true });
    await f.whenStable();
    const nachher = (f.nativeElement as HTMLElement).querySelector('boerdi-ui-probe') as ProbeElement;
    expect(nachher).toBe(vorher);
    expect(nachher.daten).toEqual({ titel: 'Neu' });
    expect(nachher.kontext.nurLesen).toBe(true);
  });

  it('setzt beschaeftigt aus dem Host und den Host nur einmal', async () => {
    const h = host();
    (h.beschaeftigt as ReturnType<typeof vi.fn>).mockReturnValue(true);
    const f = await render({ element: 'boerdi-ui-zaehl', text: 'T', laden: async () => {} }, h);
    await f.whenStable();
    f.componentRef.setInput('daten', { neu: 1 });
    await f.whenStable();
    const el = (f.nativeElement as HTMLElement).querySelector('boerdi-ui-zaehl') as ZaehlElement;
    expect(el.beschaeftigt).toBe(true);
    expect(el.hostSetzungen).toBe(1);
    expect(el.datenSetzungen).toBe(2);
  });

  it('Signale, die das Element beim Zeichnen liest, lösen keine neue Zuweisung aus', async () => {
    const f = await render({ element: 'boerdi-ui-zaehl', text: 'T', laden: async () => {} });
    await f.whenStable();
    const el = (f.nativeElement as HTMLElement).querySelector('boerdi-ui-zaehl') as ZaehlElement;
    const vorher = el.datenSetzungen;
    FREMD.update((n) => n + 1);
    await f.whenStable();
    expect(el.datenSetzungen).toBe(vorher);
  });

  it('zeigt die Textfassung, wenn das Laden scheitert', async () => {
    const f = await render({ element: 'boerdi-ui-probe', text: 'Bitte neu laden', laden: () => Promise.reject(new Error('SRI')) });
    await f.whenStable();
    const el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Bitte neu laden');
    expect(el.querySelector('boerdi-ui-probe')).toBeNull();
    expect(el.querySelector('[aria-busy="true"]')).toBeNull();
  });

  it('zeigt die Textfassung, wenn nach dem Laden kein Element definiert ist', async () => {
    const f = await render({ element: 'boerdi-ui-fehlt', text: 'Rueckfall', laden: async () => {} });
    await f.whenStable();
    expect((f.nativeElement as HTMLElement).textContent).toContain('Rueckfall');
  });

  it('spricht Englisch, wenn der Kontext es sagt', async () => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), { provide: MODUL_HOST, useValue: host() },
        { provide: NACHLADE_ZIEL, useValue: { element: 'boerdi-ui-probe', text: 'T', laden: () => new Promise(() => {}) } }],
    });
    const f = TestBed.createComponent(NachladePlatzhalter);
    f.componentRef.setInput('daten', {});
    f.componentRef.setInput('kontext', { ...KONTEXT, sprache: 'en' });
    await f.whenStable();
    expect((f.nativeElement as HTMLElement).textContent).toContain('Loading');
  });
});
