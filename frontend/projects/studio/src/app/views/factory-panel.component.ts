/**
 * The factory baseline — the config a fresh installation starts from (9-6 / A6,
 * port of ALT `SnapshotsModal.tsx:331-393`).
 *
 * Four ways in and out of one stored row (`config_snapshots` id `factory`):
 * save the live config as the baseline, restore it, download it, upload one.
 *
 * ALT's card reported `size`, `mtime`, `has_db` and `config_files` from a file on
 * disk; `GET /config/factory` answers `{exists, created_at, label}` here, which
 * is why the card was rebuilt around those three rather than ported (A5 hit the
 * same wall on the front page). Its confirmations warned that the database, the
 * sessions, the memory, the quality logs and the RAG chunks would be replaced —
 * `_apply_config` writes config areas and nothing else, so that text would be a
 * false claim and the confirmation names the real consequence instead.
 *
 * ALT could also promote a chosen snapshot to factory (`?from_snapshot=`); NEU's
 * `save_factory` takes no parameter and always packs the live config, so that
 * button has no counterpart and is not offered.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ActionState } from '../core/action-state';
import { AsyncData } from '../core/async-data';
import { saveBlob } from '../core/download';
import { germanDateTime } from '../core/format';
import { SnapshotsApi, type FactoryInfo } from '../core/snapshots-api.service';

@Component({
  selector: 'studio-factory-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './factory-panel.component.html',
  styleUrl: './factory-panel.component.scss',
})
export class FactoryPanelComponent {
  private readonly api = inject(SnapshotsApi);

  readonly factory = new AsyncData<FactoryInfo>(() => this.api.factory());
  readonly action = new ActionState();
  readonly file = signal<File | null>(null);

  /** Which confirmation is armed ('save' | 'restore' | 'upload'), or ''. */
  readonly armed = signal('');

  readonly exists = computed(() => this.factory.value()?.exists === true);
  readonly saved = computed(() => {
    const info = this.factory.value();
    return info?.exists ? germanDateTime(info.created_at ?? '') : '';
  });
  readonly label = computed(() => this.factory.value()?.label ?? '');

  constructor() {
    void this.factory.reload();
  }

  arm(what: string): void {
    this.armed.set(what);
  }

  disarm(): void {
    this.armed.set('');
  }

  onFile(event: Event): void {
    this.file.set((event.target as HTMLInputElement).files?.[0] ?? null);
    this.disarm();
  }

  async save(): Promise<void> {
    this.disarm();
    const ok = await this.action.run('save', async () => {
      await this.api.saveFactory();
      return 'Werksstand aus dem aktuellen Live-Stand gesichert.';
    });
    if (ok) await this.factory.reload();
  }

  async restore(): Promise<void> {
    this.disarm();
    await this.action.run('restore', async () => {
      const { areas } = await this.api.restoreFactory();
      return `${areas} Konfigurationsbereiche auf den Werksstand zurückgesetzt.`;
    });
  }

  async download(): Promise<void> {
    await this.action.run('download', async () => {
      saveBlob(await this.api.downloadFactory(), 'factory.zip');
      return 'Werksstand heruntergeladen.';
    });
  }

  async upload(): Promise<void> {
    const chosen = this.file();
    if (!chosen) return;
    this.disarm();
    // The file stays chosen — see backup.component.ts for why clearing it alone
    // would put the picker and the button at odds.
    const ok = await this.action.run('upload', async () => {
      await this.api.uploadFactory(chosen);
      return `„${chosen.name}" als Werksstand übernommen.`;
    });
    if (ok) await this.factory.reload();
  }
}
