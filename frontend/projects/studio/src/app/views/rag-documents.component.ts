/**
 * The documents of ONE knowledge area (9-4e) — list, full text, delete.
 *
 * A document is addressed by the pair `(title, source)`, never by title alone:
 * the backend groups on that pair, so the same title ingested from a file and
 * from a URL are two documents and deleting by title would take both.
 *
 * The full text opens inline instead of in ALT's overlay. A chunk list is long
 * and is exactly what an editor reads *while* comparing it to the list, and an
 * overlay would need its own focus trap and its own scroll container to do the
 * same job worse at 320 px.
 */
import {
  ChangeDetectionStrategy, Component, effect, inject, input, output, signal, untracked,
} from '@angular/core';

import { RagApi, type RagChunk, type RagDoc, describeRagError } from '../core/rag-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Which document is expanded — the pair, because the title is not unique. */
interface OpenDoc {
  readonly title: string;
  readonly source: string;
}

@Component({
  selector: 'studio-rag-documents',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './rag-documents.component.html',
  styleUrl: './rag-documents.component.scss',
})
export class RagDocumentsComponent {
  private readonly rag = inject(RagApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;

  readonly area = input.required<string>();
  /** Something was deleted here — the area counts above are now stale. */
  readonly changed = output<void>();

  readonly docs = signal<readonly RagDoc[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal('');

  readonly pending = signal<OpenDoc | null>(null);
  readonly deleting = signal(false);
  readonly deleteError = signal('');

  readonly openDoc = signal<OpenDoc | null>(null);
  readonly chunks = signal<readonly RagChunk[]>([]);
  readonly chunksLoading = signal(false);
  readonly chunksError = signal('');

  /** Guards against a slower response for a PREVIOUS area overwriting this one. */
  private generation = 0;

  constructor() {
    effect(() => {
      const area = this.area();
      untracked(() => void this.load(area));
    });
  }

  private async load(area: string): Promise<void> {
    const generation = ++this.generation;
    this.loading.set(true);
    this.loadError.set('');
    this.openDoc.set(null);
    this.pending.set(null);
    try {
      const docs = await this.rag.documents(area);
      if (generation !== this.generation) return;
      this.docs.set(docs);
    } catch (err) {
      if (generation !== this.generation) return;
      this.loadError.set(describeRagError(err, this.t));
    } finally {
      if (generation === this.generation) this.loading.set(false);
    }
  }

  /** Track key for the list: the pair, since the title alone repeats. */
  docKey(doc: RagDoc): string {
    return JSON.stringify([doc.title, doc.source]);
  }

  isOpen(doc: RagDoc): boolean {
    return same(this.openDoc(), doc);
  }

  isPending(doc: RagDoc): boolean {
    return same(this.pending(), doc);
  }

  async show(doc: RagDoc): Promise<void> {
    if (this.isOpen(doc)) {
      this.openDoc.set(null);
      return;
    }
    const generation = this.generation;
    this.openDoc.set({ title: doc.title, source: doc.source });
    this.chunks.set([]);
    this.chunksError.set('');
    this.chunksLoading.set(true);
    try {
      const detail = await this.rag.document(this.area(), doc.title, doc.source);
      if (generation !== this.generation) return;
      this.chunks.set(detail.chunks);
    } catch (err) {
      if (generation !== this.generation) return;
      this.chunksError.set(describeRagError(err, this.t));
    } finally {
      if (generation === this.generation) this.chunksLoading.set(false);
    }
  }

  askDelete(doc: RagDoc): void {
    this.deleteError.set('');
    this.pending.set({ title: doc.title, source: doc.source });
  }

  cancelDelete(): void {
    this.pending.set(null);
  }

  async confirmDelete(): Promise<void> {
    const doc = this.pending();
    if (!doc) return;
    this.deleting.set(true);
    this.deleteError.set('');
    try {
      await this.rag.deleteDocument(this.area(), doc.title, doc.source);
      this.pending.set(null);
      await this.load(this.area());
      this.changed.emit();
    } catch (err) {
      this.deleteError.set(describeRagError(err, this.t));
    } finally {
      this.deleting.set(false);
    }
  }
}

function same(a: OpenDoc | null, b: RagDoc): boolean {
  return a !== null && a.title === b.title && a.source === b.source;
}
