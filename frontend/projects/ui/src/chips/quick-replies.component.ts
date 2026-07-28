import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { ICONS } from '../icons/icons';
import { SafeSvgPipe } from '../icons/safe-svg.pipe';
import { actionQuickReplyLabel } from './action-qr';
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
  imports: [SafeSvgPipe],
  styleUrl: './quick-replies.component.scss',
  template: `
    @if (enabled() && quickReplies().length) {
      <div class="quick-replies">
        @for (qr of quickReplies(); track $index) {
          @if (!shouldHide(qr)) {
            @if (isGuide(qr)) {
              <button
                type="button"
                class="qr-btn qr-btn--guide"
                title="Im aktuellen Tab zur Seite navigieren"
                (click)="guideQuickReply.emit(qr)"
              >
                <span class="bb-icon" [innerHTML]="exploreIcon | safeSvg"></span>
                <span>{{ guideLabel(qr) }}</span>
              </button>
            } @else {
              <button type="button" class="qr-btn" (click)="quickReply.emit(qr)">{{ label(qr) }}</button>
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

  /** Roher qr-String eines Standard-Chips — der Shell routet (Tour/Action/Text). */
  readonly quickReply = output<string>();
  /** Roher qr-String eines Guide-Chips — der Shell navigiert (Same-Tab). */
  readonly guideQuickReply = output<string>();

  protected readonly exploreIcon = ICONS.explore;

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
    return guideQuickReplyLabel(qr, this.guideModeActive());
  }

  /** ALT `quickReplyLabel(qr)` = `actionQuickReplyLabel` (Action-Pill zeigt sein Label). */
  protected label(qr: string): string {
    return actionQuickReplyLabel(qr);
  }
}
