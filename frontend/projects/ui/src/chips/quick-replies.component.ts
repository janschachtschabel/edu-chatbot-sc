import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import type { TranslateFn } from '../i18n/i18n';
import { actionQuickReplyLabel } from './action-qr';
import { isAuthQuickReply } from './auth-qr';
import { guideQuickReplyLabel, isGuideQuickReply, shouldHideGuideQuickReply } from './guide-qr';

/**
 * QuickReplies — die Quick-Reply-Chip-Reihe unter einer Bot-Nachricht.
 * Visueller Port des ALT-Blocks (`chat.component.html:400-416` +
 * `.quick-replies`/`.qr-btn`/`.qr-btn--guide` aus chat.component.scss), der dort
 * inline im chat.component-Monolithen lag; NEU als eigenständige präsentationale
 * Komponente über den bereits portierten Chip-Helfern (8-2c action-qr/guide-qr).
 *
 * Präsentational: nimmt die QR-Strings DIREKT als Input (nicht die ganze
 * ChatMessage — nur ein Feld gebraucht, kein Modellwachstum in diesem Slice) und
 * gibt bei Klick den ROHEN qr-String nach oben (`quickReply`/`guideQuickReply`).
 * Die Klick-Logik (Tour-Start-Routing, Action-Pill-Parsing → Direct-Action-Turn,
 * Same-Tab-Navigation) bleibt beim Elternteil (Chat-Shell 8-4) — ALT
 * `onQuickReply`/`onGuideQuickReply`. Der Shell entscheidet auch, ob die
 * Komponente überhaupt gerendert wird; `enabled` spiegelt ALTs
 * `quickRepliesEnabledBool` (Widget-Modus, dort konstant true).
 *
 * Kontrollfluss zu Angular-21 übersetzt (`*ngIf`→`@if`, `*ngFor`→`@for track
 * $index`); gerendertes DOM bleibt gleich. `guideModeActive` (ALT
 * Compat-Konstante, seit Welle E immer true) wird als Input durchgereicht und
 * pro Aufruf an die reinen guide-qr-Helfer gegeben. Die Buttons sind echte
 * `<button>` mit Text-Label (korrekter Accessible-Name); der A11y-Feinschliff
 * (dekorative Icons `aria-hidden`) ist der koordinierte Sweep 8-6 — hier DOM
 * verbatim wie ALT.
 */
@Component({
  selector: 'boerdi-quick-replies',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, SafeSvgPipe],
  styleUrl: './quick-replies.component.scss',
  template: `
    @if (enabled() && quickReplies().length) {
      <div class="quick-replies">
        @for (qr of quickReplies(); track $index) {
          @if (!shouldHide(qr)) {
            @if (isAuth(qr)) {
              <!-- Anmelde-Chip (C5-c2): "filled" wie der Lotsen-Chip, denn er
                   ist die HAUPT-Antwort auf die gerade gestellte Frage; der
                   "Nur lesen"-Chip daneben bleibt getönt. Zusammen lesen sich
                   die beiden als Frage mit zwei Antworten.
                   Die Beschriftung kommt aus dem Katalog und nicht aus dem
                   Marker: sie wird nirgends hingeschickt (der Klick startet
                   einen Vorgang im Browser) und folgt so dem Sprachumschalter.
                   Kein Icon — es gäbe keins, das "anmelden" ohne Erklärung
                   trägt, und ein beliebiges wäre Zierrat. -->
              <button
                matButton="filled"
                type="button"
                class="qr-btn"
                (click)="quickReply.emit(qr)"
              >
                {{ translate()('auth.signIn') }}
              </button>
            } @else if (isGuide(qr)) {
              <!-- filled für den Lotsen-Chip, tonal für die übrigen — das ist
                   die ALT-Hierarchie in M3-Begriffen: der Lotsen-Chip war voll
                   eingefärbt, die Vorschlags-Chips getönt. Outlined
                   (transparent) hätte die Tönung verloren.
                   (Keine Backticks hier: das Template ist ein Template-Literal,
                   ein Backtick beendet es.) -->
              <button
                matButton="filled"
                type="button"
                class="qr-btn qr-btn--guide"
                title="Im aktuellen Tab zur Seite navigieren"
                (click)="guideQuickReply.emit(qr)"
              >
                <span class="bb-icon" [innerHTML]="exploreIcon | safeSvg"></span>
                <span>{{ guideLabel(qr) }}</span>
              </button>
            } @else {
              <button matButton="tonal" type="button" class="qr-btn" (click)="quickReply.emit(qr)">
                {{ label(qr) }}
              </button>
            }
          }
        }
      </div>
    }
  `,
})
export class QuickRepliesComponent {
  /** Die QR-Strings der Nachricht (ALT `msg.quickReplies`). */
  readonly quickReplies = input<readonly string[]>([]);
  /** ALT `quickRepliesEnabledBool` (Widget-Modus; dort konstant true). */
  readonly enabled = input(true);
  /** ALT `guideModeActive` (Compat-Konstante, immer true) → an die guide-qr-Helfer. */
  readonly guideModeActive = input(true);
  /** Übersetzer (C1-b4) — nur für den Rückfall-Text eines Guide-Chips ohne
   *  Label. PFLICHT wie an der Shell: eine vergessene Bindung soll ein Fehler
   *  sein, keine stumm deutsche Beschriftung. */
  readonly translate = input.required<TranslateFn>();

  /** Roher qr-String eines Standard-Chips — der Shell routet (Tour/Action/Text). */
  readonly quickReply = output<string>();
  /** Roher qr-String eines Guide-Chips — der Shell navigiert (Same-Tab). */
  readonly guideQuickReply = output<string>();

  protected readonly exploreIcon = ICONS.explore;

  /** Anmelde-Chip (C5-c2)? Er wird VOR dem Lotsen-Chip geprüft, weil er ein
   *  eigener Marker ist und sonst als gewöhnliche Antwort durchginge. */
  protected isAuth(qr: string): boolean {
    return isAuthQuickReply(qr);
  }

  /** ALT `isGuideQuickReply(qr)` — Delegate auf den guide-qr-Helfer mit Instanz-Flag. */
  protected isGuide(qr: string): boolean {
    return isGuideQuickReply(qr, this.guideModeActive());
  }

  /** ALT `shouldHideQuickReply(qr)` — Guide-QR bei ausgeschaltetem Lotsen-Modus. */
  protected shouldHide(qr: string): boolean {
    return shouldHideGuideQuickReply(qr, this.guideModeActive());
  }

  /** ALT `guideQuickReplyLabel(qr)`. */
  protected guideLabel(qr: string): string {
    return guideQuickReplyLabel(qr, this.guideModeActive(), this.translate());
  }

  /** ALT `quickReplyLabel(qr)` = `actionQuickReplyLabel` (Action-Pill zeigt sein Label). */
  protected label(qr: string): string {
    return actionQuickReplyLabel(qr);
  }
}
