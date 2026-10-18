/**
 * Zähler „das Dokument wurde von außen zurückgesetzt“ (Verwerfen) — vom Formular an jedes
 * JSON-Feld, ohne ihn durch die rekursiven Felder zu reichen (Review Paket 15, #4).
 *
 * Ein JSON-Feld räumt seinen Entwurf, wenn sich sein Wert ändert. Nach „Verwerfen“ bleibt der
 * Wert aber oft derselbe (die Vorgabe, ein Einzelwert) — dann zählt nur dieser Zähler.
 */
import { InjectionToken, type Signal } from '@angular/core';

export const FORM_EPOCHE = new InjectionToken<Signal<number>>('FORM_EPOCHE');
