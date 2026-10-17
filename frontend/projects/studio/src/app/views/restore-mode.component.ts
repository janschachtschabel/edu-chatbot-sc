/**
 * Die Wahl beim Wiederherstellen (Paket 7, P5-5): was mit Bereichen geschieht,
 * die nicht in der Sicherung liegen.
 *
 * „Ergänzend" ist die Vorgabe und lässt sie stehen; „Exakt" löscht sie — etwa
 * ein Muster, das seitdem angelegt wurde. Das Backend sichert den Stand davor
 * als Snapshot und verweigert den Lauf, wenn dafür kein Platz ist. Die Folge
 * steht deshalb schon in der Beschriftung, bevor jemand wählt, nicht erst in
 * einer Warnung danach. Eine Gruppe für drei Rückfragen (Voll-Backup, Snapshot,
 * Werksstand), damit Text und Folge nicht auseinanderlaufen.
 */
import { ChangeDetectionStrategy, Component, inject, model } from '@angular/core';

import type { RestoreMode, RestoreResult } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Drei Panels können zugleich eine Rückfrage offen haben, und Radioknöpfe mit
 *  gleichem Namen schalten einander ab — jede Gruppe bekommt ihren eigenen. */
let gruppen = 0;

@Component({
  selector: 'studio-restore-mode',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './restore-mode.component.html',
  styleUrl: './restore-mode.component.scss',
})
export class RestoreModeComponent {
  protected readonly t = inject(StudioLanguageService).t;
  readonly mode = model<RestoreMode>('merge');
  protected readonly name = `restore-mode-${++gruppen}`;
}

/** Der Satz für die Erfolgsmeldung, wenn „Exakt" etwas gelöscht hat — sonst
 *  leer. Mit führendem Leerzeichen, damit er an jeden Satz passt. */
export function geloeschtZusatz(lang: StudioLanguageService, r: RestoreResult): string {
  return r.deleted > 0 && r.snapshot_id
    ? ' ' + lang.plural('restoreMode.deleted', r.deleted, { id: r.snapshot_id })
    : '';
}
