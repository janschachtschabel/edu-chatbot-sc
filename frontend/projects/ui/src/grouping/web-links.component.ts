import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import { ChatMessage, WebLink } from './message-types';
import {
  groupedWebLinks,
  isTourMessage,
  itemTooltip as itemTooltipUtil,
  ResultGroupsContext,
} from './result-grouping';

/**
 * Die Box „Webseiten-Inhalte" — Links aus dem Antworttext. Aus
 * `result-groups` herausgelöst, weil sie in BEIDEN Trefferdarstellungen stehen
 * muss: Web-Links sind keine Karten. Seit U2b zeigt das große Fenster das
 * Kachelraster statt der Textlink-Boxen, und die Box fiel dort ganz weg
 * (Befund 2026-09-30: „Was ist WissenLebtOnline?" klein mit WLO-Startseite,
 * groß ohne). DOM und Stil der Box unverändert (`.result-group--web`).
 *
 * `standalone` — außerhalb von `result-groups` (unter dem Kachelraster) bringt
 * die Box den `.result-groups`-Rahmen für ihren Abstand selbst mit; innerhalb
 * steht sie wie bisher direkt in dessen Rahmen. Tour-Nachrichten zeigen keine
 * Box: innerhalb sorgt das Tor von `result-groups` dafür, hier dieselbe Regel.
 */
@Component({
  selector: 'boerdi-web-links',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet, SafeSvgPipe],
  styleUrl: './web-links.component.scss',
  template: `
    @if (links().length) {
      @if (standalone()) {
        <div class="result-groups"><ng-container [ngTemplateOutlet]="box" /></div>
      } @else {
        <ng-container [ngTemplateOutlet]="box" />
      }
    }
    <ng-template #box>
      <div class="result-group result-group--web">
        <div class="result-group__heading">
          <span class="bb-icon" [innerHTML]="webIcon | safeSvg"></span>
          {{ t('groups.web') }}
        </div>
        <div class="result-group__items">
          @for (link of links(); track $index) {
            <a
              class="result-group__item"
              [href]="webLinkUrl(link)"
              target="_blank"
              rel="noopener noreferrer"
              [attr.title]="webLinkTooltip(link)"
            >
              <span class="result-group__item-icon" [innerHTML]="webIcon | safeSvg"></span>
              <span class="result-group__item-title">{{ link.title }}</span>
            </a>
          }
        </div>
      </div>
    </ng-template>
  `,
})
export class WebLinksComponent {
  readonly message = input.required<ChatMessage>();
  readonly ctx = input.required<ResultGroupsContext>();
  /** Außerhalb von `result-groups` gerendert (Kachelraster) — eigener Rahmen. */
  readonly standalone = input(false);

  protected readonly webIcon = ICONS.language;

  protected readonly t = (key: string, params?: TranslationParams): string =>
    this.ctx().t(key, params);

  protected readonly links = computed(() =>
    isTourMessage(this.message()) ? [] : groupedWebLinks(this.message(), this.ctx()));

  /** ALT `ChatComponent.webLinkUrl` = `withBsid(link.url)`. Idempotent — die
   *  URL trägt aus `groupedWebLinks` bereits `?bsid` (trusted-host bricht bei
   *  vorhandenem bsid ab), der Zweit-Aufruf ist ein No-Op-Passthrough. */
  protected webLinkUrl(link: WebLink): string {
    return this.ctx().withBsid(link.url);
  }

  /** ALT-Template-Inline: `itemTooltip(link.title ? link.title + ' (Webseite)'
   *  : 'Webseite', webLinkUrl(link))` — hierher gezogen statt in den Markup. */
  protected webLinkTooltip(link: WebLink): string | null {
    const label = link.title
      ? this.t('groups.webItem', { title: link.title })
      : this.t('groups.webItemUntitled');
    return itemTooltipUtil(label, this.webLinkUrl(link), this.ctx());
  }
}
