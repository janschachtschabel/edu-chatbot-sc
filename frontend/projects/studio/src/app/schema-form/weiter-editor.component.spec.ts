// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { FORM_DOKUMENT } from './form-dokument';
import { WeiterEditorComponent } from './weiter-editor.component';

/**
 * AS-2a: `weiter` eines Ablaufschritts ohne JSON — nächster Schritt, ein bestimmter Schritt oder
 * Regeln (Bedingung, Wert, Ziel). Die Ziele und Wahlen kommen aus dem Ablauf selbst.
 */
const DOK = { id: 'a', schritte: [
  { id: 'frage', typ: 'modul', modul: 'ui_entscheidung',
    daten: { frage: '?', optionen: [{ id: 'ja', label: 'Ja' }, { id: 'nein', label: 'Nein' }] } },
  { id: 'entwurf', typ: 'werkzeug', schreibt: 'draft' },
  { id: 'wohin', typ: 'verzweigung' },
  { id: 'ende', typ: 'ende' },
] };
/** Die Verzweigung — dort gelten Regeln (Review AS-2, Befund 1). */
const VERZWEIGUNG = 2;

interface Harness {
  fixture: ComponentFixture<WeiterEditorComponent>;
  el: HTMLElement;
  werte: unknown[];
  fehler: string[];
}

function mount(value: unknown, nr = 0): Harness {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(), { provide: FORM_DOKUMENT, useValue: signal(DOK) }] });
  const fixture = TestBed.createComponent(WeiterEditorComponent);
  const h: Harness = { fixture, el: fixture.nativeElement as HTMLElement, werte: [], fehler: [] };
  fixture.componentInstance.valueChange.subscribe((v) => {
    h.werte.push(v);
    fixture.componentRef.setInput('value', v);   // das Formular reicht den Wert zurück
  });
  fixture.componentInstance.errorChange.subscribe((f) => h.fehler.push(f));
  fixture.componentRef.setInput('controlId', 'sf-w');
  fixture.componentRef.setInput('value', value);
  fixture.componentRef.setInput('pfad', ['schritte', nr, 'weiter']);
  fixture.detectChanges();
  return h;
}

function waehle(h: Harness, selektor: string, wert: string): void {
  const sel = h.el.querySelector<HTMLSelectElement>(selektor)!;
  sel.value = wert;
  sel.dispatchEvent(new Event('change'));
  h.fixture.detectChanges();
}

function tippe(h: Harness, selektor: string, wert: string): void {
  const input = h.el.querySelector<HTMLInputElement>(selektor)!;
  input.value = wert;
  input.dispatchEvent(new Event('input'));
  h.fixture.detectChanges();
}

const ziele = (h: Harness, selektor: string) =>
  [...h.el.querySelectorAll<HTMLOptionElement>(`${selektor} option`)].map((o) => o.value);
const meldung = (h: Harness) => h.el.querySelector('#sf-w-fehler')?.textContent?.trim() ?? '';
const tick = () => new Promise((r) => setTimeout(r, 0));

describe('WeiterEditorComponent (AS-2a)', () => {
  it('ohne Wert: der nächste Schritt der Liste; „bestimmter Schritt“ wählt den folgenden', () => {
    const h = mount(null);
    expect(h.el.querySelector<HTMLSelectElement>('#sf-w-art')!.value).toBe('folge');
    // an einem Modul-Schritt gibt es keine Regeln (Befund 1)
    expect(ziele(h, '#sf-w-art')).toEqual(['folge', 'schritt']);
    waehle(h, '#sf-w-art', 'schritt');
    expect(h.werte.at(-1)).toBe('entwurf');
    // der eigene Schritt steht als „dieser Schritt“ da (Befund 4)
    expect(ziele(h, '#sf-w-ziel')).toEqual(['frage', 'entwurf', 'wohin', 'ende']);
    expect(h.el.querySelector('#sf-w-ziel option[value="frage"]')!.textContent).toContain('dieser Schritt');
    waehle(h, '#sf-w-ziel', 'ende');
    expect(h.werte.at(-1)).toBe('ende');
    waehle(h, '#sf-w-art', 'folge');
    expect(h.werte.at(-1)).toBeNull();
  });

  it('ein unbekanntes Ziel bleibt sichtbar und als unbekannt markiert', () => {
    const h = mount('weg');
    expect(h.el.querySelector<HTMLSelectElement>('#sf-w-ziel')!.value).toBe('weg');
    expect(h.el.querySelector('#sf-w-ziel option[value="weg"]')!.textContent).toContain('unbekannt');
  });

  it('Verzweigung: nur Regeln; die erste bringt „sonst“ mit dem bisherigen Ziel, halbe Regeln stehen am Feld', async () => {
    const h = mount('ende', VERZWEIGUNG);
    expect(h.el.querySelector('#sf-w-art')).toBeNull();
    expect(meldung(h)).toContain('braucht Regeln');
    (h.el.querySelector('.we-neu') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    expect(h.werte.at(-1)).toEqual([{ wenn_gewaehlt: '', dann: '' }, { sonst: 'ende' }]);
    expect(meldung(h)).toContain('Regel 1');
    expect(h.el.querySelector('#sf-w-wert-0')!.getAttribute('aria-invalid')).toBe('true');
    expect(h.el.querySelector('#sf-w-wert-0')!.getAttribute('aria-describedby')).toBe('sf-w-fehler');
    // Befund 6: der Fokus steht in der neuen Regel
    document.body.appendChild(h.el);
    await tick();
    expect(document.activeElement?.id).toBe('sf-w-bedingung-0');
    h.el.remove();
    tippe(h, '#sf-w-wert-0', 'ja');
    waehle(h, '#sf-w-ziel-0', 'entwurf');
    expect(h.werte.at(-1)).toEqual([{ wenn_gewaehlt: 'ja', dann: 'entwurf' }, { sonst: 'ende' }]);
    expect(meldung(h)).toBe('');
    // der Editor meldet halbe Regeln nicht per Ereignis — das Formular rechnet sie (Befund 2)
    expect(h.fehler).toEqual([]);
    // die Wahlen der Auswahlfelder stehen als Vorschlag da
    expect([...h.el.querySelectorAll('#sf-w-wahlen option')].map((o) => (o as HTMLOptionElement).value))
      .toEqual(['ja', 'nein']);
  });

  it('Bedingung wechseln, verschieben, entfernen', () => {
    const h = mount([{ wenn_gewaehlt: 'ja', dann: 'entwurf' }, { wenn_teil: 'draft', dann: 'ende' }], VERZWEIGUNG);
    waehle(h, '#sf-w-bedingung-1', 'gewaehlt');
    expect(h.werte.at(-1)).toEqual([{ wenn_gewaehlt: 'ja', dann: 'entwurf' }, { wenn_gewaehlt: 'draft', dann: 'ende' }]);
    (h.el.querySelector('#sf-w-hoch-1') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    expect(h.werte.at(-1)).toEqual([{ wenn_gewaehlt: 'draft', dann: 'ende' }, { wenn_gewaehlt: 'ja', dann: 'entwurf' }]);
    (h.el.querySelector('#sf-w-weg-0') as HTMLButtonElement).click();
    h.fixture.detectChanges();
    expect(h.werte.at(-1)).toEqual([{ wenn_gewaehlt: 'ja', dann: 'entwurf' }]);
    // „sonst“ hat keinen Wert
    waehle(h, '#sf-w-bedingung-0', 'sonst');
    expect(h.werte.at(-1)).toEqual([{ sonst: 'entwurf' }]);
    expect(h.el.querySelector('#sf-w-wert-0')).toBeNull();
  });

  it('Regeln an einem Nicht-Verzweigungsschritt: sichtbar, markiert, umstellbar (Befund 1)', () => {
    const h = mount([{ wenn_gewaehlt: 'ja', dann: 'entwurf' }, { sonst: 'ende' }]);
    const art = h.el.querySelector<HTMLSelectElement>('#sf-w-art')!;
    expect(art.value).toBe('regeln');
    expect(art.getAttribute('aria-invalid')).toBe('true');
    expect(h.el.querySelector('#sf-w-art option[value="regeln"]')!.textContent).toContain('nur an einer Verzweigung');
    expect(meldung(h)).toContain('nur an einer Verzweigung');
    waehle(h, '#sf-w-art', 'schritt');
    expect(h.werte.at(-1)).toBe('entwurf');
    expect(ziele(h, '#sf-w-art')).toEqual(['folge', 'schritt']);
  });

  it('Entfernen und Verschieben lassen den Fokus bei der Regel (Befund 6)', async () => {
    const h = mount([{ wenn_gewaehlt: 'ja', dann: 'entwurf' }, { wenn_gewaehlt: 'nein', dann: 'ende' },
      { sonst: 'frage' }], VERZWEIGUNG);
    document.body.appendChild(h.el);
    try {
      (h.el.querySelector('#sf-w-hoch-1') as HTMLButtonElement).click();
      h.fixture.detectChanges();
      await tick();
      // ganz oben ist „hoch“ gesperrt — der Fokus geht an „runter“ derselben Regel
      expect(document.activeElement?.id).toBe('sf-w-runter-0');
      (h.el.querySelector('#sf-w-weg-2') as HTMLButtonElement).click();
      h.fixture.detectChanges();
      await tick();
      expect(document.activeElement?.id).toBe('sf-w-weg-1');
    } finally {
      h.el.remove();
    }
  });

  it('was der Editor nicht zeigen kann, bleibt JSON', () => {
    const h = mount([{ wenn_gewaehlt: 'ja', wenn_teil: 'draft', dann: 'ende' }]);
    expect(h.el.querySelector('#sf-w-art')).toBeNull();
    expect(h.el.querySelector('textarea')).not.toBeNull();
  });
});

describe('WeiterEditorComponent — Schnellantworten (AS-3a)', () => {
  it('an einem Schritt mit Schnellantworten: Hinweis statt Arten, ein gesetztes weiter lässt sich leeren', () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    const dok = { schritte: [
      { id: 'f', typ: 'nachricht', optionen: [{ id: 'a', label: { de: 'A' }, ziel: 'e' }], weiter: 'e' },
      { id: 'e', typ: 'ende' }] };
    TestBed.configureTestingModule({ providers: [
      provideZonelessChangeDetection(), { provide: FORM_DOKUMENT, useValue: signal(dok) }] });
    const fixture = TestBed.createComponent(WeiterEditorComponent);
    const werte: unknown[] = [];
    fixture.componentInstance.valueChange.subscribe((v) => werte.push(v));
    fixture.componentRef.setInput('controlId', 'sf-w');
    fixture.componentRef.setInput('value', 'e');
    fixture.componentRef.setInput('pfad', ['schritte', 0, 'weiter']);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('#sf-w-art')).toBeNull();
    expect(el.textContent).toContain('entscheidet die Schnellantwort');
    expect(el.querySelector('#sf-w-fehler')!.textContent).toContain('bitte leeren');
    (el.querySelector('#sf-w-leeren') as HTMLButtonElement).click();
    expect(werte).toEqual([null]);
  });
});

describe('WeiterEditorComponent — wenn_wert (AS-3c)', () => {
  it('Quelle, Vergleich und Wert — der Wert nur, wo der Vergleich ihn braucht', () => {
    const h = mount([{ wenn_wert: { quelle: 'teil.draft', vergleich: 'vorhanden' }, dann: 'ende' },
      { sonst: 'frage' }], VERZWEIGUNG);
    expect(h.el.querySelector<HTMLInputElement>('#sf-w-quelle-0')!.value).toBe('teil.draft');
    expect(h.el.querySelector('#sf-w-wert-0')).toBeNull();
    // die Teile des Ablaufs stehen als Quelle zur Wahl
    expect([...h.el.querySelectorAll('#sf-w-quellen option')].map((o) => (o as HTMLOptionElement).value))
      .toEqual(['teil.draft']);
    waehle(h, '#sf-w-vergleich-0', 'groesser');
    expect(h.werte.at(-1)).toEqual([{ wenn_wert: { quelle: 'teil.draft', vergleich: 'groesser', wert: '' }, dann: 'ende' },
      { sonst: 'frage' }]);
    expect(meldung(h)).toContain('Wert fehlt');
    tippe(h, '#sf-w-wert-0', '5');
    expect(h.werte.at(-1)).toEqual([{ wenn_wert: { quelle: 'teil.draft', vergleich: 'groesser', wert: '5' }, dann: 'ende' },
      { sonst: 'frage' }]);
  });
});

describe('WeiterEditorComponent — Bedingung wechseln (Review AS-3c, Befund 6)', () => {
  it('„Teil vorhanden: x“ wird „Wert vergleichen: teil.x ist vorhanden“ und zurück', () => {
    const h = mount([{ wenn_teil: 'draft', dann: 'ende' }, { sonst: 'frage' }], VERZWEIGUNG);
    waehle(h, '#sf-w-bedingung-0', 'wert');
    expect(h.werte.at(-1)).toEqual([{ wenn_wert: { quelle: 'teil.draft', vergleich: 'vorhanden' }, dann: 'ende' },
      { sonst: 'frage' }]);
    waehle(h, '#sf-w-bedingung-0', 'teil');
    expect(h.werte.at(-1)).toEqual([{ wenn_teil: 'draft', dann: 'ende' }, { sonst: 'frage' }]);
  });
});
