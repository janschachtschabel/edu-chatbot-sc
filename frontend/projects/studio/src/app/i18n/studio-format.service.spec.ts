// @vitest-environment jsdom
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { StudioFormat } from './studio-format.service';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from './studio-language.service';

function make(locale: 'de' | 'en'): { fmt: StudioFormat; lang: StudioLanguageService } {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  return { fmt: TestBed.inject(StudioFormat), lang: TestBed.inject(StudioLanguageService) };
}

describe('StudioFormat', () => {
  beforeEach(() => sessionStorage.clear());

  it('formatiert Zahlen nach der aktiven Sprache', () => {
    expect(make('de').fmt.decimal(0.812)).toBe('0,81');
    expect(make('en').fmt.decimal(0.812)).toBe('0.81');
  });

  it('formatiert Datum nach der aktiven Sprache', () => {
    expect(make('de').fmt.dateTime('2026-07-24T10:00:00Z')).toContain('24.7.2026');
    // en-GB und nicht en-US: der Tag bleibt vorn, siehe `format.locale`.
    expect(make('en').fmt.dateTime('2026-07-24T10:00:00Z')).toContain('24/07/2026');
  });

  it('nimmt den Text unter einer Minute aus dem Katalog', () => {
    const now = Date.parse('2026-07-26T12:00:00Z');
    const eben = new Date(now - 5_000).toISOString();
    expect(make('de').fmt.relative(eben, now)).toBe('gerade eben');
    expect(make('en').fmt.relative(eben, now)).toBe('just now');
  });

  it('folgt einem Sprachwechsel im Betrieb, ohne neu gebaut zu werden', () => {
    // Der Umschalter tauscht den Dienst nicht aus; läse er das Kürzel einmalig,
    // stünden Zahlen und Datum nach dem Wechsel weiter in der alten Sprache.
    const { fmt, lang } = make('de');
    expect(fmt.whole(12345)).toBe('12.345');
    lang.toggle();
    expect(fmt.whole(12345)).toBe('12,345');
  });
});
