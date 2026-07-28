/**
 * The knowledge areas that exist in the database (9-4e), as one panel of the
 * "Wissen" page.
 *
 * Areas are NOT configuration: they come into being by ingesting a document and
 * disappear with the last one, so there is no area form and no "create area"
 * button — `05-knowledge/rag-config` next to this panel only *describes* areas
 * that exist. That is why this panel reads the DB and the panel below it edits
 * a config document.
 */
import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';

import { RagApi, describeRagError } from '../core/rag-api.service';
import type { CuratedPanelSection } from './curated-views';
import { RagDocumentsComponent } from './rag-documents.component';

@Component({
  selector: 'studio-rag-areas',
  imports: [RagDocumentsComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './rag-areas.component.html',
  styleUrl: './rag-areas.component.scss',
})
export class RagAreasComponent {
  private readonly rag = inject(RagApi);

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly areas = this.rag.areas;
  readonly loading = this.rag.areasLoading;
  readonly loadError = this.rag.areasError;

  /** The area whose documents are shown; '' = none picked yet. */
  readonly selected = signal('');
  /** The area a delete was requested for, awaiting the second click. */
  readonly pending = signal('');
  readonly deleting = signal(false);
  readonly deleteError = signal('');
  readonly status = signal('');

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  /** First open only — a reopen must not discard the chosen area. */
  private ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.rag.refreshAreas();
  }

  reload(): void {
    void this.rag.refreshAreas();
  }

  select(area: string): void {
    this.selected.set(this.selected() === area ? '' : area);
  }

  askDelete(area: string): void {
    this.deleteError.set('');
    this.pending.set(area);
  }

  cancelDelete(): void {
    this.pending.set('');
  }

  async confirmDelete(): Promise<void> {
    const area = this.pending();
    if (!area) return;
    this.deleting.set(true);
    this.deleteError.set('');
    try {
      await this.rag.deleteArea(area);
      this.pending.set('');
      if (this.selected() === area) this.selected.set('');
      this.status.set(`Bereich „${area}" gelöscht.`);
      await this.rag.refreshAreas();
    } catch (err) {
      this.deleteError.set(describeRagError(err));
    } finally {
      this.deleting.set(false);
    }
  }
}
