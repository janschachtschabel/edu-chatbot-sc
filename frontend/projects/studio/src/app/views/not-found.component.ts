import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DEFAULT_VIEW } from '../studio-views';

/** Unknown URL inside the shell — the navigation stays reachable beside it. */
@Component({
  selector: 'studio-not-found',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 class="title">Seite nicht gefunden</h2>
    <p>Diese Adresse gehört zu keiner Studio-Ansicht.</p>
    <p><a [routerLink]="['/', defaultView]">Zur Übersicht</a></p>
  `,
  styles: `.title { font-size: 1.375rem; margin-bottom: var(--st-3); }`,
})
export class NotFoundComponent {
  readonly defaultView = DEFAULT_VIEW;
}
