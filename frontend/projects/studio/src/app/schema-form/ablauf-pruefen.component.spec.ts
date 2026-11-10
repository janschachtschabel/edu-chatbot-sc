// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { type AblaufBefund, type AblaufTeil, AblaufApi } from '../core/ablauf-api.service';
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
  warnungen?: readonly string[];
  teile?: readonly AblaufTeil[];
}

function mount(wert: unknown = ABLAUF, pfad: (string | number)[] = ['ablaeufe', 0]): Harness {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  const h = { gesetzt: [], entfernt: [], epoche: signal(0), antworten: [] } as unknown as Harness;
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(),
    // AS-0: die Antwort trägt dazu Warnungen — hier keine, eigener Test unten.
    { provide: AblaufApi, useValue: { pruefen: async (w: unknown) => ({
      befunde: await h.antworten.shift()!(w), warnungen: h.warnungen ?? [], teile: h.teile ?? [] }) } },
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
    // die Attrappe hüllt die Befunde in `{befunde, warnungen}` (AS-0) — ein Takt mehr
    await new Promise((r) => setTimeout(r, 0));
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

  it('die Sicht „Daten“ gilt nur zum geprüften Stand (Review AS-Dc)', async () => {
    const h = mount();
    h.teile = [{ name: 'notiz', typen: ['text'], schreiber: [0], leser: [], vor_dem_start: false,
      aus_gespraech: false, beispiel: null }];
    const daten = () => h.el.querySelector('studio-ablauf-daten details');
    await pruefe(h, async () => []);
    expect(daten()!.textContent).toContain('notiz');
    h.fixture.componentRef.setInput('wert', { ...ABLAUF, beschreibung: 'neu' });
    h.fixture.detectChanges();
    await h.fixture.whenStable();
    expect(daten()).toBeNull();
    h.fixture.componentRef.setInput('wert', ABLAUF);
    await pruefe(h, async () => []);
    expect(daten()).not.toBeNull();
    h.epoche.set(1);
    h.fixture.detectChanges();
    expect(daten()).toBeNull();
  });

  it('nimmt seine Befunde beim Abbau aus dem Formular', async () => {
    const h = mount();
    await pruefe(h, async () => [{ schritt: 'start', nr: 0, text: 'X.' }]);
    h.fixture.destroy();
    expect(h.entfernt.at(-1)).toBe('ablaeufe.0');
  });
});

describe('Warnungen ohne Sperre (AS-0)', () => {
  it('zeigt Hinweise der Prüfung, ohne sie als Fehler zu zählen', async () => {
    const h = mount();
    h.warnungen = ['Die Wendung „los“ startet auch: b'];
    await pruefe(h, async () => []);
    // Review AS-0, Befund 6: die Live-Region sagt die Hinweise mit an
    expect(status(h)).toBe('Keine Befunde, 1 Hinweis.');
    const hinweis = h.el.querySelector('[aria-label="Hinweise"]')!;
    expect(hinweis.textContent).toContain('Hinweis: Die Wendung „los“ startet auch: b');
    expect(hinweis.querySelector('.sf-error')).toBeNull();
  });
});

describe('Tests ausführen (AS-1)', () => {
  function mitTests(ergebnisse: () => Promise<unknown>, wert: unknown) {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: AblaufApi, useValue: { pruefen: async () => ({ befunde: [], warnungen: [] }),
                                        testen: ergebnisse } },
    ] });
    const fixture = TestBed.createComponent(AblaufPruefenComponent);
    fixture.componentRef.setInput('wert', wert);
    fixture.componentRef.setInput('pfad', []);
    fixture.componentRef.setInput('idBasis', 'sf-t');
    fixture.detectChanges();
    return { fixture, el: fixture.nativeElement as HTMLElement };
  }
  const MIT_TESTS = { ...ABLAUF, tests: [{ name: 'gut' }, { name: 'schlecht' }] };

  it('ohne Testfälle sagt es, wo man sie anlegt — ohne Knopf', () => {
    const { el } = mitTests(async () => [], ABLAUF);
    expect(el.querySelector('#sf-t-tests')).toBeNull();
    expect(el.textContent).toContain('Noch keine Testfälle');
  });

  it('zeigt je Testfall bestanden oder die Abweichungen — und sagt die Zahl an', async () => {
    const { fixture, el } = mitTests(async () => [
      { name: 'gut', ok: true, status: 'fertig', weg: ['start', 'ende'], ende: 'ende', abweichungen: [] },
      { name: 'schlecht', ok: false, status: 'fehler', weg: ['start'], ende: 'start',
        abweichungen: ['Status: erwartet fertig, war fehler'] },
    ], MIT_TESTS);
    (el.querySelector('#sf-t-tests') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.ap-test-status')!.textContent!.trim())
      .toBe('2 Testfälle: 1 bestanden, 1 abweichend.');
    const zeilen = [...el.querySelectorAll('.ap-test')].map((z) => z.textContent!.replace(/\s+/g, ' ').trim());
    expect(zeilen[0]).toContain('Bestanden: gut');
    expect(zeilen[1]).toContain('Abweichung: schlecht');
    expect(zeilen[1]).toContain('Status: erwartet fertig, war fehler');
    // eine Änderung macht das Ergebnis alt
    fixture.componentRef.setInput('wert', { ...MIT_TESTS, beschreibung: 'neu' });
    fixture.detectChanges();
    expect(el.querySelector('.ap-test-status')!.textContent).toContain('geändert');
  });

  it('ein Wechsel des Ablaufs während des Testlaufs gibt den Knopf frei und verwirft die späte Antwort', async () => {
    // Review AS-1, Befund 8
    let loesen!: (e: unknown[]) => void;
    const { fixture, el } = mitTests(() => new Promise((r) => { loesen = r; }), MIT_TESTS);
    (el.querySelector('#sf-t-tests') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(el.querySelector('#sf-t-tests')!.getAttribute('aria-disabled')).toBe('true');
    fixture.componentRef.setInput('wert', { ...MIT_TESTS, id: 'anderer' });
    fixture.detectChanges();
    expect(el.querySelector('#sf-t-tests')!.getAttribute('aria-disabled')).toBeNull();
    loesen([{ name: 'gut', ok: true, status: 'fertig', weg: [], ende: '', abweichungen: [] }]);
    await new Promise((r) => setTimeout(r, 0));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.ap-test-status')!.textContent!.trim()).toBe('');
  });

  it('ein Fehler des Servers steht da, ohne Ergebnis', async () => {
    const { fixture, el } = mitTests(async () => {
      throw new StudioApiError(500, 'kaputt', '/config/ablauf-testen', []);
    }, MIT_TESTS);
    (el.querySelector('#sf-t-tests') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.ap-test-status')!.textContent).toContain('Testen ging nicht');
    expect(el.querySelector('.ap-test-status')!.textContent).toContain('kaputt');
    expect(el.querySelectorAll('.ap-test').length).toBe(0);
  });

  it('zeigt die Texte des Laufs mit eingesetzten Platzhaltern — ohne Markdown-Escapes (AS-3b)', async () => {
    const { fixture, el } = mitTests(async () => [
      { name: 'gut', ok: true, status: 'fertig', weg: [], ende: 'ende', abweichungen: [],
        texte: ['Wunsch?', 'Notiert\\: Optik \\(7\\)'] },
    ], MIT_TESTS);
    (el.querySelector('#sf-t-tests') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
    const texte = el.querySelector('.ap-texte')!;
    expect(texte.querySelector('summary')!.textContent).toContain('2 Texte des Laufs');
    expect([...texte.querySelectorAll('li')].map((li) => li.textContent!.trim()))
      .toEqual(['Wunsch?', 'Notiert: Optik (7)']);
  });
});

describe('„Ablauf prüfen“ im echten Ablaufschema (K2c-4, seit AS-0 ein Dokument je Ablauf)', () => {
  it('der Befund steht am Schritt, der Eintrag ist markiert — und das Speichern bleibt frei', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: ChoicesApi, useValue: { entries: () => [], prime: async () => undefined, areaFor: () => '', catalogs: signal({}) } },
      { provide: AblaufApi, useValue: { pruefen: async () => ({ warnungen: [], befunde: [
        { schritt: 'zwei', nr: 1, text: 'Ziel fehlt.' }] }) } },
    ] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    // AS-0: das Dokument ist der Ablauf selbst — „Prüfen“ steht an der Wurzel des Formulars.
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe']);
    const dokument = { id: 'a', titel: { de: 'A' }, schritte: [
      { id: 'eins', typ: 'nachricht' }, { id: 'zwei', typ: 'nachricht', weiter: 'weg' }] };
    fixture.componentRef.setInput('value', dokument);
    const gesperrt: (readonly string[])[] = [];
    fixture.componentInstance.errorsChange.subscribe((e) => gesperrt.push(e));
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('.ap').length).toBe(1);
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
    fixture.componentRef.setInput('value', { ...dokument, beschreibung: 'neu' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('.ol-problem')).toBeNull();
  });
});

describe('Halbe Regeln sperren aus dem Dokument (Review AS-2, Befund 2)', () => {
  it('ein Wechsel des Schritts nimmt die Sperre eines anderen nicht weg', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: ChoicesApi, useValue: { entries: () => [], prime: async () => undefined, areaFor: () => '', catalogs: signal({}) } },
      { provide: AblaufApi, useValue: { pruefen: async () => ({ befunde: [], warnungen: [] }), testen: async () => [] } },
    ] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    const gemeldet: (readonly string[])[] = [];
    fixture.componentInstance.errorsChange.subscribe((e) => gemeldet.push(e));
    const halb = [{ wenn_gewaehlt: '', dann: 'ende' }, { sonst: 'ende' }];
    const ganz = [{ wenn_gewaehlt: 'x', dann: 'ende' }, { sonst: 'ende' }];
    const ablauf = (a: unknown, b: unknown) => ({ id: 'a', titel: { de: 'A' }, schritte: [
      { id: 'a', typ: 'verzweigung', weiter: a }, { id: 'b', typ: 'verzweigung', weiter: b }, { id: 'ende', typ: 'ende' }] });
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe']);
    fixture.componentRef.setInput('value', ablauf(halb, ganz));
    await fixture.whenStable();
    expect(gemeldet.at(-1)).toEqual(['schritte.0.weiter']);
    // an B wird gearbeitet — A bleibt gesperrt
    fixture.componentRef.setInput('value', ablauf(halb, [{ wenn_gewaehlt: 'y', dann: 'a' }, { sonst: 'ende' }]));
    await fixture.whenStable();
    expect(gemeldet.at(-1)).toEqual(['schritte.0.weiter']);
    fixture.componentRef.setInput('value', ablauf(ganz, halb));
    await fixture.whenStable();
    expect(gemeldet.at(-1)).toEqual(['schritte.1.weiter']);
    fixture.componentRef.setInput('value', ablauf(ganz, ganz));
    await fixture.whenStable();
    expect(gemeldet.at(-1)).toEqual([]);
  });
});

describe('Zum Schritt springen (AS-2b)', () => {
  it('„Zum Schritt“ in der Schrittfolge wählt den Schritt in der Liste und klappt ihn auf', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(),
      { provide: ChoicesApi, useValue: { entries: () => [], prime: async () => undefined, areaFor: () => '', catalogs: signal({}) } },
      { provide: AblaufApi, useValue: { pruefen: async () => ({ befunde: [], warnungen: [] }), testen: async () => [] } },
    ] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe']);
    fixture.componentRef.setInput('value', { id: 'a', titel: { de: 'A' }, schritte: [
      { id: 'eins', typ: 'nachricht' }, { id: 'zwei', typ: 'nachricht' }, { id: 'ende', typ: 'ende' }] });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    document.body.appendChild(el);
    try {
      const knopf = el.querySelector('[aria-label="Zum Schritt zwei"]') as HTMLButtonElement;
      expect(knopf).not.toBeNull();
      knopf.click();
      await fixture.whenStable();
      fixture.detectChanges();
      await new Promise((r) => setTimeout(r, 0));
      const aktuell = el.querySelector('.ol-entry[aria-current="true"]')!;
      expect(aktuell.textContent).toContain('zwei');
      expect(document.activeElement).toBe(aktuell);
      // das Bild wählt genauso
      (el.querySelectorAll('.ab-kasten')[0] as SVGGElement).dispatchEvent(new MouseEvent('click'));
      await fixture.whenStable();
      fixture.detectChanges();
      expect(el.querySelector('.ol-entry[aria-current="true"]')!.textContent).toContain('eins');
    } finally {
      el.remove();
    }
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
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe']);
    fixture.componentRef.setInput('value', { id: 'a', titel: { de: 'A' }, schritte: [
      { id: 'eins', typ: 'nachricht' }] });
    fixture.componentRef.setInput('problems', [{ path: ['id'], type: 'x', msg: 'kaputt', ctx: {} }]);
    await fixture.whenStable();
    const form = fixture.componentInstance;
    const server = form.problemTexts().get('id')!;
    form.befunde.setzen('', [
      { pfad: ['schritte', 0, 'weiter', 'list[Weiter]', 0, 'dann'], text: 'Kein Text.' },
      { pfad: ['id'], text: server },
    ]);
    expect(form.problemTexts().get('schritte.0.weiter')).toBe('Kein Text.');
    expect(form.problemTexts().get('id')).toBe(server);
    form.befunde.entfernen('');
    expect(form.problemTexts().has('schritte.0.weiter')).toBe(false);
  });
});


describe('AblaufPruefenComponent — Im Widget ausprobieren (AS-8b)', () => {
  it('führt mit der Kennung in die Vorschau und sagt, welche Fassung gilt', () => {
    const h = mount();
    const link = h.el.querySelector('a.ap-probe') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('vorschau?ablauf=a');
    expect(link.textContent?.trim()).toBe('Im Widget ausprobieren');
    const hinweis = h.el.querySelector('#' + link.getAttribute('aria-describedby'));
    expect(hinweis?.textContent).toContain('gespeicherte');
  });

  it('ohne Kennung kein Weg', () => {
    const h = mount({ schritte: [] });
    expect(h.el.querySelector('a.ap-probe')).toBeNull();
  });
});
