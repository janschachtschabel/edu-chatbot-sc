// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import type { OriginScope } from '../core/origin-scope';
import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { OriginScopeComponent } from './origin-scope.component';

async function mount(value: OriginScope = 'all'): Promise<{
  fixture: ComponentFixture<OriginScopeComponent>; el: HTMLElement; emitted: OriginScope[];
}> {
  TestBed.resetTestingModule();
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
  TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  const fixture = TestBed.createComponent(OriginScopeComponent);
  fixture.componentRef.setInput('value', value);
  fixture.componentRef.setInput('name', 'test-herkunft');
  const emitted: OriginScope[] = [];
  fixture.componentInstance.valueChange.subscribe((scope) => emitted.push(scope));
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement, emitted };
}

describe('OriginScopeComponent (ST-9)', () => {
  it('bietet die Herkünfte als echte Radiogruppe „Datenbasis“ an', async () => {
    const { el } = await mount();
    expect(el.querySelector('fieldset legend')?.textContent).toContain('Datenbasis');
    const radios = [...el.querySelectorAll<HTMLInputElement>('input[type="radio"]')];
    expect(new Set(radios.map((r) => r.name))).toEqual(new Set(['test-herkunft']));
    const labels = [...el.querySelectorAll('label')].map((l) => l.querySelector('.os-label')?.textContent?.trim());
    expect(labels.slice(0, 3)).toEqual(['Alle', 'Produktion', 'Nur Eval']);
  });

  it('sagt ehrlich, was „Produktion“ ausschließt', async () => {
    // Bis ST-9 hieß es „Nur echte Gespräche“ — und Lasttest-Sitzungen zählten mit.
    const { el } = await mount();
    const hinweis = [...el.querySelectorAll('label')][1].textContent ?? '';
    expect(hinweis).toContain('Lasttest');
    expect(hinweis).toContain('Eval');
  });

  it('TB-E2: bietet die Proben der Studio-Vorschau als eigene Datenbasis an', async () => {
    const { el, emitted } = await mount();
    const labels = [...el.querySelectorAll('label')];
    expect(labels.map((l) => l.querySelector('.os-label')?.textContent?.trim()))
      .toEqual(['Alle', 'Produktion', 'Nur Eval', 'Nur Studio-Vorschau']);
    expect(labels[1].textContent).toContain('Vorschau');   // Produktion nennt sie als ausgeschlossen
    el.querySelectorAll<HTMLInputElement>('input[type="radio"]')[3].click();
    expect(emitted).toEqual(['probe']);
  });

  it('markiert die gewählte Herkunft und meldet einen Wechsel', async () => {
    const { el, emitted } = await mount('eval');
    const radios = [...el.querySelectorAll<HTMLInputElement>('input[type="radio"]')];
    expect(radios.map((r) => r.checked)).toEqual([false, false, true, false]);
    radios[1].click();
    expect(emitted).toEqual(['production']);
  });
});
