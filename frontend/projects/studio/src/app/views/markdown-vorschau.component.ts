/**
 * Markdown lesbar zeigen (Paket 14, D2) — für die Vorlagen der Materialformate.
 *
 * Derselbe Renderer wie im Widget (`@boerdi/ui` `MarkdownRenderer`: marked + DOMPurify, ohne
 * Bilder, Medien und Stile), im Studio ohne Sitzung und ohne vertraute Hosts: hier gibt es
 * keinen Gesprächskontext, den ein Link mitnehmen dürfte. Ohne Render-Cache — das `computed`
 * rechnet nur bei geändertem Text neu, und beim Tippen wüchse ein Cache mit jedem Zeichen.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { MarkdownRenderer } from '@boerdi/ui';

import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-markdown-vorschau',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (leer()) {
      <p class="mv-leer">{{ t('materialFormate.vorlageLeer') }}</p>
    } @else {
      <div class="mv" [innerHTML]="html()"></div>
    }
  `,
  styles: `
    .mv {
      max-inline-size: 72ch;
      line-height: 1.55;
      overflow-wrap: anywhere;
    }
    .mv :is(h1, h2, h3) { margin: var(--st-3) 0 var(--st-2); line-height: 1.25; }
    .mv h1 { font-size: 1.25rem; }
    .mv h2 { font-size: 1.0625rem; }
    .mv h3 { font-size: 1rem; }
    .mv :is(p, ul, ol) { margin: 0 0 var(--st-2); }
    .mv :is(ul, ol) { padding-inline-start: var(--st-5); }
    .mv code {
      padding: 0 var(--st-1);
      border-radius: var(--st-radius);
      background: var(--st-surface-variant);
    }
    .mv-leer { margin: 0; color: var(--st-text-muted); }
  `,
})
export class MarkdownVorschauComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly sanitizer = inject(DomSanitizer);

  readonly text = input('');

  private readonly renderer = new MarkdownRenderer({
    bypassSecurityTrustHtml: (html) => this.sanitizer.bypassSecurityTrustHtml(html),
    sessionId: () => '',
    isHostTrusted: () => false,
    withBsid: (url) => url ?? '',
    t: (key, params) => this.t(key, params as Record<string, string | number> | undefined),
  });

  readonly leer = computed(() => !this.text().trim());
  readonly html = computed(() => this.renderer.render(this.text(), 'bot', false));
}
