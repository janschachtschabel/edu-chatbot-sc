// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { EvalRunsComponent } from './eval-runs.component';

const RUNS_URL = '/studio/api/eval/runs';
const QLOGS_URL = '/studio/api/eval/quality-logs';

/** Mirrors the component's own constant; a test may not import a private. */
const POLL_MS = 3000;

function run(id: string, over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id,
    created_at: '2026-07-24T10:00:00Z',
    completed_at: null,
    status: 'done',
    mode: 'golden',
    config_slug: 'wlo/v1',
    total_turns: 12,
    avg_score: 0.83,
    personas: ['P01'],
    intents: ['I02'],
    error_message: null,
    target_turns: 12,
    current_activity: 'Fertig',
    ...over,
  };
}

const RUNNING = run('r-live', {
  status: 'running', total_turns: 4, target_turns: 10,
  current_activity: 'Gold-Flow 2 von 5', avg_score: null,
});

@Component({
  selector: 'studio-eval-runs-host',
  imports: [EvalRunsComponent],
  template: '<studio-eval-runs (runChange)="opened = $event" />',
})
class HostComponent {
  opened = '';
}

interface Harness {
  fixture: ComponentFixture<HostComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
  await h.fixture.whenStable();
}

async function mount(runs: Record<string, unknown>[] = [run('r1')]): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne((r) => r.url === RUNS_URL).flush({ runs });
  await settle(h);
  return h;
}

const rows = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>('.er-row'));

describe('EvalRunsComponent', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('reads the newest runs', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(HostComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    const req = http.expectOne((r) => r.url === RUNS_URL);
    expect(req.request.params.get('limit')).toBe('50');
    req.flush({ runs: [run('r1')] });
  });

  it('shows how far a running run has got, against its target', async () => {
    const h = await mount([RUNNING]);
    const row = rows(h)[0];
    expect(row.textContent).toContain('4');
    expect(row.textContent).toContain('10');
    expect(row.textContent).toContain('Gold-Flow 2 von 5');
  });

  it('re-reads while a run is in flight and stops once it is done', async () => {
    const h = await mount([RUNNING]);

    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run('r-live')] });
    await settle(h);

    // Now nothing is running, so no further poll may be scheduled.
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it('does not poll at all when no run is in flight', async () => {
    const h = await mount([run('r1')]);
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    h.http.verify();
  });

  it('shows a failed poll and keeps the last good list', async () => {
    // ALT swallowed poll errors, so a dead backend kept claiming "läuft".
    const h = await mount([RUNNING]);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    h.http.expectOne((r) => r.url === RUNS_URL)
      .flush({ detail: 'Datenbank weg.' }, { status: 503, statusText: 'x' });
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Datenbank weg.');
    expect(rows(h)).toHaveLength(1);
  });

  it('says why a run failed, in the row', async () => {
    // "fehlgeschlagen" alone does not tell anyone what to do next. This message
    // is verbatim from the backend's stale-run sweep (`eval_service.py`, the
    // `UPDATE eval_runs SET status='failed'` on start), and a reaped run leaves
    // no other trace — the row is the only place it surfaces.
    const h = await mount([run('r-gen', {
      status: 'failed', mode: 'both',
      error_message: 'stale running-Run beim Start-Check abgeräumt',
    })]);
    expect(rows(h)[0].textContent).toContain('fehlgeschlagen');
    expect(h.el.textContent).toContain('beim Start-Check abgeräumt');
  });

  it('opens a run as a real button', async () => {
    const h = await mount([run('r1')]);
    expect(rows(h)[0].tagName).toBe('BUTTON');
    rows(h)[0].click();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.opened).toBe('r1');
  });

  it('asks before deleting one run, then deletes it', async () => {
    const h = await mount([run('r1'), run('r2')]);
    h.el.querySelector<HTMLButtonElement>('.er-arm')!.click();
    await h.fixture.whenStable();
    h.http.verify(); // arming deletes nothing

    h.el.querySelector<HTMLButtonElement>('.er-confirm')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === `${RUNS_URL}/r1` && r.method === 'DELETE')
      .flush({ deleted: 'r1' });
    await settle(h);

    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run('r2')] });
    await settle(h);
    expect(rows(h)).toHaveLength(1);
  });

  it('refuses to offer a delete for a run that is still going', async () => {
    // The endpoint answers 409 for a running run; an enabled button would make
    // the error message the way to find that out.
    const h = await mount([RUNNING]);
    expect(h.el.querySelector<HTMLButtonElement>('.er-arm')!.disabled).toBe(true);
  });

  it('names what a bulk delete will hit and only confirms an unrestricted one', async () => {
    const h = await mount([run('r1')]);
    h.el.querySelector<HTMLButtonElement>('.er-bulk')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.er-question')!.textContent).toContain('ALLE');

    h.el.querySelector<HTMLButtonElement>('.er-confirm')!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === RUNS_URL && r.method === 'DELETE');
    expect(req.request.params.get('confirm')).toBe('true');
    req.flush({ deleted: 3 });
    await settle(h);

    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [] });
    await settle(h);
    expect(h.el.querySelector('.er-status')!.textContent).toContain('3');
  });

  it('restricts the bulk delete to a status when one is chosen', async () => {
    const h = await mount([run('r1')]);
    const select = h.el.querySelector<HTMLSelectElement>('#er-status')!;
    expect(select.labels?.[0]?.textContent).toContain('Status');
    select.value = 'failed';
    select.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();

    h.el.querySelector<HTMLButtonElement>('.er-bulk')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.er-question')!.textContent).toContain('fehlgeschlagen');

    h.el.querySelector<HTMLButtonElement>('.er-confirm')!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === RUNS_URL && r.method === 'DELETE');
    expect(req.request.params.get('status')).toBe('failed');
    expect(req.request.params.has('confirm')).toBe(false);
    req.flush({ deleted: 1 });
    await settle(h);
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [] });
    await settle(h);
  });

  it('clears the quality logs an eval wrote, after asking', async () => {
    const h = await mount([run('r1')]);
    h.el.querySelector<HTMLButtonElement>('.er-clear-logs')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.er-question')!.textContent).toContain('Quality-Logs');

    h.el.querySelector<HTMLButtonElement>('.er-confirm')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === QLOGS_URL && r.method === 'DELETE').flush({ deleted: 40 });
    await settle(h);
    expect(h.el.querySelector('.er-status')!.textContent).toContain('40');
  });

  it('says an installation without runs is empty, and how it fills', async () => {
    const h = await mount([]);
    expect(h.el.querySelector('.as-line')!.textContent).toContain('Gold-Flow');
  });

  it('re-reads on demand', async () => {
    const h = await mount([run('r1')]);
    h.el.querySelector<HTMLButtonElement>('.er-reload')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [run('r1')] });
    await settle(h);
  });

/**
 * B6: the confirmation appears under the button that armed it and the focus does
 * not move, so without a live region a screen reader learns nothing before the
 * second click. `role="alert"` carries the QUESTION only — a container that also
 * held the buttons would re-announce the whole thing every time a button label
 * flips to "Wird gelöscht …" (the trap A3 documented for the cost paragraph).
 */
  it('announces the confirmation question', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.er-arm')!.click();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('.er-danger [role="alert"]');
    expect(alert?.textContent).toContain('löschen');
    expect(alert?.querySelector('button')).toBeNull();
  });
});
