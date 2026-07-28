import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { WloCard } from '../cards/card-types';
import { getCardIcon, getCardPrimaryUrl } from '../cards/card-utils';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import { TopicPageView } from './message-types';
import { cardTooltip as cardTooltipUtil, GroupingContext } from './result-grouping';

/**
 * Swimlanes — die Themenseiten-Schwimmlinien-Anzeige (Pattern M16): wenn eine
 * Bot-Antwort `topicPage` trägt, rendert das Widget NUR diese Boxen (je
 * Schwimmlinie eine, Titel + „(Auszug)") + einen Absprung-Button auf die
 * vollständige Themenseite — statt der normalen Inline-Grouping-Boxen.
 * Visueller Port des ALT-Blocks (`chat.component.html:97-131`); teilt sich die
 * `.result-group*`-Stile mit ResultGroups (8-2h) über das SCSS-Partial
 * `_result-group.scss`.
 *
 * Präsentational: `topicPage` + `ctx` (GroupingContext, für die Card-Link-/
 * Tooltip-Auflösung) kommen vom Elternteil (Chat-Shell 8-4, das auch
 * `!isLoading && topicPage`-Gating besitzt); die Komponente self-gated nur den
 * `.result-groups`-Wrapper auf `swimlanes.length` (ALTs innerer `*ngIf`).
 * Kontrollfluss zu Angular-21 (`@if`/`@for`); DOM bleibt gleich; `[attr.title]`
 * wie in Tile/ResultGroups (null-Tooltip lässt das Attribut weg).
 *
 * Der Themenseiten-CTA linkt auf die ROHE `topic_page_url` (kein `withBsid`,
 * immer `_blank`) — verbatim wie ALT (anders als die Card-Items, die über
 * `cardUrl` = `withBsid∘getCardPrimaryUrl` laufen). Die zwei
 * Card-Item-Resolver spiegeln ResultGroups (in ALT ebenfalls dupliziertes
 * Inline-Markup); ein dritter Konsument würde die Extraktion auslösen.
 */
@Component({
  selector: 'boerdi-swimlanes',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './swimlanes.component.scss',
  template: `
    @if (swimlanes().length) {
      <div class="result-groups">
        @for (sl of swimlanes(); track $index) {
          <div class="result-group result-group--topic">
            <div class="result-group__heading">
              <span class="bb-icon" [innerHTML]="topicIcon | safeSvg"></span>
              {{ sl.heading || 'Inhalte' }} (Auszug)
            </div>
            <div class="result-group__items">
              @for (card of sl.cards; track $index) {
                <a
                  class="result-group__item"
                  [href]="cardUrl(card)"
                  target="_blank"
                  rel="noopener noreferrer"
                  [attr.title]="cardTooltip(card)"
                >
                  <span class="result-group__item-icon" [innerHTML]="getCardIcon(card) | safeSvg"></span>
                  <span class="result-group__item-title">{{ card.title }}</span>
                </a>
              }
            </div>
          </div>
        }

        @if (topicPage().topic_page_url; as url) {
          <a
            class="result-group result-group--cta"
            [href]="url"
            target="_blank"
            rel="noopener noreferrer"
            [attr.title]="'Zur vollständigen Themenseite: ' + topicPage().variant_title"
          >
            <span class="result-group__cta-icon" [innerHTML]="topicIcon | safeSvg"></span>
            <span class="result-group__cta-text">
              <strong>Zur Themenseite „{{ topicPage().variant_title }}"</strong>
              <span class="result-group__cta-sub">Alle Inhalte auf der Themenseite ansehen</span>
            </span>
            <span class="result-group__cta-arrow" [innerHTML]="arrowIcon | safeSvg"></span>
          </a>
        }
      </div>
    }
  `,
})
export class SwimlanesComponent {
  readonly topicPage = input.required<TopicPageView>();
  readonly ctx = input.required<GroupingContext>();

  protected readonly topicIcon = ICONS.auto_stories;
  protected readonly arrowIcon = ICONS.chevron_right;
  /** Pures Card-Icon direkt im Template (ALT-Binding `getCardIcon(card)`). */
  protected readonly getCardIcon = getCardIcon;

  // Defensiver Read im TS (nicht `swimlanes?.length` im Template) — die
  // Real-Backend-JSON kann das Array auslassen, obwohl der Typ es führt;
  // `?? []` hier vermeidet NG8107 (template-only) und bleibt laufzeit-sicher.
  protected readonly swimlanes = computed(() => this.topicPage().swimlanes ?? []);

  /** ALT `ChatComponent.cardUrl` = `withBsid(getCardPrimaryUrl(card))`. */
  protected cardUrl(card: WloCard): string {
    return this.ctx().withBsid(getCardPrimaryUrl(card));
  }

  /** ALT `ChatComponent.cardTooltip(card)` → 8-2g-Util mit Instanz-ctx. */
  protected cardTooltip(card: WloCard): string | null {
    return cardTooltipUtil(card, null, this.ctx());
  }
}
