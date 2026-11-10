/**
 * Gemeinsamer Baum-Kern: die Regel der höflichen Statuszeile (`aria-live="polite"`) ohne Angular
 * (Paket BU-2, BU-f) — für Komponenten (`BaumAnsage`) und nachgeladene Custom Elements.
 *
 * Derselbe Text wie zuletzt wird erst geleert und {@link ANSAGE_PAUSE_MS} später neu gesetzt —
 * sonst ändert sich nichts, und Vorleser sagen ihn nicht noch einmal an. In einem eigenen Schritt
 * wie der `LiveAnnouncer` des CDK: im selben Zeichnen sähe die Zugänglichkeits-Schnittstelle
 * keine Änderung. Der Besitzer ruft {@link AnsageKern.aufraeumen} beim Zerstören.
 */

/** Pause zwischen Leeren und erneutem Setzen derselben Ansage (wie `LiveAnnouncer` im CDK). */
export const ANSAGE_PAUSE_MS = 100;

export class AnsageKern {
  private _text = '';
  private frist: ReturnType<typeof setTimeout> | undefined;

  /** `setzen` schreibt den Text in die Statuszeile (ein Signal, ein `textContent`). */
  constructor(private readonly setzen: (text: string) => void) {}

  /** Der zuletzt gesetzte Text. */
  get text(): string {
    return this._text;
  }

  sagen(text: string): void {
    clearTimeout(this.frist);
    if (this._text !== text) {
      this.setze(text);
      return;
    }
    this.setze('');
    this.frist = setTimeout(() => this.setze(text), ANSAGE_PAUSE_MS);
  }

  aufraeumen(): void {
    clearTimeout(this.frist);
  }

  private setze(text: string): void {
    this._text = text;
    this.setzen(text);
  }
}
