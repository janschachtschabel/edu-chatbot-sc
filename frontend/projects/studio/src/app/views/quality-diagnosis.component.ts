/**
 * The three "where is routing going wrong" breakdowns (9-5c).
 *
 * Each is its own read with its own state: they are separate endpoints and one
 * of them failing says nothing about the other two. ALT fetched all three in the
 * same `Promise.all` as the logs and the stats, on every keystroke in a filter
 * field — although none of the three accepts a pattern, intent or session
 * filter, so they could not have returned anything different.
 *
 * `<details>` rather than a hand-built accordion: the open/close semantics,
 * keyboard handling and screen-reader announcement come from the browser. ALT
 * kept an `openDetail` state that allowed exactly one open section, which is a
 * restriction with no reason behind it.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, output, untracked,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { formatDecimal } from '../core/format';
import {
  QualityApi, type Breakdown, type DegradationGroup, type EmptyEntityGroup,
  type LogFilters, type LowConfidence, type QualityScope,
} from '../core/quality-api.service';
import { AsyncStateComponent } from './async-state.component';

@Component({
  selector: 'studio-quality-diagnosis',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-diagnosis.component.html',
  styleUrl: './quality-diagnosis.component.scss',
})
export class QualityDiagnosisComponent {
  private readonly api = inject(QualityApi);

  readonly scope = input.required<QualityScope>();

  /** Asks the view to show the matching turns; the shell owns the log filters. */
  readonly drill = output<LogFilters>();

  readonly degradations = new AsyncData<Breakdown<DegradationGroup>>(
    () => this.api.degradations(this.scope()));
  readonly emptyEntities = new AsyncData<Breakdown<EmptyEntityGroup>>(
    () => this.api.emptyEntities(this.scope()));
  readonly lowConfidence = new AsyncData<LowConfidence>(
    () => this.api.lowConfidence(this.scope()));

  readonly degradationGroups = computed(() => this.degradations.value()?.groups ?? []);
  readonly emptyEntityGroups = computed(() => this.emptyEntities.value()?.groups ?? []);
  readonly lowConfidenceTurns = computed(() => this.lowConfidence.value()?.turns ?? []);

  constructor() {
    effect(() => {
      this.scope();
      untracked(() => {
        void this.degradations.reload();
        void this.emptyEntities.reload();
        void this.lowConfidence.reload();
      });
    });
  }

  /** Called by the panel's own "Aktualisieren"; all three are one answer. */
  reload(): void {
    void this.degradations.reload();
    void this.emptyEntities.reload();
    void this.lowConfidence.reload();
  }

  confidence(value: number): string {
    return formatDecimal(value);
  }
}
