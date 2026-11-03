// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { ModulNutzung } from '../core/eval-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalModulNutzungComponent } from './eval-modul-nutzung.component';

/** Paket U1-g (G-6): je Muster und je Anwendungsfall, welches Modul in wie vielen Zügen. */
const NUTZUNG: ModulNutzung = {
  zuege: 5, erfasst: 4,
  module: ['ui_entscheidung', 'ui_themenbaum'],
  je_muster: {
    AGENT: { zuege: 3, module: { ui_entscheidung: 1, ui_themenbaum: 2 } },
    M04: { zuege: 1, module: {} },
  },
  je_anwendungsfall: { orientieren: { zuege: 2, module: { ui_themenbaum: 2 } } },
};

let f: ComponentFixture<EvalModulNutzungComponent>;

async function mount(n: ModulNutzung = NUTZUNG, locale = 'de'): Promise<HTMLElement> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  f = TestBed.createComponent(EvalModulNutzungComponent);
  f.componentRef.setInput('nutzung', n);
  await f.whenStable();
  return f.nativeElement as HTMLElement;
}

const zeilen = (el: HTMLElement, i: number): string[][] =>
  Array.from(el.querySelectorAll('table')[i].querySelectorAll('tbody tr')).map((tr) =>
    Array.from(tr.children).map((c) => (c.textContent ?? '').trim()));

describe('EvalModulNutzungComponent (Paket U1-g)', () => {
  it('zeigt je Muster und je Anwendungsfall die Züge je Modul, fehlende als 0', async () => {
    const el = await mount();
    const tabellen = el.querySelectorAll('table');
    expect(tabellen).toHaveLength(2);
    expect(tabellen[0].querySelector('caption')?.textContent).toContain('Je Muster');
    const koepfe = Array.from(tabellen[0].querySelectorAll('thead th')).map(
      (th) => th.textContent?.trim());
    expect(koepfe).toEqual(['Muster', 'Züge', 'ui_entscheidung', 'ui_themenbaum']);
    expect(zeilen(el, 0)).toEqual([['AGENT', '3', '1', '2'], ['M04', '1', '0', '0']]);
    expect(zeilen(el, 1)).toEqual([['orientieren', '2', '0', '2']]);
    expect(el.textContent).toContain('4 von 5 beantworteten Zügen erfasst.');
  });

  it('benennt Zeilen- und Spaltenköpfe für Hilfstechnik und macht den Rahmen erreichbar', async () => {
    const el = await mount();
    const rahmen = el.querySelector('.emn-rahmen')!;
    expect(rahmen.getAttribute('tabindex')).toBe('0');
    expect(rahmen.getAttribute('role')).toBe('region');
    const caption = el.querySelector('caption')!;
    expect(rahmen.getAttribute('aria-labelledby')).toBe(caption.id);
    expect(el.querySelector('tbody th')?.getAttribute('scope')).toBe('row');
    expect(el.querySelector('thead th')?.getAttribute('scope')).toBe('col');
  });

  it('sagt „nicht erfasst“ bei einem alten Lauf statt Nullen zu zeigen', async () => {
    const el = await mount({ zuege: 3, erfasst: 0, module: [], je_muster: {},
                             je_anwendungsfall: {} });
    expect(el.textContent).toContain('Nicht erfasst');
    expect(el.querySelector('table')).toBeNull();
  });

  it('sagt „noch keine beantworteten Züge“, statt einen jungen Lauf alt zu nennen (Review U1-g #10)', async () => {
    const leer: ModulNutzung = { zuege: 0, erfasst: 0, module: [], je_muster: {},
                                 je_anwendungsfall: {} };
    let el = await mount(leer);
    expect(el.textContent).toContain('Noch keine beantworteten Züge.');
    expect(el.textContent).not.toContain('Nicht erfasst');
    expect(el.querySelector('table')).toBeNull();
    el = await mount(leer, 'en');
    expect(el.textContent).toContain('No answered turns yet.');
  });

  it('sagt, wenn in keinem Zug ein Modul erschien', async () => {
    const el = await mount({ zuege: 2, erfasst: 2, module: [],
                             je_muster: { M04: { zuege: 2, module: {} } },
                             je_anwendungsfall: {} });
    expect(el.textContent).toContain('In keinem Zug erschien ein UI-Modul.');
    expect(el.querySelector('table')).toBeNull();
  });

  it('spricht Englisch, wenn das Studio Englisch spricht', async () => {
    const el = await mount(NUTZUNG, 'en');
    expect(el.textContent).toContain('Module use');
    expect(el.textContent).toContain('Per use case');
    expect(el.textContent).toContain('4 of 5 answered turns recorded.');
  });
});
