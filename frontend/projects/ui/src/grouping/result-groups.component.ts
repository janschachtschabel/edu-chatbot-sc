import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import type { CardAction } from '../cards/card-list.component';
import { WloCard } from '../cards/card-types';
import { getCardCollectionUrl, getCardIcon, getCardPrimaryUrl } from '../cards/card-utils';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import { ChatMessage } from './message-types';
import {
  cardTooltip as cardTooltipUtil,
  groupedCollectionCards,
  groupedContentCards,
  groupedTopicCards,
  hasGroupedResults,
  ResultGroupsContext,
} from './result-grouping';
import { SearchCtaComponent } from './search-cta.component';
import { WebLinksComponent } from './web-links.component';

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
  imports: [MatButtonModule, SafeSvgPipe, SearchCtaComponent, WebLinksComponent],
  styleUrl: './result-groups.component.scss',
  template: `
    @if (hasResults()) {
      <div class="result-groups">
        @if (topicCards().length) {
          <div class="result-group result-group--topic">
            <div class="result-group__heading">
              <span class="bb-icon" [innerHTML]="topicIcon | safeSvg"></span>
              {{ t('groups.topics') }}
            </div>
            <div class="result-group__items">
              <!-- aria-label neben title: seit Sammlungen mit Themenseite in
                   beiden Kästen stehen, gibt es zwei Verweise mit demselben
                   sichtbaren Text und verschiedenen Zielen. Sehend trennt sie
                   die Kasten-Überschrift; vorgelesen trennt sie nur dieses
                   Etikett („Optik (Themenseite)" vs. „Optik (Sammlung)") —
                   title allein wird nicht verlässlich angesagt. -->
              @for (card of topicCards(); track $index) {
                <a
                  class="result-group__item"
                  [href]="cardUrl(card)"
                  target="_blank"
                  rel="noopener noreferrer"
                  [attr.title]="cardTooltip(card)"
                  [attr.aria-label]="cardTooltip(card)"
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
              {{ t('groups.collections') }}
            </div>
            <div class="result-group__items">
              <!-- Sammlungen MIT Themenseite stehen auch oben im
                   Themenseiten-Kasten — hier aber mit der Sammlungs-Adresse,
                   dem Sammlungs-Symbol und dem Sammlungs-Label, sonst wäre
                   dieselbe Zeile zweimal identisch beschriftet. -->
              @for (card of collectionCards(); track $index) {
                <a
                  class="result-group__item"
                  [href]="collectionUrl(card)"
                  target="_blank"
                  rel="noopener noreferrer"
                  [attr.title]="collectionTooltip(card)"
                  [attr.aria-label]="collectionTooltip(card)"
                >
                  <span class="result-group__item-icon" [innerHTML]="collectionItemIcon | safeSvg"></span>
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
              {{ t('groups.materials') }}
            </div>
            <div class="result-group__items">
              @for (card of contentCards(); track $index) {
                <!-- M17: Link raus zum Material PLUS ein Knopf, der den
                     Volltext im Chat öffnet. Der Knopf steht NEBEN dem Link,
                     nicht darin — ein Bedienelement im Anker wäre ungültiges
                     HTML und für die Tastatur mehrdeutig. -->
                <div class="result-group__row">
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
                  @if (card.node_id) {
                    <button
                      matIconButton
                      type="button"
                      class="result-group__item-btn"
                      [disabled]="isLoading()"
                      [attr.aria-label]="t('groups.showContent', { title: card.title })"
                      [attr.title]="t('groups.showContent', { title: card.title })"
                      (click)="showContentText.emit({ nodeId: card.node_id, title: card.title })"
                    >
                      <span class="bb-icon" [innerHTML]="contentTextIcon | safeSvg"></span>
                    </button>
                  }
                </div>
              }
            </div>
          </div>
        }

        <!-- Webseiten-Inhalte: eigene Komponente, weil das Kachelraster (großes
             Fenster) sie ebenfalls zeigt — Web-Links sind keine Karten. -->
        <boerdi-web-links [message]="message()" [ctx]="ctx()" />

        <!-- Der Such-Absprung steht seit U6b in einer eigenen Komponente: das
             Kachelraster zeigt ihn jetzt ebenfalls, und zwei Abschriften
             desselben Knopfes wären zwei Wortlaute in spe. Gerendertes DOM
             unverändert. -->
        <boerdi-search-cta [message]="message()" [ctx]="ctx()" />
      </div>
    }
  `,
})
export class ResultGroupsComponent {
  readonly message = input.required<ChatMessage>();
  readonly ctx = input.required<ResultGroupsContext>();
  /** Läuft gerade ein Turn? Sperrt den Volltext-Knopf (wie im Flach-Grid). */
  readonly isLoading = input(false);

  /** „Inhalt anzeigen" an einer Materialien-Zeile (M17). Diese Box ist die
   *  Default-Oberfläche, deshalb hängt die Aktion auch hier und nicht nur am
   *  Flach-Grid (`inline-result-grouping="false"`). */
  readonly showContentText = output<CardAction>();

  // Box-Icons (fix je Box — ALT chat.component.html:138/157/180/203/226).
  // Die beiden CTA-Icons stehen seit U6b in `search-cta.component`.
  protected readonly topicIcon = ICONS.auto_stories;
  protected readonly collectionIcon = ICONS.collections_bookmark;
  // Zeilen-Symbol im Sammlungen-Kasten: fix der Sammlungs-Stapel. Reine
  // Sammlungen bekommen ihn ohnehin von `getCardIcon`; fix gesetzt zeigen ihn
  // auch die Themenseiten-Karten, die in diesem Kasten als Sammlung stehen.
  protected readonly collectionItemIcon = ICONS.auto_stories;
  protected readonly materialIcon = ICONS.description;
  // Das Web-Symbol steht seit 2026-09-30 in `web-links.component`.
  // `visibility` (Auge = „anzeigen") und bewusst KEIN Dokument-Symbol:
  // vorn in der Zeile steht der Inhaltstyp, und dessen Menge enthält
  // `article`/`description`. Mit einem davon las sich die Zeile, als stünde
  // der Typ zweimal drin — vorn der Typ, hinten die Handlung (Nutzer-
  // Rückmeldung 2026-07-31).
  protected readonly contentTextIcon = ICONS.visibility;

  /** Pures Card-Icon direkt im Template (ALT-Binding `getCardIcon(card)`). */
  protected readonly getCardIcon = getCardIcon;
  /** Kurzform fürs Template — übersetzt über den Kontext der Shell (C1-b2). */
  protected readonly t = (key: string, params?: TranslationParams): string =>
    this.ctx().t(key, params);

  protected readonly hasResults = computed(() => hasGroupedResults(this.message(), this.ctx()));
  protected readonly topicCards = computed(() => groupedTopicCards(this.message()));
  protected readonly collectionCards = computed(() => groupedCollectionCards(this.message()));
  protected readonly contentCards = computed(() => groupedContentCards(this.message()));

  /** ALT `ChatComponent.cardUrl` = `withBsid(getCardPrimaryUrl(card))`. */
  protected cardUrl(card: WloCard): string {
    return this.ctx().withBsid(getCardPrimaryUrl(card));
  }

  /** ALT `ChatComponent.cardTooltip(card)` → 8-2g-Util mit Instanz-ctx. */
  protected cardTooltip(card: WloCard): string | null {
    return cardTooltipUtil(card, null, this.ctx());
  }

  /** Ziel im Sammlungen-Kasten — bei Sammlungen MIT Themenseite die
   *  Sammlung statt der Themenseite (siehe `getCardCollectionUrl`). */
  protected collectionUrl(card: WloCard): string {
    return this.ctx().withBsid(getCardCollectionUrl(card));
  }

  /** Wie `cardTooltip`, aber mit „Sammlung" als Typ — in diesem Kasten ist
   *  auch eine Themenseiten-Karte als Sammlung gemeint. */
  protected collectionTooltip(card: WloCard): string | null {
    return cardTooltipUtil(
      card, this.collectionUrl(card), this.ctx(), this.t('contentType.collection'),
    );
  }
}
