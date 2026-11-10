// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { ChoicesApi } from '../core/choices-api.service';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AREA_SCHEMAS } from './area-schemas.fixture';
import { FORM_DOKUMENT } from './form-dokument';
import { SchemaFormComponent } from './schema-form.component';
import { TeilWerteComponent } from './teil-werte.component';

/**
 * Paket K2c-3: die Tabelle „Argumente“ — Zeilen lesen und schreiben, Teile zur Auswahl (Schritte
 * davor und Module), ein halber Stand schreibt nichts, „Als JSON“, und im echten Ablaufschema.
 */
const CHOICES = { entries: (name: string) => (name === 'vorgang_teile' ? [{ value: 'document', label: 'document (ui_upload)', area: '' }] : []),
  prime: async () => undefined, areaFor: () => '', catalogs: signal({}) };

interface Harness {
  fixture: ComponentFixture<TeilWerteComponent>;
  el: HTMLElement;
  werte: unknown[];
  fehler: string[];
}

function mount(value: unknown, dokument: unknown = {}, pfad: (string | number)[] = []): Harness {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(),
    { provide: ChoicesApi, useValue: CHOICES },
    { provide: FORM_DOKUMENT, useValue: signal(dokument) },
  ] });
  const fixture = TestBed.createComponent(TeilWerteComponent);
  fixture.componentRef.setInput('controlId', 'sf-x');
  fixture.componentRef.setInput('value', value);
  fixture.componentRef.setInput('pfad', pfad);
  const werte: unknown[] = [];
  const fehler: string[] = [];
  fixture.componentInstance.valueChange.subscribe((v) => werte.push(v));
  fixture.componentInstance.errorChange.subscribe((f) => fehler.push(f));
  fixture.detectChanges();
  return { fixture, el: fixture.nativeElement as HTMLElement, werte, fehler };
}

/** „Als JSON bearbeiten“ — der zweite Knopf unter der Tabelle. */
const zuJson = (h: Harness) => {
  h.el.querySelectorAll<HTMLButtonElement>('.tw-aktionen .sf-add')[1].click();
  h.fixture.detectChanges();
};

const tippe = (el: HTMLInputElement | HTMLTextAreaElement, text: string) => {
  el.value = text;
  el.dispatchEvent(new Event('input'));
};

describe('TeilWerteComponent (K2c-3)', () => {
  it('zeigt je Eintrag Name, Art und Wert', () => {
    const { el } = mount({ titel: 'fest', dokument: { $teil: 'document' } });
    const zeilen = el.querySelectorAll('.tw-zeile');
    expect(zeilen.length).toBe(2);
    expect((zeilen[1].querySelector('select') as HTMLSelectElement).value).toBe('teil');
    expect((zeilen[1].querySelector('.tw-wert') as HTMLInputElement).value).toBe('document');
  });

  it('ein geänderter Text schreibt das ganze Objekt', () => {
    const h = mount({ titel: 'fest' });
    tippe(h.el.querySelector('.tw-wert') as HTMLInputElement, 'neu');
    expect(h.werte.at(-1)).toEqual({ titel: 'neu' });
  });

  it('die Art „Teil“ schreibt einen Verweis', () => {
    const h = mount({ dokument: 'x' });
    const art = h.el.querySelector('select') as HTMLSelectElement;
    art.value = 'teil';
    art.dispatchEvent(new Event('change'));
    h.fixture.detectChanges();
    tippe(h.el.querySelector('.tw-wert') as HTMLInputElement, 'document');
    expect(h.werte.at(-1)).toEqual({ dokument: { $teil: 'document' } });
  });

  it('die Teile zur Auswahl: Schritte davor und Module', () => {
    const dok = { ablaeufe: [{ schritte: [{ id: 'a', schreibt: 'volltext' }, { id: 'b' }] }] };
    const { el } = mount({ dokument: { $teil: 'volltext' } }, dok, ['ablaeufe', 0, 'schritte', 1, 'argumente']);
    const optionen = [...el.querySelectorAll('datalist option')].map((o) => (o as HTMLOptionElement).value);
    expect(optionen).toEqual(['volltext', 'document']);
    expect((el.querySelector('.tw-wert') as HTMLInputElement).getAttribute('list')).toBe('sf-x-teile');
  });

  it('ein halber Stand schreibt nichts und sperrt das Speichern', () => {
    const h = mount({ titel: 'fest' });
    (h.el.querySelector('.tw-aktionen .sf-add') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    expect(h.el.querySelectorAll('.tw-zeile').length).toBe(2);
    expect(h.werte).toEqual([]);
    tippe(h.el.querySelectorAll<HTMLInputElement>('.tw-name')[1], 'titel');
    h.fixture.detectChanges();
    expect(h.werte).toEqual([]);
    expect(h.fehler.at(-1)).toContain('„titel“ gibt es schon');
    tippe(h.el.querySelectorAll<HTMLInputElement>('.tw-name')[1], 'zweiter');
    expect(h.werte.at(-1)).toEqual({ titel: 'fest', zweiter: '' });
    expect(h.fehler.at(-1)).toBe('');
  });

  it('kaputtes JSON in einer Zeile meldet sich, Entfernen schreibt', () => {
    const h = mount({ n: 3, titel: 'fest' });
    const json = h.el.querySelector('textarea.tw-wert') as HTMLTextAreaElement;
    tippe(json, '{');
    json.dispatchEvent(new Event('change'));   // gelesen wird beim Verlassen (Review K2c-3, Befund 2)
    expect(h.fehler.at(-1)).toContain('kein gültiges JSON');
    (h.el.querySelector('.tw-weg') as HTMLButtonElement).click();
    expect(h.werte.at(-1)).toEqual({ titel: 'fest' });
  });

  it('„Als JSON“ zeigt die JSON-Box; ein Wert, der kein Objekt ist, steht nur dort', () => {
    const h = mount({ titel: 'fest' });
    (h.el.querySelectorAll<HTMLButtonElement>('.tw-aktionen .sf-add')[1]).click();
    h.fixture.detectChanges();
    expect(h.el.querySelector('textarea[id="sf-x"]')).not.toBeNull();
    const liste = mount(['kein', 'objekt']);
    expect(liste.el.querySelector('.tw')).toBeNull();
    expect(liste.el.querySelector('textarea[id="sf-x"]')).not.toBeNull();
  });
});

/** Wie das Formular: was die Tabelle schreibt, kommt als neuer Wert zurück (Review K2c-3). */
function echo(h: Harness): void {
  h.fixture.componentRef.setInput('value', h.werte.at(-1));
  h.fixture.detectChanges();
}

describe('TeilWerteComponent — Review K2c-3', () => {
  it('Befund 1: ein ganzer Verweis steht nur als JSON da', () => {
    const { el } = mount({ $teil: 'draft' });
    expect(el.querySelector('.tw')).toBeNull();
    expect(el.querySelector('textarea[id="sf-x"]')).not.toBeNull();
  });

  it('Befund 2: eine JSON-Zeile wird erst beim Verlassen gelesen und behält Art und Schreibweise', () => {
    const h = mount({ liste: [1] });
    const feld = h.el.querySelector('textarea.tw-wert') as HTMLTextAreaElement;
    tippe(feld, '[1, 2');
    tippe(feld, '"abc"');
    expect(h.werte).toEqual([]);
    expect(h.fehler).toEqual([]);
    feld.dispatchEvent(new Event('change'));
    expect(h.werte.at(-1)).toEqual({ liste: 'abc' });
    echo(h);
    // das eigene Echo lässt den Entwurf stehen: die Zeile bleibt JSON, mit dem getippten Text
    const zeile = h.el.querySelector('.tw-zeile')!;
    expect((zeile.querySelector('select') as HTMLSelectElement).value).toBe('json');
    expect((zeile.querySelector('textarea') as HTMLTextAreaElement).value).toBe('"abc"');
  });

  it('Befund 2: ein Name behält beim Echo sein Leerzeichen am Ende', () => {
    const h = mount({ a: 'x' });
    tippe(h.el.querySelector('.tw-name') as HTMLInputElement, 'ab ');
    echo(h);
    expect((h.el.querySelector('.tw-name') as HTMLInputElement).value).toBe('ab ');
    expect(h.werte.at(-1)).toEqual({ 'ab ': 'x' });
  });

  it('Befund 3/5: zwischen Tabelle und JSON-Box nur ohne offene Meldung', () => {
    const h = mount({ a: 'x' });
    (h.el.querySelector('.tw-aktionen .sf-add') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    tippe(h.el.querySelectorAll<HTMLInputElement>('.tw-name')[1], 'a');
    h.fixture.detectChanges();
    expect(h.el.querySelectorAll<HTMLButtonElement>('.tw-aktionen .sf-add')[1].disabled).toBe(true);
    const json = mount({ a: 'x' });
    (json.el.querySelectorAll<HTMLButtonElement>('.tw-aktionen .sf-add')[1]).click();
    json.fixture.detectChanges();
    const box = json.el.querySelector('textarea[id="sf-x"]') as HTMLTextAreaElement;
    box.value = '{';
    box.dispatchEvent(new Event('input'));
    box.dispatchEvent(new Event('change'));
    json.fixture.detectChanges();
    const zurueck = [...json.el.querySelectorAll<HTMLButtonElement>('button.sf-add')].at(-1)!;
    expect(zurueck.disabled).toBe(true);
  });

  it('Befund 4: ein anderer Schritt derselben Instanz nimmt Entwurf und Meldung nicht mit', () => {
    const h = mount(undefined);
    (h.el.querySelector('.tw-aktionen .sf-add') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    tippe(h.el.querySelector('.tw-name') as HTMLInputElement, ' ');
    h.fixture.detectChanges();
    expect(h.fehler.at(-1)).toContain('Name fehlt');
    h.fixture.componentRef.setInput('controlId', 'sf-y');
    h.fixture.detectChanges();
    expect(h.el.querySelectorAll('.tw-zeile').length).toBe(0);
    expect(h.fehler.at(-1)).toBe('');
  });

  it('Review 2, Befund 1: eine Meldung der JSON-Box geht beim Schrittwechsel mit — zurückgenommen', () => {
    const h = mount({ a: 'x' });
    zuJson(h);
    const box = h.el.querySelector('textarea[id="sf-x"]') as HTMLTextAreaElement;
    box.value = '{';
    box.dispatchEvent(new Event('input'));
    box.dispatchEvent(new Event('change'));
    h.fixture.detectChanges();
    expect(h.fehler.at(-1)).toContain('Kein gültiges JSON');
    h.fixture.componentRef.setInput('controlId', 'sf-y');
    h.fixture.detectChanges();
    expect(h.fehler.at(-1)).toBe('');
    // und im nächsten Schritt ist „Als Tabelle“ nach „Als JSON“ wieder frei
    zuJson(h);
    const zurueck = [...h.el.querySelectorAll<HTMLButtonElement>('button.sf-add')].at(-1)!;
    expect(zurueck.disabled).toBe(false);
  });

  it('Review 2, Befund 3: der Wechsel der Ansicht lässt den Fokus nicht fallen', async () => {
    vi.useFakeTimers();
    try {
      const h = mount({ a: 'x' });
      document.body.appendChild(h.el);
      zuJson(h);
      vi.runAllTimers();
      expect(document.activeElement?.id).toBe('sf-x');
      [...h.el.querySelectorAll<HTMLButtonElement>('button.sf-add')].at(-1)!.click();
      h.fixture.detectChanges();
      vi.runAllTimers();
      expect(document.activeElement?.id).toBe('sf-x-name-0');
      h.el.remove();
    } finally {
      vi.useRealTimers();
    }
  });

  it('Review 2, Befund 4: sichtbare Spaltenköpfe, sobald es Zeilen gibt', () => {
    expect(mount({ a: 'x' }).el.querySelector('.tw-kopf')!.textContent).toContain('Name');
    expect(mount(undefined).el.querySelector('.tw-kopf')).toBeNull();
  });

  it('Review 2, Befund 7: „Entfernen“ einer Zeile ohne Namen nennt keine leeren Klammern', () => {
    const h = mount(undefined);
    (h.el.querySelector('.tw-aktionen .sf-add') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    expect(h.el.querySelector('.tw-weg')!.getAttribute('aria-label')).toBe('Zeile 1 entfernen');
  });

  it('Befund 7: die letzte Zeile entfernen schreibt null, nicht {}', () => {
    const h = mount({ a: 'x' });
    (h.el.querySelector('.tw-weg') as HTMLButtonElement).click();
    expect(h.werte.at(-1)).toBeNull();
  });

  it('Befund 8: die Gruppe trägt den Namen des Felds, die Meldung hängt am Feld, das sie meint', () => {
    const h = mount({ a: 'x' });
    h.fixture.componentRef.setInput('beschriftetVon', 'sf-x-label');
    h.fixture.detectChanges();
    expect(h.el.querySelector('.tw')!.getAttribute('aria-labelledby')).toBe('sf-x-label');
    const art = h.el.querySelector('select') as HTMLSelectElement;
    art.value = 'teil';
    art.dispatchEvent(new Event('change'));
    h.fixture.detectChanges();
    tippe(h.el.querySelector('.tw-wert') as HTMLInputElement, ' ');
    h.fixture.detectChanges();
    const wert = h.el.querySelector('.tw-wert') as HTMLInputElement;
    expect(wert.getAttribute('aria-invalid')).toBe('true');
    // Review K2d-1 (2), Befund 7: dazu der Pfad-Hinweis
    expect(wert.getAttribute('aria-describedby')).toBe('sf-x-tw-err sf-x-tw-pfad');
    expect(h.el.querySelector('#sf-x-tw-pfad')).not.toBeNull();
    expect((h.el.querySelector('.tw-name') as HTMLInputElement).getAttribute('aria-invalid')).toBeNull();
  });
});

describe('Argumente im echten Ablaufschema (K2c-3)', () => {
  it('ein Auftragsschritt zeigt seine Argumente als Tabelle mit den Teilen der Schritte davor', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(), { provide: ChoicesApi, useValue: CHOICES }] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe']);
    fixture.componentRef.setInput('value', { id: 'lesen', titel: { de: 'Lesen' }, schritte: [
      { id: 'lesen', typ: 'auftrag', flow: 'wlo/volltext', schreibt: 'volltext',
        argumente: { dokument: { $teil: 'document' } } }] });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const tabelle = el.querySelector('.tw[id="sf-schritte.0.argumente"]');
    expect(tabelle).not.toBeNull();
    expect((tabelle!.querySelector('select') as HTMLSelectElement).value).toBe('teil');
  });

  it('Review 2, Befund 6: der Wechsel zum nächsten Schritt nimmt die Meldung am alten Pfad zurück', async () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(), { provide: ChoicesApi, useValue: CHOICES }] });
    const fixture = TestBed.createComponent(SchemaFormComponent);
    fixture.componentRef.setInput('schema', AREA_SCHEMAS['06-ablaeufe']);
    fixture.componentRef.setInput('value', { id: 'lesen', titel: { de: 'Lesen' }, schritte: [
      { id: 'eins', typ: 'auftrag', argumente: { a: 'x' } },
      { id: 'zwei', typ: 'auftrag', argumente: { b: 'y' } }] });
    const gesperrt: (readonly string[])[] = [];
    fixture.componentInstance.errorsChange.subscribe((e) => gesperrt.push(e));
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const tabelle = el.querySelector('.tw[id="sf-schritte.0.argumente"]')!;
    const name = tabelle.querySelector('.tw-name') as HTMLInputElement;
    name.value = ' ';
    name.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(gesperrt.at(-1)).toEqual(['schritte.0.argumente']);
    const zwei = [...el.querySelectorAll<HTMLButtonElement>('.ol-entry')].find((b) => b.textContent?.includes('zwei'))!;
    zwei.click();
    await fixture.whenStable();
    expect(el.querySelector('.tw[id="sf-schritte.1.argumente"]')).not.toBeNull();
    expect(gesperrt.at(-1)).toEqual([]);
  });
});
