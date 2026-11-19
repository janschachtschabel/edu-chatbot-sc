import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { ICONS } from '@boerdi/ui/icons/icons';
import { SafeSvgPipe } from '@boerdi/ui/icons/safe-svg.pipe';

import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import { type FreigabeDaten, freigabeAus } from './freigabe';
import { FreigabeListe } from './freigabe-liste.component';
import { artBezeichnung, artSymbol, dateiname, markdownDatei } from './inhaltsrahmen';

/** Eingabe laut manifest.json (`eingabe`). */
export interface UiInhaltsrahmenDaten {
  readonly titel: string;
  readonly art: string;
  readonly markdown: string;
  /** Paket N4, nur das System: die Liste einer Freigabe-Box vor einem schreibenden Auftrag. */
  readonly freigabe?: FreigabeDaten;
}

const TEXTE = {
  de: { drucken: 'Als PDF drucken / speichern', herunterladen: 'Als Markdown herunterladen' },
  en: { drucken: 'Print / save as PDF', herunterladen: 'Download as Markdown' },
} as const;

/**
 * Ein fertiges Arbeitsergebnis als gerahmte Box (Paket U1-b) — Nachfolger der Dokument-Box
 * (bis U1-b3 `ui/src/inline-doc/`), mit gleichem Aussehen und denselben Klassen. Drucken (auch als PDF)
 * und Herunterladen als Markdown gehen über den Modul-Host; den Markdown rendert der Host mit
 * dem Renderer der Bot-Antworten, bereinigt.
 */
@Component({
  selector: 'ui-inhaltsrahmen',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe, FreigabeListe],
  styleUrl: './ui-inhaltsrahmen.component.scss',
  template: `
    <div class="inline-document" [style.--inline-doc-scale]="kontext().schriftSkala">
      <div class="inline-document__heading">
        <span class="bb-icon" aria-hidden="true" [innerHTML]="symbol() | safeSvg"></span>
        <span class="inline-document__title">{{ daten().titel || bezeichnung() }}</span>
        <button type="button" class="inline-document__btn" data-aktion="drucken"
                [title]="texte().drucken" [attr.aria-label]="texte().drucken" (click)="drucken()">
          <span class="bb-icon" aria-hidden="true" [innerHTML]="druckSymbol | safeSvg"></span>
        </button>
        <button type="button" class="inline-document__btn" data-aktion="herunterladen"
                [title]="texte().herunterladen" [attr.aria-label]="texte().herunterladen" (click)="herunterladen()">
          <span class="bb-icon" aria-hidden="true" [innerHTML]="ladeSymbol | safeSvg"></span>
        </button>
      </div>
      @if (freigabe(); as liste) {
        <ui-freigabe-liste class="inline-document__body" [freigabe]="liste" [kontext]="kontext()" />
      } @else {
        <div class="inline-document__body" [innerHTML]="inhalt()"></div>
      }
    </div>
  `,
})
export class UiInhaltsrahmen {
  readonly daten = input.required<UiInhaltsrahmenDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);

  protected readonly druckSymbol = ICONS.print;
  protected readonly ladeSymbol = ICONS.download;
  protected readonly texte = computed(() => TEXTE[this.kontext().sprache]);
  protected readonly symbol = computed(() => artSymbol(this.daten().art));
  protected readonly bezeichnung = computed(() => artBezeichnung(this.daten().art, this.kontext().sprache));
  protected readonly freigabe = computed(() => freigabeAus(this.daten() as unknown as Record<string, unknown>));
  // Paket N4: die Freigabe-Box zeigt ihre Liste statt des Markdowns (der bleibt Textfassung und Druck)
  protected readonly inhalt = computed(() => (this.freigabe() ? '' : this.host.markdown(this.daten().markdown)));

  protected drucken(): void {
    this.host.drucken(this.daten().titel || this.bezeichnung(), this.daten().markdown);
  }

  protected herunterladen(): void {
    const titel = this.daten().titel || this.bezeichnung();
    this.host.herunterladen(dateiname(titel), 'text/markdown;charset=utf-8', markdownDatei(titel, this.daten().markdown));
  }
}
