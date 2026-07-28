// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { QualityMatrixComponent } from './quality-matrix.component';
import type { LogFilters, QualityScope } from '../core/quality-api.service';

const MATRIX_URL = '/studio/api/quality/matrix';

/**
 * Two cells that do NOT share a row or a column, so the derived axes are
 * 2 personas × 2 intents and exactly two pairs have no samples.
 */
const MATRIX = {
  scope: 'all',
  total_turns: 13,
  cells: [
    {
      persona_id: 'P01', intent_id: 'I02', top_pattern: 'M04',
      top_pattern_count: 8, total_count: 10, share: 0.8,
      alternatives: [{ pattern_id: 'M15', count: 2 }],
    },
    {
      persona_id: 'P02', intent_id: 'I05', top_pattern: 'M15',
      top_pattern_count: 3, total_count: 3, share: 1,
      alternatives: [],
    },
  ],
};

@Component({
  selector: 'studio-matrix-host',
  imports: [QualityMatrixComponent],
  template: '<studio-quality-matrix [scope]="scope()" (drill)="last = $event" />',
})
class HostComponent {
  readonly scope = signal<QualityScope>('all');
  last: LogFilters | null = null;
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

async function mount(matrix: object = MATRIX): Promise<Harness> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(HostComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne((r) => r.url === MATRIX_URL).flush(matrix);
  await settle(h);
  return h;
}

const cellButtons = (h: Harness): HTMLButtonElement[] =>
  Array.from(h.el.querySelectorAll<HTMLButtonElement>('.qm-cell'));

describe('QualityMatrixComponent', () => {
  it('reads the matrix for the scope, with a min-count', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(HostComponent);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();

    const req = http.expectOne((r) => r.url === MATRIX_URL);
    expect(req.request.params.get('scope')).toBe('all');
    expect(req.request.params.get('min_count')).toBe('1');
    req.flush(MATRIX);
  });

  it('makes every populated cell a real button', async () => {
    // ALT rendered each cell as `<td onClick>`: the whole grid was unreachable
    // without a mouse, and no cell could be activated with Enter or Space.
    const h = await mount();
    const cells = cellButtons(h);
    expect(cells).toHaveLength(2);
    for (const cell of cells) expect(cell.tagName).toBe('BUTTON');
  });

  it('shows the competing patterns as text, not only in a tooltip', async () => {
    // ALT put the alternatives in `title=` only — invisible to keyboard and
    // touch users, and never announced by a screen reader on the cell itself.
    const h = await mount();
    const cell = cellButtons(h)[0];
    expect(cell.textContent).toContain('M15');
    expect(cell.textContent).toContain('2');
    expect(cell.getAttribute('title')).toBeNull();
  });

  it('names the persona and the intent inside the cell button', async () => {
    // A button reached by keyboard announces its own content, and "M04 80 %"
    // alone does not say which pair it belongs to. The table headers do not
    // reach the button's accessible name.
    const h = await mount();
    expect(cellButtons(h)[0].textContent).toContain('P01');
    expect(cellButtons(h)[0].textContent).toContain('I02');
  });

  it('drills into the intent of the clicked cell', async () => {
    // Intent only, deliberately: there is no persona filter on /quality/logs,
    // so a persona-scoped drill would silently show more turns than it claims.
    const h = await mount();
    cellButtons(h)[1].click();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.last).toEqual({ intentId: 'I05' });
  });

  it('marks a pair with no samples and offers nothing to click', async () => {
    const h = await mount();
    const empty = Array.from(h.el.querySelectorAll('.qm-none'));
    expect(empty).toHaveLength(2);
    for (const cell of empty) expect(cell.querySelector('button')).toBeNull();
  });

  it('gives the grid row and column headers', async () => {
    const h = await mount();
    const cols = Array.from(h.el.querySelectorAll('th[scope="col"]')).map((t) => t.textContent);
    const rows = Array.from(h.el.querySelectorAll('th[scope="row"]')).map((t) => t.textContent);
    expect(cols.join(' ')).toContain('I02');
    expect(cols.join(' ')).toContain('I05');
    expect(rows).toHaveLength(2);
  });

  it('re-reads when the min-count is raised', async () => {
    const h = await mount();
    const input = h.el.querySelector<HTMLInputElement>('#qm-min')!;
    expect(input.labels?.[0]?.textContent).toContain('Samples');

    input.value = '5';
    input.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === MATRIX_URL);
    expect(req.request.params.get('min_count')).toBe('5');
    req.flush({ scope: 'all', total_turns: 13, cells: [] });
    await settle(h);
  });

  it('refuses a min-count below one instead of asking for min_count=0', async () => {
    const h = await mount();
    const input = h.el.querySelector<HTMLInputElement>('#qm-min')!;

    input.value = '5';
    input.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === MATRIX_URL).flush(MATRIX);
    await settle(h);

    input.value = '0';
    input.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === MATRIX_URL);
    expect(req.request.params.get('min_count')).toBe('1');
    req.flush(MATRIX);
    await settle(h);
  });

  it('does not re-fetch when a keystroke leaves the threshold unchanged', async () => {
    // Typing "0" while the value is already the clamped minimum changes nothing,
    // and a request that cannot return anything new should not be sent.
    const h = await mount();
    const input = h.el.querySelector<HTMLInputElement>('#qm-min')!;
    input.value = '0';
    input.dispatchEvent(new Event('input'));
    await h.fixture.whenStable();
    h.http.verify();
  });

  it('names the threshold that produced an empty matrix', async () => {
    // "Keine Daten" would be a lie: the data may exist below the threshold.
    const h = await mount({ scope: 'production', total_turns: 13, cells: [] });
    // Asserted on the empty message itself, not the panel: the threshold input's
    // own label contains the word too, which would make a text sweep pass here
    // even with a bare "Keine Daten".
    const message = h.el.querySelector('.as-line')!.textContent!;
    expect(message).toContain('Min-Samples');
    expect(message).toContain('1');
  });

  it('re-reads on demand, because turns keep arriving while the page is open', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.qm-reload')!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === MATRIX_URL);
    expect(req.request.params.get('min_count')).toBe('1');
    req.flush(MATRIX);
    await settle(h);
  });

  it('re-reads when the scope changes', async () => {
    const h = await mount();
    h.fixture.componentInstance.scope.set('eval');
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === MATRIX_URL);
    expect(req.request.params.get('scope')).toBe('eval');
    req.flush(MATRIX);
    await settle(h);
  });

  it('reports a failed read and keeps the grid it already had', async () => {
    const h = await mount();
    h.fixture.componentInstance.scope.set('eval');
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === MATRIX_URL)
      .flush({ detail: 'Matrix-Query abgebrochen.' }, { status: 504, statusText: 'x' });
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Matrix-Query');
    expect(cellButtons(h)).toHaveLength(2);
  });
});
