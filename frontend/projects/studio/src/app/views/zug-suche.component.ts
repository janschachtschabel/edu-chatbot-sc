/**
 * Suche nach Fehlernummer (Paket 18C/D, Phase 4) — auf der Gesprächsseite.
 *
 * Eine Fehlerblase im Chat endet mit „(Fehlernummer: …)“: dem Anfang der
 * Trace-ID des Zugs. Wer sie meldet, gibt dem Studio damit den Weg zum Zug —
 * hier eingeben, und der Verlauf öffnet sich an der Nachricht. Mehrere Treffer
 * (eine kurze Nummer, eine von einem Client wiederverwendete Kennung) stehen als
 * Liste zur Wahl.
 *
 * Geprüft wird vor dem Abruf, was der Server ohnehin ablehnte (422): derselbe
 * Zeichenvorrat wie die Trace-ID. Die Eingabe bleibt bei jedem Fehler stehen.
 */
import { ChangeDetectionStrategy, Component, inject, output, signal } from '@angular/core';

import { describeApiError } from '../core/async-data';
import { SessionsApi, type ZugTreffer } from '../core/sessions-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Zeichenvorrat der Trace-ID — wie das Muster der Route (`api/sessions.zug_suchen`), dazu
 *  Buchstabe oder Ziffer am Anfang: `.` und `..` normalisierte der Browser im Pfad weg, die
 *  Anfrage träfe dann die Sitzungsliste (Review Phase 4). */
const NUMMER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export interface ZugZiel {
  readonly sessionId: string;
  readonly messageId: number;
}

@Component({
  selector: 'studio-zug-suche',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './zug-suche.component.html',
  styleUrl: './zug-suche.component.scss',
})
export class ZugSucheComponent {
  protected readonly t = inject(StudioLanguageService).t;
  protected readonly fmt = inject(StudioFormat);
  private readonly api = inject(SessionsApi);

  /** Ein Treffer gewählt (oder der einzige gefunden): Verlauf an der Nachricht öffnen. */
  readonly oeffnen = output<ZugZiel>();

  protected readonly eingabe = signal('');
  protected readonly sucht = signal(false);
  /** Ungültige Eingabe — am Feld, mit `aria-invalid`. */
  protected readonly feldFehler = signal('');
  /** Der Abruf scheiterte. */
  protected readonly fehler = signal('');
  protected readonly status = signal('');
  protected readonly treffer = signal<readonly ZugTreffer[]>([]);

  protected onInput(event: Event): void {
    this.eingabe.set((event.target as HTMLInputElement).value);
  }

  protected async suchen(): Promise<void> {
    if (this.sucht()) return;
    const nummer = this.eingabe().trim();
    this.fehler.set('');
    this.status.set('');
    this.treffer.set([]);
    if (!NUMMER.test(nummer)) {
      this.feldFehler.set(this.t('sv.search.invalid'));
      return;
    }
    this.feldFehler.set('');
    this.sucht.set(true);
    try {
      const gefunden = await this.api.findTurn(nummer);
      if (gefunden.length === 0) {
        this.status.set(this.t('sv.search.none', { nummer }));
      } else if (gefunden.length === 1) {
        this.waehlen(gefunden[0]);
      } else {
        this.treffer.set(gefunden);
        this.status.set(this.t('sv.search.many', { count: gefunden.length }));
      }
    } catch (err) {
      this.fehler.set(describeApiError(err, this.t));
    } finally {
      this.sucht.set(false);
    }
  }

  protected waehlen(treffer: ZugTreffer): void {
    this.status.set(this.t('sv.search.opened', { id: treffer.session_id }));
    this.oeffnen.emit({ sessionId: treffer.session_id, messageId: treffer.message_id });
  }

  protected zeit(iso: string): string {
    return this.fmt.dateTime(iso);
  }
}
