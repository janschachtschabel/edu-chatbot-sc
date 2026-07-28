// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { EvalGoldenStartComponent } from './eval-golden-start.component';

const FLOWS_URL = '/studio/api/eval/gold-flows';
const START_URL = '/studio/api/eval/runs/golden';

const FLOWS = {
  flows: [
    { id: 'GS-1', title: 'Lehrkraft: Material → Lernpfad', persona: 'P-LEH',
      intents: ['I03', 'I04'], turns: [{}, {}, {}, {}] },
    { id: 'GS-2', title: 'Lernende: Bruchrechnung', persona: 'P-LER',
      intents: ['I02'], turns: [{}, {}, {}] },
  ],
  count: 2,
};

interface Harness {
  fixture: ComponentFixture<EvalGoldenStartComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let h: Harness;

async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(payload: Record<string, unknown> | null = FLOWS): Promise<void> {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(EvalGoldenStartComponent);
  const http = TestBed.inject(HttpTestingController);
  h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === FLOWS_URL);
  if (payload === null) req.flush({ detail: 'weg' }, { status: 503, statusText: 'x' });
  else req.flush(payload);
  await settle();
}

const text = (): string => h.el.textContent ?? '';
const button = (label: string): HTMLButtonElement | null =>
  Array.from(h.el.querySelectorAll('button'))
    .find((b) => (b.textContent ?? '').includes(label)) as HTMLButtonElement ?? null;
const box = (id: string): HTMLInputElement =>
  h.el.querySelector<HTMLInputElement>(`#egd-${id}`)!;

/** Arm the inline confirmation. */
async function arm(): Promise<void> {
  button('Gold-Lauf starten')!.click();
  await h.fixture.whenStable();
}

describe('EvalGoldenStartComponent', () => {
  beforeEach(() => {
    h = undefined as unknown as Harness;
  });

  it('lists each flow with what it will do', async () => {
    await mount();
    expect(box('flow-GS-1')).toBeTruthy();
    expect(text()).toContain('Lehrkraft: Material → Lernpfad');
    expect(text()).toContain('P-LEH');
    expect(text()).toContain('4 Turns');
    expect(text()).toContain('Nichts ausgewählt = alle');
  });

  it('counts the turns the selection really fires, not an estimate', async () => {
    await mount();
    // Nothing selected = all 12 gold turns of the two flows (4 + 3).
    expect(text()).toContain('7 Chat-Anfragen');

    box('flow-GS-2').click();
    await h.fixture.whenStable();
    expect(text()).toContain('3 Chat-Anfragen');
  });

  it('names the judge calls the toggle adds', async () => {
    await mount();
    expect(text()).not.toContain('Judge-Aufrufe');

    box('judge').click();
    await h.fixture.whenStable();

    expect(text()).toContain('7 Judge-Aufrufe');
  });

  it('asks before it fires anything', async () => {
    await mount();
    await arm();

    // Armed, nothing sent.
    h.http.verify();
    expect(button('Ja, starten')).toBeTruthy();
  });

  it('starts the selected flows and reports the run', async () => {
    await mount();
    const started: string[] = [];
    h.fixture.componentInstance.started.subscribe((id: string) => started.push(id));
    box('flow-GS-1').click();
    box('judge').click();
    await h.fixture.whenStable();
    await arm();

    button('Ja, starten')!.click();
    await h.fixture.whenStable();
    const req = h.http.expectOne((r) => r.url === START_URL && r.method === 'POST');
    expect(req.request.body).toEqual({
      flow_ids: ['GS-1'], judge: true, config_slug: '',
    });
    req.flush({ run_id: 'eval-g1', status: 'running', warnings: [] });
    await settle();

    expect(started).toEqual(['eval-g1']);
    expect(text()).toContain('eval-g1');
    expect(button('Ja, starten')).toBeNull();
  });

  it('surfaces the flow ids the backend dropped', async () => {
    await mount();
    await arm();
    button('Ja, starten')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === START_URL).flush({
      run_id: 'eval-g1', warnings: ['Unbekannte Flow-IDs ignoriert: [\'GS-99\']'],
    });
    await settle();

    expect(text()).toContain('GS-99');
  });

  it('keeps the selection when the start fails', async () => {
    await mount();
    box('flow-GS-1').click();
    await h.fixture.whenStable();
    await arm();

    button('Ja, starten')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === START_URL).flush(
      { detail: 'Es läuft bereits ein Eval-Lauf.' }, { status: 409, statusText: 'x' },
    );
    await settle();

    expect(text()).toContain('Es läuft bereits ein Eval-Lauf.');
    expect(box('flow-GS-1').checked).toBe(true);
  });

  it('blocks while another run is in flight', async () => {
    await mount();
    h.fixture.componentRef.setInput('busy', true);
    await h.fixture.whenStable();

    expect(button('Gold-Lauf starten')!.disabled).toBe(true);
    expect(text()).toContain('Es läuft schon ein Lauf');
  });

  it('says when no flows are configured instead of offering a dead button', async () => {
    await mount({ flows: [], count: 0 });

    expect(text()).toContain('keine Gold-Flows');
    expect(button('Gold-Lauf starten')!.disabled).toBe(true);
  });

  it('shows why the flow list could not be read', async () => {
    await mount(null);
    expect(text()).toContain('weg');
  });

/**
 * B6: the confirmation appears under the button that armed it and the focus does
 * not move, so without a live region a screen reader learns nothing before the
 * second click. `role="alert"` carries the QUESTION only — a container that also
 * held the buttons would re-announce the whole thing every time a button label
 * flips to "Wird gelöscht …" (the trap A3 documented for the cost paragraph).
 */
  it('announces the confirmation question', async () => {
    await mount();
    await arm();
    const alert = h.el.querySelector('.egd-confirm [role="alert"]');
    expect(alert?.textContent).toContain('starten?');
    expect(alert?.querySelector('button')).toBeNull();
  });
});
