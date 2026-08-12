// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { EvalRunDetailComponent } from './eval-run-detail.component';

const url = (id: string) => `/studio/api/eval/runs/${id}`;

const CELL = (ok: number, total: number) => ({ ok, total });

function goldMetrics(over: Record<string, unknown> = {}) {
  return {
    categories: ['persona', 'intent', 'register', 'structure', 'qr', 'host'],
    totals: { persona: 3, intent: 3, register: 2, structure: 1, qr: 3, host: 1 },
    passed: { persona: 3, intent: 2, register: 2, structure: 0, qr: 3, host: 1 },
    rates: { persona: 1, intent: 0.667, register: 1, structure: 0, qr: 1, host: 1 },
    overall_pass_rate: 0.833, hard_passed: 10, hard_total: 12,
    flows: 2, turns: 3,
    per_turn: [
      {
        flow: 'GS-1', title: 'Suche', turn: 1, message: 'Hallo',
        expected: { persona: 'P-LEH', intent: 'I01', must_offer: 'Material' },
        observed: { persona: 'P-LEH', intent: 'I01', pattern: 'M04', sie: 2, du: 0,
                    cards: 4, idocs: 0, qr: 3 },
        checks: { persona: true, intent: true, register: true, structure: null,
                  qr: true, host: true },
      },
      {
        flow: 'GS-1', title: 'Suche', turn: 2, message: 'Mehr davon',
        expected: { persona: 'P-LEH', intent: 'I01' },
        observed: { persona: 'P-LEH', intent: 'I03', pattern: 'M15' },
        checks: { persona: true, intent: false, register: null, structure: false,
                  qr: true, host: null },
      },
      {
        flow: 'GS-2', title: 'Wissen', turn: 1, message: 'Was ist OER?',
        expected: { persona: 'P-AND', intent: 'I03' },
        observed: { persona: 'P-AND', intent: 'I03', pattern: 'M09' },
        checks: { persona: true, intent: true, register: true, structure: null,
                  qr: true, host: null },
      },
    ],
    per_flow: {
      'GS-1': { title: 'Suche', persona: CELL(2, 2), intent: CELL(1, 2),
                register: CELL(1, 1), structure: CELL(0, 1), qr: CELL(2, 2),
                host: CELL(1, 1) },
      'GS-2': { title: 'Wissen', persona: CELL(1, 1), intent: CELL(1, 1),
                register: CELL(1, 1), structure: CELL(0, 0), qr: CELL(1, 1),
                host: CELL(0, 0) },
    },
    ...over,
  };
}

function detail(over: Record<string, unknown> = {}) {
  return {
    id: 'eval-abc', created_at: '2026-07-26T10:00:00Z',
    completed_at: '2026-07-26T10:04:00Z',
    status: 'done', mode: 'golden', config_slug: 'wlo/v1',
    personas: ['P-LEH'], intents: ['I01'], turns_per_conv: 0,
    judge_model: '', simulator_model: '',
    total_turns: 3, avg_score: 0.833, error_message: null,
    summary: { golden_metrics: goldMetrics(), target_turns: 3 },
    conversations: [
      {
        kind: 'golden', flow_id: 'GS-1', title: 'Suche', persona_id: 'P-LEH',
        intent_id: 'I01', turns: [
          { user: 'Hallo', bot: 'Hier sind vier Materialien.' },
          { user: 'Mehr davon', bot: 'Ich brauche noch das Thema.' },
        ],
      },
      {
        kind: 'golden', flow_id: 'GS-2', title: 'Wissen', persona_id: 'P-AND',
        intent_id: 'I03', turns: [{ user: 'Was ist OER?', bot: 'OER heißt …' }],
      },
    ],
    ...over,
  };
}

interface Harness {
  fixture: ComponentFixture<EvalRunDetailComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let h: Harness;

async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

async function mount(
  payload: Record<string, unknown> | null = detail(), id = 'eval-abc', locale = 'de',
): Promise<void> {
  // jsdom meldet `navigator.language === 'en-US'`; ohne die gemerkte Wahl liefe
  // die deutsche Oberfläche unter diesen Prüfungen auf Englisch.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(EvalRunDetailComponent);
  fixture.componentRef.setInput('runId', id);
  const http = TestBed.inject(HttpTestingController);
  h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  const req = http.expectOne((r) => r.url === url(id));
  if (payload === null) req.flush({ detail: 'Lauf weg.' }, { status: 404, statusText: 'x' });
  else req.flush(payload);
  await settle();
}

const text = (): string => h.el.textContent ?? '';
const button = (label: string): HTMLButtonElement | null =>
  Array.from(h.el.querySelectorAll('button'))
    .find((b) => (b.textContent ?? '').includes(label)) as HTMLButtonElement ?? null;
const rows = (): HTMLTableRowElement[] =>
  Array.from(h.el.querySelectorAll<HTMLTableRowElement>('tbody tr'));

describe('EvalRunDetailComponent', () => {
  beforeEach(() => {
    h = undefined as unknown as Harness;
  });

  it('reads the run named by its input', async () => {
    await mount();
    expect(text()).toContain('eval-abc');
    expect(text()).toContain('Gold-Flows');
    expect(text()).toContain('fertig');
    expect(text()).toContain('26.7.2026');
  });

  it('re-reads when the input names a different run', async () => {
    await mount();
    h.fixture.componentRef.setInput('runId', 'eval-xyz');
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === url('eval-xyz')).flush(detail({ id: 'eval-xyz' }));
    await settle();

    expect(text()).toContain('eval-xyz');
    expect(text()).not.toContain('eval-abc');
  });

  it('shows why a run failed instead of an empty scorecard', async () => {
    await mount(detail({
      status: 'failed', error_message: 'chat backend down',
      summary: { target_turns: 3 },
    }));

    expect(text()).toContain('chat backend down');
    expect(text()).toContain('fehlgeschlagen');
  });

  it('names the hard rate and every category quota', async () => {
    await mount();
    expect(text()).toContain('83');        // overall_pass_rate as a percentage
    expect(text()).toContain('10/12');     // hard_passed/hard_total
    expect(text()).toContain('Tonalität'); // German category label
    expect(text()).toContain('2/3');       // intent passed/total
  });

  it('reports the judge average beside the hard rate, never inside it', async () => {
    await mount(detail({
      summary: { golden_metrics: goldMetrics({ judge_avg: 0.62, judged_turns: 3 }) },
    }));

    expect(text()).toContain('Judge');
    expect(text()).toContain('0,62');
    // The headline is still the deterministic rate (C3's rule).
    expect(text()).toContain('83');
  });

  it('leaves the judge out when the run had none', async () => {
    await mount();
    expect(text()).not.toContain('Judge');
  });

  it('groups the turns by flow and closes each group with its own rate', async () => {
    await mount();
    const labels = rows().map((r) => r.cells[0]?.textContent?.trim() ?? '');

    // Two turns for GS-1, then its summary; one turn for GS-2, then its summary.
    expect(labels.filter((l) => l.includes('Gesamt'))).toHaveLength(2);
    expect(labels[2]).toContain('GS-1');
    expect(labels[2]).toContain('Gesamt');
    // GS-1 hard: persona 2/2 + intent 1/2 + register 1/1 + structure 0/1 + qr 2/2.
    expect(rows()[2].textContent).toContain('6/8');
  });

  it('opens a turn with a focusable button, not a row click', async () => {
    await mount();
    // ALT made the whole <tr> the click target, which no keyboard could reach.
    const opener = rows()[0].querySelector('button')!;
    expect(opener?.tagName).toBe('BUTTON');
    opener.focus();
    expect(document.activeElement).toBe(opener);

    opener.click();
    await h.fixture.whenStable();

    expect(text()).toContain('Hier sind vier Materialien.');  // the bot answer
    expect(text()).toContain('Material');                      // expected.must_offer
    expect(opener.getAttribute('aria-expanded')).toBe('true');
  });

  it('closes an opened turn again', async () => {
    await mount();
    const opener = rows()[0].querySelector('button')!;
    opener.click();
    await h.fixture.whenStable();
    opener.click();
    await h.fixture.whenStable();

    expect(text()).not.toContain('Hier sind vier Materialien.');
  });

  it('falls back to the transcript when a run has no gold metrics', async () => {
    await mount(detail({
      mode: 'generative',
      summary: { target_turns: 3, matrix: {}, pattern_usage: {} },
      conversations: [{
        kind: 'generative', persona_id: 'P-LEH', intent_id: 'I01', turns: [
          { user: 'Suche Wasser', bot: 'Hier sind Materialien.',
            judge: { total: 7.5, notes: 'solide' } },
        ],
      }],
    }));

    expect(text()).toContain('keine Gold-Metriken');
    expect(text()).toContain('Suche Wasser');
    expect(text()).toContain('Hier sind Materialien.');
    expect(text()).toContain('7,5');       // the judge score of that turn
    expect(text()).toContain('solide');
  });

  it('calls a running run a snapshot and names what it is doing', async () => {
    await mount(detail({
      status: 'running', completed_at: null,
      summary: { target_turns: 12, current_activity: 'Gold-Flow GS-4 — Turn 2/3' },
    }));

    expect(text()).toContain('Momentaufnahme');
    expect(text()).toContain('Gold-Flow GS-4 — Turn 2/3');
    // Die Zeile setzt sich aus drei Teilen zusammen (ausgezeichneter Satz,
    // Tätigkeit, Begründung). Ohne Abstand dazwischen klebte sie aneinander.
    expect(h.el.querySelector('.erd-live')?.textContent?.replace(/\s+/g, ' ').trim())
      .toBe('Momentaufnahme — der Lauf läuft noch. Gold-Flow GS-4 — Turn 2/3 '
        + 'Die Lauf-Liste oben aktualisiert sich selbst; hier bewusst nicht, weil '
        + 'diese Antwort die vollständigen Transkripte mitbringt.');
  });

  it('re-reads on demand', async () => {
    await mount();
    button('Aktualisieren')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === url('eval-abc')).flush(detail({ total_turns: 4 }));
    await settle();

    h.http.verify();
  });

  it('can be closed', async () => {
    await mount();
    const closed: number[] = [];
    h.fixture.componentInstance.dismiss.subscribe(() => closed.push(1));

    button('Schließen')!.click();
    await h.fixture.whenStable();

    expect(closed).toHaveLength(1);
  });

  it('shows the load failure of a run that is gone', async () => {
    await mount(null);
    expect(text()).toContain('Lauf weg.');
  });

  it('spricht auf Englisch vollständig englisch — Kennzahlen, Spalten, Kategorien', async () => {
    await mount(detail(), 'eval-abc', 'en');

    expect(text()).toContain('Gold flows');       // Art des Laufs
    expect(text()).toContain('Scored turns');     // Kennzahlen-Liste
    expect(text()).toContain('Hit rates');        // Abschnitts-Überschrift
    expect(text()).toContain('Register');         // Kategorie der Scorecard
    expect(text()).toContain('Expected P/I');     // Spaltenkopf
    expect(text()).toContain('done');             // Status, aus C1-d4b1
    // Kein deutscher Rest — der Fall, den ein Blick auf die Seite übersieht.
    expect(text()).not.toMatch(/[äöüß]/);
  });

  it('setzt die Auszeichnung im Satz als Element, nicht als sichtbaren Stern', async () => {
    await mount(detail({
      status: 'running', completed_at: null, summary: { target_turns: 12 },
    }));

    const strong = Array.from(h.el.querySelectorAll('strong')).map((s) => s.textContent);
    expect(strong).toContain('Momentaufnahme');
    expect(text()).not.toContain('*');
  });

  it('setzt den Variablennamen im Hinweis als <code>', async () => {
    await mount();
    const code = Array.from(h.el.querySelectorAll('code')).map((c) => c.textContent);
    expect(code).toContain('REPO_BASE_URL');
    expect(text()).not.toContain('`');
  });

  it('lässt einen Stern in der Backend-Fehlermeldung keine Auszeichnung werden', async () => {
    // Der Grund, warum der Katalog-Text ZUERST geteilt und danach eingesetzt
    // wird: die Meldung ist fremder Text.
    await mount(detail({
      status: 'failed', error_message: 'chat *backend* down',
      summary: { target_turns: 3 },
    }));

    const strong = Array.from(h.el.querySelectorAll('strong')).map((s) => s.textContent);
    expect(strong).toContain('Fehler:');
    expect(strong).not.toContain('backend');
    expect(text()).toContain('chat *backend* down');
  });
});
