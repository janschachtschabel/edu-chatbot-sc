/**
 * AS-Dc (Plan 2026-11-09 §5e): die Sicht „Daten“ eines Ablaufs — je Teil Typ, schreibende und
 * lesende Schritte, ein Beispielwert aus den Testfällen.
 *
 * Die Zeilen rechnet das Backend mit „Prüfen“ (`teile` der Antwort), aus derselben Quelle wie die
 * Prüfung — eine zweite Typtabelle hier liefe auseinander. Ein Schritt in der Tabelle führt wie
 * „Zum Schritt“ in die Liste der Schritte (`FORM_LISTENWAHL`).
 *
 * RB-2 (Querschnitts-Review AS-D, NIT): Typen erscheinen mit einem Namen statt als Kennung. Das ist
 * nur Anzeige — ein unbekannter Typ zeigt seine Kennung, die Kennungen stehen im `title`.
 */
import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';

import type { AblaufTeil } from '../core/ablauf-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { FolgeZeile } from './ablauf-folge';
import { FORM_LISTENWAHL } from './form-listenwahl';
import type { ValuePath } from './form-value';

/**
 * Bekannte Typen (`services/ablauf/typen.py`) → Schlüssel ihres Namens (`ablaufDaten.typName.*`).
 * Fehlt einer, zeigt die Sicht die Kennung — nichts geht verloren.
 */
export const TYP_NAMEN: Readonly<Record<string, string>> = {
  'text': 'text',
  'wlo.start@1': 'start',
  'wlo.ordnerbaum@1': 'ordnerbaum',
  'wlo.dokument-verweis@1': 'dokument',
  'wlo.sammlungsstruktur@1': 'struktur',
  'wlo.ablage@1': 'ablage',
  'wlo.auftrag@1': 'auftrag',
  'wlo.strukturabgleich@1': 'abgleich',
  'wlo.abdeckung@1': 'abdeckung',
  'wlo.metadaten@1': 'metadaten',
  'wlo_create_collection_tree@1': 'angelegt',
  'baum_aus_entwurf@1': 'baum',
};

/** Ergebnis eines Werkzeugs ohne eigenen Typ (`typen._werkzeug_typ`): `<werkzeug>@<n>`. */
const WERKZEUG_TYP = /^([a-z0-9_-]+)@\d+$/i;

@Component({
  selector: 'studio-ablauf-daten',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    @if (teile(); as liste) {
      @if (!liste.length) {
        <!-- Review AS-Dc, Befund 12: gerechnet, aber ohne Teile -->
        <p class="sf-desc">{{ t('ablaufDaten.keine') }}</p>
      } @else {
      <details class="ad">
        <summary class="ab-kopf">{{ lang.plural('ablaufDaten.titel', liste.length) }}</summary>
        <div class="ad-flaeche" tabindex="0" role="region" [attr.aria-label]="t('ablaufDaten.region')">
          <table class="ad-tabelle">
            <caption class="sr">{{ t('ablaufDaten.caption') }}</caption>
            <thead>
              <tr>
                <th scope="col">{{ t('ablaufDaten.teil') }}</th>
                <th scope="col">{{ t('ablaufDaten.typ') }}</th>
                <th scope="col">{{ t('ablaufDaten.schreiber') }}</th>
                <th scope="col">{{ t('ablaufDaten.leser') }}</th>
                <th scope="col">{{ t('ablaufDaten.beispiel') }}</th>
              </tr>
            </thead>
            <tbody>
              @for (z of liste; track z.name) {
                <tr>
                  <th scope="row"><code>{{ z.name }}</code></th>
                  <td [attr.title]="kennungen(z)">{{ typText(z) }}@if (kennungen(z); as k) {<span class="sr"> ({{ k }})</span>}</td>
                  <td>
                    <span class="ad-zelle">
                      @if (z.vor_dem_start) { <span>{{ t('ablaufDaten.vorStart') }}</span> }
                      @for (nr of z.schreiber; track nr) { <ng-container *ngTemplateOutlet="schritt; context: { nr }" /> }
                      @if (!z.vor_dem_start && !z.schreiber.length) {
                        @if (z.aus_gespraech) { <span>{{ t('ablaufDaten.gespraech') }}</span> }
                        @else { <span class="sf-error">{{ t('ablaufDaten.niemand') }}</span> }
                      }
                    </span>
                  </td>
                  <td>
                    <span class="ad-zelle">
                      @for (nr of z.leser; track nr) { <ng-container *ngTemplateOutlet="schritt; context: { nr }" /> }
                      @if (!z.leser.length) { <span>{{ t('ablaufDaten.keiner') }}</span> }
                    </span>
                  </td>
                  <td><code class="ad-beispiel">{{ z.beispiel ?? '—' }}</code></td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </details>
      }
    }
    <ng-template #schritt let-nr="nr">
      @if (listenwahl) {
        <button type="button" class="ad-schritt" [attr.aria-label]="t('ablaufBild.zumSchritt', { id: kennung(nr) })"
          (click)="zeigen(nr)">{{ kennung(nr) }}</button>
      } @else {
        <span class="ad-schritt">{{ kennung(nr) }}</span>
      }
    </ng-template>
  `,
  imports: [NgTemplateOutlet],
})
export class AblaufDatenComponent {
  protected readonly lang = inject(StudioLanguageService);
  protected readonly listenwahl = inject(FORM_LISTENWAHL, { optional: true });
  protected readonly t = this.lang.t;

  /** ``null``: noch nicht (gültig) geprüft — dann nichts. */
  readonly teile = input<readonly AblaufTeil[] | null>(null);
  readonly folge = input<readonly FolgeZeile[]>([]);
  readonly pfad = input<ValuePath>([]);

  protected kennung(nr: number): string {
    return this.folge()[nr]?.id || this.t('ablaufPruefen.ohneKennung');
  }

  protected typText(z: AblaufTeil): string {
    return z.typen.length ? z.typen.map((t) => this.typName(t)).join(', ') : '—';
  }

  /** Die Kennungen hinter den Namen — für Fachleute (`title`) und Screenreader (versteckter
   *  Text; ein `title` allein ist mit Tastatur und Touch nicht erreichbar, Review RB-2, Befund 4).
   *  Ohne die Marken `?`/`…`, die keine Kennung sind. */
  protected kennungen(z: AblaufTeil): string | null {
    const echte = z.typen.filter((t) => t !== '?' && t !== '…');
    return echte.length ? echte.join(', ') : null;
  }

  private typName(typ: string): string {
    if (typ === '?') return this.t('ablaufDaten.ki');
    if (typ === '…') return this.t('ablaufDaten.unbekannt');
    const schluessel = TYP_NAMEN[typ];
    if (schluessel) return this.t(`ablaufDaten.typName.${schluessel}`);
    const werkzeug = WERKZEUG_TYP.exec(typ)?.[1];
    return werkzeug ? this.t('ablaufDaten.typErgebnis', { werkzeug }) : typ;
  }

  protected zeigen(nr: number): void {
    this.listenwahl?.waehlen([...this.pfad(), 'schritte'], nr);
  }
}
