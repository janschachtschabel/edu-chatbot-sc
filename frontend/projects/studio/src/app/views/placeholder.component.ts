/**
 * Stand-in for a view that a later P9 slice implements (9-3…9-5).
 *
 * Deliberately honest rather than a blank page or a fake skeleton: it names the
 * view and the package that will fill it, so clicking through the finished shell
 * never leaves anyone wondering whether something is broken. Mirrors the
 * backend's `todo("P9-3")` convention, which names the package in the 501 body.
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { StudioView } from '../studio-views';

@Component({
  selector: 'studio-placeholder',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 class="title">{{ view()?.label }}</h2>
    <p class="desc">{{ view()?.desc }}</p>
    <p class="note">
      Diese Ansicht wird mit Paket <strong>{{ view()?.paket }}</strong> gebaut.
      Die Konfiguration selbst ist im Backend bereits vollständig vorhanden.
    </p>
  `,
  styles: `
    .title { font-size: 1.375rem; }
    .desc { margin: var(--st-2) 0 var(--st-5); color: var(--st-text-muted); }
    .note {
      max-width: 42rem;
      padding: var(--st-4);
      border: 1px solid var(--st-rule);
      border-inline-start: 4px solid var(--st-warn-dot);
      border-radius: var(--st-radius);
      background: var(--st-panel);
      margin: 0;
    }
  `,
})
export class PlaceholderComponent {
  /** Bound from the route's `data.view` via withComponentInputBinding(). */
  readonly view = input<StudioView>();
}
