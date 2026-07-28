/**
 * The three system reads of the front page (9-5f / A5).
 *
 * The fourth figure on that page — the last finished eval — comes from
 * `EvalApi.runs()`, which already exists and is already typed; asking the same
 * endpoint through a second service would only give the two views a chance to
 * disagree about its shape.
 *
 * `factory()` is where NEU and ALT genuinely differ. ALT read a file from disk
 * and reported `size`, `mtime`, `has_db` and `config_files`; NEU keeps snapshots
 * as rows in `config_snapshots` and the factory row answers `{exists,
 * created_at, label}` (api/config_snapshots.py:107-113). Those four ALT fields
 * do not exist here, which is why the card was rebuilt around `created_at`
 * rather than ported — a port would have painted three em-dashes and a "0
 * Configs" that reads as a measurement.
 */
import { Injectable, inject } from '@angular/core';

import type { FactoryInfo, SnapshotRow } from './snapshots-api.service';
import { StudioApi } from './studio-api.service';
import type { ElementsPayload } from '../views/overview-cards';

/** `/api/health` — provider and model for display, never a secret. */
export interface HealthInfo {
  readonly status?: string;
  readonly provider?: string;
  readonly chat_model?: string;
  readonly embed_model?: string;
}

@Injectable({ providedIn: 'root' })
export class OverviewApi {
  private readonly api = inject(StudioApi);

  health(): Promise<HealthInfo> {
    return this.api.get<HealthInfo>('/health');
  }

  factory(): Promise<FactoryInfo> {
    return this.api.get<FactoryInfo>('/config/factory');
  }

  snapshots(): Promise<SnapshotRow[]> {
    return this.api.get<SnapshotRow[]>('/config/snapshots');
  }

  /**
   * The element lists, for the layer counts. A heavy payload (every persona
   * carries its prose), read once when the page opens — the alternative would be
   * a new endpoint, and six counts do not justify one.
   */
  elements(): Promise<ElementsPayload> {
    return this.api.get<ElementsPayload>('/config/elements');
  }
}
