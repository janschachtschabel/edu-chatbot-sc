// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { QualityOverviewComponent } from './quality-overview.component';
import type { QualityScope } from '../core/quality-api.service';

const STATS_URL = '/studio/api/quality/stats';

/** German typography puts a NO-BREAK space before the percent sign. */
const NBSP = '\u00A0';

const STATS = {
  scope: 'all',
  total_turns: 120,
  pattern_distribution: { M04: 60, M15: 40 },
  intent_distribution: { I02: 70, I05: 30 },
  avg_confidence: 0.812,
  degradation_rate: 0.025,
  empty_entity_rate: 0.1,
  avg_response_length: 431,
};

@Component({
  selector: 'studio-overview-host',
  imports: [QualityOverviewComponent],
  template: '<studio-quality-overview [scope]="scope()" />',
})
class HostComponent {
  readonly scope = signal<QualityScope>('all');
}

interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

async function mount(stats: object = STATS): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne((r) => r.url === STATS_URL).flush(stats);
  await settle(h);
  flushDiagnosis(h);
  await settle(h);
  return h;
}

/**
 * The hosted diagnosis blocks read three endpoints of their own. Matched rather
 * than expected: they are created inside `@if (!isEmpty())`, so an empty or
 * failed stats answer means there is nothing to flush.
 */
function flushDiagnosis(h: Harness): void {
  for (const path of ['degradations', 'empty-entities', 'low-confidence']) {
    for (const req of h.http.match((r) => r.url === `/studio/api/quality/${path}`)) {
      req.flush({ scope: 'all', total: 0, groups: [], turns: [], max_confidence: 0.6 });
    }
  }
}

describe('QualityOverviewComponent', () => {
  it('shows the headline numbers in German units', async () => {
    const h = await mount();
    const text = h.el.textContent!;
    expect(text).toContain('120');
    expect(text).toContain('0,81'); // German decimal comma, not 0.812
    // A rate is shown as a percentage, and German typography puts a NO-BREAK
    // space before the sign — asserted verbatim so a switch to a plain space
    // (or to en-US) shows up here.
    expect(text).toContain(`2,5${NBSP}%`);
    expect(text).toContain('431');
  });

  it('does not show the two metrics that can never be non-zero', async () => {
    // `phase2_score_gap` and `tight_races` are structurally 0 since Welle E v4.
    // ALT still rendered "Ø Score-Gap" as a live KPI showing a permanent 0,000.
    const h = await mount();
    // Asserted against the KPI labels, not the whole panel: the note below the
    // strip names both metrics on purpose, to say why they are not there.
    const labels = Array.from(h.el.querySelectorAll('.qo-kpi dt')).map((dt) => dt.textContent!);
    expect(labels.some((l) => l.includes('Score-Gap'))).toBe(false);
    expect(labels.some((l) => l.includes('Tight'))).toBe(false);
    expect(labels).toHaveLength(5);
  });

  it('says why the score metrics are missing instead of silently dropping them', async () => {
    const h = await mount();
    expect(h.el.querySelector('.qo-note')!.textContent).toContain('Score-Phase');
  });

  it('renders both distributions with distinguishable names', async () => {
    const h = await mount();
    const captions = Array.from(h.el.querySelectorAll('caption')).map((c) => c.textContent);
    expect(captions).toEqual(['Pattern-Verteilung', 'Intent-Verteilung']);
  });

  it('warns only when a rate is actually above its threshold', async () => {
    const quiet = await mount();
    expect(quiet.el.querySelector('.qo-hints')).toBeNull();

    const loud = await mount({ ...STATS, degradation_rate: 0.22 });
    expect(loud.el.querySelector('.qo-hints')!.textContent).toContain(`22,0${NBSP}%`);
  });

  it('re-reads the stats and the diagnosis blocks on demand', async () => {
    // One button for the whole panel: the three breakdowns below the numbers are
    // part of the same answer, and refreshing half of it would be misleading.
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.qo-reload')!.click();
    await h.fixture.whenStable();

    h.http.expectOne((r) => r.url === STATS_URL).flush(STATS);
    await settle(h);
    flushDiagnosis(h);
    await settle(h);
    h.http.verify(); // one round of reads, nothing left dangling
  });

  it('re-reads when the scope changes', async () => {
    const h = await mount();
    h.fixture.componentInstance.scope.set('eval');
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === STATS_URL);
    expect(req.request.params.get('scope')).toBe('eval');
    req.flush({ ...STATS, total_turns: 4 });
    await settle(h);
    expect(h.el.textContent).toContain('4');
  });

  it('reports a failed read instead of showing an empty dashboard', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(HostComponent);
    const http = TestBed.inject(HttpTestingController);
    const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
    await fixture.whenStable();
    http.expectOne((r) => r.url === STATS_URL)
      .flush({ detail: 'Datenbank nicht erreichbar.' }, { status: 503, statusText: 'x' });
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Datenbank');
  });

  it('says an untouched installation is empty, and how it fills', async () => {
    const h = await mount({ ...STATS, total_turns: 0, pattern_distribution: {},
      intent_distribution: {} });
    expect(h.el.textContent).toContain('Noch keine Turns');
  });
});
