// @vitest-environment jsdom
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { SessionStore } from '../auth/session-store';
import { STUDIO_VIEWS } from '../studio-views';
import { ShellComponent } from './shell.component';

/**
 * The a11y properties asserted here are all things ALT lacked (page.tsx:350-446):
 * nav items were `<button onClick>` with no href and no `aria-current`, there was
 * no skip link, and the status dot was an empty span with no live region.
 */
describe('ShellComponent', () => {
  let fixture: ComponentFixture<ShellComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        // Real (empty) routes for every slug, so nav clicks actually navigate —
        // that is what makes routerLinkActive/aria-current observable here.
        provideRouter(STUDIO_VIEWS.map((v) => ({ path: v.slug, children: [] }))),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    fixture = TestBed.createComponent(ShellComponent);
    http = TestBed.inject(HttpTestingController);
    await fixture.whenStable();
    el = fixture.nativeElement as HTMLElement;
  });

  it('renders every view as a real link, not a button', () => {
    // `Array.from`, not spread: the workspace tsconfig lib is ES2022+dom without
    // dom.iterable, so a NodeList is not iterable here.
    const links = Array.from(el.querySelectorAll<HTMLAnchorElement>('.nav-item'));
    expect(links).toHaveLength(STUDIO_VIEWS.length);
    for (const link of links) {
      // A real href is what makes middle-click, open-in-new-tab and the browser
      // status bar work — ALT's buttons had none.
      expect(link.getAttribute('href')).toMatch(/^\/[a-z-]+$/);
    }
  });

  it('exposes the grouped structure with headings inside a labelled nav', () => {
    const nav = el.querySelector('nav');
    expect(nav?.getAttribute('aria-label')).toBe('Konfigurationsbereiche');
    const titles = Array.from(el.querySelectorAll('.nav-group-title'), (h) => h.textContent?.trim());
    expect(titles).toEqual(['Konfiguration', 'Auswertung', 'System']);
    // Lists, so a screen reader announces "3 of 16".
    expect(el.querySelectorAll('.nav-list').length).toBe(4);
  });

  it('has a skip link that targets the main landmark', () => {
    const skip = el.querySelector<HTMLAnchorElement>('a.skip');
    expect(skip?.textContent?.trim()).toBe('Zum Inhalt springen');
    const target = skip?.getAttribute('href')?.replace('#', '');
    expect(el.querySelector(`#${target}`)?.tagName).toBe('MAIN');
  });

  it('marks no nav item as current while no view is open', () => {
    expect(el.querySelector('[aria-current="page"]')).toBeNull();
  });

  it('announces the backend status in a live region', () => {
    const status = el.querySelector('[role="status"]');
    expect(status).not.toBeNull();
    // Third state: neither "Verbunden" nor "Offline" before the first answer.
    expect(status?.textContent).toContain('Verbindung wird geprüft');
    http.expectOne('/studio/api/health').flush({ status: 'ok' });
  });

  it('toggles the narrow-screen drawer with an honest aria-expanded', async () => {
    const toggle = el.querySelector<HTMLButtonElement>('.nav-toggle');
    expect(toggle?.getAttribute('aria-expanded')).toBe('false');
    expect(toggle?.getAttribute('aria-controls')).toBe('studio-nav');

    toggle?.click();
    await fixture.whenStable();
    expect(el.querySelector('.nav-toggle')?.getAttribute('aria-expanded')).toBe('true');

    // Following a link closes it again, so the content is not left behind a drawer.
    el.querySelector<HTMLAnchorElement>('.nav-item')?.click();
    await fixture.whenStable();
    expect(el.querySelector('.nav-toggle')?.getAttribute('aria-expanded')).toBe('false');
  });

  it('marks the open view with aria-current, not just a CSS class', async () => {
    el.querySelector<HTMLAnchorElement>('.nav-item')?.click();
    await fixture.whenStable();

    const current = Array.from(el.querySelectorAll('[aria-current="page"]'));
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toContain(STUDIO_VIEWS[0].label);
    // ALT conveyed the active state through the `active` class alone, so a
    // screen reader had no way to know where it was.
    expect(current[0].classList.contains('nav-item--active')).toBe(true);
  });

  it('hides "Abmelden" when no password guards the studio', async () => {
    expect(el.querySelector('.header-tools button')?.textContent).toContain('Abmelden');

    TestBed.inject(SessionStore).set('signed-in', true);
    await fixture.whenStable();
    // A logout button that cannot log anyone out is worse than none.
    expect(el.querySelector('.header-tools button')).toBeNull();
  });

  it('makes the brand a link — ALT put the click handler on the <h1>', () => {
    const brand = el.querySelector('h1.brand a');
    expect(brand?.getAttribute('href')).toBe('/');
  });
});
