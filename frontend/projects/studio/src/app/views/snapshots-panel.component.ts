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
 * ALT's wipe/merge question is back as „ergänzend/exakt" (Paket 7, P5-5): exact
 * deletes the areas the snapshot does not carry — config areas only, never the
 * database ALT's wipe replaced. "als Factory übernehmen" per row still has no
 * counterpart (`save_factory` takes no `from_snapshot`; it packs the live config).
 *
 * ALT's three `confirm()` dialogs are inline confirmations, as in every other
 * writing view since 9-5a.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked,
} from '@angular/core';

import { ActionState } from '../core/action-state';
import { AsyncData } from '../core/async-data';
import { saveBlob } from '../core/download';
import { injectFocus } from '../core/inject-focus';
import { SnapshotsApi, type RestoreMode, type SnapshotRow } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { RestoreModeComponent, geloeschtZusatz } from './restore-mode.component';
import { StudioFormat } from '../i18n/studio-format.service';

/**
 * Mirrored from `services/snapshots.py` (`MAX_SNAPSHOTS = 50`). No endpoint
 * publishes it, and it only announces itself as a 400 once the limit is hit —
 * the same reason the load-test view mirrors its four caps.
 */
const MAX_SNAPSHOTS = 50;

@Component({
  selector: 'studio-snapshots-panel',
  imports: [AsyncStateComponent, RestoreModeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './snapshots-panel.component.html',
  styleUrl: './snapshots-panel.component.scss',
})
export class SnapshotsPanelComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly api = inject(SnapshotsApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;

  readonly snapshots = new AsyncData<SnapshotRow[]>(() => this.api.list(), this.t);
  readonly action = new ActionState(this.t);
  /** Paket 9 (V8): Rückfrage → „Abbrechen“, danach zurück auf den Knopf der Zeile. */
  private readonly focus = injectFocus();
  readonly label = signal('');

  /** `${kind}:${id}` of the confirmation that is armed, or ''. */
  private readonly armedKey = signal('');
  /** Paket 7 (P5-5): jede Rückfrage beginnt bei „ergänzend". */
  readonly mode = signal<RestoreMode>('merge');

  readonly limit = MAX_SNAPSHOTS;
  readonly rows = computed(() => this.snapshots.value() ?? []);
  readonly count = computed(() => this.rows().length);

  constructor() {
    void this.snapshots.reload();
    // Legt der Server nebenbei einen Snapshot an (exaktes Wiederherstellen, auch
    // aus einem Nachbar-Panel), steht er ohne „Aktualisieren" in der Liste.
    const anfang = this.api.stand();
    effect(() => {
      if (this.api.stand() !== anfang) untracked(() => void this.snapshots.reload());
    });
  }

  arm(kind: 'restore' | 'delete', id: string): void {
    this.mode.set('merge');
    this.armedKey.set(`${kind}:${id}`);
    this.focus(`${row(id)} .sp-cancel`);
  }

  /** „Abbrechen“: zurück auf den Knopf, der die Rückfrage öffnete. */
  disarm(kind: 'restore' | 'delete', id: string): void {
    this.armedKey.set('');
    this.focus(`${row(id)} .sp-${kind}`);
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
      return this.t('snapshots.created', { name: snap.label || snap.id });
    });
    if (!ok) return;
    this.label.set('');
    await this.snapshots.reload();
  }

  async restore(snap: SnapshotRow): Promise<void> {
    this.armedKey.set('');
    await this.action.run(`restore:${snap.id}`, async () => {
      const r = await this.api.restore(snap.id, this.mode());
      // Derselbe Satz wie beim Voll-Backup — beide schreiben Bereiche aus einer
      // ZIP, und zwei Einträge könnten voneinander abdriften.
      return this.lang.plural('backup.areasRestored', r.areas, { name: this.name(snap) })
        + geloeschtZusatz(this.lang, r);
    });
    this.focus(`${row(snap.id)} .sp-restore`, '#sp-title');
  }

  async remove(snap: SnapshotRow): Promise<void> {
    this.armedKey.set('');
    const ok = await this.action.run(`delete:${snap.id}`, async () => {
      await this.api.remove(snap.id);
      return this.t('snapshots.deleted', { name: this.name(snap) });
    });
    if (ok) await this.snapshots.reload();
    // Nach dem Löschen fehlt die Zeile — dann die Überschrift.
    this.focus(`${row(snap.id)} .sp-delete`, '#sp-title');
  }

  async download(row: SnapshotRow): Promise<void> {
    await this.action.run(`download:${row.id}`, async () => {
      saveBlob(await this.api.download(row.id), `${row.id}.zip`);
      return this.t('snapshots.downloaded', { name: this.name(row) });
    });
  }

  /** The label an editor typed, or the generated id when they typed none. */
  name(row: SnapshotRow): string {
    return row.label.trim() || row.id;
  }

  when(iso: string): string {
    return this.fmt.dateTime(iso);
  }
}

/** Die Zeile eines Snapshots. Kennungen sind `snap-` und zwölf Hex-Zeichen
 *  (`services/snapshots.create_snapshot`), im Selektor also unbedenklich. */
function row(id: string): string {
  return `[data-row="${id}"]`;
}
