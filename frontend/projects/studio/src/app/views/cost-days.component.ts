/**
 * Kosten je Tag (Paket 16, D2) — Säulendiagramm und Tabelle unter der Summe der Kosten-Seite.
 *
 * Die Tabelle ist die Textfassung des Diagramms (WCAG 1.1.1): wer das Bild nicht sieht, liest
 * dieselben Zahlen dort. Sie steht in einem aufklappbaren Teil, damit ein Quartal die Seite
 * nicht verlängert.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { UsageDay } from '../core/usage-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { costDayChart } from './cost-day-chart';

let naechsteKennung = 0;

@Component({
  selector: 'studio-cost-days',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cost-days.component.html',
  styleUrl: './cost-days.component.scss',
})
export class CostDaysComponent {
  protected readonly t = inject(StudioLanguageService).t;
  protected readonly fmt = inject(StudioFormat);

  readonly tage = input.required<readonly UsageDay[]>();
  readonly currency = input.required<string>();

  protected readonly kennung = `cd-${naechsteKennung++}`;
  readonly chart = computed(() => costDayChart(this.tage()));

  betrag(tag: UsageDay): string {
    if (tag.amount === null) return this.t('costs.noPrice');
    const betrag = this.fmt.money(tag.amount, this.currency());
    return tag.unvollstaendig ? this.t('costDays.unvollstaendig', { betrag }) : betrag;
  }

  /** Der Name einer Säule — beim Überfahren als Tooltip. */
  titel(tag: UsageDay): string {
    return `${this.fmt.day(tag.tag)}: ${this.betrag(tag)}`;
  }
}
