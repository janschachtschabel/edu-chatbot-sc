/**
 * The two catalogues of the architecture reference: the signal modulation table
 * and the material types (A5-Rest).
 *
 * Both are rendered from the running configuration, not from a checked-in copy —
 * see `reference-catalogs.ts` for the four wrong rows and the missing type that
 * ALT's hand-written versions had accumulated.
 *
 * The signals arrive as an input because the front page already reads
 * `/config/elements` for its layer counts; asking a second time would give the
 * two halves of one page a chance to disagree. The material types have no such
 * reader, so this component owns that request — paid only when the reference tab
 * is opened, since it mounts on first visit.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { pickLocalized } from '@boerdi/ui';

import { AsyncData } from '../core/async-data';
import { ConfigApi, type AreaDocument } from '../core/config-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import {
  groupSignals, splitMaterialTypes, type MaterialType, type SignalElement,
} from './reference-catalogs';
import { RichTextComponent } from './rich-text.component';

const MATERIAL_AREA = '05-canvas/material-types';

@Component({
  selector: 'studio-reference-catalogs',
  imports: [RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-catalogs.component.html',
  styleUrl: './reference-catalogs.component.scss',
})
export class ReferenceCatalogsComponent {
  private readonly lang = inject(StudioLanguageService);

  /** Uebersetzer fuer den Fehlersatz der Leseoperationen und fuer die
   *  Texte dieser Ansicht. */
  protected readonly t = this.lang.t;

  /** Drei Saetze tragen `<code>` oder `<strong>` mitten im Satz. */
  protected readonly rich = this.lang.rich;

  private readonly config = inject(ConfigApi);

  readonly signals = input<readonly SignalElement[]>([]);

  readonly materials = new AsyncData<AreaDocument>(() => this.config.data(MATERIAL_AREA), this.t);

  readonly dimensions = computed(() => groupSignals(this.signals()));
  readonly split = computed(() => splitMaterialTypes(this.materials.value()?.data ?? {}));

  readonly area = MATERIAL_AREA;

  constructor() {
    void this.materials.reload();
  }

  /**
   * Beschriftung eines Material-Typs in der aktiven Sprache.
   *
   * Sie kommt aus der Konfiguration, nicht aus dem Katalog: seit C1-g2e pflegt
   * `material-types.yaml` je Typ ein `label_en`. Ohne diese Wahl staenden
   * deutsche Chip-Namen mitten in einer englischen Tabelle; ist das Feld leer,
   * bleibt es bei der deutschen Beschriftung — „leer heisst nicht gepflegt".
   */
  materialLabel(type: MaterialType): string {
    return pickLocalized(type.label, type.labelEn, this.lang.i18n.locale());
  }

  /** „3 Einträge · 2 Typen" — zwei Anzahlen, zwei Formen, ein Zusammenbau
   *  (dasselbe Muster wie `ltRun.totals`). */
  caption(): string {
    const split = this.split();
    return this.t('rc.mat.caption', {
      entries: this.lang.plural('rc.mat.entries', split.entries),
      types: this.lang.plural('rc.mat.types', split.types),
    });
  }
}
