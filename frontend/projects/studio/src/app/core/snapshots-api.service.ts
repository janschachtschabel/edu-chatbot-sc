/**
 * Snapshots, factory baseline and full backup — `api/config_snapshots.py` (9-6).
 *
 * What a snapshot IS here decides what the view may say about it. NEU packs the
 * config areas into a ZIP row in `config_snapshots`; the `include_db` column is
 * carried through the schema but never set (`create_snapshot` calls
 * `save_snapshot` without it) because the Postgres dump is deferred to P10.
 * ALT's snapshots really did contain the database, which is why its UI had a
 * "Datenbank einschließen" checkbox, a "+ DB" badge and confirmations warning
 * that sessions, memory and RAG chunks would be replaced. None of that is true
 * here, so none of it is ported — see snapshots-panel.component.ts.
 *
 * Restore always merges: `_apply_config` writes every area found in the ZIP and
 * touches nothing else. ALT's wipe/merge question has no counterpart.
 */
import { Injectable, inject } from '@angular/core';

import { StudioApi } from './studio-api.service';

/** `/api/config/factory` — the "Werkseinstellungen" row, if one was ever saved. */
export interface FactoryInfo {
  readonly exists: boolean;
  readonly created_at?: string;
  readonly label?: string;
}

/**
 * One row of `/api/config/snapshots` (the factory row is excluded there).
 * `include_db` is in the payload and always false — see the module docstring.
 */
export interface SnapshotRow {
  readonly id: string;
  readonly created_at: string;
  readonly label: string;
  readonly include_db: boolean;
}

export interface SnapshotCreated {
  readonly id: string;
  readonly label: string;
}

/** Every restore answers with the number of config areas it wrote. */
export interface RestoreResult {
  readonly status: string;
  readonly areas: number;
}

export interface FactorySaved {
  readonly status: string;
  readonly id: string;
}

/**
 * `/api/config/seed` — der Auslieferungsstand, der im Abbild mitreist.
 *
 * Nicht zu verwechseln mit {@link FactoryInfo}: der Werksstand ist eine
 * Momentaufnahme des *gelebten* Standes, dieser hier der Stand, mit dem das
 * Abbild gebaut wurde. Die vier Listen tragen Bereichsnamen, damit das Panel
 * zeigen kann, *was* betroffen ist — bei `nur_in_db` ist das die Löschliste.
 */
export interface SeedStatus {
  readonly available: boolean;
  readonly area_count: number;
  readonly neu: readonly string[];
  readonly gleich: readonly string[];
  readonly abweichend: readonly string[];
  readonly nur_in_db: readonly string[];
}

/** `snapshot_id` ist nur bei `exact` gesetzt — dort ist er der Rückweg. */
export interface SeedApplied {
  readonly written: number;
  readonly deleted: number;
  readonly snapshot_id: string | null;
}

export type SeedMode = 'missing' | 'exact';

const SNAPSHOTS = '/config/snapshots';
const FACTORY = '/config/factory';
const SEED = '/config/seed';

@Injectable({ providedIn: 'root' })
export class SnapshotsApi {
  private readonly api = inject(StudioApi);

  list(): Promise<SnapshotRow[]> {
    return this.api.get<SnapshotRow[]>(SNAPSHOTS);
  }

  /** The label travels in the body (`SnapshotCreate`), not in the query. */
  create(label: string): Promise<SnapshotCreated> {
    return this.api.post<SnapshotCreated>(SNAPSHOTS, { label });
  }

  remove(id: string): Promise<{ status: string; id: string }> {
    return this.api.delete(`${SNAPSHOTS}/${encodeURIComponent(id)}`);
  }

  restore(id: string): Promise<RestoreResult> {
    return this.api.post<RestoreResult>(`${SNAPSHOTS}/${encodeURIComponent(id)}/restore`, null);
  }

  download(id: string): Promise<Blob> {
    return this.api.blob(`${SNAPSHOTS}/${encodeURIComponent(id)}/download`);
  }

  factory(): Promise<FactoryInfo> {
    return this.api.get<FactoryInfo>(FACTORY);
  }

  /** Packs the LIVE config as the new baseline; there is no "from this snapshot"
   *  variant (`save_factory` takes no parameter, unlike ALT's `?from_snapshot=`). */
  saveFactory(): Promise<FactorySaved> {
    return this.api.post<FactorySaved>(`${FACTORY}/save`, null);
  }

  restoreFactory(): Promise<RestoreResult> {
    return this.api.post<RestoreResult>(`${FACTORY}/restore`, null);
  }

  downloadFactory(): Promise<Blob> {
    return this.api.blob(`${FACTORY}/download`);
  }

  uploadFactory(file: File): Promise<FactorySaved> {
    return this.api.upload<FactorySaved>(`${FACTORY}/upload`, file);
  }

  /** Zählung des Auslieferungsstandes — ändert nichts. */
  seed(): Promise<SeedStatus> {
    return this.api.get<SeedStatus>(SEED);
  }

  /** `'exact'` überschreibt gepflegte Bereiche und löscht; das Backend legt
   *  dafür zuerst einen Schnappschuss an und verweigert den Lauf, wenn dafür
   *  kein Platz mehr ist. */
  applySeed(mode: SeedMode): Promise<SeedApplied> {
    return this.api.post<SeedApplied>(`${SEED}/apply`, { mode });
  }

  /** The live config as a ZIP — not a stored snapshot. */
  backup(): Promise<Blob> {
    return this.api.blob('/config/backup');
  }

  restoreBackup(file: File): Promise<RestoreResult> {
    return this.api.upload<RestoreResult>('/config/restore', file);
  }
}
