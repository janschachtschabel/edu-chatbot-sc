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
} from '@angular/core';

import { pathKey } from '../core/field-problems';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { safeIdPart } from './field-ids';
import type { ValuePath } from './form-value';
import { FieldControlComponent } from './field-control.component';
import { JsonValueComponent } from './json-value.component';
import { ListItems } from './list-items';
import { MapEntries } from './map-entries';
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

  /** Bearbeitung einer Liste — Chips, hervorgehobener Eintrag (`list-items.ts`). */
  readonly list = new ListItems(this, this.lang);
  /** Bearbeitung einer Map — Schlüssel anlegen, umbenennen (`map-entries.ts`). */
  readonly map = new MapEntries(this, this.lang);

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

  /** Paket 4c, B2: nicht gesetzt — es gilt die Vorgabe, nicht „keine“. */
  readonly unset = computed(() => this.field().vorgabe === true && this.value() == null);

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

  /** Eine Liste oder Map von OBJEKTEN (ST-3): als Liste│Editor statt Wand. */
  readonly objectItems = computed(() => this.field().item?.kind === 'group');

  onJsonError(message: string): void {
    this.edit.emit({ kind: 'field-error', path: this.path(), message });
  }
}
