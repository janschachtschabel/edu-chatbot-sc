import {
  ChangeDetectionStrategy, Component, computed, effect, input, output, signal, untracked,
} from '@angular/core';

import type { AblaufStand } from '../grouping/message-types';
import type { TranslationParams } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';

/** Status des Laufs → Schlüssel des Texts; ein unbekannter Status zeigt nur den Schritt. */
const STATUS_TEXT: Readonly<Record<string, string>> = {
  laeuft: 'ablauf.leiste.status.laeuft',
  wartet_wahl: 'ablauf.leiste.status.person',
  wartet_person: 'ablauf.leiste.status.person',
  wartet_ki: 'ablauf.leiste.status.ki',
  wartet_auftrag: 'ablauf.leiste.status.auftrag',
  wartet_freigabe: 'ablauf.leiste.status.freigabe',
  // AS-7b (Plan 2026-11-09 §5m): eine Führung wartet, bis die Person auf der Seite ist
  wartet_seite: 'ablauf.leiste.status.seite',
};

/** Ablauf und Lauf — die Pause gilt nur diesem Lauf; ein neuer Lauf desselben Ablaufs („Neu
 *  starten“) erscheint offen (zweites Review AS-U, Befund 2). */
function laufKennung(s: AblaufStand | null): string | null {
  return s ? `${s.id}|${s.lauf ?? ''}` : null;
}

/**
 * Paket AS-Ub (Plan 2026-11-09 §5h, D10): die Ablauf-Leiste über dem Eingabefeld, solange im
 * Gespräch ein Lauf nicht beendet ist (``ui.ablauf`` der letzten Serverantwort, AS-Ua).
 *
 * - Titel, „Schritt n von m“ und der Status in Worten; der Stand ist eine höfliche Live-Region —
 *   ein neuer Schritt wird angesagt, ohne die Person zu unterbrechen.
 * - „Ablauf abbrechen“ geht als Ereignis an die Shell (Direktaktion mit Rückfrage, U-5).
 * - „Einklappen“ (bis Q-12: „Später fortsetzen“) klappt die Leiste zu einer Zeile zusammen (U-6). Es ist **ein**
 *   Umschaltknopf, der im DOM bleibt — der Fokus geht nicht verloren
 *   (Review AS-Ub, Befund 2). Endet der Lauf oder startet ein anderer, ist sie wieder offen
 *   (Befund 3).
 * - Die gesammelten Daten als natives ``<details>``, je Teil der lesbare Kurztext (die
 *   technischen Teilnamen bleiben weg — Befund 5).
 *
 * Die Schritte selbst bleiben Nachrichten und Module im Gespräch; die Leiste ersetzt sie nicht.
 */
@Component({
  selector: 'boerdi-ablauf-leiste',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './ablauf-leiste.component.scss',
  template: `
    @if (stand(); as s) {
      <section class="ablauf-leiste" [attr.aria-label]="t('ablauf.leiste.region')">
        <div class="ablauf-leiste__kopf">
          <div class="ablauf-leiste__text">
            @if (!pausiert()) {
              <span class="ablauf-leiste__titel">{{ s.titel }}</span>
              <span class="ablauf-leiste__stand" aria-live="polite">{{ standText() }}</span>
            } @else {
              <span class="ablauf-leiste__pause">{{ t('ablauf.leiste.pausiert', { titel: s.titel }) }}</span>
            }
          </div>
          <!-- Zweites Review AS-U, Befund 3: die Beschriftung sagt den Zustand — kein zusätzliches
               aria-expanded (sonst „Später fortsetzen, erweitert“). -->
          <button type="button" class="ablauf-leiste__umschalten" (click)="umschalten()">
            {{ t(pausiert() ? 'ablauf.leiste.zeigen' : 'ablauf.leiste.spaeter') }}
          </button>
          @if (!pausiert() && s.weg) {
            <!-- AS-7 (Querschnitts-Review, Befund 1): der Weg einer wartenden Führung -->
            <button type="button" class="ablauf-leiste__weg" (click)="fuehren.emit(s.weg.url)">
              {{ s.weg.label }}
            </button>
          }
          @if (!pausiert()) {
            <button type="button" class="ablauf-leiste__abbrechen" [disabled]="beschaeftigt()"
                    (click)="abbrechen.emit()">
              {{ t('ablauf.leiste.abbrechen') }}
            </button>
          }
        </div>
        @if (!pausiert() && s.teile.length) {
          <details class="ablauf-leiste__daten">
            <summary>{{ t('ablauf.leiste.daten', { anzahl: s.teile.length }) }}</summary>
            <ul>
              @for (teil of s.teile; track teil.name) {
                <li>{{ teil.text }}</li>
              }
            </ul>
          </details>
        }
      </section>
    }
  `,
})
export class AblaufLeisteComponent {
  readonly stand = input<AblaufStand | null>(null);
  readonly translate = input.required<TranslateFn>();
  /** Ein Zug läuft — „Abbrechen“ wartet, bis er fertig ist. */
  readonly beschaeftigt = input(false);
  readonly abbrechen = output<void>();
  /** AS-7: Klick auf den Weg einer wartenden Führung — die Shell navigiert wie beim Führungs-Chip. */
  readonly fuehren = output<string>();

  /** Für welchen Ablauf die Leiste zugeklappt ist — derselbe Ablauf bleibt zugeklappt, solange er
   *  läuft. */
  private readonly _pausiertFuer = signal<string | null>(null);
  /** Ohne Lauf oder mit einem anderen Ablauf wieder offen (Review AS-Ub, Befund 3). Ein Effekt und
   *  kein ``linkedSignal``: ohne Stand liest das Template die Pause gar nicht — ein abgeleitetes
   *  Signal sähe das Ende des Laufs nie. */
  private readonly _zuruecksetzen = effect(() => {
    const id = laufKennung(this.stand());
    if (id !== untracked(this._pausiertFuer)) untracked(() => this._pausiertFuer.set(null));
  });
  protected readonly pausiert = computed(() => {
    const s = this.stand();
    return s !== null && this._pausiertFuer() === laufKennung(s);
  });

  protected readonly standText = computed(() => {
    const s = this.stand();
    if (!s) return '';
    const schritt = this.t('ablauf.leiste.schritt', { nr: s.nr, von: s.von });
    const schluessel = STATUS_TEXT[s.status];
    return schluessel
      ? this.t('ablauf.leiste.stand', { schritt, status: this.t(schluessel) })
      : schritt;
  });

  protected t(key: string, params?: TranslationParams): string {
    return this.translate()(key, params);
  }

  protected umschalten(): void {
    this._pausiertFuer.set(this.pausiert() ? null : laufKennung(this.stand()));
  }
}
