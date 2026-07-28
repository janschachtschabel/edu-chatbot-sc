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
}

export interface ConfigFileText {
  readonly path: string;
  readonly content: string;
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
  saveData(area: string, data: Record<string, unknown>): Promise<AreaDocument> {
    return this.api.put<AreaDocument>(`/config/data/${encodeAreaPath(area)}`, { data });
  }

  fileText(path: string): Promise<ConfigFileText> {
    return this.api.get<ConfigFileText>('/config/file', { path });
  }

  saveFileText(path: string, content: string): Promise<{ status: string }> {
    return this.api.put<{ status: string }>('/config/file', { path, content });
  }
}

/** Per segment: the slashes are part of the route (`{area:path}`), the rest is not. */
function encodeAreaPath(area: string): string {
  return area.split('/').map(encodeURIComponent).join('/');
}
