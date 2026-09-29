// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, type TestRequest } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AgentProbeComponent } from './agent-probe.component';

const URL = '/studio/api/chat';
const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const ANTWORT = {
  session_id: 'x',
  content: 'Hier sind zwei Materialien zur Optik.',
  cards: [{ node_id: 'n-1' }, { node_id: 'n-2' }],
  inline_documents: [{ title: 'Arbeitsblatt Linsen' }],
  result_stop_reason: 'text',
  debug: {
    engine: 'agent',
    token_usage: { prompt_tokens: 1200, cached_tokens: 900, completion_tokens: 80 },
    trace: [
      {
        step: 'agent_round', duration_ms: 3100,
        data: { runde: 1, dauer_ms: 3100, werkzeuge: [{ name: 'search_wlo_content', argumente: ['query'] }] },
      },
      { step: 'agent_stop', duration_ms: 3100, data: { stop_reason: 'text', runden: 1 } },
    ],
  },
};

interface Harness {
  fixture: ComponentFixture<AgentProbeComponent>;
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
  const fixture = TestBed.createComponent(AgentProbeComponent);
  fixture.componentRef.setInput('section', {
    panel: 'agent-probe',
    labelKey: 'curated.agent.probe.label',
    hintKey: 'curated.agent.probe.hint',
  });
  fixture.componentRef.setInput('open', true);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
}

async function sende(h: Harness, nachricht: string): Promise<void> {
  const feld = h.el.querySelector<HTMLTextAreaElement>('#apr-message')!;
  feld.value = nachricht;
  feld.dispatchEvent(new Event('input'));
  h.el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  await h.fixture.whenStable();
}

async function antworte(h: Harness, body: object = ANTWORT): Promise<TestRequest> {
  const req = h.http.expectOne(URL);
  req.flush(body);
  await tick();
  await h.fixture.whenStable();
  return req;
}

const text = (node: Element | null): string => (node?.textContent ?? '').replace(/\s+/g, ' ').trim();

function sitzung(el: HTMLElement): string {
  return text(el.querySelector('.apr-session code'));
}

function fakt(zug: Element, label: string): string | null {
  for (const paar of Array.from(zug.querySelectorAll('.apr-facts > div'))) {
    if (text(paar.querySelector('dt')) === label) return text(paar.querySelector('dd'));
  }
  return null;
}

describe('AgentProbeComponent (ST-8e)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sagt vor dem Senden, was ein Zug kostet und unter welcher Sitzung er steht', async () => {
    const { el } = await mount();
    expect(text(el.querySelector('.apr-cost'))).toContain('kostet wie einer');
    expect(sitzung(el)).toMatch(/^studio-[0-9a-f-]{36}$/);
    expect(text(el.querySelector('label[for="apr-message"]'))).toBe('Nachricht');
  });

  it('fährt den echten Chat-Weg mit der Agent-Maschine', async () => {
    const h = await mount();
    await sende(h, '  Zeig mir Material zu Linsen  ');
    const req = await antworte(h);
    expect(req.request.method).toBe('POST');
    expect(req.request.headers.get('X-Boerdi-Engine')).toBe('agent');
    expect(req.request.body).toEqual({
      session_id: sitzung(h.el),
      message: 'Zeig mir Material zu Linsen',
      environment: { locale: 'de' },
    });
  });

  it('zeigt je Zug Nachricht, Antwort, Dauer, Karten, Dokument-Boxen und die Spur', async () => {
    const h = await mount();
    const uhr = vi.spyOn(performance, 'now');
    uhr.mockReturnValueOnce(1000).mockReturnValueOnce(13345);
    await sende(h, 'Zeig mir Material zu Linsen');
    await antworte(h);
    const zug = h.el.querySelector('ol.apr-turns > li')!;
    expect(text(zug.querySelector('.apr-message'))).toBe('Zeig mir Material zu Linsen');
    expect(text(zug.querySelector('.apr-answer'))).toBe('Hier sind zwei Materialien zur Optik.');
    expect(fakt(zug, 'Dauer')).toBe('12,3 s');
    expect(fakt(zug, 'Karten')).toBe('2');
    expect(fakt(zug, 'Dokument-Boxen')).toBe('Arbeitsblatt Linsen');
    expect(text(zug.querySelector('studio-agent-trace'))).toContain('Agent-Schleife');
    expect(zug.querySelector('studio-agent-trace .atr-table tbody tr')).not.toBeNull();
    expect(h.el.querySelector<HTMLTextAreaElement>('#apr-message')!.value).toBe('');
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toBe('Zug fertig nach 12,3 s.');
  });

  it('bleibt für Folgezüge in derselben Sitzung', async () => {
    const h = await mount();
    await sende(h, 'Erste Frage');
    const erste = await antworte(h);
    await sende(h, 'Und weiter?');
    const zweite = await antworte(h);
    expect(zweite.request.body.session_id).toBe(erste.request.body.session_id);
    expect(h.el.querySelectorAll('ol.apr-turns > li')).toHaveLength(2);
  });

  it('beginnt mit „Neues Gespräch" eine neue Sitzung', async () => {
    const h = await mount();
    await sende(h, 'Erste Frage');
    await antworte(h);
    const vorher = sitzung(h.el);
    h.el.querySelector<HTMLButtonElement>('.apr-reset')!.click();
    await h.fixture.whenStable();
    expect(sitzung(h.el)).not.toBe(vorher);
    expect(sitzung(h.el)).toMatch(/^studio-/);
    expect(h.el.querySelector('ol.apr-turns')).toBeNull();
    expect(text(h.el.querySelector('[aria-live="polite"]'))).toBe('Neues Gespräch begonnen.');
  });

  it('schickt die gewählte Widget-Sprache mit', async () => {
    const h = await mount();
    const wahl = h.el.querySelector<HTMLSelectElement>('#apr-locale')!;
    wahl.value = 'en';
    wahl.dispatchEvent(new Event('change'));
    await sende(h, 'Hello');
    const req = await antworte(h);
    expect(req.request.body.environment).toEqual({ locale: 'en' });
  });

  it('prüft eine leere Nachricht am Feld, ohne zu senden', async () => {
    const h = await mount();
    await sende(h, '   ');
    const feld = h.el.querySelector<HTMLTextAreaElement>('#apr-message')!;
    expect(feld.getAttribute('aria-invalid')).toBe('true');
    expect(feld.getAttribute('aria-describedby')).toBe('apr-message-hint apr-message-error');
    expect(text(h.el.querySelector('#apr-message-error'))).toBe('Bitte eine Nachricht eingeben.');
    expect(h.el.querySelector('#apr-message-error')!.getAttribute('role')).toBe('alert');
    h.http.expectNone(URL);
  });

  it('sperrt die Knöpfe während des Zugs', async () => {
    const h = await mount();
    await sende(h, 'Frage');
    const senden = h.el.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    expect(senden.disabled).toBe(true);
    expect(text(senden)).toBe('Läuft …');
    expect(h.el.querySelector<HTMLButtonElement>('.apr-reset')!.disabled).toBe(true);
    await antworte(h);
    expect(senden.disabled).toBe(false);
  });

  it('zeigt einen Fehler und behält die Nachricht', async () => {
    const h = await mount();
    await sende(h, 'Frage');
    h.http.expectOne(URL).flush({ detail: 'Zu viele Anfragen' }, { status: 429, statusText: 'x' });
    await tick();
    await h.fixture.whenStable();
    expect(text(h.el.querySelector('[role="alert"]'))).toContain('Zu viele Anfragen');
    expect(h.el.querySelector<HTMLTextAreaElement>('#apr-message')!.value).toBe('Frage');
    expect(h.el.querySelector('ol.apr-turns')).toBeNull();
  });
});
