import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import { WloCard } from './card-types';
import { getCardIcon, getContentTypeLabel, isInhalt, isSammlung, isThemenseite } from './card-utils';
import { getLicenseShort } from './license';

/**
 * WloCard-Tile — die einzelne Ergebniskarte im Chat. Visueller Port der
 * ALT-`.wlo-card` (chat.component.html:246-294), die dort inline im
 * chat.component-Monolithen lag; NEU als eigenständige, präsentationale
 * Komponente. Rendert Header (Typ-Icon + -Label), Body (Titel, gekürzte
 * Beschreibung, Vorschau-Thumb mit Lizenz-Badge) und Footer (Bildungsstufe,
 * Fach).
 *
 * Präsentational: der bereits aufgelöste `href` und `tooltip` kommen als
 * Inputs vom Elternteil (in ALT `cardUrl()`/`cardTooltip()` der
 * ChatComponent — Session-/Trusted-Host-Logik, die das Tile nicht besitzt).
 * Klassifikation/Icon/Label/Lizenzkürzel leitet das Tile selbst aus der
 * portierten `card-utils`/`license`-Logik ab.
 *
 * NICHT enthalten (eigene Slices): die `.card-actions`-Buttons
 * (Sammlung/Themenseite) und die Pagination — beide hängen an
 * ChatComponent-State/-Methoden und folgen mit der Chat-Shell (8-2i).
 * `@if` ersetzt ALTs `*ngIf` (Angular-21-Kontrollfluss); gerendertes DOM
 * bleibt gleich.
 */
@Component({
  selector: 'boerdi-wlo-card-tile',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe],
  styleUrl: './wlo-card-tile.component.scss',
  template: `
    <div
      class="wlo-card-wrapper"
      [class.is-themenseite]="themenseite()"
      [class.is-sammlung]="sammlung()"
      [class.is-inhalt]="inhalt()"
    >
      <a
        class="wlo-card"
        [href]="href()"
        target="_blank"
        rel="noopener noreferrer"
        [attr.title]="tooltip()"
        (click)="$event.stopPropagation()"
      >
        <div class="card-header">
          <span class="card-content-type" [title]="contentTypeTitle()">
            <span class="card-content-icon" [innerHTML]="icon() | safeSvg"></span>
            <span class="card-content-label">{{ label() }}</span>
          </span>
        </div>

        <div class="card-body">
          <div class="card-title">{{ card().title }}</div>
          <div class="card-body-row">
            <div class="card-desc-wrap">
              @if (card().description) {
                <div class="card-desc">{{ descPreview() }}</div>
              }
            </div>
            @if (card().preview_url) {
              <div class="card-thumb-side">
                <img [src]="card().preview_url" [alt]="card().title" loading="lazy" class="card-img-side" />
                @if (card().license) {
                  <span class="card-license-badge-side" [title]="card().license">{{ licenseShort() }}</span>
                }
              </div>
            }
          </div>
        </div>

        <div class="card-footer">
          @if (stufe(); as s) {
            <span class="footer-meta footer-stufe">
              <span class="footer-icon" [innerHTML]="schoolIcon | safeSvg"></span>
              <span>{{ s }}</span>
            </span>
          }
          @if (fach(); as f) {
            <span class="footer-meta footer-fach">
              <span class="footer-icon" [innerHTML]="bookIcon | safeSvg"></span>
              <span>{{ f }}</span>
            </span>
          }
        </div>
      </a>
      <!-- Slot für die Sammlungs-Aktionsleiste (8-2i): in ALT ist .card-actions
           ein Geschwister der Karte INNERHALB des Wrappers — die Rundungs-Regel
           .wlo-card-wrapper:not(:has(.card-actions)) hängt an dieser
           Verschachtelung. Das Tile bleibt präsentational; die Buttons besitzt
           die Card-List. (Keine Backticks hier: das Template ist ein
           Template-Literal.) -->
      <ng-content />
    </div>
  `,
})
export class WloCardTileComponent {
  readonly card = input.required<WloCard>();
  /** Aufgelöste Primary-URL (ALT `cardUrl(card)`); vom Elternteil geliefert. */
  readonly href = input<string>('#');
  /** Title-Tooltip (ALT `cardTooltip(card)`); `null` → Attribut entfällt. */
  readonly tooltip = input<string | null>(null);

  protected readonly schoolIcon = ICONS.school;
  protected readonly bookIcon = ICONS.menu_book;

  protected readonly themenseite = computed(() => isThemenseite(this.card()));
  protected readonly sammlung = computed(() => isSammlung(this.card()));
  protected readonly inhalt = computed(() => isInhalt(this.card()));
  protected readonly icon = computed(() => getCardIcon(this.card()));
  protected readonly label = computed(() => getContentTypeLabel(this.card()));
  protected readonly licenseShort = computed(() => getLicenseShort(this.card().license));

  protected readonly contentTypeTitle = computed(() => {
    const c = this.card();
    return getContentTypeLabel(c) + (c.title ? ': ' + c.title : '');
  });

  /** ALT: `{{ desc | slice:0:120 }}{{ desc.length > 120 ? '…' : '' }}`. */
  protected readonly descPreview = computed(() => {
    const d = this.card().description || '';
    return d.length > 120 ? d.slice(0, 120) + '…' : d;
  });

  // Footer-Meta defensiv (die Card-JSON kann die Arrays im Real-Backend
  // auslassen, obwohl der Typ sie führt): `?.[0]` liegt im TS statt im
  // Template, damit kein NG8107 („optional chain not nullable") entsteht.
  protected readonly stufe = computed(() => this.card().educational_contexts?.[0]);
  protected readonly fach = computed(() => this.card().disciplines?.[0]);
}
