/**
 * Snapshot, Backup und Einspielen in der Kopfzeile (ST-9) — wieder von jeder
 * Seite aus erreichbar, wie im ALT.
 *
 * Seit 9-6 lagen die drei nur auf der Seite „Sicherung". Das war aufgeräumt,
 * kostete aber den schnellen Griff vor einer Änderung: erst die Seite wechseln,
 * und auf einer Formularseite mit offenen Änderungen hält der Verlassen-Schutz
 * dabei an. Snapshot und Backup handeln deshalb hier sofort und ohne Seitenwechsel
 * — beide ändern nichts. Einspielen ERSETZT die ganze Konfiguration: dafür
 * braucht es Datei-Wahl und Rückfrage, und die stehen auf der Sicherungs-Seite;
 * die Kopfzeile führt nur dorthin, statt einen zweiten Einspiel-Weg zu bauen.
 *
 * Die Meldung zur letzten Aktion verschwindet beim Seitenwechsel: die Kopfzeile
 * bleibt stehen, eine Meldung zu „Snapshot angelegt" gehört nicht auf die
 * nächste Seite. Den Wechsel meldet die Shell (`dismiss()` aus
 * `onViewActivated`) — das Frontend hält bewusst keine Router-Abos.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ActionState } from '../core/action-state';
import { saveBlob } from '../core/download';
import { SnapshotsApi } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-backup-tools',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './backup-tools.component.html',
  styleUrl: './backup-tools.component.scss',
})
export class BackupToolsComponent {
  private readonly api = inject(SnapshotsApi);
  protected readonly t = inject(StudioLanguageService).t;

  readonly action = new ActionState(this.t);
  /** Nach einem Snapshot: der Weg zur Liste steht neben der Meldung. */
  readonly snapshotMade = signal(false);

  async snapshot(): Promise<void> {
    const ok = await this.action.run('snapshot', async () => {
      // Ohne Namen: die Liste zeigt dann Kennung und Zeit — mehr weiß die
      // Kopfzeile nicht, und ein Eingabefeld hier wäre der Umweg, den sie spart.
      const snap = await this.api.create('');
      return this.t('snapshots.created', { name: snap.label || snap.id });
    });
    this.snapshotMade.set(ok);
  }

  async backup(): Promise<void> {
    this.snapshotMade.set(false);
    await this.action.run('backup', async () => {
      saveBlob(await this.api.backup(), 'boerdi-config-backup.zip');
      return this.t('backup.downloaded');
    });
  }

  /** Die Meldung der letzten Aktion wegräumen — die Shell ruft das beim Seitenwechsel. */
  dismiss(): void {
    this.action.dismiss();
    this.snapshotMade.set(false);
  }
}
