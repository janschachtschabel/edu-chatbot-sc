import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { ICONS } from '@boerdi/ui/icons/icons';
import { SafeSvgPipe } from '@boerdi/ui/icons/safe-svg.pipe';

import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';

/** Eingabe laut manifest.json (`eingabe`). */
export interface UiLinkboxDaten {
  readonly links: readonly { readonly titel: string; readonly url: string }[];
}

const TEXTE = {
  de: { ueberschrift: 'Webseiten-Inhalte', eintrag: (t: string) => `${t} (Webseite)`, ohne: 'Webseite' },
  en: { ueberschrift: 'Web page contents', eintrag: (t: string) => `${t} (web page)`, ohne: 'Web page' },
} as const;

/**
 * Die Webseiten einer Antwort als Linkliste (Paket U1-c1) — Nachfolger der Box
 * `boerdi-web-links`, mit gleichem DOM und demselben Stil-Partial. Adresse und Warnhinweis
 * liefert der Host (Sitzungs-Kennung bei vertrauten Seiten, Hinweis bei fremden); die Daten
 * leitet das Backend aus `web_links` ab (Grenze `webseiten_max`, nur http/https).
 */
@Component({
  selector: 'ui-linkbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './ui-linkbox.component.scss',
  template: `
    <div class="result-groups">
      <div class="result-group result-group--web">
        <div class="result-group__heading">
          <span class="bb-icon" aria-hidden="true" [innerHTML]="symbol | safeSvg"></span>
          {{ texte().ueberschrift }}
        </div>
        <div class="result-group__items">
          @for (link of eintraege(); track $index) {
            <!-- Ohne http(s)-Adresse kein Link (sonst <a href=""> auf die eigene Seite; Review 2026-11-07). -->
            @if (link.href) {
              <a class="result-group__item" [href]="link.href" target="_blank" rel="noopener noreferrer"
                 [attr.title]="link.tooltip">
                <span class="result-group__item-icon" aria-hidden="true" [innerHTML]="symbol | safeSvg"></span>
                <span class="result-group__item-title">{{ link.titel || texte().ohne }}</span>
              </a>
            } @else {
              <span class="result-group__item" [attr.title]="link.tooltip">
                <span class="result-group__item-icon" aria-hidden="true" [innerHTML]="symbol | safeSvg"></span>
                <span class="result-group__item-title">{{ link.titel || texte().ohne }}</span>
              </span>
            }
          }
        </div>
      </div>
    </div>
  `,
})
export class UiLinkbox {
  readonly daten = input.required<UiLinkboxDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);

  protected readonly symbol = ICONS.language;
  protected readonly texte = computed(() => TEXTE[this.kontext().sprache]);

  /** Tooltip wie bisher (`itemTooltip`): Beschriftung, bei fremden Seiten „— Hinweis“. */
  protected readonly eintraege = computed(() => (this.daten().links ?? []).map((l) => {
    const { href, hinweis } = this.host.link(l.url);
    const label = l.titel ? this.texte().eintrag(l.titel) : this.texte().ohne;
    return { titel: l.titel, href, tooltip: hinweis ? `${label} — ${hinweis}` : label };
  }));
}
