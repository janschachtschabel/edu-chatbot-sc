/**
 * Das ganze Dokument des Formulars (Paket K2c-3) — vom Formular an Felder, die über ihren Teilbaum
 * hinaus lesen müssen, ohne es durch die rekursiven Felder zu reichen (wie `FORM_EPOCHE`). Die
 * Tabelle „Argumente“ eines Ablaufschritts liest damit die Teile der Schritte davor.
 */
import { InjectionToken, type Signal } from '@angular/core';

export const FORM_DOKUMENT = new InjectionToken<Signal<unknown>>('FORM_DOKUMENT');
