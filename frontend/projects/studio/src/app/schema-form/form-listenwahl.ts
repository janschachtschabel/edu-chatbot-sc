/**
 * AS-2b (Plan 2026-11-09): „diesen Eintrag zeigen“ — vom Formular an jede Objektliste, ohne es durch
 * die rekursiven Felder zu reichen (wie `FORM_DOKUMENT`). Das Ablaufbild und „Zum Schritt“ in der
 * Schrittfolge wählen damit einen Schritt in der Liste der Schritte; die Liste klappt ihren Abschnitt
 * auf, wählt den Eintrag und setzt den Fokus darauf.
 *
 * Ein Wunsch gilt einmal: die Liste, deren Pfad passt, nimmt ihn (`erledigt`) — eine später erzeugte
 * Liste springt nicht noch einmal. `zaehler` macht denselben Wunsch zweimal hintereinander zu zwei.
 */
import { InjectionToken, type Signal } from '@angular/core';

import type { ValuePath } from './form-value';

export interface ListenWunsch {
  /** `pathKey` der Liste. */
  readonly pfad: string;
  readonly id: number | string;
  readonly zaehler: number;
}

export interface FormListenwahl {
  readonly wunsch: Signal<ListenWunsch | null>;
  waehlen(pfad: ValuePath, id: number | string): void;
  erledigt(zaehler: number): void;
}

export const FORM_LISTENWAHL = new InjectionToken<FormListenwahl>('FORM_LISTENWAHL');
