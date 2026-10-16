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
import { injectFocus } from '../core/inject-focus';
import { SnapshotsApi, type RestoreMode } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { FactoryPanelComponent } from './factory-panel.component';
import { FassungenPanelComponent } from './fassungen-panel.component';
import { RestoreModeComponent, geloeschtZusatz } from './restore-mode.component';
import { SeedPanelComponent } from './seed-panel.component';
import { SnapshotsPanelComponent } from './snapshots-panel.component';

@Component({
  selector: 'studio-backup',
  imports: [
    FassungenPanelComponent, SnapshotsPanelComponent, FactoryPanelComponent, SeedPanelComponent,
    RestoreModeComponent,
  ],
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
  /** Paket 7 (P5-5): jede Rückfrage beginnt bei „ergänzend" — „exakt" löscht
   *  und wird deshalb jedes Mal ausdrücklich gewählt, nie vom letzten Mal geerbt. */
  readonly mode = signal<RestoreMode>('merge');
  /** Paket 9 (V8): Rückfrage → „Abbrechen“, danach zurück auf „Backup einspielen“. */
  private readonly focus = injectFocus();

  onFile(event: Event): void {
    this.file.set((event.target as HTMLInputElement).files?.[0] ?? null);
    this.armed.set(false);
  }

  arm(): void {
    this.mode.set('merge');
    this.armed.set(true);
    this.focus('.bk-cancel');
  }

  disarm(): void {
    this.armed.set(false);
    this.focus('.bk-restore');
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
      const r = await this.api.restoreBackup(chosen, this.mode());
      return this.lang.plural('backup.areasRestored', r.areas, { name: chosen.name })
        + geloeschtZusatz(this.lang, r);
    });
    this.focus('.bk-restore');
  }
}
