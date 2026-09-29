/**
 * The "Datenbasis" choice — all sessions, production only, eval only (ST-9).
 *
 * Lifted out of the analysis page when Kosten and Sessions needed the same
 * choice: three copies of a radio group drift (the analysis hint said "real
 * conversations only" while load tests still counted). Real radios in a
 * fieldset: arrow keys, the group name and the checked state come from the
 * platform. `name` keeps two groups on one page apart.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, output,
} from '@angular/core';

import type { OriginScope } from '../core/origin-scope';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Ids and key names only: the wording is the catalogue's. */
const SCOPES: readonly { readonly id: OriginScope; readonly key: string }[] = [
  { id: 'all', key: 'origin.all' },
  { id: 'production', key: 'origin.production' },
  { id: 'eval', key: 'origin.eval' },
];

@Component({
  selector: 'studio-origin-scope',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './origin-scope.component.html',
  styleUrl: './origin-scope.component.scss',
})
export class OriginScopeComponent {
  protected readonly t = inject(StudioLanguageService).t;

  readonly value = input.required<OriginScope>();
  /** The radio group's name — unique per page. */
  readonly name = input.required<string>();
  readonly valueChange = output<OriginScope>();

  readonly options = computed(() => SCOPES.map((scope) => ({
    id: scope.id, label: this.t(scope.key), hint: this.t(`${scope.key}.hint`),
  })));
}
