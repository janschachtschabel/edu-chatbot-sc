// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { EngineComparison, EngineSummary } from '../core/eval-profile';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalCompareComponent } from './eval-compare.component';

const URL = '/studio/api/eval/compare';
/** `Intl` setzt vor das Prozentzeichen ein geschütztes Leerzeichen. */
const NBSP = '\u00a0';

const QUALITY = {
  hard_rate: 0.95, hard_passed: 19, hard_total: 20,
  axes: { auftrag_erfuellt: 1.4, intent_fit: 1.8, persona_tone: 1.1,
          info_quality: 1.5, safety: 2, pattern_match: null },
};

function summary(runs: number): EngineSummary {
  return {
    runs, quality: QUALITY, hard_rate_runs: Array(runs).fill(0.95),
    determinism: { turns_compared: 20, check_agreement: 0.8, tool_jaccard: 0.9,
                   text_similarity: 0.7, judge_spread: 0.2 },
    speed: { p50_ms: 12000, p95_ms: 20000, over_30s: 0, over_90s: 0 },
    cost: { turns_with_usage: 20, prompt: 1000, cached: 0, completion: 100,
            cost_per_turn: 0.00015, cost_total: 0.003, price_unavailable: [] },
    robustness: { turns: 20, chat_errors: 0, judge_failed: 0, empty: 0, fallback: 0 },
    safe: QUALITY, frei: QUALITY,
  };
}

function vergleich(over: Partial<EngineComparison> = {}): EngineComparison {
  return {
    engines: { agent: summary(1), pattern: summary(2) },
    rules: { R2a: { erfuellt: true, gruende: ['stabiler', 'billiger'], d_agreement: 0.12,
                    kosten_faktor: 0.6, p50_faktor: 0.9 } },
    currency: 'USD',
    conditions: [{
      provider: 'openai', chat_model: 'gpt-6-luna', judge_model: 'gpt-4o-mini',
      master_skill: { enabled: true, sha256: 'abc123def456' },
      agent_limits: { max_iterations: 20, deadline_s: 300, token_budget: 400000 },
      runs: ['eval-m1', 'eval-m2', 'eval-a1'],
    }],
    runs: [],
    warnings: [],
    ...over,
  };
}

@Component({
  selector: 'studio-compare-host',
  imports: [EvalCompareComponent],
  template: '<studio-eval-compare [runIds]="ids()" (dismiss)="closed = true" />',
})
class HostComponent {
  readonly ids = signal<readonly string[]>(['eval-m1', 'eval-m2', 'eval-a1']);
  closed = false;
}

interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(
  payload: EngineComparison | null = vergleich(), locale = 'de',
): Promise<Harness> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()),
                provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === URL);
  if (payload === null) {
    req.flush({ detail: 'Ein Vergleich braucht mindestens zwei verschiedene Läufe.' },
              { status: 422, statusText: 'x' });
  } else {
    req.flush(payload);
  }
  await settle(h);
  return h;
}

const text = (h: Harness): string => (h.el.textContent ?? '').replace(/\s+/g, ' ');

describe('EvalCompareComponent (ST-7c)', () => {
  it('fragt den Vergleich der gewählten Läufe an', async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()),
                  provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(HostComponent);
    await fixture.whenStable();
    const req = TestBed.inject(HttpTestingController).expectOne((r) => r.url === URL);
    expect(req.request.params.get('ids')).toBe('eval-m1,eval-m2,eval-a1');
    req.flush(vergleich());
  });

  it('sagt beim Rechnen, dass es dauern kann', async () => {
    // Die Textnähe vergleicht jede Antwort mit jeder — sechs Läufe brauchten
    // gemessen 14 s. Ohne Satz sähe das wie ein Hänger aus.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()),
                  provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(HostComponent);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.cmp-computing')?.textContent).toContain('einige Sekunden');
    TestBed.inject(HttpTestingController).expectOne((r) => r.url === URL).flush(vergleich());
    await new Promise((resolve) => setTimeout(resolve, 0));
    await fixture.whenStable();
    // Leer statt weg: die Region bleibt für das nächste Laden (Paket 4b, B1).
    expect(el.querySelector('.cmp-computing')?.textContent).toBe('');
  });

  it('sagt auch ein neues Rechnen in derselben Region an', async () => {
    // Ändert sich die Auswahl, rechnet das offene Panel neu. Die Zeile entstand
    // dabei jedes Mal neu — und eine Live-Region, die mit ihrem Text entsteht,
    // sagen Screenreader oft nicht an.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()),
                  provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(HostComponent);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const http = TestBed.inject(HttpTestingController);
    http.expectOne((r) => r.url === URL).flush(vergleich());
    await new Promise((resolve) => setTimeout(resolve, 0));
    await fixture.whenStable();
    const region = el.querySelector<HTMLElement>('.cmp-computing[role="status"]');
    expect(region?.textContent).toBe('');

    fixture.componentInstance.ids.set(['eval-m1', 'eval-a1']);
    await fixture.whenStable();

    expect(el.querySelector('.cmp-computing')).toBe(region);
    expect(region!.textContent).toContain('einige Sekunden');
    http.expectOne((r) => r.url === URL).flush(vergleich());
  });

  it('stellt je Maschine eine Spalte, die Muster-Maschine zuerst', async () => {
    const h = await mount();
    const koepfe = Array.from(h.el.querySelectorAll('.cmp-table thead th'))
      .map((th) => th.textContent?.trim());
    expect(koepfe).toEqual(['Kennzahl', 'Muster-Maschine (2 Läufe)', 'Agent-Schleife (1 Lauf)']);
    const zeile = Array.from(h.el.querySelectorAll('.cmp-table tbody tr'))
      .find((tr) => tr.querySelector('th')?.textContent?.includes('Übereinstimmung'))!;
    expect(zeile.querySelectorAll('td')[0].textContent?.trim()).toBe(`80${NBSP}%`);
  });

  it('nennt das Urteil der Regel R2(a) mit seinen Gründen', async () => {
    const h = await mount();
    expect(h.el.querySelector('.cmp-rule')?.textContent?.replace(/\s+/g, ' '))
      .toContain('messbaren Vorteil: stabiler und billiger');
  });

  it('sagt, wenn R2(a) mangels beider Maschinen nicht rechenbar ist', async () => {
    const h = await mount(vergleich({ engines: { agent: summary(2) }, rules: {} }));
    expect(h.el.querySelector('.cmp-rule')?.textContent).toContain('beide Maschinen');
  });

  it('übersetzt die Warnungen des Servers', async () => {
    const h = await mount(vergleich({
      warnings: [
        { code: 'not_done', run: 'eval-x', status: 'running' },
        { code: 'engine_unknown', run: 'eval-alt' },
        { code: 'price_missing', models: ['gpt-6-luna'] },
        { code: 'conditions_differ' },
        { code: 'master_skill_off', runs: ['eval-a2'] },
      ],
    }));
    const hinweise = Array.from(h.el.querySelectorAll('.cmp-warnings li'))
      .map((li) => li.textContent?.trim());
    expect(hinweise).toEqual([
      'eval-x ist nicht fertig (läuft) und zählt nicht.',
      'Bei eval-alt ist die Maschine unbekannt — der Lauf zählt nicht.',
      'Kein Preis gepflegt für gpt-6-luna — die Kostenzeile bleibt leer.',
      'Die Läufe liefen unter verschiedenen Bedingungen — siehe unten.',
      'Ohne Master-Skill gemessen: eval-a2 — der Agent lief ohne seine Anleitung.',
    ]);
  });

  it('nennt die Messbedingungen je Gruppe von Läufen', async () => {
    const h = await mount();
    const bedingung = h.el.querySelector('.cmp-conditions li')?.textContent?.replace(/\s+/g, ' ');
    expect(bedingung).toContain('eval-m1, eval-m2 und eval-a1');
    expect(bedingung).toContain('gpt-6-luna');
    expect(bedingung).toContain('Master-Skill an (abc123def456)');
  });

  it('zeigt eine Abweisung des Servers mit seinem Satz', async () => {
    const h = await mount(null);
    expect(text(h)).toContain('mindestens zwei verschiedene Läufe');
    expect(h.el.querySelector('.cmp-table')).toBeNull();
  });

  it('liest neu, wenn sich die Auswahl ändert', async () => {
    const h = await mount();
    h.fixture.componentInstance.ids.set(['eval-a1', 'eval-a2']);
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === URL);
    expect(req.request.params.get('ids')).toBe('eval-a1,eval-a2');
    req.flush(vergleich({ engines: { agent: summary(2) }, rules: {} }));
    await settle(h);
    expect(h.el.querySelectorAll('.cmp-table thead th')).toHaveLength(2);
  });

  it('lässt sich schließen', async () => {
    const h = await mount();
    const zu = Array.from(h.el.querySelectorAll('button'))
      .find((b) => b.textContent?.trim() === 'Vergleich schließen')!;
    zu.click();
    expect(h.fixture.componentInstance.closed).toBe(true);
  });

  it('spricht Englisch', async () => {
    const h = await mount(vergleich(), 'en');
    expect(text(h)).toContain('Pattern engine (2 runs)');
    expect(text(h)).not.toMatch(/[äöüß]/);
  });
});
