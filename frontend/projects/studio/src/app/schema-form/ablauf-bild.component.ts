/**
 * AS-2b (Plan 2026-11-09): das Ablaufbild — die Schrittfolge als Zeichnung (`ablauf-bild.ts`).
 *
 * Nur für das Auge (`aria-hidden`): dieselbe Auskunft steht als Text in der Schrittfolge darunter,
 * und dort führt „Zum Schritt“ per Tastatur dorthin, wohin hier ein Klick auf einen Kasten führt.
 * Bögen „bei Fehler“ sind gestrichelt, nicht nur andersfarbig; ein Kasten mit unbekanntem Ziel hat
 * einen kräftigeren Rand und ein ⚠.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { bildAus, type Kasten, KASTEN_B, KASTEN_H, type Linie, SPUR } from './ablauf-bild';
import type { FolgeZeile } from './ablauf-folge';

const ZEICHEN = 24;
const ZEICHEN_BESCHRIFTUNG = 16;
let naechste = 0;

@Component({
  selector: 'studio-ablauf-bild',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    <svg class="ab" aria-hidden="true" focusable="false"
      [attr.viewBox]="'0 0 ' + bild().breite + ' ' + bild().hoehe"
      [attr.width]="bild().breite" [attr.height]="bild().hoehe">
      <defs>
        <marker [attr.id]="marke" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7"
          orient="auto-start-reverse">
          <path class="ab-spitze" d="M0,0 L8,4 L0,8 z" />
        </marker>
      </defs>
      @for (l of bild().linien; track $index) {
        <path class="ab-linie" [class.ab-bogen]="!l.gerade" [class.ab-fehler]="l.art === 'fehler'"
          [attr.d]="weg(l)" [attr.marker-end]="'url(#' + marke + ')'" />
        @if (!l.gerade && beschriftung(l); as text) {
          <text class="ab-beschriftung" [attr.x]="spurX(l) + 3" [attr.y]="mitteY(l)">{{ text }}</text>
        }
      }
      @for (k of bild().kaesten; track k.nr) {
        <g class="ab-kasten" [class.ab-unbekannt]="k.unbekannt" (click)="waehlen.emit(k.nr)">
          <title>{{ titel(k) }}</title>
          <rect [attr.x]="k.x" [attr.y]="k.y" [attr.width]="k.breite" [attr.height]="k.hoehe" rx="4" />
          <text class="ab-text" [attr.x]="k.x + 8" [attr.y]="k.y + k.hoehe / 2 + 4">
            {{ kurz(k) }}@if (k.unbekannt) { ⚠ }
          </text>
        </g>
      }
    </svg>
  `,
})
export class AblaufBildComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  /** Je Bild eine eigene Pfeilspitze — zwei Bilder auf einer Seite teilen sonst eine Kennung. */
  protected readonly marke = `ab-spitze-${++naechste}`;

  readonly folge = input.required<readonly FolgeZeile[]>();
  /** Die Stelle des angeklickten Schritts in `schritte`. */
  readonly waehlen = output<number>();

  readonly bild = computed(() => bildAus(this.folge()));

  protected weg(l: Linie): string {
    const k = this.bild().kaesten;
    const von = k[l.von];
    const nach = k[l.nach];
    if (l.gerade) {
      const x = von.x + KASTEN_B / 2;
      return `M ${x} ${von.y + KASTEN_H} V ${nach.y - 1}`;
    }
    const x = von.x + KASTEN_B;
    return `M ${x} ${this.y(von)} H ${this.spurX(l)} V ${this.y(nach)} H ${x + 2}`;
  }

  protected spurX(l: Linie): number {
    return this.bild().kaesten[l.von].x + KASTEN_B + (l.spur + 1) * SPUR;
  }

  protected mitteY(l: Linie): number {
    const k = this.bild().kaesten;
    return (this.y(k[l.von]) + this.y(k[l.nach])) / 2 + 4;
  }

  protected beschriftung(l: Linie): string {
    if (l.art === 'fehler') return this.t('ablaufBild.fehler');
    if (l.art === 'freitext') return this.t('ablaufBild.freitext');
    if (l.bedingung === 'sonst') return this.t('weiter.bedingung.sonst');
    // ein Teil steht mit „+“ davor — sonst sähe er aus wie eine Wahl
    const text = l.bedingung === 'teil' ? `+${l.beschriftung}` : l.beschriftung;
    return gekuerzt(text, ZEICHEN_BESCHRIFTUNG);
  }

  protected kurz(k: Kasten): string {
    return gekuerzt(k.id || '—', ZEICHEN);
  }

  protected titel(k: Kasten): string {
    const key = `feld.Schritt.typ.wahl.${k.typ}`;
    const typ = k.typ ? (this.lang.has(key) ? this.t(key) : k.typ) : '';
    return typ ? `${k.id || '—'} (${typ})` : k.id || '—';
  }

  private y(k: Kasten): number {
    return k.y + KASTEN_H / 2;
  }
}

function gekuerzt(text: string, zeichen: number): string {
  return text.length > zeichen ? `${text.slice(0, zeichen - 1)}…` : text;
}
