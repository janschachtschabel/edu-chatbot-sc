// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { AuswertungV2 } from '../core/eval-auswertung';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalZeitenComponent } from './eval-zeiten.component';

/**
 * Zeiten je Schritt (Paket 13, F6): je Art (Knoten, Teilschritte, LLM-Aufrufe) eine Tabelle mit
 * Median, p95 und Anzahl, langsamste zuerst; der Balken ist Zierde, die Tabelle die Quelle.
 */
const ZEITEN: AuswertungV2['zeiten'] = {
  knoten: {
    assess: { p50_ms: 300, p95_ms: 500, n: 4 },
    respond: { p50_ms: 4000, p95_ms: 9000, n: 4 },
  },
  schritte: {},
  llm: { agent: { p50_ms: 3500, p95_ms: 8000, n: 4 } },
};

const norm = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ').trim();

describe('EvalZeitenComponent (Paket 13, F6)', () => {
  let fixture: ComponentFixture<EvalZeitenComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(EvalZeitenComponent);
    fixture.componentRef.setInput('zeiten', ZEITEN);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('zeigt je Art mit Messwerten eine Tabelle, leere Arten nicht', () => {
    const titel = Array.from(el.querySelectorAll('caption'), (c) => norm(c.textContent));
    expect(titel).toEqual(['Knoten', 'LLM-Aufrufe']);
  });

  it('ordnet die Schritte nach Median, langsamste zuerst, mit Median, p95 und Anzahl', () => {
    const zeilen = Array.from(el.querySelectorAll('table')[0].querySelectorAll('tbody tr'),
      (tr) => Array.from(tr.querySelectorAll('th, td'), (z) => norm(z.textContent)));
    expect(zeilen[0].slice(0, 4)).toEqual(['respond', '4,0 s', '9,0 s', '4']);
    expect(zeilen[1][0]).toBe('assess');
  });

  it('lässt den Rahmen per Tastatur rollen und benennt ihn (Review PR #18)', () => {
    const rahmen = el.querySelector('.ez')!;
    expect(rahmen.getAttribute('tabindex')).toBe('0');
    expect(rahmen.getAttribute('role')).toBe('region');
    expect(rahmen.getAttribute('aria-label')).toBe('Zeiten je Schritt');
  });

  it('sagt es, wenn nichts gemessen wurde', async () => {
    fixture.componentRef.setInput('zeiten', { knoten: {}, schritte: {}, llm: {} });
    await fixture.whenStable();
    expect(el.querySelector('table')).toBeNull();
    expect(el.textContent).toContain('Keine Zeiten gemessen');
  });
});
