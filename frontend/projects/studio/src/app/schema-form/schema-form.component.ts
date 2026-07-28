/**
 * Renders a whole config document from its JSON schema (9-3d).
 *
 * The only place a document is written: field components report *what* changed
 * as a path, this applies it with the immutable helpers from form-value.ts and
 * emits the new document. Nothing is ever rebuilt from the schema, so keys no
 * field describes survive untouched — the guarantee the whole slice rests on.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  output,
  signal,
} from '@angular/core';

import { removeAt, renameKeyAt, setAt } from './form-value';
import type { JsonSchema } from './json-schema';
import { pickFields } from './pick-fields';
import { type FormEdit, SchemaFieldComponent } from './schema-field.component';
import { rootField, type SchemaField } from './schema-to-fields';

@Component({
  selector: 'studio-schema-form',
  imports: [SchemaFieldComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (unmapped().length > 0) {
      <p class="sf-note">
        @if (unmapped().length === 1) {
          Ein Schlüssel wird hier nicht angezeigt, weil das Bereichsmodell ihn nicht kennt:
          <code>{{ unmapped()[0] }}</code
          >. Beim Speichern bleibt er erhalten; ändern lässt er sich im Reiter „Rohtext“.
        } @else {
          {{ unmapped().length }} Schlüssel werden hier nicht angezeigt, weil das
          Bereichsmodell sie nicht kennt: <code>{{ unmapped().join(', ') }}</code
          >. Beim Speichern bleiben sie erhalten; ändern lassen sie sich im Reiter „Rohtext“.
        }
      </p>
    }
    <studio-schema-field
      [field]="rendered()"
      [path]="[]"
      [value]="value()"
      [idPrefix]="idPrefix()"
      (edit)="apply($event)"
    />
  `,
  styles: `
    .sf-note {
      max-inline-size: 46rem;
      margin: 0 0 var(--st-4);
      padding: var(--st-3);
      border: 1px solid var(--st-rule);
      border-inline-start: 4px solid var(--st-warn-dot);
      border-radius: var(--st-radius);
      background: var(--st-panel);
      font-size: 0.8125rem;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
  `,
  styleUrl: './schema-form.scss',
})
export class SchemaFormComponent {
  readonly schema = input.required<JsonSchema>();
  readonly value = input.required<Record<string, unknown>>();
  /** Makes `<label for>` ids unique — the area key, so they are stable too. */
  readonly idPrefix = input('sf');
  /**
   * Nur diese Dokument-Pfade rendern (A7, Formulare mit Reitern); `null` =
   * alles. Betrifft ausschließlich die Anzeige: geschrieben wird weiterhin das
   * ganze Dokument, und `unmapped` zählt weiterhin über den VOLLEN Baum — sonst
   * meldete jeder geschlossene Reiter seine Felder als unbekannt.
   */
  readonly visiblePaths = input<readonly string[] | null>(null);

  readonly valueChange = output<Record<string, unknown>>();

  readonly field = computed<SchemaField>(() => rootField(this.schema()));

  /** Der Ausschnitt, den dieses Formular gerade zeigt. */
  readonly rendered = computed<SchemaField>(() => {
    const paths = this.visiblePaths();
    return paths ? pickFields(this.field(), new Set(paths)) : this.field();
  });

  /**
   * Document paths no field renders — at ANY depth. Being told beats
   * discovering it: a form that quietly shows two of five keys reads as the
   * whole truth. Top-level-only would have been the wrong scope, since the
   * unpinned config in this project sits nested (`welcome.haus_intern`).
   */
  readonly unmapped = computed(() => collectUnmapped(this.field(), this.value(), ''));

  /** Fields whose input cannot be parsed right now, by dotted path. */
  private readonly fieldErrors = signal<Readonly<Record<string, string>>>({});
  readonly errorsChange = output<readonly string[]>();

  apply(edit: FormEdit): void {
    const current = this.value();
    switch (edit.kind) {
      case 'set':
        this.valueChange.emit(setAt(current, edit.path, edit.value));
        return;
      case 'remove':
        this.valueChange.emit(removeAt(current, edit.path));
        return;
      case 'rename':
        this.valueChange.emit(renameKeyAt(current, edit.path, edit.from, edit.to));
        return;
      case 'field-error':
        this.setFieldError(edit.path.join('.') || '(Wurzel)', edit.message);
        return;
    }
  }

  private setFieldError(where: string, message: string): void {
    const next = { ...this.fieldErrors() };
    if (message) next[where] = message;
    else delete next[where];
    this.fieldErrors.set(next);
    this.errorsChange.emit(Object.keys(next));
  }
}

/** Walk field tree and document together; a `raw` field covers its subtree. */
function collectUnmapped(field: SchemaField, value: unknown, path: string): string[] {
  if (value === null || typeof value !== 'object') return [];
  if (field.kind === 'list') {
    if (!Array.isArray(value) || !field.item) return [];
    return value.flatMap((entry, index) =>
      collectUnmapped(field.item!, entry, `${path}[${index}]`),
    );
  }
  if (Array.isArray(value)) return [];
  const entries = Object.entries(value as Record<string, unknown>);
  if (field.kind === 'map') {
    if (!field.item) return [];
    return entries.flatMap(([key, entry]) =>
      collectUnmapped(field.item!, entry, join(path, key)),
    );
  }
  if (field.kind !== 'group') return []; // `raw` shows the whole subtree as JSON
  const children = new Map((field.children ?? []).map((child) => [child.key, child]));
  return entries.flatMap(([key, entry]) => {
    const child = children.get(key);
    return child ? collectUnmapped(child, entry, join(path, key)) : [join(path, key)];
  });
}

function join(path: string, key: string): string {
  return path ? `${path}.${key}` : key;
}
