/**
 * Config endpoints of the studio-bff (9-3e).
 *
 * Two representations of the same area, deliberately both:
 *   - `data`/`saveData` — the document as JSON, what the schema form binds to;
 *   - `fileText`/`saveFileText` — the YAML/MD source, the escape hatch for
 *     everything no schema pins (13 free-form fields, plus any key a model does
 *     not know about at all).
 */
import { Injectable, inject } from '@angular/core';

import type { JsonSchema } from '../schema-form/json-schema';
import { StudioApi } from './studio-api.service';

export interface ConfigFileEntry {
  readonly path: string;
  readonly full_path: string;
  readonly name: string;
  readonly type: string;
}

export interface AreaDocument {
  readonly area: string;
  readonly data: Record<string, unknown>;
  /** `md` | `yaml` — decided by the store, never guessed from the shape. */
  readonly type: string;
  /**
   * The stored version (Paket 4, D5) — what a save names as `expected_version`.
   * `null`: no row yet, a save creates it. Absent: the server did not say, and
   * a save stays unconditional.
   */
  readonly version?: number | null;
}

export interface ConfigFileText {
  readonly path: string;
  readonly content: string;
  /** As `AreaDocument.version`. */
  readonly version?: number | null;
}

/** What a save asserts about the stored state (Paket 4, D5): 409 if untrue. */
export type SaveCondition =
  | { readonly expected_version: number }
  | { readonly create: true }
  | Record<string, never>;

/** The condition for a document loaded at `version` (see `AreaDocument`). */
export function saveCondition(version: number | null | undefined): SaveCondition {
  if (typeof version === 'number') return { expected_version: version };
  return version === null ? { create: true } : {};
}

@Injectable({ providedIn: 'root' })
export class ConfigApi {
  private readonly api = inject(StudioApi);

  listFiles(): Promise<ConfigFileEntry[]> {
    return this.api.get<ConfigFileEntry[]>('/config/files');
  }

  schema(area: string): Promise<JsonSchema> {
    return this.api.get<JsonSchema>(`/config/schema/${encodeAreaPath(area)}`);
  }

  data(area: string): Promise<AreaDocument> {
    return this.api.get<AreaDocument>(`/config/data/${encodeAreaPath(area)}`);
  }

  /** `data` is the WHOLE document — the endpoint replaces, it does not merge. */
  saveData(
    area: string, data: Record<string, unknown>, condition: SaveCondition = {},
  ): Promise<AreaDocument> {
    return this.api.put<AreaDocument>(
      `/config/data/${encodeAreaPath(area)}`, { data, ...condition });
  }

  fileText(path: string): Promise<ConfigFileText> {
    return this.api.get<ConfigFileText>('/config/file', { path });
  }

  saveFileText(
    path: string, content: string, condition: SaveCondition = {},
  ): Promise<{ status: string; version?: number }> {
    return this.api.put<{ status: string; version?: number }>(
      '/config/file', { path, content, ...condition });
  }

  /**
   * Ein Muster oder eine Persona anlegen oder — mit `source` — duplizieren
   * (Paket 6, S1). Den Schlüssel leitet der Server aus der Kennung ab; 409,
   * wenn es die Kennung oder den Schlüssel schon gibt.
   */
  createDocument(body: DocumentCreate): Promise<DocumentCreated> {
    return this.api.post<DocumentCreated>('/config/documents', body);
  }

  /** Ein Muster oder eine Persona löschen; feste Bereiche weist der Server ab (400).
   *  Mit `version` nur, wenn das Dokument noch so steht — sonst 409 wie beim Speichern. */
  deleteDocument(key: string, version: number | null = null): Promise<{ status: string; path: string }> {
    const params: Record<string, string> = { path: `${key}.md` };
    if (typeof version === 'number') params['expected_version'] = String(version);
    return this.api.delete<{ status: string; path: string }>('/config/file', params);
  }
}

export interface DocumentCreate {
  readonly group: string;
  readonly id: string;
  readonly label: string;
  /** Die Vorlage beim Duplizieren — ein Dokument desselben Ordners. */
  readonly source?: string;
}

export interface DocumentCreated {
  readonly status: string;
  readonly key: string;
  readonly version: number;
}

/** Per segment: the slashes are part of the route (`{area:path}`), the rest is not. */
function encodeAreaPath(area: string): string {
  return area.split('/').map(encodeURIComponent).join('/');
}
