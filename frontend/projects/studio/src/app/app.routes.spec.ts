// @vitest-environment jsdom
import { Component, inject } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, type UrlTree, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { describe, expect, it, vi } from 'vitest';

import { routes } from './app.routes';
import { startseiteGuard } from './startseite.guard';
import { StudioAnsicht } from './core/studio-ansicht.service';
import { DASHBOARD_SECTIONS } from './views/area-homes';
import { CURATED_VIEWS } from './views/curated-views';
import { unsavedChangesGuard } from './views/unsaved-changes.guard';

describe('Routen', () => {
  it('schützt jede Seite mit einem Formular vor dem stillen Verlassen (ST-9)', () => {
    // Kosten und Evaluation bearbeiten seit ST-9 je einen Bereich (Preistafel,
    // Gold-Flows). Ohne den Schutz verwürfe ein Klick in die Navigation die
    // Änderung wortlos — auf den kuratierten Seiten fragt er seit 9-3.
    const kinder = routes.find((r) => r.path === '')!.children!;
    const mitFormular = [
      ...CURATED_VIEWS.map((view) => view.slug),
      ...Object.keys(DASHBOARD_SECTIONS),
    ];
    const ohneSchutz = mitFormular.filter((slug) =>
      !(kinder.find((r) => r.path === slug)?.canDeactivate ?? []).includes(unsavedChangesGuard));
    expect(ohneSchutz).toEqual([]);
  });

  it('die Startseite wartet auf den Arbeitsbereich, bevor sie weiterleitet (Review #1)', async () => {
    // Ohne Wahl steht der Arbeitsbereich erst mit der Vorgabe des Servers fest; ein sofortiges
    // Lesen landete bei der Vorgabe „pattern“ auf der Agent-Übersicht.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [{ provide: StudioAnsicht, useValue: { ermittle: () => Promise.resolve('pattern') } }],
    });
    const start = routes.find((r) => r.path === '')!.children!
      .find((r) => r.path === '' && r.pathMatch === 'full')!;
    // Review PR #18: ein Wächter statt einer Umleitung — Umleitungen laufen vor `authGuard`.
    expect(start.redirectTo).toBeUndefined();
    expect(start.canActivate).toContain(startseiteGuard);
    const ziel = await TestBed.runInInjectionContext(
      () => startseiteGuard({} as never, {} as never) as Promise<UrlTree>);
    expect(TestBed.inject(Router).serializeUrl(ziel)).toBe('/uebersicht');
  });

  it('fragt abgemeldet nicht nach der Vorgabe, sondern geht zuerst zur Anmeldung (Review PR #18)', async () => {
    // Vorher: die Umleitung lief vor `authGuard`, holte die Vorgabe mit 401 und landete bei
    // „pattern“ auf der Agent-Übersicht.
    const ermittle = vi.fn(() => Promise.resolve('pattern' as const));
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        { provide: StudioAnsicht, useValue: { ermittle } },
        provideRouter([
          { path: 'login', component: Leer },
          { path: 'uebersicht', component: Leer },
          {
            path: '', canActivate: [() => inject(Router).createUrlTree(['/login'])],
            children: [{ path: '', pathMatch: 'full', canActivate: [startseiteGuard], children: [] }],
          },
        ]),
      ],
    });
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/');
    expect(TestBed.inject(Router).url).toBe('/login');
    expect(ermittle).not.toHaveBeenCalled();
  });
});

@Component({ template: '' })
class Leer {}
