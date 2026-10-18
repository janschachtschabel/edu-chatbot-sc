// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { TrendsV2 } from '../core/eval-auswertung';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalTrendsV2Component } from './eval-trends-v2.component';

/**
 * Der Verlauf der Noten (Paket 13, F8): je Lauf eine Zeile mit Gesamt, Zug-Mittel, Skalen,
 * Antwortzeit und Kosten — und was sich gegenüber dem Lauf davor änderte (Wechselmarken).
 */
const V2: TrendsV2 = {
  gesamt: [{ run_id: 'r1', created_at: '2026-10-01T10:00:00Z', value: 3 },
           { run_id: 'r2', created_at: '2026-10-02T10:00:00Z', value: 4 }],
  zug_mittel: [{ run_id: 'r2', created_at: '2026-10-02T10:00:00Z', value: 3.8 }],
  latenz_p50_ms: [{ run_id: 'r1', created_at: '2026-10-01T10:00:00Z', value: 2000 },
                  { run_id: 'r2', created_at: '2026-10-02T10:00:00Z', value: 1500 }],
  kosten_je_zug: [],
  skalen: { verlauf: [{ run_id: 'r2', created_at: '2026-10-02T10:00:00Z', value: 4.5 }] },
  wechsel: [{ run_id: 'r2', created_at: '2026-10-02T10:00:00Z', felder: ['modell'], prompts: ['agent.kopf'] }],
};

const norm = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ').trim();

describe('EvalTrendsV2Component (Paket 13, F8)', () => {
  let fixture: ComponentFixture<EvalTrendsV2Component>;
  let el: HTMLElement;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(EvalTrendsV2Component);
    fixture.componentRef.setInput('v2', V2);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('hat je Lauf eine Zeile, älteste zuerst, mit Lücken statt Nullen', () => {
    const kopf = Array.from(el.querySelectorAll('thead th'), (th) => norm(th.textContent));
    expect(kopf).toEqual(['Lauf', 'Gesamt', 'Mittel der Zug-Noten', 'Verlauf', 'Median',
      'Kosten je Zug', 'Geändert']);
    const zeilen = Array.from(el.querySelectorAll('tbody tr'),
      (tr) => Array.from(tr.querySelectorAll('td'), (td) => norm(td.textContent)));
    expect(zeilen[0].slice(0, 5)).toEqual(['3', '—', '—', '2,0 s', '—']);
    expect(zeilen[1].slice(0, 4)).toEqual(['4', '3,8', '4,5', '1,5 s']);
  });

  it('nennt in der Wechsel-Spalte geänderte Felder und Prompt-Bausteine', () => {
    const letzte = Array.from(el.querySelectorAll('tbody tr:nth-child(2) td'));
    const wechsel = norm(letzte[letzte.length - 1].textContent);
    expect(wechsel).toContain('Chat-Modell');
    expect(wechsel).toContain('agent.kopf');
  });

  it('sagt es, wenn es noch keine Werte gibt', async () => {
    fixture.componentRef.setInput('v2', {
      gesamt: [], zug_mittel: [], latenz_p50_ms: [], kosten_je_zug: [], skalen: {}, wechsel: [],
    });
    await fixture.whenStable();
    expect(el.querySelector('table')).toBeNull();
    expect(el.textContent).toContain('Noch kein Lauf mit Judge v2');
  });
});
