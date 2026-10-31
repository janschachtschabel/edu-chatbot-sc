// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';

import type { RetentionRow } from '../core/sessions-api.service';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
import { RetentionComponent } from './retention.component';

const tick = (): Promise<unknown> => new Promise((resolve) => setTimeout(resolve, 0));

const URL = '/studio/api/sessions/retention';

// Mittags gespeichert: in jeder Zeitzone von −11 bis +11 derselbe Kalendertag.
const FRISTEN: RetentionRow[] = [
  { bereich: 'messages', tage: 30, faellig: 12, aeltester: '2026-08-01T12:00:00+00:00' },
  { bereich: 'memory', tage: 30, faellig: 0, aeltester: null },
  { bereich: 'session_state', tage: 30, faellig: 0, aeltester: '2026-09-20T12:00:00+00:00' },
  { bereich: 'safety_logs', tage: 90, faellig: 3, aeltester: '2026-07-01T12:00:00+00:00' },
  { bereich: 'quality_logs', tage: 0, faellig: 0, aeltester: null },
  { bereich: 'quality_text', tage: 30, faellig: 4, aeltester: '2026-06-01T12:00:00+00:00' },
];

/** Dieselben Bereiche nach einer kürzeren Frist der Gesprächsverläufe. */
const FRISTEN_KUERZER: RetentionRow[] = FRISTEN.map((r) => (
  r.bereich === 'messages' ? { ...r, tage: 7, faellig: 40 }
    : r.bereich === 'session_state' ? { ...r, tage: 7, faellig: 5 } : r
));

const NICHTS_FAELLIG: RetentionRow[] = FRISTEN.map((r) => ({ ...r, faellig: 0 }));

interface Harness {
  fixture: ComponentFixture<RetentionComponent>;
  el: HTMLElement;
  http: HttpTestingController;
}

let current: Harness | null = null;

/** Montiert das Panel; `open` = wie auf der Seite als erster Abschnitt aufgeklappt. */
async function mount(open = true): Promise<Harness> {
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
  const fixture = TestBed.createComponent(RetentionComponent);
  fixture.componentRef.setInput('section', {
    panel: 'retention',
    labelKey: 'curated.datenschutz.retention.label',
    hintKey: 'curated.datenschutz.retention.hint',
  });
  fixture.componentRef.setInput('open', open);
  const http = TestBed.inject(HttpTestingController);
  current = { fixture, el: fixture.nativeElement as HTMLElement, http };
  await fixture.whenStable();
  return current;
}

async function mountLoaded(): Promise<Harness> {
  const h = await mount();
  h.http.expectOne(URL).flush({ fristen: FRISTEN });
  await settle(h.fixture);
  return h;
}

async function settle(fixture: ComponentFixture<unknown>): Promise<void> {
  await tick();
  await fixture.whenStable();
}

/** Die Zeile eines Protokolls — gefunden über ihre Zeilenüberschrift. */
function row(el: HTMLElement, name: string): HTMLElement {
  const head = [...el.querySelectorAll('tbody th[scope="row"]')]
    .find((th) => th.textContent?.trim() === name);
  if (!head) throw new Error(`keine Zeile „${name}"`);
  return head.closest('tr') as HTMLElement;
}

function button(scope: HTMLElement, text: string): HTMLButtonElement {
  const found = [...scope.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!found) throw new Error(`kein Knopf „${text}"`);
  return found;
}

async function press(h: Harness, text: string): Promise<void> {
  button(h.el, text).click();
  await settle(h.fixture);
}

function confirmText(h: Harness): string {
  return h.el.querySelector('.op-confirm')?.textContent ?? '';
}

/** Rückfrage öffnen; sie zählt neu (Paket 9), die Zählung wird beantwortet. */
async function armWith(h: Harness, fristen: RetentionRow[] = FRISTEN): Promise<void> {
  await press(h, 'Bereinigen …');
  h.http.expectOne((r) => r.url === URL && r.method === 'GET').flush({ fristen });
  await settle(h.fixture);
}

/** Rückfrage bestätigen, Anfrage beantworten, den Überblick neu laden lassen. */
async function runWith(h: Harness, deleted: Record<string, number>): Promise<void> {
  await armWith(h);
  await press(h, 'Jetzt bereinigen');
  const req = h.http.expectOne(URL);
  expect(req.request.method).toBe('POST');
  req.flush({ status: 'done', deleted });
  await settle(h.fixture);
  h.http.expectOne((r) => r.url === URL && r.method === 'GET').flush({ fristen: FRISTEN });
  await settle(h.fixture);
}

describe('RetentionComponent (Paket 8, A)', () => {
  afterEach(() => {
    current?.http.verify();
    current = null;
  });

  it('zeigt je Protokoll Frist, fällige Einträge und den ältesten Eintrag', async () => {
    const { el } = await mountLoaded();
    const sicherheit = row(el, 'Sicherheitsprotokoll').textContent ?? '';
    expect(sicherheit).toContain('90 Tage');
    expect(sicherheit).toContain('3 Einträge');
    expect(sicherheit).toContain('1.7.2026');
  });

  it('nennt eine Frist von 0 Tagen „unbegrenzt“ — dort wird nie etwas fällig', async () => {
    const { el } = await mountLoaded();
    const qualitaet = row(el, 'Qualitäts-Protokoll').textContent ?? '';
    expect(qualitaet).toContain('unbegrenzt');
    expect(qualitaet).toContain('nie');
    expect(qualitaet).toContain('keiner');
  });

  it('führt die Gesprächsverläufe zuerst und sagt, dass die Sitzungen bleiben', async () => {
    // Nutzer 2026-10-09: Vorgabe 30 Tage. Die Sitzungen bleiben — mit ihnen
    // gingen ihre Verbrauchszahlen; der Satz darüber muss das sagen.
    const { el } = await mountLoaded();
    const zeilen = [...el.querySelectorAll('tbody th[scope="row"]')]
      .map((th) => th.textContent?.trim());
    expect(zeilen).toEqual([
      'Chatnachrichten', 'Sitzungsgedächtnis', 'Gesprächsstand ruhender Sitzungen',
      'Sicherheitsprotokoll', 'Qualitäts-Protokoll', 'Text im Qualitäts-Protokoll',
    ]);
    const nachrichten = row(el, 'Chatnachrichten').textContent ?? '';
    expect(nachrichten).toContain('30 Tage');
    expect(nachrichten).toContain('12 Einträge');
    expect(el.querySelector('.op-lead')?.textContent)
      .toContain('Sitzungen und ihre Verbrauchszahlen bleiben');
  });

  it('nennt beide Wege, auf denen Sitzungen samt Verbrauch verschwinden (Paket 9)', async () => {
    // Review Paket 7 (MINOR 13): „sie löscht nur ‚Gespräche löschen‘“ stimmte
    // nicht — auch „Löschen“ in der Ansicht „Sessions“ nimmt den Verbrauch mit.
    const { el } = await mountLoaded();
    const lead = el.querySelector('.op-lead')?.textContent ?? '';
    expect(lead).toContain('„Sessions“');
    expect(lead).toContain('„Gespräche löschen“');
    expect(lead).toContain('Gesprächsstand');
  });

  it('sagt, dass Datenbank-Sicherungen Gelöschtes länger halten (Paket 19, N-7)', async () => {
    const { el } = await mountLoaded();
    const hinweis = el.querySelector('.rt-backups')?.textContent ?? '';
    expect(hinweis).toContain('Sicherungen');
    expect(hinweis).toContain('BACKUP_KEEP_DAYS');
    expect(hinweis).toContain('14 Tage');
  });

  it('lädt erst, wenn das Panel aufgeht', async () => {
    const h = await mount(false);
    h.http.expectNone(URL);
    const details = h.el.querySelector('details')!;
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    await settle(h.fixture);
    h.http.expectOne(URL).flush({ fristen: FRISTEN });
    await settle(h.fixture);
    expect(row(h.el, 'Sicherheitsprotokoll').textContent).toContain('90 Tage');
  });

  it('bereinigt erst nach einer Rückfrage und setzt den Fokus dort auf „Abbrechen“', async () => {
    const h = await mountLoaded();
    const region = h.el.querySelector<HTMLElement>('.op-msg[role="status"]');
    expect(region?.textContent).toBe('');

    await armWith(h);
    h.http.expectNone((r) => r.method === 'POST');
    expect(h.el.querySelector('[role="alert"]')?.textContent).toContain('endgültig');
    expect(document.activeElement?.textContent?.trim()).toBe('Abbrechen');

    await press(h, 'Jetzt bereinigen');
    h.http.expectOne((r) => r.method === 'POST')
      .flush({ status: 'done', deleted: { safety_logs: 3, quality_logs: 0 } });
    await settle(h.fixture);
    h.http.expectOne((r) => r.method === 'GET').flush({ fristen: FRISTEN });
    await settle(h.fixture);

    expect(h.el.querySelector('[role="status"]')).toBe(region);
    expect(region!.textContent).toContain('Bereinigt: 3 Sicherheits-Einträge.');
    expect(document.activeElement).toBe(button(h.el, 'Bereinigen …'));
  });

  it('zählt beim Scharfschalten neu und nennt die Zahl in der Rückfrage (Paket 9)', async () => {
    // Review Paket 7 (MINOR 16): gezählt wurde nur beim Öffnen — nach einer
    // kürzeren Frist stand die alte Zahl da, gelöscht wurde mit der neuen.
    const h = await mountLoaded();
    await press(h, 'Bereinigen …');
    expect(confirmText(h)).toContain('werden gezählt');
    expect(button(h.el, 'Jetzt bereinigen').disabled).toBe(true);

    h.http.expectOne((r) => r.method === 'GET').flush({ fristen: FRISTEN_KUERZER });
    await settle(h.fixture);
    expect(confirmText(h)).toContain(
      'Löscht jetzt endgültig 40 Nachrichten, 5 Gesprächsstände, 3 Sicherheits-Einträge und 4 Texte '
      + 'im Qualitäts-Protokoll',
    );
    expect(row(h.el, 'Chatnachrichten').textContent).toContain('40 Einträge');
    expect(button(h.el, 'Jetzt bereinigen').disabled).toBe(false);
  });

  it('sagt in der Rückfrage, wenn gerade nichts fällig ist (Paket 9)', async () => {
    const h = await mountLoaded();
    await armWith(h, NICHTS_FAELLIG);
    expect(confirmText(h)).toContain('Gerade ist nichts fällig');
  });

  it('scheitert die Zählung, bleibt die Rückfrage ohne Zahl bedienbar (Paket 9)', async () => {
    const h = await mountLoaded();
    await press(h, 'Bereinigen …');
    h.http.expectOne((r) => r.method === 'GET')
      .flush('nope', { status: 500, statusText: 'Server Error' });
    await settle(h.fixture);
    expect(confirmText(h)).toContain('alle Einträge, die älter sind als ihre Frist');
    expect(confirmText(h)).not.toContain('12 Nachrichten');
    expect(button(h.el, 'Jetzt bereinigen').disabled).toBe(false);
  });

  it('wer die Seite während des Laufs verlässt, löst keinen Fehler aus (Paket 9)', async () => {
    // Review Paket 7 (MINOR 17): der Fokus nach dem Lauf griff in eine zerstörte
    // Ansicht (Angular NG0911), und der Überblick lud noch einmal.
    const h = await mountLoaded();
    await armWith(h);
    const lauf = h.fixture.componentInstance.run();
    h.fixture.destroy();
    h.http.expectOne((r) => r.method === 'POST')
      .flush({ status: 'done', deleted: { messages: 1 } });
    await expect(lauf).resolves.toBeUndefined();
    await tick();
    h.http.expectNone((r) => r.method === 'GET');
  });

  it('eine ältere Zählung überschreibt keine neuere (Paket 9)', async () => {
    // Review Paket 7 (MINOR 18): der eigene Lader hatte keinen Schutz davor.
    const h = await mount();
    await press(h, 'Bereinigen …');
    const [beimOeffnen, beimScharfschalten] = h.http.match(URL);
    beimScharfschalten.flush({ fristen: FRISTEN_KUERZER });
    await settle(h.fixture);
    beimOeffnen.flush({ fristen: FRISTEN });
    await settle(h.fixture);
    expect(row(h.el, 'Chatnachrichten').textContent).toContain('40 Einträge');
  });

  it('zieht einen stehenden Ladefehler beim Sprachwechsel mit (Paket 9)', async () => {
    const h = await mount();
    h.http.expectOne(URL).error(new ProgressEvent('error'));
    await settle(h.fixture);
    expect(h.el.querySelector('.cs-state--error')?.textContent).toContain('Backend nicht erreichbar.');
    TestBed.inject(StudioLanguageService).toggle();
    await settle(h.fixture);
    expect(h.el.querySelector('.cs-state--error')?.textContent).toContain('Backend unreachable.');
  });

  it('Abbrechen schließt die Rückfrage ohne Anfrage', async () => {
    const h = await mountLoaded();
    await armWith(h);
    await press(h, 'Abbrechen');
    expect(h.el.querySelector('[role="alert"]')).toBeNull();
    expect(document.activeElement).toBe(button(h.el, 'Bereinigen …'));
    h.http.expectNone((r) => r.method === 'POST');
  });

  it('nennt beide Protokolle, wenn in beiden gelöscht wurde', async () => {
    const h = await mountLoaded();
    await runWith(h, { safety_logs: 1, quality_logs: 12 });
    expect(h.el.querySelector('[role="status"]')?.textContent)
      .toContain('Bereinigt: 1 Sicherheits-Eintrag und 12 Qualitäts-Einträge.');
  });

  it('nennt gelöschte Nachrichten und Gedächtnis-Einträge vor den Protokollen', async () => {
    const h = await mountLoaded();
    await runWith(h, { messages: 12, memory: 1, safety_logs: 0, quality_logs: 2 });
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain(
      'Bereinigt: 12 Nachrichten, 1 Gedächtnis-Eintrag und 2 Qualitäts-Einträge.',
    );
  });

  it('nennt geleerte Gesprächsstände ruhender Sitzungen (Paket 9, V7)', async () => {
    const h = await mountLoaded();
    await runWith(h, { messages: 2, memory: 0, session_state: 5 });
    expect(h.el.querySelector('[role="status"]')?.textContent)
      .toContain('Bereinigt: 2 Nachrichten und 5 Gesprächsstände.');
  });

  it('leert den Text im Qualitäts-Protokoll nach der Frist der Gespräche (Paket 16, D1)', async () => {
    const h = await mountLoaded();
    const text = row(h.el, 'Text im Qualitäts-Protokoll').textContent ?? '';
    expect(text).toContain('30 Tage');
    expect(text).toContain('4 Einträge');
    expect(h.el.querySelector('.op-lead')?.textContent).toContain('Text im Qualitäts-Protokoll');
    await runWith(h, { quality_logs: 2, quality_text: 4 });
    expect(h.el.querySelector('[role="status"]')?.textContent)
      .toContain('Bereinigt: 2 Qualitäts-Einträge und 4 Texte im Qualitäts-Protokoll.');
  });

  it('sagt es, wenn nichts fällig war', async () => {
    const h = await mountLoaded();
    await runWith(h, { safety_logs: 0, quality_logs: 0 });
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain('Es war nichts fällig.');
  });

  it('meldet einen laufenden Lauf (409) als Alarm und lädt den Überblick nicht neu', async () => {
    const h = await mountLoaded();
    await armWith(h);
    await press(h, 'Jetzt bereinigen');
    h.http.expectOne((r) => r.method === 'POST').flush(
      { detail: 'Die Bereinigung läuft gerade schon.' }, { status: 409, statusText: 'Conflict' },
    );
    await settle(h.fixture);
    h.http.expectNone((r) => r.method === 'GET');
    expect(h.el.querySelector('[role="alert"]')?.textContent)
      .toContain('Die Bereinigung läuft gerade schon.');
    expect(h.el.querySelector('.op-msg[role="status"]')?.textContent).toBe('');
  });

  it('sperrt den Knopf, solange der Lauf geht', async () => {
    const h = await mountLoaded();
    await armWith(h);
    await press(h, 'Jetzt bereinigen');
    const start = button(h.el, 'Wird bereinigt …');
    expect(start.disabled).toBe(true);
    h.http.expectOne((r) => r.method === 'POST')
      .flush({ status: 'done', deleted: { safety_logs: 0, quality_logs: 0 } });
    await settle(h.fixture);
    h.http.expectOne((r) => r.method === 'GET').flush({ fristen: FRISTEN });
    await settle(h.fixture);
  });

  it('zeigt einen Ladefehler mit „Erneut versuchen“', async () => {
    const h = await mount();
    h.http.expectOne(URL).flush('nope', { status: 500, statusText: 'Server Error' });
    await settle(h.fixture);
    expect(h.el.querySelector('[role="alert"]')).not.toBeNull();
    await press(h, 'Erneut versuchen');
    h.http.expectOne(URL).flush({ fristen: FRISTEN });
    await settle(h.fixture);
    expect(row(h.el, 'Sicherheitsprotokoll').textContent).toContain('90 Tage');
  });
});
