import {
  ChangeDetectionStrategy, Component, HostListener, computed, input, output, signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { WloCard } from './card-types';
import { getCardPrimaryUrl, isInhalt } from './card-utils';
import { WloCardTileComponent } from './wlo-card-tile.component';
import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslationParams } from '../i18n/dictionary';
import { ChatMessage } from '../grouping/message-types';
import { cardTooltip as cardTooltipUtil, ResultGroupsContext } from '../grouping/result-grouping';
import { SearchCtaComponent } from '../grouping/search-cta.component';

/** Aktions-Nutzlast der Sammlungs-Buttons (ALT `browseCollection(node_id, title)`
 *  bzw. `generateLearningPath(node_id, title)`). */
export interface CardAction {
  nodeId: string;
  title: string;
}

/**
 * CardList — die flache Card-Liste einer Bot-Nachricht: Tile-Grid, die
 * Sammlungs-Aktionsleiste (Inhalte / Lernpfad / Themenseite samt Varianten-
 * Dropdown) und die Pagination-Leiste. Visueller Port des ALT-Blocks
 * `chat.component.html:240-378`, der dort inline im Monolithen lag.
 *
 * Kontrollfluss zu Angular 21 übersetzt (`*ngIf`→`@if`, `*ngFor`→`@for`);
 * gerendertes DOM bleibt gleich — inklusive der Verschachtelung von
 * `.card-actions` INNERHALB von `.wlo-card-wrapper` (dafür projiziert die
 * Liste in den Tile-Slot, ALT-Rundungsregel `:not(:has(.card-actions))`).
 *
 * Schnitt wie bei den Geschwistern (result-groups/swimlanes/inline-documents):
 * präsentational + Outputs. Die HOST-FLAG-Gates (`cards-enabled`,
 * `inline-result-grouping`, `hideCards`) bleiben beim Elternteil (Chat-Shell);
 * hier leben nur die Daten-Gates. Ausgeführt werden die Aktionen von
 * `controllers/collection-actions.ts` über die Shell.
 *
 * Das Dropdown ist der einzige eigene Zustand — inklusive ALTs
 * `@HostListener('document:click')`, der es beim Klick daneben schließt.
 *
 * A11y-Feinschliff (Fokus-Ring-Audit, Dropdown-Tastaturmuster) ist der
 * koordinierte Sweep 8-6; hier DOM verbatim wie ALT.
 */
@Component({
  selector: 'boerdi-card-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, SafeSvgPipe, WloCardTileComponent, SearchCtaComponent],
  styleUrl: './card-list.component.scss',
  template: `
    @if (visibleCards().length) {
      <div class="cards-list">
        @for (card of visibleCards(); track $index) {
          <boerdi-wlo-card-tile
            [card]="card"
            [href]="cardUrl(card)"
            [tooltip]="cardTooltip(card)"
            [translate]="ctx().t"
          >
            @if (card.node_type === 'collection' && card.node_id) {
              <div class="card-actions">
                <button
                  matButton="outlined"
                  type="button"
                  class="card-btn-m3"
                  [disabled]="isLoading()"
                  (click)="browse.emit({ nodeId: card.node_id, title: card.title })"
                >
                  <span class="bb-icon" [innerHTML]="ICONS.list | safeSvg"></span>
                  <span>{{ t('cards.browse') }}</span>
                </button>
                <button
                  matButton="outlined"
                  type="button"
                  class="card-btn-m3"
                  [disabled]="isLoading()"
                  (click)="learningPath.emit({ nodeId: card.node_id, title: card.title })"
                >
                  <span class="bb-icon" [innerHTML]="ICONS.route | safeSvg"></span>
                  <span>{{ t('cards.learningPath') }}</span>
                </button>

                <!-- Themenseite: ein Smart-Button auf die beste Variante
                     (Backend sortiert), weitere hinter dem Dropdown. -->
                @if (topicPages(card); as pages) {
                  <div class="tp-wrapper">
                    <a
                      matButton="outlined"
                      class="card-btn-m3"
                      [href]="ctx().withBsid(pages[0].url)"
                      target="_blank"
                      rel="noopener noreferrer"
                      [attr.title]="topicTooltip(card)"
                    >
                      <span class="bb-icon" [innerHTML]="ICONS.language | safeSvg"></span>
                      <span>{{ t('cards.topicPage') }}</span>
                    </a>
                    @if (pages.length > 1) {
                      <!-- Der Wrapper ist KEIN Bedienelement, sondern Delegat: Escape
                           kommt per Bubbling vom fokussierten Toggle bzw. von einem
                           Dropdown-Eintrag. Ein tabindex hier wäre ein nutzloser
                           Tab-Stop und würde die Reihenfolge verschlechtern.
                           (Kein Backtick in diesem Kommentar: das Template ist ein
                           TS-Template-Literal, ein Backtick beendet es.) -->
                      <!-- eslint-disable-next-line @angular-eslint/template/interactive-supports-focus -->
                      <div class="tp-dropdown-wrap" (keydown.escape)="closeDropdownByKeyboard($event)">
                        <button
                          matIconButton
                          type="button"
                          class="tp-toggle"
                          (click)="toggleTopicDropdown($event, card.node_id)"
                          [attr.aria-expanded]="openTopicDropdown() === card.node_id"
                          aria-haspopup="true"
                          [attr.aria-label]="t('cards.topicPageMore')"
                        >
                          <span class="bb-icon" [innerHTML]="ICONS.arrow_drop_down | safeSvg"></span>
                        </button>
                        @if (openTopicDropdown() === card.node_id) {
                          <div class="tp-dropdown">
                            @for (tp of pages; track $index) {
                              <a
                                class="tp-dropdown-item"
                                [href]="ctx().withBsid(tp.url)"
                                target="_blank"
                                rel="noopener noreferrer"
                                [attr.title]="ctx().externalLinkWarning(tp.url) || null"
                                [class.tp-active]="$first"
                              >{{ tp.label }}</a>
                            }
                          </div>
                        }
                      </div>
                    }
                  </div>
                }
              </div>
            } @else if (isInhalt(card) && card.node_id) {
              <!-- M17: Einzelinhalte bekommen genau EINE Aktion — den Volltext
                   im Chat öffnen. Ob es einen gibt, weiß erst der Server; er
                   nennt den Grund, wenn nicht (access_denied etc.), deshalb
                   steht der Knopf an jedem Inhalt mit node_id. -->
              <div class="card-actions">
                <button
                  matButton="tonal"
                  type="button"
                  class="card-btn-m3"
                  [disabled]="isLoading()"
                  (click)="showContentText.emit({ nodeId: card.node_id, title: card.title })"
                >
                  <span class="bb-icon" [innerHTML]="ICONS.visibility | safeSvg"></span>
                  {{ t('cards.showContent') }}
                </button>
              </div>
            }
          </boerdi-wlo-card-tile>
        }
      </div>
    }

    <!-- Pagination: Zähler + „Mehr anzeigen" (schon geladene Karten aufdecken)
         bzw. „Weitere laden" (nächste Seite aus der Sammlung nachholen). -->
    @if (totalCards() > 1) {
      <div class="pagination-bar">
        <span class="pagination-info">
          {{ t('cards.pagination.count', { visible: visibleCards().length, total: totalCards() }) }}
        </span>
        @if (hasHiddenCards()) {
          <button type="button" class="btn-load-more" (click)="showMore.emit(message().id)">
            <span>{{ t('cards.pagination.showMore') }}</span>
            <span class="bb-icon" [innerHTML]="ICONS.arrow_drop_down | safeSvg"></span>
          </button>
        } @else if (message().pagination?.has_more && message().pagination?.collection_id) {
          <button
            type="button"
            class="btn-load-more"
            [disabled]="isLoading()"
            (click)="loadMore.emit(message().id)"
          >
            <span>{{ isLoading() ? t('cards.pagination.loading') : t('cards.pagination.loadMore') }}</span>
            @if (!isLoading()) {
              <span class="bb-icon" [innerHTML]="ICONS.arrow_drop_down | safeSvg"></span>
            }
          </button>
        }
      </div>
    }

    <!-- Absprung in die vollständige, gefilterte WLO-Suche. Steht seit U6b
         (2026-08-09) auch hier: bis dahin hing er allein an der Gruppen-Box,
         und der große Modus — der ihn am ehesten braucht — zeigte statt der
         Box das Raster. Ganz unten, weil er weiterführt, nachdem man die
         Treffer gesehen hat. -->
    <boerdi-search-cta [message]="message()" [ctx]="ctx()" />
  `,
})
export class CardListComponent {
  /** Die Nachricht, deren `cards`/`visibleCardCount`/`pagination` gerendert wird. */
  readonly message = input.required<ChatMessage>();
  /** bsid-Rewrite + Extern-Link-Warnung der Shell (ALT `_groupingCtx`). Seit
   *  U6b der breitere Kontext: der Such-Absprung unten braucht zusätzlich die
   *  Host-Trust-Abfrage für seine `_self`/`_blank`-Entscheidung. */
  readonly ctx = input.required<ResultGroupsContext>();
  /** Läuft gerade ein Turn? Sperrt die Aktions-Buttons (ALT `isLoading`). */
  readonly isLoading = input(false);

  /** „Inhalte" — Sammlung im Chat auflisten. */
  readonly browse = output<CardAction>();
  /** „Lernpfad" — Lernpfad aus der Sammlung generieren. */
  readonly learningPath = output<CardAction>();
  /** „Inhalt anzeigen" — Volltext des Einzelinhalts im Chat öffnen (M17). */
  readonly showContentText = output<CardAction>();
  /** „Mehr anzeigen" — schon geladene Karten aufdecken (Message-ID). */
  readonly showMore = output<string>();
  /** „Weitere laden" — nächste Seite aus der Sammlung holen (Message-ID). */
  readonly loadMore = output<string>();

  /** Offenes Themenseiten-Dropdown (Karten-`node_id`), ALT `openTopicDropdown`. */
  readonly openTopicDropdown = signal<string | null>(null);

  readonly ICONS = ICONS;
  /** Einzelinhalt? — entscheidet über die Volltext-Aktion (M17). Aus
   *  `card-utils` statt eigener Prüfung, damit Flach-Grid und Gruppen-Box
   *  dieselbe Definition benutzen. */
  readonly isInhalt = isInhalt;
  /** Kurzform fürs Template — übersetzt über den Kontext der Shell (C1-b2). */
  protected readonly t = (key: string, params?: TranslationParams): string =>
    this.ctx().t(key, params);

  private readonly cards = computed<WloCard[]>(() => this.message().cards || []);
  readonly totalCards = computed(() => this.cards().length);
  /** Sichtbares Fenster — ALT `getVisibleCards` (Default-Seitengröße 5). */
  readonly visibleCards = computed(() => this.cards().slice(0, this.message().visibleCardCount || 5));
  /** Noch ungezeigte, aber bereits geladene Karten? ALT `hasHiddenCards`. */
  readonly hasHiddenCards = computed(() => this.totalCards() > (this.message().visibleCardCount || 5));

  /** Typ-bewusste Ziel-URL der Karte inkl. bsid. ALT `cardUrl`. */
  cardUrl(card: WloCard): string {
    return this.ctx().withBsid(getCardPrimaryUrl(card));
  }

  /** Tooltip der Karte (Typ-Label + Extern-Warnung). ALT `cardTooltip`. */
  cardTooltip(card: WloCard): string | null {
    return cardTooltipUtil(card, this.cardUrl(card), this.ctx());
  }

  /** Themenseiten-Varianten der Karte, oder `null` wenn keine da sind.
   *  `WloCard.topic_pages` ist im Typ nicht-optional, in echten Backend-
   *  Payloads aber oft gar nicht gesetzt (ALT prüfte darum `card.topic_pages &&
   *  …`). Dieser Accessor ist die einzige Stelle, die das abfedert — im Template
   *  bleibt es dadurch bei einem einfachen `@if (…; as pages)`. */
  topicPages(card: WloCard): WloCard['topic_pages'] | null {
    const pages = card.topic_pages;
    return pages && pages.length ? pages : null;
  }

  /** Tooltip des Themenseiten-Buttons — nennt weitere Varianten und hängt die
   *  Extern-Warnung an. Verbatim aus ALT chat.component.html:320-323. */
  topicTooltip(card: WloCard): string {
    const pages = this.topicPages(card) || [];
    const first = pages[0];
    const base = pages.length > 1
      ? this.t('cards.topicTooltip.more', { variant: first.label })
      : this.t('cards.topicTooltip.single');
    const warning = this.ctx().externalLinkWarning(first.url);
    return warning ? base + ' — ' + warning : base;
  }

  /** Dropdown der Karte auf/zu. `stopPropagation`, damit der Dokument-Listener
   *  unten es nicht im selben Klick wieder schließt. Verbatim ALT 1065-1068. */
  toggleTopicDropdown(event: Event, nodeId: string): void {
    event.stopPropagation();
    this.openTopicDropdown.update(open => (open === nodeId ? null : nodeId));
  }

  /** Klick irgendwo sonst schließt das Dropdown. Verbatim ALT 1062-1063. */
  @HostListener('document:click')
  closeTopicDropdown(): void {
    this.openTopicDropdown.set(null);
  }

  /** Escape schließt das Dropdown und gibt den Fokus an seinen Toggle zurück
   *  (8-6, ARIA-APG-Muster für Menü-Buttons). ALT kannte nur ALTs
   *  `document:click` — Tastatur-Nutzer kamen aus dem offenen Dropdown nicht
   *  mehr heraus, ohne mit der Maus daneben zu klicken.
   *
   *  `stopPropagation` ist load-bearing: die Widget-Hülle schließt bei Escape
   *  das ganze Chat-Panel (`@HostListener('keydown.escape')`). Ohne den Stopp
   *  würde ein Escape im Dropdown das Panel mitreißen. */
  closeDropdownByKeyboard(event: Event): void {
    if (this.openTopicDropdown() === null) return;
    event.stopPropagation();
    this.openTopicDropdown.set(null);
    const wrap = event.currentTarget as HTMLElement | null;
    (wrap?.querySelector('.tp-toggle') as HTMLElement | null)?.focus();
  }
}
