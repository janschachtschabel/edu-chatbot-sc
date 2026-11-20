import { DOCUMENT } from '@angular/common';
import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, Injector,
  input, output, Renderer2, signal, untracked, viewChild,
} from '@angular/core';

import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import type { TranslateFn } from '../i18n/i18n';
import { initialen } from '../session/initialen';

/**
 * Paket D1 (Plan 2026-11-20, E-D1): der Konto-Knopf der Fußzeile — EIN Knopf statt des Kürzel-Kreises
 * und des Anmelde-Knopfs daneben, in der Größe der Nachbarknöpfe.
 *
 * - Abgemeldet: Umriss einer Person, ausgegraut, gestrichelter Rand. Der Klick meldet an — synchron
 *   über `anmelden`, denn er ist die Nutzergeste, ohne die der Browser das Anmeldefenster blockt.
 * - Angemeldet: die Initialen (ohne bekannten Namen das gefüllte Personen-Symbol). Der Klick öffnet
 *   ein kleines Menü nach dem APG-Muster „Menu Button“: wer angemeldet ist und „Abmelden“.
 *   Pfeiltasten, Pos1/Ende, Esc schließt und gibt den Fokus zurück; Klick außerhalb und Tab hinaus
 *   schließen. Kein CDK-Menü: das Widget-Bündel steht an seiner gzip-Grenze, und ein Menü mit
 *   einem Eintrag braucht kein Overlay.
 *
 * Präsentational: was Anmelden und Abmelden tun, entscheidet die Shell (`onAuthClick`).
 */
@Component({
  selector: 'boerdi-konto-knopf',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './konto-knopf.component.scss',
  host: {
    class: 'konto',
    '(focusout)': 'fokusWeg($event)',
  },
  template: `
    <button #knopf type="button" class="btn-auth" [class.btn-auth--aus]="!angemeldet()"
            [title]="knopfName()" [attr.aria-label]="knopfName()"
            [attr.aria-haspopup]="angemeldet() ? 'menu' : null"
            [attr.aria-expanded]="angemeldet() ? offen() : null"
            [attr.aria-controls]="offen() ? menueId() : null"
            (click)="klick()" (keydown)="knopfTaste($event)">
      @if (kuerzel()) {
        <span class="btn-auth__kuerzel" aria-hidden="true">{{ kuerzel() }}</span>
      } @else {
        <span class="bb-icon" aria-hidden="true"
              [innerHTML]="(angemeldet() ? ICONS.person : ICONS.person_outline) | safeSvg"></span>
      }
    </button>
    @if (offen()) {
      <div class="konto-menue">
        <p class="konto-menue__wer" [id]="menueId() + '-wer'">{{ wer() }}</p>
        <ul class="konto-menue__liste" role="menu" [id]="menueId()" [attr.aria-labelledby]="menueId() + '-wer'">
          <li role="none">
            <button type="button" role="menuitem" tabindex="-1" class="konto-menue__eintrag"
                    (click)="abmeldenGewaehlt()" (keydown)="menueTaste($event)">
              <span class="bb-icon" aria-hidden="true" [innerHTML]="ICONS.logout | safeSvg"></span>
              {{ t('auth.konto.abmelden') }}
            </button>
          </li>
        </ul>
      </div>
    }
  `,
})
export class KontoKnopfComponent {
  readonly angemeldet = input.required<boolean>();
  /** Anzeigename der angemeldeten Person — leer, solange keiner bekannt ist. */
  readonly name = input('');
  readonly translate = input.required<TranslateFn>();
  readonly menueId = input('boerdi-konto-menue');
  readonly anmelden = output<void>();
  readonly abmelden = output<void>();

  protected readonly ICONS = ICONS;
  protected readonly offen = signal(false);

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly renderer = inject(Renderer2);
  private readonly dokument = inject(DOCUMENT);
  /** Lauscher für Klicks daneben — nur bei offenem Menü angemeldet (Review D, 2): sonst plante jeder
   *  Klick auf der Gastseite einen Durchlauf. */
  private _draussenAbmelden: (() => void) | null = null;
  private readonly knopf = viewChild.required<ElementRef<HTMLButtonElement>>('knopf');

  protected readonly kuerzel = computed(() => (this.angemeldet() ? initialen(this.name()) : ''));
  private readonly _name = computed(() => (this.angemeldet() ? this.name().trim() : ''));
  protected readonly knopfName = computed(() => {
    if (!this.angemeldet()) return this.t('auth.konto.aus');
    const name = this._name();
    return name ? this.t('auth.konto.an', { name }) : this.t('auth.konto.anOhneName');
  });
  protected readonly wer = computed(() => {
    const name = this._name();
    return name ? this.t('auth.signedInAs', { name }) : this.t('auth.signedIn');
  });

  /** Abgemeldet (Abweisung, Abmelden anderswo) gibt es kein Menü mehr. Lag der Fokus darin, geht er an
   *  den Knopf, statt mit dem Menü zu verschwinden (Review D, 7). */
  private readonly _zuBeimAbmelden = effect(() => {
    if (this.angemeldet() || !untracked(this.offen)) return;
    const wurzel = this.host.nativeElement.getRootNode() as Document | ShadowRoot;
    const fokus = wurzel.activeElement;
    this.schliessen(!!fokus && !!this.host.nativeElement.querySelector('.konto-menue')?.contains(fokus));
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => this._draussenLos());
  }

  protected t(key: string, params?: TranslationParams): string {
    return this.translate()(key, params);
  }

  protected klick(): void {
    if (!this.angemeldet()) {
      this.anmelden.emit();
      return;
    }
    if (this.offen()) this.schliessen(true);
    else this.oeffnen('erster');
  }

  protected knopfTaste(e: KeyboardEvent): void {
    if (!this.angemeldet()) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      this.oeffnen(e.key === 'ArrowDown' ? 'erster' : 'letzter');
    } else if (e.key === 'Escape' && this.offen()) {
      this.escape(e);
    }
  }

  protected menueTaste(e: KeyboardEvent): void {
    // Review D, 8: ein gehaltenes Enter (vom Öffnen) wiederholt sich auf dem Eintrag — kein Abmelden daraus
    if (e.repeat && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      return;
    }
    const eintraege = this.eintraege();
    const jetzt = eintraege.indexOf(e.target as HTMLElement);
    const ziel = {
      ArrowDown: (jetzt + 1) % eintraege.length,
      ArrowUp: (jetzt - 1 + eintraege.length) % eintraege.length,
      Home: 0,
      End: eintraege.length - 1,
    }[e.key];
    if (ziel !== undefined) {
      e.preventDefault();
      eintraege[ziel]?.focus();
    } else if (e.key === 'Escape') {
      this.escape(e);
    }
  }

  protected abmeldenGewaehlt(): void {
    this.schliessen(true);
    this.abmelden.emit();
  }

  /** Ein Klick außerhalb schließt — der Pfad, weil das Widget im Shadow-DOM sitzt und `target` am
   *  Dokument nur noch dessen Wirt nennt. */
  private draussenGeklickt(e: Event): void {
    if (this.offen() && !e.composedPath().includes(this.host.nativeElement)) this.schliessen(false);
  }

  /** Tab hinaus schließt — in beide Richtungen: Umschalt+Tab aus einem Eintrag landet auf dem Knopf
   *  (Review D, 1). Ohne neues Ziel (`relatedTarget` leer, z. B. Safari beim Klick auf einen Knopf)
   *  bleibt es offen — sonst verschwände der Eintrag vor seinem eigenen Klick; Klicks daneben fängt
   *  `draussenGeklickt`. */
  protected fokusWeg(e: FocusEvent): void {
    const neu = e.relatedTarget as Node | null;
    if (!this.offen() || !neu) return;
    const ausEintrag = (e.target as Element | null)?.getAttribute?.('role') === 'menuitem';
    if (!this.host.nativeElement.contains(neu) || (ausEintrag && neu === this.knopf().nativeElement)) {
      this.schliessen(false);
    }
  }

  private escape(e: KeyboardEvent): void {
    // endet hier: die Widget-Hülle schließt bei Esc sonst das ganze Chat-Fenster
    e.preventDefault();
    e.stopPropagation();
    this.schliessen(true);
  }

  private oeffnen(wohin: 'erster' | 'letzter'): void {
    this.offen.set(true);
    this._draussenAbmelden ??= this.renderer.listen(this.dokument, 'pointerdown', (e: Event) => this.draussenGeklickt(e));
    afterNextRender(() => {
      const eintraege = this.eintraege();
      eintraege[wohin === 'erster' ? 0 : eintraege.length - 1]?.focus();
    }, { injector: this.injector });
  }

  private schliessen(fokusZurueck: boolean): void {
    this.offen.set(false);
    this._draussenLos();
    if (fokusZurueck) this.knopf().nativeElement.focus();
  }

  private _draussenLos(): void {
    this._draussenAbmelden?.();
    this._draussenAbmelden = null;
  }

  private eintraege(): HTMLElement[] {
    return Array.from(this.host.nativeElement.querySelectorAll<HTMLElement>('[role="menuitem"]'));
  }
}
