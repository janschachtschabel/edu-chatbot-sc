// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { MaterialTypenComponent } from './material-typen.component';

/**
 * Materialformate (Paket 14, D3): Liste mit Filter und Suche, Detail mit gerenderter Vorschau
 * der Vorlage und den Querbezügen, Bearbeiten, Anlegen, Löschen — gespeichert wird die ganze
 * Liste über den Bereichs-Endpunkt, bedingt auf die Version.
 */
const BASE = '/studio/api/config/data/05-canvas';
const TYPEN = [
  { id: 'arbeitsblatt', label: 'Arbeitsblatt', label_en: 'Worksheet', emoji: '📝',
    category: 'didaktisch', structure: '# Arbeitsblatt: [Thema]\n\n1. Aufgabe' },
  { id: 'faktenblatt', label: 'Faktenblatt', label_en: '', emoji: '📊', category: 'analytisch',
    structure: '## Kernaussagen' },
];
const ALIASE = { arbeitsblatt: 'arbeitsblatt', worksheet: 'arbeitsblatt', aufgabenblatt: 'arbeitsblatt' };

const KONFLIKT = {
  detail: { message: 'Inzwischen geändert.', version: 12, updated_by: 'studio-form',
    updated_at: '2026-10-17T10:00:00+00:00' },
};

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));
const norm = (t: string | null | undefined): string => (t ?? '').replace(/\s+/g, ' ').trim();

describe('MaterialTypenComponent (Paket 14, D3)', () => {
  let fixture: ComponentFixture<MaterialTypenComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;

  async function settle(): Promise<void> {
    await tick();
    await fixture.whenStable();
  }

  async function laden(typen: object[] = TYPEN, version = 7): Promise<void> {
    http.expectOne(`${BASE}/material-types`).flush(
      { area: '05-canvas/material-types', type: 'yaml', version, data: { material_types: typen } });
    http.expectOne(`${BASE}/type-aliases`).flush(
      { area: '05-canvas/type-aliases', type: 'yaml', version: 2, data: { aliases: ALIASE } });
    http.expectOne(`${BASE}/persona-priorities`).flush({
      area: '05-canvas/persona-priorities', type: 'yaml', version: 1,
      data: { analytical_personas: ['P-ENT', 'P-RED'] },
    });
    await settle();
  }

  const eintraege = () => Array.from(el.querySelectorAll<HTMLButtonElement>('.mf-eintrag'));
  const knopf = (text: string) => Array.from(el.querySelectorAll<HTMLButtonElement>('button'))
    .find((b) => norm(b.textContent) === text)!;
  const reiter = (text: string) => Array.from(el.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
    .find((b) => norm(b.textContent) === text)!;

  async function tippe(selector: string, wert: string): Promise<void> {
    const feld = el.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
    feld.value = wert;
    feld.dispatchEvent(new Event('input'));
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
    fixture = TestBed.createComponent(MaterialTypenComponent);
    fixture.componentRef.setInput('section', {
      panel: 'material-typen', labelKey: 'curated.materialFormate.typen.label',
      hintKey: 'curated.materialFormate.typen.hint',
    });
    fixture.componentRef.setInput('open', true);
    http = TestBed.inject(HttpTestingController);
    el = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  it('listet die Typen mit Symbol, Name und Kennung; filtert nach Kategorie und Suche', async () => {
    await laden();
    expect(eintraege().map((b) => norm(b.textContent))).toEqual([
      '📝 Arbeitsblatt arbeitsblatt · Didaktisch', '📊 Faktenblatt faktenblatt · Analytisch',
    ]);
    const filter = Array.from(el.querySelectorAll<HTMLInputElement>('input[name="mf-filter"]'));
    expect(filter.map((r) => norm(r.closest('label')?.textContent)))
      .toEqual(['Alle (2)', 'Didaktisch (1)', 'Analytisch (1)']);
    filter[2].checked = true;
    filter[2].dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(eintraege()).toHaveLength(1);
    filter[0].checked = true;
    filter[0].dispatchEvent(new Event('change'));
    await tippe('#mf-suche', 'arbeit');
    expect(eintraege().map((b) => norm(b.textContent))).toEqual(['📝 Arbeitsblatt arbeitsblatt · Didaktisch']);
  });

  it('zeigt die Vorlage gerendert und wie der Chatbot den Typ anbietet', async () => {
    await laden();
    eintraege()[0].click();
    await fixture.whenStable();
    expect(eintraege()[0].getAttribute('aria-current')).toBe('true');
    expect(el.querySelector('.mf-detail h1')?.textContent).toBe('Arbeitsblatt: [Thema]');
    const angebot = norm(el.querySelector('.mf-angebot')?.textContent);
    expect(angebot).toContain('Chip-Text: Arbeitsblatt');
    expect(angebot).toContain('Erkannt auch als: arbeitsblatt, aufgabenblatt, worksheet');
    expect(angebot).toContain('alle Zielgruppen außer: P-ENT, P-RED');
  });

  it('warnt, wenn ein Chip-Text keinen Alias auf den Typ hat', async () => {
    await laden();
    eintraege()[1].click();
    await fixture.whenStable();
    expect(norm(el.querySelector('.mf-angebot [role="note"]')?.textContent))
      .toContain('Zu „Faktenblatt“ zeigt kein Alias auf diesen Typ');
    expect(norm(el.querySelector('.mf-angebot')?.textContent)).toContain('Steht vorn für: P-ENT, P-RED');
  });

  it('speichert eine Änderung als ganze Liste, bedingt auf die Version', async () => {
    await laden();
    eintraege()[0].click();
    await fixture.whenStable();
    reiter('Bearbeiten').click();
    await fixture.whenStable();
    expect((el.querySelector('#mf-id') as HTMLInputElement).readOnly).toBe(true);
    await tippe('#mf-label', 'Arbeitsbogen');
    // Ein ungespeicherter Entwurf sperrt die Liste — ein Wechsel verlöre ihn sonst still.
    expect(eintraege().every((b) => b.disabled)).toBe(true);
    expect(el.textContent).toContain('Erst speichern oder verwerfen');
    knopf('Speichern').click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.method === 'PUT' && r.url === `${BASE}/material-types`);
    expect(req.request.body.expected_version).toBe(7);
    expect(req.request.body.data.material_types.map((t: { label: string }) => t.label))
      .toEqual(['Arbeitsbogen', 'Faktenblatt']);
    req.flush({ area: '05-canvas/material-types', type: 'yaml', version: 8,
      data: req.request.body.data });
    await settle();
    expect(el.textContent).toContain('Gespeichert.');
    expect(eintraege().every((b) => !b.disabled)).toBe(true);
  });

  it('legt einen neuen Typ an — erst nach bestandener Prüfung', async () => {
    await laden();
    knopf('Neuer Materialtyp').click();
    await fixture.whenStable();
    await tippe('#mf-id', 'Quiz-Neu');
    knopf('Anlegen').click();
    await fixture.whenStable();
    http.expectNone((r) => r.method === 'PUT');
    const fehler = norm(el.querySelector('.mf-fehler')?.textContent);
    expect(fehler).toContain('Die Kennung darf nur a–z, Ziffern und _ enthalten.');
    expect(fehler).toContain('Bitte einen Namen angeben.');

    await tippe('#mf-id', 'quiz');
    await tippe('#mf-label', 'Quiz');
    const kategorie = el.querySelector<HTMLInputElement>('input[name="mf-kategorie"][value="didaktisch"]')!;
    kategorie.checked = true;
    kategorie.dispatchEvent(new Event('change'));
    await tippe('#mf-vorlage', '# Quiz');
    expect(el.querySelector('.mf-live h1')?.textContent).toBe('Quiz');
    knopf('Anlegen').click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.method === 'PUT');
    expect(req.request.body.data.material_types.at(-1)).toMatchObject(
      { id: 'quiz', label: 'Quiz', category: 'didaktisch', structure: '# Quiz' });
  });

  it('löscht erst nach Rückfrage', async () => {
    await laden();
    eintraege()[1].click();
    await fixture.whenStable();
    knopf('Löschen').click();
    await fixture.whenStable();
    expect(norm(el.querySelector('.mf-frage')?.textContent))
      .toContain('Den Materialtyp „Faktenblatt“ wirklich löschen?');
    http.expectNone((r) => r.method === 'PUT');
    knopf('Ja, löschen').click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.method === 'PUT');
    expect(req.request.body.data.material_types.map((t: { id: string }) => t.id)).toEqual(['arbeitsblatt']);
  });

  async function konfliktNachAenderung(): Promise<void> {
    await laden();
    eintraege()[0].click();
    await fixture.whenStable();
    reiter('Bearbeiten').click();
    await fixture.whenStable();
    await tippe('#mf-label', 'Arbeitsbogen');
    knopf('Speichern').click();
    await fixture.whenStable();
    http.expectOne((r) => r.method === 'PUT').flush(KONFLIKT, { status: 409, statusText: 'Conflict' });
    await settle();
  }

  it('meldet einen fremden Stand mit der Konflikt-Komponente; der Entwurf bleibt (§5.4)', async () => {
    await konfliktNachAenderung();
    expect(norm(el.querySelector('studio-save-conflict')?.textContent)).toContain('inzwischen');
    expect((el.querySelector('#mf-label') as HTMLInputElement).value).toBe('Arbeitsbogen');
    knopf('Neu laden').click();
    await fixture.whenStable();
    await laden(TYPEN, 9);
    expect(el.querySelector('studio-save-conflict')).toBeNull();
    expect(el.textContent).not.toContain('Ungespeicherte Änderungen');
  });

  it('„Trotzdem speichern“ schreibt den Entwurf gegen die gemeldete Version', async () => {
    await konfliktNachAenderung();
    knopf('Trotzdem speichern').click();
    await fixture.whenStable();
    const req = http.expectOne((r) => r.method === 'PUT');
    expect(req.request.body.expected_version).toBe(12);
    expect(req.request.body.data.material_types.map((t: { label: string }) => t.label))
      .toEqual(['Arbeitsbogen', 'Faktenblatt']);
    req.flush({ area: '05-canvas/material-types', type: 'yaml', version: 13,
      data: req.request.body.data });
    await settle();
    expect(el.querySelector('studio-save-conflict')).toBeNull();
    expect(el.textContent).toContain('Gespeichert.');
  });

  it('zeigt Prüffehler auch, wenn auf der Vorschau gespeichert wird (Review #3)', async () => {
    await laden();
    eintraege()[0].click();
    await fixture.whenStable();
    reiter('Bearbeiten').click();
    await fixture.whenStable();
    await tippe('#mf-label', '');
    reiter('Vorschau').click();
    await fixture.whenStable();
    knopf('Speichern').click();
    await fixture.whenStable();
    http.expectNone((r) => r.method === 'PUT');
    expect(reiter('Bearbeiten').getAttribute('aria-selected')).toBe('true');
    expect(norm(el.querySelector('.mf-fehler')?.textContent)).toContain('Bitte einen Namen angeben.');
  });

  it('hält die Statuszeile bereit, bevor eine Meldung kommt (Review #5)', async () => {
    await laden();
    const status = el.querySelectorAll('[role="status"]');
    expect(status.length).toBeGreaterThanOrEqual(1);
    expect([...status].every((s) => norm(s.textContent) === '')).toBe(true);
  });

  it('sagt, wenn das Laden scheitert, und bietet Wiederholen an', async () => {
    http.expectOne(`${BASE}/material-types`).flush({ detail: 'weg' }, { status: 503, statusText: 'x' });
    http.match(() => true).forEach((r) => r.flush({ data: {} }));
    await settle();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('weg');
    knopf('Erneut versuchen').click();
    await fixture.whenStable();
    await laden();
    expect(eintraege()).toHaveLength(2);
  });
});
