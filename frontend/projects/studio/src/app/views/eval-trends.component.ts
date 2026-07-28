/**
 * Eval trends across runs (9-5d): does quality move, and in which direction?
 *
 * Six things are plotted. The judge score per run comes from the run metadata
 * and covers golden runs too. The five classification series come from
 * `summary.classification_metrics`, which only a **generative** run writes — so
 * an installation that has only ever run gold flows sees the score timeline
 * filled and the five series empty. That is stated in the UI rather than left
 * looking broken.
 *
 * The charts are `role="img"` with a spoken summary; the table below is the
 * accessible source for every number (same split as the load-test chart).
 */
import {
  ChangeDetectionStrategy, Component, computed, inject,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalTrends, type TrendPoint } from '../core/eval-api.service';
import { formatDecimal, formatPercent, germanDateTime } from '../core/format';
import { AsyncStateComponent } from './async-state.component';
import { type TrendChart, rateChart, scoreChart } from './trend-chart';

interface RateSeries {
  readonly key: string;
  readonly label: string;
  /** What the rate means — the number alone does not say it. */
  readonly hint: string;
  readonly chart: TrendChart;
}

interface PatternSeries {
  readonly patternId: string;
  readonly chart: TrendChart;
  readonly latest: TrendPoint | null;
}

interface RunRow {
  readonly id: string;
  readonly createdAt: string;
  readonly mode: string;
  readonly totalTurns: number;
  readonly avgScore: number | null;
  readonly rates: readonly (number | null)[];
}

const EMPTY: EvalTrends = {
  runs: [], pattern_trend: {}, cache_hit_trend: [],
  llm_engine_match_trend: [], persona_correct_trend: [], intent_correct_trend: [],
};

@Component({
  selector: 'studio-eval-trends',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-trends.component.html',
  styleUrl: './eval-trends.component.scss',
})
export class EvalTrendsComponent {
  private readonly api = inject(EvalApi);

  readonly trends = new AsyncData<EvalTrends>(() => this.api.trends());

  /** `AsyncData` never fetches on its own — the first read is triggered here. */
  constructor() {
    void this.trends.reload();
  }

  private readonly data = computed(() => this.trends.value() ?? EMPTY);

  readonly runs = computed(() => this.data().runs);

  readonly scores = computed(() => scoreChart(this.runs()));

  readonly rates = computed<readonly RateSeries[]>(() => {
    const d = this.data();
    return [
      {
        key: 'cache', label: 'Cache-Hit-Rate',
        hint: 'Anteil der Prompt-Tokens, die aus dem Provider-Cache kamen.',
        chart: rateChart(d.cache_hit_trend),
      },
      {
        key: 'match', label: 'LLM-Pattern-Übereinstimmung',
        hint: 'Wie oft der LLM-Pattern-Hint mit der Engine-Wahl übereinstimmte.',
        chart: rateChart(d.llm_engine_match_trend),
      },
      {
        key: 'persona', label: 'Persona-Trefferquote',
        hint: 'Anteil der Turns, in denen die erkannte Persona der erwarteten entsprach.',
        chart: rateChart(d.persona_correct_trend),
      },
      {
        key: 'intent', label: 'Intent-Trefferquote',
        hint: 'Anteil der Turns, in denen der erkannte Intent dem erwarteten entsprach.',
        chart: rateChart(d.intent_correct_trend),
      },
    ];
  });

  /** True once any classification series carries a point. */
  readonly hasClassification = computed(() =>
    this.rates().some((series) => series.chart.points.length > 0));

  readonly patterns = computed<readonly PatternSeries[]>(() =>
    Object.entries(this.data().pattern_trend)
      .sort(([a], [b]) => a.localeCompare(b, 'de'))
      .map(([patternId, series]) => ({
        patternId,
        chart: rateChart(series),
        latest: series.length > 0 ? series[series.length - 1] : null,
      })));

  /** Runs joined with each series by run id — the table's accessible rows. */
  readonly rows = computed<readonly RunRow[]>(() => {
    const byRun = this.rates().map((series) =>
      new Map(series.chart.points.map((p) => [p.runId, p.value])));
    return this.runs().map((run) => ({
      id: run.id,
      createdAt: run.created_at,
      mode: run.mode,
      totalTurns: run.total_turns,
      avgScore: run.avg_score,
      rates: byRun.map((map) => map.get(run.id) ?? null),
    }));
  });

  reload(): void {
    void this.trends.reload();
  }

  /** Spoken summary for a chart's `aria-label`. */
  describe(series: RateSeries): string {
    const points = series.chart.points;
    if (points.length === 0) return `${series.label}: keine Daten.`;
    const latest = points[points.length - 1].value;
    const current = `aktuell ${formatPercent(latest)}`;
    if (points.length === 1) return `${series.label}: ${current}, ein Lauf.`;
    const first = points[0].value;
    const direction = latest > first ? 'gestiegen' : latest < first ? 'gefallen' : 'unverändert';
    return `${series.label}: ${current}, über ${points.length} Läufe `
      + `von ${formatPercent(first)} ${direction}. Werte in der Tabelle darunter.`;
  }

  describeScores(): string {
    const points = this.scores().points;
    if (points.length === 0) return 'Ø Judge-Score: keine bewerteten Läufe.';
    const latest = points[points.length - 1].value;
    return `Ø Judge-Score: aktuell ${formatDecimal(latest)} über ${points.length} `
      + 'bewertete Läufe. Werte in der Tabelle darunter.';
  }

  percent(value: number | null): string {
    return value === null ? '–' : formatPercent(value);
  }

  score(value: number | null): string {
    return value === null ? '–' : formatDecimal(value);
  }

  when(iso: string): string {
    return germanDateTime(iso);
  }
}
