// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { JsonValueComponent } from './json-value.component';

/**
 * Paket 4, S1 (Audit 2026-09-29, F-M6): Eine Live-Region, die erst MIT ihrem
 * Text entsteht, sagen Screenreader oft nicht an. Die Fehlerzeile steht deshalb
 * leer im DOM, bevor ein Fehler kommt — dieselbe Region bekommt danach den Text.
 */
describe('JsonValueComponent — Live-Region', () => {
  it('steht leer bereit und bekommt den Fehler danach', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(JsonValueComponent);
    fixture.componentRef.setInput('fieldId', 'f1');
    fixture.componentRef.setInput('value', { a: 1 });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    const region = el.querySelector<HTMLElement>('[aria-live="polite"]');
    expect(region).not.toBeNull();
    expect(region!.textContent).toBe(''); // ganz leer, sonst greift `:empty` nicht

    const box = el.querySelector<HTMLTextAreaElement>('textarea')!;
    box.value = '{ kaputt';
    box.dispatchEvent(new Event('change'));
    await fixture.whenStable();

    // dieselbe Region, nicht eine neu erzeugte
    expect(el.querySelector('[aria-live="polite"]')).toBe(region);
    expect(region!.textContent).toContain('JSON');
  });

  it('trägt eine eigene Kennung, nicht die der Serverprüfung', async () => {
    // Prüfer 2026-10-04: Das Feld nennt seine Serverprüfung `<id>-err`. Seit die
    // Region dauerhaft steht, gab es die Kennung zweimal, und `aria-describedby`
    // traf die leere Region statt der Meldung des Servers.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(JsonValueComponent);
    fixture.componentRef.setInput('fieldId', 'f1');
    fixture.componentRef.setInput('value', { a: 1 });
    fixture.componentRef.setInput('describedByBase', 'f1-err');
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[aria-live="polite"]')!.id).toBe('f1-json-err');

    const box = el.querySelector<HTMLTextAreaElement>('textarea')!;
    box.value = '{ kaputt';
    box.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(box.getAttribute('aria-describedby')!.split(' ')).toEqual(['f1-err', 'f1-json-err']);
  });
});
