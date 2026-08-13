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
import { RouterLink } from '@angular/router';

import { ChoicesApi } from '../core/choices-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { nextFreeKey, safeIdPart } from './field-ids';
import type { ValuePath } from './form-value';
import { JsonValueComponent } from './json-value.component';
import type { SchemaField } from './schema-to-fields';

export type FormEdit =
  | { readonly kind: 'set'; readonly path: ValuePath; readonly value: unknown }
  | { readonly kind: 'remove'; readonly path: ValuePath }
  | { readonly kind: 'rename'; readonly path: ValuePath; readonly from: string; readonly to: string }
  /** Not a document change: a field reporting that its input cannot be parsed,
   *  so the form can stop a save that would silently drop it. `''` clears. */
  | { readonly kind: 'field-error'; readonly path: ValuePath; readonly message: string };

interface MapEntry {
  readonly key: string;
  readonly value: unknown;
}

/** Grobe Zeichen je Zeile bei 46rem Feldbreite und Schriftgrad 0.8125rem. */
const CHARS_PER_ROW = 70;
/** Auch leer eine Fläche, die zum Schreiben einlädt … */
const MIN_ROWS = 3;
/** … und nach oben ein Bildschirm, nicht mehr. */
const MAX_ROWS = 20;

@Component({
  selector: 'studio-schema-field',
  // forwardRef: the template recurses into this very component, and a bare
  // self-reference would read the binding before the class exists.
  imports: [JsonValueComponent, RouterLink, forwardRef(() => SchemaFieldComponent)],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './schema-field.component.html',
  styleUrl: './schema-form.scss',
})
export class SchemaFieldComponent {
  private readonly lang = inject(StudioLanguageService);
  private readonly choices = inject(ChoicesApi);
  protected readonly t = this.lang.t;

  readonly field = input.required<SchemaField>();
  readonly path = input.required<ValuePath>();
  readonly value = input<unknown>();
  /** Prefix that makes `<label for>` ids unique when two forms share a page. */
  readonly idPrefix = input('sf');
  /** Overrides `field.label` — a list entry is "quick_replies 2", a map entry
   * carries its own key as the heading. */
  readonly labelOverride = input<string | null>(null);

  readonly edit = output<FormEdit>();

  /** Refused rename, kept next to the row it belongs to. */
  readonly keyError = signal<{ readonly key: string; readonly message: string } | null>(null);

  readonly label = computed(() => this.labelOverride() ?? this.field().label);
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
  readonly descId = computed(() => (this.field().description ? `${this.fieldId()}-desc` : null));

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

  /** Typed views of `value` — a template cannot bind `unknown` to an input. */
  readonly asText = computed(() => {
    const value = this.value();
    if (typeof value === 'string') return value;
    return value === null || value === undefined ? '' : String(value);
  });
  readonly asNumber = computed(() => {
    const value = this.value();
    return typeof value === 'number' && Number.isFinite(value) ? String(value) : '';
  });
  readonly asBoolean = computed(() => this.value() === true);

  /**
   * Die Höhe einer Textfläche, aus dem Inhalt.
   *
   * Eine feste Höhe kann nur eines von beidem: ein leeres Feld nicht zur
   * halben Seite aufblasen, oder einen 700-Zeichen-Text zeigen. Die Zahl
   * wächst beim Tippen mit — ein Attribut, kein Elementwechsel, also ohne
   * Fokusverlust. Wer selbst zieht, gewinnt: die gezogene Höhe steht als
   * `style` und schlägt `rows`.
   */
  readonly rows = computed(() => {
    const geschaetzt = Math.ceil(this.asText().length / CHARS_PER_ROW);
    return Math.min(MAX_ROWS, Math.max(MIN_ROWS, geschaetzt));
  });

  /**
   * Die Optionen eines Auswahlfeldes: die leere zuerst, dann der Vorrat — und
   * ein gespeicherter Wert, den der Vorrat nicht kennt, als eigener Eintrag.
   *
   * Ohne diesen letzten Teil zeigte das Feld die erste Option an, obwohl etwas
   * anderes gespeichert ist, und der nächste Speichervorgang schriebe die
   * Anzeige fest. Ein Auswahlfeld darf einen Bestandswert nicht wegwerfen — es
   * darf ihn nur ausweisen.
   */
  readonly options = computed<readonly { value: string; label: string }[]>(() => {
    const vorrat = this.field().choices ?? [];
    const rows = [
      { value: '', label: this.lang.t('schemaField.noChoice') },
      ...vorrat.map((value) => ({ value, label: value })),
    ];
    const current = this.asText();
    if (current && !vorrat.includes(current)) {
      rows.push({ value: current, label: this.lang.t('schemaField.foreignChoice', { current }) });
    }
    return rows;
  });

  /**
   * Die `id` der Vorschlagsliste, oder `null` wenn das Feld keine hat. Aus dem
   * KATALOG-Namen gebildet, nicht aus dem Feld: die Liste selbst rendert das
   * Formular einmal je Katalog (`SchemaFormComponent`), sonst stünde derselbe
   * Vorrat einmal je Listeneintrag in der Seite.
   */
  readonly datalistId = computed(() => {
    const catalog = this.field().catalog;
    return catalog ? `${this.idPrefix()}-cat-${catalog}` : null;
  });

  /**
   * Der Sprung zum gewählten Element, als Routen-Segmente. `null`, solange der
   * Wert in keinem Katalog steht oder das Element keine eigene Seite hat
   * (Werkzeuge) — dann zeigt das Formular keinen Link statt eines toten.
   *
   * Segmente und nicht ein Stück: ein Bereichsschlüssel trägt einen
   * Schrägstrich (`03-patterns/m06-…`), und als EIN Segment übergeben landet er
   * `%2F`-kodiert in der Adresse. Ebenso in `areas.component.ts`.
   */
  readonly linkSegments = computed<readonly string[] | null>(() => {
    const area = this.choices.areaFor(this.field().catalog, this.asText());
    return area ? ['/bereich', ...area.split('/')] : null;
  });

  readonly items = computed<readonly unknown[]>(() => {
    const value = this.value();
    return Array.isArray(value) ? value : [];
  });

  readonly entries = computed<readonly MapEntry[]>(() => {
    const value = this.value();
    if (typeof value !== 'object' || value === null || Array.isArray(value)) return [];
    return Object.entries(value as Record<string, unknown>).map(([key, entry]) => ({
      key,
      value: entry,
    }));
  });

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

  /** Text, Textfläche und Auswahlfeld — alle drei tragen ihren Wert in `value`. */
  onText(event: Event): void {
    const control = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
    this.setValue(control.value);
  }

  onNumber(event: Event): void {
    const input = event.target as HTMLInputElement;
    // An empty numeric field is not 0 — sending null keeps "I cleared this"
    // distinguishable, and the save surfaces a 422 naming the field if it was
    // required. Silently substituting 0 would write a value nobody chose.
    this.setValue(input.value === '' ? null : input.valueAsNumber);
  }

  onBoolean(event: Event): void {
    this.setValue((event.target as HTMLInputElement).checked);
  }

  addItem(): void {
    this.setValue([...this.items(), structuredClone(this.field().item?.blank ?? null)]);
  }

  removeItem(index: number): void {
    this.edit.emit({ kind: 'remove', path: this.childPath(index) });
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
