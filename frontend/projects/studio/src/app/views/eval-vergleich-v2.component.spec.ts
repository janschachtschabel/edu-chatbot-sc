// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import type { EngineComparison } from '../core/eval-profile';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalVergleichV2Component } from './eval-vergleich-v2.component';

/**
 * Der Vergleich mit dem Judge v2 (Paket 13, F8): Noten je Maschine und was zwischen den Läufen
 * anders war — Felder der Messbedingungen, Bereiche und Prompt-Bausteine mit Text-Unterschied.
 */
const VERGLEICH = {
  engines: {}, rules: {}, currency: null, conditions: [], warnings: [],
  runs: [{ id: 'r1', engine: 'agent', status: 'done', label: '', counted: true }],
  bewertung_je_maschine: {
    agent: { laeufe: 2, gesamt_mittel: 3.5, zug_mittel: 3.8, skalen_mittel: { verlauf: 3 } },
  },
  unterschiede: {
    referenz: 'r1',
    laeufe: [{
      run: 'r2',
      felder: [{ feld: 'modell', a: 'gpt-6-luna', b: 'gpt-6' }],
      bereiche: ['04-personas'],
      prompts: [{ art: 'agent.kopf', a: ['aaaaaaaaaaaa'], b: ['bbbbbbbbbbbb'] }],
    }],
  },
} as unknown as EngineComparison;

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));
const norm = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ').trim();

describe('EvalVergleichV2Component (Paket 13, F8)', () => {
  let fixture: ComponentFixture<EvalVergleichV2Component>;
  let el: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    fixture = TestBed.createComponent(EvalVergleichV2Component);
    fixture.componentRef.setInput('vergleich', VERGLEICH);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
    http = TestBed.inject(HttpTestingController);
  });

  it('zeigt die Noten je Maschine als Tabelle', () => {
    const kopf = Array.from(el.querySelectorAll('thead th'), (th) => norm(th.textContent));
    expect(kopf).toEqual(['Maschine', 'Läufe', 'Gesamt', 'Mittel der Zug-Noten', 'Verlauf']);
    const zeile = Array.from(el.querySelectorAll('tbody tr:first-child th, tbody tr:first-child td'),
      (z) => norm(z.textContent));
    expect(zeile).toEqual(['Agent-Schleife', '2', '3,5', '3,8', '3']);
  });

  it('nennt geänderte Felder, Bereiche und Prompt-Bausteine gegenüber der Referenz', () => {
    const text = norm(el.querySelector('.vg-unterschiede')?.textContent);
    expect(text).toContain('Unterschiede gegenüber r1');
    expect(text).toContain('Chat-Modell: gpt-6-luna → gpt-6');
    expect(text).toContain('Geänderte Konfigurationsbereiche: 04-personas');
    expect(text).toContain('Prompt-Baustein agent.kopf geändert');
  });

  it('holt auf Wunsch den Text-Unterschied und zeigt ihn zeilenweise', async () => {
    el.querySelector<HTMLButtonElement>('.vg-diff-knopf')!.click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.url.endsWith('/eval/prompt-diff'));
    expect(req.request.params.get('a')).toBe('aaaaaaaaaaaa');
    expect(req.request.params.get('b')).toBe('bbbbbbbbbbbb');
    req.flush({ diff: ['--- a', '+++ b', '-Sie siezen.', '+Du duzt.', ' Kurz.'] });
    await tick();
    await fixture.whenStable();
    const zeilen = Array.from(el.querySelectorAll('.vg-diff span'));
    expect(zeilen.find((z) => z.textContent === '-Sie siezen.')?.className).toContain('vg-weg');
    expect(zeilen.find((z) => z.textContent === '+Du duzt.')?.className).toContain('vg-neu');
  });

  it('vergleicht die Fassung, die nur A hat, mit der, die nur B hat (Review PR #18)', async () => {
    // Je Baustein eine sortierte Liste von Prüfsummen; a[0] gegen b[0] verglich h1 mit h1.
    const zwei = { ...VERGLEICH, unterschiede: { referenz: 'r1', laeufe: [{
      run: 'r2', felder: [], bereiche: [],
      prompts: [{ art: 'agent.kopf', a: ['h1aaaaaaaaaa', 'h2aaaaaaaaaa'],
        b: ['h1aaaaaaaaaa', 'h3aaaaaaaaaa'] }],
    }] } } as unknown as EngineComparison;
    fixture.componentRef.setInput('vergleich', zwei);
    await fixture.whenStable();
    el.querySelector<HTMLButtonElement>('.vg-diff-knopf')!.click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.url.endsWith('/eval/prompt-diff'));
    expect([req.request.params.get('a'), req.request.params.get('b')])
      .toEqual(['h2aaaaaaaaaa', 'h3aaaaaaaaaa']);
  });

  it('lässt einen gescheiterten Text-Unterschied erneut holen (Review PR #18)', async () => {
    const knopf = () => el.querySelector<HTMLButtonElement>('.vg-diff-knopf')!;
    knopf().click();
    await fixture.whenStable();
    http.expectOne((r) => r.url.endsWith('/eval/prompt-diff'))
      .flush({ detail: 'weg' }, { status: 500, statusText: 'x' });
    await tick();
    await fixture.whenStable();
    expect(knopf().disabled).toBe(false);
    knopf().click();
    await fixture.whenStable();
    http.expectOne((r) => r.url.endsWith('/eval/prompt-diff'));
  });

  it('sagt, wenn die Läufe unter gleichen Bedingungen liefen', async () => {
    fixture.componentRef.setInput('vergleich', {
      ...VERGLEICH, unterschiede: { referenz: 'r1', laeufe: [{ run: 'r2', felder: [], bereiche: [], prompts: [] }] },
    });
    await fixture.whenStable();
    expect(norm(el.querySelector('.vg-unterschiede')?.textContent)).toContain('Keine Unterschiede');
  });

  it('zeigt nichts von alledem bei einem älteren Backend', async () => {
    fixture.componentRef.setInput('vergleich', { ...VERGLEICH, bewertung_je_maschine: undefined, unterschiede: undefined });
    await fixture.whenStable();
    expect(norm(el.textContent)).toBe('');
  });

  it('macht die breite Tabelle per Tastatur erreichbar und benennt sie (Review PR #18)', () => {
    const rahmen = el.querySelector('.vg-rahmen')!;
    expect(rahmen.getAttribute('tabindex')).toBe('0');
    expect(rahmen.getAttribute('role')).toBe('region');
    expect(el.querySelector(`#${rahmen.getAttribute('aria-labelledby')}`)?.textContent).toBeTruthy();
    expect(el.querySelector('.vg-tabelle')?.getAttribute('aria-labelledby')).toBe('vg-noten');
  });
});
