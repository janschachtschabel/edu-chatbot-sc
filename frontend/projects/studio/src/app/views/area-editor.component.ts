/**
 * The generic area editor (9-3e) — the route that makes every one of the 35
 * config areas editable, including the ones ALT only claimed to support.
 *
 * Two tabs over the same area:
 *   - "Formular": the schema-driven form. Edits a copy of the whole document,
 *     so keys no field renders survive the save untouched.
 *   - "Rohtext": the YAML/MD source. The complete view, and the only way to
 *     change a key the area model does not know about.
 *
 * Switching tabs with unsaved changes is refused rather than silently resolved:
 * the two tabs are two representations of one document, and the raw text comes
 * from the server, so a swap would show a stale copy of what was just edited.
 *
 * The document half lives in `AreaDocEditor` (9-4a) — shared with the curated
 * views, including its generation guard, which this component also uses for
 * its raw-text requests so both halves count on one clock.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { ConfigApi } from '../core/config-api.service';
import { AreaDocEditor, describeAreaError } from '../schema-form/area-doc-editor';
import { SchemaFormComponent } from '../schema-form/schema-form.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';
import { warnOnUnload } from './unsaved-changes.guard';

type Tab = 'form' | 'raw';

/** The shared strip addresses panels by tab id, so the ids carry the prefix. */
const TAB_ID: Readonly<Record<Tab, string>> = { form: 'ae-form', raw: 'ae-raw' };

@Component({
  selector: 'studio-area-editor',
  imports: [SchemaFormComponent, TabBarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './area-editor.component.html',
  styleUrl: './area-editor.component.scss',
})
export class AreaEditorComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly config = inject(ConfigApi);
  readonly editor = new AreaDocEditor(this.config);

  /** `bereich/**` — the area key is everything after the first segment. */
  private readonly segments = toSignal(this.route.url, { initialValue: [] });
  readonly area = computed(() =>
    this.segments()
      .slice(1)
      .map((segment) => segment.path)
      .join('/'),
  );

  readonly tab = signal<Tab>('form');
  readonly rawText = signal('');
  readonly filePath = signal('');
  private readonly savedRaw = signal('');

  readonly activeTab = computed(() => TAB_ID[this.tab()]);
  /** The raw tab names the format it is about to show — md and yaml save through
   *  different paths, and getting that wrong replaces the whole area. */
  readonly tabs = computed<readonly TabDef[]>(() => [
    { id: TAB_ID.form, label: 'Formular' },
    {
      id: TAB_ID.raw,
      label: `Rohtext (${this.filePath().endsWith('.md') ? 'Markdown' : 'YAML'})`,
    },
  ]);

  readonly loading = this.editor.loading;
  readonly loadError = this.editor.loadError;
  readonly saving = this.editor.saving;
  readonly saveError = this.editor.saveError;
  readonly status = this.editor.status;
  readonly schema = this.editor.schema;
  readonly doc = this.editor.doc;

  readonly rawDirty = computed(() => this.rawText() !== this.savedRaw());
  readonly dirty = computed(() =>
    this.tab() === 'form' ? this.editor.dirty() : this.rawDirty(),
  );
  readonly blocked = computed(() => this.tab() === 'form' && this.editor.blocked());

  /** `null` = nothing handled yet. NOT `''`: the empty area is a real case
   *  (`bereich/**` matches the bare `/bereich`) and must not look "already
   *  handled" on the first run. */
  private loadedArea: string | null = null;

  constructor() {
    // An effect on the URL, not ngOnInit: the router REUSES this component when
    // navigating from one area to another, so ngOnInit fires once and the
    // second area would never load.
    effect(() => {
      const area = this.area();
      if (area === this.loadedArea) return;
      this.loadedArea = area;
      if (!area) {
        // `bereich/**` also matches the bare `/bereich`; without this the page
        // would sit on "wird geladen" forever, with no error and no retry.
        this.editor.loading.set(false);
        this.editor.loadError.set(
          'Es ist kein Bereich angegeben. Bitte über „Alle Bereiche“ öffnen.',
        );
        return;
      }
      void this.load();
    });
    warnOnUnload(() => this.dirty());
  }

  async load(): Promise<void> {
    const area = this.area();
    // Chained on the load's own generation, never a new one: bumping it here
    // would void a load for a DIFFERENT area that is still in flight.
    if (!(await this.editor.load(area))) return;
    await this.loadRaw(area, this.editor.currentGeneration);
  }

  /**
   * The extension comes from the store's `type`, which decides md-vs-yaml with
   * an EXACT `{frontmatter, body}` match. Guessing it here from the document
   * shape once used a superset test, and the two sides disagreeing means saving
   * YAML text through the `.md` path — which replaces the whole area with
   * `{frontmatter: {}, body: "<the YAML dump>"}`.
   */
  private async loadRaw(area: string, generation: number): Promise<void> {
    const path = `${area}.${this.editor.docType() === 'md' ? 'md' : 'yaml'}`;
    try {
      const file = await this.config.fileText(path);
      if (!this.editor.isCurrent(generation)) return;
      this.filePath.set(path);
      this.rawText.set(file.content);
      this.savedRaw.set(file.content);
    } catch (err) {
      if (this.editor.isCurrent(generation)) this.editor.loadError.set(describeAreaError(err));
    }
  }

  onDoc(next: Record<string, unknown>): void {
    this.editor.setDoc(next);
  }

  onFieldErrors(fields: readonly string[]): void {
    this.editor.setFieldErrors(fields);
  }

  onRawInput(event: Event): void {
    this.rawText.set((event.target as HTMLTextAreaElement).value);
    this.editor.status.set('');
    this.editor.saveError.set('');
  }

  onTabChange(id: string): void {
    this.selectTab(id === TAB_ID.raw ? 'raw' : 'form');
  }

  selectTab(tab: Tab): void {
    if (tab === this.tab()) return;
    if (this.dirty()) {
      this.editor.status.set('Bitte erst speichern oder verwerfen — die Ansichten zeigen sonst '
        + 'unterschiedliche Stände desselben Bereichs.');
      return;
    }
    this.editor.status.set('');
    this.editor.saveError.set('');
    this.tab.set(tab);
  }

  discard(): void {
    if (this.tab() === 'form') {
      this.editor.discard();
      return;
    }
    this.rawText.set(this.savedRaw());
    this.editor.saveError.set('');
    this.editor.status.set('Änderungen verworfen.');
  }

  async save(): Promise<void> {
    if (this.saving() || !this.dirty()) return;
    if (this.tab() === 'form') {
      if (!(await this.editor.save(this.area()))) return;
      // the YAML view is now stale — reload it rather than let it lie
      await this.loadRaw(this.area(), this.editor.currentGeneration);
      return;
    }
    await this.saveRaw();
  }

  private async saveRaw(): Promise<void> {
    if (this.blocked()) return;
    const area = this.area();
    const generation = this.editor.nextGeneration();
    this.editor.saving.set(true);
    this.editor.saveError.set('');
    this.editor.status.set('');
    try {
      await this.config.saveFileText(this.filePath(), this.rawText());
      if (!this.editor.isCurrent(generation)) return;
      this.savedRaw.set(this.rawText());
      const document = await this.config.data(area);
      if (!this.editor.isCurrent(generation)) return;
      this.editor.adopt(document.data);
      this.editor.docType.set(document.type);
      this.editor.status.set('Gespeichert.');
    } catch (err) {
      if (this.editor.isCurrent(generation)) this.editor.saveError.set(describeAreaError(err));
    } finally {
      if (this.editor.isCurrent(generation)) this.editor.saving.set(false);
    }
  }
}
