// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { ZugSucheComponent } from './zug-suche.component';

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));

interface Harness {
  fixture: ComponentFixture<ZugSucheComponent>;
  el: HTMLElement;
  http: HttpTestingController;
  geoeffnet: { sessionId: string; messageId: number }[];
}

async function mount(): Promise<Harness> {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [provideZonelessChangeDetection(), provideHttpClient(withXhr()), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(ZugSucheComponent);
  const geoeffnet: Harness['geoeffnet'] = [];
  fixture.componentInstance.oeffnen.subscribe((ziel) => geoeffnet.push(ziel));
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController), geoeffnet };
}

async function suche(h: Harness, nummer: string): Promise<void> {
  const feld = h.el.querySelector<HTMLInputElement>('input')!;
  feld.value = nummer;
  feld.dispatchEvent(new Event('input'));
  h.el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  await h.fixture.whenStable();
}

async function antworte(h: Harness, nummer: string, body: object, status = 200): Promise<void> {
  const anfrage = h.http.expectOne((r) => r.url === `/studio/api/sessions/zug/${nummer}`);
  if (status === 200) anfrage.flush(body);
  else anfrage.flush(body, { status, statusText: 'Fehler' });
  await tick();
  await h.fixture.whenStable();
}

const TREFFER = { session_id: 'bb-1', message_id: 7, trace_id: '4711abcdef01-x', created_at: '2026-10-30T10:00:00Z' };

describe('ZugSucheComponent (Paket 18C/D)', () => {
  it('hat ein beschriftetes Suchfeld mit Hinweis', async () => {
    const h = await mount();
    const feld = h.el.querySelector<HTMLInputElement>('input')!;
    const label = h.el.querySelector<HTMLLabelElement>(`label[for="${feld.id}"]`);
    expect(label?.textContent).toContain('Fehlernummer');
    expect(feld.getAttribute('aria-describedby')).toContain('zs-hint');
    expect(h.el.querySelector('form')!.getAttribute('role')).toBe('search');
  });

  it('ein Treffer öffnet den Verlauf an der Nachricht', async () => {
    const h = await mount();
    await suche(h, '4711abcdef01');
    await antworte(h, '4711abcdef01', [TREFFER]);
    expect(h.geoeffnet).toEqual([{ sessionId: 'bb-1', messageId: 7 }]);
    expect(h.el.textContent).toContain('Gefunden');
  });

  it('mehrere Treffer erscheinen als Liste, ein Klick öffnet den gewählten', async () => {
    const h = await mount();
    await suche(h, '4711abcd');
    await antworte(h, '4711abcd', [TREFFER, { ...TREFFER, session_id: 'bb-2', message_id: 9 }]);
    expect(h.geoeffnet).toEqual([]);
    const knoepfe = h.el.querySelectorAll<HTMLButtonElement>('.zs-hits button');
    expect(knoepfe.length).toBe(2);
    expect(h.el.textContent).toContain('2 Treffer');
    knoepfe[1].click();
    expect(h.geoeffnet).toEqual([{ sessionId: 'bb-2', messageId: 9 }]);
  });

  it('kein Treffer: sagt es und nennt die Nummer', async () => {
    const h = await mount();
    await suche(h, '4711abcdef01');
    await antworte(h, '4711abcdef01', []);
    expect(h.el.textContent).toContain('Keine Antwort mit der Fehlernummer 4711abcdef01');
    expect(h.geoeffnet).toEqual([]);
  });

  it('eine ungültige Nummer wird gar nicht erst gesucht', async () => {
    const h = await mount();
    await suche(h, 'a b');
    h.http.verify();
    const feld = h.el.querySelector<HTMLInputElement>('input')!;
    expect(feld.getAttribute('aria-invalid')).toBe('true');
    expect(h.el.querySelector('[role="alert"]')!.textContent).toContain('Buchstaben');
    expect(feld.value).toBe('a b'); // die Eingabe bleibt stehen
    // Nur Punkte: der Browser normalisierte `/zug/..` zur Sitzungsliste (Review Phase 4).
    await suche(h, '..');
    h.http.verify();
    expect(feld.getAttribute('aria-invalid')).toBe('true');
  });

  it('ein Fehler des Servers wird gemeldet, die Eingabe bleibt', async () => {
    const h = await mount();
    await suche(h, '4711abcdef01');
    await antworte(h, '4711abcdef01', { detail: 'kaputt' }, 500);
    expect(h.el.querySelector('[role="alert"]')).not.toBeNull();
    expect(h.el.querySelector<HTMLInputElement>('input')!.value).toBe('4711abcdef01');
  });
});
