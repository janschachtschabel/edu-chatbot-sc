/**
 * Load / edit / save state for ONE config-area document (9-4a).
 *
 * Extracted from the area-editor route so the curated views of 9-4 can put
 * several areas on one page without re-implementing the parts that were hard
 * to get right in 9-3:
 *
 *   - the whole document is edited and PUT back whole — a value rebuilt from
 *     the rendered fields deletes the 357 config paths no schema pins;
 *   - every request carries a generation, so a slow answer cannot install
 *     area A's document under area B and then replace B with it on save;
 *   - a field holding unparseable input blocks the save instead of silently
 *     writing the last value that did parse.
 *
 * One instance per area. Not injectable: it holds the state of a single
 * editor, and two editors on one page must not share it.
 */
import { computed, signal } from '@angular/core';

import type { ConfigApi } from '../core/config-api.service';
import { StudioApiError } from '../core/studio-api-error';
import type { JsonSchema } from './json-schema';

export class AreaDocEditor {
  constructor(private readonly config: ConfigApi) {}

  readonly schema = signal<JsonSchema | null>(null);
  readonly doc = signal<Record<string, unknown>>({});
  /** `md` | `yaml` — from the store, never guessed from the document shape. */
  readonly docType = signal('yaml');

  readonly loading = signal(true);
  readonly loadError = signal('');
  readonly saving = signal(false);
  readonly saveError = signal('');
  /** Announced in a live region; cleared as soon as anything is edited again. */
  readonly status = signal('');
  /** Form fields whose input cannot be parsed — a save would drop them. */
  readonly fieldErrors = signal<readonly string[]>([]);

  private readonly savedDoc = signal('{}');
  readonly dirty = computed(() => JSON.stringify(this.doc()) !== this.savedDoc());
  readonly blocked = computed(() => this.fieldErrors().length > 0);

  private generation = 0;

  /** Start a request and get the token that decides whether it may install. */
  nextGeneration(): number {
    return ++this.generation;
  }

  /** The newest token. A follow-up request that must NOT outrank a pending one
   *  — reloading the raw text for the document just installed — uses this
   *  instead of starting a new generation. */
  get currentGeneration(): number {
    return this.generation;
  }

  isCurrent(generation: number): boolean {
    return generation === this.generation;
  }

  /** `true` when this call installed the document (i.e. was not overtaken). */
  async load(area: string): Promise<boolean> {
    const generation = this.nextGeneration();
    this.loading.set(true);
    this.loadError.set('');
    this.status.set('');
    this.saveError.set('');
    this.fieldErrors.set([]);
    try {
      const [schema, document] = await Promise.all([
        this.config.schema(area),
        this.config.data(area),
      ]);
      if (!this.isCurrent(generation)) return false;
      this.schema.set(schema);
      this.adopt(document.data);
      this.docType.set(document.type);
      return true;
    } catch (err) {
      if (this.isCurrent(generation)) this.loadError.set(describeAreaError(err));
      return false;
    } finally {
      if (this.isCurrent(generation)) this.loading.set(false);
    }
  }

  /** `true` when the document was written and the clean state moved with it. */
  async save(area: string): Promise<boolean> {
    if (this.saving() || !this.dirty()) return false;
    if (this.blocked()) {
      this.saveError.set(
        `Nicht gespeichert: ${this.fieldErrors().join(', ')} enthält kein gültiges JSON.`,
      );
      return false;
    }
    const generation = this.nextGeneration();
    this.saving.set(true);
    this.saveError.set('');
    this.status.set('');
    try {
      const saved = await this.config.saveData(area, this.doc());
      if (!this.isCurrent(generation)) return false;
      this.adopt(saved.data);
      this.docType.set(saved.type);
      this.status.set('Gespeichert.');
      return true;
    } catch (err) {
      // the edit stays in `doc` — clearing it would lose what was typed
      if (this.isCurrent(generation)) this.saveError.set(describeAreaError(err));
      return false;
    } finally {
      if (this.isCurrent(generation)) this.saving.set(false);
    }
  }

  setDoc(next: Record<string, unknown>): void {
    this.doc.set(next);
    this.status.set('');
    this.saveError.set('');
  }

  setFieldErrors(fields: readonly string[]): void {
    this.fieldErrors.set(fields);
    if (fields.length === 0) this.saveError.set('');
  }

  discard(): void {
    this.doc.set(JSON.parse(this.savedDoc()) as Record<string, unknown>);
    this.saveError.set('');
    this.status.set('Änderungen verworfen.');
  }

  /** Install a document as the new clean baseline. */
  adopt(data: Record<string, unknown>): void {
    this.doc.set(data);
    this.savedDoc.set(JSON.stringify(data));
  }
}

/** Turn an API failure into something an editor can act on. */
export function describeAreaError(err: unknown): string {
  if (!(err instanceof StudioApiError)) return 'Unerwarteter Fehler.';
  switch (err.status) {
    case 0:
      return 'Backend nicht erreichbar.';
    case 400:
      // The backend sends two different 400s here: a malformed area key and a
      // document it could not parse. Reporting a YAML problem for a bad key
      // sends the editor looking in the wrong place.
      return err.detail.startsWith('Invalid path')
        ? 'Der Bereichsschlüssel ist ungültig.'
        : err.detail;
    case 404:
      return 'Diesen Konfigurationsbereich gibt es nicht.';
    case 422:
      return `Die Eingabe passt nicht zum Bereichsmodell: ${err.detail}`;
    default:
      return `Fehler ${err.status}: ${err.detail}`;
  }
}
