// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { routes } from '../app.routes';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
import { DEFAULT_VIEW } from '../studio-views';
import { OverviewComponent } from './overview.component';

const HEALTH_URL = '/studio/api/health';
const FACTORY_URL = '/studio/api/config/factory';
const SNAPSHOTS_URL = '/studio/api/config/snapshots';
const ELEMENTS_URL = '/studio/api/config/elements';
const RUNS_URL = '/studio/api/eval/runs';

interface Harness {
  fixture: ComponentFixture<OverviewComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function settle(h: Harness): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await h.fixture.whenStable();
}

interface Answers {
  health?: Record<string, unknown>;
  factory?: Record<string, unknown>;
  snapshots?: readonly unknown[];
  elements?: Record<string, unknown>;
  runs?: readonly Record<string, unknown>[];
}

const ELEMENTS_NONE = {
  patterns: [], personas: [], intents: [], states: [], entities: [], signals: [],
};

async function mount(answers: Answers = {}): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `navigator.language === 'en-US'`, und der Browser ist beim
  // Studio die zweitstärkste Sprachquelle. Dieser Test prüft deutsche Texte,
  // also muss er die deutsche Oberfläche ausdrücklich verlangen (C1-d3b).
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(OverviewComponent);
  const http = TestBed.inject(HttpTestingController);
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  http.expectOne((r) => r.url === HEALTH_URL).flush(answers.health ?? { status: 'ok' });
  http.expectOne((r) => r.url === FACTORY_URL).flush(answers.factory ?? { exists: false });
  http.expectOne((r) => r.url === SNAPSHOTS_URL).flush(answers.snapshots ?? []);
  http.expectOne((r) => r.url === ELEMENTS_URL).flush(answers.elements ?? ELEMENTS_NONE);
  http.expectOne((r) => r.url === RUNS_URL).flush({ runs: answers.runs ?? [] });
  await settle(h);
  return h;
}

const text = (h: Harness): string => h.el.textContent ?? '';
const links = (h: Harness): HTMLAnchorElement[] =>
  Array.from(h.el.querySelectorAll<HTMLAnchorElement>('a[href]'));

describe('OverviewComponent', () => {
  it('is what the studio opens on', async () => {
    // `uebersicht` is DEFAULT_VIEW, so a placeholder here is the first thing an
    // editor sees. This pins the route away from that placeholder.
    const children = routes.find((r) => r.path === '')!.children!;
    const route = children.find((r) => r.path === DEFAULT_VIEW)!;
    const loaded = await (route.loadComponent as () => Promise<unknown>)();
    expect(loaded).toBe(OverviewComponent);
  });

  it('offers the overview and the architecture reference as two tabs', async () => {
    const h = await mount();
    expect(Array.from(h.el.querySelectorAll('[role="tab"]')).map((t) => t.textContent?.trim()))
      .toEqual(['Übersicht', 'Architektur & Referenz']);
    // The reference is static prose behind a tab; it must not be in the DOM
    // before it is asked for.
    expect(h.el.querySelector('studio-architecture-reference')).toBeNull();
  });

  it('mounts the reference on its first visit', async () => {
    const h = await mount();
    h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]')[1].click();
    await settle(h);
    h.http.expectOne((r) => r.url.includes('material-types')).flush({ data: {} });
    await settle(h);
    expect(h.el.querySelector('studio-architecture-reference')).toBeTruthy();
    expect(h.el.querySelector('#panel-uebersicht')!.hasAttribute('hidden')).toBe(true);
  });

  it('reicht die geladenen Signale bis in die Referenz-Tabelle durch', async () => {
    // Ein Attribut, das seinen Konsumenten nie erreicht, ist in diesem Port
    // schon zweimal passiert (`data-position` 8-5, `inline-result-grouping`
    // 8-7). Hier hängt eine ganze Tabelle daran: ohne Weitergabe stünde
    // dauerhaft „die Signale stehen hier, sobald …".
    const h = await mount({
      elements: {
        ...ELEMENTS_NONE,
        signals: [{
          id: 'zeitdruck',
          modulations: { dimension: 'D1-Zeit', tone: 'sachlich', length: 'kurz' },
        }],
      },
    });
    h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]')[1].click();
    await settle(h);
    h.http.expectOne((r) => r.url.includes('material-types')).flush({ data: {} });
    await settle(h);

    expect(text(h)).toContain('D1 — Zeit');
    expect(text(h)).toContain('zeitdruck');
  });

  it('names the model the backend answers with', async () => {
    const h = await mount({
      health: { status: 'ok', provider: 'b-api-openai', chat_model: 'gpt-5-mini' },
    });
    expect(text(h)).toContain('gpt-5-mini');
    expect(text(h)).toContain('b-api-openai');
  });

  it('dates the factory snapshot and counts the others', async () => {
    const h = await mount({
      factory: { exists: true, created_at: new Date().toISOString(), label: 'factory' },
      snapshots: [{ id: 'snap-1', created_at: '2026-07-01T08:00:00Z', label: 'vor dem Umbau', include_db: false }],
    });
    expect(text(h)).toContain('gerade eben');
    expect(text(h)).toContain('1 weiterer Snapshot');
  });

  it('beugt die Snapshot-Zeile als Ganzes, nicht nur ihr Substantiv', async () => {
    // „1 weiterer Snapshot" gegen „3 weitere Snapshots": das Adjektiv beugt sich
    // mit. Bis C1-d4a stand die Grenze als `=== 1` im Code — die deutsche Regel,
    // fest verdrahtet; jetzt entscheidet `Intl.PluralRules` der aktiven Sprache.
    const h = await mount({
      factory: { exists: false },
      snapshots: [1, 2, 3].map((n) => ({
        id: `snap-${n}`, created_at: '2026-07-01T08:00:00Z', label: '', include_db: false,
      })),
    });
    expect(text(h)).toContain('3 weitere Snapshots');
    expect(text(h)).not.toContain('weiterer');
  });

  it('spricht auf Englisch vollständig englisch — Kopf, Reiter und Karten', async () => {
    // C1-d4a. Die Reiter-Beschriftungen und die sechs Schicht-Karten standen als
    // fertige Sätze auf Modulebene und wären in der Sprache eingefroren, die
    // beim Laden des Moduls galt.
    const h = await mount({ elements: ELEMENTS_NONE });
    TestBed.inject(StudioLanguageService).toggle();
    await h.fixture.whenStable();

    expect(text(h)).toContain('Overview');
    expect(text(h)).toContain('Architecture & reference');
    expect(text(h)).toContain('Who is the chatbot? What must it never do?');
    expect(text(h)).toContain('Layer 1 —');
    expect(text(h)).not.toContain('Schicht 1');
  });

  it('übersetzt auch die vier Erklär-Karten am Fuss der Seite', async () => {
    // C1-d5d, die letzte Scheibe der Studio-Oberfläche. Bis hierher standen die
    // vier Karten als deutsche Prosa in der Vorlage — sichtbar deutsch mitten
    // in einer sonst englischen Seite.
    const h = await mount({ elements: ELEMENTS_NONE });
    expect(text(h)).toContain('So entscheidet der Bot');
    expect(text(h)).toContain('3-Stufen-Eskalation');

    TestBed.inject(StudioLanguageService).toggle();
    await h.fixture.whenStable();
    expect(text(h)).toContain('How the bot decides');
    expect(text(h)).toContain('Three-step escalation');
    expect(text(h)).not.toContain('So entscheidet der Bot');
  });

  it('gibt jedem Verweis in den Karten eine vollständige Wortgruppe', async () => {
    // Zwei Verweise standen mitten im Satz — einer davon in einer Klammer
    // („siehe Dimensionen"). Einen Satz um ein `<a>` herum zu zerschneiden
    // hiesse, die Wortstellung dem Template zu überlassen (Muster aus C1-d4a).
    const h = await mount({ elements: ELEMENTS_NONE });
    const linkText = (href: string): string =>
      h.el.querySelector(`.ov-info a[href="${href}"]`)?.textContent?.trim() ?? '';
    expect(linkText('/patterns')).toBe('editierbar unter Patterns');
    expect(linkText('/dimensionen')).toBe('nachzusehen unter Dimensionen');
  });

  it('says a factory snapshot is missing instead of implying an empty one', async () => {
    // ALT read four fields NEU does not have (size/mtime/has_db/config_files) and
    // would have rendered "— · 0 Configs · ohne DB" for every state.
    const h = await mount({ factory: { exists: false } });
    expect(text(h)).toContain('kein Werksstand gesichert');
    expect(text(h)).not.toContain('0 Configs');
    expect(text(h)).not.toContain('ohne DB');
  });

  it('shows the last finished eval, ignoring a run still going', async () => {
    const h = await mount({
      runs: [
        { id: 'r-2', status: 'running', avg_score: null, total_turns: 0, completed_at: null },
        { id: 'r-1', status: 'done', avg_score: 0.83, total_turns: 12,
          completed_at: '2026-07-26T10:00:00Z' },
      ],
    });
    expect(text(h)).toContain('0,83');
    expect(text(h)).toContain('12 Turns');
  });

  it('says so when no eval has finished yet', async () => {
    const h = await mount({ runs: [{ id: 'r-1', status: 'failed', avg_score: null }] });
    expect(text(h)).toContain('noch keine');
  });

  it('links every layer and every operations card to its view', async () => {
    const h = await mount();
    const hrefs = links(h).map((a) => a.getAttribute('href'));
    // Navigation is an anchor, not ALT's `<button onClick>`: middle-click and
    // "open in new tab" work, and the target is announced as a link.
    expect(hrefs).toContain('/patterns');
    expect(hrefs).toContain('/material-formate');
    expect(hrefs).toContain('/safety-logs');
    expect(hrefs).toContain('/datenschutz');
  });

  it('counts the elements on the layer cards once they arrive', async () => {
    const h = await mount({
      elements: {
        patterns: new Array(16).fill({}), personas: new Array(6).fill({}),
        intents: new Array(8).fill({}), states: new Array(3).fill({}),
        entities: new Array(5).fill({}), signals: new Array(17).fill({}),
      },
    });
    expect(text(h)).toContain('16 Patterns');
    expect(text(h)).toContain('6 Personas · 8 Intents');
  });

  it('surfaces a failed read instead of a silently empty page', async () => {
    // ALT wrapped all four fetches in Promise.allSettled and dropped every
    // rejection, so a broken endpoint looked like "no data" forever.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    const fixture = TestBed.createComponent(OverviewComponent);
    const http = TestBed.inject(HttpTestingController);
    const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
    await fixture.whenStable();
    http.expectOne((r) => r.url === HEALTH_URL)
      .flush({ detail: 'Datenbank weg.' }, { status: 503, statusText: 'x' });
    http.expectOne((r) => r.url === FACTORY_URL).flush({ exists: false });
    http.expectOne((r) => r.url === SNAPSHOTS_URL).flush([]);
    http.expectOne((r) => r.url === ELEMENTS_URL).flush(ELEMENTS_NONE);
    http.expectOne((r) => r.url === RUNS_URL).flush({ runs: [] });
    await settle(h);

    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Datenbank weg.');
  });

  it('says "Backend nicht erreichbar" once, not once per read', async () => {
    // With the backend down all five reads fail with the SAME sentence. Five
    // identical strings are five identical `@for` track keys, and repeating the
    // sentence five times would be noise even if Angular allowed it.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    const fixture = TestBed.createComponent(OverviewComponent);
    const http = TestBed.inject(HttpTestingController);
    const h = { fixture, el: fixture.nativeElement as HTMLElement, http };
    await fixture.whenStable();
    for (const url of [HEALTH_URL, FACTORY_URL, SNAPSHOTS_URL, ELEMENTS_URL, RUNS_URL]) {
      http.expectOne((r) => r.url === url).error(new ProgressEvent('error'), { status: 0 });
    }
    await settle(h);

    const alerts = h.el.querySelectorAll('[role="alert"]');
    expect(alerts).toHaveLength(1);
    expect(alerts[0].textContent).toContain('Backend nicht erreichbar.');
  });
});
