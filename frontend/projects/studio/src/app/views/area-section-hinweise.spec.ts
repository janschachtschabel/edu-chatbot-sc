// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AREA_SCHEMAS } from '../schema-form/area-schemas.fixture';
import { AreaSectionComponent } from './area-section.component';
import { type CuratedAreaSection, curatedView, isAreaSection } from './curated-views';

/**
 * Hinweise eines Abschnitts (Paket 15, A1): Einstellungen, die einander aushebeln. Auf
 * „Betrieb“ wirkt „Token-Streaming an“ im Agent-Modus nur mit den Agent-Schnellantworten —
 * steht dieser Schalter aus, sagt die Seite es, statt dass die Antwort still ungestreamt kommt.
 */
const AREA = '01-base/engine';
const DATA_URL = `/studio/api/config/data/${AREA}`;
const BETRIEB = curatedView('betrieb')!.sections.filter(isAreaSection)[0] as CuratedAreaSection;

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

async function mount(doc: Record<string, unknown>) {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(), provideHttpClient(withXhr()),
      provideHttpClientTesting(), provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(AreaSectionComponent);
  fixture.componentRef.setInput('section', BETRIEB);
  fixture.componentRef.setInput('open', true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.match('/studio/api/config/effects').forEach((r) => r.flush({}));
  http.match('/studio/api/config/choices').forEach((r) => r.flush({}));
  http.expectOne(`/studio/api/config/schema/${AREA}`).flush(AREA_SCHEMAS[AREA]);
  http.expectOne(DATA_URL).flush({ area: AREA, data: doc, type: 'yaml', version: 3 });
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

const hinweis = (el: HTMLElement) => el.querySelector('.cs-hinweis')?.textContent ?? '';

describe('AreaSectionComponent — Hinweise (Paket 15, A1)', () => {
  it('warnt, wenn der Agent streamen soll, aber die Agent-Schnellantworten aus sind', async () => {
    const { el } = await mount({ mode: 'agent', betrieb: { agent_schnellantworten: false } });
    expect(el.querySelector('.cs-hinweis')?.getAttribute('role')).toBe('note');
    expect(hinweis(el)).toContain('Agent-Schnellantworten');
  });

  it('schweigt bei den Vorgaben — fehlende Schalter sind an', async () => {
    const { el } = await mount({ mode: 'agent', betrieb: {} });
    expect(el.querySelector('.cs-hinweis')).toBeNull();
  });

  it('schweigt im Muster-Modus und ohne Streaming', async () => {
    expect((await mount({ mode: 'pattern', betrieb: { agent_schnellantworten: false } }))
      .el.querySelector('.cs-hinweis')).toBeNull();
    expect((await mount({ mode: 'agent',
      betrieb: { token_streaming: false, agent_schnellantworten: false } }))
      .el.querySelector('.cs-hinweis')).toBeNull();
  });

  it('folgt dem Entwurf, nicht erst dem gespeicherten Stand', async () => {
    const { el, fixture } = await mount({ mode: 'agent', betrieb: { agent_schnellantworten: true } });
    const schalter = el.querySelector<HTMLInputElement>('[id$="betrieb.agent_schnellantworten"]')!;
    schalter.checked = false;
    schalter.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(hinweis(el)).toContain('Agent-Schnellantworten');
  });
});

describe('AreaSectionComponent — ungespeichert (Review-Runde 2, R2-11)', () => {
  it('ein nicht lesbarer Feld-Entwurf zählt für Verlassen-Schutz und Kennzeichen', async () => {
    const { fixture, el } = await mount({ mode: 'agent' });
    const section = fixture.componentInstance as unknown as {
      dirty: () => boolean; editor: { setFieldErrors(f: readonly string[]): void };
    };
    expect(section.dirty()).toBe(false);
    section.editor.setFieldErrors(['betrieb.x']);
    await fixture.whenStable();
    expect(section.dirty()).toBe(true);
    expect(el.querySelector('.cs-flag')).not.toBeNull();
  });
});

describe('AreaSectionComponent — Rohtext-Link (Review-Runde 2, R2-16)', () => {
  it('nennt die Seite, auf der der Abschnitt steht', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(), provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { routeConfig: { path: 'betrieb' } } } },
      ],
    });
    const fixture = TestBed.createComponent(AreaSectionComponent);
    fixture.componentRef.setInput('section', BETRIEB);
    fixture.componentRef.setInput('open', true);
    const http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    http.match('/studio/api/config/effects').forEach((r) => r.flush({}));
    http.match('/studio/api/config/choices').forEach((r) => r.flush({}));
    http.expectOne(`/studio/api/config/schema/${AREA}`).flush(AREA_SCHEMAS[AREA]);
    http.expectOne(DATA_URL).flush({ area: AREA, data: {}, type: 'yaml', version: 3 });
    await tick();
    await fixture.whenStable();
    const link = (fixture.nativeElement as HTMLElement).querySelector('a[href^="/bereich/"]');
    expect(link?.getAttribute('href')).toBe('/bereich/01-base/engine?von=betrieb');
  });
});
