/**
 * Modul-Nutzung eines Eval-Laufs (Paket U1-g, G-6): je Muster und je Anwendungsfall, in wie
 * vielen Zügen welches UI-Modul erschien. Gerechnet beim Lesen
 * (`services/eval/modul_nutzung.py`); hier wird nur beschriftet.
 *
 * Ein Lauf von vor U1-g hat nichts erfasst — das steht da, statt Nullen zu zeigen, die wie
 * „kein Modul erschien“ läsen. Ein Lauf ohne beantworteten Zug (`zuege == 0`, etwa gerade
 * gestartet) ist nicht alt: dafür ein eigener Satz (Review U1-g #10). Die Spalten sind die Modulnamen (technisch, wie im Katalog und in
 * den Erwartungen `ui_any`); Anwendungsfälle stehen wie in der Matrix als Kennung.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import type { ModulNutzung, ModulNutzungZeile } from '../core/eval-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

export interface NutzungTabelle {
  readonly id: string;
  readonly titel: string;
  readonly kopf: string;
  readonly zeilen: readonly { readonly name: string; readonly zuege: string;
                              readonly zellen: readonly string[] }[];
}

@Component({
  selector: 'studio-eval-modul-nutzung',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-modul-nutzung.component.html',
  styleUrl: './eval-modul-nutzung.component.scss',
})
export class EvalModulNutzungComponent {
  private readonly fmt = inject(StudioFormat);
  protected readonly t = inject(StudioLanguageService).t;

  readonly nutzung = input.required<ModulNutzung>();

  readonly erfasst = computed(() => this.nutzung().erfasst > 0);
  readonly module = computed(() => this.nutzung().module);

  readonly tabellen = computed<readonly NutzungTabelle[]>(() => {
    const n = this.nutzung();
    const teile = [
      { id: 'muster', titel: 'evalModul.jeMuster', kopf: 'evalModul.col.muster',
        gruppen: n.je_muster },
      { id: 'fall', titel: 'evalModul.jeFall', kopf: 'evalModul.col.fall',
        gruppen: n.je_anwendungsfall },
    ];
    return teile
      .filter((teil) => Object.keys(teil.gruppen).length > 0)
      .map((teil) => ({
        id: teil.id, titel: this.t(teil.titel), kopf: this.t(teil.kopf),
        zeilen: Object.entries(teil.gruppen).map(([name, zeile]) => this.zeile(name, zeile)),
      }));
  });

  readonly zusammenfassung = computed(() => {
    const n = this.nutzung();
    return this.t('evalModul.erfasst', {
      erfasst: this.fmt.whole(n.erfasst), zuege: this.fmt.whole(n.zuege) });
  });

  private zeile(name: string, zeile: ModulNutzungZeile) {
    return {
      name,
      zuege: this.fmt.whole(zeile.zuege),
      zellen: this.module().map((modul) => this.fmt.whole(zeile.module[modul] ?? 0)),
    };
  }
}
