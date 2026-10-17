/**
 * Die Seitenliste eines Liste│Editors (ST-3): Zähler, Suche, je Eintrag ein
 * Titel, die Wahl als `aria-current`.
 *
 * Darstellend: Suche, Filter und Wahl gehören dem Aufrufer. Zwei nutzen sie —
 * `object-list` (Einträge EINES Dokuments, Änderungen bleiben im Formular) und
 * `group-section` (die Dokumente eines Ordners, ST-3d: jede Wahl lädt ein
 * Dokument, Anlegen und Löschen gehen sofort zum Server). Was sie trennt, sind
 * die Knöpfe; die stehen als Inhalt darunter (`<ng-content>`). Was sie teilen,
 * steht hier einmal — vorher hätte es zwei Fassungen derselben Liste gegeben.
 */
import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';

export type EntryId = number | string;

export interface ListEntry {
  readonly id: EntryId;
  readonly title: string;
  /** Kurzer Zusatz hinter dem Titel, etwa die Kennung eines Dokuments. */
  readonly note?: string;
  /** Der Server hat an diesem Eintrag etwas abgewiesen (ST-2e). */
  readonly problem?: boolean;
}

/** Die Einträge, deren Titel oder Zusatz `query` enthält (ohne Groß/Klein). */
export function filterEntries<T extends ListEntry>(entries: readonly T[], query: string): readonly T[] {
  const q = query.trim().toLowerCase();
  if (!q) return entries;
  return entries.filter((entry) =>
    `${entry.title} ${entry.note ?? ''}`.toLowerCase().includes(q));
}

@Component({
  selector: 'studio-entry-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './entry-list.component.html',
  styleUrl: './entry-list.component.scss',
})
export class EntryListComponent {
  protected readonly t = inject(StudioLanguageService).t;

  /** Die SICHTBAREN Einträge — gefiltert hat der Aufrufer (`filterEntries`). */
  readonly entries = input.required<readonly ListEntry[]>();
  readonly current = input<EntryId | null>(null);
  readonly countText = input.required<string>();
  readonly query = input('');
  /** Die Beschriftung der Sammlung — für die Namen von Suche und Liste. */
  readonly label = input.required<string>();
  readonly baseId = input.required<string>();
  readonly emptyText = input.required<string>();

  readonly queryChange = output<string>();
  readonly pick = output<EntryId>();

  onSearch(event: Event): void {
    this.queryChange.emit((event.target as HTMLInputElement).value);
  }
}
