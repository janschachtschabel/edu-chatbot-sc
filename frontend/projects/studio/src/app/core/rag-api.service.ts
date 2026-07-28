/**
 * The RAG knowledge base as the studio sees it (9-4e): areas, their documents,
 * and the three ingest routes.
 *
 * The area list lives here rather than in a component because two panels of the
 * "Wissen" page need the same list: one lists the areas, the other ingests into
 * them and must make the counts update. A signal in one shared client is the
 * whole coordination — no events between siblings, no second fetch.
 *
 * ALT called `fetch` inline in the component for all of this, which is why its
 * upload never refreshed the counts and every failure was a silent `catch {}`.
 */
import { Injectable, computed, inject, signal } from '@angular/core';

import { StudioApiError } from './studio-api-error';
import { StudioApi } from './studio-api.service';

export interface RagArea {
  readonly area: string;
  readonly chunks: number;
  readonly documents: number;
}

export interface RagDoc {
  readonly title: string;
  readonly source: string;
  readonly chunks: number;
  readonly preview: string;
}

export interface RagChunk {
  readonly index: number;
  readonly content: string;
  readonly created_at: string;
}

export interface RagDocDetail {
  readonly area: string;
  readonly title: string;
  readonly source: string;
  readonly chunk_count: number;
  readonly total_chars: number;
  readonly chunks: readonly RagChunk[];
}

export interface IngestResult {
  readonly status: string;
  readonly area: string;
  readonly title: string;
  readonly chunks: number;
  readonly preview?: string;
}

@Injectable({ providedIn: 'root' })
export class RagApi {
  private readonly api = inject(StudioApi);

  private readonly areaList = signal<readonly RagArea[]>([]);
  private readonly areaError = signal('');
  private readonly areaLoading = signal(false);

  readonly areas = this.areaList.asReadonly();
  readonly areasError = this.areaError.asReadonly();
  readonly areasLoading = this.areaLoading.asReadonly();
  /** Area names for a datalist — ingest offers the existing ones without a fetch. */
  readonly areaNames = computed(() => this.areaList().map((a) => a.area));

  async refreshAreas(): Promise<void> {
    this.areaLoading.set(true);
    try {
      this.areaList.set(await this.api.get<RagArea[]>('/rag/areas'));
      this.areaError.set('');
    } catch (err) {
      // Keep the last good list: a failed refresh should not make the page
      // claim the knowledge base is empty.
      this.areaError.set(describeRagError(err));
    } finally {
      this.areaLoading.set(false);
    }
  }

  documents(area: string): Promise<RagDoc[]> {
    return this.api.get<RagDoc[]>(`/rag/area/${encodeURIComponent(area)}`);
  }

  document(area: string, title: string, source: string): Promise<RagDocDetail> {
    return this.api.get<RagDocDetail>(`/rag/area/${encodeURIComponent(area)}/doc`,
      { title, source });
  }

  deleteArea(area: string): Promise<unknown> {
    return this.api.delete(`/rag/area/${encodeURIComponent(area)}`);
  }

  deleteDocument(area: string, title: string, source: string): Promise<unknown> {
    return this.api.delete(`/rag/area/${encodeURIComponent(area)}/doc`, { title, source });
  }

  ingestFile(area: string, title: string, file: File): Promise<IngestResult> {
    const form = formOf(area, title);
    form.set('file', file);
    return this.api.post<IngestResult>('/rag/ingest/file', form);
  }

  ingestUrl(area: string, title: string, url: string): Promise<IngestResult> {
    const form = formOf(area, title);
    form.set('url', url);
    return this.api.post<IngestResult>('/rag/ingest/url', form);
  }

  ingestText(area: string, title: string, content: string): Promise<IngestResult> {
    const form = formOf(area, title);
    form.set('content', content);
    return this.api.post<IngestResult>('/rag/ingest/text', form);
  }
}

/** The endpoints read `area`/`title` from the form body, not the query string. */
function formOf(area: string, title: string): FormData {
  const form = new FormData();
  form.set('area', area);
  form.set('title', title);
  return form;
}

/**
 * A message an editor can act on.
 *
 * Reads `detail`, never `message`: the latter is the transport envelope
 * ("HTTP 400 /rag/ingest/text — …"), which names a route the editor never
 * typed and buries the sentence that actually explains the failure.
 */
export function describeRagError(err: unknown): string {
  if (!(err instanceof StudioApiError)) return 'Unerwarteter Fehler.';
  switch (err.status) {
    case 0:
      return 'Backend nicht erreichbar.';
    case 400:
      // markitdown's own message ("Fehler beim Konvertieren: …") or the SSRF
      // guard's — both name the actual obstacle.
      return err.detail || 'Die Datei oder Adresse konnte nicht gelesen werden.';
    case 413:
      return 'Die Datei ist größer als das Upload-Limit des Servers.';
    default:
      return err.detail || 'Unbekannter Fehler.';
  }
}
