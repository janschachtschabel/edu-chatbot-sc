/**
 * „Fehlende Einbettungen nachholen" (Paket 4, C2).
 *
 * Steht unter dem Ergebnis eines Imports, wenn Vektoren fehlten. Bis dahin
 * verlor der Import solche Abschnitte ganz; jetzt liegen sie ohne Vektor in der
 * Datenbank, und die Suche findet sie erst nach dem Nachholen
 * (`POST /api/rag/embed`, über alle Bereiche). Wie viele es sind, sagt die
 * Ergebniszeile des Imports: Sie ist die angesagte Live-Region, ein Absatz hier
 * entstünde erst mit dem Ergebnis und bliebe stumm (Prüfer 2026-10-04).
 *
 * Die Statuszeile steht von Anfang an leer im DOM: Eine Live-Region, die erst
 * mit ihrem Text entsteht, sagen Screenreader oft nicht an (Audit 2026-09-29,
 * F-M6).
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { describeRagError, RagApi } from '../core/rag-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-rag-embed-missing',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="rem">
      @if (!fertig()) {
        <button type="button" class="cs-btn" [disabled]="busy()" (click)="nachholen()">
          {{ busy() ? t('rag.embedMissing.busy') : t('rag.embedMissing.go') }}
        </button>
      }
      <p class="cs-state rem-status" aria-live="polite">{{ status() }}</p>
      @if (error()) {
        <p class="cs-state cs-state--error" role="alert">{{ error() }}</p>
      }
    </div>
  `,
  styleUrl: './rag-embed-missing.component.scss',
})
export class RagEmbedMissingComponent {
  private readonly rag = inject(RagApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;

  readonly busy = signal(false);
  /** Alles nachgeholt — dann gibt es nichts mehr anzubieten. */
  readonly fertig = signal(false);
  readonly status = signal('');
  readonly error = signal('');

  async nachholen(): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.status.set('');
    try {
      const { embedded, total } = await this.rag.embedMissing();
      const gesamt = total ?? embedded;
      this.fertig.set(embedded >= gesamt);
      this.status.set(embedded >= gesamt
        ? this.plural('rag.embedMissing.done', embedded)
        : this.t('rag.embedMissing.partial', { embedded, total: gesamt }));
    } catch (err) {
      this.error.set(describeRagError(err, this.t));
    } finally {
      this.busy.set(false);
    }
  }
}
