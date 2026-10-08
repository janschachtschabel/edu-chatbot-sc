// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';

import type { DbStats } from '../core/sessions-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { PrivacyPurgeComponent } from './privacy-purge.component';

const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const PURGE = '/studio/api/sessions/purge';
const STATS_URL = '/studio/api/sessions/db-stats';
const MIB = 1024 ** 2;

const STATS: DbStats = {
  size_bytes: 20.47 * MIB, live_tuples: 900, dead_tuples: 10, reclaimable_bytes: 1536,
};

interface Harness {
  fixture: ComponentFixture<PrivacyPurgeComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let current: Harness | null = null;

async function mount(): Promise<Harness> {
  TestBed.resetTestingModule();
  // jsdom meldet `en-US`; die Sätze unten sind deutsch.
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withXhr()),
      provideHttpClientTesting(),
    ],
  });
  const fixture = TestBed.createComponent(PrivacyPurgeComponent);
  fixture.componentRef.setInput('section', {
    panel: 'privacy-purge',
    labelKey: 'curated.datenschutz.purge.label',
    hintKey: 'curated.datenschutz.purge.hint',
  });
  fixture.componentRef.setInput('open', true);
  const http = TestBed.inject(HttpTestingController);
  await fixture.whenStable();
  http.expectOne(STATS_URL).flush(STATS);
  await settle(fixture);
  current = { fixture, el: fixture.nativeElement as HTMLElement, http };
  return current;
}

async function settle(fixture: ComponentFixture<unknown>): Promise<void> {
  await tick();
  await fixture.whenStable();
}

/** Die Karte unter ihrer Überschrift — so, wie man sie auf der Seite findet. */
function card(el: HTMLElement, title: string): HTMLElement {
  const heading = [...el.querySelectorAll('h4')].find((h) => h.textContent?.trim() === title);
  if (!heading) throw new Error(`keine Karte „${title}"`);
  return heading.closest('li') as HTMLElement;
}

function button(scope: HTMLElement, text: string): HTMLButtonElement {
  const found = [...scope.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!found) throw new Error(`kein Knopf „${text}"`);
  return found;
}

async function press(h: Harness, scope: HTMLElement, text: string): Promise<void> {
  button(scope, text).click();
  await settle(h.fixture);
}

/** Beide Rückfragen einer Lösch-Karte bis vor die Anfrage. */
async function armFully(h: Harness, title: string, start: string): Promise<void> {
  await press(h, card(h.el, title), start);
  await press(h, card(h.el, title), 'Weiter');
  await press(h, card(h.el, title), 'Endgültig löschen');
}

describe('PrivacyPurgeComponent (ST-6)', () => {
  afterEach(() => {
    current?.http.verify();
    current = null;
  });

  it('zeigt Größe der Datenbank und den geschätzten Platz gelöschter Zeilen', async () => {
    const { el } = await mount();
    const text = card(el, 'Datenbank aufräumen').textContent ?? '';
    expect(text).toContain('Größe der Datenbank: 20,5 MB');
    expect(text).toContain('etwa 1,5 kB');
  });

  it('sagt „etwa" nur bei einer Schätzung — ohne gelöschte Zeilen gibt es nichts zu schätzen', async () => {
    const h = await mount();
    h.fixture.componentInstance.stats.set({ ...STATS, dead_tuples: 0, reclaimable_bytes: 0 });
    await settle(h.fixture);
    const text = card(h.el, 'Datenbank aufräumen').textContent ?? '';
    expect(text).not.toContain('etwa');
    expect(text).toContain('keine gelöschten Zeilen');
  });

  it('löscht erst nach zwei Rückfragen', async () => {
    const h = await mount();
    // Paket 4b, B3: die Rückmeldung steht leer bereit.
    const region = h.el.querySelector<HTMLElement>('.op-msg[role="status"]');
    expect(region?.textContent).toBe('');
    const inhalte = (): HTMLElement => card(h.el, 'Gesprächsinhalte');

    await press(h, inhalte(), 'Gesprächsinhalte löschen …');
    h.http.expectNone(PURGE);
    expect(inhalte().querySelector('[role="alert"]')?.textContent).toContain('endgültig');

    await press(h, inhalte(), 'Weiter');
    h.http.expectNone(PURGE);
    expect(inhalte().querySelector('[role="alert"]')?.textContent).toContain('Letzte Rückfrage');

    await press(h, inhalte(), 'Endgültig löschen');
    h.http.expectOne((r) => r.url === PURGE)
      .flush({ status: 'purged', deleted: { messages: 12, memory: 1, quality_logs: 0 } });
    await settle(h.fixture);
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h.fixture);

    expect(h.el.querySelector('[role="status"]')).toBe(region);
    expect(region!.textContent).toContain('Gelöscht: 12 Nachrichten und 1 Gedächtnis-Eintrag.');
  });

  it('löscht je Karte genau ihre Tabellen', async () => {
    const faelle = [
      { title: 'Gesprächsinhalte', start: 'Gesprächsinhalte löschen …',
        safety: 'false', sessions: 'false' },
      { title: 'Gesprächsinhalte und Sitzungen', start: 'Inhalte und Sitzungen löschen …',
        safety: 'false', sessions: 'true' },
      { title: 'Alles, auch das Sicherheitsprotokoll', start: 'Alles löschen …',
        safety: 'true', sessions: 'true' },
    ];
    for (const fall of faelle) {
      const h = await mount();
      await armFully(h, fall.title, fall.start);
      const req = h.http.expectOne((r) => r.url === PURGE);
      for (const inhalt of ['messages', 'memory', 'quality_logs']) {
        expect(req.request.params.get(inhalt), `${fall.title}: ${inhalt}`).toBe('true');
      }
      expect(req.request.params.get('safety_logs'), fall.title).toBe(fall.safety);
      expect(req.request.params.get('sessions'), fall.title).toBe(fall.sessions);
      req.flush({ status: 'purged', deleted: {} });
      await settle(h.fixture);
      h.http.expectOne(STATS_URL).flush(STATS);
      await settle(h.fixture);
      h.http.verify();
    }
  });

  it('sagt an der Sitzungs-Karte, dass die Kostenzahlen mitgehen', async () => {
    // Die Datenbank löscht `usage_events` mit den Sitzungen (ON DELETE CASCADE).
    const { el } = await mount();
    expect(card(el, 'Gesprächsinhalte und Sitzungen').textContent).toContain('Kostenübersicht');
    expect(card(el, 'Gesprächsinhalte').textContent).toContain('Verbrauchszahlen');
  });

  it('setzt den Fokus beim Scharfschalten auf „Abbrechen", nicht auf das Löschen', async () => {
    const h = await mount();
    await press(h, card(h.el, 'Gesprächsinhalte'), 'Gesprächsinhalte löschen …');
    expect(document.activeElement?.textContent?.trim()).toBe('Abbrechen');
    await press(h, card(h.el, 'Gesprächsinhalte'), 'Weiter');
    expect(document.activeElement?.textContent?.trim()).toBe('Abbrechen');
  });

  it('Abbrechen schließt ohne Anfrage und gibt den Fokus an die Karte zurück', async () => {
    const h = await mount();
    const inhalte = (): HTMLElement => card(h.el, 'Gesprächsinhalte');
    for (const schritte of [[], ['Weiter']]) {
      await press(h, inhalte(), 'Gesprächsinhalte löschen …');
      for (const schritt of schritte) await press(h, inhalte(), schritt);
      await press(h, inhalte(), 'Abbrechen');
      expect(inhalte().querySelector('[role="alert"]')).toBeNull();
      expect(document.activeElement).toBe(button(inhalte(), 'Gesprächsinhalte löschen …'));
    }
    h.http.expectNone(PURGE);
  });

  it('hält nur eine Rückfrage zugleich offen', async () => {
    const h = await mount();
    await press(h, card(h.el, 'Gesprächsinhalte'), 'Gesprächsinhalte löschen …');
    await press(h, card(h.el, 'Gesprächsinhalte und Sitzungen'), 'Inhalte und Sitzungen löschen …');
    const offen = h.el.querySelectorAll('[role="alert"]');
    expect(offen.length).toBe(1);
    expect(card(h.el, 'Gesprächsinhalte und Sitzungen').contains(offen[0])).toBe(true);
  });

  it('sperrt während des Löschens jeden Knopf des Panels', async () => {
    const h = await mount();
    await armFully(h, 'Gesprächsinhalte', 'Gesprächsinhalte löschen …');
    const knoepfe = [...h.el.querySelectorAll('button')];
    expect(knoepfe.length).toBeGreaterThan(0);
    expect(knoepfe.every((b) => b.disabled)).toBe(true);
    expect(h.el.textContent).toContain('Wird gelöscht …');
    h.http.expectOne((r) => r.url === PURGE).flush({ status: 'purged', deleted: {} });
    await settle(h.fixture);
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h.fixture);
  });

  it('meldet einen Fehlschlag als Alarm und lässt die Größe stehen', async () => {
    const h = await mount();
    const region = h.el.querySelector<HTMLElement>('.op-msg[role="status"]');
    await armFully(h, 'Gesprächsinhalte', 'Gesprächsinhalte löschen …');
    h.http.expectOne((r) => r.url === PURGE)
      .flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle(h.fixture);
    h.http.expectNone(STATS_URL);
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain('⚠');
    // Zweites Review 4b: nur im Alarm, die Status-Region bleibt leer.
    expect(h.el.querySelector('.op-msg[role="status"]')).toBe(region);
    expect(region!.textContent).toBe('');
  });

  it('sagt es, wenn es nichts zu löschen gab', async () => {
    const h = await mount();
    await armFully(h, 'Gesprächsinhalte', 'Gesprächsinhalte löschen …');
    h.http.expectOne((r) => r.url === PURGE)
      .flush({ status: 'purged', deleted: { messages: 0, memory: 0, quality_logs: 0 } });
    await settle(h.fixture);
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h.fixture);
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain('Es gab nichts zu löschen.');
  });

  it('räumt nach einer Rückfrage auf und nennt die Größe vorher und nachher', async () => {
    const h = await mount();
    const db = (): HTMLElement => card(h.el, 'Datenbank aufräumen');
    await press(h, db(), 'Aufräumen …');
    h.http.expectNone('/studio/api/sessions/optimize');
    await press(h, db(), 'Jetzt aufräumen');
    const req = h.http.expectOne('/studio/api/sessions/optimize');
    expect(req.request.method).toBe('POST');
    req.flush({
      status: 'optimized', before_bytes: 2 * MIB, after_bytes: 1.5 * MIB, reclaimed_bytes: 0.5 * MIB,
    });
    await settle(h.fixture);
    h.http.expectOne(STATS_URL).flush(STATS);
    await settle(h.fixture);
    expect(h.el.querySelector('[role="status"]')?.textContent)
      .toContain('Aufgeräumt. Größe vorher 2 MB, nachher 1,5 MB.');
  });

  it('zeigt einen Ladefehler der Größe mit „Erneut versuchen"', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withXhr()),
        provideHttpClientTesting(),
      ],
    });
    const fixture = TestBed.createComponent(PrivacyPurgeComponent);
    fixture.componentRef.setInput('section', {
      panel: 'privacy-purge', labelKey: 'curated.datenschutz.purge.label',
      hintKey: 'curated.datenschutz.purge.hint',
    });
    fixture.componentRef.setInput('open', true);
    const http = TestBed.inject(HttpTestingController);
    current = { fixture, el: fixture.nativeElement as HTMLElement, http };
    await fixture.whenStable();
    http.expectOne(STATS_URL).flush('nope', { status: 500, statusText: 'Server Error' });
    await settle(fixture);

    const db = card(current.el, 'Datenbank aufräumen');
    expect(db.querySelector('[role="alert"]')).not.toBeNull();
    await press(current, db, 'Erneut versuchen');
    http.expectOne(STATS_URL).flush(STATS);
    await settle(fixture);
    expect(card(current.el, 'Datenbank aufräumen').textContent).toContain('20,5 MB');
  });
});
