// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import type { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import { routes } from '../app.routes';
import { NAV_GROUPS, STUDIO_VIEWS } from '../studio-views';
import { STUDIO_DE } from './de';
import { STUDIO_EN } from './en';
import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from './studio-language.service';

/**
 * Die Ansichts-Registry im Katalog (C1-d2).
 *
 * Getrennt von `studio-views.spec.ts`: dort steht, was die Registry als
 * *Struktur* zusagt (Slugs, Routen, Gruppen), hier, was sie als *Inhalt* zeigt.
 * Zwei Gründe zu ändern, zwei Dateien — und nur diese braucht ein DOM.
 */
const shellChildren = routes.find((r) => r.path === '')?.children ?? [];

/**
 * Ruft den Titel-Resolver einer Route im Injektionskontext auf.
 *
 * Enger typisiert als `ResolveFn<string>`, dessen Rückgabe auch ein Promise
 * oder eine Umleitung sein darf: die Titel des Studios sind alle sofort da.
 */
type SyncTitle = (a: ActivatedRouteSnapshot, b: RouterStateSnapshot) => string;

function routeTitle(path: string): string {
  const route = path === 'login'
    ? routes.find((r) => r.path === 'login')
    : shellChildren.find((c) => c.path === path);
  const title = route?.title as SyncTitle;
  return TestBed.runInInjectionContext(() =>
    title({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  );
}

describe('Ansichts-Registry im Katalog', () => {
  beforeEach(() => {
    TestBed.resetTestingModule();
    // jsdom meldet `navigator.language === 'en-US'` (C1-c-Fund); ohne diese
    // Zeile stünde das Studio hier auf Englisch.
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        // Eine nackte Route mit dem ECHTEN Titel-Resolver aus `app.routes.ts`:
        // so läuft er durch Angulars eigene Titel-Kette, ohne dass eine der
        // 20 Ansichten samt Wächtern und Diensten geladen werden muss.
        provideRouter([{
          path: 'probe',
          title: shellChildren.find((c) => c.path === 'uebersicht')?.title,
          children: [],
        }]),
      ],
    });
  });

  it('kennt jeden Schlüssel der Registry in beiden Sprachen', () => {
    // Der eigentliche Wächter dieser Scheibe: ein Schlüssel ohne Katalog-Eintrag
    // fällt nicht auf, er zeigt den Schlüssel selbst als Beschriftung —
    // „view.wissen.label" mitten in der Navigation.
    const keys = [
      ...STUDIO_VIEWS.flatMap((v) => [v.labelKey, v.descKey]),
      ...NAV_GROUPS.map((g) => g.titleKey).filter((k): k is string => k !== null),
    ];
    expect(keys).toHaveLength(20 * 2 + 3);
    for (const key of keys) {
      expect(STUDIO_DE[key], `fehlt im deutschen Katalog: ${key}`).toBeTypeOf('string');
      expect(STUDIO_EN[key], `fehlt im englischen Katalog: ${key}`).toBeTypeOf('string');
    }
  });

  it('zeigt die 20 Beschriftungen des Katalogs auf Deutsch', () => {
    // 19 aus §5.6 und seinen drei Zugaben, dazu „Kosten" aus K5. Welche Ansicht
    // woher stammt, hält `studio-views.spec.ts` fest — hier steht nur, wie sie
    // heisst.
    const lang = TestBed.inject(StudioLanguageService);
    expect(STUDIO_VIEWS.map((v) => lang.t(v.labelKey))).toEqual([
      'Übersicht', 'Begrüßung', 'Kontext-Aktionen', 'Identität & Schutz', 'Domain-Wissen',
      'Patterns', 'Dimensionen', 'Material-Formate', 'Wissen', 'Sessions', 'Analyse',
      'Evaluation', 'Lasttest', 'Safety-Logs', 'Kosten', 'Anzeige', 'Datenschutz',
      'Alle Bereiche', 'Sicherung', 'Vorschau',
    ]);
  });

  it('übersetzt Beschriftungen und Gruppen beim Umschalten mit', () => {
    const lang = TestBed.inject(StudioLanguageService);
    lang.toggle();
    expect(lang.t('view.uebersicht.label')).toBe('Overview');
    expect(lang.t('view.bereiche.desc')).not.toMatch(/[äöüß]/);
    expect(NAV_GROUPS.map((g) => (g.titleKey ? lang.t(g.titleKey) : null)))
      .toEqual([null, 'Configuration', 'Monitoring', 'System']);
  });

  it('setzt den Dokumenttitel der Ansichten in der aktiven Sprache', () => {
    // ALT hatte gar keine Routen und damit keinen Titel je Ansicht. Der Titel
    // ist das, was ein Screenreader beim Ansichtswechsel ansagt — er darf nicht
    // in der zuletzt gebauten Sprache einfrieren, also ist er ein Resolver.
    expect(routeTitle('uebersicht')).toBe('Übersicht — BOERDi Studio');
    expect(routeTitle('login')).toBe('Anmelden — BOERDi Studio');

    TestBed.inject(StudioLanguageService).toggle();
    expect(routeTitle('uebersicht')).toBe('Overview — BOERDi Studio');
    expect(routeTitle('login')).toBe('Sign in — BOERDi Studio');
  });

  it('lässt Angular den Resolver wirklich aufrufen, nicht nur den Test', async () => {
    // Der Test darüber ruft die Funktion selbst auf und beweist damit nur, dass
    // sie das Richtige zurückgibt. Erst eine echte Navigation zeigt, dass
    // Angular sie im Injektionskontext aufruft — `inject()` darin ist der
    // einzige neue Teil gegenüber dem bestehenden `bereich/**`-Resolver.
    await TestBed.inject(Router).navigateByUrl('/probe');
    expect(document.title).toBe('Übersicht — BOERDi Studio');
  });
});
