/**
 * Plakette je Feld (Rundgang 3) — vom Formular an jedes Feld, ohne sie durch die rekursiven
 * Felder zu reichen (wie `FORM_EPOCHE`). Die Funktion liest Signale (Zuordnung, Arbeitsbereich);
 * ein Feld, das sie in einem `computed` ruft, folgt ihnen.
 */
import { InjectionToken } from '@angular/core';

import type { FeldPlakette } from '../core/feld-wirkung';

export type FeldWirkung = (pfad: string) => FeldPlakette | null;

export const FORM_WIRKUNG = new InjectionToken<FeldWirkung>('FORM_WIRKUNG');
