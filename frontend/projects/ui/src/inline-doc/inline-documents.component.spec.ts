import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { beforeEach, describe, expect, it } from 'vitest';

import { InlineDocument } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { TranslateFn } from '../i18n/i18n';
import { InlineDocumentsComponent } from './inline-documents.component';

/**
 * Charakterisierung des Inline-Document-Renderers — visueller Port des ALT
 * `.inline-document`-Blocks (`chat.component.html:37-52`). In ALT integrativ
 * gedeckt; hier am DOM gepinnt: Box je Doc (Kind-Icon + Titel/Fallback +
 * Print-Button + gerenderter Markdown-Body über die Render-Seam), CSS-Scale
 * aus display_rules, print-Output, Leerzustand.
 */
describe('InlineDocumentsComponent', () => {
  let sanitizer: DomSanitizer;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [InlineDocumentsComponent],
      providers: [provideZonelessChangeDetection()],
    });
    sanitizer = TestBed.inject(DomSanitizer);
  });

  async function render(
    documents: InlineDocument[],
    displayRules: Record<string, unknown> | null = null,
    translate: TranslateFn = createTranslator(DE, DE),
  ): Promise<{ host: HTMLElement; printed: InlineDocument[] }> {
    const printed: InlineDocument[] = [];
    const fixture = TestBed.createComponent(InlineDocumentsComponent);
    fixture.componentRef.setInput('documents', documents);
    fixture.componentRef.setInput('displayRules', displayRules);
    fixture.componentRef.setInput('translate', translate);
    fixture.componentRef.setInput(
      'renderMarkdown',
      (c: string): SafeHtml => sanitizer.bypassSecurityTrustHtml(`<p class="md">${c}</p>`),
    );
    fixture.componentInstance.print.subscribe((d: InlineDocument) => printed.push(d));
    fixture.detectChanges();
    await fixture.whenStable();
    return { host: fixture.nativeElement as HTMLElement, printed };
  }

  it('rendert je Doc Heading (Icon+Titel), Print-Button, Scale und Markdown-Body', async () => {
    const docs: InlineDocument[] = [
      { kind: 'lernpfad', title: 'Mein Pfad', content: '# Schritt 1' },
      { kind: 'edit', title: '', content: 'Body zwei' },
    ];
    const { host } = await render(docs, { inline_documents: { font_size_percent: 90 } });

    const boxes = host.querySelectorAll('.inline-document');
    expect(boxes.length).toBe(2);
    expect((boxes[0] as HTMLElement).style.getPropertyValue('--inline-doc-scale')).toBe('0.9');

    expect(boxes[0].querySelector('.inline-document__heading .bb-icon svg')).not.toBeNull();
    expect(boxes[0].querySelector('.inline-document__title')?.textContent?.trim()).toBe('Mein Pfad');
    // Leerer Titel → Fallback-Label des kind
    expect(boxes[1].querySelector('.inline-document__title')?.textContent?.trim()).toBe('Bearbeitete Version');
    // Markdown-Body über die Render-Seam
    expect(boxes[0].querySelector('.inline-document__body .md')?.textContent).toBe('# Schritt 1');

    const btn = boxes[0].querySelector('.inline-document__print-btn') as HTMLButtonElement;
    expect(btn.getAttribute('type')).toBe('button');
    expect(btn.getAttribute('aria-label')).toBe('Als PDF drucken / speichern');
    expect(btn.querySelector('svg')).not.toBeNull();
  });

  /** Das Fallback-Label („Bearbeitete Version") bleibt bewusst außen vor: es
   *  kommt aus `inline-doc.ts` und ist Sache von C1-b3. */
  it('nimmt die Druck-Beschriftung aus `[translate]` (C1-b2)', async () => {
    const { host } = await render(
      [{ kind: 'lernpfad', title: 'P', content: 'x' }],
      null,
      (key) => (key === 'inlineDoc.print' ? 'Print / save as PDF' : key),
    );
    const btn = host.querySelector('.inline-document__print-btn')!;
    expect(btn.getAttribute('aria-label')).toBe('Print / save as PDF');
    expect(btn.getAttribute('title')).toBe('Print / save as PDF');
  });

  it('leere documents → nichts gerendert', async () => {
    const { host } = await render([]);
    expect(host.querySelector('.inline-document')).toBeNull();
  });

  it('Print-Button-Klick → print-Output emittiert das Doc', async () => {
    const doc: InlineDocument = { kind: 'bericht', title: 'B', content: 'x' };
    const { host, printed } = await render([doc]);
    (host.querySelector('.inline-document__print-btn') as HTMLButtonElement).click();
    expect(printed).toEqual([doc]);
  });
});
