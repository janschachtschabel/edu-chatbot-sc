import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { DEFAULT_VIEW } from '../studio-views';

/** Unknown URL inside the shell — the navigation stays reachable beside it. */
@Component({
  selector: 'studio-not-found',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 class="title">{{ t('notFound.title') }}</h2>
    <p>{{ t('notFound.text') }}</p>
    <p><a [routerLink]="['/', defaultView]">{{ t('notFound.link') }}</a></p>
  `,
  styles: `.title { font-size: 1.375rem; margin-bottom: var(--st-3); }`,
})
export class NotFoundComponent {
  readonly defaultView = DEFAULT_VIEW;

  protected readonly t = inject(StudioLanguageService).t;
}
