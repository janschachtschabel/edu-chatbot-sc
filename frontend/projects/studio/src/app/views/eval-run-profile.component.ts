/**
 * Das Profil eines Eval-Laufs im Detail (ST-7b): Judge je Achse, Dauer je Zug,
 * Token und Kosten, Robustheit.
 *
 * Die Zahlen rechnet das Backend mit derselben Arithmetik wie der
 * Maschinen-Vergleich (K0-1); hier wird nur beschriftet. Die harte Quote fehlt
 * mit Absicht — sie steht schon in der Gold-Scorecard darüber.
 *
 * Was ein Lauf nicht misst, fehlt, statt als 0 dazustehen: ohne Judge keine
 * Achsen (und kein Wort vom Judge), ein generativer Lauf ohne Zugdauer, ein
 * Modell ohne Preis ohne Kosten — dafür mit seinem Namen.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { JUDGE_AXES, WEAK_AXIS, type RunProfile } from '../core/eval-profile';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

interface AxisRow {
  readonly axis: string;
  readonly label: string;
  readonly value: number | null;
  readonly text: string;
  readonly weak: boolean;
  /** Balkenbreite in Prozent der Skala 0–2. */
  readonly share: number;
}

/** Zwölf Nachkommastellen reichen jedem Betrag je Zug; `toFixed` schreibt nie
 *  die Exponentform („1e-7"), die `formatMoney` nicht lesen könnte. */
const MONEY_PLACES = 12;

@Component({
  selector: 'studio-eval-run-profile',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-run-profile.component.html',
  styleUrl: './eval-run-profile.component.scss',
})
export class EvalRunProfileComponent {
  private readonly fmt = inject(StudioFormat);
  protected readonly t = inject(StudioLanguageService).t;

  readonly profile = input.required<RunProfile>();

  /** Leer, wenn keine Achse bewertet wurde — dann lief kein Judge. */
  readonly axes = computed<readonly AxisRow[]>(() => {
    const values = this.profile().quality.axes;
    const rows = JUDGE_AXES.map((axis) => {
      const value = values[axis] ?? null;
      const weak = value !== null && value < WEAK_AXIS;
      const number = value === null ? '' : this.fmt.decimal(value);
      return {
        axis,
        label: this.t(`evalProfile.axis.${axis}`),
        value,
        text: value === null ? this.t('evalProfile.notJudged')
          : weak ? this.t('evalProfile.weak', { value: number }) : number,
        weak,
        share: value === null ? 0 : (Math.min(Math.max(value, 0), 2) / 2) * 100,
      };
    });
    return rows.some((row) => row.value !== null) ? rows : [];
  });

  readonly speed = computed(() => {
    const speed = this.profile().speed;
    if (speed.p50_ms === null || speed.p95_ms === null) return '';
    return this.t('evalProfile.speedText', {
      p50: this.fmt.seconds(speed.p50_ms),
      p95: this.fmt.seconds(speed.p95_ms),
      over30: this.fmt.percent(speed.over_30s ?? 0, 0),
      over90: speed.over_90s,
    });
  });

  readonly tokens = computed(() => {
    const cost = this.profile().cost;
    if (!cost.turns_with_usage || cost.prompt === null) return '';
    return this.t('evalProfile.tokensText', {
      prompt: this.fmt.whole(Math.round(cost.prompt)),
      cached: this.fmt.whole(Math.round(cost.cached ?? 0)),
      completion: this.fmt.whole(Math.round(cost.completion ?? 0)),
    });
  });

  readonly cost = computed(() => {
    const { cost, currency } = this.profile();
    if (!cost.turns_with_usage) return '';
    if (cost.cost_per_turn !== null && cost.cost_total !== null && currency) {
      return this.t('evalProfile.costText', {
        perTurn: this.money(cost.cost_per_turn, currency),
        total: this.money(cost.cost_total, currency),
      });
    }
    if (cost.price_unavailable.length > 0) {
      return this.t('evalProfile.noPrice', { models: cost.price_unavailable.join(', ') });
    }
    return this.t('evalProfile.noPricing');
  });

  readonly robustness = computed(() => {
    const { robustness, quality } = this.profile();
    const judged = robustness.judge_failed > 0
      || Object.values(quality.axes).some((value) => value !== null);
    return this.t(judged ? 'evalProfile.robustnessText' : 'evalProfile.robustnessNoJudge', {
      errors: robustness.chat_errors,
      judge: robustness.judge_failed,
      empty: robustness.empty,
      fallback: robustness.fallback,
    });
  });

  private money(value: number, currency: string): string {
    return this.fmt.money(value.toFixed(MONEY_PLACES), currency);
  }
}
