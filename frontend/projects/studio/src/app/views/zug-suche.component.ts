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

/** Die Nummer aus einer kopierten Zeile der Fehlerblase: „(Fehlernummer: 4f2a…)“ bzw.
 *  „(Error number: 4f2a…)“ — bis dahin scheiterte genau das am Muster (Review 2026-10-30). */
const BESCHRIFTUNG = /fehlernummer|error number/i;
/** Klammern, Anführungszeichen (de/en) und Satzzeichen um eine Nummer. */
const RAND = /^[(„“‘"':]+|[)“”’"'.,;:]+$/g;

export function nummerAus(eingabe: string): string {
  const roh = eingabe.trim();
  const beschriftung = BESCHRIFTUNG.exec(roh);
  if (beschriftung) {
    // Das erste Wort danach mit einer Ziffer — nicht „lautet“, „is“ oder das „n“ aus
    // „Fehlernummern“ (Abschluss-Review 18G); ein Satzzeichen am Ende gehört zum Satz.
    const wort = roh.slice(beschriftung.index + beschriftung[0].length).split(/\s+/)
      .map((w) => w.replace(RAND, ''))
      .find((w) => /\d/.test(w) && NUMMER.test(w));
    if (wort) return wort;
  }
  return roh.replace(RAND, '');
}

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
    const nummer = nummerAus(this.eingabe());
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
        // Mehrere Sitzungen: die Nummer ist nicht eindeutig — etwa eine von einem Client
        // wiederverwendete Kennung (Review 2026-10-30). Das sagen, statt still eine Liste.
        const sitzungen = new Set(gefunden.map((t) => t.session_id)).size;
        this.status.set(sitzungen > 1
          ? this.t('sv.search.manySessions', { count: gefunden.length, sessions: sitzungen })
          : this.t('sv.search.many', { count: gefunden.length }));
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
