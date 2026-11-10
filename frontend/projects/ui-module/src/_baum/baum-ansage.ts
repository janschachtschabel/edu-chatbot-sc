/**
 * Gemeinsamer Baum-Kern (Paket U2): die höfliche Statuszeile (`aria-live="polite"`) als Signal für
 * Angular-Komponenten (`ui-themenbaum`). Die Regel (gleicher Text → leeren, Pause, neu setzen)
 * steht seit Paket BU-2 rahmenlos in `ansage-kern.ts`; hier nur die Hülle mit Signal.
 * Die Komponente ruft {@link BaumAnsage.aufraeumen} beim Zerstören.
 */
import { signal } from '@angular/core';

import { AnsageKern } from './ansage-kern';

export { ANSAGE_PAUSE_MS } from './ansage-kern';

export class BaumAnsage {
  /** Der Text der Statuszeile. */
  readonly text = signal('');
  private readonly kern = new AnsageKern((t) => this.text.set(t));

  sagen(text: string): void {
    this.kern.sagen(text);
  }

  aufraeumen(): void {
    this.kern.aufraeumen();
  }
}
