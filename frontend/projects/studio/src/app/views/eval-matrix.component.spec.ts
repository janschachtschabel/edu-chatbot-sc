// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalMatrixComponent, type MatrixDaten } from './eval-matrix.component';

/**
 * Die farbige Matrix des Lauf-Details (Paket 13, F3): eine echte Tabelle mit Zeilen- und
 * Spaltenköpfen; jede Zelle trägt die Zahl UND eine Farbstufe (Farbe nie allein), leere Zellen
 * sind schraffiert und nicht wählbar, gefüllte sind Knöpfe (Tastatur von der Plattform).
 */
const DATEN: MatrixDaten = {
  'P-LEH': { suchen: { note: 4.6, n: 3 }, erzeugen: { note: 2.0, n: 1 } },
  'P-LER': { suchen: { note: 3.5, n: 2 } },
};

describe('EvalMatrixComponent (Paket 13, F3)', () => {
  let fixture: ComponentFixture<EvalMatrixComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(EvalMatrixComponent);
    fixture.componentRef.setInput('titel', 'Zielgruppe × Anwendungsfall');
    fixture.componentRef.setInput('zeilenKopf', 'Zielgruppe');
    fixture.componentRef.setInput('daten', DATEN);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('ist eine Tabelle mit Titel, Spalten- und Zeilenköpfen', () => {
    expect(el.querySelector('caption')?.textContent).toContain('Zielgruppe × Anwendungsfall');
    const spalten = Array.from(el.querySelectorAll('thead th'), (th) => th.textContent?.trim());
    expect(spalten).toEqual(['Zielgruppe', 'erzeugen', 'suchen']);
    expect(el.querySelectorAll('thead th[scope="col"]').length).toBe(3);
    expect(Array.from(el.querySelectorAll('tbody th[scope="row"]'), (th) => th.textContent?.trim()))
      .toEqual(['P-LEH', 'P-LER']);
  });

  it('zeigt Zahl, Anzahl und Stufe — Farbe nie allein', () => {
    const zelle = el.querySelector<HTMLButtonElement>('tbody tr:first-child td:nth-of-type(2) button')!;
    expect(zelle.textContent).toContain('4,6');
    expect(zelle.closest('td')!.className).toContain('em-sehr-gut');
    expect(zelle.getAttribute('aria-label')).toBe('P-LEH × suchen: 4,6 (n = 3), sehr gut');
    const schwach = el.querySelector('tbody tr:first-child td:nth-of-type(1)')!;
    expect(schwach.className).toContain('em-schwach');
  });

  it('eine leere Zelle ist schraffiert, sagt „keine Daten“ und ist kein Knopf', () => {
    const leer = el.querySelector('tbody tr:nth-child(2) td:nth-of-type(1)')!;
    expect(leer.className).toContain('em-leer');
    expect(leer.querySelector('button')).toBeNull();
    expect(leer.textContent).toContain('—');
    expect(leer.querySelector('.sr')?.textContent).toContain('keine Daten');
  });

  it('meldet die gewählte Zelle', () => {
    let gewaehlt: unknown = null;
    fixture.componentInstance.waehle.subscribe((wahl) => (gewaehlt = wahl));
    el.querySelector<HTMLButtonElement>('tbody tr:nth-child(2) td:nth-of-type(2) button')!.click();
    expect(gewaehlt).toEqual({ zeile: 'P-LER', spalte: 'suchen' });
  });

  it('nennt die Stufen in einer Legende', () => {
    const legende = el.querySelector('.em-legende')?.textContent ?? '';
    for (const wort of ['ab 4,5', 'ab 3,5', 'ab 2,5', 'unter 2,5', 'keine Daten']) {
      expect(legende).toContain(wort);
    }
  });

  it('sagt es, wenn es nichts zu zeigen gibt', async () => {
    fixture.componentRef.setInput('daten', {});
    await fixture.whenStable();
    expect(el.querySelector('table')).toBeNull();
    expect(el.textContent).toContain('Keine bewerteten Züge');
  });
});
