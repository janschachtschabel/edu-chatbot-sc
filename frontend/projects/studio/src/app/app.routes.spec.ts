import { describe, expect, it } from 'vitest';

import { routes } from './app.routes';
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
});
