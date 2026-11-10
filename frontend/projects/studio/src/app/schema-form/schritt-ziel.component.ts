/**
 * AS-3a (Plan 2026-11-09 §5d): ein Schritt desselben Ablaufs als Ziel (`x-widget: schritt-ziel`) —
 * an Schnellantworten und Freitext. Eine Auswahl der Schritte statt eines Textfelds; der eigene
 * Schritt steht als „dieser Schritt“ da, ein gesetztes Ziel, das es nicht gibt, markiert.
 *
 * Der Ablauf ist der Teil des Dokuments vor dem letzten `schritte` im Pfad
 * (`…, schritte, i, optionen, j, ziel`).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { FORM_DOKUMENT } from './form-dokument';
import { getAt } from './form-value';
import { schritteAus } from './weiter-regeln';

@Component({
  selector: 'studio-schritt-ziel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    <select class="sf-input" [id]="controlId()" [attr.aria-labelledby]="beschriftetVon()"
      [attr.aria-describedby]="describedBy()" [attr.aria-invalid]="unbekannt() || invalid() ? 'true' : null"
      [attr.aria-required]="pflicht() ? 'true' : null" (change)="waehlen($event)">
      @for (z of ziele(); track z.id) {
        <option [value]="z.id" [selected]="z.id === wert()">{{ z.text }}</option>
      }
    </select>
  `,
})
export class SchrittZielComponent {
  private readonly lang = inject(StudioLanguageService);
  private readonly dokument = inject(FORM_DOKUMENT, { optional: true });
  protected readonly t = this.lang.t;

  readonly controlId = input.required<string>();
  readonly value = input<unknown>();
  readonly describedBy = input<string | null>(null);
  readonly beschriftetVon = input<string | null>(null);
  readonly pfad = input<readonly (string | number)[]>([]);
  /** Der Server hat den Wert abgelehnt (wie an jedem Feld, ST-2e). */
  readonly invalid = input(false);
  readonly pflicht = input(false);
  readonly valueChange = output<unknown>();

  readonly wert = computed(() => (typeof this.value() === 'string' ? (this.value() as string) : ''));

  private readonly stelle = computed(() => {
    const pfad = this.pfad();
    const k = pfad.lastIndexOf('schritte');
    const nr = pfad[k + 1];
    return k < 0 ? null : { ablauf: getAt(this.dokument?.(), pfad.slice(0, k)), nr };
  });

  readonly unbekannt = computed(() => {
    const wert = this.wert();
    return wert !== '' && !schritteAus(this.stelle()?.ablauf).some((s) => s.id === wert);
  });

  readonly ziele = computed(() => {
    const stelle = this.stelle();
    const schritte = schritteAus(stelle?.ablauf);
    const roh = stelle && typeof stelle.nr === 'number' ? getAt(stelle.ablauf, ['schritte', stelle.nr, 'id']) : '';
    const liste = schritte.map((s) => ({
      id: s.id,
      text: s.id === roh ? this.t('weiter.dieser', { id: s.id })
        : s.typ ? `${s.id} (${this.typText(s.typ)})` : s.id,
    }));
    const wert = this.wert();
    if (!wert) return [{ id: '', text: this.t('weiter.zielWaehlen') }, ...liste];
    return this.unbekannt() ? [{ id: wert, text: this.t('weiter.unbekannt', { id: wert }) }, ...liste] : liste;
  });

  private typText(typ: string): string {
    const key = `feld.Schritt.typ.wahl.${typ}`;
    return this.lang.has(key) ? this.t(key) : typ;
  }

  protected waehlen(ereignis: Event): void {
    this.valueChange.emit((ereignis.target as HTMLSelectElement).value);
  }
}
