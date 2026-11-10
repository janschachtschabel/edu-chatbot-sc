// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { type AblaufZeile, AblaufApi } from '../core/ablauf-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AblaufProbeComponent, type ProbeStart } from './ablauf-probe.component';

/**
 * Paket AS-8b (Plan 2026-11-09 §5n, P-9): „Ablauf ausprobieren“ in der Vorschau — Ablauf wählen,
 * Startdaten (JSON, optional), „Ablauf starten“. Laden, leer und Fehler haben je einen Zustand.
 */
const ZEILE = (id: string, aktiv = true): AblaufZeile => ({
  key: `06-ablaeufe/${id}`, id, titel: { de: `Titel ${id}` }, aktiv, ausloeser: [], module: [],
  befunde: 0, lesbar: true,
});

interface Harness {
  fixture: ComponentFixture<AblaufProbeComponent>;
  el: HTMLElement;
  starts: (ProbeStart | null)[];
  liste: () => Promise<readonly AblaufZeile[]>;
}

async function mount(liste: () => Promise<readonly AblaufZeile[]>, vorauswahl: string | null = null
): Promise<Harness> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  const h = { starts: [], liste } as unknown as Harness;
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(),
    { provide: AblaufApi, useValue: { liste: () => h.liste() } },
  ] });
  h.fixture = TestBed.createComponent(AblaufProbeComponent);
  h.fixture.componentRef.setInput('vorauswahl', vorauswahl);
  h.fixture.componentInstance.starten.subscribe((s) => h.starts.push(s));
  h.fixture.detectChanges();
  await h.fixture.whenStable();
  h.fixture.detectChanges();
  h.el = h.fixture.nativeElement as HTMLElement;
  document.body.appendChild(h.el);               // für den Fokus
  return h;
}

const knopf = (h: Harness, text: string) => Array.from(h.el.querySelectorAll('button'))
  .find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

describe('AblaufProbeComponent (AS-8b)', () => {
  it('listet die Abläufe, ausgeschaltete erkennbar, und wählt den aus der Adresse', async () => {
    const h = await mount(async () => [ZEILE('a'), ZEILE('b', false)], 'b');
    const auswahl = h.el.querySelector('select') as HTMLSelectElement;
    const optionen = Array.from(auswahl.options).map((o) => o.textContent?.trim());
    expect(optionen).toEqual(['Titel a', 'Titel b (aus)']);
    expect(auswahl.value).toBe('b');
    expect(h.el.querySelector('label[for="' + auswahl.id + '"]')).not.toBeNull();
  });

  it('startet mit kompakten Startdaten', async () => {
    const h = await mount(async () => [ZEILE('a')]);
    const feld = h.el.querySelector('textarea') as HTMLTextAreaElement;
    feld.value = '{ "thema": "Optik" }';
    feld.dispatchEvent(new Event('input'));
    knopf(h, 'Ablauf starten')!.click();
    expect(h.starts).toEqual([{ ablauf: 'a', daten: '{"thema":"Optik"}' }]);
  });

  it('ungültige Startdaten: Meldung am Feld, kein Start, der Text bleibt', async () => {
    const h = await mount(async () => [ZEILE('a')]);
    const feld = h.el.querySelector('textarea') as HTMLTextAreaElement;
    feld.value = '[1, 2]';
    feld.dispatchEvent(new Event('input'));
    knopf(h, 'Ablauf starten')!.click();
    h.fixture.detectChanges();
    expect(h.starts).toEqual([]);
    expect(feld.getAttribute('aria-invalid')).toBe('true');
    const meldung = h.el.querySelector('#' + feld.getAttribute('aria-describedby')!.split(' ').pop());
    expect(meldung?.textContent).toContain('Objekt');
    expect(feld.value).toBe('[1, 2]');
  });

  it('eine laufende Probe lässt sich beenden', async () => {
    const h = await mount(async () => [ZEILE('a')]);
    h.fixture.componentRef.setInput('aktiv', 'a');
    h.fixture.detectChanges();
    expect(h.el.querySelector('[role="status"]')?.textContent).toContain('Titel a');
    knopf(h, 'Probe beenden')!.click();
    expect(h.starts).toEqual([null]);
  });

  it('ohne Abläufe ein Hinweis statt einer leeren Auswahl', async () => {
    const h = await mount(async () => []);
    expect(h.el.querySelector('select')).toBeNull();
    expect(h.el.textContent).toContain('Noch keine Abläufe');
  });

  it('scheitert die Liste, gibt es einen neuen Versuch', async () => {
    let mal = 0;
    const h = await mount(async () => { if (mal++ === 0) throw new Error('weg'); return [ZEILE('a')]; });
    expect(h.el.querySelector('[role="alert"]')).not.toBeNull();
    knopf(h, 'Erneut versuchen')!.click();
    await h.fixture.whenStable();
    h.fixture.detectChanges();
    expect(h.el.querySelector('select')).not.toBeNull();
  });
});

describe('AblaufProbeComponent — Review AS-8b', () => {
  it('Befund 4: bei ungültigen Startdaten springt der Fokus ins Feld', async () => {
    const h = await mount(async () => [ZEILE('a')]);
    const feld = h.el.querySelector('textarea') as HTMLTextAreaElement;
    feld.value = 'kein json';
    feld.dispatchEvent(new Event('input'));
    knopf(h, 'Ablauf starten')!.focus();
    knopf(h, 'Ablauf starten')!.click();
    h.fixture.detectChanges();
    expect(document.activeElement).toBe(feld);
  });

  it('Befund 3: nach „Probe beenden“ steht der Fokus auf „Ablauf starten“', async () => {
    const h = await mount(async () => [ZEILE('a')]);
    h.fixture.componentRef.setInput('aktiv', 'a');
    h.fixture.detectChanges();
    knopf(h, 'Probe beenden')!.focus();
    knopf(h, 'Probe beenden')!.click();
    h.fixture.componentRef.setInput('aktiv', null);   // die Vorschau beendet die Probe
    h.fixture.detectChanges();
    expect(document.activeElement).toBe(knopf(h, 'Ablauf starten'));
  });

  it('eine Kennung aus der Adresse, die es nicht gibt, wird gesagt (erst speichern)', async () => {
    const h = await mount(async () => [ZEILE('a')], 'neu_ungespeichert');
    expect(h.el.textContent).toContain('neu_ungespeichert');
    expect((h.el.querySelector('select') as HTMLSelectElement).value).toBe('a');
  });
});
