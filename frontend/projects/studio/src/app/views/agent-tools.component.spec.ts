// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import type { AgentToolList } from '../core/agent-center-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AgentToolsComponent } from './agent-tools.component';

const URL = '/studio/api/agent-center/tools';
const SERVERS_URL = '/studio/api/config/mcp-servers';
/** Paket 15: die Schalter schreiben `werkzeuge_aus` der Server-Liste. */
const SERVERS = [
  { id: 'wlo-mcp', name: 'WLO', url: 'https://wlo.example/mcp', description: '', enabled: true,
    tools: ['search_wlo_content', 'get_skill', 'search_skill', 'wlo_create_content'],
    werkzeuge_aus: ['search_skill'],
    werkzeuge_im_katalog: ['get_skill', 'search_skill', 'search_wlo_content'] },
];

function antworteServer(http: HttpTestingController, servers: object[] = SERVERS): void {
  http.match(SERVERS_URL).forEach((r) => r.flush(servers, { headers: { 'X-Config-Version': '4' } }));
}
const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const LISTE: AgentToolList = {
  tools: [
    {
      name: 'search_wlo_content', kind: 'read', offered: true,
      description: 'Sucht einzelne Lerninhalte. Nutze das für konkrete Materialwünsche.',
      locks: [
        { code: 'safety_fixed', signals: ['pii'] },
        { code: 'policy', rules: ['keine-suche'] },
      ],
    },
    { name: 'get_skill', kind: 'read', offered: true, description: 'Lädt eine Anleitung.', locks: [] },
    {
      name: 'search_skill', kind: 'read', offered: false, description: 'Findet Skills.',
      locks: [{ code: 'hidden' }],
    },
    {
      name: 'wlo_create_content', kind: 'curation', offered: false,
      description: 'Legt ein Material an.',
      locks: [{ code: 'needs_access' }, { code: 'tool_mode', modes: ['read-only'] }],
    },
    { name: 'zeige_dokument', kind: 'virtual', offered: true, description: 'Liefert eine Box.', locks: [] },
  ],
};

interface Harness {
  fixture: ComponentFixture<AgentToolsComponent>;
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
      provideRouter([]),
    ],
  });
  const fixture = TestBed.createComponent(AgentToolsComponent);
  fixture.componentRef.setInput('section', {
    panel: 'agent-tools',
    labelKey: 'curated.agent.tools.label',
    hintKey: 'curated.agent.tools.hint',
  });
  fixture.componentRef.setInput('open', open);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
}

async function loaded(): Promise<Harness> {
  const h = await mount(true);
  h.http.expectOne(URL).flush(LISTE);
  antworteServer(h.http);
  await tick();
  await h.fixture.whenStable();
  return h;
}

function zeile(el: HTMLElement, name: string): HTMLTableRowElement {
  const code = Array.from(el.querySelectorAll('.agt-table tbody tr code'))
    .find((c) => c.textContent?.trim() === name);
  return code!.closest('tr')!;
}

const text = (node: Element | null): string => (node?.textContent ?? '').replace(/\s+/g, ' ').trim();

describe('AgentToolsComponent (ST-8b)', () => {
  it('lädt die Liste erst beim Aufklappen', async () => {
    const h = await mount(false);
    h.http.expectNone(URL);
    const details = h.el.querySelector('details')!;
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await h.fixture.whenStable();
    h.http.expectOne(URL).flush(LISTE);
    antworteServer(h.http);
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelectorAll('.agt-table tbody tr:not(.agt-group)')).toHaveLength(5);
  });

  // Review-Befund 2026-09-27: Krise, Drohung und harte Moderations-Sperre nehmen
  // keine einzelnen Werkzeuge — dann antwortet das Schutzmuster statt der Schleife.
  it('sagt über der Tabelle, dass bei Krise und Drohung das Schutzmuster antwortet', async () => {
    const { el } = await loaded();
    const hinweis = el.querySelector('.agt-diversion')!;
    expect(hinweis.getAttribute('role')).toBe('note');
    expect(text(hinweis)).toContain('antwortet statt der Schleife das Schutzmuster');
  });

  it('sagt, wie viele Werkzeuge ein gewöhnlicher Zug bekommt', async () => {
    const { el } = await loaded();
    expect(text(el.querySelector('.agt-summary')))
      .toBe('Ein gewöhnlicher Chat-Zug im Agent-Modus bekommt 3 von 5 Werkzeugen.');
  });

  it('gruppiert nach Art, mit Kopfzeile je Gruppe', async () => {
    const { el } = await loaded();
    const köpfe = Array.from(el.querySelectorAll('.agt-group th'));
    expect(köpfe.map((th) => th.getAttribute('scope'))).toEqual(['rowgroup', 'rowgroup', 'rowgroup']);
    expect(köpfe.map((th) => text(th.querySelector('.agt-group-name'))))
      .toEqual(['Lesend', 'Kuratierend', 'Virtuell']);
  });

  it('nennt je Werkzeug den ersten Satz, ob ein Zug es bekommt, und die Sperren', async () => {
    const { el } = await loaded();
    const suche = zeile(el, 'search_wlo_content');
    expect(text(suche.querySelector('.agt-desc'))).toBe('Sucht einzelne Lerninhalte.');
    expect(text(suche.querySelector('.agt-offered'))).toBe('ja');
    const sperren = Array.from(suche.querySelectorAll('.agt-locks li')).map((li) => text(li));
    expect(sperren[0]).toBe('Fällt weg, wenn das Regex-Gate persönliche Daten in der Nachricht '
      + 'erkennt (fest im Code).');
    expect(sperren[1]).toContain('Fällt weg, wenn die Policy-Regel keine-suche greift.');
    expect(text(zeile(el, 'wlo_create_content').querySelector('.agt-offered'))).toBe('nein');
  });

  it('verweist bei Policy-Sperren auf die Seite, auf der sie gepflegt werden', async () => {
    const { el } = await loaded();
    const link = zeile(el, 'search_wlo_content').querySelector<HTMLAnchorElement>('.agt-locks a')!;
    expect(link.getAttribute('href')).toBe('/identitaet');
    expect(text(link)).toBe('Seite Identität & Schutz');
  });

  it('sagt „immer dabei" bei einem Werkzeug ohne Sperre', async () => {
    const { el } = await loaded();
    expect(text(zeile(el, 'get_skill').querySelector('.agt-offered + td'))).toBe('immer dabei');
  });

  it('zeigt einen Fehler mit erneutem Versuch', async () => {
    const h = await mount(true);
    h.http.expectOne(URL).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await tick();
    await h.fixture.whenStable();
    const alarm = h.el.querySelector('[role="alert"]');
    expect(alarm).not.toBeNull();
    alarm!.querySelector('button')!.click();
    await h.fixture.whenStable();
    h.http.expectOne(URL).flush(LISTE);
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector('[role="alert"]')).toBeNull();
    expect(h.el.querySelector('.agt-table')).not.toBeNull();
  });
});

describe('AgentToolsComponent — Werkzeuge fremder MCP-Server (Paket 11, E)', () => {
  it('zeigt sie als eigene Gruppe „Extern“ nach den WLO-Werkzeugen', async () => {
    const h = await mount(true);
    h.http.expectOne(URL).flush({
      tools: [
        ...LISTE.tools,
        {
          name: 'wikidata__search_entities', kind: 'external', offered: true,
          description: '[Externer Dienst: Wikidata] Sucht Einträge.',
          locks: [{ code: 'tool_mode', modes: ['curate'] }],
        },
      ],
    });
    await tick();
    await h.fixture.whenStable();
    const köpfe = Array.from(h.el.querySelectorAll('.agt-group th'))
      .map((th) => text(th.querySelector('.agt-group-name')));
    expect(köpfe).toEqual(['Lesend', 'Kuratierend', 'Extern', 'Virtuell']);
  });
});

describe('AgentToolsComponent — Schalter (Paket 15)', () => {
  const schalter = (el: HTMLElement, name: string) =>
    zeile(el, name).querySelector<HTMLInputElement>('input[type="checkbox"]');

  it('zeigt die Herkunft und einen Schalter nur, wo er wirkt', async () => {
    const { el } = await loaded();
    expect(text(zeile(el, 'get_skill').querySelector('.agt-herkunft'))).toBe('WLO');
    expect(text(zeile(el, 'zeige_dokument').querySelector('.agt-herkunft'))).toBe('Eingebaut');
    expect(schalter(el, 'get_skill')?.checked).toBe(true);
    expect(schalter(el, 'search_skill')?.checked).toBe(false);
    expect(schalter(el, 'zeige_dokument')).toBeNull();
    expect(schalter(el, 'wlo_create_content')).toBeNull();
  });

  it('schaltet ein Werkzeug ab und speichert die Server-Liste mit ihrer Version', async () => {
    const h = await loaded();
    const box = schalter(h.el, 'search_wlo_content')!;
    box.checked = false;
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.dirty()).toBe(true);
    Array.from(h.el.querySelectorAll('button'))
      .find((b) => b.textContent?.trim() === 'Speichern')!.click();
    await h.fixture.whenStable();
    const put = h.http.expectOne((r) => r.url === SERVERS_URL && r.method === 'PUT');
    expect(put.request.body.expected_version).toBe(4);
    expect(put.request.body.servers[0].werkzeuge_aus).toEqual(['search_skill', 'search_wlo_content']);
    put.flush({});
    await tick();
    antworteServer(h.http);
    await tick();
    // Nach dem Speichern liest die Tabelle neu, was ein Zug jetzt bekommt.
    h.http.expectOne(URL).flush(LISTE);
    await tick();
    await h.fixture.whenStable();
    expect(h.fixture.componentInstance.dirty()).toBe(false);
  });

  it('verwirft eine Änderung', async () => {
    const h = await loaded();
    const box = schalter(h.el, 'get_skill')!;
    box.checked = false;
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    Array.from(h.el.querySelectorAll('button'))
      .find((b) => b.textContent?.trim() === 'Verwerfen')!.click();
    await h.fixture.whenStable();
    expect(schalter(h.el, 'get_skill')?.checked).toBe(true);
    expect(h.fixture.componentInstance.dirty()).toBe(false);
  });
});

describe('AgentToolsComponent — Review-Runde 2', () => {
  const FREMD = {
    name: 'wikidata__search_entities', kind: 'external', offered: true,
    description: 'Sucht Einträge.', locks: [], server_id: 'wikidata', tool: 'search_entities',
  };

  it('behauptet während des Ladens der Server-Liste nicht „fest“, und die Herkunft stimmt', async () => {
    const h = await mount(true);
    h.http.expectOne(URL).flush({ tools: [...LISTE.tools, FREMD] });
    await tick();
    await h.fixture.whenStable();
    // Die Server-Liste ist noch unterwegs (Live-Abfrage, bis 22 s).
    expect(text(zeile(h.el, 'get_skill').querySelector('.agt-schalter'))).toBe('wird geladen …');
    expect(text(zeile(h.el, 'wikidata__search_entities').querySelector('.agt-herkunft')))
      .toBe('wikidata');
    expect(text(zeile(h.el, 'zeige_dokument').querySelector('.agt-schalter'))).toBe('fest');
  });

  it('sagt „unbekannt“, wenn die Server-Liste nicht kommt', async () => {
    const h = await mount(true);
    h.http.expectOne(URL).flush(LISTE);
    h.http.match(SERVERS_URL).forEach((r) => r.flush('weg', { status: 502, statusText: 'Bad Gateway' }));
    await tick();
    await h.fixture.whenStable();
    expect(text(zeile(h.el, 'get_skill').querySelector('.agt-schalter'))).toBe('unbekannt');
  });

  it('zeigt nach 409 den Konflikt; „Neu laden“ holt Server-Liste UND Tabelle neu', async () => {
    const h = await loaded();
    const box = Array.from(h.el.querySelectorAll<HTMLInputElement>('.agt-schalter input'))[0];
    box.checked = !box.checked;
    box.dispatchEvent(new Event('change'));
    await h.fixture.whenStable();
    Array.from(h.el.querySelectorAll('button'))
      .find((b) => b.textContent?.trim() === 'Speichern')!.click();
    await h.fixture.whenStable();
    h.http.expectOne((r) => r.url === SERVERS_URL && r.method === 'PUT').flush(
      { detail: { message: 'x', version: 6, updated_by: 'studio', updated_at: '2026-10-18T08:00:00+00:00' } },
      { status: 409, statusText: 'Conflict' });
    await tick();
    await h.fixture.whenStable();
    const konflikt = h.el.querySelector('studio-save-conflict');
    expect(konflikt?.textContent).toContain('inzwischen');
    Array.from(konflikt!.querySelectorAll<HTMLButtonElement>('button'))
      .find((b) => b.textContent?.includes('Neu laden'))!.click();
    await h.fixture.whenStable();
    antworteServer(h.http);
    h.http.expectOne(URL).flush(LISTE);
    await tick();
    await h.fixture.whenStable();
    expect(h.el.querySelector('studio-save-conflict')).toBeNull();
  });
});
