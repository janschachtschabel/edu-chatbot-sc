/**
 * „2 Läufe zum Vergleich gewählt · Gewählte vergleichen · Auswahl aufheben"
 * (ST-7c) — die Leiste über der Lauf-Liste, sobald etwas angekreuzt ist.
 *
 * Eigener Baustein, damit die Lauf-Liste nicht noch eine Aufgabe samt Stil
 * trägt. Die Auswahl selbst hält die Liste (`RunSelection`); die Leiste liest
 * sie und meldet nur den Wunsch zu vergleichen.
 *
 * Ein gesperrter Knopf sagt, warum: ohne den Satz daneben wäre er ein Rätsel.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, output,
} from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { MAX_COMPARE, type RunSelection } from './run-selection';

@Component({
  selector: 'studio-compare-bar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="cb">
      <p class="cb-count" role="status">{{ countText() }}</p>
      <button
        type="button"
        class="cb-start"
        [disabled]="selection().count() < 2"
        [attr.aria-describedby]="hint() ? 'cb-hint' : null"
        (click)="compare.emit(selection().ids())"
      >
        {{ t('evalCompare.start') }}
      </button>
      <button type="button" class="cb-clear" (click)="selection().clear()">
        {{ t('evalCompare.clear') }}
      </button>
      @if (hint(); as text) {
        <p class="cb-hint" id="cb-hint">{{ text }}</p>
      }
    </div>
  `,
  styles: `
    .cb {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: var(--st-2) var(--st-3);
      margin-block-end: var(--st-3);
      padding: var(--st-2) var(--st-3);
      border: 1px solid var(--st-accent);
      border-radius: var(--st-radius);
      background: var(--st-accent-soft);
    }

    .cb-count {
      margin: 0;
      font-size: 0.875rem;
      font-weight: 600;
    }

    .cb-hint {
      flex-basis: 100%;
      margin: 0;
      font-size: 0.8125rem;
      color: var(--st-text-muted);
    }

    button {
      min-block-size: 2.25rem;
      padding: var(--st-1) var(--st-3);
      border: 1px solid var(--st-rule-strong);
      border-radius: var(--st-radius);
      background: var(--st-panel);
      color: var(--st-text);
      font: inherit;
      font-size: 0.8125rem;
      cursor: pointer;
    }

    .cb-start:not(:disabled) {
      border-color: var(--st-accent);
      font-weight: 600;
    }

    button:disabled {
      opacity: 0.6;
      cursor: default;
    }
  `,
})
export class CompareBarComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly selection = input.required<RunSelection>();
  readonly compare = output<readonly string[]>();

  readonly countText = computed(() =>
    this.lang.plural('evalCompare.chosen', this.selection().count()));

  readonly hint = computed(() => {
    const selection = this.selection();
    if (selection.count() < 2) return this.t('evalCompare.needTwo');
    return selection.full() ? this.t('evalCompare.full', { max: MAX_COMPARE }) : '';
  });
}
