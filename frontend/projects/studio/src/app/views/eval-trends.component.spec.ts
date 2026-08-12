// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalTrendsComponent } from './eval-trends.component';

const TRENDS_URL = '/studio/api/eval/trends';

function runMeta(id: string, over: Record<string, unknown> = {}) {
  return {
    id, created_at: '2026-07-24T10:00:00Z', mode: 'generative',
    config_slug: 'wlo/v1', total_turns: 12, avg_score: 0.83, ...over,
  };
}

const P = (runId: string, value: number) => ({
  run_id: runId, created_at: '2026-07-24T10:00:00Z', value,
});

function body(over: Record<string, unknown> = {}) {
  return {
    runs: [runMeta('r1'), runMeta('r2', { avg_score: 0.9 })],
    pattern_trend: {},
    cache_hit_trend: [P('r1', 0.2), P('r2', 0.4)],
    llm_engine_match_trend: [P('r1', 0.5), P('r2', 0.5)],
    persona_correct_trend: [P('r1', 0.8), P('r2', 0.6)],
    intent_correct_trend: [P('r1', 0.7), P('r2', 0.75)],
    ...over,
  };
}

interface Harness {
  fixture: ComponentFixture<EvalTrendsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let h: Harness;

/** `AsyncData.reload` resolves a promise chain — one macrotask settles it. */
async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

/** jsdom meldet `navigator.language === 'en-US'`; ohne die gemerkte Wahl liefe
 *  die deutsche Oberfläche unter diesen Prüfungen auf Englisch. */
async function mount(
  payload: Record<string, unknown> | null = body(), locale = 'de',
): Promise<void> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(EvalTrendsComponent);
  const http = TestBed.inject(HttpTestingController);
  h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === TRENDS_URL);
  if (payload === null) {
    req.flush({ detail: 'Datenbank weg.' }, { status: 503, statusText: 'x' });
  } else {
    req.flush(payload);
  }
  await settle();
}

const charts = (): SVGElement[] =>
  Array.from(h.el.querySelectorAll<SVGElement>('svg.et-chart'));

describe('EvalTrendsComponent', () => {
  beforeEach(() => {
    h = undefined as unknown as Harness;
  });

  it('asks for the trend window', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
      ],
    });
    const fixture = TestBed.createComponent(EvalTrendsComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    const req = http.expectOne((r) => r.url === TRENDS_URL);
    expect(req.request.params.get('limit')).toBe('20');
    req.flush(body());
  });

  it('draws the score timeline plus one chart per classification series', async () => {
    await mount();
    // 1 score chart + 4 rate charts.
    expect(charts()).toHaveLength(5);
    expect(h.el.textContent).toContain('Ø Judge-Score je Lauf');
    for (const label of ['Cache-Hit-Rate', 'LLM-Pattern-Übereinstimmung',
      'Persona-Trefferquote', 'Intent-Trefferquote']) {
      expect(h.el.textContent).toContain(label);
    }
  });

  it('gives every chart a spoken summary naming value and direction', async () => {
    await mount();
    const labels = charts().map((c) => c.getAttribute('aria-label') ?? '');
    expect(labels[0]).toContain('Ø Judge-Score');
    const cache = labels.find((l) => l.startsWith('Cache-Hit-Rate'))!;
    expect(cache).toContain('aktuell 40');
    expect(cache).toContain('gestiegen');
    const persona = labels.find((l) => l.startsWith('Persona-Trefferquote'))!;
    expect(persona).toContain('gefallen');
    const match = labels.find((l) => l.startsWith('LLM-Pattern'))!;
    expect(match).toContain('unverändert');
  });

  it('puts every number in a real table as the accessible source', async () => {
    await mount();
    const table = h.el.querySelector('table.et-table')!;
    const headers = Array.from(table.querySelectorAll('thead th')).map(
      (th) => th.textContent?.trim(),
    );
    expect(headers).toEqual([
      'Lauf', 'Zeitpunkt', 'Art', 'Turns', 'Ø Score',
      'Cache-Hit-Rate', 'LLM-Pattern-Übereinstimmung',
      'Persona-Trefferquote', 'Intent-Trefferquote',
    ]);
    const firstRow = table.querySelectorAll('tbody tr')[0];
    expect(firstRow.querySelector('th')!.textContent).toContain('r1');
    expect(firstRow.textContent).toContain('0,83');
  });

  it('says why the classification series are empty when only gold ran', async () => {
    // classification_metrics is written by generative runs only; an
    // installation with gold flows alone must not look broken.
    await mount(body({
      runs: [runMeta('r1', { mode: 'golden' })],
      cache_hit_trend: [], llm_engine_match_trend: [],
      persona_correct_trend: [], intent_correct_trend: [],
    }));
    const note = h.el.querySelector('.et-note')!.textContent!;
    expect(note).toContain('generativer Lauf');
    expect(note).toContain('classification_metrics');
    expect(h.el.querySelectorAll('.et-empty')).toHaveLength(4);
    // The score timeline still works — it covers golden runs too.
    expect(charts()).toHaveLength(1);
  });

  it('hides that note as soon as one series carries data', async () => {
    await mount();
    expect(h.el.querySelector('.et-note')).toBeNull();
  });

  it('skips an unjudged run in the chart but keeps its table row', async () => {
    await mount(body({ runs: [runMeta('r1', { avg_score: null }), runMeta('r2')] }));
    expect(charts()[0].querySelectorAll('circle')).toHaveLength(1);
    expect(h.el.querySelectorAll('table.et-table tbody tr')).toHaveLength(2);
    expect(h.el.querySelectorAll('table.et-table tbody tr')[0].textContent).toContain('–');
  });

  it('lists tool compliance per pattern behind a disclosure', async () => {
    await mount(body({
      pattern_trend: {
        M06: [{ run_id: 'r1', created_at: '', rate: 0.5, ok: 1, total: 2 }],
        M05: [{ run_id: 'r1', created_at: '', rate: 1, ok: 3, total: 3 }],
      },
    }));
    const details = h.el.querySelector('details.et-details')!;
    expect(details.querySelector('summary')!.textContent).toContain('(2)');
    const rows = Array.from(details.querySelectorAll('tbody tr'));
    // Sorted by pattern id so the list is stable across reloads.
    expect(rows.map((r) => r.querySelector('th')!.textContent!.trim())).toEqual(
      ['M05', 'M06'],
    );
    expect(rows[1].textContent).toContain('50');
  });

  it('omits the pattern block when no pattern was measured', async () => {
    await mount();
    expect(h.el.querySelector('details.et-details')).toBeNull();
  });

  it('says an installation without finished runs is empty, and how it fills', async () => {
    await mount(body({
      runs: [], cache_hit_trend: [], llm_engine_match_trend: [],
      persona_correct_trend: [], intent_correct_trend: [],
    }));
    expect(h.el.querySelector('.as-line')!.textContent).toContain('Gold-Flow');
    expect(charts()).toHaveLength(0);
  });

  // ── C1-d4c ──────────────────────────────────────────────────────────
  //
  // Die gesprochene Zusammenfassung war bis hierher aus Bruchstücken
  // zusammengesetzt (`${label}: ${current}, über N Läufe von X ${richtung}`).
  // Sie steht jetzt als GANZER Satz im Katalog — die Wortstellung gehört der
  // Übersetzung, nicht der Methode.
  it('fügt die gesprochene Zusammenfassung ohne eingestreute Leerzeichen zusammen', async () => {
    await mount();
    const cache = charts()
      .map((c) => c.getAttribute('aria-label') ?? '')
      .find((l) => l.startsWith('Cache-Hit-Rate'))!;
    // Zeichenweise verglichen statt `\s+`-normalisiert: die Prüfung soll
    // ein versehentlich doppeltes Leerzeichen finden, und Zusammenziehen
    // nähme ihr genau das. Vor dem Prozentzeichen steht im erwarteten Text
    // deshalb das GESCHÜTZTE Leerzeichen (U+00A0), das `Intl` dort setzt.
    expect(cache).toBe(
      'Cache-Hit-Rate: aktuell 40,0 %, über 2 Läufe von 20,0 % gestiegen. '
      + 'Werte in der Tabelle darunter.',
    );
  });

  it('zählt den Verlauf eines Patterns in der Mehrzahl der Sprache', async () => {
    await mount(body({
      pattern_trend: { M06: [{ run_id: 'r1', created_at: '', rate: 0.5, ok: 1, total: 2 }] },
    }));
    // Ein einziger Lauf: „über 1 Läufe" wäre schon einsprachig falsch.
    expect(h.el.querySelector('svg.et-spark')!.getAttribute('aria-label'))
      .toContain('über 1 Lauf;');
  });

  it('spricht die ganze Ansicht in der aktiven Sprache', async () => {
    await mount(body(), 'en');
    const table = h.el.querySelector('table.et-table')!;
    const headers = Array.from(table.querySelectorAll('thead th')).map(
      (th) => th.textContent?.trim(),
    );
    expect(headers).toEqual([
      'Run', 'Time', 'Kind', 'Turns', 'Avg score',
      'Cache hit rate', 'LLM pattern match', 'Persona hit rate', 'Intent hit rate',
    ]);
    expect(h.el.textContent).toContain('Avg judge score per run');
    expect(h.el.textContent).not.toMatch(/Trefferquote/);
  });

  it('shows a failed read and offers a retry', async () => {
    await mount(null);
    expect(h.el.textContent).toContain('Datenbank weg.');
    h.el.querySelector<HTMLButtonElement>('.et-reload')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === TRENDS_URL).flush(body());
    await settle();
    expect(charts()).toHaveLength(5);
  });
});
