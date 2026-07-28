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

import { AsyncData } from '../core/async-data';
import { ConfigApi, type AreaDocument } from '../core/config-api.service';
import {
  groupSignals, splitMaterialTypes, type SignalElement,
} from './reference-catalogs';

const MATERIAL_AREA = '05-canvas/material-types';

@Component({
  selector: 'studio-reference-catalogs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-catalogs.component.html',
  styleUrl: './reference-catalogs.component.scss',
})
export class ReferenceCatalogsComponent {
  private readonly config = inject(ConfigApi);

  readonly signals = input<readonly SignalElement[]>([]);

  readonly materials = new AsyncData<AreaDocument>(() => this.config.data(MATERIAL_AREA));

  readonly dimensions = computed(() => groupSignals(this.signals()));
  readonly split = computed(() => splitMaterialTypes(this.materials.value()?.data ?? {}));

  readonly area = MATERIAL_AREA;

  constructor() {
    void this.materials.reload();
  }
}
