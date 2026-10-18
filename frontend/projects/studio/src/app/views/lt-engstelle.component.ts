/**
 * Engstelle je Anfrageart (Paket 16, D4) — unter der Stufentabelle eines Lasttests.
 *
 * Je Art ein gestapelter Balken (nur zur Orientierung, `aria-hidden`) und dieselben Anteile als
 * Text daneben; der größte Teil steht beim Namen. Die Folge der Teile ist fest, damit eine
 * Farbe in jeder Zeile dasselbe meint; die Bedeutung trägt der Text (WCAG 1.4.1).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { StageResult } from '../core/loadtest-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { type EngstellenTeil, engstelle } from './engstelle-chart';

@Component({
  selector: 'studio-lt-engstelle',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './lt-engstelle.component.html',
  styleUrl: './lt-engstelle.component.scss',
})
export class LtEngstelleComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);

  readonly stages = input.required<readonly StageResult[]>();
  readonly daten = computed(() => engstelle(this.stages()));

  teilText(teil: EngstellenTeil): string {
    return `${this.t('ltEngstelle.teil.' + teil.kategorie)} ${this.fmt.percent(teil.anteil, 0)}`;
  }
}
