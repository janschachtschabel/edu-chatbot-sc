/**
 * Die Muster-Tafeln eines Laufs (ST-7d): Kennzahlen, Konfusionsmatrizen,
 * Werkzeugtreue je Muster — aus `summary.classification_metrics`.
 *
 * Zugeklappt, weil sie Fachleuten für die Muster-Maschine gelten: wer einen
 * Lauf öffnet, will zuerst Scorecard und Profil. Das Lauf-Detail zeigt sie
 * nicht bei Agent-Läufen (dort gibt es weder Hinweis noch Musterwahl).
 *
 * Zahlen stehen in echten Tabellen; die Färbung der Matrix-Zellen doppelt nur,
 * was Zeile und Spalte schon sagen (gleiches Label = Treffer).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import {
  type ConfusionCell, type PatternKpi, confusionTable, patternKpis, toolComplianceRows,
} from './pattern-panels';

/** Welche Matrix aus welchem Feld, und wie ihre Ecke die Achsen nennt. */
const MATRICES = [
  { key: 'persona', field: 'persona_confusion', corner: 'evalClass.corner.expected' },
  { key: 'intent', field: 'intent_confusion', corner: 'evalClass.corner.expected' },
  { key: 'pattern', field: 'pattern_confusion_llm_vs_engine', corner: 'evalClass.corner.hint' },
] as const;

/** Unter dieser Quote gilt ein Muster als auffällig in der Werkzeugtreue. */
const WEAK_COMPLIANCE = 0.5;

@Component({
  selector: 'studio-eval-pattern-panels',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-pattern-panels.component.html',
  styleUrl: './eval-pattern-panels.component.scss',
})
export class EvalPatternPanelsComponent {
  private readonly fmt = inject(StudioFormat);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly metrics = input.required<Readonly<Record<string, unknown>>>();

  readonly kpis = computed(() => patternKpis(this.metrics()).map((kpi) => ({
    key: kpi.key,
    label: this.t(`evalClass.kpi.${kpi.key}`),
    text: this.kpiText(kpi),
  })));

  readonly matrices = computed(() => MATRICES.flatMap((matrix) => {
    const table = confusionTable(this.metrics()[matrix.field]);
    return table ? [{
      key: matrix.key,
      caption: this.t(`evalClass.matrix.${matrix.key}`),
      corner: this.t(matrix.corner),
      table,
    }] : [];
  }));

  readonly tools = computed(() => toolComplianceRows(this.metrics()).map((row) => ({
    ...row,
    rateText: row.rate === null ? '–' : this.fmt.percent(row.rate, 0),
    weak: row.rate !== null && row.rate < WEAK_COMPLIANCE,
  })));

  cellClass(cell: ConfusionCell): string {
    if (cell.n === 0) return 'pp-zero';
    return cell.diagonal ? 'pp-hit' : 'pp-miss';
  }

  private kpiText(kpi: PatternKpi): string {
    if (kpi.value === null) return this.t('evalClass.notMeasured');
    const main = this.lang.plural('evalClass.value', kpi.basis, {
      rate: this.fmt.percent(kpi.value, 0),
    });
    return kpi.sub === undefined || kpi.sub === null ? main
      : `${main} · ${this.t('evalClass.fullyFitting', { rate: this.fmt.percent(kpi.sub, 0) })}`;
  }
}
