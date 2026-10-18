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
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';

import { ChoicesApi } from '../core/choices-api.service';
import { EffectsApi } from '../core/effects-api.service';
import { feldPlakette } from '../core/feld-wirkung';
import { describeProblem, type FieldProblem, pathKey } from '../core/field-problems';
import { StudioAnsicht } from '../core/studio-ansicht.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { fieldAt } from './field-at';
import { FORM_EPOCHE } from './form-epoche';
import { FORM_WIRKUNG } from './form-wirkung';
import { type FeldGruppe, type FormSection, formSections, gruppenSections } from './form-sections';
import { removeAt, renameKeyAt, setAt } from './form-value';
import type { JsonSchema } from './json-schema';
import { pickFields } from './pick-fields';
import { type DocumentEdit, type FormEdit, SchemaFieldComponent } from './schema-field.component';
import { rootField, type SchemaField } from './schema-to-fields';

@Component({
  selector: 'studio-schema-form',
  imports: [SchemaFieldComponent],
  providers: [
    { provide: FORM_EPOCHE, useFactory: () => inject(SchemaFormComponent).epoche },
    { provide: FORM_WIRKUNG, useFactory: () => inject(SchemaFormComponent).plakette },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (unmapped().length; as anzahl) {
      <p class="sf-note">{{ plural('schemaForm.unmapped', anzahl, {
        keys: unmapped().join(', '),
      }) }}</p>
    }
    @if (problemsElsewhere().length) {
      <p class="sf-note sf-error">{{ t('schemaForm.problemsElsewhere', {
        list: problemsElsewhere().join('; '),
      }) }}</p>
    }
    @if (sections().length) {
      @for (section of sections(); track section.id) {
        <details class="sf-section" [open]="$first && !alleZu()">
          <summary class="sf-section-head">
            @let kopf = sectionHead(section);
            {{ kopf.label }}
            @if (kopf.key) {
              <span class="sf-key">{{ kopf.key }}</span>
            }
          </summary>
          <studio-schema-field
            [oben]="true"
            [field]="section.field"
            [path]="section.basePath"
            [value]="valueAt(section.basePath)"
            [idPrefix]="idPrefix()"
            [problems]="problemTexts()"
            (edit)="apply($event)"
          />
        </details>
      }
    } @else {
      <studio-schema-field
        [field]="rendered()"
        [path]="[]"
        [value]="value()"
        [idPrefix]="idPrefix()"
        [problems]="problemTexts()"
        (edit)="apply($event)"
      />
    }
    <!-- Eine Vorschlagsliste je KATALOG, hier und nicht am Feld: ein Muster
         nennt bis zu acht Werkzeuge, und jedes Feld mit einer eigenen Liste
         schriebe denselben Vorrat achtmal in die Seite. -->
    @for (name of catalogsInUse(); track name) {
      <datalist [id]="idPrefix() + '-cat-' + name">
        @for (entry of choices.entries(name); track entry.value) {
          <option [value]="entry.value" [label]="entry.label"></option>
        }
      </datalist>
    }
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
  private readonly lang = inject(StudioLanguageService);
  protected readonly choices = inject(ChoicesApi);
  private readonly format = inject(StudioFormat);
  protected readonly plural = this.lang.plural;
  protected readonly t = this.lang.t;

  readonly schema = input.required<JsonSchema>();
  /** What the server refused at the last save (ST-2e) — shown at each field. */
  readonly problems = input<readonly FieldProblem[]>([]);
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
  /** Rundgang 3: benannte Feldgruppen statt des Schnitts nach der Form des Dokuments — auch
   *  zusammen mit `visiblePaths` (dann über die gezeigten Felder). */
  readonly gruppen = input<readonly FeldGruppe[] | null>(null);

  readonly valueChange = output<Record<string, unknown>>();
  /** Zählt „Verwerfen“ des Editors hoch: JSON-Felder räumen ihren Entwurf (`FORM_EPOCHE`). */
  readonly epoche = input(0);
  /** Rundgang 3: der Bereich dieses Formulars — für die Plakette je Feld (`FORM_WIRKUNG`). */
  readonly area = input<string | null>(null);
  /** Alle Abschnitte zugeklappt starten, auch den ersten — wo er so groß ist, dass man ihn
   *  erst zuklappen müsste, um die übrigen zu sehen (Studio-Rundgang 2026-10-18). */
  readonly alleZu = input(false);
  private readonly effects = inject(EffectsApi).effects;
  private readonly ansicht = inject(StudioAnsicht).ansicht;
  /** Liest Signale: ein Feld, das sie in einem `computed` ruft, folgt Zuordnung und Ansicht. */
  readonly plakette = (pfad: string) => {
    const area = this.area();
    return area ? feldPlakette(this.effects(), area, pfad, this.ansicht()) : null;
  };

  readonly field = computed<SchemaField>(() => rootField(this.schema()));

  /** Der Ausschnitt, den dieses Formular gerade zeigt. */
  readonly rendered = computed<SchemaField>(() => {
    const paths = this.visiblePaths();
    return paths ? pickFields(this.field(), new Set(paths)) : this.field();
  });

  /**
   * Die aufklappbaren Abschnitte (S5) — leer heißt „ungegliedert rendern".
   *
   * Nicht bei Reitern: `visiblePaths` schneidet den Baum bereits, und eine
   * Gliederung im Reiter wäre eine Gliederung der Gliederung.
   */
  readonly sections = computed<readonly FormSection[]>(() => {
    const gruppen = this.gruppen();
    if (gruppen?.length) return gruppenSections(this.rendered(), gruppen);
    return this.visiblePaths() ? [] : formSections(this.field());
  });

  /** Die Meldungen, die an einem Feld stehen können: Pfad → Satz (ST-2e). */
  readonly problemTexts = computed<ReadonlyMap<string, string>>(() => new Map(
    this.problems()
      .filter((problem) => fieldAt(this.field(), problem.path))
      .map((problem) => [pathKey(problem.path), this.describe(problem)]),
  ));
  /** … und die ohne ein Feld, das sie tragen könnte — über dem Formular. */
  readonly problemsElsewhere = computed<readonly string[]>(() => this.problems()
    .filter((problem) => !fieldAt(this.field(), problem.path))
    .map((problem) => `${pathKey(problem.path)}: ${this.describe(problem)}`));

  /** Die Kataloge, aus denen dieses Schema Vorschläge zieht (S4). */
  readonly catalogsInUse = computed<readonly string[]>(() => [
    ...collectCatalogs(this.field(), new Set<string>()),
  ]);

  /**
   * Die Kataloge einmal je Formular holen, und nur wenn dieses Schema sie
   * überhaupt braucht (S4). Hier und nicht im Feld: ein Bereich hat leicht ein
   * Dutzend Katalog-Felder, und alle zeigen auf dieselben Listen — ein Effekt
   * je Feld wäre ein Dutzend Effekte für einen Abruf.
   */
  private readonly primeCatalogs = effect(() => {
    if (this.catalogsInUse().length > 0) void this.choices.prime();
  });

  /**
   * Kopf eines Abschnitts (ST-1): die Katalog-Beschriftung seines Feldes mit
   * dem Schlüssel klein dahinter, wie am Feld selbst. Ohne Katalogtext bleibt
   * der Schlüssel die Überschrift; der Sammel-Abschnitt heißt „Grundwerte".
   */
  protected sectionHead(section: FormSection): { label: string; key: string | null } {
    if (section.labelKey) return { label: this.t(section.labelKey), key: null };
    if (!section.key) return { label: this.t('schemaForm.basics'), key: null };
    // Paket 15: ein Block-Abschnitt ist der Block selbst; sonst ein Kind des Rumpfs.
    const feld = section.field.key === section.key
      ? section.field
      : section.field.children?.find((child) => child.key === section.key);
    const text = feld?.textKey ? `${feld.textKey}.label` : null;
    return text && this.lang.has(text)
      ? { label: this.t(text), key: section.key }
      : { label: section.key, key: null };
  }

  private describe(problem: FieldProblem): string {
    return describeProblem(problem, this.t, this.format.decimal);
  }

  /** Der Ausschnitt des Dokuments, an dem ein Abschnitt ansetzt. */
  protected valueAt(path: readonly string[]): unknown {
    return path.reduce<unknown>(
      (node, key) =>
        node && typeof node === 'object' ? (node as Record<string, unknown>)[key] : undefined,
      this.value(),
    );
  }

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
  /** Nach dem Zurücksetzen gilt kein Feldfehler mehr — der Editor hat seine Liste schon geleert. */
  private readonly nachZuruecksetzen = effect(() => {
    this.epoche();
    untracked(() => {
      if (Object.keys(this.fieldErrors()).length > 0) this.fieldErrors.set({});
    });
  });

  apply(edit: FormEdit): void {
    if (edit.kind === 'field-error') {
      this.setFieldError(edit.path.join('.') || this.lang.t('schemaForm.root'), edit.message);
      return;
    }
    this.valueChange.emit(applyEdit(this.value(), edit));
  }

  private setFieldError(where: string, message: string): void {
    const next = { ...this.fieldErrors() };
    if (message) next[where] = message;
    else delete next[where];
    this.fieldErrors.set(next);
    this.errorsChange.emit(Object.keys(next));
  }
}

/** A document change applied — a `batch` one after the other to the SAME document. */
function applyEdit(doc: Record<string, unknown>, edit: DocumentEdit): Record<string, unknown> {
  switch (edit.kind) {
    case 'set':
      return setAt(doc, edit.path, edit.value);
    case 'remove':
      return removeAt(doc, edit.path);
    case 'rename':
      return renameKeyAt(doc, edit.path, edit.from, edit.to);
    case 'batch':
      return edit.edits.reduce(applyEdit, doc);
  }
}

/** Jeder Katalog, den dieser Baum nennt — je Name einmal. */
function collectCatalogs(field: SchemaField, found: Set<string>): Set<string> {
  if (field.catalog) found.add(field.catalog);
  if (field.item) collectCatalogs(field.item, found);
  for (const child of field.children ?? []) collectCatalogs(child, found);
  return found;
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
