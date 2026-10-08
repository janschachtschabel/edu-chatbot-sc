/**
 * One field of a config document, rendered from its schema description and
 * recursing into groups, lists and maps (9-3d).
 *
 * It never owns the value. Every change leaves as a `FormEdit` carrying the
 * absolute path, and `SchemaFormComponent` applies it to the document — so the
 * parts of the document no field describes (357 unpinned paths in the ALT
 * config) are never rebuilt and therefore never lost.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

import { pathKey } from '../core/field-problems';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { nextFreeKey, safeIdPart } from './field-ids';
import type { ValuePath } from './form-value';
import { FieldControlComponent } from './field-control.component';
import { JsonValueComponent } from './json-value.component';
import { ObjectListComponent } from './object-list.component';
import type { SchemaField } from './schema-to-fields';

/** A change to the document itself. */
export type DocumentEdit =
  | { readonly kind: 'set'; readonly path: ValuePath; readonly value: unknown }
  | { readonly kind: 'remove'; readonly path: ValuePath }
  | { readonly kind: 'rename'; readonly path: ValuePath; readonly from: string; readonly to: string }
  /** Several changes applied to ONE document and reported once (ST-2i). Two
   *  edits emitted in the same tick would each start from the same stale
   *  input, and the second would silently undo the first. */
  | { readonly kind: 'batch'; readonly edits: readonly DocumentEdit[] };

export type FormEdit =
  | DocumentEdit
  /** Not a document change: a field reporting that its input cannot be parsed,
   *  so the form can stop a save that would silently drop it. `''` clears. */
  | { readonly kind: 'field-error'; readonly path: ValuePath; readonly message: string };

interface MapEntry {
  readonly key: string;
  readonly value: unknown;
}

const NO_PROBLEMS: ReadonlyMap<string, string> = new Map();

@Component({
  selector: 'studio-schema-field',
  // forwardRef: the template recurses into this very component, and a bare
  // self-reference would read the binding before the class exists. The object
  // list (ST-3) renders its editor with this component in turn — same reason.
  imports: [
    FieldControlComponent, JsonValueComponent,
    forwardRef(() => SchemaFieldComponent), forwardRef(() => ObjectListComponent),
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './schema-field.component.html',
  styleUrl: './schema-form.scss',
})
export class SchemaFieldComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly field = input.required<SchemaField>();
  readonly path = input.required<ValuePath>();
  readonly value = input<unknown>();
  /** Prefix that makes `<label for>` ids unique when two forms share a page. */
  readonly idPrefix = input('sf');
  /** Overrides `field.label` — a list entry is "quick_replies 2", a map entry
   * carries its own key as the heading. */
  readonly labelOverride = input<string | null>(null);
  /** The server's messages by absolute path (ST-2e); each field takes its own. */
  readonly problems = input<ReadonlyMap<string, string>>(NO_PROBLEMS);
  /** `list` with a marker (ST-2i): the value of the sibling that marks a row. */
  readonly markerValue = input<unknown>(undefined);

  readonly edit = output<FormEdit>();

  /** Refused rename, kept next to the row it belongs to. */
  readonly keyError = signal<{ readonly key: string; readonly message: string } | null>(null);

  /** Beschriftung aus dem Katalog (ST-1), `null` ohne Eintrag. */
  private readonly catalogueLabel = computed(() => this.catalogueText('label'));
  readonly label = computed(
    () => this.labelOverride() ?? this.catalogueLabel() ?? this.field().label,
  );
  /**
   * Der Rohschlüssel, klein hinter einer Katalog-Beschriftung: so benennen
   * Formular und YAML-Reiter weiter dasselbe Ding. Ohne Katalogtext IST die
   * Beschriftung schon der Schlüssel, und ein Listeneintrag („Regeln 2") hat
   * keinen eigenen.
   */
  readonly rawKey = computed(() =>
    this.labelOverride() === null && this.catalogueLabel() !== null ? this.field().key : null,
  );
  /** Hilfetext: der Katalog vor dem `description` des Schemas. */
  readonly hint = computed(() => this.catalogueText('hint') ?? this.field().description ?? null);
  /**
   * A list or map always needs a name — for its legend and for its buttons'
   * accessible names. The ROOT of a map area (`05-knowledge/rag-config`) has
   * no key, which produced an empty legend and "Eintrag zu  hinzufügen".
   * A group keeps the empty label: its legend is simply omitted.
   */
  readonly groupLabel = computed(
    () => this.label() || this.lang.t('schemaField.fallbackGroup'),
  );
  readonly fieldId = computed(() => {
    const suffix = this.path().map(safeIdPart).join('.');
    return suffix ? `${this.idPrefix()}-${suffix}` : this.idPrefix();
  });
  readonly descId = computed(() => (this.hint() ? `${this.fieldId()}-desc` : null));
  /** Der Name des hervorhebenden Nachbarfelds („Tour-Chip") für die Radios. */
  readonly markerLabel = computed(() => {
    const key = this.field().markerTextKey;
    return key && this.lang.has(`${key}.label`)
      ? this.lang.t(`${key}.label`)
      : (this.field().marker ?? '');
  });
  /** Die Prüfmeldung des Servers zu GENAU diesem Feld (ST-2e), sonst `null`. */
  readonly problem = computed(() => this.problems().get(pathKey(this.path())) ?? null);
  readonly errId = computed(() => (this.problem() ? `${this.fieldId()}-err` : null));
  /** Hilfetext und Meldung zusammen — `aria-describedby` nimmt mehrere Kennungen. */
  readonly describedWith = computed(
    () => [this.descId(), this.errId()].filter(Boolean).join(' ') || null,
  );

  /**
   * The stored value cannot hold what this field renders — an array where the
   * schema says object, a scalar where it says list. Showing an empty group
   * would be a lie AND every edit into it would be discarded, so the value is
   * handed to the JSON editor instead, where it can be seen and repaired.
   */
  readonly shapeMismatch = computed(() => {
    const value = this.value();
    if (value === undefined || value === null) return false;
    switch (this.field().kind) {
      case 'list':
        return !Array.isArray(value);
      case 'group':
      case 'map':
        return typeof value !== 'object' || Array.isArray(value);
      default:
        return false;
    }
  });

  // Die Formnamen tragen ihren Artikel, weil der Satz sie so einsetzt („ist
  // eine Liste") — und welcher Artikel das ist, entscheidet die Sprache.
  readonly expectedShape = computed(() => this.lang.t(
    this.field().kind === 'list' ? 'schemaField.shape.list' : 'schemaField.shape.object',
  ));
  readonly actualShape = computed(() => {
    const value = this.value();
    if (Array.isArray(value)) return this.lang.t('schemaField.shape.list');
    return typeof value === 'object'
      ? this.lang.t('schemaField.shape.object')
      : this.lang.t('schemaField.shape.scalar', { type: typeof value });
  });

  readonly items = computed<readonly unknown[]>(() => {
    const value = this.value();
    return Array.isArray(value) ? value : [];
  });

  /** Paket 4c, B2: nicht gesetzt — es gilt die Vorgabe, nicht „keine“. */
  readonly unset = computed(() => this.field().vorgabe === true && this.value() == null);

  readonly entries = computed<readonly MapEntry[]>(() => {
    const value = this.value();
    if (typeof value !== 'object' || value === null || Array.isArray(value)) return [];
    return Object.entries(value as Record<string, unknown>).map(([key, entry]) => ({
      key,
      value: entry,
    }));
  });

  private catalogueText(part: 'label' | 'hint'): string | null {
    const key = this.field().textKey;
    return key && this.lang.has(`${key}.${part}`) ? this.lang.t(`${key}.${part}`) : null;
  }

  childPath(key: string | number): ValuePath {
    return [...this.path(), key];
  }

  childValue(key: string): unknown {
    const value = this.value();
    if (typeof value !== 'object' || value === null) return undefined;
    return (value as Record<string, unknown>)[key];
  }

  setValue(value: unknown): void {
    this.edit.emit({ kind: 'set', path: this.path(), value });
  }

  /** `aria-disabled` statt `disabled`: der Knopf behält den Fokus, wirkt aber nur, wenn gesetzt.
   *  Entfernt den Schlüssel statt `null` zu schreiben — fehlend liest die Laufzeit als Vorgabe. */
  restoreDefault(): void {
    if (!this.unset()) this.edit.emit({ kind: 'remove', path: this.path() });
  }

  addItem(): void {
    this.setValue([...this.items(), structuredClone(this.field().item?.blank ?? null)]);
  }

  removeItem(index: number): void {
    const remove: DocumentEdit = { kind: 'remove', path: this.childPath(index) };
    const unmark = this.isMarked(index) ? this.markEdit('') : null;
    // sonst zeigte der Tour-Chip auf eine Zeile, die es nicht mehr gibt
    this.edit.emit(unmark ? { kind: 'batch', edits: [remove, unmark] } : remove);
  }

  /** Eine Liste oder Map von OBJEKTEN (ST-3): als Liste│Editor statt Wand. */
  readonly objectItems = computed(() => this.field().item?.kind === 'group');

  // ── ST-2g: eine Liste von Katalog-Namen als Chips ────────────────────

  /** Werkzeuge, Wissensbereiche … — je Wert ein Chip statt je Eintrag ein Feld. */
  readonly chipList = computed(() => {
    const field = this.field();
    return field.kind === 'list' && field.item?.kind === 'text' && !!field.item.catalog
      && !field.marker;
  });
  /** Ein doppelter Wert, beim Eingabefeld gemeldet statt still verworfen. */
  readonly chipError = signal('');

  addChip(input: HTMLInputElement): void {
    const value = input.value.trim();
    if (!value) return;
    if (this.items().includes(value)) {
      this.chipError.set(this.lang.t('schemaField.chipTaken', { value, group: this.groupLabel() }));
      return;
    }
    this.chipError.set('');
    this.setValue([...this.items(), value]);
    input.value = '';
  }

  // ── ST-2i: EIN Eintrag der Liste ist hervorgehoben (`x-marker`) ──────

  /** Die Zeile trägt den Wert, den das Nachbarfeld hervorhebt. */
  isMarked(index: number): boolean {
    return !!this.field().marker && this.items()[index] === this.markerValue();
  }

  /** Schreibt den hervorgehobenen Wert ins Nachbarfeld — `''` hebt keinen hervor. */
  mark(value: unknown): void {
    const edit = this.markEdit(value);
    if (edit) this.edit.emit(edit);
  }

  private markEdit(value: unknown): DocumentEdit | null {
    const marker = this.field().marker;
    return marker ? { kind: 'set', path: [...this.path().slice(0, -1), marker], value } : null;
  }

  /**
   * Eine Zeile wurde bearbeitet. War sie die hervorgehobene, wandert der Marker
   * mit — sonst verlöre eine Umbenennung des Tour-Chips still die Web-Tour.
   * `items()` trägt hier noch den ALTEN Wert: das Dokument ist noch nicht neu.
   */
  onItemEdit(index: number, edit: FormEdit): void {
    const follow = this.isMarked(index) && edit.kind === 'set'
      && edit.path.length === this.path().length + 1
      ? this.markEdit(edit.value)
      : null;
    this.edit.emit(follow && edit.kind === 'set' ? { kind: 'batch', edits: [edit, follow] } : edit);
  }

  addEntry(): void {
    const key = nextFreeKey(this.entries().map((entry) => entry.key));
    this.edit.emit({
      kind: 'set',
      path: this.childPath(key),
      value: structuredClone(this.field().item?.blank ?? null),
    });
  }

  removeEntry(key: string): void {
    this.edit.emit({ kind: 'remove', path: this.childPath(key) });
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
    this.edit.emit({ kind: 'rename', path: this.path(), from, to });
  }

  onJsonError(message: string): void {
    this.edit.emit({ kind: 'field-error', path: this.path(), message });
  }
}
