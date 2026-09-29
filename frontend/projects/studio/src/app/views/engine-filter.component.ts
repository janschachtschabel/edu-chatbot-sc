/**
 * „Maschine: alle | Muster-Maschine | Agent-Schleife" — der Filter der
 * Lauf-Liste und des Verlaufs (ST-7a).
 *
 * Eine Auswahl statt Radios wie bei der Herkunft (`studio-origin-scope`): er
 * steht in derselben Werkzeugleiste wie der Status der Lauf-Liste und sieht
 * aus wie dieser. Gefiltert wird auf dem Server — die Komponente meldet nur
 * die Wahl. `inputId` trennt die beiden Filter der Evaluationsseite, deren
 * Reiter montiert bleiben.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, output,
} from '@angular/core';

import type { EngineFilter } from '../core/eval-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { engineLabel } from './engine-label';

const FILTERS: readonly EngineFilter[] = ['', 'pattern', 'agent'];

@Component({
  selector: 'studio-engine-filter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <label class="ef" [for]="inputId()">
      {{ t('evalEngine.filter.label') }}
      <select [id]="inputId()" (change)="choose($any($event.target).value)">
        @for (option of options(); track option.value) {
          <option [value]="option.value" [selected]="option.value === value()">
            {{ option.label }}
          </option>
        }
      </select>
    </label>
  `,
  styles: `
    .ef {
      display: flex;
      flex-direction: column;
      gap: var(--st-1);
      font-size: 0.8125rem;
      color: var(--st-text-muted);
    }

    select {
      min-block-size: 2.25rem;
      padding: var(--st-1) var(--st-2);
      border: 1px solid var(--st-text-muted);
      border-radius: var(--st-radius);
      background: var(--st-panel);
      color: var(--st-text);
      font: inherit;
    }
  `,
})
export class EngineFilterComponent {
  protected readonly t = inject(StudioLanguageService).t;

  readonly inputId = input.required<string>();
  readonly value = input.required<EngineFilter>();
  readonly valueChange = output<EngineFilter>();

  readonly options = computed(() => FILTERS.map((value) => ({
    value,
    label: value ? engineLabel(value, this.t) : this.t('evalEngine.filter.all'),
  })));

  /** Nur ein angebotener Wert geht weiter — die Auswahl kennt keinen anderen,
   *  aber der Typ soll es nicht bloß behaupten. */
  choose(raw: string): void {
    const chosen = FILTERS.find((value) => value === raw);
    if (chosen !== undefined) this.valueChange.emit(chosen);
  }
}
