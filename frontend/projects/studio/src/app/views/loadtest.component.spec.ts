// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { LoadtestComponent } from './loadtest.component';

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

const RUNS_URL = '/studio/api/loadtest/runs';
const MIX_URL = '/studio/api/loadtest/mix-options';

const MIX = [
  { key: 'wissen', label: 'Wissensfragen', prompt: 'Was ist ein Erklärvideo?' },
  { key: 'lernpfad', label: 'Lernpfade', prompt: 'Baue mir einen Lernpfad.' },
];

// Exactly what `_summary` in services/loadtest.py returns — four keys. The
// earlier fixture invented `peak_rss_mb`/`peak_proc_cpu_pct`, which no backend
// path ever writes (resource sampling was dropped with psutil), and that is why
// the row line rendered "Spitze NaN MB" in the real studio (B5).
const SUMMARY = {
  stable_concurrency: 4, p95_threshold_s: 20, total_requests: 32, total_errors: 0,
};

const PROFILE = {
  stages: [1, 2, 4, 8], requests_per_stage: 8, mix: { wissen: 2 },
  p95_threshold_s: 20, total_requests: 32,
};

const DONE_RUN = {
  id: 'lt-abc123', status: 'completed', created_at: '2026-07-24T18:00:00Z',
  summary: SUMMARY, profile: PROFILE, error: null,
};

const RUNNING_RUN = { ...DONE_RUN, id: 'lt-live99', status: 'running', summary: null };

interface Harness {
  fixture: ComponentFixture<LoadtestComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

function create(): Harness {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(LoadtestComponent);
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

async function mount(runs: unknown[] = [DONE_RUN]): Promise<Harness> {
  const h = create();
  await h.fixture.whenStable();
  h.http.expectOne(RUNS_URL).flush({ runs });
  h.http.expectOne(MIX_URL).flush({ options: MIX });
  await settle(h);
  return h;
}

function startButton(h: Harness): HTMLButtonElement {
  return h.el.querySelector<HTMLButtonElement>('.lt-btn--go')!;
}

async function typeStages(h: Harness, value: string): Promise<void> {
  const input = h.el.querySelector<HTMLInputElement>('#lt-stages')!;
  input.value = value;
  input.dispatchEvent(new Event('input'));
  await h.fixture.whenStable();
}

describe('LoadtestComponent', () => {
  it('names the real cost of the profile before the button is pressed', async () => {
    const h = await mount();
    expect(h.el.querySelector('.lt-cost')!.textContent).toContain('32 echte Chat-Anfragen');
  });

  it('shows what the backend will actually run, not what was typed', async () => {
    // ALT multiplied the typed stage count by requests-per-stage; the backend
    // then dropped everything past the sixth stage and capped 64 at 32.
    const h = await mount();
    await typeStages(h, '1, 2, 4, 8, 16, 32, 64');

    const cost = h.el.querySelector('.lt-cost')!.textContent!;
    expect(cost).toContain('48 echte Chat-Anfragen'); // 6 stages × 8, not 7 × 8
    expect(cost).toContain('1 → 2 → 4 → 8 → 16 → 32');
    expect(h.el.querySelector('.lt-adjust')!.textContent).toContain('6 Stufen');
  });

  it('blocks the start and says why when the profile is too big', async () => {
    const h = await mount();
    await typeStages(h, '1,2,4,8,16,32');
    const rps = h.el.querySelector<HTMLInputElement>('#lt-rps')!;
    rps.value = '60';
    rps.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();

    expect(startButton(h).disabled).toBe(true);
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('200');
  });

  it('blocks the start while any run is in flight, not just the open one', async () => {
    // The backend permits one run at a time and answers 409; ALT only looked at
    // the run it had open, so the usual way to find out was the error message.
    const h = await mount([RUNNING_RUN]);
    expect(startButton(h).disabled).toBe(true);
    expect(h.el.querySelector('.lt-busy')!.textContent).toContain('lt-live99');
  });

  it('posts the effective profile and opens the new run', async () => {
    const h = await mount([]);
    startButton(h).click();
    await h.fixture.whenStable();

    const req = h.http.expectOne(RUNS_URL);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      stages: [1, 2, 4, 8],
      requests_per_stage: 8,
      // The zero-weight category is dropped, not sent as 0.
      mix: { wissen: 2, suche: 2, orientierung: 1 },
      p95_threshold_s: 20,
    });
    req.flush({ id: 'lt-new001', status: 'running', profile: PROFILE });
    await settle(h);

    h.http.expectOne(RUNS_URL).flush({ runs: [{ ...RUNNING_RUN, id: 'lt-new001' }] });
    await settle(h);
    // the detail panel asks for the run it just started
    h.http.expectOne('/studio/api/loadtest/runs/lt-new001').flush({
      ...DONE_RUN, id: 'lt-new001', status: 'running', stages: [], resource_samples: [],
      summary: null, finished_at: null,
    });
    await settle(h);
    expect(h.fixture.componentInstance.selected()).toBe('lt-new001');
  });

  it('reports a refused start in the backend words', async () => {
    const h = await mount([]);
    startButton(h).click();
    await h.fixture.whenStable();
    h.http.expectOne(RUNS_URL).flush(
      { detail: 'Lasttest ist auf dieser Instanz deaktiviert (BOERDI_ALLOW_LOADTEST).' },
      { status: 403, statusText: 'Forbidden' },
    );
    await settle(h);

    const error = h.el.querySelector('.lt-error')!;
    expect(error.textContent).toContain('BOERDI_ALLOW_LOADTEST');
    expect(error.textContent).not.toContain('HTTP 403'); // never the transport envelope
  });

  it('asks before deleting a run and does nothing when cancelled', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.lt-del')!.click();
    await h.fixture.whenStable();
    expect(h.el.textContent).toContain('Diesen Lauf mit allen Messwerten löschen');

    h.el.querySelectorAll<HTMLButtonElement>('.lt-confirm .lt-btn')[1].click();
    await h.fixture.whenStable();
    h.http.verify();
  });

  it('deletes the confirmed run and re-reads the list', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.lt-del')!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>('.lt-del-yes')!.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne(`${RUNS_URL}/lt-abc123`);
    expect(req.request.method).toBe('DELETE');
    req.flush({ deleted: 'lt-abc123' });
    await settle(h);
    h.http.expectOne(RUNS_URL).flush({ runs: [] });
  });

  it('keeps a running run from being deleted at all', async () => {
    // The endpoint answers 409; offering the button anyway is an invitation to
    // an error message.
    const h = await mount([RUNNING_RUN]);
    expect(h.el.querySelector<HTMLButtonElement>('.lt-del')!.disabled).toBe(true);
  });

  it('says an empty list is empty, and how something gets into it', async () => {
    const h = await mount([]);
    expect(h.el.textContent).toContain('Noch kein Lasttest gelaufen');
  });

  it('keeps the form usable when only the mix categories fail to load', async () => {
    const h = create();
    await h.fixture.whenStable();
    h.http.expectOne(RUNS_URL).flush({ runs: [] });
    h.http.expectOne(MIX_URL).flush('x', { status: 500, statusText: 'Server Error' });
    await settle(h);

    expect(h.el.querySelector('.lt-mix-state [role="alert"]')).not.toBeNull();
    expect(h.el.querySelector('#lt-stages')).not.toBeNull();
  });

  it('labels every mix weight with its category', async () => {
    const h = await mount();
    for (const option of MIX) {
      const input = h.el.querySelector<HTMLInputElement>(`#lt-mix-${option.key}`)!;
      const label = h.el.querySelector(`label[for="lt-mix-${option.key}"]`)!;
      expect(input).not.toBeNull();
      expect(label.textContent).toContain(option.label);
    }
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
    h.el.querySelector<HTMLButtonElement>('.lt-del')!.click();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('.lt-confirm [role="alert"]');
    expect(alert?.textContent).toContain('nicht rückgängig');
    expect(alert?.querySelector('button')).toBeNull();
  });

  /**
   * B5: the studio showed "Spitze NaN MB" for every finished run. `_summary` in
   * services/loadtest.py returns four keys and none of them is a resource peak —
   * the psutil sampling ALT had was dropped in the port, on purpose. Only the
   * fixtures kept the fields alive, so neither the type checker nor the suite
   * ever saw it. Now the view says what it does not measure.
   */
  it('never prints a resource peak the backend does not measure', async () => {
    const h = await mount();
    const line = h.el.querySelector('.lt-run-meta, .lt-summary, li')!.textContent ?? '';
    expect(h.el.textContent).not.toContain('NaN');
    expect(h.el.textContent).not.toContain('Spitze');
    expect(line + (h.el.textContent ?? '')).toContain('stabil bis 4 parallel');
  });
});
