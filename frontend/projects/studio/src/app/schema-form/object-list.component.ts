/**
 * Eine Liste oder Map von OBJEKTEN als Liste│Editor (ST-3).
 *
 * Bis ST-3 stand jedes Objekt voll aufgeklappt unter dem vorigen — 22
 * Gold-Flows samt ihrer Züge waren eine Wand, und wer den vierzehnten suchte,
 * scrollte. Links jetzt Zähler, Suche und je Eintrag ein Titel
 * (`entry-title.ts`), rechts der Editor genau eines Eintrags.
 *
 * Löschen fragt nicht nach: es ist eine Änderung am Formular wie jede andere,
 * und „Verwerfen" holt den Eintrag zurück. Erst Speichern schreibt.
 *
 * Die Auswahl merkt sich eine Kennung (Index bzw. Schlüssel), nicht das Objekt:
 * nach jeder Änderung reicht das Formular einen neuen Wert herein, und ein
 * gemerktes Objekt wäre dann ein veraltetes.
 */
import {
  ChangeDetectionStrategy, Component, computed, forwardRef, inject, input, output, signal,
} from '@angular/core';

import { pathKey } from '../core/field-problems';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { entryTitle } from './entry-title';
import { nextFreeKey, safeIdPart } from './field-ids';
import type { ValuePath } from './form-value';
import { type FormEdit, SchemaFieldComponent } from './schema-field.component';
import type { SchemaField } from './schema-to-fields';

type EntryId = number | string;

interface Entry {
  readonly id: EntryId;
  readonly title: string;
  readonly value: unknown;
  readonly path: ValuePath;
  /** Der Server hat an diesem Eintrag etwas abgewiesen (ST-2e). */
  readonly problem: boolean;
}

const NO_PROBLEMS: ReadonlyMap<string, string> = new Map();

@Component({
  selector: 'studio-object-list',
  // forwardRef: der Editor rechts ist wieder ein Schema-Feld, und das setzt für
  // eine Liste von Objekten wieder diese Komponente ein.
  imports: [forwardRef(() => SchemaFieldComponent)],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './object-list.component.html',
  styleUrls: ['./schema-form.scss', './object-list.component.scss'],
})
export class ObjectListComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  /** Das Listen- oder Map-Feld; sein `item` ist eine Gruppe. */
  readonly field = input.required<SchemaField>();
  readonly path = input.required<ValuePath>();
  readonly value = input<unknown>();
  /** Die Beschriftung der Sammlung — für die Namen von Suche und Knöpfen. */
  readonly label = input.required<string>();
  readonly idPrefix = input('sf');
  readonly problems = input<ReadonlyMap<string, string>>(NO_PROBLEMS);
  readonly edit = output<FormEdit>();

  readonly query = signal('');
  private readonly chosen = signal<EntryId | null>(null);
  readonly keyError = signal('');

  readonly isMap = computed(() => this.field().kind === 'map');
  readonly baseId = computed(
    () => `${this.idPrefix()}-${this.path().map(safeIdPart).join('-')}-ol`);

  private readonly items = computed<readonly unknown[]>(() => {
    const value = this.value();
    return Array.isArray(value) ? value : [];
  });

  readonly entries = computed<readonly Entry[]>(() => {
    const value = this.value();
    const problems = [...this.problems().keys()];
    const make = (id: EntryId, entry: unknown, title: string): Entry => {
      const path = [...this.path(), id];
      const key = pathKey(path);
      return {
        id, value: entry, path, title,
        problem: problems.some((p) => p === key || p.startsWith(`${key}.`)),
      };
    };
    if (this.isMap()) {
      if (typeof value !== 'object' || value === null || Array.isArray(value)) return [];
      return Object.entries(value as Record<string, unknown>).map(([key, entry]) =>
        make(key, entry, key));
    }
    const item = this.field().item!;
    return this.items().map((entry, index) => make(index, entry,
      entryTitle(item, entry, this.t('objectList.entry', { index: index + 1 }))));
  });

  readonly shown = computed<readonly Entry[]>(() => {
    const query = this.query().trim().toLowerCase();
    return query
      ? this.entries().filter((entry) => entry.title.toLowerCase().includes(query))
      : this.entries();
  });

  /** Der gewählte Eintrag; ohne Wahl der erste sichtbare. */
  readonly current = computed<Entry | null>(() => {
    const chosen = this.chosen();
    return this.entries().find((entry) => entry.id === chosen) ?? this.shown()[0] ?? null;
  });

  readonly countText = computed(() => {
    const total = this.entries().length;
    const shown = this.shown().length;
    return shown === total
      ? this.lang.plural('objectList.count', total)
      : this.t('objectList.countFiltered', { shown, count: total });
  });

  select(id: EntryId): void {
    this.chosen.set(id);
    this.keyError.set('');
  }

  onSearch(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  add(): void {
    const blank = structuredClone(this.field().item?.blank ?? null);
    if (this.isMap()) {
      const key = nextFreeKey(this.keys());
      this.select(key);
      this.edit.emit({ kind: 'set', path: [...this.path(), key], value: blank });
      return;
    }
    this.select(this.items().length);
    this.edit.emit({ kind: 'set', path: this.path(), value: [...this.items(), blank] });
  }

  /** Die Kopie steht direkt hinter dem Original und ist danach gewählt. */
  duplicate(): void {
    const entry = this.current();
    if (!entry) return;
    const copy = structuredClone(entry.value);
    if (this.isMap()) {
      const key = nextFreeKey(this.keys(), `${entry.id}_kopie`);
      this.select(key);
      this.edit.emit({ kind: 'set', path: [...this.path(), key], value: copy });
      return;
    }
    const at = (entry.id as number) + 1;
    const items = [...this.items()];
    items.splice(at, 0, mitFreierKennung(copy, items));
    this.select(at);
    this.edit.emit({ kind: 'set', path: this.path(), value: items });
  }

  remove(): void {
    const entry = this.current();
    if (!entry) return;
    // danach der Vorgänger — sonst sprang die Wahl nach jedem Löschen nach oben
    this.chosen.set(this.isMap() ? null : Math.max(0, (entry.id as number) - 1));
    this.edit.emit({ kind: 'remove', path: entry.path });
  }

  /**
   * Schlüssel einer Map umbenennen — `change`, nicht `input`: ein halb getippter
   * Schlüssel („F", „FA") bliebe sonst als Spur im Dokument. Abgewiesen wird ein
   * leerer oder vergebener Name, und das Feld zeigt dann wieder den alten.
   */
  rename(event: Event): void {
    const entry = this.current();
    const input = event.target as HTMLInputElement;
    if (!entry) return;
    const from = String(entry.id);
    const to = input.value.trim();
    if (to === from) return;
    if (!to || this.keys().includes(to)) {
      input.value = from;
      this.keyError.set(to
        ? this.t('schemaField.keyTaken', { key: to })
        : this.t('schemaField.emptyKey'));
      return;
    }
    this.keyError.set('');
    this.select(to);
    this.edit.emit({ kind: 'rename', path: this.path(), from, to });
  }

  private keys(): string[] {
    return this.entries().map((entry) => String(entry.id));
  }
}

/**
 * Eine Listen-Kopie mit eigener Kennung (Paket 4, D5; externes Audit F14).
 * Trug die Kopie die `id` des Originals, gab es sie zweimal — Regeln, Server
 * und Flows werden über sie angesprochen. Einträge ohne `id` bleiben, wie sie
 * sind; vergeben wird wie bei Map-Schlüsseln: `<id>_kopie`, `_kopie_2` …
 */
function mitFreierKennung(copy: unknown, items: readonly unknown[]): unknown {
  if (!copy || typeof copy !== 'object' || Array.isArray(copy)) return copy;
  const id = (copy as { id?: unknown }).id;
  if (typeof id !== 'string' || !id) return copy;
  const vergeben = items.flatMap((item) => {
    const andere = item && typeof item === 'object' ? (item as { id?: unknown }).id : undefined;
    return typeof andere === 'string' ? [andere] : [];
  });
  return { ...copy, id: nextFreeKey(vergeben, `${id}_kopie`) };
}
