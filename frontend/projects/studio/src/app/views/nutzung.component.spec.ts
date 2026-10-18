// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { StudioAnsicht } from '../core/studio-ansicht.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { NutzungComponent } from './nutzung.component';

const URL = '/studio/api/nutzung/ueberblick';
const raster = (): number[][] => Array.from({ length: 7 }, () => Array(24).fill(0));

function antwort(extra: Record<string, unknown> = {}) {
  const r = raster();
  r[1][10] = 12;
  r[2][21] = 2;
  return {
    zuege: 14, sitzungen: 3, zuege_je_sitzung: { mittel: 4.67, median: 2 },
    tage: [
      { tag: '2026-03-10', sitzungen: 2, zuege: 12 },
      { tag: '2026-03-11', sitzungen: 1, zuege: 2 },
    ],
    raster: r,
    verteilungen: {
      maschine: [{ wert: 'pattern', anzahl: 12 }, { wert: 'agent', anzahl: 2 }],
      sprache: [{ wert: 'de', anzahl: 14 }],
      geraet: [{ wert: '', anzahl: 14 }],
      seitenart: [{ wert: 'themenseite', anzahl: 9 }],
      persona: [{ wert: 'P-LK', anzahl: 12 }],
      anliegen: [{ wert: 'I01 (Suche)', anzahl: 12 }],
    },
    protokoll_an: true, ...extra,
  };
}

const norm = (t: string | null | undefined) => (t ?? '').replace(/\s+/g, ' ').trim();

async function mount(body: object = antwort()) {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  localStorage.clear();
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()),
      provideHttpClientTesting(), provideRouter([])],
  });
  TestBed.inject(StudioAnsicht).waehle('pattern');
  const fixture = TestBed.createComponent(NutzungComponent);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === URL);
  req.flush(body);
  await new Promise((r) => setTimeout(r, 0));
  await fixture.whenStable();
  return { el: fixture.nativeElement as HTMLElement, req, http, fixture };
}

describe('NutzungComponent (Paket 16, D3)', () => {
  it('fragt den Zeitraum mit Herkunft — und beide Maschinen, nicht nur die des Arbeitsbereichs', async () => {
    // Review Paket 16 (D-1): mit Filter zeigte „Maschine“ immer 100 % einer Maschine, und
    // Zielgruppe/Anliegen blieben im Agent-Arbeitsbereich leer.
    const { req } = await mount();
    expect(req.request.params.get('from')).toBeTruthy();
    expect(req.request.params.get('to')).toBeTruthy();
    expect(req.request.params.has('engine')).toBe(false);
  });

  it('nennt Züge, Sitzungen und Züge je Sitzung', async () => {
    const { el } = await mount();
    const band = norm(el.querySelector('.nz-band')?.textContent);
    expect(band).toContain('14');
    expect(band).toContain('3');
    expect(band).toContain('4,67');
  });

  it('zeigt Wochentag × Stunde als Tabelle mit genauen Zahlen (Studio-Rundgang)', async () => {
    const { el } = await mount();
    const zeilen = el.querySelectorAll('table.nz-raster tbody tr');
    expect(zeilen).toHaveLength(7);
    expect(norm(zeilen[0].querySelector('th')?.textContent)).toBe('Mo');
    const dienstag = zeilen[1].querySelectorAll('td');
    expect(dienstag).toHaveLength(24);
    // Review D-6: die Tabelle hat einen Namen, die Stunden eine Einheit.
    expect(el.querySelector('table.nz-raster caption')?.textContent).toContain('Wochentag');
    expect(el.querySelectorAll('table.nz-raster thead th')[10].getAttribute('aria-label')).toBe('10 Uhr');
    expect(norm(dienstag[10].textContent)).toBe('12');
    expect(norm(zeilen[2].querySelectorAll('td')[21].textContent)).toBe('2');
    expect(el.textContent).not.toContain('<5');
  });

  it('nennt die Farbstufen in einer Legende, abgeleitet aus den Zahlen der Anzeige', async () => {
    const { el } = await mount();
    const legende = Array.from(el.querySelectorAll('.nz-legende li'), (li) => norm(li.textContent));
    // Höchstwert 12 → Schritte zu 2: 1, 2–3, 4–5 … gerundet; die letzte Stufe ist offen.
    expect(legende.at(-1)).toBe('keine');
    expect(legende.at(-2)).toMatch(/^ab \d+$/);
    expect(legende[0]).toMatch(/^1/);
    // Jede Zelle trägt die Stufe ihres Bereichs; die höchste Zahl die höchste.
    const dienstag = el.querySelectorAll('table.nz-raster tbody tr')[1].querySelectorAll('td');
    expect(dienstag[10].getAttribute('data-stufe')).toBe(String(legende.length - 1));
    expect(dienstag[0].getAttribute('data-stufe')).toBe('0');
  });

  it('führt die Verteilungen; leere Werte und Maschinen heißen verständlich', async () => {
    const { el } = await mount();
    const maschine = norm(el.querySelector('[data-facette="maschine"]')?.textContent);
    expect(maschine).toContain('Muster-Maschine');
    expect(maschine).toMatch(/Agent-Schleife\s*2/);
    expect(norm(el.querySelector('[data-facette="geraet"]')?.textContent))
      .toContain('ohne Angabe');
    expect(norm(el.querySelector('[data-facette="persona"]')?.textContent))
      .toContain('nur Muster-Züge');
  });

  it('führt die Tage als Tabelle', async () => {
    const { el } = await mount();
    const zeilen = Array.from(el.querySelectorAll('table.nz-tage tbody tr'), (tr) =>
      Array.from(tr.querySelectorAll('th, td'), (c) => norm(c.textContent)));
    expect(zeilen[0].slice(0, 3)).toEqual(['10.3.2026', '2', '12']);
  });

  it('sagt es, wenn das Qualitätsprotokoll nichts schreibt — mit dem Weg zum Schalter', async () => {
    const { el } = await mount(antwort({ protokoll_an: false }));
    const hinweis = el.querySelector('.nz-aus');
    expect(norm(hinweis?.textContent)).toContain('Qualitäts-Protokoll');
    expect(hinweis?.querySelector('a')?.getAttribute('href')).toBe('/datenschutz');
  });

  it('schweigt darüber, solange es schreibt', async () => {
    const { el } = await mount();
    expect(el.querySelector('.nz-aus')).toBeNull();
  });

  it('benennt die Spalten der Verteilungen (Review PR #18)', async () => {
    const { el } = await mount();
    const kopf = Array.from(el.querySelectorAll('[data-facette="sprache"] thead th'),
      (th) => norm(th.textContent));
    expect(kopf).toEqual(['Wert', 'Züge']);
  });
});
