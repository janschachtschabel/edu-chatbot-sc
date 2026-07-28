import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { WloCard } from '../cards/card-types';
import { getCardIcon, getCardPrimaryUrl } from '../cards/card-utils';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import { ChatMessage, WebLink } from './message-types';
import {
  cardTooltip as cardTooltipUtil,
  groupedCollectionCards,
  groupedContentCards,
  groupedSearchTerm,
  groupedSearchUrl,
  groupedTopicCards,
  groupedWebLinks,
  GroupingContext,
  hasGroupedResults,
  itemTooltip as itemTooltipUtil,
  searchCtaTooltip,
} from './result-grouping';

/**
 * Instanz-Kontext für den Result-Grouping-Renderer. Erweitert den reinen
 * {@link GroupingContext} (withBsid/externalLinkWarning, den die 8-2g-Utils
 * lesen) um die eine Host-Trust-Abfrage, die nur die Such-CTA-Target-
 * Entscheidung braucht (ALT `ChatComponent.isHostTrusted`). Die Chat-Shell
 * (8-4) baut ihn aus `session/trusted-host` (sessionId + effektive
 * Trusted-Liste) und reicht ihn als Input herein — analog zum präsentationalen
 * Schnitt des WloCard-Tiles (8-2f), wo der Elternteil die Session-/Trust-Logik
 * besitzt.
 */
export interface ResultGroupsContext extends GroupingContext {
  /** ALT `ChatComponent.isHostTrusted(host)` = `isTrustedHost(host, effektive
   *  Trusted-Domains)`, gebunden an die Instanz-Liste. */
  isTrustedHost: (host: string) => boolean;
}

/**
 * ResultGroups — der Inline-Result-Grouping-Block: statt einer flachen
 * Card-Liste separate Boxen für Themenseiten / Sammlungen / Materialien /
 * Webseiten-Inhalte + eine Such-CTA. Visueller Port des ALT-Blocks
 * (`chat.component.html:133-236` + `.result-group*` aus chat.component.scss),
 * der dort inline im chat.component-Monolithen lag; NEU als eigenständige
 * präsentationale Komponente über der portierten 8-2g-Grouping-Logik.
 *
 * Kontrollfluss zu Angular-21 übersetzt (`*ngIf`→`@if`, `*ngFor`→`@for`);
 * gerendertes DOM bleibt gleich. Der `.result-groups`-Wrapper erscheint NUR
 * wenn `hasGroupedResults` (ALTs „kein leerer Rahmen"-Garantie, inkl.
 * Tour-Unterdrückung) — die HOST-Flag-Gates (`inline-result-grouping`,
 * `hideCards`) bleiben beim Elternteil (Chat-Shell 8-4), das entscheidet, ob
 * die Komponente überhaupt gerendert wird.
 *
 * Tooltips via `[attr.title]` (nicht `[title]`): die 8-2g-Tooltip-Utils geben
 * bewusst `null` zurück, damit das Attribut ENTFÄLLT statt literal „null" ins
 * DOM zu schreiben — dieselbe Korrektur wie im Tile (8-2f).
 *
 * NICHT enthalten (eigene Slices): die Themenseiten-Schwimmlinien-Boxen
 * (`msg.topicPage`, chat.component.html:97-131 — swimlanes, 8-2-Rest) und die
 * `.inline-document`-Box (inline-doc-Slice). A11y-Feinschliff (Heading-
 * Semantik, `aria-hidden` auf dekorative Icons, Fokus-Ring-Audit) ist der
 * geplante koordinierte Sweep 8-6 — hier DOM verbatim wie ALT.
 */
@Component({
  selector: 'boerdi-result-groups',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './result-groups.component.scss',
  template: `
    @if (hasResults()) {
      <div class="result-groups">
        @if (topicCards().length) {
          <div class="result-group result-group--topic">
            <div class="result-group__heading">
              <span class="bb-icon" [innerHTML]="topicIcon | safeSvg"></span>
              Themenseiten
            </div>
            <div class="result-group__items">
              @for (card of topicCards(); track $index) {
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

        @if (collectionCards().length) {
          <div class="result-group result-group--collection">
            <div class="result-group__heading">
              <span class="bb-icon" [innerHTML]="collectionIcon | safeSvg"></span>
              Sammlungen
            </div>
            <div class="result-group__items">
              @for (card of collectionCards(); track $index) {
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

        @if (contentCards().length) {
          <div class="result-group result-group--material">
            <div class="result-group__heading">
              <span class="bb-icon" [innerHTML]="materialIcon | safeSvg"></span>
              Ausgewählte Materialien
            </div>
            <div class="result-group__items">
              @for (card of contentCards(); track $index) {
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

        @if (webLinks().length) {
          <div class="result-group result-group--web">
            <div class="result-group__heading">
              <span class="bb-icon" [innerHTML]="webIcon | safeSvg"></span>
              Webseiten-Inhalte
            </div>
            <div class="result-group__items">
              @for (link of webLinks(); track $index) {
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
        }

        @if (searchUrl(); as url) {
          <a
            class="result-group result-group--cta"
            [href]="url"
            [attr.target]="searchTargetSelf() ? '_self' : '_blank'"
            rel="noopener noreferrer"
            [attr.title]="searchTooltip()"
          >
            <span class="result-group__cta-icon" [innerHTML]="searchIcon | safeSvg"></span>
            <span class="result-group__cta-text">
              @if (searchTerm(); as q) {
                <strong>Treffer zur Suche „{{ q }}"</strong>
              } @else {
                <strong>Alle Treffer in der Suche</strong>
              }
              <span class="result-group__cta-sub">Alle passenden Materialien anzeigen</span>
            </span>
            <span class="result-group__cta-arrow" [innerHTML]="arrowIcon | safeSvg"></span>
          </a>
        }
      </div>
    }
  `,
})
export class ResultGroupsComponent {
  readonly message = input.required<ChatMessage>();
  readonly ctx = input.required<ResultGroupsContext>();

  // Box-/CTA-Icons (fix je Box — ALT chat.component.html:138/157/180/203/226/234).
  protected readonly topicIcon = ICONS.auto_stories;
  protected readonly collectionIcon = ICONS.collections_bookmark;
  protected readonly materialIcon = ICONS.description;
  protected readonly webIcon = ICONS.language;
  protected readonly searchIcon = ICONS.search;
  protected readonly arrowIcon = ICONS.chevron_right;

  /** Pures Card-Icon direkt im Template (ALT-Binding `getCardIcon(card)`). */
  protected readonly getCardIcon = getCardIcon;

  protected readonly hasResults = computed(() => hasGroupedResults(this.message(), this.ctx()));
  protected readonly topicCards = computed(() => groupedTopicCards(this.message()));
  protected readonly collectionCards = computed(() => groupedCollectionCards(this.message()));
  protected readonly contentCards = computed(() => groupedContentCards(this.message()));
  protected readonly webLinks = computed(() => groupedWebLinks(this.message(), this.ctx()));
  protected readonly searchUrl = computed(() => groupedSearchUrl(this.message(), this.ctx()));
  protected readonly searchTerm = computed(() => groupedSearchTerm(this.message()));
  protected readonly searchTooltip = computed(() => searchCtaTooltip(this.message(), this.ctx()));

  /** ALT `ChatComponent.isTrustedSearchUrl` — `_self` bei same-origin oder
   *  trusted Host, sonst `_blank`. `window.location` = Widget-Host-Seite. */
  protected readonly searchTargetSelf = computed(() => {
    const url = this.searchUrl();
    if (!url) return false;
    try {
      const u = new URL(url, window.location.href);
      if (u.origin === window.location.origin) return true;
      return this.ctx().isTrustedHost(u.hostname.toLowerCase());
    } catch {
      return false;
    }
  });

  /** ALT `ChatComponent.cardUrl` = `withBsid(getCardPrimaryUrl(card))`. */
  protected cardUrl(card: WloCard): string {
    return this.ctx().withBsid(getCardPrimaryUrl(card));
  }

  /** ALT `ChatComponent.cardTooltip(card)` → 8-2g-Util mit Instanz-ctx. */
  protected cardTooltip(card: WloCard): string | null {
    return cardTooltipUtil(card, null, this.ctx());
  }

  /** ALT `ChatComponent.webLinkUrl` = `withBsid(link.url)`. Idempotent — die
   *  URL trägt aus `groupedWebLinks` bereits `?bsid` (trusted-host bricht bei
   *  vorhandenem bsid ab), der Zweit-Aufruf ist ein No-Op-Passthrough. */
  protected webLinkUrl(link: WebLink): string {
    return this.ctx().withBsid(link.url);
  }

  /** ALT-Template-Inline: `itemTooltip(link.title ? link.title + ' (Webseite)'
   *  : 'Webseite', webLinkUrl(link))` — hierher gezogen statt in den Markup. */
  protected webLinkTooltip(link: WebLink): string | null {
    const label = link.title ? link.title + ' (Webseite)' : 'Webseite';
    return itemTooltipUtil(label, this.webLinkUrl(link), this.ctx());
  }
}
