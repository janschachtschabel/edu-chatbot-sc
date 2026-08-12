import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatCardModule } from '@angular/material/card';

import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslateFn } from '../i18n/i18n';
import { WloCard } from './card-types';
import { getCardIcon, getContentTypeLabel, isInhalt, isSammlung, isThemenseite } from './card-utils';
import { getLicenseShort } from './license';

/**
 * WloCard-Tile — die einzelne Ergebniskarte im Chat. Ursprünglich visueller
 * Port der ALT-`.wlo-card` (chat.component.html:246-294); seit 2026-07-31 folgt
 * der Aufbau der edu-sharing-Kachel aus der Nutzer-Vorlage (Plan
 * `docs/plans/2026-07-31-material3-edu-sharing.md`):
 *
 *   [ Vorschaubild, formatfüllend + Lizenz-Siegel ]
 *   Quelle (publisher)
 *   Titel (2 Zeilen)
 *   Beschreibung (2 Zeilen)
 *   Materialart · Fach · Stufe (Zeilen mit Symbol)
 *
 * Der Medienbereich steht IMMER, auch ohne `preview_url` — sonst wäre eine
 * bildlose Kachel flacher als ihre Nachbarn (Nutzer-Vorgabe: einheitliche
 * Größen). Ohne Bild trägt er das Typ-Symbol statt eines Fotos.
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
  imports: [MatCardModule, SafeSvgPipe],
  styleUrl: './wlo-card-tile.component.scss',
  template: `
    <mat-card
      appearance="outlined"
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
        <div class="card-media">
          @if (card().preview_url) {
            <img [src]="card().preview_url" [alt]="card().title" loading="lazy" class="card-img" />
          } @else {
            <span class="card-media-fallback" aria-hidden="true" [innerHTML]="placeholderIcon | safeSvg"></span>
          }
          @if (card().license) {
            <span class="card-license-badge" [title]="card().license">{{ licenseShort() }}</span>
          }
        </div>

        <div class="card-body">
          @if (card().publisher) {
            <div class="card-source">{{ card().publisher }}</div>
          }
          <div class="card-title">{{ card().title }}</div>
          @if (card().description) {
            <div class="card-desc">{{ descPreview() }}</div>
          }

          <div class="card-meta">
            <span class="card-meta-row card-content-type" [title]="contentTypeTitle()">
              <span class="card-content-icon" [innerHTML]="icon() | safeSvg"></span>
              <span class="card-content-label">{{ label() }}</span>
            </span>
            @if (fach(); as f) {
              <span class="card-meta-row card-meta-fach">
                <span class="card-meta-icon" [innerHTML]="bookIcon | safeSvg"></span>
                <span>{{ f }}</span>
              </span>
            }
            @if (stufe(); as s) {
              <span class="card-meta-row card-meta-stufe">
                <span class="card-meta-icon" [innerHTML]="schoolIcon | safeSvg"></span>
                <span>{{ s }}</span>
              </span>
            }
          </div>
        </div>
      </a>
      <!-- Slot für die Sammlungs-Aktionsleiste (8-2i): in ALT ist .card-actions
           ein Geschwister der Karte INNERHALB des Wrappers — die Rundungs-Regel
           .wlo-card-wrapper:not(:has(.card-actions)) hängt an dieser
           Verschachtelung. Das Tile bleibt präsentational; die Buttons besitzt
           die Card-List. (Keine Backticks hier: das Template ist ein
           Template-Literal.) -->
      <ng-content />
    </mat-card>
  `,
})
export class WloCardTileComponent {
  readonly card = input.required<WloCard>();
  /** Aufgelöste Primary-URL (ALT `cardUrl(card)`); vom Elternteil geliefert. */
  readonly href = input<string>('#');
  /** Title-Tooltip (ALT `cardTooltip(card)`); `null` → Attribut entfällt. */
  readonly tooltip = input<string | null>(null);
  /** Übersetzer (C1-b3) — die Kachel leitet ihr Typ-Label selbst aus
   *  `getContentTypeLabel` ab, und das braucht seit C1-b3 einen Übersetzer.
   *  Eigener Input statt `GroupingContext`: die Kachel ist präsentational und
   *  kennt weder bsid noch Trust. PFLICHT wie `[translate]` an der Shell —
   *  eine vergessene Bindung soll ein Fehler sein, keine stumm deutsche Zeile. */
  readonly translate = input.required<TranslateFn>();

  protected readonly schoolIcon = ICONS.school;
  protected readonly bookIcon = ICONS.menu_book;
  /** Platzhalter im Medienfeld, wenn die Karte kein Vorschaubild hat.
   *  Bewusst ein NEUTRALES Bildsymbol und nicht das Typ-Symbol: der Inhaltstyp
   *  wird genau einmal bebildert, in der Metazeile (Nutzer 2026-07-31, „vorn
   *  würde reichen"). */
  protected readonly placeholderIcon = ICONS.image;

  protected readonly themenseite = computed(() => isThemenseite(this.card()));
  protected readonly sammlung = computed(() => isSammlung(this.card()));
  protected readonly inhalt = computed(() => isInhalt(this.card()));
  protected readonly icon = computed(() => getCardIcon(this.card()));
  protected readonly label = computed(() => getContentTypeLabel(this.card(), this.translate()));
  protected readonly licenseShort = computed(() => getLicenseShort(this.card().license));

  protected readonly contentTypeTitle = computed(() => {
    const c = this.card();
    return getContentTypeLabel(c, this.translate()) + (c.title ? ': ' + c.title : '');
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
