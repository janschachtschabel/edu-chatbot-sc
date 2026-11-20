// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { ChoicesApi } from '../core/choices-api.service';
import { StudioApi } from '../core/studio-api.service';
import { UiModuleApi } from '../core/ui-module-api.service';
import { FIELDS_ABLAEUFE } from '../i18n/catalogue/fields-ablaeufe';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { FORM_DOKUMENT } from './form-dokument';
import { TeilWerteComponent } from './teil-werte.component';

/**
 * Plan 2026-11-20, P6: unter „Daten“ eines Modul-Schritts stehen die Parameter des Moduls (aus dem
 * Manifest, `dienst.parameter`) als Hilfe zum Lesen — Name, Beschreibung, erlaubte Werte, Vorgabe.
 */
const CHOICES = { entries: () => [], prime: async () => undefined, areaFor: () => '', catalogs: signal({}) };

const UPLOAD = { name: 'ui_upload', dienst: { name: 'upload_angebot', parameter: {
  type: 'object', required: ['zweck'],
  properties: {
    zweck: { enum: ['bereitstellen', 'sammlungsstruktur'], description: 'Wofuer das Feld da ist.' },
    vorauswahl: { enum: ['auto', 'wlo', 'chat'], description: 'Welcher Ort vorgewaehlt ist.' },
    orte: { type: 'array', items: { enum: ['chat', 'wlo', 'namen'] } },
    erschliessen: { type: 'boolean', description: 'Haekchen.', default: true },
  } } } };

function mount(pfad: (string | number)[], schritt: Record<string, unknown>, sprache: 'de' | 'en' = 'de') {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, sprache);
  const laden = vi.fn(async () => undefined);
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(),
    { provide: ChoicesApi, useValue: CHOICES },
    { provide: UiModuleApi, useValue: { manifeste: signal(new Map([['ui_upload', UPLOAD]])), manifesteLaden: laden } },
    { provide: FORM_DOKUMENT, useValue: signal({ schritte: [schritt] }) },
  ] });
  const fixture = TestBed.createComponent(TeilWerteComponent);
  fixture.componentRef.setInput('controlId', 'sf-x');
  fixture.componentRef.setInput('value', { zweck: 'bereitstellen' });
  fixture.componentRef.setInput('pfad', pfad);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, laden };
}

const MODUL = { id: 'laden', typ: 'modul', modul: 'ui_upload', daten: { zweck: 'bereitstellen' } };

describe('Modul-Parameter unter „Daten“ (P6)', () => {
  it('zeigt je Parameter Name, Beschreibung, erlaubte Werte und Vorgabe als benannte Liste', () => {
    const { el, laden } = mount(['schritte', 0, 'daten'], MODUL);
    expect(laden).toHaveBeenCalled();
    const liste = el.querySelector('ul.mp-liste') as HTMLUListElement;
    expect(liste).not.toBeNull();
    const kopf = el.querySelector(`#${liste.getAttribute('aria-labelledby')}`);
    expect(kopf?.textContent).toContain('Parameter des Moduls ui_upload');
    // Review P6, NIT 8: die Hilfe steht auch unter der JSON-Box — sie nennt keine Tabelle
    expect(kopf?.textContent).toContain('oben eintragen');
    expect(kopf?.textContent).not.toContain('Tabelle');
    const punkte = [...liste.querySelectorAll('li')].map((li) => li.textContent?.replace(/\s+/g, ' ').trim());
    expect(punkte).toHaveLength(4);
    expect(punkte[0]).toContain('zweck');
    expect(punkte[0]).toContain('Pflicht');
    expect(punkte[0]).toContain('Erlaubte Werte: bereitstellen, sammlungsstruktur');
    expect(punkte[1]).toContain('Welcher Ort vorgewaehlt ist.');
    expect(punkte[2]).toContain('Liste aus: chat, wlo, namen');
    expect(punkte[3]).toContain('Typ: boolean');
    expect(punkte[3]).toContain('Vorgabe: true');
    // die Beschreibung stammt aus dem Manifest und ist deutsch
    expect(liste.querySelector('li [lang="de"]')?.textContent).toContain('Wofuer das Feld da ist.');
  });

  it('auf Englisch die eigenen Beschriftungen', () => {
    const { el } = mount(['schritte', 0, 'daten'], MODUL, 'en');
    const text = el.querySelector('.mp')?.textContent?.replace(/\s+/g, ' ') ?? '';
    expect(text).toContain('Parameters of module ui_upload');
    expect(text).toContain('enter them above');
    expect(text).not.toContain('table');
    expect(text).toContain('Allowed values: bereitstellen, sammlungsstruktur');
    expect(text).toContain('required');
    expect(text).toContain('Default: true');
  });

  it('nicht bei Argumenten, anderen Schritten oder Modulen ohne Dienst', () => {
    expect(mount(['schritte', 0, 'argumente'], { id: 'a', typ: 'auftrag', argumente: {} }).el.querySelector('.mp')).toBeNull();
    expect(mount(['schritte', 0, 'daten'], { ...MODUL, modul: 'ui_karte' }).el.querySelector('.mp')).toBeNull();
    const ohne = mount(['schritte', 0, 'daten'], { ...MODUL, typ: 'werkzeug' });
    expect(ohne.el.querySelector('.mp')).toBeNull();
    expect(ohne.laden).not.toHaveBeenCalled();
  });
});

/** Zweites Review P4–P6, MINOR 2: nur wo der Katalog `daten_sind_parameter` meldet (heute
 *  `ui_upload`), sind die Schritt-`daten` Parameter des Diensts — sonst Blockdaten nach `eingabe`. */
describe('Modul-Parameter nur, wo die Daten Parameter sind', () => {
  const ENTWURF = { name: 'ui_strukturentwurf', dienst: { name: 'strukturentwurf', parameter: {
    type: 'object', properties: { titel: { type: 'string', description: 'Titel.' } } } } };
  const KATALOG = { bereich: '01-base/display-rules', module: [
    { name: 'ui_upload', manifest: UPLOAD, schaltbar: { aktiv: true, agent: true }, abgeleitet: false, daten_sind_parameter: true },
    { name: 'ui_strukturentwurf', manifest: ENTWURF, schaltbar: { aktiv: true, agent: true }, abgeleitet: false, daten_sind_parameter: false },
  ] };

  async function echt(modul: string): Promise<HTMLElement> {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: ChoicesApi, useValue: CHOICES },
      { provide: StudioApi, useValue: { get: vi.fn(async () => KATALOG) } },
      { provide: FORM_DOKUMENT, useValue: signal({ schritte: [{ ...MODUL, modul }] }) },
    ] });
    const fixture = TestBed.createComponent(TeilWerteComponent);
    fixture.componentRef.setInput('controlId', 'sf-x');
    fixture.componentRef.setInput('value', {});
    fixture.componentRef.setInput('pfad', ['schritte', 0, 'daten']);
    fixture.detectChanges();
    await TestBed.inject(UiModuleApi).manifesteLaden();
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('ui_strukturentwurf (Dienst mit Parametern, Daten = Blockdaten): keine Hilfe', async () => {
    expect((await echt('ui_strukturentwurf')).querySelector('.mp')).toBeNull();
  });

  it('ui_upload: die Hilfe', async () => {
    expect((await echt('ui_upload')).querySelector('.mp')).not.toBeNull();
  });

  it('der Hinweis am Feld „Daten“ sagt, dass Liste und Prüfung der Werte nur für solche Module gelten', () => {
    const de = FIELDS_ABLAEUFE.de['feld.Schritt.daten.hint'];
    const en = FIELDS_ABLAEUFE.en['feld.Schritt.daten.hint'];
    expect(de).toContain('Nimmt das Modul die Daten als Parameter (etwa ui_upload)');
    expect(de).toContain('Blockdaten');
    expect(en).toContain('If the module takes the data as parameters (such as ui_upload)');
    expect(en).toContain('block data');
  });
});
