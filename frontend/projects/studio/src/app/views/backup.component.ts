/**
 * "Sicherung" — snapshots, factory baseline and the full config ZIP (9-6 / A6).
 *
 * **A view, not ALT's header modal.** ALT reached all of this through three
 * header buttons and a `<div>` overlay (page.tsx:353-413 + SnapshotsModal.tsx).
 * A faithful modal here would mean `<dialog>.showModal()`, and jsdom 29.1.1 —
 * the studio's test environment — implements `HTMLDialogElement` with the `open`
 * property ALONE: no `showModal`, no `close` (probed before deciding). The
 * modal's most valuable properties are exactly the ones a stub cannot verify
 * (focus trap, Esc, inert background), so the choice was between an untestable
 * modal and a hand-rolled focus trap. Both lose to a route: the studio is a
 * router app, every other surface is a view, and this one is now deep-linkable
 * and reachable from the sidebar. The placement is UI idiom, not contract — the
 * same category as `<div onClick>` → `<button>` and `confirm()` → inline
 * confirmation, both already established in this port.
 *
 * The hull owns the full backup (download the live config, restore a ZIP);
 * snapshots and the factory baseline are their own panels because each has its
 * own reads and its own reason to change.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { ActionState } from '../core/action-state';
import { saveBlob } from '../core/download';
import { SnapshotsApi } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { FactoryPanelComponent } from './factory-panel.component';
import { SnapshotsPanelComponent } from './snapshots-panel.component';

@Component({
  selector: 'studio-backup',
  imports: [SnapshotsPanelComponent, FactoryPanelComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './backup.component.html',
  styleUrl: './backup.component.scss',
})
export class BackupComponent {
  private readonly api = inject(SnapshotsApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly action = new ActionState(this.t);
  readonly file = signal<File | null>(null);
  readonly armed = signal(false);

  onFile(event: Event): void {
    this.file.set((event.target as HTMLInputElement).files?.[0] ?? null);
    this.armed.set(false);
  }

  arm(): void {
    this.armed.set(true);
  }

  disarm(): void {
    this.armed.set(false);
  }

  async download(): Promise<void> {
    await this.action.run('backup', async () => {
      saveBlob(await this.api.backup(), 'boerdi-config-backup.zip');
      return this.t('backup.downloaded');
    });
  }

  async restore(): Promise<void> {
    const chosen = this.file();
    if (!chosen) return;
    this.armed.set(false);
    // The chosen file stays chosen afterwards. Clearing the signal alone would
    // leave the native picker showing a file name beside a button that refuses
    // to use it, and clearing the input element too takes a DOM reach-around for
    // no gain — applying the same ZIP twice writes the same areas.
    await this.action.run('restore', async () => {
      const { areas } = await this.api.restoreBackup(chosen);
      return this.lang.plural('backup.areasRestored', areas, { name: chosen.name });
    });
  }
}
