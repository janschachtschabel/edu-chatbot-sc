// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AREA_SCHEMAS } from '../schema-form/area-schemas.fixture';
import { AreaSectionComponent } from './area-section.component';
import type { CuratedAreaSection } from './curated-views';

/**
 * Ein Feld-Ausschnitt eines Bereichs (Paket 14, B1): `01-base/engine` trägt Felder beider
 * Arbeitsbereiche — Rolle und Schutzregeln gehören dem Agent, die Vorgabe-Maschine dem Betrieb.
 * Eine Seite zeigt nur ihren Ausschnitt; gespeichert wird weiter das ganze Dokument.
 */
const AREA = '01-base/engine';
const DATA_URL = `/studio/api/config/data/${AREA}`;
const DOC = {
  mode: 'agent', muster_skills: false, betrieb: {}, agent: {},
  agent_rolle: { rolle: 'Du hilfst.', schutzregeln: ['R-01'] },
};

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

async function mount(section: CuratedAreaSection) {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(), provideHttpClient(withXhr()),
      provideHttpClientTesting(), provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(AreaSectionComponent);
  fixture.componentRef.setInput('section', section);
  fixture.componentRef.setInput('open', true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.match('/studio/api/config/effects').forEach((r) => r.flush({}));
  http.match('/studio/api/config/choices').forEach((r) => r.flush({}));
  http.expectOne(`/studio/api/config/schema/${AREA}`).flush(AREA_SCHEMAS[AREA]);
  http.expectOne(DATA_URL).flush({ area: AREA, data: DOC, type: 'yaml', version: 3 });
  await tick();
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http };
}

const ids = (el: HTMLElement): string[] =>
  Array.from(el.querySelectorAll('input, textarea, select'), (e) => e.id);

describe('AreaSectionComponent — Feld-Ausschnitt (Paket 14, B1)', () => {
  it('zeigt nur die genannten Felder', async () => {
    const { el } = await mount({
      area: AREA, labelKey: 'curated.agent.engine.label', hintKey: 'curated.agent.engine.hint',
      felder: ['agent_rolle'],
    });
    const felder = ids(el).filter((id) => id.startsWith('cs-'));
    expect(felder.some((id) => id.includes('agent_rolle'))).toBe(true);
    expect(felder.some((id) => id.endsWith('-mode'))).toBe(false);
    expect(felder.some((id) => id.includes('muster_skills'))).toBe(false);
  });

  it('speichert das ganze Dokument, nicht nur den Ausschnitt', async () => {
    const { el, fixture, http } = await mount({
      area: AREA, labelKey: 'curated.agent.engine.label', hintKey: 'curated.agent.engine.hint',
      felder: ['agent_rolle'],
    });
    const rolle = Array.from(el.querySelectorAll<HTMLTextAreaElement>('textarea'))
      .find((t) => t.id.includes('agent_rolle'))!;
    rolle.value = 'Du hilfst freundlich.';
    rolle.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes('Speichern'))!.click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.url === DATA_URL && r.method === 'PUT');
    expect(req.request.body.data.mode).toBe('agent');
    expect(req.request.body.data.agent_rolle.rolle).toBe('Du hilfst freundlich.');
  });

  it('ohne Ausschnitt zeigt der Abschnitt alle Felder wie bisher', async () => {
    const { el } = await mount({
      area: AREA, labelKey: 'curated.agent.engine.label', hintKey: 'curated.agent.engine.hint',
    });
    const felder = ids(el).filter((id) => id.startsWith('cs-'));
    expect(felder.some((id) => id.includes('agent_rolle'))).toBe(true);
    expect(felder.some((id) => id.includes('muster_skills'))).toBe(true);
  });
});
