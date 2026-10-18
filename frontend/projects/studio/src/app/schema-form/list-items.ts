/**
 * Was eine Liste (`kind: 'list'`) an Bearbeitung kann — Einträge hinzufügen und
 * entfernen, Katalog-Namen als Chips (ST-2g), der hervorgehobene Eintrag
 * (ST-2i). Aus `SchemaFieldComponent` gelöst (Paket 6): die Komponente rendert
 * und rekursiert, die Regeln einer Liste stehen hier.
 *
 * Wie das Feld besitzt auch sie den Wert nicht: jede Änderung geht als
 * `FormEdit` über das Feld hinaus.
 */
import { computed, signal } from '@angular/core';

import type { StudioLanguageService } from '../i18n/studio-language.service';
import type { ValuePath } from './form-value';
import type { DocumentEdit, FormEdit } from './schema-field.component';
import type { SchemaField } from './schema-to-fields';

/** Was die Liste von ihrem Feld liest — `SchemaFieldComponent` erfüllt es. */
export interface ListHost {
  readonly field: () => SchemaField;
  readonly path: () => ValuePath;
  readonly value: () => unknown;
  /** Der Wert des Nachbarfelds, das eine Zeile hervorhebt (ST-2i). */
  readonly markerValue: () => unknown;
  readonly groupLabel: () => string;
  readonly edit: { emit(edit: FormEdit): void };
}

export class ListItems {
  readonly items = computed<readonly unknown[]>(() => {
    const value = this.host.value();
    return Array.isArray(value) ? value : [];
  });

  /** Werkzeuge, Wissensbereiche … — je Wert ein Chip statt je Eintrag ein Feld. */
  readonly chipList = computed(() => {
    const field = this.host.field();
    return field.kind === 'list' && field.item?.kind === 'text' && !!field.item.catalog
      && !field.marker;
  });
  /** Ein doppelter Wert, beim Eingabefeld gemeldet statt still verworfen. */
  readonly chipError = signal('');

  /** Der Name des hervorhebenden Nachbarfelds („Tour-Chip") für die Radios. */
  readonly markerLabel = computed(() => {
    const key = this.host.field().markerTextKey;
    return key && this.lang.has(`${key}.label`)
      ? this.lang.t(`${key}.label`)
      : (this.host.field().marker ?? '');
  });

  constructor(
    private readonly host: ListHost,
    private readonly lang: Pick<StudioLanguageService, 't' | 'has'>,
  ) {}

  addItem(): void {
    this.setValue([...this.items(), structuredClone(this.host.field().item?.blank ?? null)]);
  }

  removeItem(index: number): void {
    const remove: DocumentEdit = { kind: 'remove', path: [...this.host.path(), index] };
    const unmark = this.isMarked(index) ? this.markEdit('') : null;
    // sonst zeigte der Tour-Chip auf eine Zeile, die es nicht mehr gibt
    this.host.edit.emit(unmark ? { kind: 'batch', edits: [remove, unmark] } : remove);
  }

  addChip(input: HTMLInputElement): void {
    const value = input.value.trim();
    if (!value) return;
    if (this.items().includes(value)) {
      this.chipError.set(
        this.lang.t('schemaField.chipTaken', { value, group: this.host.groupLabel() }),
      );
      return;
    }
    this.chipError.set('');
    this.setValue([...this.items(), value]);
    input.value = '';
  }

  // ── ST-2i: EIN Eintrag der Liste ist hervorgehoben (`x-marker`) ──────

  /** Paket 15: ein gespeicherter Marker-Wert, der zu keiner Zeile passt (sonst `''`). */
  readonly markerVerwaist = computed(() => {
    const wert = this.host.markerValue();
    if (!this.host.field().marker || typeof wert !== 'string' || !wert) return '';
    return this.items().includes(wert) ? '' : wert;
  });

  /** Die Zeile trägt den Wert, den das Nachbarfeld hervorhebt. */
  isMarked(index: number): boolean {
    return !!this.host.field().marker && this.items()[index] === this.host.markerValue();
  }

  /** Schreibt den hervorgehobenen Wert ins Nachbarfeld — `''` hebt keinen hervor. */
  mark(value: unknown): void {
    const edit = this.markEdit(value);
    if (edit) this.host.edit.emit(edit);
  }

  /**
   * Eine Zeile wurde bearbeitet. War sie die hervorgehobene, wandert der Marker
   * mit — sonst verlöre eine Umbenennung des Tour-Chips still die Web-Tour.
   * `items()` trägt hier noch den ALTEN Wert: das Dokument ist noch nicht neu.
   */
  onItemEdit(index: number, edit: FormEdit): void {
    const follow = this.isMarked(index) && edit.kind === 'set'
      && edit.path.length === this.host.path().length + 1
      ? this.markEdit(edit.value)
      : null;
    this.host.edit.emit(
      follow && edit.kind === 'set' ? { kind: 'batch', edits: [edit, follow] } : edit,
    );
  }

  private markEdit(value: unknown): DocumentEdit | null {
    const marker = this.host.field().marker;
    const path = this.host.path();
    return marker ? { kind: 'set', path: [...path.slice(0, -1), marker], value } : null;
  }

  private setValue(value: unknown): void {
    this.host.edit.emit({ kind: 'set', path: this.host.path(), value });
  }
}
