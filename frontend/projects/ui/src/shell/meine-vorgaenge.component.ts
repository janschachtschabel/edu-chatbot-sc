import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, ElementRef, inject, Injector, input, output,
} from '@angular/core';

import type { TranslationParams } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { fortsetzenDatum } from './fortsetzen';
import type { EigenerVorgang, MeineVorgaengeController } from './meine-vorgaenge';

/** Status des Vorgangs → Schlüssel; ein unbekannter Status heißt „Offen“. */
const STATUS_TEXT: Readonly<Record<string, string>> = {
  aktiv: 'vorgaenge.status.aktiv',
  wartet_auftrag: 'vorgaenge.status.wartet_auftrag',
  wartet_person: 'vorgaenge.status.wartet_person',
};

/** Querschnitts-Review Q-7: der Status des Laufs ist feiner (Freigabe, KI) und kennt das Ende —
 *  dieselben Zustände wie die Ablauf-Leiste, am Zeilenanfang groß geschrieben. */
const LAUF_TEXT: Readonly<Record<string, string>> = {
  laeuft: 'vorgaenge.lauf.laeuft',
  wartet_wahl: 'vorgaenge.lauf.person',
  wartet_person: 'vorgaenge.lauf.person',
  wartet_ki: 'vorgaenge.lauf.ki',
  wartet_auftrag: 'vorgaenge.status.wartet_auftrag',
  wartet_freigabe: 'vorgaenge.lauf.freigabe',
  wartet_seite: 'vorgaenge.lauf.seite',   // AS-7b
  fertig: 'vorgaenge.lauf.beendet',
  fehler: 'vorgaenge.lauf.beendet',
  abgebrochen: 'vorgaenge.lauf.beendet',
};

/**
 * Paket AS-Ud (Plan 2026-11-09 §5j, Ud-4): die Liste „Meine Vorgänge“ über dem Eingabefeld — die
 * eigenen, nicht abgeschlossenen Vorgänge anderer Gespräche mit „Fortsetzen“ und „Löschen“.
 *
 * - Zustände: lädt, Fehler (mit „Erneut versuchen“), leer — alle in EINER ständigen Statuszeile.
 * - Löschen fragt im Panel nach (Rückfrage am Eintrag, Fokus auf „Ja, löschen“); „Behalten“ führt
 *   zum Löschen-Knopf zurück, nach dem Löschen steht der Fokus auf dem Titel des Panels und die
 *   Statuszeile sagt es an.
 * - Beim Öffnen bekommt der Titel den Fokus; Esc schließt das Panel und endet hier (sonst schlösse
 *   es das ganze Chat-Fenster, `widget.component.ts`).
 * - Die Knöpfe nennen den Vorgang („„Lesen“ löschen“) — sonst hießen bei drei Einträgen drei Knöpfe
 *   gleich.
 *
 * Präsentational: der Zustand liegt im {@link MeineVorgaengeController}, den die Shell hält.
 */
@Component({
  selector: 'boerdi-meine-vorgaenge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './meine-vorgaenge.component.scss',
  // Esc am Host: das Ereignis steigt aus jedem Knopf im Panel hierher auf.
  host: { '(keydown.escape)': 'esc($event)' },
  template: `
    @let c = vorgaenge();
    <section class="meine-vorgaenge" [id]="panelId()" [attr.aria-labelledby]="panelId() + '-titel'">
      <div class="meine-vorgaenge__kopf">
        <p class="meine-vorgaenge__titel" [id]="panelId() + '-titel'" tabindex="-1">{{ t('vorgaenge.titel') }}</p>
        <button type="button" class="meine-vorgaenge__zu" (click)="schliessen.emit()"
                [title]="t('vorgaenge.schliessen')" [attr.aria-label]="t('vorgaenge.schliessen')">×</button>
      </div>
      <!-- Review AS-Ud, Befund 4: EINE ständige Live-Region für Laden, Fehler, leere Liste und
           Meldungen — eine gefüllt eingefügte sagen Vorleser oft nicht an. -->
      <p class="meine-vorgaenge__meldung" role="status" aria-live="polite">{{ ansage() }}</p>
      @switch (c.stand()) {
        @case ('fehler') {
          <button type="button" class="meine-vorgaenge__knopf" (click)="erneut()">{{ t('vorgaenge.erneut') }}</button>
        }
        @case ('bereit') {
          @if (c.liste().length) {
            <ul class="meine-vorgaenge__liste">
              @for (v of c.liste(); track v.id) {
                <li class="meine-vorgaenge__eintrag" [attr.data-vorgang]="v.id">
                  <span class="meine-vorgaenge__name">{{ v.titel }}</span>
                  <span class="meine-vorgaenge__stand">{{ standText(v) }}</span>
                  @if (c.frage() === v.id) {
                    <p class="meine-vorgaenge__frage" [id]="panelId() + '-frage-' + v.id">{{ t('vorgaenge.frage', { titel: v.titel }) }}</p>
                    <div class="meine-vorgaenge__knoepfe">
                      <button type="button" class="meine-vorgaenge__knopf meine-vorgaenge__ja"
                              [attr.aria-describedby]="panelId() + '-frage-' + v.id"
                              [attr.aria-disabled]="c.loescht() || beschaeftigt() ? 'true' : null" (click)="loeschen(v)">
                        {{ t('vorgaenge.ja') }}
                      </button>
                      <button type="button" class="meine-vorgaenge__knopf" (click)="behalten(v)">{{ t('vorgaenge.nein') }}</button>
                    </div>
                  } @else {
                    <div class="meine-vorgaenge__knoepfe">
                      <button type="button" class="meine-vorgaenge__knopf meine-vorgaenge__los" [disabled]="beschaeftigt()"
                              [attr.aria-label]="t('vorgaenge.fortsetzenName', { titel: v.titel })" (click)="fortsetzen.emit(v)">
                        {{ t('vorgaenge.fortsetzen') }}
                      </button>
                      <button type="button" class="meine-vorgaenge__knopf meine-vorgaenge__weg" [disabled]="beschaeftigt()"
                              [attr.aria-label]="t('vorgaenge.loeschenName', { titel: v.titel })" (click)="fragen(v)">
                        {{ t('vorgaenge.loeschen') }}
                      </button>
                    </div>
                  }
                </li>
              }
            </ul>
          }
        }
      }
    </section>
  `,
})
export class MeineVorgaengeComponent {
  readonly vorgaenge = input.required<MeineVorgaengeController>();
  readonly translate = input.required<TranslateFn>();
  readonly locale = input('de');
  /** Ein Zug läuft — „Fortsetzen“ wartet (wie der Hinweis „Gespräch fortsetzen“). */
  readonly beschaeftigt = input(false);
  /** Kennung des Panels — der Knopf in der Shell verweist mit `aria-controls` darauf. */
  readonly panelId = input('boerdi-meine-vorgaenge');
  readonly fortsetzen = output<EigenerVorgang>();
  readonly schliessen = output<void>();

  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  /** Was die Statuszeile sagt: die letzte Meldung (gelöscht / nicht gelöscht) und der Zustand der
   *  Liste (lädt, Fehler, leer). */
  protected readonly ansage = computed(() => {
    const c = this.vorgaenge();
    const m = c.meldung();
    const zustand = c.stand() === 'laedt' ? 'vorgaenge.laedt' : c.stand() === 'fehler' ? 'vorgaenge.fehler'
      : c.liste().length ? '' : 'vorgaenge.leer';
    return [m ? this.t(m.schluessel, { titel: m.titel }) : '', zustand ? this.t(zustand) : '']
      .filter(Boolean).join(' ');
  });

  constructor() {
    afterNextRender(() => this.fokus('.meine-vorgaenge__titel'));
  }

  protected t(key: string, params?: TranslationParams): string {
    return this.translate()(key, params);
  }

  protected standText(v: EigenerVorgang): string {
    const schluessel = (v.lauf_status && LAUF_TEXT[v.lauf_status]) || STATUS_TEXT[v.status] || 'vorgaenge.status.aktiv';
    const status = this.t(schluessel);
    return this.t('vorgaenge.stand', { status, datum: fortsetzenDatum(v.geaendert, this.locale()) });
  }

  protected fragen(v: EigenerVorgang): void {
    this.vorgaenge().fragen(v.id);
    this.spaeter(() => this.fokus(`[data-vorgang="${v.id}"] .meine-vorgaenge__ja`));
  }

  protected behalten(v: EigenerVorgang): void {
    this.vorgaenge().nichtLoeschen();
    this.spaeter(() => this.fokus(`[data-vorgang="${v.id}"] .meine-vorgaenge__weg`));
  }

  protected async loeschen(v: EigenerVorgang): Promise<void> {
    // Review AS-Ud, Befund 2a: nicht während eines Zugs — er arbeitet vielleicht auf diesem Vorgang
    if (this.vorgaenge().loescht() || this.beschaeftigt()) return;
    await this.vorgaenge().loeschen(v.id);
    // Der Eintrag ist weg (oder die Liste neu geladen) — der Fokus nicht ins Leere.
    this.spaeter(() => this.fokus('.meine-vorgaenge__titel'));
  }

  /** Review AS-Ud, Befund 5: der Knopf verschwindet beim Laden — danach der Fokus auf den Titel. */
  protected async erneut(): Promise<void> {
    await this.vorgaenge().laden();
    this.spaeter(() => this.fokus('.meine-vorgaenge__titel'));
  }

  /** Esc schließt die innerste Ebene: erst die Rückfrage (Kleinigkeit 10), dann das Panel. */
  protected esc(e: Event): void {
    e.preventDefault();
    e.stopPropagation();
    const c = this.vorgaenge();
    const gefragt = c.liste().find((v) => v.id === c.frage());
    if (gefragt) this.behalten(gefragt);
    else this.schliessen.emit();
  }

  private spaeter(f: () => void): void {
    afterNextRender(f, { injector: this.injector });
  }

  private fokus(selektor: string): void {
    this.el.nativeElement.querySelector<HTMLElement>(selektor)?.focus();
  }
}
