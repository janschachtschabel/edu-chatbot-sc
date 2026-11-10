/**
 * `<boerdi-ui-debug-panel>` — das Diagnose-Panel unter dem Chat (Redaktions- und Entwickler-Sicht),
 * seit Paket BU-3 ein nachgeladenes, rahmenloses Element (Plan 2026-11-09 §5i, Entscheid Ud-5 neu):
 * nur wer den Debug-Schalter nutzt, lädt es. Verhalten wie zuvor als Komponente
 * (`debug-panel.component.ts`, visueller Port des ALT-Blocks `chat.component.html:422-607`):
 *
 * - `show` und ein Debug-Block → das volle Panel in sechs Abschnitten;
 * - `show` ohne Debug-Block (seit Paket 18C/D nur mit Freigabe), aber mit `ui` → die Zusammenfassung
 *   aus `ui` und der Hinweis, dass die Diagnose im Studio steht (übersetzt über `uebersetzen` —
 *   `translate` ist schon ein Attribut jedes HTML-Elements);
 * - sonst nichts.
 *
 * Eigenschaften wie beim Vertrag der UI-Module: jede Zuweisung zeichnet neu. Fremdtext steht immer
 * als Text. Ein zweites Laden des Bündels definiert nicht noch einmal (`definiere`).
 */
import type { DebugInfo, UiInfo } from '../../grouping/message-types';
import type { TranslateFn } from '../../i18n/i18n';
import { el, gespraechsPhase, klassifikation, modulation, patternEngine, toolsUndWissen } from './debug-abschnitte';
import { sicherheit } from './debug-sicherheit';
import { STIL } from './ui-debug-panel.stil.generated';

export const ELEMENT = 'boerdi-ui-debug-panel';

/** Alles, was die Hülle auf einmal setzt (Review BU-3, Befund 4: einmal zeichnen statt viermal). */
export interface DebugPanelWerte {
  debug: DebugInfo | null;
  ui: UiInfo | null;
  show: boolean;
  uebersetzen: TranslateFn;
}

export class UiDebugPanelElement extends HTMLElement {
  private _debug: DebugInfo | null = null;
  private _ui: UiInfo | null = null;
  private _show = false;
  private _translate: TranslateFn = (key) => key;
  private readonly inhalt: HTMLDivElement;
  /** Die Box bleibt dasselbe Element, solange das Panel offen ist — ihre Scroll-Lage auch. */
  private readonly box = el('div', 'debug-panel');

  constructor() {
    super();
    const wurzel = this.attachShadow({ mode: 'open' });
    const stil = document.createElement('style');
    stil.textContent = STIL;
    this.inhalt = document.createElement('div');
    wurzel.append(stil, this.inhalt);
  }

  set debug(d: DebugInfo | null) { this._debug = d ?? null; this.zeichne(); }
  get debug(): DebugInfo | null { return this._debug; }
  set ui(u: UiInfo | null) { this._ui = u ?? null; this.zeichne(); }
  get ui(): UiInfo | null { return this._ui; }
  set show(s: boolean) { this._show = s === true; this.zeichne(); }
  get show(): boolean { return this._show; }
  set uebersetzen(t: TranslateFn) { this._translate = t; this.zeichne(); }
  get uebersetzen(): TranslateFn { return this._translate; }

  /** Alle Werte auf einmal — ein Zeichnen. */
  setze(w: DebugPanelWerte): void {
    this._debug = w.debug ?? null;
    this._ui = w.ui ?? null;
    this._show = w.show === true;
    this._translate = w.uebersetzen;
    this.zeichne();
  }

  private zeichne(): void {
    const d = this._debug;
    const u = this._ui;
    if (!this._show || (!d && !u)) {
      this.inhalt.replaceChildren();
      return;
    }
    // Review BU-3, Befund 6: ein kaputter Block (etwa `null` in einer Liste) zeigt nichts — nie
    // still weiter den alten Zug.
    try {
      this.box.replaceChildren(...this.abschnitte(d, u));
    } catch (fehler) {
      console.warn('boerdi-chat: Debug-Panel konnte den Block nicht zeigen.', fehler);
      this.inhalt.replaceChildren();
      return;
    }
    if (this.box.parentNode !== this.inhalt) this.inhalt.replaceChildren(this.box);
  }

  private abschnitte(d: DebugInfo | null, u: UiInfo | null): Node[] {
    const panel: Node[] = [];
    if (d) {
      panel.push(...gespraechsPhase(d), ...klassifikation(d), ...patternEngine(d), ...modulation(d),
        ...toolsUndWissen(d), ...sicherheit(d));
    } else if (u) {
      const t = this._translate;
      const hinweis = el('p', 'debug-row', t('debug.onlyInStudio'));
      hinweis.setAttribute('role', 'note');
      const reihe = (key: string, wert: string) =>
        el('div', 'debug-row', el('span', 'debug-label', `${t(key)}:`), ' ', wert || '–');
      panel.push(hinweis, reihe('debug.ui.pattern', String(u.pattern ?? '')),
        reihe('debug.ui.intent', String(u.intent ?? '')), reihe('debug.ui.state', String(u.state ?? '')),
        reihe('debug.ui.tools', (u.tools_called ?? []).join(', ')));
    }
    return panel;
  }
}

/** Pflicht aus dem Element-Vertrag: ein zweites Laden des Bündels definiert nicht noch einmal. */
export function definiere(): void {
  if (!customElements.get(ELEMENT)) customElements.define(ELEMENT, UiDebugPanelElement);
}

definiere();
