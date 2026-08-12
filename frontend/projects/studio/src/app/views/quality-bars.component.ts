/**
 * A ranked distribution (9-5c): "which pattern fired how often".
 *
 * A table, not a row of styled divs, because the numbers ARE the content — the
 * bar only makes the ranking scannable and is hidden from assistive technology.
 * ALT drew the same thing with flex divs and no text alternative beyond the
 * count sitting next to it, which happened to work; a table makes it structural.
 *
 * Steht in drei Ansichten an sieben Stellen und übersetzt seit C1-d4b3 seine
 * eigenen drei Texte selbst (`bars.*`, `label.unclassified` aus `shared.ts`).
 * Was die Zahlen ZÄHLEN weiss nur die Aufrufstelle — Beschriftung und eine
 * abweichende Einheit kommen deshalb weiterhin fertig übersetzt von dort.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';

interface BarRow {
  readonly key: string;
  readonly label: string;
  readonly count: number;
  /** Percent of the largest value in the set, for the bar width. */
  readonly share: number;
}

@Component({
  selector: 'studio-quality-bars',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (rows().length > 0) {
      <table class="qb">
        <caption>{{ caption() }}</caption>
        <!-- Screen-reader only: the header carries the column meaning, which on
             screen is self-evident from the two columns themselves. -->
        <thead class="sr">
          <tr><th scope="col">{{ t('bars.key') }}</th><th scope="col">{{ unitLabel() }}</th></tr>
        </thead>
        <tbody>
          @for (row of rows(); track row.key) {
            <tr>
              <th scope="row" class="qb-key">{{ row.label }}</th>
              <td class="qb-value">
                <span class="qb-bar" aria-hidden="true">
                  <span class="qb-bar-fill" [style.inline-size.%]="row.share"></span>
                </span>
                <span class="qb-count">{{ row.count }}</span>
              </td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styleUrl: './quality-bars.component.scss',
})
export class QualityBarsComponent {
  protected readonly t = inject(StudioLanguageService).t;

  readonly data = input.required<Record<string, number>>();
  /** The table's accessible name — two distributions sit side by side.
   *  Already translated by the view that knows what it counts. */
  readonly caption = input.required<string>();
  /** What the numbers count. Leer = der Regelfall („Turns"), hier übersetzt;
   *  eine Ansicht, die etwas anderes zählt, gibt ihr eigenes Wort mit. */
  readonly unit = input('');

  protected readonly unitLabel = computed(() => this.unit() || this.t('bars.unit'));

  readonly rows = computed<readonly BarRow[]>(() => {
    const entries = Object.entries(this.data() ?? {});
    // A distribution of only zeroes would make `count / max` NaN, and an
    // invalid width silently renders as a full bar.
    const max = Math.max(...entries.map(([, count]) => count), 0);
    return entries
      .sort((a, b) => b[1] - a[1])
      .map(([key, count]) => ({
        key,
        // An unclassified turn is stored as an empty id; a blank row would look
        // like a rendering fault.
        label: key || this.t('label.unclassified'),
        count,
        share: max > 0 ? (count / max) * 100 : 0,
      }));
  });
}
