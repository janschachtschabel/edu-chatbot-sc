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
import { SnapshotsApi, type FactoryInfo } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { StudioFormat } from '../i18n/studio-format.service';

@Component({
  selector: 'studio-factory-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './factory-panel.component.html',
  styleUrl: './factory-panel.component.scss',
})
export class FactoryPanelComponent {
  /** Zahlen und Datum in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly api = inject(SnapshotsApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly factory = new AsyncData<FactoryInfo>(() => this.api.factory(), this.t);
  readonly action = new ActionState(this.t);
  readonly file = signal<File | null>(null);

  /** Which confirmation is armed ('save' | 'restore' | 'upload'), or ''. */
  readonly armed = signal('');

  readonly exists = computed(() => this.factory.value()?.exists === true);
  readonly saved = computed(() => {
    const info = this.factory.value();
    return info?.exists ? this.fmt.dateTime(info.created_at ?? '') : '';
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
      return this.t('factory.saved');
    });
    if (ok) await this.factory.reload();
  }

  async restore(): Promise<void> {
    this.disarm();
    await this.action.run('restore', async () => {
      const { areas } = await this.api.restoreFactory();
      return this.lang.plural('factory.wasReset', areas);
    });
  }

  async download(): Promise<void> {
    await this.action.run('download', async () => {
      saveBlob(await this.api.downloadFactory(), 'factory.zip');
      return this.t('factory.downloaded');
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
      return this.t('factory.uploaded', { name: chosen.name });
    });
    if (ok) await this.factory.reload();
  }
}
