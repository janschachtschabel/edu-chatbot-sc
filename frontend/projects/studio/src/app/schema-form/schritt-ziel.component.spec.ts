// @vitest-environment jsdom
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { FORM_DOKUMENT } from './form-dokument';
import { SchrittZielComponent } from './schritt-ziel.component';

/** AS-3a: das Ziel einer Schnellantwort — eine Auswahl der Schritte desselben Ablaufs. */
const DOK = { id: 'a', schritte: [
  { id: 'frage', typ: 'nachricht', optionen: [{ id: 'x', label: { de: 'X' }, ziel: '' }] },
  { id: 'ende', typ: 'ende' },
] };

function mount(value: unknown) {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [
    provideZonelessChangeDetection(), { provide: FORM_DOKUMENT, useValue: signal(DOK) }] });
  const fixture = TestBed.createComponent(SchrittZielComponent);
  const werte: unknown[] = [];
  fixture.componentInstance.valueChange.subscribe((v) => werte.push(v));
  fixture.componentRef.setInput('controlId', 'sf-z');
  fixture.componentRef.setInput('value', value);
  fixture.componentRef.setInput('pfad', ['schritte', 0, 'optionen', 0, 'ziel']);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, werte };
}

const optionen = (el: HTMLElement) =>
  [...el.querySelectorAll<HTMLOptionElement>('option')].map((o) => [o.value, o.textContent?.trim()]);

describe('SchrittZielComponent (AS-3a)', () => {
  it('bietet die Schritte an, den eigenen als „dieser Schritt“', () => {
    const { el, werte } = mount('');
    expect(optionen(el).map(([v]) => v)).toEqual(['', 'frage', 'ende']);
    expect(optionen(el)[1][1]).toContain('dieser Schritt');
    const sel = el.querySelector('select')!;
    sel.value = 'ende';
    sel.dispatchEvent(new Event('change'));
    expect(werte).toEqual(['ende']);
  });

  it('ein unbekanntes Ziel bleibt sichtbar und ist markiert', () => {
    const { el } = mount('weg');
    expect(optionen(el)[0]).toEqual(['weg', 'weg (unbekannt)']);
    expect(el.querySelector('select')!.getAttribute('aria-invalid')).toBe('true');
  });
});
