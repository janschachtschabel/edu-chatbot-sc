/**
 * Eval trends across runs (9-5d): does quality move, and in which direction?
 *
 * Six things are plotted. The judge score per run comes from the run metadata
 * and covers golden runs too. The five classification series come from
 * `summary.classification_metrics`, which golden AND generative runs write —
 * but a golden v2 run has no classifier targets, so its rates are None and the
 * backend skips its points (GV6 + review fix 2026-08-22): the series show a
 * gap for such runs rather than a fake 0 % crash. An installation that has
 * only ever run gold flows therefore sees the score timeline filled and the
 * classification series empty — stated in the UI rather than left looking
 * broken.
 *
 * The charts are `role="img"` with a spoken summary; the table below is the
 * accessible source for every number (same split as the load-test chart).
 */
import {
  ChangeDetectionStrategy, Component, computed, inject,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { EvalApi, type EvalTrends, type TrendPoint } from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { RichTextComponent } from './rich-text.component';
import { type TrendChart, rateChart, scoreChart } from './trend-chart';
import { StudioFormat } from '../i18n/studio-format.service';

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

/**
 * Eingefroren war bis C1-d4c die Beschriftung samt Erklärsatz, nicht nur die
 * Kennung — der zehnte Fall dieser Art. Jetzt trägt die Tabelle nur noch die
 * beiden Schlüssel und den Griff auf die passende Serie; die Texte entstehen
 * beim Rendern.
 *
 * Als Modul-Konstante und nicht mehr im `computed()`: die vier Einträge hängen
 * an keinem Zustand, und vier Objekte je Neuberechnung neu zu bauen war Arbeit
 * ohne Anlass.
 */
const RATES: readonly {
  readonly key: string;
  readonly labelKey: string;
  readonly hintKey: string;
  readonly pick: (data: EvalTrends) => readonly TrendPoint[];
}[] = [
  {
    key: 'cache',
    labelKey: 'evalTrends.rate.cache', hintKey: 'evalTrends.rate.cache.hint',
    pick: (d) => d.cache_hit_trend,
  },
  {
    key: 'match',
    labelKey: 'evalTrends.rate.match', hintKey: 'evalTrends.rate.match.hint',
    pick: (d) => d.llm_engine_match_trend,
  },
  {
    key: 'persona',
    labelKey: 'evalTrends.rate.persona', hintKey: 'evalTrends.rate.persona.hint',
    pick: (d) => d.persona_correct_trend,
  },
  {
    key: 'intent',
    labelKey: 'evalTrends.rate.intent', hintKey: 'evalTrends.rate.intent.hint',
    pick: (d) => d.intent_correct_trend,
  },
];

const EMPTY: EvalTrends = {
  runs: [], pattern_trend: {}, cache_hit_trend: [],
  llm_engine_match_trend: [], persona_correct_trend: [], intent_correct_trend: [],
};

@Component({
  selector: 'studio-eval-trends',
  imports: [AsyncStateComponent, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-trends.component.html',
  styleUrl: './eval-trends.component.scss',
})
export class EvalTrendsComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;
  protected readonly rich = this.lang.rich;

  private readonly api = inject(EvalApi);

  readonly trends = new AsyncData<EvalTrends>(() => this.api.trends(), this.t);

  /** `AsyncData` never fetches on its own — the first read is triggered here. */
  constructor() {
    void this.trends.reload();
  }

  private readonly data = computed(() => this.trends.value() ?? EMPTY);

  readonly runs = computed(() => this.data().runs);

  readonly scores = computed(() => scoreChart(this.runs()));

  readonly rates = computed<readonly RateSeries[]>(() => {
    const d = this.data();
    return RATES.map((series) => ({
      key: series.key,
      label: this.t(series.labelKey),
      hint: this.t(series.hintKey),
      chart: rateChart(series.pick(d)),
    }));
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

  /**
   * Spoken summary for a chart's `aria-label`.
   *
   * Drei ganze Sätze aus dem Katalog statt eines zusammengesetzten (C1-d4c).
   * „ein Lauf" ist dabei kein Mehrzahl-Fall, sondern ein anderer INHALT: bei
   * einem einzigen Punkt gibt es keine Richtung zu nennen.
   */
  describe(series: RateSeries): string {
    const points = series.chart.points;
    const label = series.label;
    if (points.length === 0) return this.t('evalTrends.say.none', { label });

    const latest = points[points.length - 1].value;
    const value = this.fmt.percent(latest);
    if (points.length === 1) return this.t('evalTrends.say.one', { label, value });

    const first = points[0].value;
    return this.t('evalTrends.say.many', {
      label, value, count: points.length,
      first: this.fmt.percent(first),
      direction: this.t(this.directionKey(latest, first)),
    });
  }

  describeScores(): string {
    const points = this.scores().points;
    if (points.length === 0) return this.t('evalTrends.scores.none');
    return this.t('evalTrends.scores.some', {
      value: this.fmt.decimal(points[points.length - 1].value),
      count: points.length,
    });
  }

  /** Spoken summary of a pattern sparkline — „über 1 Lauf" statt „1 Läufe". */
  describeSpark(pattern: PatternSeries): string {
    return this.lang.plural('evalTrends.spark', pattern.chart.points.length);
  }

  percent(value: number | null): string {
    return value === null ? '–' : this.fmt.percent(value);
  }

  /** Obere Achsen-Marke der Raten-Kurven (Feedback 2026-08-22): die Achse
   *  ist fix 0..1 (`rateChart`), die Marke ganzzahlig — „100,0 %" wäre
   *  Pseudo-Präzision an einer Skala. */
  rateAxisTop(): string {
    return this.fmt.percent(1, 0);
  }

  score(value: number | null): string {
    return value === null ? '–' : this.fmt.decimal(value);
  }

  when(iso: string): string {
    return this.fmt.dateTime(iso);
  }

  /** Ausgeschrieben statt aus dem Vorzeichen gerechnet: ein Schlüssel, den
   *  eine Suche im Katalog findet. */
  private directionKey(latest: number, first: number): string {
    if (latest > first) return 'evalTrends.dir.up';
    if (latest < first) return 'evalTrends.dir.down';
    return 'evalTrends.dir.flat';
  }
}
