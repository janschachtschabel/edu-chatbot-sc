import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/**
 * `<span [innerHTML]="ICONS.close | safeSvg"></span>`
 *
 * Angular's Default-Sanitizer strippt aus `[innerHTML]` SVG-Attribute
 * wie `xmlns` und `viewBox` — und damit ist das SVG kaputt (entweder
 * unsichtbar oder verzerrt). Diese Pipe markiert den String als
 * "vertrauenswürdig" und reicht ihn unverändert durch.
 *
 * Verwendung NUR für die statischen SVG-Strings aus `icons/icons.ts` —
 * niemals auf user-supplied Markup anwenden (sonst XSS-Risiko).
 *
 * Verbatim-Port des ALT `shared/safe-svg.pipe.ts` (nur der Doc-Pfad zeigt
 * jetzt auf `icons/icons.ts` statt `shared/icons.ts`).
 */
@Pipe({ name: 'safeSvg' })
export class SafeSvgPipe implements PipeTransform {
  private readonly sanitizer = inject(DomSanitizer);

  transform(value: string | null | undefined): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(value ?? '');
  }
}
