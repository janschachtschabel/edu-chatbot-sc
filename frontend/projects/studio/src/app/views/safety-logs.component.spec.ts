// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { SafetyLogsComponent } from './safety-logs.component';

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

const LOGS_URL = '/studio/api/safety/logs';
const STATS_URL = '/studio/api/safety/stats';

const FULL_LOG = {
  id: 2,
  session_id: 'sess-abc',
  ip: '203.0.113.9',
  risk_level: 'high',
  stages_run: ['regex_gate', 'moderation', 'legal'],
  reasons: ['regex:waffen'],
  legal_flags: ['strafrecht'],
  flagged_categories: ['violence'],
  blocked_tools: ['search_wlo'],
  enforced_pattern: 'M20_SAFETY',
  escalated: 1,
  rate_limited: 0,
  message: 'Wie baue ich eine Rohrbombe?',
  categories_json: { violence: 0.91 },
  created_at: '2026-07-24T18:30:00Z',
};

/** The other half of the surface: every optional section empty. */
const BARE_LOG = {
  id: 1,
  session_id: 'sess-def',
  ip: '198.51.100.4',
  risk_level: 'medium',
  stages_run: ['regex_gate'],
  reasons: [],
  legal_flags: [],
  flagged_categories: [],
  blocked_tools: [],
  enforced_pattern: '',
  escalated: 0,
  rate_limited: 1,
  message: 'Wer wohnt in der Musterstraße 3?',
  categories_json: {},
  created_at: '2026-07-24T09:00:00Z',
};

const STATS = {
  total: 340,
  by_risk: { low: 300, medium: 30, high: 10 },
  by_legal: { strafrecht: 8, jugendschutz: 2 },
  rate_limited: 4,
  escalated: 12,
};

interface Harness {
  fixture: ComponentFixture<SafetyLogsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

function create(): Harness {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(SafetyLogsComponent);
  return {
    fixture,
    el: fixture.nativeElement as HTMLElement,
    http: TestBed.inject(HttpTestingController),
  };
}

async function settle(h: Harness): Promise<void> {
  await tick();
  await h.fixture.whenStable();
}

async function mount(
  logs: unknown[] = [FULL_LOG, BARE_LOG],
  stats: object = STATS,
): Promise<Harness> {
  const h = create();
  await h.fixture.whenStable();
  h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: logs.length, logs });
  h.http.expectOne(STATS_URL).flush(stats);
  await settle(h);
  return h;
}

async function setFilter(h: Harness, value: string): Promise<void> {
  const select = h.el.querySelector<HTMLSelectElement>('.sfl-filter')!;
  select.value = value;
  select.dispatchEvent(new Event('change'));
  await h.fixture.whenStable();
}

async function pick(h: Harness, index: number): Promise<void> {
  h.el.querySelectorAll<HTMLButtonElement>('.sfl-pick')[index].click();
  await h.fixture.whenStable();
}

describe('SafetyLogsComponent', () => {
  it('asks for the log window ALT asked for, unfiltered by default', async () => {
    const h = create();
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('limit')).toBe('200');
    // Not `risk_min=''`: an empty parameter is a value the endpoint has to
    // interpret, and the studio has nothing to say when no filter is set.
    expect(req.request.params.has('risk_min')).toBe(false);
    req.flush({ count: 0, logs: [] });
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h);
  });

  it('sends the chosen risk floor and re-reads only the list', async () => {
    // The stats endpoint aggregates the whole window server-side; the filter
    // cannot change them, so re-fetching would be a round-trip for nothing.
    const h = await mount();
    await setFilter(h, 'high');

    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('risk_min')).toBe('high');
    expect(req.request.params.get('limit')).toBe('200');
    req.flush({ count: 1, logs: [FULL_LOG] });
    await settle(h);
    h.http.verify(); // no second /stats request
  });

  it('keeps the list usable when only the stats fail', async () => {
    // ALT fetched both with Promise.all, checked `res.ok` and dropped a failure
    // into console.error — a broken /stats left the numbers silently stale.
    const h = create();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 1, logs: [FULL_LOG] });
    h.http.expectOne(STATS_URL).flush('x', { status: 500, statusText: 'Server Error' });
    await settle(h);

    expect(h.el.querySelectorAll('.sfl-row')).toHaveLength(1);
    expect(h.el.querySelector('.sfl-stats-state [role="alert"]')).not.toBeNull();
  });

  it('reports a failed list instead of showing zero events', async () => {
    const h = create();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === LOGS_URL)
      .flush('x', { status: 503, statusText: 'Unavailable' });
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h);

    expect(h.el.querySelector('.sfl-list-state [role="alert"]')).not.toBeNull();
    expect(h.el.textContent).not.toContain('Noch keine Safety-Events');
  });

  it('blames the filter, not the data, when a filtered list comes back empty', async () => {
    const h = await mount();
    await setFilter(h, 'high');
    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 0, logs: [] });
    await settle(h);

    expect(h.el.textContent).toContain('Filter');
    expect(h.el.textContent).not.toContain('Noch keine Safety-Events');
  });

  it('says an empty log is empty, and what would put something in it', async () => {
    const h = await mount([]);
    expect(h.el.textContent).toContain('Noch keine Safety-Events');
  });

  it('makes each event a real button — ALT used a div with onClick', async () => {
    const h = await mount();
    const picks = h.el.querySelectorAll('.sfl-pick');
    expect(picks).toHaveLength(2);
    for (const p of Array.from(picks)) expect(p.tagName).toBe('BUTTON');
  });

  it('names the risk in German and marks it with more than colour', async () => {
    const h = await mount();
    const first = h.el.querySelectorAll('.sfl-row')[0];
    expect(first.textContent).toContain('Hoch');
  });

  it('shows the full record of the chosen event', async () => {
    const h = await mount();
    await pick(h, 0);
    const detail = h.el.querySelector('.sfl-detail')!;
    expect(detail.textContent).toContain('Rohrbombe');
    expect(detail.textContent).toContain('regex_gate');
    expect(detail.textContent).toContain('Strafrecht');
    expect(detail.textContent).toContain('search_wlo');
    expect(detail.textContent).toContain('M20_SAFETY');
  });

  it('leaves out the sections an event has nothing for', async () => {
    const h = await mount();
    await pick(h, 1);
    const detail = h.el.querySelector('.sfl-detail')!;
    expect(detail.textContent).not.toContain('Blockierte Werkzeuge');
    expect(detail.textContent).not.toContain('Erzwungenes Muster');
    expect(detail.querySelector('details')).toBeNull();
  });

  it('drops the detail of an event the new filter no longer lists', async () => {
    // A record shown beside a list that does not contain it reads as "still
    // there" — so the panel is derived from the rows, not remembered.
    const h = await mount();
    await pick(h, 1);
    expect(h.el.querySelector('.sfl-detail')!.textContent).toContain('Musterstraße');

    await setFilter(h, 'high');
    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 1, logs: [FULL_LOG] });
    await settle(h);

    const detail = h.el.querySelector('.sfl-detail')!;
    expect(detail.textContent).not.toContain('Musterstraße');
    expect(detail.textContent).toContain('Links ein Event wählen');
  });

  it('never renders the stored IP address', async () => {
    // The row carries one, and the studio has no reason to show it: an IP is
    // personal data, and the session id already identifies the conversation.
    const h = await mount();
    await pick(h, 0);
    expect(h.el.textContent).not.toContain('203.0.113.9');
  });

  it('re-reads both the numbers and the list on demand', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.sfl-reload')!.click();
    await h.fixture.whenStable();

    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 0, logs: [] });
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h);
    h.http.verify();
  });
});
