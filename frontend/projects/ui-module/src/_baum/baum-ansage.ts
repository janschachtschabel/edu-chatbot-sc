/**
 * Gemeinsamer Baum-Kern (Paket U2): die höfliche Statuszeile (`aria-live="polite"`) beider Bäume.
 * Seit U2 hier statt in `ui-themenbaum` (Verhalten unverändert, Review U1-h Befund 10).
 *
 * Derselbe Text wie zuletzt wird erst geleert und {@link ANSAGE_PAUSE_MS} später neu gesetzt —
 * sonst ändert sich nichts, und Vorleser sagen ihn nicht noch einmal an. In einem eigenen Schritt
 * wie der `LiveAnnouncer` des CDK: im selben Zeichnen sähe die Zugänglichkeits-Schnittstelle
 * keine Änderung. Die Komponente ruft {@link BaumAnsage.aufraeumen} beim Zerstören.
 */
import { signal } from '@angular/core';

/** Pause zwischen Leeren und erneutem Setzen derselben Ansage (wie `LiveAnnouncer` im CDK). */
export const ANSAGE_PAUSE_MS = 100;

export class BaumAnsage {
  /** Der Text der Statuszeile. */
  readonly text = signal('');
  private frist: ReturnType<typeof setTimeout> | undefined;

  sagen(text: string): void {
    clearTimeout(this.frist);
    if (this.text() !== text) {
      this.text.set(text);
      return;
    }
    this.text.set('');
    this.frist = setTimeout(() => this.text.set(text), ANSAGE_PAUSE_MS);
  }

  aufraeumen(): void {
    clearTimeout(this.frist);
  }
}
