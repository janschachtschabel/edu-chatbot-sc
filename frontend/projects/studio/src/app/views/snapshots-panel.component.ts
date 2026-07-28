/**
 * Server-side snapshots of the configuration (9-6 / A6, port of ALT
 * `SnapshotsModal.tsx`).
 *
 * **What a snapshot contains decides what this panel may promise.** ALT's
 * snapshots really carried the SQLite file, so its UI had a "Datenbank
 * einschließen" checkbox, a "+ DB" badge per row and confirmations warning that
 * sessions, memory, quality logs and RAG chunks would be replaced. In NEU a
 * snapshot is the config areas and nothing else (`services/snapshots.py`:
 * `create_snapshot` never sets `include_db`, the Postgres dump is P10). All
 * three would therefore be false claims here and are not ported — the same class
 * as the factory card in A5 and the tight-races counter in C2.
 *
 * Two more ALT interactions have no counterpart: the wipe/merge question (NEU's
 * `_apply_config` always merges — it writes what is in the ZIP and touches
 * nothing else) and "als Factory übernehmen" per row (`save_factory` takes no
 * `from_snapshot`; it always packs the live config).
 *
 * ALT's three `confirm()` dialogs are inline confirmations, as in every other
 * writing view since 9-5a.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';

import { ActionState } from '../core/action-state';
import { AsyncData } from '../core/async-data';
import { saveBlob } from '../core/download';
import { germanDateTime } from '../core/format';
import { SnapshotsApi, type SnapshotRow } from '../core/snapshots-api.service';
import { AsyncStateComponent } from './async-state.component';

/**
 * Mirrored from `services/snapshots.py` (`MAX_SNAPSHOTS = 50`). No endpoint
 * publishes it, and it only announces itself as a 400 once the limit is hit —
 * the same reason the load-test view mirrors its four caps.
 */
const MAX_SNAPSHOTS = 50;

@Component({
  selector: 'studio-snapshots-panel',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './snapshots-panel.component.html',
  styleUrl: './snapshots-panel.component.scss',
})
export class SnapshotsPanelComponent {
  private readonly api = inject(SnapshotsApi);

  readonly snapshots = new AsyncData<SnapshotRow[]>(() => this.api.list());
  readonly action = new ActionState();
  readonly label = signal('');

  /** `${kind}:${id}` of the confirmation that is armed, or ''. */
  private readonly armedKey = signal('');

  readonly limit = MAX_SNAPSHOTS;
  readonly rows = computed(() => this.snapshots.value() ?? []);
  readonly count = computed(() => this.rows().length);

  constructor() {
    void this.snapshots.reload();
  }

  arm(kind: string, id: string): void {
    this.armedKey.set(`${kind}:${id}`);
  }

  disarm(): void {
    this.armedKey.set('');
  }

  isArmed(kind: string, id: string): boolean {
    return this.armedKey() === `${kind}:${id}`;
  }

  onLabel(event: Event): void {
    this.label.set((event.target as HTMLInputElement).value);
  }

  async create(): Promise<void> {
    const ok = await this.action.run('create', async () => {
      const snap = await this.api.create(this.label().trim());
      return `Snapshot „${snap.label || snap.id}" angelegt.`;
    });
    if (!ok) return;
    this.label.set('');
    await this.snapshots.reload();
  }

  async restore(row: SnapshotRow): Promise<void> {
    this.disarm();
    await this.action.run(`restore:${row.id}`, async () => {
      const { areas } = await this.api.restore(row.id);
      return `${areas} Konfigurationsbereiche aus „${this.name(row)}" eingespielt.`;
    });
  }

  async remove(row: SnapshotRow): Promise<void> {
    this.disarm();
    const ok = await this.action.run(`delete:${row.id}`, async () => {
      await this.api.remove(row.id);
      return `Snapshot „${this.name(row)}" gelöscht.`;
    });
    if (ok) await this.snapshots.reload();
  }

  async download(row: SnapshotRow): Promise<void> {
    await this.action.run(`download:${row.id}`, async () => {
      saveBlob(await this.api.download(row.id), `${row.id}.zip`);
      return `„${this.name(row)}" heruntergeladen.`;
    });
  }

  /** The label an editor typed, or the generated id when they typed none. */
  name(row: SnapshotRow): string {
    return row.label.trim() || row.id;
  }

  when(iso: string): string {
    return germanDateTime(iso);
  }
}
