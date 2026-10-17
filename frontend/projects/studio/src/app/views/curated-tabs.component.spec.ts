// @vitest-environment jsdom
/**
 * Reiter mit Zählern auf der Dimensionen-Seite (Paket 6, S2 — ST-4c).
 *
 * ALT hatte dort fünf Reiter mit Zahl und eine Kopfkarte, die die Achsen der
 * Einordnung mit ihrer Anzahl nennt. NEU stapelte acht aufklappbare Abschnitte.
 * Die Zahlen kommen aus EINEM Abruf (`/config/elements`) und werden nach jedem
 * Speichern neu geholt; ein besuchter Reiter bleibt eingehängt, damit offene
 * Änderungen den Reiterwechsel überleben.
 */
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AreaSectionComponent } from './area-section.component';
import { CuratedTabsComponent } from './curated-tabs.component';
import { curatedView, isAreaSection } from './curated-views';

const ELEMENTS = {
  patterns: [{ id: 'M01' }],
  personas: [{ id: 'P-LEH', label: 'Lehrkraft', file: '04-personas/leh.md' },
    { id: 'P-LER', label: 'Lernende', file: '04-personas/ler.md' }],
  intents: [{ id: 'I01' }, { id: 'I02' }, { id: 'I03' }],
  states: [{ id: 'S1' }],
  entities: [{ id: 'fach' }, { id: 'stufe' }],
  signals: [{ id: 'eile' }],
};

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

interface Harness {
  fixture: ComponentFixture<CuratedTabsComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

/** Alle offenen Abrufe beantworten — die Reiter laden ihre Bereiche selbst. */
function beantworte(http: HttpTestingController): number {
  const elemente = http.match('/studio/api/config/elements');
  elemente.forEach((req) => req.flush(ELEMENTS));
  http.match(() => true).forEach((req) => req.flush({}));
  return elemente.length;
}

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(CuratedTabsComponent);
  const sections = curatedView('dimensionen')!.sections.filter(isAreaSection);
  fixture.componentRef.setInput('sections', sections);
  fixture.componentRef.setInput('label', 'Dimensionen');
  const h = { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
  await fixture.whenStable();
  beantworte(h.http);
  await tick();
  await fixture.whenStable();
  return h;
}

function reiter(h: Harness): string[] {
  return [...h.el.querySelectorAll('[role="tab"]')].map(
    (tab) => tab.getAttribute('aria-label') ?? tab.textContent!.trim());
}

describe('Dimensionen als Reiter mit Zählern (ST-4c)', () => {
  it('zeigt einen Reiter je Abschnitt, mit Zahl dort, wo ALT eine hatte', async () => {
    const h = await mount();
    expect(reiter(h)).toEqual([
      'Personas (2)', 'Intents (3)', 'Gesprächszustände (1)', 'Entitäten (2)',
      'Platzhalter-Themen', 'Signale (1)', 'Tonalität', 'Feste Anker der Einordnung',
    ]);
  });

  it('nennt die Achsen mit ihrer Anzahl in einer Kopfkarte', async () => {
    const h = await mount();
    const karte = h.el.querySelector('.ct-card')!;
    expect(karte.textContent).toContain('2 Personas');
    expect(karte.textContent).toContain('3 Intents');
    expect(karte.textContent).toContain('1 Signal');
  });

  it('hängt nur den offenen Reiter ein und behält besuchte beim Wechsel', async () => {
    const h = await mount();
    expect(h.fixture.debugElement.queryAll(By.css('studio-group-section')).length).toBe(1);
    expect(h.fixture.debugElement.queryAll(By.directive(AreaSectionComponent)).length).toBe(0);

    const intents = [...h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]')][1];
    intents.click();
    await h.fixture.whenStable();
    beantworte(h.http);
    await tick();
    await h.fixture.whenStable();

    expect(intents.getAttribute('aria-selected')).toBe('true');
    const panels = [...h.el.querySelectorAll<HTMLElement>('[role="tabpanel"]')];
    expect(panels.filter((p) => !p.hidden).length).toBe(1);
    expect(panels.find((p) => !p.hidden)?.getAttribute('aria-labelledby'))
      .toBe(intents.id);
    // Personas bleibt eingehängt, nur verborgen; ungeöffnete Reiter haben bloß
    // eine leere Hülle (Review Paket 6 — `aria-controls` zeigt sonst ins Leere).
    expect(h.fixture.debugElement.queryAll(By.css('studio-group-section')).length).toBe(1);
    expect(h.fixture.debugElement.queryAll(By.directive(AreaSectionComponent)).length).toBe(1);
  });

  it('lässt jeden Reiter auf einen Bereich zeigen, den es gibt', async () => {
    const h = await mount();
    const tabs = [...h.el.querySelectorAll('[role="tab"]')];
    expect(tabs.length).toBe(8);
    for (const tab of tabs) {
      const ziel = tab.getAttribute('aria-controls');
      expect(ziel && h.el.querySelector(`#${ziel}`)?.getAttribute('role')).toBe('tabpanel');
    }
  });

  it('behält offene Änderungen im verborgenen Reiter und meldet sie weiter', async () => {
    const h = await mount();
    const gruppe = h.fixture.debugElement.query(By.css('studio-group-section'));
    gruppe.componentInstance.editor.setDoc({ frontmatter: {}, body: 'x' });
    await h.fixture.whenStable();

    [...h.el.querySelectorAll<HTMLButtonElement>('[role="tab"]')][1].click();
    await h.fixture.whenStable();
    beantworte(h.http);
    await tick();
    await h.fixture.whenStable();

    expect(h.fixture.debugElement.query(By.css('studio-group-section'))).toBe(gruppe);
    expect(gruppe.componentInstance.editor.doc()).toEqual({ frontmatter: {}, body: 'x' });
    expect(h.fixture.componentInstance.dirty()).toBe(true);
  });

  it('lässt eine ältere Zähl-Antwort keine neuere überschreiben', async () => {
    const h = await mount();
    const gruppe = h.fixture.debugElement.query(By.css('studio-group-section'));
    gruppe.componentInstance.changed.emit();
    gruppe.componentInstance.changed.emit();
    await h.fixture.whenStable();
    const [aelter, neuer] = h.http.match('/studio/api/config/elements');
    neuer.flush({ ...ELEMENTS, personas: [...ELEMENTS.personas, { id: 'P-ELT', label: 'Eltern' }] });
    await tick();
    aelter.flush(ELEMENTS);
    await tick();
    await h.fixture.whenStable();
    expect(reiter(h)[0]).toBe('Personas (3)');
  });

  it('zählt nach einer Änderung in einem Abschnitt neu', async () => {
    const h = await mount();
    const gruppe = h.fixture.debugElement.query(By.css('studio-group-section'));
    gruppe.componentInstance.changed.emit();
    await h.fixture.whenStable();
    expect(beantworte(h.http)).toBe(1);
  });

  it('meldet offene Änderungen jedes eingehängten Abschnitts', async () => {
    const h = await mount();
    expect(h.fixture.componentInstance.dirty()).toBe(false);
    const gruppe = h.fixture.debugElement.query(By.css('studio-group-section'));
    gruppe.componentInstance.editor.setDoc({ frontmatter: {}, body: 'x' });
    expect(h.fixture.componentInstance.dirty()).toBe(true);
  });
});
