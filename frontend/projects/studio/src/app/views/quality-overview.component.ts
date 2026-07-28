/**
 * The Analyse landing panel (9-5c): headline numbers and the two distributions.
 *
 * Two of ALT's seven KPI cards are gone, and their absence is stated rather than
 * silently applied. Since Welle E v4 the pattern engine is hint-primary and no
 * longer scores candidates, so `phase2_scores` carries a single entry: the
 * runner-up is always empty and the gap always 0. ALT retired the "Tight Races"
 * card (it shows a literal "—") but left "Ø Score-Gap" reading a permanent
 * 0,000 next to it — a number that looks measured and is not.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, output, untracked,
  viewChild,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { formatDecimal, formatPercent, formatWhole } from '../core/format';
import {
  QualityApi, type LogFilters, type QualityScope, type QualityStats,
} from '../core/quality-api.service';
import { AsyncStateComponent } from './async-state.component';
import { QualityBarsComponent } from './quality-bars.component';
import { QualityDiagnosisComponent } from './quality-diagnosis.component';

/** ALT's thresholds for the advisory box, kept so the same runs read the same. */
const DEGRADATION_HINT = 0.05;
const EMPTY_ENTITY_HINT = 0.3;

@Component({
  selector: 'studio-quality-overview',
  imports: [AsyncStateComponent, QualityBarsComponent, QualityDiagnosisComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-overview.component.html',
  styleUrl: './quality-overview.component.scss',
})
export class QualityOverviewComponent {
  private readonly api = inject(QualityApi);

  readonly scope = input.required<QualityScope>();

  /** Forwarded from the diagnosis blocks: "show me the turns behind this row". */
  readonly drill = output<LogFilters>();

  private readonly diagnosis = viewChild(QualityDiagnosisComponent);

  readonly stats = new AsyncData<QualityStats>(() => this.api.stats(this.scope()));
  readonly value = computed(() => this.stats.value());

  /** Loaded, and the installation has not answered a single turn yet. */
  readonly isEmpty = computed(() => this.value()?.total_turns === 0);

  readonly hints = computed<readonly string[]>(() => {
    const stats = this.value();
    if (!stats) return [];
    const out: string[] = [];
    if (stats.degradation_rate > DEGRADATION_HINT) {
      out.push(`Degradation-Rate bei ${this.percent(stats.degradation_rate)} — `
        + 'Pflicht-Slots der betroffenen Patterns prüfen.');
    }
    if (stats.empty_entity_rate > EMPTY_ENTITY_HINT) {
      out.push(`${this.percent(stats.empty_entity_rate)} der Turns ohne erkannte Entities — `
        + 'Entity-Erkennung im Classifier prüfen.');
    }
    return out;
  });

  constructor() {
    effect(() => {
      this.scope();
      untracked(() => void this.stats.reload());
    });
  }

  /**
   * The three breakdowns below the numbers are part of the same answer, so one
   * button refreshes the whole panel. Reaching into the child's own reads is the
   * pattern the sessions view already uses for its transcript.
   */
  reload(): void {
    void this.stats.reload();
    this.diagnosis()?.reload();
  }

  decimal(value: number): string {
    return formatDecimal(value);
  }

  percent(value: number): string {
    return formatPercent(value);
  }

  whole(value: number): string {
    return formatWhole(value);
  }
}
