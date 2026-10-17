/**
 * Was eine Map (`kind: 'map'`) an Bearbeitung kann — Einträge unter freiem
 * Schlüssel anlegen, entfernen, umbenennen. Aus `SchemaFieldComponent` gelöst
 * (Paket 6): die Komponente rendert und rekursiert, die Regeln einer Map
 * stehen hier.
 */
import { computed, signal } from '@angular/core';

import type { StudioLanguageService } from '../i18n/studio-language.service';
import { nextFreeKey } from './field-ids';
import type { ValuePath } from './form-value';
import type { FormEdit } from './schema-field.component';
import type { SchemaField } from './schema-to-fields';

interface MapEntry {
  readonly key: string;
  readonly value: unknown;
}

/** Was die Map von ihrem Feld liest — `SchemaFieldComponent` erfüllt es. */
export interface MapHost {
  readonly field: () => SchemaField;
  readonly path: () => ValuePath;
  readonly value: () => unknown;
  readonly edit: { emit(edit: FormEdit): void };
}

export class MapEntries {
  /** Refused rename, kept next to the row it belongs to. */
  readonly keyError = signal<{ readonly key: string; readonly message: string } | null>(null);

  readonly entries = computed<readonly MapEntry[]>(() => {
    const value = this.host.value();
    if (typeof value !== 'object' || value === null || Array.isArray(value)) return [];
    return Object.entries(value as Record<string, unknown>).map(([key, entry]) => ({
      key,
      value: entry,
    }));
  });

  constructor(
    private readonly host: MapHost,
    private readonly lang: Pick<StudioLanguageService, 't'>,
  ) {}

  addEntry(): void {
    const key = nextFreeKey(this.entries().map((entry) => entry.key));
    this.host.edit.emit({
      kind: 'set',
      path: [...this.host.path(), key],
      value: structuredClone(this.host.field().item?.blank ?? null),
    });
  }

  removeEntry(key: string): void {
    this.host.edit.emit({ kind: 'remove', path: [...this.host.path(), key] });
  }

  /**
   * `change`, not `input`: a map key is user data, and renaming per keystroke
   * would leave a trail of half-typed keys ("F", "FA", "FAQ") in the document.
   *
   * A refused rename must put the field back. `renameKeyAt` returns the SAME
   * document, so the signal never notifies and the input would keep showing a
   * name the document does not have — two rows claiming the same key, and a
   * later save reporting success for a rename that never happened.
   */
  renameEntry(from: string, event: Event): void {
    const input = event.target as HTMLInputElement;
    const to = input.value.trim();
    if (to === from) return;
    const taken = this.entries().some((entry) => entry.key === to);
    if (!to || taken) {
      input.value = from;
      this.keyError.set({
        key: from,
        message: taken
          ? this.lang.t('schemaField.keyTaken', { key: to })
          : this.lang.t('schemaField.emptyKey'),
      });
      return;
    }
    this.keyError.set(null);
    this.host.edit.emit({ kind: 'rename', path: this.host.path(), from, to });
  }
}
