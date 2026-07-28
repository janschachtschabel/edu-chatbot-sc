// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { EvalPatternUsageComponent } from './eval-pattern-usage.component';

const USAGE_URL = '/studio/api/eval/analytics/pattern-usage';

const USAGE = {
  triples: [
    { pattern_id: 'M04', intent_id: 'I01', persona_id: 'P-LEH', count: 12, avg_conf: 0.91 },
    { pattern_id: 'M15', intent_id: 'I03', persona_id: 'P-AND', count: 5, avg_conf: 0.62 },
    { pattern_id: '', intent_id: '', persona_id: '', count: 2, avg_conf: null },
  ],
  by_pattern: [{ pattern_id: 'M04', count: 12 }, { pattern_id: 'M15', count: 5 }],
  by_intent: [{ intent_id: 'I01', count: 12 }, { intent_id: 'I03', count: 5 }],
  total: 19,
  scope: 'all',
};

interface Harness {
  fixture: ComponentFixture<EvalPatternUsageComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let h: Harness;

async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(payload: Record<string, unknown> | null = USAGE): Promise<void> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(EvalPatternUsageComponent);
  const http = TestBed.inject(HttpTestingController);
  h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === USAGE_URL);
  if (payload === null) req.flush({ detail: 'kaputt' }, { status: 500, statusText: 'x' });
  else req.flush(payload);
  await settle();
}

const text = (): string => h.el.textContent ?? '';
const lastQuery = (): URLSearchParams =>
  new URLSearchParams(h.http.match(() => true).at(-1)?.request.params.toString() ?? '');

describe('EvalPatternUsageComponent', () => {
  beforeEach(() => {
    h = undefined as unknown as Harness;
  });

  it('reads the whole window for every scope by default', async () => {
    await mount();
    expect(text()).toContain('19');   // total turns
    expect(text()).toContain('M04');
    expect(text()).toContain('I01');
  });

  it('feeds both distributions to the shared bar table', async () => {
    await mount();
    const captions = Array.from(h.el.querySelectorAll('caption'))
      .map((c) => c.textContent?.trim() ?? '');

    // Reused rather than re-drawn: `QualityBarsComponent` already renders "a key
    // with a number" as a table with a hidden bar.
    expect(captions.some((c) => c.includes('Pattern'))).toBe(true);
    expect(captions.some((c) => c.includes('Intent'))).toBe(true);
  });

  it('re-reads when the scope changes, and sends it', async () => {
    await mount();
    const select = h.el.querySelector<HTMLSelectElement>('#epu-scope')!;
    select.value = 'eval';
    select.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === USAGE_URL);
    expect(req.request.params.get('scope')).toBe('eval');
    req.flush({ ...USAGE, scope: 'eval' });
    await settle();
    h.http.verify();
  });

  it('sends a since floor only once one is set', async () => {
    await mount();
    expect(lastQuery().has('since')).toBe(false);

    const field = h.el.querySelector<HTMLInputElement>('#epu-since')!;
    expect(field.type).toBe('date');   // platform native, no datepicker dependency
    field.value = '2026-07-01';
    field.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === USAGE_URL);
    expect(req.request.params.get('since')).toBe('2026-07-01');
    req.flush(USAGE);
    await settle();
  });

  it('names an unclassified triple instead of showing a blank row', async () => {
    await mount();
    // The third triple has empty ids — a blank row reads as a rendering fault.
    expect(text()).toContain('(ohne)');
  });

  it('leaves out a confidence it does not have', async () => {
    await mount();
    expect(text()).toContain('0,91');
    // `avg_conf: null` means no turn carried one, not 0.
    const cells = Array.from(h.el.querySelectorAll('tbody td'))
      .map((c) => c.textContent?.trim() ?? '');
    expect(cells).toContain('–');
  });

  it('says the log is empty rather than drawing empty tables', async () => {
    await mount({ triples: [], by_pattern: [], by_intent: [], total: 0, scope: 'all' });

    expect(text()).toContain('Noch keine Turns');
  });

  it('shows why the numbers could not be read', async () => {
    await mount(null);
    expect(text()).toContain('kaputt');
  });
});
