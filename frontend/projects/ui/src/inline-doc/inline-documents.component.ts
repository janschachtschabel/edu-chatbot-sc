import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { SafeHtml } from '@angular/platform-browser';

import { InlineDocument } from '../grouping/message-types';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { inlineDocFallbackLabel, inlineDocFontSize, inlineDocIcon } from './inline-doc';

/**
 * InlineDocuments — die gerahmten Markdown-Boxen im Chat-Verlauf für Lernpfade
 * (M09), KI-Materialien (M10) und Edits (M11). Visueller Port des ALT-Blocks
 * (`chat.component.html:37-52` + `.inline-document`-SCSS 450-564).
 *
 * Präsentational: die Shell (Chat-Shell 8-4) besitzt die zwei Seiteneffekt-/
 * Kontext-Seams —
 *   - `renderMarkdown`: liefert den fertig sanitisierten Markdown-Body (ALT
 *     `renderMarkdown(content,'bot')` = `MarkdownRenderer.render`, gebunden an
 *     die Instanz mit Session-/Trust-Kontext);
 *   - `print`: Output statt direktem Print-Fenster (ALT `printInlineDocument`
 *     → print-utils) — die Shell verdrahtet ihn.
 * Kind-Icon/Fallback-Label/Font-Scale leitet die Komponente selbst aus der
 * portierten `inline-doc`-Logik ab. `!isLoading`-Gating besitzt der Elternteil;
 * leeres `documents` rendert via `@for` schlicht nichts (kein Wrapper — jede
 * Box ist wie in ALT ein eigenständiges Top-Level-Element).
 */
@Component({
  selector: 'boerdi-inline-documents',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './inline-documents.component.scss',
  template: `
    @for (doc of documents(); track $index) {
      <div class="inline-document" [style.--inline-doc-scale]="fontScale()">
        <div class="inline-document__heading">
          <span class="bb-icon" [innerHTML]="inlineDocIcon(doc.kind) | safeSvg"></span>
          <span class="inline-document__title">{{ doc.title || fallbackLabel(doc.kind) }}</span>
          <button
            type="button"
            class="inline-document__print-btn"
            (click)="print.emit(doc)"
            [title]="t('inlineDoc.print')"
            [attr.aria-label]="t('inlineDoc.print')"
          >
            <span class="bb-icon" [innerHTML]="printIcon | safeSvg"></span>
          </button>
        </div>
        <div class="inline-document__body" [innerHTML]="renderBody(doc.content)"></div>
      </div>
    }
  `,
})
export class InlineDocumentsComponent {
  readonly documents = input.required<InlineDocument[]>();
  /** Message-Display-Rules (für die Body-Schriftgröße, ALT `inlineDocFontSize`). */
  readonly displayRules = input<Record<string, unknown> | null>(null);
  /** Render-Seam: fertig sanitisierter Markdown-Body (SafeHtml). */
  readonly renderMarkdown = input.required<(content: string) => SafeHtml>();
  /** Übersetzer der Shell (C1-b2) — eigener Input statt über einen Kontext:
   *  diese Box kennt weder `GroupingContext` noch bsid/Trust, und ein
   *  Funktions-Seam als Input ist hier schon das Muster (`renderMarkdown`). */
  readonly translate = input.required<TranslateFn>();

  /** ALT `printInlineDocument(doc)` — als Output ausgelagert (Shell 8-4). */
  readonly print = output<InlineDocument>();

  /** Kurzform fürs Template (Muster wie in Shell und Hülle). */
  protected readonly t = (key: string, params?: TranslationParams): string =>
    this.translate()(key, params);

  protected readonly printIcon = ICONS.print;
  protected readonly inlineDocIcon = inlineDocIcon;

  /** Rückfall-Titel der Box (C1-b3): die freie Funktion braucht seit C1-b3
   *  einen Übersetzer, also eine Methode statt der direkten Referenz. */
  protected fallbackLabel(kind: string): string {
    return inlineDocFallbackLabel(kind, this.translate());
  }

  /** ALT `[style.--inline-doc-scale]="inlineDocFontSize(msg) / 100"`. */
  protected readonly fontScale = computed(() => inlineDocFontSize(this.displayRules()) / 100);

  protected renderBody(content: string): SafeHtml {
    return this.renderMarkdown()(content);
  }
}
