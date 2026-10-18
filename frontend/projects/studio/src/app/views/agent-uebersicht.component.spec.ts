// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { EffectsApi } from '../core/effects-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AgentUebersichtComponent } from './agent-uebersicht.component';

/**
 * Die Startseite des Agent-Arbeitsbereichs (Paket 14, C1; Rundgang 3): mit welcher Maschine der
 * Server antwortet, oben dieselbe Statusleiste wie im Muster-Bereich (Modell, Grundstand, letzter
 * Lauf der Agent-Schleife), der Master-Skill, die Architektur der Agent-Schleife mit Sprüngen und
 * die Testseiten.
 */
const SKILL = {
  enabled: true, node_id: '535cabca-47e4', cached: true, fetched_at: '2026-10-17T10:00:00Z',
  length: 12000, sha256: 'abcdef1234567890', last_error: null, ttl_seconds: 300, text: 'Vorgehen',
  edit_url: 'https://repo.example/md-editor/?nodeId=535cabca-47e4',
  view_url: 'https://repo.example/render/535cabca-47e4',
};

const RUNS = {
  runs: [
    { id: 'r-laufend', status: 'running', created_at: '2026-10-17T12:00:00Z', engine: 'agent',
      mode: 'golden', avg_score: null },
    { id: 'r-fertig', status: 'done', created_at: '2026-10-16T09:00:00Z', engine: 'agent',
      mode: 'golden', avg_score: 0.82 },
  ],
};

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));
const norm = (t: string | null | undefined): string => (t ?? '').replace(/\s+/g, ' ').trim();

describe('AgentUebersichtComponent (Paket 14, C1)', () => {
  let fixture: ComponentFixture<AgentUebersichtComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;

  async function settle(): Promise<void> {
    await tick();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(), provideRouter([]),
      ],
    });
    TestBed.inject(EffectsApi).effects.set({ engine: 'agent', areas: {} });
    fixture = TestBed.createComponent(AgentUebersichtComponent);
    http = TestBed.inject(HttpTestingController);
    el = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  function antworten(runs: object = RUNS): void {
    http.expectOne('/studio/api/master-skill').flush(SKILL);
    http.expectOne('/studio/api/health').flush({ status: 'ok', chat_model: 'gpt-6-luna',
      provider: 'openai' });
    http.expectOne('/studio/api/config/factory').flush({ exists: false });
    http.expectOne('/studio/api/config/snapshots').flush([]);
    http.expectOne((r) => r.url === '/studio/api/eval/runs').flush(runs);
  }

  it('sagt, mit welcher Maschine der Server antwortet, und verweist auf „Betrieb“', async () => {
    antworten();
    await settle();
    expect(norm(el.querySelector('.au-zustand')?.textContent))
      .toContain('Der Server antwortet mit der Agent-Schleife.');
    expect(el.querySelector('.au-zustand a')?.getAttribute('href')).toBe('/betrieb');

    TestBed.inject(EffectsApi).effects.set({ engine: 'pattern', areas: {} });
    await fixture.whenStable();
    expect(norm(el.querySelector('.au-zustand')?.textContent))
      .toContain('Einbettungen können die Agent-Schleife wählen');
  });

  it('zeigt den Master-Skill mit NodeID und Links ins Repositorium', async () => {
    antworten();
    await settle();
    expect(el.textContent).toContain('535cabca-47e4');
    const hrefs = Array.from(el.querySelectorAll('studio-master-skill a'), (a) => a.getAttribute('href'));
    expect(hrefs).toContain(SKILL.edit_url);
    expect(hrefs).toContain(SKILL.view_url);
  });

  it('zeigt oben die Statusleiste: Modell und letzter Lauf der Agent-Schleife', async () => {
    antworten();
    await settle();
    const leiste = norm(el.querySelector('studio-status-strip')?.textContent);
    expect(leiste).toContain('gpt-6-luna');
    expect(leiste).toContain('0,82');
  });

  it('fragt die Statusleiste nur nach Läufen der Agent-Schleife', async () => {
    http.expectOne('/studio/api/master-skill').flush(SKILL);
    const lauf = http.expectOne((r) => r.url === '/studio/api/eval/runs');
    expect(lauf.request.params.get('engine')).toBe('agent');
  });

  it('zeigt die Architektur der Agent-Schleife mit Sprüngen zu den Seiten', async () => {
    antworten();
    await settle();
    const ziele = Array.from(el.querySelectorAll('.au-schichten a'), (a) => a.getAttribute('href'));
    expect(ziele).toEqual(['/agent-rolle', '/agent-rolle', '/skills', '/werkzeuge', '/wissen',
      '/anzeige']);
  });

  it('führt zu den Testseiten des Widgets — in neuem Tab — und zur Vorschau', async () => {
    antworten();
    await settle();
    const links = Array.from(el.querySelectorAll<HTMLAnchorElement>('.au-testseiten a'));
    expect(links.map((a) => a.getAttribute('href'))).toEqual(
      ['/widget/', '/widget/inline', '/widget/classic', '/widget/frameless', '/vorschau']);
    expect(links.slice(0, 4).every((a) => a.target === '_blank' && a.rel.includes('noopener')))
      .toBe(true);
  });
});
