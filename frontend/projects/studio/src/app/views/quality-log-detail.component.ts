/**
 * One logged turn, in full (9-5c). Presentational — it fetches nothing.
 *
 * ALT's "Pattern-Engine" block had four figures, two of which cannot vary:
 * `phase2_scores` holds a single entry since Welle E v4, so `phase2_winner_score`
 * is 1.0 and `phase2_score_gap` is 0.0 on every row (`obs/quality_events.py`
 * reaches its runner-up branch only for `len(...) >= 2`). Both are dropped, for
 * the same reason the two KPI cards in the overview are. `candidate_count` and
 * `eliminated_count` come from phase-1 elimination, which still runs, so they
 * stay.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import type { QualityLog } from '../core/quality-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { StudioFormat } from '../i18n/studio-format.service';

@Component({
  selector: 'studio-quality-log-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-log-detail.component.html',
  styleUrl: './quality-log-detail.component.scss',
})
export class QualityLogDetailComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  /** Teilt sich den Teilkatalog mit dem Log-Panel — es ist EIN Panel. */
  protected readonly t = inject(StudioLanguageService).t;

  readonly log = input.required<QualityLog>();

  readonly dismiss = output<void>();

  readonly entities = computed<readonly { key: string; value: string }[]>(() =>
    Object.entries(this.log().entities ?? {})
      .filter(([, value]) => value !== null && value !== '' && value !== undefined)
      .map(([key, value]) => ({ key, value: String(value) })));

  readonly when = computed(() => this.fmt.dateTime(this.log().created_at));

  decimal(value: number): string {
    return this.fmt.decimal(value);
  }

  whole(value: number): string {
    return this.fmt.whole(value);
  }
}
