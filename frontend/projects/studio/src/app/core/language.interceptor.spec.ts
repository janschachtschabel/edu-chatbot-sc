// @vitest-environment jsdom
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService }
  from '../i18n/studio-language.service';
import { languageInterceptor } from './language.interceptor';

function setUp(locale: 'de' | 'en'): {
  http: HttpClient; ctrl: HttpTestingController; lang: StudioLanguageService;
} {
  sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, locale);
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withInterceptors([languageInterceptor])),
      provideHttpClientTesting(),
    ],
  });
  return {
    http: TestBed.inject(HttpClient),
    ctrl: TestBed.inject(HttpTestingController),
    lang: TestBed.inject(StudioLanguageService),
  };
}

describe('languageInterceptor', () => {
  beforeEach(() => sessionStorage.clear());

  it('nennt dem Backend die Sprache der Oberfläche', () => {
    const { http, ctrl } = setUp('en');
    http.get('/api/config/welcome').subscribe();
    expect(ctrl.expectOne('/api/config/welcome').request.headers.get('Accept-Language'))
      .toBe('en');
    ctrl.verify();
  });

  it('folgt dem Umschalter, ohne dass ein Dienst neu gebaut wird', () => {
    const { http, ctrl, lang } = setUp('de');
    http.get('/api/config/welcome').subscribe();
    expect(ctrl.expectOne('/api/config/welcome').request.headers.get('Accept-Language'))
      .toBe('de');

    lang.toggle();
    http.get('/api/config/welcome').subscribe();
    expect(ctrl.expectOne('/api/config/welcome').request.headers.get('Accept-Language'))
      .toBe('en');
    ctrl.verify();
  });

  it('rührt fremde Adressen nicht an', () => {
    // Das Studio ruft heute nur das eigene Backend; die Sprache der Redaktion
    // gehört trotzdem nicht in eine Anfrage an irgendwen sonst.
    const { http, ctrl } = setUp('en');
    http.get('https://example.org/etwas').subscribe();
    expect(ctrl.expectOne('https://example.org/etwas').request.headers.has('Accept-Language'))
      .toBe(false);
    ctrl.verify();
  });

  it('überschreibt einen mitgegebenen Header nicht', () => {
    const { http, ctrl } = setUp('en');
    http.get('/api/config/welcome', { headers: { 'Accept-Language': 'de' } }).subscribe();
    expect(ctrl.expectOne('/api/config/welcome').request.headers.get('Accept-Language'))
      .toBe('de');
    ctrl.verify();
  });
});
