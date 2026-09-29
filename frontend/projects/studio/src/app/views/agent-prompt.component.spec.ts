// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { PromptPreview } from '../core/agent-center-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AgentPromptComponent } from './agent-prompt.component';

const URL = '/studio/api/agent-center/prompt';
const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));
const JE_ZUG = [
  'result_schema', 'host_capabilities', 'page_context', 'host_instruction',
  'skill_hints', 'history', 'prefetch', 'last_shown', 'message',
];

function vorschau(masterSkill: Record<string, unknown> = {}): PromptPreview {
  return {
    locale: 'de',
    chain: [
      { id: 'head', text: 'Du bist BOERDi.\n\nSPRACHE: Antworte …', chars: 2345 },
      {
        id: 'master_skill', state: 'on', text: '## Master-Skill\n\nText', chars: 28000,
        node_id: 'k-1', sha256: '8bbf014fa385d526'.padEnd(64, '0'), error: null, ...masterSkill,
      },
      ...JE_ZUG.map((id) => ({ id })),
    ],
    tools: { count: 27, chars: 41234 },
  };
}

interface Harness {
  fixture: ComponentFixture<AgentPromptComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

async function mount(open: boolean): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(AgentPromptComponent);
  fixture.componentRef.setInput('section', {
    panel: 'agent-prompt',
    labelKey: 'curated.agent.prompt.label',
    hintKey: 'curated.agent.prompt.hint',
  });
  fixture.componentRef.setInput('open', open);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
}

async function flush(h: Harness, body: object, locale = 'de'): Promise<void> {
  const req = h.http.expectOne((r) => r.url === URL);
  expect(req.request.params.get('locale')).toBe(locale);
  req.flush(body);
  await tick();
  await h.fixture.whenStable();
}

async function loaded(body: PromptPreview = vorschau()): Promise<Harness> {
  const h = await mount(true);
  await flush(h, body);
  return h;
}

const text = (node: Element | null): string => (node?.textContent ?? '').replace(/\s+/g, ' ').trim();

describe('AgentPromptComponent (ST-8d)', () => {
  it('lädt erst beim Aufklappen', async () => {
    const h = await mount(false);
    h.http.expectNone((r) => r.url === URL);
    const details = h.el.querySelector('details')!;
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await h.fixture.whenStable();
    await flush(h, vorschau());
    expect(h.el.querySelector('.agp-chain')).not.toBeNull();
  });

  it('zeigt die Kette als nummerierte Folge in der Reihenfolge des Zugs', async () => {
    const { el } = await loaded();
    const schritte = Array.from(el.querySelectorAll('ol.agp-chain > li'));
    expect(schritte).toHaveLength(11);
    expect(text(schritte[0].querySelector('.agp-name'))).toBe('Kopf: Rolle, Anrede, Grenzen, Sprache');
    expect(text(schritte[1].querySelector('.agp-name'))).toBe('Master-Skill');
    // Paket C: was die Person zuletzt gesehen hat — ein bekanntes Glied, keine rohe Kennung.
    expect(text(schritte[9].querySelector('.agp-name'))).toBe('Zuletzt gezeigt');
    expect(text(schritte[10].querySelector('.agp-name'))).toBe('Nachricht der Person');
  });

  it('zeigt den Kopf im Wortlaut, als reinen Text und mit seiner Länge', async () => {
    const { el } = await loaded();
    const kopf = el.querySelector('ol.agp-chain > li')!;
    expect(text(kopf.querySelector('.agp-meta'))).toBe('2.345 Zeichen');
    const pre = kopf.querySelector('pre')!;
    expect(pre.textContent).toBe('Du bist BOERDi.\n\nSPRACHE: Antworte …');
    expect(pre.getAttribute('tabindex')).toBe('0');
  });

  // Review-Befund 2026-09-27: die Länge ist die des Blocks im Prompt (mit Rahmen),
  // die Prüfsumme die des Dokuments — wie im Master-Skill-Panel darunter.
  it('nennt beim Master-Skill die Länge im Prompt und die Prüfsumme des Dokuments', async () => {
    const { el } = await loaded();
    const skill = el.querySelectorAll('ol.agp-chain > li')[1];
    expect(text(skill.querySelector('.agp-meta')))
      .toBe('28.000 Zeichen im Prompt · Prüfsumme des Dokuments 8bbf014fa385');
  });

  it.each([
    [{ state: 'off', text: null, chars: 0 }, 'Aus: der Agent arbeitet ohne Master-Skill.'],
    [{ state: 'no_node', text: null, chars: 0 }, 'An, aber kein Knoten gepflegt (MASTER_SKILL_NODE_ID).'],
    [{ state: 'failed', text: null, chars: 0, error: 'Server lehnte ab: timeout' },
      'An, aber nicht geladen: Server lehnte ab: timeout. Der Zug läuft ohne.'],
  ])('sagt, warum der Master-Skill fehlt (%o)', async (abweichung, satz) => {
    const { el } = await loaded(vorschau(abweichung));
    const skill = el.querySelectorAll('ol.agp-chain > li')[1];
    expect(text(skill.querySelector('.agp-meta'))).toBe(satz);
    expect(skill.querySelector('pre')).toBeNull();
  });

  it('sagt bei den Blöcken je Zug, wann sie erscheinen, statt Text zu erfinden', async () => {
    const { el } = await loaded();
    const seite = el.querySelectorAll('ol.agp-chain > li')[4];
    expect(text(seite.querySelector('.agp-name'))).toBe('Seitenkontext');
    expect(text(seite.querySelector('.agp-when')))
      .toBe('Wenn die Seite eine Sammlung, einen Inhalt oder eine Themenseite zeigt.');
    expect(seite.querySelector('pre')).toBeNull();
  });

  it('nennt Zahl und Umfang der Werkzeug-Beschreibungen', async () => {
    const { el } = await loaded();
    expect(text(el.querySelector('.agp-tools')))
      .toBe('Dazu gehen 27 Werkzeug-Beschreibungen mit 41.234 Zeichen mit — in jeder Runde.');
  });

  it('lädt in der gewählten Widget-Sprache neu', async () => {
    const h = await loaded();
    const englisch = h.el.querySelector<HTMLInputElement>('input[type="radio"][value="en"]')!;
    englisch.checked = true;
    englisch.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    await flush(h, { ...vorschau(), locale: 'en' }, 'en');
    expect(h.el.querySelector('.agp-chain')).not.toBeNull();
  });

  it('zeigt einen Fehler mit erneutem Versuch', async () => {
    const h = await mount(true);
    h.http.expectOne((r) => r.url === URL).flush({ detail: 'kaputt' }, { status: 500, statusText: 'x' });
    await tick();
    await h.fixture.whenStable();
    const alarm = h.el.querySelector('[role="alert"]')!;
    expect(text(alarm)).toContain('kaputt');
    alarm.querySelector('button')!.click();
    await h.fixture.whenStable();
    await flush(h, vorschau());
    expect(h.el.querySelector('[role="alert"]')).toBeNull();
  });
});
