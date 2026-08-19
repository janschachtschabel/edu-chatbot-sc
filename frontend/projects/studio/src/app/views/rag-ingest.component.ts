/**
 * Reading a document into the knowledge base (9-4e): file, web page, or text.
 *
 * **Der Wissensbereich wird GEWÄHLT, nicht getippt** (S2, 18.08.2026). Bis
 * dahin stand hier ein Textfeld mit `datalist`, begründet mit: „ein Bereich
 * entsteht, indem man hineinschreibt — einen bestehenden zu wählen und einen
 * neuen zu benennen ist derselbe Vorgang." Beide Hälften haben sich als falsch
 * erwiesen:
 *
 * 1. Eine `datalist` ist unsichtbar, bis jemand tippt. Gemeldet wurde genau
 *    das: „ich sehe keine Auswahlmöglichkeit für den Wissensbereich."
 * 2. Es ist NICHT derselbe Vorgang. Einen bestehenden Bereich zu wählen genügt;
 *    ein neuer muss zusätzlich in `05-knowledge/rag-config` stehen, sonst
 *    durchsucht der Chatbot ihn nie (Paket R). Ein Tippfehler im Textfeld sah
 *    aus wie ein Treffer und legte schweigend eine tote Ablage an.
 *
 * Deshalb jetzt: ein `select` der vorhandenen Bereiche, und der neue Name erst
 * nach ausdrücklicher Wahl von `__neu__` — mit dem Hinweis, was noch fehlt.
 * Gibt es noch gar keinen Bereich, fragt das Panel direkt nach dem Namen: ein
 * leeres Auswahlfeld wäre eine Sackgasse.
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
/** Der Wert der Option „neuen Bereich anlegen". Kein gültiger Bereichsname:
 *  die Unterstriche kämen aus keiner Redaktionshand. */
export const NEUER_BEREICH = '__neu__';

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
  /** Der Wert des Auswahlfelds: ein Bereichsname, {@link NEUER_BEREICH} oder ''. */
  readonly auswahl = signal('');
  /** Der getippte Name, wenn ein neuer Bereich angelegt wird. */
  readonly neuerName = signal('');
  /** Wird ein neuer Bereich benannt? Auch wahr, solange es keinen einzigen gibt. */
  readonly neu = computed(
    () => this.auswahl() === NEUER_BEREICH || this.areaNames().length === 0);
  /** Der Bereich, in den dieser Upload geht — aus beidem zusammengesetzt. */
  readonly area = computed(() =>
    this.neu() ? this.neuerName().trim() : this.auswahl());
  readonly title = signal('');
  readonly url = signal('');
  readonly text = signal('');
  readonly file = signal<File | null>(null);

  readonly sending = signal(false);
  readonly error = signal('');
  readonly result = signal<IngestResult | null>(null);

  /** A unique prefix so several panels on one page keep distinct label targets. */
  readonly idPrefix = 'ri';
  /** Fürs Template — der Wert der Option „neuen Bereich anlegen". */
  readonly NEUER_BEREICH = NEUER_BEREICH;

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

  onArea(value: string): void {
    this.auswahl.set(value);
    if (value !== NEUER_BEREICH) this.neuerName.set('');
    this.error.set('');
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
      // Den benutzten Bereich im Auswahlfeld stehen lassen. Ohne das faellt er
      // nach dem ERSTEN Einlesen aus dem Formular: die Liste ist dann nicht
      // mehr leer, `auswahl` steht aber noch auf '' — `neu()` kippt, das
      // Namensfeld verschwindet, und wer ein zweites Dokument in denselben
      // Bereich legen will, muss ihn neu waehlen (Durchsicht 2026-08-18).
      this.auswahl.set(area);
      this.neuerName.set('');
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
