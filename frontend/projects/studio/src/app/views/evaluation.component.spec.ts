// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { routes } from '../app.routes';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvaluationComponent } from './evaluation.component';

const RUNS_URL = '/studio/api/eval/runs';
const TRENDS_URL = '/studio/api/eval/trends';
/** The start panel (A3) sits in the same tab and loads its own choices. */
const CONFIG_URL = '/studio/api/eval/config';
/** The gold-flow start panel (A2) reads its own choices. */
const FLOWS_URL = '/studio/api/eval/gold-flows';

interface Harness {
  fixture: ComponentFixture<EvaluationComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

/** One list row, only the fields the list itself renders. */
function runRow(over: Record<string, unknown> = {}) {
  return {
    id: 'eval-abc', created_at: '2026-07-26T10:00:00Z', completed_at: null,
    status: 'done', mode: 'golden', config_slug: '', total_turns: 3,
    avg_score: 0.83, personas: [], intents: [], error_message: null,
    target_turns: 3, current_activity: '', ...over,
  };
}

async function mount(
  runs: readonly Record<string, unknown>[] = [], locale = 'de',
): Promise<Harness> {
  // jsdom meldet `navigator.language === 'en-US'`; ohne diese Zeile liefe eine
  // Prüfung auf deutschen Wortlaut gegen die englische Oberfläche (C1-d4a).
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(EvaluationComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne((r) => r.url === RUNS_URL).flush({ runs: runs.map((r) => runRow(r)) });
  http.expectOne((r) => r.url === CONFIG_URL).flush({ personas: [], intents: [] });
  http.expectOne((r) => r.url === FLOWS_URL).flush({ flows: [], count: 0 });
  await settle(h);
  return h;
}

const tabs = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]'));

describe('EvaluationComponent', () => {
  it('is what the evaluation route actually loads', async () => {
    // A view nobody can navigate to is not built. 9-5c shipped four finished
    // panels that were unreachable until the route entry landed.
    const children = routes.find((r) => r.path === '')!.children!;
    const route = children.find((r) => r.path === 'evaluation')!;
    const loaded = await (route.loadComponent as () => Promise<unknown>)();
    expect(loaded).toBe(EvaluationComponent);
  });

  it('opens on the run list and loads only that panel', async () => {
    const h = await mount();
    expect(tabs(h).map((t) => t.textContent?.trim()))
      .toEqual(['Läufe', 'Trends', 'Pattern-Nutzung']);
    // Trends must not fetch before it is opened.
    h.http.verify();
    expect(h.el.querySelector('#panel-trends')!.hasAttribute('hidden')).toBe(true);
  });

  it('beschriftet die Reiter in der aktiven Sprache', async () => {
    // Bis C1-d4b standen die drei Beschriftungen als fertige Sätze in einer
    // Modul-Konstante `TABS` — dem siebten eingefrorenen Fall dieser Art. Auf
    // Englisch blieben sie deutsch, obwohl die Seite sonst wechselte.
    const h = await mount([], 'en');
    expect(tabs(h).map((t) => t.textContent?.trim()))
      .toEqual(['Runs', 'Trends', 'Pattern usage']);
  });

  it('opens the detail of the run the list points at, and closes it again', async () => {
    // The list has emitted `runChange` since 9-5d; until this listener existed
    // nothing happened when a row was opened.
    const h = await mount([{ id: 'eval-abc' }]);
    const row = h.el.querySelector<HTMLButtonElement>('#panel-laeufe .er-row')!;
    row.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/eval/runs/eval-abc').flush({
      id: 'eval-abc', created_at: '2026-07-26T10:00:00Z', completed_at: null,
      status: 'done', mode: 'golden', config_slug: '', personas: [], intents: [],
      turns_per_conv: 0, judge_model: '', simulator_model: '', total_turns: 0,
      avg_score: null, error_message: null, summary: {}, conversations: [],
    });
    await settle(h);

    expect(h.el.querySelector('studio-eval-run-detail')).toBeTruthy();

    const close = Array.from(h.el.querySelectorAll('button'))
      .find((b) => (b.textContent ?? '').includes('Schließen')) as HTMLButtonElement;
    close.click();
    await settle(h);

    expect(h.el.querySelector('studio-eval-run-detail')).toBeNull();
  });

  it('puts both start forms in the same panel as the list they feed', async () => {
    // A run takes minutes and the list is its only progress display — a start
    // button on another tab would report nothing after the click.
    const h = await mount();
    const panel = h.el.querySelector('#panel-laeufe')!;
    expect(panel.querySelector('studio-eval-golden-start')).toBeTruthy();
    expect(panel.querySelector('studio-eval-generative-start')).toBeTruthy();
    expect(panel.querySelector('studio-eval-runs')).toBeTruthy();
  });

  it('loads the trends panel on its first visit', async () => {
    const h = await mount();
    tabs(h)[1].click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === TRENDS_URL).flush({
      runs: [], pattern_trend: {}, cache_hit_trend: [],
      llm_engine_match_trend: [], persona_correct_trend: [], intent_correct_trend: [],
    });
    await settle(h);
    expect(h.el.querySelector('#panel-trends')!.hasAttribute('hidden')).toBe(false);
    expect(h.el.querySelector('#panel-laeufe')!.hasAttribute('hidden')).toBe(true);
  });

  it('keeps a visited panel mounted so switching back does not refetch', async () => {
    const h = await mount();
    tabs(h)[1].click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === TRENDS_URL).flush({
      runs: [], pattern_trend: {}, cache_hit_trend: [],
      llm_engine_match_trend: [], persona_correct_trend: [], intent_correct_trend: [],
    });
    await settle(h);

    tabs(h)[0].click();
    await settle(h);
    tabs(h)[1].click();
    await settle(h);
    // Neither panel re-fetches — both are still mounted, just hidden.
    h.http.verify();
  });

  it('loads the pattern usage on its first visit', async () => {
    const h = await mount();
    tabs(h)[2].click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === '/studio/api/eval/analytics/pattern-usage').flush({
      triples: [], by_pattern: [], by_intent: [], total: 0, scope: 'all',
    });
    await settle(h);

    expect(h.el.querySelector('#panel-pattern')!.hasAttribute('hidden')).toBe(false);
  });

  it('wires each panel to its tab for assistive technology', async () => {
    const h = await mount();
    for (const id of ['laeufe', 'trends', 'pattern']) {
      const panel = h.el.querySelector(`#panel-${id}`)!;
      expect(panel.getAttribute('role')).toBe('tabpanel');
      expect(panel.getAttribute('aria-labelledby')).toBe(`tab-${id}`);
      expect(panel.getAttribute('tabindex')).toBe('0');
    }
  });
});
