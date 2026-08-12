// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
import { AREA_KEYS, AREA_SCHEMAS } from '../schema-form/area-schemas.fixture';
import { STUDIO_VIEWS, type StudioView } from '../studio-views';
import { CURATED_VIEWS, curatedView, isAreaSection } from './curated-views';
import { CuratedViewComponent } from './curated-view.component';

/** Only the config-area sections — panels have no area key (9-4e). */
const AREA_SECTIONS = CURATED_VIEWS.map((view) => ({
  slug: view.slug,
  sections: view.sections.filter(isAreaSection),
}));

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<CuratedViewComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

function viewFor(slug: string): StudioView {
  const view = STUDIO_VIEWS.find((v) => v.slug === slug);
  if (!view) throw new Error(`no such view: ${slug}`);
  return view;
}

/** A schema the fixture may not carry under this key (areas share models). */
function schemaFor(area: string): object {
  return AREA_SCHEMAS[area] ?? AREA_SCHEMAS['01-base/base-persona'];
}

async function mount(slug: string): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `en-US`; die Wortlaute unten sind deutsch (C1-d3b).
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(CuratedViewComponent);
  fixture.componentRef.setInput('view', viewFor(slug));
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

/** Answer the pair of requests one section makes when it opens. */
function answer(
  http: HttpTestingController,
  area: string,
  data: Record<string, unknown>,
): void {
  http.expectOne(`/studio/api/config/schema/${area}`).flush(schemaFor(area));
  http.expectOne(`/studio/api/config/data/${area}`).flush({ area, data, type: 'yaml' });
}

describe('CURATED_VIEWS declaration', () => {
  it('names only real config areas', () => {
    // A typo here is invisible until someone opens the page and reads
    // "Diesen Konfigurationsbereich gibt es nicht."
    const unknown = AREA_SECTIONS.flatMap((view) =>
      view.sections.map((s) => s.area).filter((area) => !AREA_KEYS.includes(area)),
    );
    expect(unknown).toEqual([]);
  });

  it('renders every declared panel — no silently empty section', () => {
    // A panel id with no `@case` in the template renders nothing at all: the
    // heading and hint would be gone too, so the page just looks shorter.
    const RENDERED = ['rag-areas', 'rag-ingest', 'mcp-registry'];
    const declared = CURATED_VIEWS.flatMap((view) =>
      view.sections.flatMap((s) => (isAreaSection(s) ? [] : [s.panel])),
    );
    expect(declared.filter((panel) => !RENDERED.includes(panel))).toEqual([]);
  });

  it('names only slugs the view registry routes to this package', () => {
    for (const view of CURATED_VIEWS) {
      const registered = STUDIO_VIEWS.find((v) => v.slug === view.slug);
      expect(registered, `slug ${view.slug}`).toBeDefined();
      expect(registered?.paket, `slug ${view.slug}`).toBe('9-4');
    }
  });

  it('marks the two folder areas as groups, and nothing else', () => {
    // `03-patterns` and `04-personas` hold many documents; GET /config/data
    // answers 404 for them, so an unmarked one renders a dead panel. The
    // reverse is just as wrong: a file key rendered as a group asks
    // /config/elements for a list that does not exist.
    const FOLDERS = new Set(['03-patterns', '04-personas']);
    for (const view of AREA_SECTIONS) {
      for (const section of view.sections) {
        expect(section.kind === 'group', `${view.slug} → ${section.area}`)
          .toBe(FOLDERS.has(section.area));
      }
    }
  });

  it('lists every area at most once per view', () => {
    for (const view of AREA_SECTIONS) {
      const areas = view.sections.map((s) => s.area);
      expect(new Set(areas).size, `view ${view.slug}`).toBe(areas.length);
    }
  });

  it('gives every area exactly one home across all views', () => {
    // Two pages editing the same area is two documents in two states, and the
    // one saved second silently wins.
    const areas = AREA_SECTIONS.flatMap((view) => view.sections.map((s) => s.area));
    expect(new Set(areas).size).toBe(areas.length);
  });

  it('leaves no 9-4 view without a definition', () => {
    // Not a wish list: a new 9-4 view added to the registry without an entry
    // here would render the placeholder page and look finished from the nav.
    const missing = STUDIO_VIEWS.filter((v) => v.paket === '9-4')
      .map((v) => v.slug)
      .filter((slug) => !curatedView(slug));
    expect(missing).toEqual([]);
  });

  it('nennt nur Katalog-Schlüssel, die es in beiden Sprachen gibt', () => {
    // Bis C1-d3d standen hier 70 fertige deutsche Texte auf Modulebene — sie
    // frören in der Sprache ein, die beim Laden des Moduls galt. Jetzt sind es
    // Schlüssel, und ein Tippfehler darin wäre unsichtbar bis jemand die Seite
    // öffnet: `t()` gibt den Schlüssel selbst als Überschrift aus. Dieselbe
    // Prüfung wie `views-i18n.spec.ts` für die Ansichts-Registry.
    const keys = CURATED_VIEWS.flatMap((view) => [
      view.introKey,
      ...view.sections.flatMap((section) => [section.labelKey, section.hintKey]),
    ]);
    expect(keys.filter((key) => !(key in STUDIO_DE)), 'fehlt auf Deutsch').toEqual([]);
    expect(keys.filter((key) => !(key in STUDIO_EN)), 'fehlt auf Englisch').toEqual([]);
  });

  it('gibt keinem Abschnitt denselben Schlüssel wie einem anderen', () => {
    // Zwei Abschnitte mit demselben Schlüssel tragen dieselbe Überschrift —
    // aus dem Katalog heraus nicht erkennbar, weil beide Sprachen ihn brav
    // führen. Die Sichtprüfung fiele erst auf der Seite auf.
    const keys = CURATED_VIEWS.flatMap((view) =>
      view.sections.map((section) => section.labelKey),
    );
    expect(new Set(keys).size).toBe(keys.length);
  });

  it('keeps the MCP registry off the generic form, which has no SSRF gate', () => {
    // `PUT /config/data/…` validates the model; only `PUT /config/mcp-servers`
    // knows what a server URL means. Listing the area here would put a second,
    // weaker write path for it on the very page that manages MCP.
    const areas = AREA_SECTIONS.flatMap((view) => view.sections.map((s) => s.area));
    expect(areas).not.toContain('05-knowledge/mcp-servers');
  });
});

describe('CuratedViewComponent', () => {
  it('shows one section per configured area, in the declared order', async () => {
    const { el, http } = await mount('anzeige');
    answer(http, '01-base/display-rules', { display_rules: {} });

    const headings = Array.from(el.querySelectorAll('summary .cs-title'))
      .map((h) => h.textContent?.trim());
    expect(headings).toEqual(['Darstellungsregeln', 'Kopfzeilen-Navigation', 'Geräte']);
  });

  it('nimmt Einleitung und Abschnitts-Überschriften aus dem Katalog', async () => {
    // Die Erwartung steht ausgeschrieben und wird NICHT aus derselben Quelle
    // gezogen, gegen die geprüft wird — sonst bestünde der Test auch dann,
    // wenn überall der Schlüssel statt des Textes erschiene.
    const { el, http, fixture } = await mount('anzeige');
    answer(http, '01-base/display-rules', { display_rules: {} });
    expect(el.querySelector('.cv-intro')?.textContent).toContain('Wie Ergebnisse im Widget');

    TestBed.inject(StudioLanguageService).toggle();
    await fixture.whenStable();
    expect(el.querySelector('.cv-intro')?.textContent).toContain('How results appear');
    expect(Array.from(el.querySelectorAll('summary .cs-title')).map((h) => h.textContent?.trim()))
      .toEqual(['Display rules', 'Header navigation', 'Devices']);
  });

  it('loads only the section that is open', async () => {
    // Three areas mean six requests on arrival if every section loads eagerly.
    const { http } = await mount('anzeige');
    answer(http, '01-base/display-rules', { display_rules: {} });
    http.verify(); // nothing for header-nav or device-config yet
  });

  it('loads a section the first time it is opened, and not again', async () => {
    const { el, http, fixture } = await mount('anzeige');
    answer(http, '01-base/display-rules', { display_rules: {} });

    const second = el.querySelectorAll('details')[1];
    second.open = true;
    second.dispatchEvent(new Event('toggle'));
    await fixture.whenStable();
    answer(http, '01-base/header-nav', { header_nav: {} });

    second.open = false;
    second.dispatchEvent(new Event('toggle'));
    second.open = true;
    second.dispatchEvent(new Event('toggle'));
    await fixture.whenStable();
    http.verify(); // reopening must not refetch and discard the edits in it
  });

  it('reports unsaved changes in ANY section, so the leave guard sees them', async () => {
    const { el, http, fixture } = await mount('anzeige');
    answer(http, '01-base/display-rules', { display_rules: {} });

    const second = el.querySelectorAll('details')[1];
    second.open = true;
    second.dispatchEvent(new Event('toggle'));
    await fixture.whenStable();
    answer(http, '01-base/header-nav', { header_nav: { links: [] } });
    await tick();
    await fixture.whenStable();

    expect(fixture.componentInstance.dirty()).toBe(false);
    fixture.componentInstance.sections()[1].editor.setDoc({ header_nav: { links: ['x'] } });
    await fixture.whenStable();
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it('saves one area at a time — a section never writes its neighbour', async () => {
    const { el, http, fixture } = await mount('datenschutz');
    answer(http, '01-base/privacy-config', { privacy: { store_messages: true } });
    await tick();
    await fixture.whenStable();

    const section = fixture.componentInstance.sections()[0];
    section.editor.setDoc({ privacy: { store_messages: false } });
    await fixture.whenStable();

    const save = el.querySelector<HTMLButtonElement>('.cs-save');
    save?.click();
    await fixture.whenStable();

    const req = http.expectOne('/studio/api/config/data/01-base/privacy-config');
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({ data: { privacy: { store_messages: false } } });
    req.flush({
      area: '01-base/privacy-config',
      data: { privacy: { store_messages: false } },
      type: 'yaml',
    });
    await fixture.whenStable();
    http.verify(); // quality-log-config was never touched
  });

  it('offers the raw source of each area, because the form cannot reach every key', async () => {
    const { el, http, fixture } = await mount('begruessung');
    answer(http, '01-base/welcome-config', { welcome: {} });
    await tick();
    await fixture.whenStable();

    const link = el.querySelector<HTMLAnchorElement>('.cs-raw-link');
    expect(link?.getAttribute('href')).toBe('/bereich/01-base/welcome-config');
  });
});
