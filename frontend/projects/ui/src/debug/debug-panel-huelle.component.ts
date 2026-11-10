import {
  ChangeDetectionStrategy, Component, computed, effect, type ElementRef, input, signal, untracked, viewChild,
} from '@angular/core';

import type { DebugInfo, UiInfo } from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';

/** Was das nachgeladene Element annimmt (`nachgeladen/ui-debug-panel/ui-debug-panel.element.ts`). */
interface DebugPanelElement extends HTMLElement {
  setze(werte: { debug: DebugInfo | null; ui: UiInfo | null; show: boolean; uebersetzen: TranslateFn }): void;
}

type Stand = 'nicht' | 'laedt' | 'bereit' | 'fehler';

/** Name des Bündels im Nachlade-Index und des Elements (Paket BU-3). */
export const DEBUG_PANEL_MODUL = 'ui_debug_panel';
const ELEMENT = 'boerdi-ui-debug-panel';

/**
 * Paket BU-3 (Plan 2026-11-09 §5i, Entscheid Ud-5 neu): die Hülle des Debug-Panels in der Shell.
 * Das Panel ist ein nachgeladenes, rahmenloses Element — nur wer den Debug-Schalter nutzt, lädt es
 * (`/widget/module/`, Index und SRI wie die UI-Module). Geladen wird erst, wenn es zu sehen sein
 * soll (Schalter an und ein Debug-Block oder `ui` da), und nur einmal; danach reicht die Hülle bei
 * jeder Änderung alles an dasselbe Element weiter (`setze`: ein Zeichnen). Eine ständige Statuszeile
 * sagt „lädt“ und einen Fehler an (Review BU-3, Befund 5). Nach einem Fehler versucht Aus und wieder
 * An es erneut (Befund 3) — der Lader lässt das zu.
 *
 * Im Dev-Server (`ng serve widget`) ist der Nachlade-Index leer: dort meldet das Panel immer den
 * Ladefehler; zum Ausprobieren `npm run build:widget` (Review BU-3, Befund 2).
 */
@Component({
  selector: 'boerdi-debug-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Immer im DOM (auch leer): eine erst eingefügte Live-Region sagen Vorleser oft nicht an. -->
    <p class="debug-lade-stand" role="status">{{ standText() }}</p>
    <div #ort></div>
  `,
  styles: [`
    :host { display: block; }
    .debug-lade-stand { margin: 0; padding: 0 14px; font-size: 0.72rem; color: var(--mat-sys-on-surface-variant); }
    .debug-lade-stand:not(:empty) { padding-block: 6px; }
  `],
})
export class DebugPanelHuelleComponent {
  readonly debug = input<DebugInfo | null>(null);
  readonly ui = input<UiInfo | null>(null);
  readonly translate = input.required<TranslateFn>();
  readonly show = input(false);
  /** Der Lader der Shell (`erzeugeLader`); ohne ihn bleibt das Panel weg. */
  readonly nachladen = input<((modul: string) => Promise<void>) | null>(null);

  private readonly ort = viewChild<ElementRef<HTMLElement>>('ort');
  private element: DebugPanelElement | null = null;
  protected readonly stand = signal<Stand>('nicht');
  protected readonly sichtbar = computed(() => this.show() && (!!this.debug() || !!this.ui()));
  protected readonly standText = computed(() => {
    if (!this.sichtbar()) return '';
    const s = this.stand();
    return s === 'laedt' ? this.translate()('debug.laedt') : s === 'fehler' ? this.translate()('debug.ladeFehler') : '';
  });

  constructor() {
    effect(() => {
      if (!this.sichtbar()) {
        // Befund 3: nach einem Fehler gilt das nächste Einschalten als neuer Versuch
        if (untracked(this.stand) === 'fehler') this.stand.set('nicht');
        return;
      }
      if (untracked(this.stand) !== 'nicht') return;
      const lader = this.nachladen();
      if (!lader) return;
      this.stand.set('laedt');
      lader(DEBUG_PANEL_MODUL).then(
        () => this.stand.set(customElements.get(ELEMENT) ? 'bereit' : 'fehler'),
        () => this.stand.set('fehler'),
      );
    });
    effect(() => {
      const ort = this.ort()?.nativeElement;
      if (this.stand() !== 'bereit' || !ort) return;
      const werte = { debug: this.debug(), ui: this.ui(), show: this.show(), uebersetzen: this.translate() };
      untracked(() => {
        // Wie der Element-Vertrag (`_nachladen/element-vertrag.ts`): erst alle Werte setzen, dann
        // einhängen — `connectedCallback` sieht schon alles (Querschnitts-Review Q-10).
        const neu = !this.element;
        this.element ??= ort.ownerDocument.createElement(ELEMENT) as DebugPanelElement;
        this.element.setze(werte);
        if (neu) ort.appendChild(this.element);
      });
    });
  }
}
