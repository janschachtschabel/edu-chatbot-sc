// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import {
  CLEAR_URL, LOGS_URL, mount, rows, settle, submit, log, type,
} from './quality-logs.harness';

describe('QualityLogsComponent — löschen', () => {
  it('asks before deleting one turn, then deletes it', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.ql-arm')!.click();
    await h.fixture.whenStable();
    h.http.verify(); // arming alone deletes nothing

    h.el.querySelector<HTMLButtonElement>('.ql-confirm')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === `${LOGS_URL}/1` && r.method === 'DELETE').flush({});
    await settle(h);

    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 1, logs: [log(2)] });
    await settle(h);
    expect(rows(h)).toHaveLength(1);
  });

  it('deletes nothing when the question is dismissed', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.ql-arm')!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>('.ql-cancel')!.click();
    await h.fixture.whenStable();

    h.http.verify();
    expect(h.el.querySelector('.ql-confirm')).toBeNull();
  });

  it('says whether a bulk delete hits the filtered rows or everything', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.ql-clear')!.click();
    await h.fixture.whenStable();
    expect(h.el.querySelector('.ql-question')!.textContent).toContain('ALLE');

    h.el.querySelector<HTMLButtonElement>('.ql-cancel')!.click();
    await h.fixture.whenStable();

    type(h, '#ql-pattern', 'M15');
    await submit(h);
    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 1, logs: [log(2)] });
    await settle(h);

    h.el.querySelector<HTMLButtonElement>('.ql-clear')!.click();
    await h.fixture.whenStable();
    const question = h.el.querySelector('.ql-question')!.textContent!;
    expect(question).toContain('M15');
    expect(question).not.toContain('ALLE');
  });

  it('sends the bulk delete with the filters that are actually applied', async () => {
    const h = await mount();
    type(h, '#ql-intent', 'I02');
    await submit(h);
    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 1, logs: [log(1)] });
    await settle(h);

    h.el.querySelector<HTMLButtonElement>('.ql-clear')!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>('.ql-confirm')!.click();
    await h.fixture.whenStable();

    const req = h.http.expectOne((r) => r.url === CLEAR_URL);
    expect(req.request.params.get('intent_id')).toBe('I02');
    // `confirm=true` is only for wiping every scope unfiltered — see quality-api.
    expect(req.request.params.has('confirm')).toBe(false);
    req.flush({ deleted: 2 });
    await settle(h);

    h.http.expectOne((r) => r.url === LOGS_URL).flush({ count: 0, logs: [] });
    await settle(h);
    expect(h.el.querySelector('.ql-status')!.textContent).toContain('2');
  });

  it('reports a failed delete and keeps the list standing', async () => {
    const h = await mount();
    h.el.querySelector<HTMLButtonElement>('.ql-arm')!.click();
    await h.fixture.whenStable();
    h.el.querySelector<HTMLButtonElement>('.ql-confirm')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.method === 'DELETE')
      .flush({ detail: 'Zeile ist gesperrt.' }, { status: 409, statusText: 'x' });
    await settle(h);

    expect(h.el.querySelector('.ql-error')!.textContent).toContain('gesperrt');
    expect(rows(h)).toHaveLength(2);
  });
});
