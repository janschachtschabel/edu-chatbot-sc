import { TestBed } from '@angular/core/testing';
import type { RedirectFunction } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { routes } from './app.routes';
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
    const weiter = start.redirectTo as RedirectFunction;
    const ziel = await TestBed.runInInjectionContext(() => weiter({} as never));
    expect(ziel).toBe('uebersicht');
  });
});
