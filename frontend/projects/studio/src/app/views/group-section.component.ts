/**
 * A GROUP of config documents as one disclosure panel (9-4d): the patterns
 * folder and the personas folder, where the area key addresses a directory
 * rather than a single document.
 *
 * Pick from the list, edit the picked document, save it. Nothing is edited in
 * bulk — deliberately: `PUT /api/config/patterns` (the ALT route, ported
 * byte-exact in P2) rebuilds each frontmatter from a typed model and writes
 * the whole set, so a key no model field covers is gone after one save. The
 * per-document route `PUT /api/config/data/03-patterns/x` replaces the
 * document with exactly what was read, which is the rule 9-3 arrived at.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';

import { ConfigApi } from '../core/config-api.service';
import { StudioApi } from '../core/studio-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AreaDocEditor, describeAreaError } from '../schema-form/area-doc-editor';
import { SchemaFormComponent } from '../schema-form/schema-form.component';
import { rootField } from '../schema-form/schema-to-fields';
import type { CuratedAreaSection } from './curated-views';
import { type FieldTab, patternFieldTabs } from './pattern-field-tabs';
import { TabBarComponent } from './tab-bar.component';

interface GroupEntry {
  /** Area key without extension — how the document is addressed. */
  readonly key: string;
  readonly label: string;
}

interface ElementsResponse {
  readonly patterns?: readonly { id?: string; label?: string; file?: string }[];
  readonly personas?: readonly { id?: string; label?: string; file?: string }[];
}

@Component({
  selector: 'studio-group-section',
  imports: [SchemaFormComponent, TabBarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './group-section.component.html',
  styleUrl: './group-section.component.scss',
})
export class GroupSectionComponent {
  readonly section = input.required<CuratedAreaSection>();
  readonly open = input(false);

  private readonly api = inject(StudioApi);
  private readonly config = inject(ConfigApi);
  protected readonly t = inject(StudioLanguageService).t;
  readonly editor = new AreaDocEditor(this.config, this.t);

  readonly entries = signal<readonly GroupEntry[]>([]);
  readonly selected = signal('');
  readonly listLoading = signal(false);
  readonly listError = signal('');
  readonly newName = signal('');
  readonly newError = signal('');
  readonly creating = signal(false);
  readonly notice = signal('');

  readonly area = computed(() => this.section().area);
  readonly dirty = this.editor.dirty;

  // ── Feld-Reiter (A7, nur mit `feature: 'pattern-tabs'`) ───────────
  /** Welcher Reiter offen ist; leer = der erste. Er bleibt beim Wechsel des
   *  Dokuments stehen: alle Dokumente der Gruppe teilen ein Schema, und wer
   *  „Anweisungen" vergleicht, will nicht bei jedem Muster neu klicken. */
  private readonly wantedTab = signal('');

  readonly fieldTabs = computed<readonly FieldTab[]>(() => {
    const schema = this.editor.schema();
    if (!schema || this.section().feature !== 'pattern-tabs') return [];
    return patternFieldTabs(rootField(schema));
  });

  readonly activeTab = computed(() => {
    const tabs = this.fieldTabs();
    const wanted = this.wantedTab();
    return tabs.some((tab) => tab.id === wanted) ? wanted : (tabs[0]?.id ?? '');
  });

  readonly visiblePaths = computed<readonly string[] | null>(() => {
    const active = this.activeTab();
    return this.fieldTabs().find((tab) => tab.id === active)?.paths ?? null;
  });

  /**
   * Die gesperrten Felder mit ihrem Reiter. Ohne den Namen suchte man ein
   * gesperrtes Speichern in fünf Reitern; der Fehler steht ja unter dem
   * Formular, nicht bei seinem Feld.
   */
  readonly blockedFields = computed<readonly string[]>(() =>
    this.editor.fieldErrors().map((path) => {
      const tab = this.fieldTabs().find((entry) => entry.paths.some((p) => isUnder(path, p)));
      return tab ? `${path} (Reiter „${tab.label}")` : path;
    }),
  );

  selectTab(id: string): void {
    this.wantedTab.set(id);
  }
  readonly idPrefix = computed(() => `gs-${this.area().replace(/[^\w-]/g, '-')}`);
  readonly newKey = computed(() => {
    const slug = slugify(this.newName());
    return slug ? `${this.area()}/${slug}` : '';
  });

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.loadList();
  }

  async loadList(): Promise<void> {
    this.listLoading.set(true);
    this.listError.set('');
    try {
      const elements = await this.api.get<ElementsResponse>('/config/elements');
      const raw = this.area() === '04-personas' ? elements.personas : elements.patterns;
      this.entries.set(
        (raw ?? [])
          .map((entry) => ({
            // `file` is always `<key>.md` (config_loader sets it from the key)
            key: String(entry.file ?? '').replace(/\.md$/, ''),
            label: `${entry.id ?? ''} — ${entry.label ?? entry.id ?? ''}`,
          }))
          .filter((entry) => entry.key.startsWith(`${this.area()}/`)),
      );
    } catch (err) {
      this.listError.set(describeAreaError(err, this.t));
    } finally {
      this.listLoading.set(false);
    }
  }

  select(key: string): void {
    if (key === this.selected()) return;
    if (this.editor.dirty()) {
      this.notice.set(this.t('groupSection.switchBlocked'));
      return;
    }
    this.notice.set('');
    this.selected.set(key);
    void this.editor.load(key);
  }

  save(): void {
    // A refusal notice outlives what it referred to unless it is cleared here;
    // the live region would keep announcing "please save first" after saving.
    this.notice.set('');
    void this.editor.save(this.selected());
  }

  onNewName(event: Event): void {
    this.newName.set((event.target as HTMLInputElement).value);
    this.newError.set('');
  }

  async create(): Promise<void> {
    const key = this.newKey();
    if (!key) {
      this.newError.set(this.t('groupSection.needName'));
      return;
    }
    if (this.entries().some((entry) => entry.key === key)) {
      this.newError.set(this.t('groupSection.duplicate', { name: key }));
      return;
    }
    if (this.editor.dirty()) {
      // Creating selects the new document, which would drop the open edits
      // exactly as switching entries would.
      this.newError.set(this.t('groupSection.createBlocked'));
      return;
    }
    this.creating.set(true);
    this.newError.set('');
    try {
      await this.config.saveFileText(`${key}.md`, newDocument(this.newName()));
      this.newName.set('');
      await this.loadList();
      this.selected.set(key);
      await this.editor.load(key);
      this.notice.set(this.t('groupSection.created'));
    } catch (err) {
      this.newError.set(describeAreaError(err, this.t));
    } finally {
      this.creating.set(false);
    }
  }
}

/** Fehlerpfad `frontmatter.tools` bzw. ein Kind davon (`…tools.0`)? */
function isUnder(path: string, field: string): boolean {
  return path === field || path.startsWith(`${field}.`);
}

/** `M03 Kuratieren` → `m03-kuratieren`. Empty when nothing usable is left. */
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[äöüß]/g, (c) => ({ ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' })[c] ?? c)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * The smallest document the area model accepts — every field is optional.
 *
 * The label is JSON-encoded (valid YAML for a scalar): a name containing a
 * colon makes the frontmatter unparseable, and one containing a newline adds
 * keys of its own.
 */
function newDocument(name: string): string {
  const id = slugify(name).split('-')[0] || slugify(name);
  return `---\nid: ${id}\nlabel: ${JSON.stringify(name.trim())}\n---\n\n`;
}
