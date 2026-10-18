// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AnredeComponent } from './anrede.component';

/**
 * Anrede je Zielgruppe (Paket 14, C2): im Agent-Arbeitsbereich nur Name und `formality` jeder
 * Persona — die Zuordnung gilt in beiden Modi und bleibt in den Persona-Dokumenten. Gespeichert
 * wird je Zeile das ganze Dokument, bedingt auf seine Version.
 */
const ELEMENTS = {
  personas: [
    { id: 'P-LEH', label: 'Lehrkraft', file: '04-personas/leh.md' },
    { id: 'P-LER', label: 'Lernende', file: '04-personas/ler.md' },
  ],
};
const doc = (formality: string, version: number) => ({
  area: 'x', type: 'md', version,
  data: { frontmatter: { id: 'P', label: 'L', formality, tone: 'kollegial' }, body: 'Text' },
});

const KONFLIKT = {
  detail: { message: 'Inzwischen geändert.', version: 7, updated_by: 'studio-form',
    updated_at: '2026-10-17T10:00:00+00:00' },
};

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

describe('AnredeComponent (Paket 14, C2)', () => {
  let fixture: ComponentFixture<AnredeComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;

  async function settle(): Promise<void> {
    await tick();
    await fixture.whenStable();
  }

  async function laden(): Promise<void> {
    http.expectOne('/studio/api/config/elements').flush(ELEMENTS);
    await settle();
    http.expectOne('/studio/api/config/data/04-personas/leh').flush(doc('siezen', 3));
    http.expectOne('/studio/api/config/data/04-personas/ler').flush(doc('duzen', 4));
    await settle();
  }

  const zeilen = () => Array.from(el.querySelectorAll<HTMLTableRowElement>('tbody tr'));
  const auswahl = (i: number) => zeilen()[i].querySelector<HTMLSelectElement>('select')!;
  const knopf = (i: number) => zeilen()[i].querySelector<HTMLButtonElement>('button')!;

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(), provideRouter([]),
      ],
    });
    fixture = TestBed.createComponent(AnredeComponent);
    fixture.componentRef.setInput('section', {
      panel: 'anrede', labelKey: 'curated.agentRolle.anrede.label',
      hintKey: 'curated.agentRolle.anrede.hint',
    });
    fixture.componentRef.setInput('open', true);
    http = TestBed.inject(HttpTestingController);
    el = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  it('zeigt je Zielgruppe ihre Anrede als Auswahl', async () => {
    await laden();
    expect(zeilen().map((z) => z.querySelector('th')?.textContent?.trim()))
      .toEqual(['Lehrkraft (P-LEH)', 'Lernende (P-LER)']);
    expect(auswahl(0).value).toBe('siezen');
    expect(auswahl(1).value).toBe('duzen');
    expect(Array.from(auswahl(0).options, (o) => o.textContent?.trim()))
      .toEqual(['Sie', 'du', 'wie die Person schreibt', 'ohne direkte Anrede']);
    expect(auswahl(0).labels?.[0]?.textContent).toContain('Lehrkraft');
  });

  it('speichert eine Zeile als ganzes Dokument, bedingt auf seine Version', async () => {
    await laden();
    expect(knopf(1).disabled).toBe(true);
    auswahl(1).value = 'wie_user';
    auswahl(1).dispatchEvent(new Event('change'));
    await fixture.whenStable();
    knopf(1).click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.method === 'PUT'
      && r.url === '/studio/api/config/data/04-personas/ler');
    expect(req.request.body.expected_version).toBe(4);
    expect(req.request.body.data.frontmatter).toEqual(
      { id: 'P', label: 'L', formality: 'wie_user', tone: 'kollegial' });
    expect(req.request.body.data.body).toBe('Text');
    req.flush(doc('wie_user', 5));
    await settle();
    expect(zeilen()[1].textContent).toContain('Gespeichert');
    expect(knopf(1).disabled).toBe(true);
  });

  async function konflikt(): Promise<void> {
    await laden();
    auswahl(0).value = 'duzen';
    auswahl(0).dispatchEvent(new Event('change'));
    await fixture.whenStable();
    knopf(0).click();
    await fixture.whenStable();
    http.expectOne((r) => r.method === 'PUT').flush(KONFLIKT, { status: 409, statusText: 'Conflict' });
    await settle();
  }

  const zeilenKnopf = (i: number, text: string) => Array.from(zeilen()[i].querySelectorAll('button'))
    .find((b) => b.textContent?.includes(text))!;

  it('meldet einen fremden Stand wie überall; Neu laden zeigt den gespeicherten Stand', async () => {
    await konflikt();
    expect(zeilen()[0].querySelector('studio-save-conflict')?.textContent).toContain('inzwischen');
    expect(auswahl(0).value).toBe('duzen');
    zeilenKnopf(0, 'Neu laden').click();
    await fixture.whenStable();
    http.expectOne('/studio/api/config/data/04-personas/leh').flush(doc('siezen', 6));
    await settle();
    expect(auswahl(0).value).toBe('siezen');
    expect(zeilen()[0].querySelector('studio-save-conflict')).toBeNull();
  });

  it('„Trotzdem speichern“ schreibt gegen die gemeldete Version', async () => {
    await konflikt();
    zeilenKnopf(0, 'Trotzdem speichern').click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.method === 'PUT');
    expect(req.request.body.expected_version).toBe(7);
    expect(req.request.body.data.frontmatter.formality).toBe('duzen');
    req.flush(doc('duzen', 8));
    await settle();
    expect(zeilen()[0].querySelector('studio-save-conflict')).toBeNull();
  });

  it('zählt eine ungespeicherte Wahl für den Verlassen-Schutz (Review #2)', async () => {
    await laden();
    expect(fixture.componentInstance.dirty()).toBe(false);
    auswahl(1).value = 'wie_user';
    auswahl(1).dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(fixture.componentInstance.dirty()).toBe(true);
  });

  it('hält je Zeile die Statuszeile bereit, bevor gespeichert wird (Review #5)', async () => {
    await laden();
    const status = zeilen().map((z) => z.querySelector('[role="status"]'));
    expect(status.every((s) => s !== null && s.textContent?.trim() === '')).toBe(true);
  });

  it('sagt, wenn die Liste nicht lädt, und bietet Wiederholen an', async () => {
    http.expectOne('/studio/api/config/elements')
      .flush({ detail: 'weg' }, { status: 503, statusText: 'x' });
    await settle();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('weg');
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes('Erneut'))!.click();
    await fixture.whenStable();
    http.expectOne('/studio/api/config/elements').flush(ELEMENTS);
  });

  it('nennt für „wie die Person schreibt“ den Rückfall darunter (Paket 15: dieselbe Seite)', async () => {
    await laden();
    expect(el.querySelector('a[href="/anzeige"]')).toBeNull();
    expect(el.querySelector('.an-rueckfall')?.textContent).toContain('Rückfall im Abschnitt darunter');
  });
});
