/**
 * Kosten je Tag (Paket 16, D2) — Säulendiagramm und Tabelle unter der Summe der Kosten-Seite.
 *
 * Die Tabelle ist die Textfassung des Diagramms (WCAG 1.1.1): wer das Bild nicht sieht, liest
 * dieselben Zahlen dort. Sie steht in einem aufklappbaren Teil, damit ein Quartal die Seite
 * nicht verlängert.
 *
 * Umschalter „Betrag | Aufrufe“ (Studio-Rundgang 2026-10-18): ohne gepflegten Preis gibt es
 * keinen Betrag — dann zeigt das Diagramm von selbst die Aufrufe als gewöhnliche Säulen, statt
 * eine leere Fläche mit Ersatzmarken.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, signal,
} from '@angular/core';

import type { UsageDay } from '../core/usage-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { type CostDayMass, costDayChart } from './cost-day-chart';

let naechsteKennung = 0;

@Component({
  selector: 'studio-cost-days',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cost-days.component.html',
  styleUrl: './cost-days.component.scss',
})
export class CostDaysComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly fmt = inject(StudioFormat);

  readonly tage = input.required<readonly UsageDay[]>();
  readonly currency = input.required<string>();

  protected readonly kennung = `cd-${naechsteKennung++}`;

  protected readonly masse: readonly CostDayMass[] = ['betrag', 'aufrufe'];
  /** Die Wahl der Person; `null`, solange sie nicht umgeschaltet hat. */
  private readonly gewaehlt = signal<CostDayMass | null>(null);
  /** Hat irgendein Tag mit Nutzung einen Betrag? Ohne ihn bleibt nur „Aufrufe“. */
  readonly hatPreis = computed(() => this.tage().some((d) => d.amount !== null && d.calls > 0));
  readonly mass = computed<CostDayMass>(
    () => (this.hatPreis() ? (this.gewaehlt() ?? 'betrag') : 'aufrufe'));
  readonly ohnePreis = computed(
    () => this.tage().filter((d) => d.amount === null && d.calls > 0).length);
  readonly chart = computed(() => costDayChart(this.tage(), this.mass()));

  readonly hinweis = computed(() => {
    const c = this.chart();
    if (this.mass() === 'aufrufe') {
      const satz = this.t('costDays.hintAufrufe', { max: this.fmt.whole(c.max) });
      return this.hatPreis() ? satz : `${satz} ${this.t('costDays.hintOhnePreis')}`;
    }
    const satz = c.max > 0
      // toFixed statt '' + c.max: „1e-7“ läse formatMoney als zwei Stellen (wie S2, PR #18).
      ? this.t('costDays.hint', { max: this.fmt.money(c.max.toFixed(10), this.currency()) })
      : this.t('costDays.hintKeinBetrag');
    const ohne = this.ohnePreis();
    return ohne > 0 ? `${satz} ${this.lang.plural('costDays.ohnePreis', ohne)}` : satz;
  });

  waehle(mass: CostDayMass): void {
    this.gewaehlt.set(mass);
  }

  betrag(tag: UsageDay): string {
    if (tag.amount === null) return this.t('costs.noPrice');
    const betrag = this.fmt.money(tag.amount, this.currency());
    return tag.unvollstaendig ? this.t('costDays.unvollstaendig', { betrag }) : betrag;
  }

  /** Der Name einer Säule — beim Überfahren als Tooltip, im gewählten Maß. */
  titel(tag: UsageDay): string {
    const wert = this.mass() === 'aufrufe'
      ? this.lang.plural('costDays.aufrufe', tag.calls, { anzahl: this.fmt.whole(tag.calls) })
      : this.betrag(tag);
    return `${this.fmt.day(tag.tag)}: ${wert}`;
  }
}
