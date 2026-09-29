/**
 * „Wirkt in: Muster-Maschine · Agent-Schleife (teilweise)" — im Kopf jedes
 * Abschnitts (ST-5). Reiner Text: er steht in einem `<summary>`, und dort ist
 * nichts Bedienbares erlaubt.
 *
 * Ohne Zuordnung für den Bereich bleibt er leer, statt zu raten.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { EffectsApi, type Engine } from '../core/effects-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

const ENGINES: readonly Engine[] = ['pattern', 'agent'];

@Component({
  selector: 'studio-effect-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (text(); as satz) {
      <span class="eb">{{ satz }}</span>
    }
  `,
  styles: `
    .eb {
      display: block;
      margin-block-start: var(--st-1);
      font-size: 0.75rem;
      color: var(--st-text-muted);
    }
  `,
})
export class EffectBadgeComponent {
  private readonly effects = inject(EffectsApi).effects;
  private readonly lang = inject(StudioLanguageService);

  readonly area = input.required<string>();

  readonly text = computed(() => {
    const wirkung = this.effects()?.areas[this.area()];
    if (!wirkung) return '';
    const wo = ENGINES
      .filter((engine) => wirkung[engine] !== 'keine')
      .map((engine) => {
        const name = this.lang.t(`effect.engine.${engine}`);
        switch (wirkung[engine]) {
          case 'teilweise': return this.lang.t('effect.partial', { engine: name });
          case 'krise': return this.lang.t('effect.crisisOnly', { engine: name });
          default: return name;
        }
      });
    return wo.length
      ? `${this.lang.t('effect.label')}: ${wo.join(' · ')}`
      : this.lang.t('effect.nowhere');
  });
}
