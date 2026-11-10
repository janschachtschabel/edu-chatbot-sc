/**
 * Die Schrittfolge eines Ablaufs — als Text (Paket K2c-4) und als Bild (AS-2b), unter „Prüfen“.
 *
 * Live aus dem Entwurf (`ablauf-folge.ts`): je Schritt die Pfeile zum nächsten, bei Fehler, je
 * Regel; unbekannte Ziele sind markiert, die Befunde der letzten Prüfung stehen am Schritt.
 *
 * AS-2b: Ein Klick auf einen Kasten des Bilds und „Zum Schritt“ (die Tastatur-Entsprechung) wählen
 * den Schritt in der Liste der Schritte (`FORM_LISTENWAHL`). Das Bild ist bei mehr als zwölf
 * Schritten zugeklappt — dann ist es eher eine Wand als ein Überblick.
 *
 * AS-2c: Ein Modul-Schritt verweist auf die Seite seines Moduls (`/ui-module?modul=…`) — nur im
 * Studio mit Router; ein Formular ohne Router (Tests, Vorschau) zeigt den Namen ohne Verweis.
 */
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { AblaufBildComponent } from './ablauf-bild.component';
import { type FolgePfeil, type FolgeZeile } from './ablauf-folge';
import { FORM_LISTENWAHL } from './form-listenwahl';
import type { ValuePath } from './form-value';

const BILD_OFFEN_BIS = 12;
const KEINE: ReadonlyMap<number, readonly string[]> = new Map();

@Component({
  selector: 'studio-ablauf-schrittfolge',
  imports: [AblaufBildComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    <p class="sf-desc">{{ t('ablaufPruefen.folge') }}</p>
    @if (!folge().length) {
      <p class="sf-desc">{{ t('ablaufPruefen.keineSchritte') }}</p>
    } @else {
      <details class="ab-rahmen" [open]="bildOffen()">
        <summary class="ab-kopf">{{ t('ablaufBild.titel') }}<span class="sr"> {{ t('ablaufBild.nurGrafik') }}</span></summary>
        <div class="ab-flaeche">
          <studio-ablauf-bild [folge]="folge()" (waehlen)="zeigen($event)" />
        </div>
      </details>
      <ol class="ap-folge">
        @for (z of folge(); track z.nr) {
          <li class="ap-zeile" [class.ap-mit-befund]="befundeAn(z.nr).length > 0">
            <span class="ap-schritt">
              <code>{{ z.id || t('ablaufPruefen.ohneKennung') }}</code>
              @if (z.typ) { <span class="ap-typ">{{ typText(z.typ) }}</span> }
              @if (z.modul) {
                @if (mitRouter) {
                  <a class="ap-modul" routerLink="/ui-module" [queryParams]="{ modul: z.modul }">{{ t('ablaufBild.modul', { modul: z.modul }) }}</a>
                } @else {
                  <span class="ap-modul">{{ t('ablaufBild.modul', { modul: z.modul }) }}</span>
                }
              }
              @if (listenwahl) {
                <button type="button" class="sf-add ap-zum"
                  [attr.aria-label]="t('ablaufBild.zumSchritt', { id: z.id || t('ablaufPruefen.ohneKennung') })"
                  (click)="zeigen(z.nr)">{{ t('ablaufBild.zum') }}</button>
              }
            </span>
            @if (!z.pfeile.length) {
              <!-- Befund 3: „Endet hier.“ nur am ende-Schritt; sonst läuft der Lauf aus -->
              <span class="ap-pfeil">{{ z.typ === 'ende' ? t('ablaufPruefen.endetHier') : t('ablaufPruefen.laeuftAus') }}</span>
            } @else {
              <ul class="ap-pfeile">
                @for (p of z.pfeile; track $index) {
                  <li class="ap-pfeil" [class.ap-unbekannt]="!p.bekannt">{{ pfeilText(p) }}</li>
                }
              </ul>
            }
            @for (text of befundeAn(z.nr); track $index) {
              <p class="sf-error ap-befund">{{ text }}</p>
            }
          </li>
        }
      </ol>
    }
  `,
})
export class AblaufSchrittfolgeComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly listenwahl = inject(FORM_LISTENWAHL, { optional: true });
  protected readonly mitRouter = inject(ActivatedRoute, { optional: true }) !== null;
  protected readonly t = this.lang.t;

  readonly folge = input.required<readonly FolgeZeile[]>();
  /** Der Pfad des Ablaufs im Dokument — die Schritte liegen unter `…, schritte`. */
  readonly pfad = input.required<ValuePath>();
  /** Die Befunde der letzten gültigen Prüfung je Stelle in `schritte`. */
  readonly befunde = input<ReadonlyMap<number, readonly string[]>>(KEINE);

  /** Review AS-2, Befund 8: nur der Anfangszustand — wer das Bild selbst auf- oder zuklappt,
   *  behält es so, auch wenn der Ablauf über zwölf Schritte wächst. */
  private anfangsOffen: boolean | null = null;
  protected bildOffen(): boolean {
    this.anfangsOffen ??= this.folge().length <= BILD_OFFEN_BIS;
    return this.anfangsOffen;
  }

  protected befundeAn(nr: number): readonly string[] {
    return this.befunde().get(nr) ?? [];
  }

  protected zeigen(nr: number): void {
    this.listenwahl?.waehlen([...this.pfad(), 'schritte'], nr);
  }

  /** AS-3c (Review, Befund 5): `teil.x ist größer als „10“` — der Vergleich übersetzt. */
  protected vergleichText(w: { quelle: string; vergleich: string; wert: string }): string {
    const key = `weiter.vergleich.${w.vergleich}`;
    const vergleich = this.lang.has(key) ? this.t(key) : w.vergleich;
    return [w.quelle, vergleich, w.wert ? `„${w.wert}“` : ''].filter(Boolean).join(' ');
  }

  protected typText(typ: string): string {
    const key = `feld.Schritt.typ.wahl.${typ}`;
    return this.lang.has(key) ? this.t(key) : typ;
  }

  protected pfeilText(p: FolgePfeil): string {
    const ziel = p.ziel ? p.ziel : this.t('ablaufPruefen.laeuftAus');
    const unbekannt = p.bekannt ? '' : ` ${this.t('ablaufPruefen.unbekannt')}`;
    if (p.keineGreift) return this.t('ablaufPruefen.keineGreift', { ziel });
    if (p.art === 'fehler') return this.t('ablaufPruefen.beiFehler', { ziel }) + unbekannt;
    if (p.art === 'weiter') return this.t('ablaufPruefen.weiter', { ziel }) + unbekannt;
    if (p.art === 'wahl') return this.t('ablaufPruefen.wahl', { label: p.label ?? '', ziel }) + unbekannt;
    if (p.art === 'freitext') return this.t('ablaufPruefen.freitext', { ziel }) + unbekannt;
    if (p.sonst) return this.t('ablaufPruefen.sonst', { ziel }) + unbekannt;
    const bedingungen = [
      ...(p.wennTeil ? [this.t('ablaufPruefen.wennTeil', { teil: p.wennTeil })] : []),
      ...(p.wennGewaehlt ? [this.t('ablaufPruefen.wennGewaehlt', { wahl: p.wennGewaehlt })] : []),
      ...(p.wennWert ? [this.t('ablaufPruefen.wennWert', { vergleich: this.vergleichText(p.wennWert) })] : []),
      ...(p.wennSeite ? [this.t('ablaufPruefen.wennSeite', { muster: p.wennSeite })] : []),
    ];
    return this.t('ablaufPruefen.regel', {
      wenn: bedingungen.length ? this.lang.listOr(bedingungen) : this.t('ablaufPruefen.ohneBedingung'),
      ziel,
    }) + unbekannt;
  }
}
