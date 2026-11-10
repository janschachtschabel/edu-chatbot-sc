// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import type { AblaufStand } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
import { createTranslator } from '../i18n/dictionary';
import { AblaufLeisteComponent } from './ablauf-leiste.component';

/**
 * Paket AS-Ub (Plan 2026-11-09 §5h, D10): die Ablauf-Leiste über dem Eingabefeld — Titel,
 * „Schritt n von m“, Status in Worten, „Abbrechen“ und „Einklappen“ (bis Q-12: „Später fortsetzen“), dazu aufklappbar die
 * gesammelten Daten. Rein darstellend: den Stand liefert die Shell, „Abbrechen“ geht als Ereignis
 * nach oben.
 */

const STAND: AblaufStand = {
  id: 'probe', titel: 'Sammlung aus Ordnern', nr: 2, von: 5, status: 'wartet_wahl',
  teile: [{ name: 'draft', text: 'Entwurf mit 5 Punkten' }, { name: 'ablage', text: '3 von 4 abgelegt' }],
};

function bauen(stand: AblaufStand | null, beschaeftigt = false, sprache: 'de' | 'en' = 'de') {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const f = TestBed.createComponent(AblaufLeisteComponent);
  f.componentRef.setInput('translate', sprache === 'de' ? createTranslator(DE, DE) : createTranslator(EN, DE));
  f.componentRef.setInput('stand', stand);
  f.componentRef.setInput('beschaeftigt', beschaeftigt);
  f.detectChanges();
  return f;
}

const text = (el: Element | null) => (el?.textContent ?? '').replace(/\s+/g, ' ').trim();

describe('AblaufLeisteComponent (AS-Ub)', () => {
  it('ohne Stand zeigt sie nichts', () => {
    const el = bauen(null).nativeElement as HTMLElement;
    expect(el.querySelector('section')).toBeNull();
  });

  it('zeigt Titel, Schritt und Status als benannte Region', () => {
    const el = bauen(STAND).nativeElement as HTMLElement;
    const region = el.querySelector('section')!;
    expect(region.getAttribute('aria-label')).toBe('Laufender Ablauf');
    expect(text(region.querySelector('.ablauf-leiste__titel'))).toBe('Sammlung aus Ordnern');
    const stand = region.querySelector('.ablauf-leiste__stand')!;
    expect(text(stand)).toBe('Schritt 2 von 5, wartet auf dich');
    expect(stand.getAttribute('aria-live')).toBe('polite');
  });

  it('auf Englisch', () => {
    const el = bauen(STAND, false, 'en').nativeElement as HTMLElement;
    expect(text(el.querySelector('.ablauf-leiste__stand'))).toBe('Step 2 of 5, waiting for you');
  });

  it('AS-7b: eine Führung wartet auf den Seitenwechsel (de/en)', () => {
    const de = bauen({ ...STAND, status: 'wartet_seite' }).nativeElement as HTMLElement;
    expect(text(de.querySelector('.ablauf-leiste__stand'))).toBe('Schritt 2 von 5, wartet auf den Seitenwechsel');
    const en = bauen({ ...STAND, status: 'wartet_seite' }, false, 'en').nativeElement as HTMLElement;
    expect(text(en.querySelector('.ablauf-leiste__stand'))).toBe('Step 2 of 5, waiting for you to open the page');
  });

  it('Querschnitts-Review AS-7, Befund 1: wartet eine Führung, steht ihr Weg als Knopf da', () => {
    const f = bauen({ ...STAND, status: 'wartet_seite', weg: { label: 'Zur Mitmach-Seite', url: '/mitmachen/' } });
    const gerufen = vi.fn();
    f.componentInstance.fuehren.subscribe(gerufen);
    const knopf = (f.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.ablauf-leiste__weg')!;
    expect(text(knopf)).toBe('Zur Mitmach-Seite');
    knopf.click();
    expect(gerufen).toHaveBeenCalledWith('/mitmachen/');
    // ohne Weg kein Knopf
    const ohne = bauen(STAND).nativeElement as HTMLElement;
    expect(ohne.querySelector('.ablauf-leiste__weg')).toBeNull();
  });

  it('ein unbekannter Status zeigt nur den Schritt', () => {
    const el = bauen({ ...STAND, status: 'etwas_neues' }).nativeElement as HTMLElement;
    expect(text(el.querySelector('.ablauf-leiste__stand'))).toBe('Schritt 2 von 5');
  });

  it('Abbrechen geht als Ereignis nach oben — gesperrt, solange ein Zug läuft', () => {
    const f = bauen(STAND);
    const gerufen = vi.fn();
    f.componentInstance.abbrechen.subscribe(gerufen);
    const knopf = (f.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.ablauf-leiste__abbrechen')!;
    expect(text(knopf)).toBe('Ablauf abbrechen');
    knopf.click();
    expect(gerufen).toHaveBeenCalledTimes(1);
    const belegt = bauen(STAND, true).nativeElement as HTMLElement;
    expect(belegt.querySelector<HTMLButtonElement>('.ablauf-leiste__abbrechen')!.disabled).toBe(true);
  });

  it('„Einklappen“ klappt zu einer Zeile zusammen — der Fokus bleibt am Knopf', () => {
    const f = bauen(STAND);
    const el = f.nativeElement as HTMLElement;
    document.body.appendChild(el);
    const knopf = el.querySelector<HTMLButtonElement>('.ablauf-leiste__umschalten')!;
    knopf.focus();
    knopf.click();
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__abbrechen')).toBeNull();
    expect(text(el.querySelector('.ablauf-leiste__pause'))).toContain('„Sammlung aus Ordnern“ wartet');
    // Review AS-Ub, Befund 2: derselbe Knopf, im DOM geblieben, mit Fokus
    expect(el.querySelector('.ablauf-leiste__umschalten')).toBe(knopf);
    expect(document.activeElement).toBe(knopf);
    expect(text(knopf)).toBe('Aufklappen');
    knopf.click();
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__abbrechen')).not.toBeNull();
    el.remove();
  });

  it('ein neuer Ablauf erscheint wieder aufgeklappt', () => {
    const f = bauen(STAND);
    const el = f.nativeElement as HTMLElement;
    el.querySelector<HTMLButtonElement>('.ablauf-leiste__umschalten')!.click();
    f.componentRef.setInput('stand', { ...STAND, id: 'anderer' });
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__abbrechen')).not.toBeNull();
  });

  it('endet der Lauf, ist derselbe Ablauf beim nächsten Mal wieder offen (Review AS-Ub, Befund 3)', () => {
    const f = bauen(STAND);
    const el = f.nativeElement as HTMLElement;
    el.querySelector<HTMLButtonElement>('.ablauf-leiste__umschalten')!.click();
    f.detectChanges();
    f.componentRef.setInput('stand', null);
    f.detectChanges();
    f.componentRef.setInput('stand', { ...STAND });
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__abbrechen')).not.toBeNull();
  });

  it('„Neu starten“ desselben Ablaufs (neue Laufmarke) erscheint offen (zweites Review AS-U)', () => {
    const f = bauen({ ...STAND, lauf: 'a' });
    const el = f.nativeElement as HTMLElement;
    el.querySelector<HTMLButtonElement>('.ablauf-leiste__umschalten')!.click();
    f.detectChanges();
    f.componentRef.setInput('stand', { ...STAND, lauf: 'a', nr: 3 });   // derselbe Lauf: bleibt zu
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__abbrechen')).toBeNull();
    f.componentRef.setInput('stand', { ...STAND, lauf: 'b', nr: 1 });   // neuer Lauf: offen
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__abbrechen')).not.toBeNull();
  });

  it('ein neuer Schritt ändert den Text in derselben Live-Region (Ansage)', () => {
    const f = bauen(STAND);
    const el = f.nativeElement as HTMLElement;
    const region = el.querySelector('.ablauf-leiste__stand');
    f.componentRef.setInput('stand', { ...STAND, nr: 3 });
    f.detectChanges();
    expect(el.querySelector('.ablauf-leiste__stand')).toBe(region);
    expect(text(region)).toBe('Schritt 3 von 5, wartet auf dich');
  });

  it('die gesammelten Daten stehen aufklappbar da — ohne Teile nicht', () => {
    const el = bauen(STAND).nativeElement as HTMLElement;
    const daten = el.querySelector('details.ablauf-leiste__daten')!;
    expect(text(daten.querySelector('summary'))).toBe('Gesammelte Daten (2)');
    // Review AS-Ub, Befund 5: nur der lesbare Kurztext, nicht der technische Teilname
    expect([...daten.querySelectorAll('li')].map(text)).toEqual(
      ['Entwurf mit 5 Punkten', '3 von 4 abgelegt']);
    const ohne = bauen({ ...STAND, teile: [] }).nativeElement as HTMLElement;
    expect(ohne.querySelector('details')).toBeNull();
  });
});
