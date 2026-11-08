// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { type AblaufBefund, AblaufApi } from '../core/ablauf-api.service';
import { pathKey } from '../core/field-problems';
import { StudioApiError } from '../core/studio-api-error';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { ChoicesApi } from '../core/choices-api.service';
import { AblaufPruefenComponent } from './ablauf-pruefen.component';
import { AREA_SCHEMAS } from './area-schemas.fixture';
import { SchemaFormComponent } from './schema-form.component';
import { FORM_BEFUNDE, type FormBefund } from './form-befunde';
import { FORM_EPOCHE } from './form-epoche';

/**
 * Paket K2c-4: „Ablauf prüfen“ — Befunde am Schritt, im Formular gemeldet (ohne Sperre), ein Stand,
 * der mit der nächsten Änderung abläuft; und die Schrittfolge live aus dem Entwurf.
 */
const ABLAUF = { id: 'a', schritte: [
  { id: 'start', typ: 'nachricht' },
  { id: 'holen', typ: 'auftrag', bei_fehler: 'fehler' },
  { id: 'fehler', typ: 'nachricht', weiter: 'gibtsnicht' },
  { id: 'ende', typ: 'ende' },
] };

interface Harness {
  fixture: ComponentFixture<AblaufPruefenComponent>;
  el: HTMLElement;
  gesetzt: [string, ReadonlyMap<string, string>][];
  entfernt: string[];
  epoche: ReturnType<typeof signal<number>>;
  antworten: ((wert: unknown) => Promise<readonly AblaufBefund[]>)[];
}

function mount(wert: unknown = ABLAUF, pfad: (string | number)[] = ['ablaeufe', 0]): Harness {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  const h = { gesetzt: [], entfernt: [], epoche: signal(0), antworten: [] } as unknown as Harness;
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(),
    { provide: AblaufApi, useValue: { pruefen: (w: unknown) => h.antworten.shift()!(w) } },
    { provide: FORM_BEFUNDE, useValue: {
      setzen: (q: string, b: readonly FormBefund[]) =>
        h.gesetzt.push([q, new Map(b.map((x) => [pathKey(x.pfad), x.text]))]),
      entfernen: (q: string) => h.entfernt.push(q),
    } },
    { provide: FORM_EPOCHE, useValue: h.epoche },
  ] });
  h.fixture = TestBed.createComponent(AblaufPruefenComponent);
  h.fixture.componentRef.setInput('wert', wert);
  h.fixture.componentRef.setInput('pfad', pfad);
  h.fixture.componentRef.setInput('idBasis', 'sf-a');
  h.fixture.detectChanges();
  h.el = h.fixture.nativeElement as HTMLElement;
  return h;
}

async function pruefe(h: Harness, antwort: (wert: unknown) => Promise<readonly AblaufBefund[]>): Promise<void> {
  h.antworten.push(antwort);
  (h.el.querySelector('#sf-a-knopf') as HTMLButtonElement).click();
  await h.fixture.whenStable();
  h.fixture.detectChanges();
}

const status = (h: Harness) => h.el.querySelector('.ap-status')!.textContent!.trim();
const zeilen = (h: Harness) => [...h.el.querySelectorAll('.ap-zeile')] as HTMLElement[];

describe('AblaufPruefenComponent (K2c-4)', () => {
  it('zeigt die Schrittfolge live, unbekannte Ziele markiert', () => {
    const h = mount();
    const z = zeilen(h);
    expect(z.length).toBe(4);
    expect(z[0].textContent).toContain('→ holen');
    expect(z[1].textContent).toContain('bei Fehler → fehler');
    expect(z[2].querySelector('.ap-unbekannt')!.textContent).toContain('gibtsnicht');
    expect(z[3].textContent).toContain('Endet hier');
    expect(status(h)).toBe('');
  });

  it('Prüfen: Befunde am Schritt, im Formular unter dem Pfad des Schritts, die des Ablaufs oben', async () => {
    const h = mount();
    let geschickt: unknown;
    await pruefe(h, async (w) => {
      geschickt = w;
      return [
        { schritt: 'fehler', nr: 2, text: 'Ziel gibtsnicht fehlt.' },
        { schritt: 'fehler', nr: 2, text: 'Noch etwas.' },
        { schritt: null, nr: null, text: 'Ein Auftrag braucht die Anmeldung.' },
      ];
    });
    expect(geschickt).toEqual(ABLAUF);
    expect(status(h)).toBe('3 Befunde — an den Schritten markiert.');
    expect(zeilen(h)[2].querySelectorAll('.ap-befund').length).toBe(2);
    expect(zeilen(h)[2].classList).toContain('ap-mit-befund');
    expect(h.el.querySelector('.ap-befunde')!.textContent).toContain('Anmeldung');
    const [quelle, befunde] = h.gesetzt.at(-1)!;
    expect(quelle).toBe('ablaeufe.0');
    expect([...befunde]).toEqual([['ablaeufe.0.schritte.2', 'Ziel gibtsnicht fehlt. Noch etwas.']]);
  });

  it('ohne Befunde meldet es das', async () => {
    const h = mount();
    await pruefe(h, async () => []);
    expect(status(h)).toBe('Keine Befunde.');
  });

  it('eine Änderung danach macht den Stand alt: Befunde verlassen das Formular, Knopf „Erneut prüfen“', async () => {
    const h = mount();
    await pruefe(h, async () => [{ schritt: 'start', nr: 0, text: 'X.' }]);
    h.fixture.componentRef.setInput('wert', { ...ABLAUF, beschreibung: 'neu' });
    h.fixture.detectChanges();
    await h.fixture.whenStable();
    expect(status(h)).toContain('Geändert seit der Prüfung');
    expect(h.entfernt).toContain('ablaeufe.0');
    expect(h.el.querySelectorAll('.ap-befund').length).toBe(0);
    expect(h.el.querySelector('#sf-a-knopf')!.textContent!.trim()).toBe('Erneut prüfen');
  });

  it('eine Antwort, die nach einer Änderung kommt, gilt nicht', async () => {
    const h = mount();
    let loesen!: (b: readonly AblaufBefund[]) => void;
    h.antworten.push(() => new Promise((r) => { loesen = r; }));
    (h.el.querySelector('#sf-a-knopf') as HTMLButtonElement).click();
    h.fixture.componentRef.setInput('wert', { ...ABLAUF, beschreibung: 'neu' });
    h.fixture.detectChanges();
    loesen([{ schritt: 'start', nr: 0, text: 'X.' }]);
    await h.fixture.whenStable();
    h.fixture.detectChanges();
    expect(h.gesetzt).toEqual([]);
    expect(status(h)).toBe('');
  });

  it('ein Entwurf, der das Modell nicht besteht (422), meldet sich am Feld — ohne `body`', async () => {
    const h = mount();
    await pruefe(h, async () => {
      throw new StudioApiError(422, 'x', '/config/ablauf-pruefen', [
        { path: ['body', 'schritte', 1, 'id'], type: 'string_pattern_mismatch', msg: 'bad', ctx: {} },
      ]);
    });
    expect(status(h)).toContain('1 Stelle');
    expect([...h.gesetzt.at(-1)![1].keys()]).toEqual(['ablaeufe.0.schritte.1.id']);
    // Review K2c-4, Befund 1: die Meldung steht mit ihrer Stelle auch im Block
    expect(h.el.querySelector('.ap-befunde')!.textContent).toContain('schritte.1.id');
  });

  it('Befund 5: ein Wechsel des Ablaufs während der Prüfung gibt den Knopf sofort frei', async () => {
    const h = mount();
    let loesen!: (b: readonly AblaufBefund[]) => void;
    h.antworten.push(() => new Promise((r) => { loesen = r; }));
    (h.el.querySelector('#sf-a-knopf') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    expect(status(h)).toBe('Wird geprüft …');
    h.fixture.componentRef.setInput('pfad', ['ablaeufe', 1]);
    h.fixture.detectChanges();
    expect(status(h)).toBe('');
    expect(h.el.querySelector('#sf-a-knopf')!.getAttribute('aria-disabled')).toBeNull();
    loesen([{ schritt: 'start', nr: 0, text: 'X.' }]);
    await h.fixture.whenStable();
    expect(h.gesetzt).toEqual([]);
  });

  it('Befund 6: ein anderer Ablauf an derselben Stelle (nach dem Löschen) erbt keinen Stand', async () => {
    const h = mount();
    await pruefe(h, async () => []);
    h.fixture.componentRef.setInput('wert', { ...ABLAUF, id: 'anderer' });
    h.fixture.detectChanges();
    expect(status(h)).toBe('');
  });

  it('Befund 2/3: Verzweigung ohne greifende Regel und ein Schritt ohne Pfeil laufen aus', () => {
    const h = mount({ id: 'a', schritte: [
      { id: 'w', typ: 'verzweigung' },
      { id: 'x', typ: 'nachricht', weiter: [] },
    ] });
    const z = zeilen(h);
    expect(z[0].textContent).toContain('greift keine Regel → (Ende ohne „ende“-Schritt)');
    expect(z[1].textContent).toContain('(Ende ohne „ende“-Schritt)');
    expect(z[1].textContent).not.toContain('Endet hier');
  });

  it('ein anderer Fehler steht als Text da und meldet nichts ins Formular', async () => {
    const h = mount();
    await pruefe(h, async () => { throw new StudioApiError(502, 'Backend weg', '/config/ablauf-pruefen'); });
    expect(status(h)).toContain('Backend weg');
    expect(h.gesetzt).toEqual([]);
  });

  it('ein anderer Ablauf in derselben Instanz und „Verwerfen“ setzen alles zurück', async () => {
    const h = mount();
    await pruefe(h, async () => [{ schritt: 'start', nr: 0, text: 'X.' }]);
    h.fixture.componentRef.setInput('pfad', ['ablaeufe', 1]);
    h.fixture.detectChanges();
    expect(h.entfernt).toContain('ablaeufe.0');
    expect(status(h)).toBe('');
    await pruefe(h, async () => [{ schritt: 'start', nr: 0, text: 'Y.' }]);
    expect(h.gesetzt.at(-1)![0]).toBe('ablaeufe.1');
    h.epoche.set(1);
    h.fixture.detectChanges();
    expect(h.entfernt).toContain('ablaeufe.1');
    expect(status(h)).toBe('');
  });

  it('nimmt seine Befunde beim Abbau aus dem Formular', async () => {
    const h = mount();
    await pruefe(h, async () => [{ schritt: 'start', nr: 0, text: 'X.' }]);
    h.fixture.destroy();
    expect(h.entfernt.at(-1)).toBe('ablaeufe.0');
  });
});

describe('„Ablauf prüfen“ im echten Ablaufschema (K2c-4)', () => {
  it('der Befund steht am Schritt, der Eintrag ist markiert — und das Speichern bleibt frei', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: ChoicesApi, useValue: { entries: () => [], prime: async () => undefined, areaFor: () => '', catalogs: signal({}) } },
      { provide: AblaufApi, useValue: { pruefen: async () => [
        { schritt: 'zwei', nr: 1, text: 'Ziel fehlt.' }] } },
    ] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe/katalog']);
    const dokument = { ablaeufe: [{ id: 'a', titel: { de: 'A' }, schritte: [
      { id: 'eins', typ: 'nachricht' }, { id: 'zwei', typ: 'nachricht', weiter: 'weg' }] }] };
    fixture.componentRef.setInput('value', dokument);
    const gesperrt: (readonly string[])[] = [];
    fixture.componentInstance.errorsChange.subscribe((e) => gesperrt.push(e));
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const knopf = el.querySelector('.ap button') as HTMLButtonElement;
    expect(knopf).not.toBeNull();
    knopf.click();
    await fixture.whenStable();
    fixture.detectChanges();
    const zwei = [...el.querySelectorAll<HTMLButtonElement>('.ol-entry')].find((b) => b.textContent?.includes('zwei'))!;
    expect(zwei.querySelector('.ol-problem')).not.toBeNull();
    zwei.click();
    await fixture.whenStable();
    expect(el.textContent).toContain('Ziel fehlt.');
    expect(gesperrt).toEqual([]);
    // eine Änderung am Ablauf nimmt den Befund aus dem Formular
    fixture.componentRef.setInput('value', { ablaeufe: [{ ...dokument.ablaeufe[0], beschreibung: 'neu' }] });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.ol-problem')).toBeNull();
  });
});

describe('FORM_BEFUNDE im Formular (Review K2c-4)', () => {
  it('ohne Feld an der Stelle steht der Befund am nächsten darüber — und dieselbe Meldung nur einmal', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: ChoicesApi, useValue: { entries: () => [], prime: async () => undefined, areaFor: () => '', catalogs: signal({}) } },
    ] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe/katalog']);
    fixture.componentRef.setInput('value', { ablaeufe: [{ id: 'a', titel: { de: 'A' }, schritte: [
      { id: 'eins', typ: 'nachricht' }] }] });
    fixture.componentRef.setInput('problems', [
      { path: ['ablaeufe', 0, 'id'], type: 'x', msg: 'kaputt', ctx: {} }]);
    await fixture.whenStable();
    const form = fixture.componentInstance;
    const server = form.problemTexts().get('ablaeufe.0.id')!;
    form.befunde.setzen('ablaeufe.0', [
      { pfad: ['ablaeufe', 0, 'schritte', 0, 'weiter', 'list[Weiter]', 0, 'dann'], text: 'Kein Text.' },
      { pfad: ['ablaeufe', 0, 'id'], text: server },
    ]);
    expect(form.problemTexts().get('ablaeufe.0.schritte.0.weiter')).toBe('Kein Text.');
    expect(form.problemTexts().get('ablaeufe.0.id')).toBe(server);
    form.befunde.entfernen('ablaeufe.0');
    expect(form.problemTexts().has('ablaeufe.0.schritte.0.weiter')).toBe(false);
  });
});
