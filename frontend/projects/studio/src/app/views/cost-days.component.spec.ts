// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { UsageDay } from '../core/usage-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { CostDaysComponent } from './cost-days.component';

const TAGE: UsageDay[] = [
  { tag: '2026-03-09', calls: 0, amount: '0', unvollstaendig: false },
  { tag: '2026-03-10', calls: 4, amount: '1.25', unvollstaendig: false },
  { tag: '2026-03-11', calls: 2, amount: null, unvollstaendig: true },
  { tag: '2026-03-12', calls: 3, amount: '0.5', unvollstaendig: true },
];

async function mount(tage: readonly UsageDay[] = TAGE): Promise<HTMLElement> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(CostDaysComponent);
  fixture.componentRef.setInput('tage', tage);
  fixture.componentRef.setInput('currency', 'EUR');
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

const norm = (t: string | null | undefined) => (t ?? '').replace(/\s+/g, ' ').trim();

describe('CostDaysComponent (Paket 16, D2)', () => {
  it('zeichnet eine Säule je Tag, als Bild mit Namen', async () => {
    const el = await mount();
    const bild = el.querySelector('svg[role="img"]');
    expect(bild?.getAttribute('aria-labelledby')).toBeTruthy();
    expect(el.querySelectorAll('svg .cd-bar')).toHaveLength(4);
    // Keine Ersatzmarken mehr (Studio-Rundgang): ein Tag ohne Preis steht im Hinweis.
    expect(el.querySelector('svg .cd-ohne')).toBeNull();
  });

  it('nennt im Betrag die Tage ohne Preis und bietet „Aufrufe“ an', async () => {
    const el = await mount();
    const wahl = (w: string) => el.querySelector<HTMLInputElement>(`input[type="radio"][value="${w}"]`)!;
    expect(wahl('betrag').checked).toBe(true);
    expect(norm(el.querySelector('.cd-hinweis')?.textContent)).toContain('An 1 Tag fehlt der Preis');
    wahl('aufrufe').click();
    await new Promise((r) => setTimeout(r, 0));
    const hoehen = Array.from(el.querySelectorAll('svg .cd-bar'), (r) => Number(r.getAttribute('height')));
    expect(hoehen.filter((h) => h > 0)).toHaveLength(3);
    expect(norm(el.querySelector('.cd-hinweis')?.textContent)).toContain('4 LLM-Aufrufe');
  });

  it('steht ganz ohne Preis von selbst auf „Aufrufe“ — normale Säulen statt leerer Fläche', async () => {
    const el = await mount([
      { tag: '2026-03-10', calls: 4, amount: null, unvollstaendig: true },
      { tag: '2026-03-11', calls: 2, amount: null, unvollstaendig: true },
    ]);
    const betrag = el.querySelector<HTMLInputElement>('input[type="radio"][value="betrag"]')!;
    expect(el.querySelector<HTMLInputElement>('input[type="radio"][value="aufrufe"]')!.checked).toBe(true);
    expect(betrag.disabled).toBe(true);
    // Der Grund der Sperre ist mit dem Umschalter verknüpft, nicht nur danebengeschrieben.
    const grund = el.querySelector('fieldset')?.getAttribute('aria-describedby') ?? '';
    expect(norm(el.querySelector(`#${grund}`)?.textContent)).toContain('kein Preis gepflegt');
    const hoehen = Array.from(el.querySelectorAll('svg .cd-bar'), (r) => Number(r.getAttribute('height')));
    expect(hoehen.every((h) => h > 0)).toBe(true);
  });

  it('führt die Tage zusätzlich als Tabelle — die Textfassung des Diagramms', async () => {
    const el = await mount();
    const zeilen = Array.from(el.querySelectorAll('table tbody tr'), (tr) =>
      Array.from(tr.querySelectorAll('th, td'), (c) => norm(c.textContent)));
    expect(zeilen[1][0]).toBe('10.3.2026');
    expect(zeilen[1][1]).toBe('4');
    expect(zeilen[1][2]).toContain('1,25');
    expect(zeilen[2][2]).toBe('kein Preis');
    expect(zeilen[3][2]).toContain('unvollständig');
  });

  it('sagt ohne jeden bepreisten Betrag nicht „die höchste steht für 0,00 €“', async () => {
    const el = await mount([
      { tag: '2026-03-10', calls: 4, amount: null, unvollstaendig: true },
      { tag: '2026-03-11', calls: 0, amount: '0', unvollstaendig: false },
    ]);
    const hinweis = norm(el.querySelector('.cd-hinweis')?.textContent);
    expect(hinweis).not.toContain('0,00');
    expect(hinweis).toContain('kein Preis gepflegt');
  });

  it('zeigt nichts ohne Tage', async () => {
    const el = await mount([]);
    expect(el.querySelector('svg')).toBeNull();
    expect(el.querySelector('table')).toBeNull();
  });
});
