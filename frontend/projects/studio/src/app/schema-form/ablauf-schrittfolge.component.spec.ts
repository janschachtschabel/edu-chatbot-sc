// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { schrittFolge } from './ablauf-folge';
import { AblaufSchrittfolgeComponent } from './ablauf-schrittfolge.component';

/**
 * AS-2c: ein Modul-Schritt verweist auf die Seite seines Moduls — im Studio mit Router als Link,
 * ohne Router als Text. Ohne Formular (keine Listenwahl) fehlt „Zum Schritt“.
 */
const ABLAUF = { schritte: [
  { id: 'frage', typ: 'modul', modul: 'ui_entscheidung' },
  { id: 'ende', typ: 'ende' },
] };

function mount(mitRouter: boolean): HTMLElement {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(), ...(mitRouter ? [provideRouter([])] : [])] });
  const fixture = TestBed.createComponent(AblaufSchrittfolgeComponent);
  fixture.componentRef.setInput('folge', schrittFolge(ABLAUF));
  fixture.componentRef.setInput('pfad', []);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('AblaufSchrittfolgeComponent (AS-2c)', () => {
  it('mit Router: der Modul-Schritt verweist auf die Seite des Moduls', () => {
    const el = mount(true);
    const links = el.querySelectorAll<HTMLAnchorElement>('a.ap-modul');
    expect(links.length).toBe(1);
    expect(links[0].getAttribute('href')).toBe('/ui-module?modul=ui_entscheidung');
    expect(links[0].textContent).toContain('ui_entscheidung');
    expect(el.querySelector('.ap-zum')).toBeNull();
  });

  it('ohne Router: der Name steht als Text da', () => {
    const el = mount(false);
    expect(el.querySelector('a.ap-modul')).toBeNull();
    expect(el.querySelector('span.ap-modul')?.textContent).toContain('ui_entscheidung');
  });
});

describe('AblaufSchrittfolgeComponent — wenn_wert (Review AS-3c, Befund 5)', () => {
  it.each([
    ['de', 'teil.zahlen.n ist größer als „10“'],
    ['en', 'teil.zahlen.n is greater than “10”'],   // Review PR #51, S4: auch die Zeichen der Sprache
  ])('zeigt den Vergleich übersetzt, den Wert in Anführungszeichen (%s)', (sprache, erwartet) => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, sprache);
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(AblaufSchrittfolgeComponent);
    fixture.componentRef.setInput('folge', schrittFolge({ schritte: [
      { id: 'v', typ: 'verzweigung', weiter: [
        { wenn_wert: { quelle: 'teil.zahlen.n', vergleich: 'groesser', wert: '10' }, dann: 'e' }, { sonst: 'e' }] },
      { id: 'e', typ: 'ende' }] }));
    fixture.componentRef.setInput('pfad', []);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(erwartet);
  });
});
