// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { LanguageSwitcherComponent } from './language-switcher.component';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from './studio-language.service';

/**
 * Der Umschalter (C1-d1). Eigene Komponente statt zweimal derselbe Knopf im
 * Markup: er steht in der Kopfzeile UND auf der Anmeldeseite — wer die
 * Oberfläche nicht lesen kann, muss auch vor dem Anmelden umschalten können.
 */
describe('LanguageSwitcherComponent', () => {
  let fixture: ComponentFixture<LanguageSwitcherComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    TestBed.resetTestingModule();
    // Deutsche Oberfläche über die oberste Quelle herstellen: jsdom meldet
    // `navigator.language === 'en-US'`, und der Browser ist im Studio die
    // zweitstärkste Quelle (C1-c-Fund, C1-d1-Rangfolge).
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    fixture = TestBed.createComponent(LanguageSwitcherComponent);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('zeigt das Kürzel der ZIELsprache', () => {
    expect(el.querySelector('button')?.textContent?.trim()).toBe('EN');
  });

  it('trägt einen zugänglichen Namen, der die Zielsprache ausspricht', () => {
    // „EN" allein sagt einem Screenreader-Nutzer nicht, ob der Knopf die
    // aktuelle oder die nächste Sprache nennt (WCAG 2.5.3 im Blick: der
    // sichtbare Text steckt im Namen).
    const knopf = el.querySelector('button');
    expect(knopf?.getAttribute('aria-label')).toBe('Auf Englisch umschalten');
    expect(knopf?.getAttribute('title')).toBe('Auf Englisch umschalten');
  });

  it('schaltet beim Klick wirklich um — und beschriftet sich neu', async () => {
    el.querySelector('button')?.click();
    await fixture.whenStable();

    expect(TestBed.inject(StudioLanguageService).i18n.locale()).toBe('en');
    const knopf = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    expect(knopf.textContent?.trim()).toBe('DE');
    expect(knopf.getAttribute('aria-label')).toBe('Switch to German');
  });

  it('versteckt das Kürzel vor der Vorlesehilfe — der Name sagt es besser', () => {
    // Sonst hört man „EN, Auf Englisch umschalten, Schaltfläche".
    expect(el.querySelector('button span')?.getAttribute('aria-hidden')).toBe('true');
  });
});
