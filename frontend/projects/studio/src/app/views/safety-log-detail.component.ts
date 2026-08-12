/**
 * One safety decision in full (9-5b) — the record behind a row in the list.
 *
 * Everything here comes from the row the list already holds, so this panel
 * fetches nothing. Sections an event has nothing for are left out entirely
 * rather than shown with a dash: a wall of "–" hides the two lines that matter.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { type SafetyLog } from '../core/safety-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { legalLabels, riskLabel } from './safety-labels';

@Component({
  selector: 'studio-safety-log-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './safety-log-detail.component.html',
  styleUrl: './safety-log-detail.component.scss',
})
export class SafetyLogDetailComponent {
  /** Uebersetzer fuer die Texte dieses Panels. */
  protected readonly t = inject(StudioLanguageService).t;

  readonly log = input.required<SafetyLog>();

  readonly risk = computed(() => riskLabel(this.log().risk_level, this.t));
  readonly stages = computed(() => this.log().stages_run.join(' → '));
  readonly reasons = computed(() => this.log().reasons.join(', '));
  readonly legal = computed(() => legalLabels(this.log().legal_flags, this.t));

  /** Pretty-printed scores; the block is hidden when there are none. */
  readonly scores = computed(() => JSON.stringify(this.log().categories_json, null, 2));
  readonly hasScores = computed(() => Object.keys(this.log().categories_json ?? {}).length > 0);
}
