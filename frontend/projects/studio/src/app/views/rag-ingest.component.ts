/**
 * Reading a document into the knowledge base (9-4e): file, web page, or text.
 *
 * The area is a free-text field with a datalist of the areas that already
 * exist, not a select plus a "new area" toggle: an area is created by writing
 * into it, so picking an existing one and naming a new one are the same act.
 * ALT modelled them as two modes and needed a state flag to switch between.
 */
import {
  ChangeDetectionStrategy, Component, type ElementRef, computed, inject, input, signal, viewChild,
} from '@angular/core';

import { RagApi, type IngestResult, describeRagError } from '../core/rag-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

type Source = 'file' | 'url' | 'text';

/**
 * Die drei Quellen. `labelKey` statt `label`: fertiger Text auf Modulebene
 * fröre in der Sprache ein, die beim Laden des Moduls galt — derselbe Fall wie
 * `PREVIEW_CONTEXT_KINDS` (C1-d3b), `CONFIRM_LEAVE` (C1-d3a) und der
 * Routen-Titel (C1-d2). `id` bleibt Datum: es steht im Formular-Feld und
 * entscheidet, welcher Endpunkt gerufen wird.
 *
 * Ausgeschrieben statt `'rag.ingest.source.' + id` zusammengesetzt: ein zur
 * Laufzeit gebauter Schlüssel gäbe bei einer neuen Quelle den Schlüssel selbst
 * als Beschriftung aus.
 */
const SOURCES: readonly { readonly id: Source; readonly labelKey: string }[] = [
  { id: 'file', labelKey: 'rag.ingest.source.file' },
  { id: 'url', labelKey: 'rag.ingest.source.url' },
  { id: 'text', labelKey: 'rag.ingest.source.text' },
];

/** Was fehlt, in der Reihenfolge des Formulars — je Quelle genau eines. */
const NEED_KEY: Record<Source, string> = {
  file: 'rag.ingest.need.file',
  url: 'rag.ingest.need.url',
  text: 'rag.ingest.need.text',
};

@Component({
  selector: 'studio-rag-ingest',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './rag-ingest.component.html',
  styleUrl: './rag-ingest.component.scss',
})
export class RagIngestComponent {
  private readonly rag = inject(RagApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly sources = SOURCES;
  readonly areaNames = this.rag.areaNames;

  readonly source = signal<Source>('file');
  readonly area = signal('');
  readonly title = signal('');
  readonly url = signal('');
  readonly text = signal('');
  readonly file = signal<File | null>(null);

  readonly sending = signal(false);
  readonly error = signal('');
  readonly result = signal<IngestResult | null>(null);

  /** A unique prefix so several panels on one page keep distinct label targets. */
  readonly idPrefix = 'ri';

  private readonly fileInput = viewChild<ElementRef<HTMLInputElement>>('fileInput');

  /**
   * What still keeps "Einlesen" disabled, or '' when nothing does.
   *
   * Joined by `list()` and not by `gaps.join(' und ')`: that was the German
   * rule wired in, and an ‹und›-key would only be the next sentence built from
   * fragments — where a comma goes is the language's business, not ours
   * (C1-d3c).
   */
  readonly missing = computed(() => {
    const gaps: string[] = [];
    if (!this.area().trim()) gaps.push(this.t('rag.ingest.need.area'));
    if (!this.hasSourceInput()) gaps.push(this.t(NEED_KEY[this.source()]));
    return this.lang.list(gaps);
  });

  readonly ready = computed(() => this.missing() === '');

  /** Whether the field belonging to the chosen source holds something. */
  private hasSourceInput(): boolean {
    switch (this.source()) {
      case 'file':
        return this.file() !== null;
      case 'url':
        return this.url().trim() !== '';
      default:
        return this.text().trim() !== '';
    }
  }

  onSource(value: string): void {
    this.source.set(value as Source);
    this.error.set('');
  }

  onFile(event: Event): void {
    const chosen = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.file.set(chosen);
    // A file name is a better default title than "Unbenannt", and the editor
    // can still overwrite it before sending.
    if (chosen && !this.title().trim()) this.title.set(chosen.name);
  }

  async send(): Promise<void> {
    if (!this.ready() || this.sending()) return;
    this.sending.set(true);
    this.error.set('');
    this.result.set(null);
    const area = this.area().trim();
    const title = this.title().trim();
    try {
      this.result.set(await this.ingest(area, title));
      this.clearInput();
      await this.rag.refreshAreas();
    } catch (err) {
      // Deliberately keeps every field: a rejected upload must not cost the
      // editor the text they pasted.
      this.error.set(describeRagError(err, this.t));
    } finally {
      this.sending.set(false);
    }
  }

  private ingest(area: string, title: string): Promise<IngestResult> {
    switch (this.source()) {
      case 'file':
        return this.rag.ingestFile(area, title, this.file() as File);
      case 'url':
        return this.rag.ingestUrl(area, title, this.url().trim());
      default:
        return this.rag.ingestText(area, title, this.text());
    }
  }

  private clearInput(): void {
    this.file.set(null);
    // A file input keeps its own value; without this the panel would still show
    // the uploaded file name next to an empty form.
    const input = this.fileInput()?.nativeElement;
    if (input) input.value = '';
    this.url.set('');
    this.text.set('');
    this.title.set('');
  }
}
