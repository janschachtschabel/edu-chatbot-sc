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
 *
 * Since Paket 6 (ST-3d) a list│editor: the side list is `studio-entry-list`
 * (count, search, the id beside each name), with Duplicate and Delete beside
 * New. The traffic with the server — load, create, copy, delete, „shipped?" —
 * lives in `GroupDocuments`; the server derives the key of a new document.
 */
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { ConfigApi } from '../core/config-api.service';
import { SnapshotsApi } from '../core/snapshots-api.service';
import { StudioApiError } from '../core/studio-api-error';
import { StudioApi } from '../core/studio-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AreaDocEditor, describeAreaError } from '../schema-form/area-doc-editor';
import {
  EntryListComponent, type EntryId, filterEntries,
} from '../schema-form/entry-list.component';
import { SchemaFormComponent } from '../schema-form/schema-form.component';
import type { CuratedAreaSection } from './curated-views';
import { EffectBadgeComponent } from './effect-badge.component';
import { feldAusschnitt } from './feld-ausschnitt';
import { FeldReiter } from './feld-reiter';
import { GroupDocuments, type GroupEntry, slugify } from './group-documents';
import { LoeschRueckfrage } from './loesch-rueckfrage';
import { SaveConflictComponent } from './save-conflict.component';
import { TabBarComponent } from './tab-bar.component';
import { RagHinweis } from './wirksame-bereiche';

@Component({
  selector: 'studio-group-section',
  imports: [
    EffectBadgeComponent, EntryListComponent, SaveConflictComponent, SchemaFormComponent,
    TabBarComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './group-section.component.html',
  styleUrl: './group-section.component.scss',
})
export class GroupSectionComponent {
  readonly section = input.required<CuratedAreaSection>();
  readonly open = input(false);
  /** After a save, create, copy or delete — a tabbed page counts again (ST-4c). */
  readonly changed = output<void>();

  private readonly config = inject(ConfigApi);
  private readonly lang = inject(StudioLanguageService);
  private readonly injector = inject(Injector);
  protected readonly t = this.lang.t;
  readonly editor = new AreaDocEditor(this.config, this.t);
  readonly docs = new GroupDocuments(
    inject(StudioApi), this.config, inject(SnapshotsApi), () => this.area());
  /** Die Rückfrage vor dem Löschen — an EIN Dokument gebunden (Review Paket 6). */
  readonly rueckfrage = new LoeschRueckfrage(this.docs);

  readonly selected = signal('');
  readonly listError = signal('');
  readonly query = signal('');
  readonly newName = signal('');
  readonly newError = signal('');
  readonly creating = signal(false);
  readonly copying = signal(false);
  readonly notice = signal('');
  /** Läuft Anlegen, Duplizieren oder Löschen, bleiben Wahl und Knöpfe stehen:
   *  sonst landete das Ergebnis über einem inzwischen gewählten Dokument. */
  readonly beschaeftigt = computed(
    () => this.creating() || this.copying() || this.rueckfrage.busy());

  private readonly loeschKnopf = viewChild<ElementRef<HTMLElement>>('loeschKnopf');
  private readonly abbrechenKnopf = viewChild<ElementRef<HTMLElement>>('abbrechenKnopf');
  private readonly listTitel = viewChild<ElementRef<HTMLElement>>('listTitel');

  readonly area = computed(() => this.section().area);
  /** Auch ein nicht lesbarer Feld-Entwurf ist ungespeicherte Arbeit (Review-Runde 2). */
  readonly dirty = this.editor.verwerfbar;

  /** Paket 14 (B2): nur diese Kennungen wählbar (die Schutzantworten im Agent-Arbeitsbereich);
   *  dort gibt es weder Anlegen noch Duplizieren oder Löschen. `null` = die ganze Gruppe. */
  readonly nurAuswahl = computed(() => {
    const kennungen = this.section().dokumente;
    return kennungen ? new Set(kennungen.map((k) => k.toUpperCase())) : null;
  });

  /** Was diese Seite führt: die Auswahl oder die ganze Gruppe — Grundlage für Liste und Zähler. */
  private readonly gefuehrt = computed(() => {
    const auswahl = this.nurAuswahl();
    return auswahl
      ? this.docs.entries().filter((e) => auswahl.has(e.kennung.toUpperCase()))
      : this.docs.entries();
  });

  readonly shown = computed(() => filterEntries(this.gefuehrt(), this.query()));
  readonly current = computed<GroupEntry | null>(
    () => this.docs.entries().find((entry) => entry.id === this.selected()) ?? null);
  readonly countText = computed(() => {
    const total = this.gefuehrt().length;
    const shown = this.shown().length;
    return shown === total
      ? this.lang.plural('objectList.count', total)
      : this.t('objectList.countFiltered', { shown, count: total });
  });

  // ── Feld-Reiter (A7, nur mit `feature: 'pattern-tabs'`) ───────────
  readonly reiter = new FeldReiter(
    () => this.editor.schema(),
    () => this.section().feature === 'pattern-tabs',
    () => this.editor.fieldErrors(),
  );
  /** Was das Formular zeigt: der offene Reiter, sonst der Ausschnitt der Seite (Paket 15). */
  readonly sichtbar = computed(() =>
    this.reiter.visiblePaths() ?? feldAusschnitt(this.editor.schema(), this.section()));
  /** S4 (externes Audit F13): die Wissensbereiche, die ein Muster tatsächlich nutzt. */
  readonly rag = new RagHinweis(
    this.config, () => this.area() === '03-patterns', () => this.editor.doc(),
    () => this.reiter.active(), this.t, this.lang.list,
  );

  readonly idPrefix = computed(() => `gs-${this.area().replace(/[^\w-]/g, '-')}`);
  /** Die Kennung eines neuen Dokuments — den Schlüssel leitet der Server ab. */
  readonly newId = computed(() => slugify(this.newName()));

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
    this.listError.set('');
    try {
      await this.docs.load();
    } catch (err) {
      this.listError.set(describeAreaError(err, this.t));
    }
  }

  select(id: EntryId): void {
    const key = String(id);
    if (key === this.selected() || this.beschaeftigt()) return;
    if (this.editor.verwerfbar()) {
      this.notice.set(this.t('groupSection.switchBlocked'));
      return;
    }
    this.notice.set('');
    this.rueckfrage.schliessen();
    this.selected.set(key);
    void this.editor.load(key);
    this.rag.laden();
  }

  /** `force`: „Trotzdem speichern" after a conflict (Paket 4, D5). */
  save(force = false): void {
    // A refusal notice outlives what it referred to unless it is cleared here;
    // the live region would keep announcing "please save first" after saving.
    this.notice.set('');
    void this.editor.save(this.selected(), { force }).then((saved) => {
      if (saved) this.changed.emit();
    });
  }

  /** „Neu laden" after a conflict: the stored state replaces the draft. */
  reloadDocument(): void {
    void this.editor.load(this.selected());
  }

  onNewName(event: Event): void {
    this.newName.set((event.target as HTMLInputElement).value);
    this.newError.set('');
  }

  async create(): Promise<void> {
    const id = this.newId();
    if (!id) {
      this.newError.set(this.t('groupSection.needName'));
      return;
    }
    if (this.docs.taken(id)) {
      this.newError.set(this.t('groupSection.duplicate', { name: id }));
      return;
    }
    if (this.editor.verwerfbar()) {
      // Creating selects the new document, which would drop the open edits
      // exactly as switching entries would.
      this.newError.set(this.t('groupSection.createBlocked'));
      return;
    }
    this.creating.set(true);
    this.newError.set('');
    try {
      // The server derives the key and creates only (409 for a taken id or
      // key) — the list above may be stale (Paket 4, D5).
      const key = await this.docs.create(id, this.newName().trim());
      this.newName.set('');
      const geoeffnet = await this.openCreated(key);
      this.notice.set(this.t(geoeffnet ? 'groupSection.created' : 'groupSection.createdNotOpened'));
      this.changed.emit();
    } catch (err) {
      this.newError.set(err instanceof StudioApiError && err.status === 409
        ? this.t('groupSection.duplicate', { name: id })
        : describeAreaError(err, this.t));
    } finally {
      this.creating.set(false);
    }
  }

  /** Eine Kopie des gewählten Dokuments, aus dem GESPEICHERTEN Stand (ST-3d). */
  async duplicate(): Promise<void> {
    const entry = this.current();
    if (!entry) return;
    if (this.editor.verwerfbar()) {
      this.notice.set(this.t('groupSection.copyBlocked'));
      return;
    }
    this.copying.set(true);
    this.notice.set('');
    try {
      const label = this.t('groupSection.copyLabel', { label: entry.name });
      const key = await this.docs.create(this.docs.freeCopyId(entry.kennung), label, entry.id);
      const geoeffnet = await this.openCreated(key);
      this.notice.set(geoeffnet
        ? this.t('groupSection.copied', { title: label })
        : this.t('groupSection.createdNotOpened'));
      this.changed.emit();
    } catch (err) {
      this.notice.set(describeAreaError(err, this.t));
    } finally {
      this.copying.set(false);
    }
  }

  /** Erster Schritt: die Rückfrage, dazu ob das Dokument zum Auslieferungsstand
   *  gehört. Der Fokus geht auf „Abbrechen“ — die sichere Wahl. */
  askRemove(): void {
    const entry = this.current();
    if (!entry) return;
    this.rueckfrage.fragen(entry.id);
    this.fokus(this.abbrechenKnopf);
  }

  cancelRemove(): void {
    this.rueckfrage.schliessen();
    this.fokus(this.loeschKnopf);
  }

  async remove(): Promise<void> {
    const entry = this.current();
    if (!entry) return;
    const geloescht = await this.rueckfrage.loeschen(entry.id, this.editor.version() ?? null,
      (err) => err instanceof StudioApiError && err.status === 409
        ? this.t('groupSection.removeConflict') : describeAreaError(err, this.t));
    if (!geloescht) {
      this.fokus(this.loeschKnopf);
      return;
    }
    // Ein gelöschtes Dokument hat keinen Entwurf mehr — ohne `discard` hielte
    // ein offener den Wechsel- und Verlassen-Schutz fest.
    this.editor.discard();
    this.selected.set('');
    this.notice.set(this.t('groupSection.removed', { title: entry.name }));
    this.changed.emit();
    await this.loadList();
    this.fokus(this.listTitel);
  }

  /** Öffnet ein eben angelegtes Dokument — nicht, wenn während der Anfrage
   *  Änderungen am offenen entstanden: die blieben sonst still auf der Strecke. */
  private async openCreated(key: string): Promise<boolean> {
    this.rueckfrage.schliessen();
    this.query.set('');
    await this.loadList();
    if (this.editor.verwerfbar()) return false;
    this.selected.set(key);
    this.rag.laden();
    await this.editor.load(key);
    return true;
  }

  /** Der Knopf, der den Fokus hatte, verschwindet oft mit der Aktion (WCAG 2.4.3). */
  private fokus(ziel: () => ElementRef<HTMLElement> | undefined): void {
    afterNextRender(() => ziel()?.nativeElement.focus(), { injector: this.injector });
  }
}
