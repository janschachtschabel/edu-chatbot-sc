/**
 * The routing matrix (9-5c): which pattern wins for each persona × intent pair.
 *
 * Two ALT defects are fixed rather than ported. Every populated cell was a
 * `<td onClick>`, so the entire grid — the densest information in the studio —
 * could not be reached without a mouse; here each cell is a `<button>`. And the
 * competing patterns lived in a `title=` tooltip only, which keyboard and touch
 * users never see; here they are text in the cell.
 *
 * ALT also tinted each cell by a hash of the pattern id (`hsl(hash % 360, …)`)
 * and then multiplied the opacity by the share. That is dropped: a hue picked by
 * a hash cannot be made to hold 3:1 against its background, the opacity ramp
 * pushed the text below 4.5:1, and both encoded only the pattern id and the
 * share — which are printed in the cell as text. The share keeps a proportional
 * bar, which is redundant with the printed percentage and hidden from assistive
 * technology.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal, untracked,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import {
  QualityApi, type LogFilters, type MatrixCell, type QualityScope, type RoutingMatrix,
} from '../core/quality-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { StudioFormat } from '../i18n/studio-format.service';

interface MatrixRow {
  readonly persona: string;
  /** One entry per intent column; `null` where that pair has no samples. */
  readonly cells: readonly (MatrixCell | null)[];
}

@Component({
  selector: 'studio-quality-matrix',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-matrix.component.html',
  styleUrl: './quality-matrix.component.scss',
})
export class QualityMatrixComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;

  private readonly api = inject(QualityApi);

  readonly scope = input.required<QualityScope>();

  /**
   * Intent only. `/quality/logs` has no persona filter, so drilling with the
   * persona would show every persona's turns under a promise it cannot keep —
   * ALT's own comment says as much before dropping the persona.
   */
  readonly drill = output<LogFilters>();

  readonly minCount = signal(1);

  readonly matrix = new AsyncData<RoutingMatrix>(
    () => this.api.matrix(this.scope(), this.minCount()), this.t);

  readonly value = computed(() => this.matrix.value());

  /** Loaded, and no pair cleared the threshold. */
  readonly isEmpty = computed(() => this.value()?.cells.length === 0);

  /** The axes are derived from the data: the backend returns only occupied pairs. */
  readonly intents = computed<readonly string[]>(() =>
    [...new Set((this.value()?.cells ?? []).map((cell) => cell.intent_id))].sort());

  readonly rows = computed<readonly MatrixRow[]>(() => {
    const cells = this.value()?.cells ?? [];
    const personas = [...new Set(cells.map((cell) => cell.persona_id))].sort();
    const index = new Map(cells.map((cell) => [`${cell.persona_id}|${cell.intent_id}`, cell]));
    return personas.map((persona) => ({
      persona,
      cells: this.intents().map((intent) => index.get(`${persona}|${intent}`) ?? null),
    }));
  });

  constructor() {
    effect(() => {
      this.scope();
      this.minCount();
      untracked(() => void this.matrix.reload());
    });
  }

  reload(): void {
    void this.matrix.reload();
  }

  /** `min_count=0` would ask the endpoint for every pair ever seen once. */
  onMinCount(value: string): void {
    this.minCount.set(Math.max(1, Number.parseInt(value, 10) || 1));
  }

  /** „Aggregiert aus 13 Turns (all)." — die Anzahl wählt die Form, der
   *  gruppierte Text füllt den Platzhalter. */
  total(matrix: RoutingMatrix): string {
    return this.lang.plural('qualMatrix.total', matrix.total_turns, {
      count: this.fmt.whole(matrix.total_turns), scope: matrix.scope,
    });
  }

  /** Anteil und Sample-Zahl einer Zelle; die Zahl trägt ihre eigene Mehrzahl.
   *  Nicht `cell(…)`: im Template verdeckt die Schleifenvariable den Namen. */
  cellText(cell: MatrixCell): string {
    return this.t('qualMatrix.cell', {
      share: this.fmt.percent(cell.share, 0),
      samples: this.lang.plural('qualMatrix.samples', cell.total_count),
    });
  }

  /** "M15 (2), M08 (1)" — the patterns that lost this cell, and by how much. */
  alternatives(cell: MatrixCell): string {
    return cell.alternatives.map((alt) => `${alt.pattern_id} (${alt.count})`).join(', ');
  }
}
