// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { SkillDirectory, SkillSearch } from '../core/agent-center-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AgentSkillsComponent } from './agent-skills.component';

const URL = '/studio/api/agent-center/skills';
const SEARCH_URL = '/studio/api/agent-center/skills/search';
const RENDER = 'https://repo.example/edu-sharing/components/render';
const EDITOR = 'https://repo.example/edu-sharing/services/md-editor/?nodeId=';
const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const VERZEICHNIS: SkillDirectory = {
  collection_id: 'f35c17d1',
  registry: { node_id: 'reg-1', title: 'Skills Geometrische Optik', url: `${RENDER}/reg-1` },
  entries: [
    {
      node_id: 's-1', title: 'Quiz erstellen', description: 'Baut ein Quiz zum Thema.',
      keywords: ['Quiz', 'Test'], context: 'Unterricht', url: `${RENDER}/s-1`,
      edit_url: `${EDITOR}s-1&field=file`,
    },
    {
      node_id: 's-2', title: '', description: '', keywords: [], context: '', url: `${RENDER}/s-2`,
      edit_url: `${EDITOR}s-2&field=file`,
    },
  ],
  unresolved: [{ node_id: 's-9', title: 'Alter Skill' }, { node_id: '', title: 'Ohne Link' }],
  reason: null,
  truncated: false,
};

interface Harness {
  fixture: ComponentFixture<AgentSkillsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(AgentSkillsComponent);
  fixture.componentRef.setInput('section', {
    panel: 'agent-skills',
    labelKey: 'curated.agent.skills.label',
    hintKey: 'curated.agent.skills.hint',
  });
  fixture.componentRef.setInput('open', true);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
}

async function suche(h: Harness, eingabe: string): Promise<void> {
  const feld = h.el.querySelector<HTMLInputElement>('#ags-collection')!;
  feld.value = eingabe;
  feld.dispatchEvent(new Event('input'));
  h.el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  await h.fixture.whenStable();
}

async function antwort(h: Harness, body: object, status = 200): Promise<void> {
  const req = h.http.expectOne((r) => r.url === URL);
  expect(req.request.params.get('collection')).toBe('f35c17d1');
  if (status === 200) req.flush(body);
  else req.flush(body, { status, statusText: 'Bad Gateway' });
  await tick();
  await h.fixture.whenStable();
}

const text = (node: Element | null): string => (node?.textContent ?? '').replace(/\s+/g, ' ').trim();

describe('AgentSkillsComponent (ST-8c)', () => {
  it('beschriftet das Feld und hängt den Hinweis an', async () => {
    const { el } = await mount();
    const feld = el.querySelector<HTMLInputElement>('#ags-collection')!;
    expect(text(el.querySelector('label[for="ags-collection"]'))).toBe('Sammlungs-ID');
    expect(feld.getAttribute('aria-describedby')).toBe('ags-collection-hint');
    expect(feld.getAttribute('aria-invalid')).toBeNull();
  });

  it('prüft die Kennung vor dem Abruf und sagt am Feld, was fehlt', async () => {
    const h = await mount();
    await suche(h, '  ');
    const feld = h.el.querySelector<HTMLInputElement>('#ags-collection')!;
    expect(feld.getAttribute('aria-invalid')).toBe('true');
    expect(feld.getAttribute('aria-describedby')).toBe('ags-collection-hint ags-collection-error');
    expect(text(h.el.querySelector('#ags-collection-error'))).toBe('Bitte eine Sammlungs-ID eingeben.');
    // Angesagt, sobald er erscheint — sonst erfährt ein Screenreader nichts davon.
    expect(h.el.querySelector('#ags-collection-error')!.getAttribute('role')).toBe('alert');
    await suche(h, 'https://repo.example/x?id=1');
    expect(text(h.el.querySelector('#ags-collection-error'))).toContain('Nur die Kennung');
    h.http.expectNone((r) => r.url === URL);
  });

  it('zeigt Registry-Dokument, Skills mit Verweis ins Repositorium und nicht aufgelöste', async () => {
    const h = await mount();
    await suche(h, ' f35c17d1 ');
    await antwort(h, VERZEICHNIS);
    const dokument = h.el.querySelector<HTMLAnchorElement>('.ags-doc a')!;
    expect(dokument.getAttribute('href')).toBe(`${RENDER}/reg-1`);
    expect(dokument.getAttribute('target')).toBe('_blank');
    expect(dokument.getAttribute('rel')).toBe('noopener noreferrer');
    expect(text(h.el.querySelector('.ags-count'))).toBe('2 freigegebene Skills');

    const [quiz, ohneTitel] = Array.from(h.el.querySelectorAll('.ags-entry'));
    expect(quiz.querySelector('a')!.getAttribute('href')).toBe(`${RENDER}/s-1`);
    expect(text(quiz.querySelector('.ags-title'))).toContain('Quiz erstellen');
    expect(text(quiz.querySelector('.ags-context'))).toBe('Kontext: Unterricht');
    expect(text(quiz.querySelector('.ags-desc'))).toBe('Baut ein Quiz zum Thema.');
    expect(text(quiz.querySelector('.ags-keywords'))).toBe('Stichworte: Quiz und Test');
    // Ohne Titel steht die Kennung da, statt eines leeren Links.
    expect(text(ohneTitel.querySelector('.ags-title'))).toContain('s-2');
    expect(ohneTitel.querySelector('.ags-desc')).toBeNull();

    // Paket F2: je Skill ein Link in den md-editor — der Name sagt, WAS bearbeitet
    // wird, sonst hört ein Screenreader fünfmal nur „Bearbeiten“.
    const bearbeiten = quiz.querySelector<HTMLAnchorElement>('a.ags-edit')!;
    expect(bearbeiten.getAttribute('href')).toBe(`${EDITOR}s-1&field=file`);
    expect(bearbeiten.getAttribute('target')).toBe('_blank');
    expect(bearbeiten.getAttribute('rel')).toBe('noopener noreferrer');
    // Derselbe Zusatz wie auf der Master-Skill-Karte (Review 2026-09-29).
    expect(text(bearbeiten)).toBe('Bearbeiten: Quiz erstellen im Editor (öffnet einen neuen Tab)');
    expect(text(ohneTitel.querySelector('a.ags-edit'))).toContain('s-2 im Editor');

    const offen = Array.from(h.el.querySelectorAll('.ags-unresolved li'));
    expect(text(offen[0])).toBe('Alter Skill s-9');
    // Der typische Fehler im Dokument: ein Block ganz ohne Link.
    expect(text(offen[1])).toBe('Ohne Link — ohne Kennung im Dokument');
    expect(offen[1].querySelector('code')).toBeNull();
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toBe('Verzeichnis geladen.');
  });

  it('sagt ohne Registry-Dokument, warum es keine Liste gibt', async () => {
    const h = await mount();
    await suche(h, 'f35c17d1');
    await antwort(h, { ...VERZEICHNIS, registry: null, entries: [], unresolved: [], reason: 'no_registry' });
    expect(text(h.el.querySelector('.ags-empty')))
      .toBe('Diese Sammlung führt kein Registry-Dokument — sie gibt keine Skills frei.');
    expect(h.el.querySelector('.ags-list')).toBeNull();
  });

  it('warnt, wenn die Liste womöglich unvollständig ist', async () => {
    const h = await mount();
    await suche(h, 'f35c17d1');
    await antwort(h, { ...VERZEICHNIS, truncated: true });
    expect(h.el.querySelector('.ags-note')?.getAttribute('role')).toBe('note');
    expect(text(h.el.querySelector('.ags-note'))).toContain('unvollständig');
  });

  it('zeigt einen Fehler des Servers, ohne das Feld zu leeren', async () => {
    const h = await mount();
    await suche(h, 'f35c17d1');
    await antwort(h, { detail: 'Das Repositorium hat das Skill-Verzeichnis nicht geliefert (timeout).' }, 502);
    expect(text(h.el.querySelector('[role="alert"]'))).toContain('(timeout)');
    expect(h.el.querySelector<HTMLInputElement>('#ags-collection')!.value).toBe('f35c17d1');
  });

  it('sperrt den Knopf während des Abrufs und nimmt das alte Ergebnis weg', async () => {
    const h = await mount();
    await suche(h, 'f35c17d1');
    await antwort(h, VERZEICHNIS);
    await suche(h, 'f35c17d1');
    const knopf = h.el.querySelector<HTMLButtonElement>('form button')!;
    expect(knopf.disabled).toBe(true);
    expect(text(knopf)).toBe('Wird geholt …');
    expect(h.el.querySelector('.ags-list')).toBeNull();
    await antwort(h, VERZEICHNIS);
    expect(knopf.disabled).toBe(false);
    // Der gesperrte Knopf hat den Fokus verloren; er kehrt ins Feld zurück.
    expect(document.activeElement?.id).toBe('ags-collection');
  });
});

// ── Paket F3: Suche per Suchbegriff (MCP `search_skill`, falls aktiv) ──────

const TREFFER: SkillSearch = {
  query: 'Optik',
  available: true,
  entries: [{
    node_id: 'ref-1', title: 'Linsen prüfen', description: 'Prüft eine Seite.', keywords: ['Optik'],
    context: '', url: `${RENDER}/ref-1`, edit_url: `${EDITOR}orig-1&field=file`,
  }],
};

async function suchart(h: Harness, art: 'collection' | 'term'): Promise<void> {
  const knopf = h.el.querySelector<HTMLInputElement>(`input[name="ags-mode"][value="${art}"]`)!;
  knopf.click();
  await h.fixture.whenStable();
}

async function treffer(h: Harness, body: object, erwartet = 'Optik'): Promise<void> {
  const req = h.http.expectOne((r) => r.url === SEARCH_URL);
  expect(req.request.params.get('q')).toBe(erwartet);
  req.flush(body);
  await tick();
  await h.fixture.whenStable();
}

describe('AgentSkillsComponent (Paket F3: Suchbegriff)', () => {
  it('bietet Sammlungs-ID und Suchbegriff als Suchart an, Sammlungs-ID vorgewählt', async () => {
    const { el } = await mount();
    expect(text(el.querySelector('fieldset.ags-mode legend'))).toBe('Suchen nach');
    const arten = Array.from(el.querySelectorAll<HTMLInputElement>('input[name="ags-mode"]'));
    expect(arten.map((r) => [r.value, r.checked])).toEqual([['collection', true], ['term', false]]);
    // Jede Option trägt ihren Namen über das umschließende <label>.
    expect(arten.map((r) => text(r.closest('label')))).toEqual(['Sammlungs-ID', 'Suchbegriff']);
  });

  it('sucht per Suchbegriff und zeigt die Treffer samt Bearbeiten-Link', async () => {
    const h = await mount();
    await suchart(h, 'term');
    expect(text(h.el.querySelector('label[for="ags-collection"]'))).toBe('Suchbegriff');
    expect(text(h.el.querySelector('form button'))).toBe('Skills suchen');
    await suche(h, '  Optik ');
    await treffer(h, TREFFER);
    // Die Zahl steht EINMAL — in der Statuszeile, die zugleich vorgelesen wird
    // (Review 2026-09-29: vorher zusätzlich als `.ags-count` darunter).
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toBe('1 Skill gefunden');
    expect(h.el.querySelector('.ags-count')).toBeNull();
    const eintrag = h.el.querySelector('.ags-entry')!;
    expect(eintrag.querySelector('a.ags-title')!.getAttribute('href')).toBe(`${RENDER}/ref-1`);
    // Bearbeitet wird das Original, nicht der Verweis aus der Fachsammlung.
    const bearbeiten = eintrag.querySelector('a.ags-edit')!;
    expect(bearbeiten.getAttribute('href')).toBe(`${EDITOR}orig-1&field=file`);
    expect(text(bearbeiten)).toBe('Bearbeiten: Linsen prüfen im Editor (öffnet einen neuen Tab)');
    h.http.expectNone((r) => r.url === URL);
  });

  it('nennt die Mehrzahl und warnt, wenn die Liste gekappt sein kann', async () => {
    const h = await mount();
    await suchart(h, 'term');
    await suche(h, 'Optik');
    const zweiter = { ...TREFFER.entries[0], node_id: 'ref-2', title: 'Spiegel' };
    await treffer(h, { ...TREFFER, entries: [...TREFFER.entries, zweiter], truncated: true });
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toBe('2 Skills gefunden');
    expect(text(h.el.querySelector('.ags-note[role="note"]'))).toContain('mehr als 2');
  });

  it('sperrt den Knopf während der Suche und zeigt einen Fehler, ohne den Begriff zu leeren', async () => {
    const h = await mount();
    await suchart(h, 'term');
    await suche(h, 'Optik');
    const knopf = h.el.querySelector<HTMLButtonElement>('form button')!;
    expect(knopf.disabled).toBe(true);
    expect(text(knopf)).toBe('Wird gesucht …');
    const req = h.http.expectOne((r) => r.url === SEARCH_URL);
    req.flush({ detail: 'Das Repositorium hat die Skill-Suche nicht beantwortet (timeout).' },
      { status: 502, statusText: 'Bad Gateway' });
    await tick();
    await h.fixture.whenStable();
    expect(text(h.el.querySelector('.cs-state--error[role="alert"]'))).toContain('(timeout)');
    expect(h.el.querySelector<HTMLInputElement>('#ags-collection')!.value).toBe('Optik');
    expect(knopf.disabled).toBe(false);
  });

  it('zeigt ohne Editor-Adresse keinen toten Bearbeiten-Link', async () => {
    const h = await mount();
    await suchart(h, 'term');
    await suche(h, 'Optik');
    await treffer(h, { ...TREFFER, entries: [{ ...TREFFER.entries[0], edit_url: '' }] });
    expect(h.el.querySelector('a.ags-title')).not.toBeNull();
    expect(h.el.querySelector('a.ags-edit')).toBeNull();
  });

  it('holt den Fokus nicht zurück, wenn die Person inzwischen woanders ist', async () => {
    const h = await mount();
    const woanders = document.createElement('button');
    document.body.appendChild(woanders);
    try {
      await suchart(h, 'term');
      await suche(h, 'Optik');
      woanders.focus();
      await treffer(h, TREFFER);
      expect(document.activeElement).toBe(woanders);
    } finally {
      woanders.remove();
    }
  });

  it('prüft den Suchbegriff vor dem Abruf und sagt am Feld, was fehlt', async () => {
    const h = await mount();
    await suchart(h, 'term');
    await suche(h, '   ');
    expect(text(h.el.querySelector('#ags-collection-error'))).toBe('Bitte einen Suchbegriff eingeben.');
    await suche(h, 'x'.repeat(201));
    expect(text(h.el.querySelector('#ags-collection-error'))).toBe('Höchstens 200 Zeichen.');
    h.http.expectNone((r) => r.url === SEARCH_URL);
  });

  it('sagt ehrlich, wenn die Suche auf dem Server nicht aktiv ist, und führt zur Sammlungs-ID', async () => {
    const h = await mount();
    await suchart(h, 'term');
    await suche(h, 'Optik');
    await treffer(h, { query: 'Optik', available: false, entries: [] });

    const hinweis = h.el.querySelector('#ags-search-off')!;
    expect(hinweis.getAttribute('role')).toBe('note');
    expect(text(hinweis)).toContain('nicht aktiv');
    const [sammlung, begriff] = Array.from(
      h.el.querySelectorAll<HTMLInputElement>('input[name="ags-mode"]'));
    expect(begriff.disabled).toBe(true);
    expect(begriff.getAttribute('aria-describedby')).toBe('ags-search-off');
    expect(sammlung.checked).toBe(true);
    expect(text(h.el.querySelector('label[for="ags-collection"]'))).toBe('Sammlungs-ID');
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toContain('nicht aktiv');
    expect(document.activeElement?.id).toBe('ags-collection');
    expect(h.el.querySelector('.ags-empty')).toBeNull();
  });

  it('ohne Treffer sagt es das, statt eine leere Liste zu zeigen', async () => {
    const h = await mount();
    await suchart(h, 'term');
    await suche(h, 'Zzz');
    await treffer(h, { query: 'Zzz', available: true, entries: [] }, 'Zzz');
    // Einmal, in der Statuszeile — nicht zusätzlich „0 Skills gefunden“ darüber.
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toBe('Keine Skills zu „Zzz“ gefunden.');
    expect(h.el.querySelector('.ags-empty')).toBeNull();
    expect(h.el.querySelector('.ags-list')).toBeNull();
  });

  it('behält je Suchart die eigene Eingabe', async () => {
    const h = await mount();
    const feld = (): HTMLInputElement => h.el.querySelector<HTMLInputElement>('#ags-collection')!;
    feld().value = 'f35c17d1';
    feld().dispatchEvent(new Event('input'));
    // Zwischen Tippen und Klick läuft im Browser immer eine Änderungserkennung.
    await h.fixture.whenStable();
    await suchart(h, 'term');
    expect(feld().value).toBe('');
    await suchart(h, 'collection');
    expect(feld().value).toBe('f35c17d1');
  });
});
