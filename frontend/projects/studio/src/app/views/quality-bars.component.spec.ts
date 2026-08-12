// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { QualityBarsComponent } from './quality-bars.component';

let fixture: ComponentFixture<QualityBarsComponent>;
let el: HTMLElement;

/** jsdom meldet `navigator.language === 'en-US'`; ohne die gemerkte Wahl liefe
 *  die deutsche Oberfläche unter diesen Prüfungen auf Englisch. */
async function build(locale = 'de'): Promise<void> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  fixture = TestBed.createComponent(QualityBarsComponent);
  el = fixture.nativeElement as HTMLElement;
  fixture.componentRef.setInput('caption', 'Pattern-Verteilung');
  fixture.componentRef.setInput('data', {});
  await fixture.whenStable();
}

async function render(data: Record<string, number>): Promise<void> {
  fixture.componentRef.setInput('data', data);
  await fixture.whenStable();
}

function rowKeys(): string[] {
  return Array.from(el.querySelectorAll('.qb-key')).map((th) => th.textContent!.trim());
}

describe('QualityBarsComponent', () => {
  beforeEach(async () => {
    await build();
  });

  it('names the table so the two distributions are tellable apart', async () => {
    await render({ M04: 1 });
    expect(el.querySelector('caption')!.textContent).toContain('Pattern-Verteilung');
  });

  it('sorts by count, biggest first', async () => {
    await render({ M04: 3, M15: 9, M02: 5 });
    expect(rowKeys()).toEqual(['M15', 'M02', 'M04']);
  });

  it('gives the number as text, not only as bar length', async () => {
    // The bar is decoration; a screen reader has to get the value from the row.
    await render({ M04: 42 });
    expect(el.querySelector('tbody tr')!.textContent).toContain('42');
    expect(el.querySelector('.qb-bar')!.getAttribute('aria-hidden')).toBe('true');
  });

  it('scales the bars against the largest value', async () => {
    await render({ gross: 10, klein: 2 });
    const bars = el.querySelectorAll<HTMLElement>('.qb-bar-fill');
    expect(bars[0].style.inlineSize).toBe('100%');
    expect(bars[1].style.inlineSize).toBe('20%');
  });

  it('survives a distribution that is all zeroes', async () => {
    // `count / max` with max = 0 would be NaN and render an invalid width.
    await render({ a: 0, b: 0 });
    const bars = el.querySelectorAll<HTMLElement>('.qb-bar-fill');
    expect(bars[0].style.inlineSize).toBe('0%');
  });

  it('renders nothing at all when there is no data', async () => {
    // The caller owns the empty state — it knows what would be here.
    await render({});
    expect(el.querySelector('table')).toBeNull();
  });

  it('labels an empty key rather than showing a blank row', async () => {
    await render({ '': 4 });
    expect(el.querySelector('tbody tr')!.textContent).toContain('(ohne)');
  });

  // ── C1-d4b3 ─────────────────────────────────────────────────────────
  //
  // Die Balken-Tabelle steht in drei Ansichten an sieben Stellen. Ihre eigenen
  // drei Texte übersetzt sie deshalb selbst; nur die Beschriftung der Tabelle
  // und die Einheit kommen fertig von der Aufrufstelle, die weiss, was sie
  // zählt.
  it('trägt seine eigenen drei Texte in der aktiven Sprache', async () => {
    await build('en');
    await render({ M04: 3, '': 1 });

    const kopf = el.querySelector('thead')!.textContent ?? '';
    expect(kopf).toContain('Id');           // Spaltenkopf, nur für Screenreader
    expect(kopf).toContain('Turns');        // Voreinstellung der Einheit
    expect(el.querySelector('tbody tr:last-child')!.textContent).toContain('(none)');
    expect(el.textContent).not.toMatch(/\(ohne\)/);
  });

  it('lässt eine mitgegebene Einheit stehen — sie gehört der Aufrufstelle', async () => {
    fixture.componentRef.setInput('unit', 'Übergänge');
    await render({ M04: 1 });
    expect(el.querySelector('thead')!.textContent).toContain('Übergänge');
  });
});
