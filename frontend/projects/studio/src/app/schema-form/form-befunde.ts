/**
 * Befunde einer Prüfung ohne Speichern (Paket K2c-4) — vom Feld, das prüft, an das Formular, ohne
 * sie durch die rekursiven Felder zu reichen (wie `FORM_EPOCHE`).
 *
 * Sie stehen am Feld wie eine Meldung des Servers nach dem Speichern (`problems`) und markieren
 * den Eintrag in seiner Liste, **sperren aber das Speichern nicht**: Sie sind ein Stand von einem
 * Zeitpunkt, keine Eingabe, die sich nicht lesen ließe. Das Feld, das sie gesetzt hat, nimmt sie
 * zurück, sobald sich sein Wert ändert; „Verwerfen“ räumt alle.
 */
import { InjectionToken } from '@angular/core';

import type { ValuePath } from './form-value';

/** Ein Befund an einer Stelle im Dokument. Gibt es dort kein Feld (ein Zweig einer Union, eine Stelle
 *  in rohem JSON), steht er am nächsten Feld darüber (Review K2c-4, Befund 1). */
export interface FormBefund {
  readonly pfad: ValuePath;
  readonly text: string;
}

export interface FormBefunde {
  /** Die Befunde einer Quelle setzen; ersetzt ihre vorigen. */
  setzen(quelle: string, befunde: readonly FormBefund[]): void;
  entfernen(quelle: string): void;
}

export const FORM_BEFUNDE = new InjectionToken<FormBefunde>('FORM_BEFUNDE');
