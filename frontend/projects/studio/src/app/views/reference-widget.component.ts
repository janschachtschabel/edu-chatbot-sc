/**
 * The widget-embedding section of the architecture reference (9-5f / A5).
 *
 * Its own component, not a block in the host template, because it documents a
 * different thing for a different reason: the public host contract of
 * `<boerdi-chat>` (§5.5) rather than the prompt architecture. Data in
 * `widget-contract-data.ts`, pinned from the widget project's own spec.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { RichTextComponent } from './rich-text.component';
import {
  EMBED_SAMPLE, HOST_ATTRIBUTES, HOST_EVENTS, HOST_OUTPUTS, type HostAttribute,
} from './widget-contract-data';

@Component({
  selector: 'studio-reference-widget',
  imports: [RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-widget.component.html',
  styleUrl: './reference-widget.component.scss',
})
export class ReferenceWidgetComponent {
  private readonly lang = inject(StudioLanguageService);

  /** Die Prosa dieses Abschnitts (C1-d5b2) aus `i18n/catalogue/reference-widget.ts`. */
  protected readonly t = this.lang.t;

  protected readonly rich = this.lang.rich;

  readonly attributes = HOST_ATTRIBUTES;
  readonly events = HOST_EVENTS;
  readonly outputs = HOST_OUTPUTS.join(', ');

  /**
   * Das Einbettungs-Beispiel mit übersetzten Kommentaren.
   *
   * `computed`, damit der Sprachwechsel es neu setzt: die Vorlage liest den Wert
   * einmal, ein Feld bliebe auf der Startsprache stehen.
   */
  readonly embedSample = computed(() => EMBED_SAMPLE
    .replace('{minimal}', this.t('rw.sample.minimal'))
    .replace('{lean}', this.t('rw.sample.lean'))
    .replace('{edu}', this.t('rw.sample.edu')));

  /** True on the first row of an attribute group, so the group is named once. */
  isGroupStart(index: number): boolean {
    return index === 0
      || this.attributes[index - 1].groupKey !== this.attributes[index].groupKey;
  }

  /** Der Vorgabewert: wörtlich, oder als Wort aus dem Katalog („leer"). */
  fallbackOf(row: HostAttribute): string {
    return row.fallbackKey ? this.t(row.fallbackKey) : row.fallback;
  }
}
