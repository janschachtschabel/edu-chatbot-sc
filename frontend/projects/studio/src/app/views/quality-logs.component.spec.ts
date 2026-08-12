// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import {
  LOGS_URL, PAGE, bare, log, mount, rows, settle, submit, type,
} from './quality-logs.harness';

describe('QualityLogsComponent — lesen', () => {
  it('reads one page for the scope and sends no empty filters', async () => {
    const h = await bare();
    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('limit')).toBe('200');
    expect(req.request.params.get('scope')).toBe('all');
    expect(req.request.params.has('pattern_id')).toBe(false);
    req.flush(PAGE);
    await settle(h);
  });

  it('does not query while someone is still typing', async () => {
    // ALT re-fetched five endpoints on every keystroke, four of which accept
    // nothing but the scope. Here the form decides when the query happens.
    const h = await mount();
    type(h, '#ql-pattern', 'M0');
    await h.fixture.whenStable();
    h.http.verify();
  });

  it('applies the filters when the form is submitted', async () => {
    const h = await mount();
    type(h, '#ql-pattern', 'M15');
    type(h, '#ql-session', 'sess-2');
    await submit(h);

    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('pattern_id')).toBe('M15');
    expect(req.request.params.get('session_id')).toBe('sess-2');
    expect(req.request.params.has('intent_id')).toBe(false);
    req.flush({ count: 1, logs: [log(2)] });
    await settle(h);
    expect(rows(h)).toHaveLength(1);
  });

  it('clears every filter field on reset', async () => {
    const h = await mount();
    type(h, '#ql-pattern', 'M15');
    await submit(h);
    h.http.expectOne((r) => r.url === LOGS_URL).flush(PAGE);
    await settle(h);

    h.el.querySelector<HTMLButtonElement>('.ql-reset')!.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.has('pattern_id')).toBe(false);
    req.flush(PAGE);
    await settle(h);
    expect(h.el.querySelector<HTMLInputElement>('#ql-pattern')!.value).toBe('');
  });

  it('adopts a filter pushed in from the outside, fields included', async () => {
    // The matrix and the diagnosis blocks drill into this panel; the fields have
    // to show what is being filtered, or the list looks arbitrarily short.
    const h = await mount();
    h.fixture.componentInstance.filters.set({ intentId: 'I05' });
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('intent_id')).toBe('I05');
    req.flush(PAGE);
    await settle(h);
    expect(h.el.querySelector<HTMLInputElement>('#ql-intent')!.value).toBe('I05');
  });

  it('offers every row as a button, not a clickable div', async () => {
    const h = await mount();
    expect(rows(h)).toHaveLength(2);
    for (const row of rows(h)) expect(row.tagName).toBe('BUTTON');
  });

  it('marks a degraded turn in text, not only by colour', async () => {
    const h = await mount();
    expect(rows(h)[1].textContent).toContain('Degradation');
    expect(rows(h)[0].textContent).not.toContain('Degradation');
  });

  it('shows the detail of the selected turn and says which row is current', async () => {
    const h = await mount();
    rows(h)[0].click();
    await h.fixture.whenStable();

    expect(rows(h)[0].getAttribute('aria-current')).toBe('true');
    const detail = h.el.querySelector('.qd-panel')!;
    expect(detail.textContent).toContain('Bruchrechnen');
    expect(detail.textContent).toContain('P01');
  });

  it('distinguishes "filter matched nothing" from "there are no logs"', async () => {
    const h = await mount({ count: 0, logs: [] });
    expect(h.el.querySelector('.as-line')!.textContent).toContain('Noch keine');

    type(h, '#ql-pattern', 'M99');
    await submit(h);
    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 0, logs: [] });
    await settle(h);
    expect(h.el.querySelector('.as-line')!.textContent).toContain('Filter');
  });

  it('re-reads on demand without touching the filters', async () => {
    const h = await mount();
    type(h, '#ql-pattern', 'M15');
    await submit(h);
    h.http.expectOne((r) => r.url === LOGS_URL).flush(PAGE);
    await settle(h);

    h.el.querySelector<HTMLButtonElement>('.ql-reload')!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('pattern_id')).toBe('M15');
    req.flush(PAGE);
    await settle(h);
  });

  it('re-reads when the scope changes', async () => {
    const h = await mount();
    h.fixture.componentInstance.scope.set('eval');
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === LOGS_URL);
    expect(req.request.params.get('scope')).toBe('eval');
    req.flush(PAGE);
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
    h.el.querySelector<HTMLButtonElement>('.ql-clear')!.click();
    await h.fixture.whenStable();
    const alert = h.el.querySelector('.ql-danger [role="alert"]');
    expect(alert?.textContent).toContain('löschen');
    expect(alert?.querySelector('button')).toBeNull();
  });

  it('setzt die Zählzeile in die Mehrzahl der Sprache', async () => {
    // Fest verdrahtet las sich das bei genau einem Treffer als „1 Turns".
    const h = await mount({ count: 1, logs: [log(1)] });
    expect(h.el.querySelector('.ql-count')!.textContent!.trim())
      .toBe('1 Turn · neueste zuerst');
  });

  it('benennt den Löschen-Knopf in EINEM Namen statt in zwei Bruchstücken', async () => {
    // Derselbe Fehler, den C1-d4b1 in der Lauf-Liste abgestellt hat: der Name
    // stand als sichtbares Wort plus `<span class="sr">`-Anhang da. Der
    // zugängliche Name beginnt jetzt mit dem sichtbaren Wort (WCAG 2.5.3).
    const h = await mount();
    const arm = h.el.querySelector<HTMLButtonElement>('.ql-arm')!;
    expect(arm.getAttribute('aria-label')).toBe('Löschen — Turn #1');
    expect(arm.querySelector('.sr')).toBeNull();
  });

  it('nimmt Filterfelder und Knöpfe aus dem Katalog', async () => {
    const h = await mount(PAGE, 'en');
    const labels = Array.from(h.el.querySelectorAll('.ql-field')).map((l) =>
      l.textContent!.trim().split('\n')[0].trim());
    expect(labels).toEqual(['Pattern id', 'Intent id', 'Session id']);
    expect(h.el.querySelector('.ql-apply')!.textContent!.trim()).toBe('Filter');
    expect(h.el.querySelector('.ql-clear')!.textContent!.trim()).toBe('Delete all');
  });
});
