/**
 * Ein Materialtyp im Detail (Paket 14, D3) — Vorschau und Bearbeiten, ohne eigenen Zustand.
 *
 * Die Vorschau zeigt die Vorlage gerendert (`studio-markdown-vorschau`) und wie der Chatbot den
 * Typ anbietet: Chip-Text, Aliase, Vorrang — samt Warnung, wenn ein Chip-Text keinen Alias auf
 * den Typ hat. Bearbeiten zeigt das Formular mit Live-Vorschau. Den Entwurf hält die Seite
 * (`material-typen.component.ts`); hier wird nur gemeldet, was sich ändert.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import {
  KATEGORIEN, type MaterialTyp, type Pruefung, aliaseFuer, fehlendeAliase, vorrang,
} from '../core/material-types';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { MarkdownVorschauComponent } from './markdown-vorschau.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';

export type DetailReiter = 'mf-vorschau' | 'mf-bearbeiten';

export interface FeldAenderung {
  readonly feld: keyof MaterialTyp;
  readonly wert: string;
}

@Component({
  selector: 'studio-material-typ-detail',
  imports: [MarkdownVorschauComponent, TabBarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './material-typ-detail.component.html',
  styleUrl: './material-typ-detail.component.scss',
  host: { class: 'mf-detail' },
})
export class MaterialTypDetailComponent {
  protected readonly t = inject(StudioLanguageService).t;

  readonly entwurf = input.required<MaterialTyp>();
  /** Beim Anlegen ist die Kennung frei; danach steht sie fest (der Code verweist auf sie). */
  readonly neu = input(false);
  readonly aliase = input<Readonly<Record<string, string>>>({});
  readonly analytisch = input<readonly string[]>([]);
  readonly fehler = input<readonly Pruefung[]>([]);
  readonly reiter = input<DetailReiter>('mf-vorschau');

  /** Nur das geänderte Feld: die Seite wendet es auf ihren aktuellen Entwurf an. Ein ganzes
   *  Objekt aus dem (noch alten) Eingang überschriebe eine zweite Änderung im selben Takt. */
  readonly feldChange = output<FeldAenderung>();
  readonly reiterChange = output<DetailReiter>();

  readonly kategorien = KATEGORIEN;

  readonly tabs = computed<readonly TabDef[]>(() => [
    { id: 'mf-vorschau', label: this.t('materialFormate.reiter.vorschau') },
    { id: 'mf-bearbeiten', label: this.t('materialFormate.reiter.bearbeiten') },
  ]);

  readonly aliasListe = computed(() => aliaseFuer(this.entwurf().id, this.aliase()));
  readonly ohneAlias = computed(() => fehlendeAliase(this.entwurf(), this.aliase()));

  readonly vorrangText = computed(() => {
    const { fall, personas } = vorrang(this.entwurf(), this.analytisch());
    return this.t(`materialFormate.vorrang.${fall}`, { liste: personas.join(', ') });
  });

  waehleReiter(id: string): void {
    this.reiterChange.emit(id === 'mf-bearbeiten' ? 'mf-bearbeiten' : 'mf-vorschau');
  }

  setze(feld: keyof MaterialTyp, wert: string): void {
    this.feldChange.emit({ feld, wert });
  }
}
