/**
 * Das Modul-Register: Name → Manifest + Komponente. Erzeugt von `npm run module:register` in
 * `register.generated.ts`; hier nur Typ und Token, damit Tests ein eigenes Register einsetzen.
 */
import { InjectionToken, type Type } from '@angular/core';

import { MODUL_REGISTER } from '../register.generated';
import type { UiModulManifest } from './manifest';

/** Was das Widget zur Laufzeit vom Manifest braucht. Beschreibung, Schemas und Beispiele bleiben
 *  draußen: sie liest das Backend (`manifeste.json`), im Bündel kosteten sie nur Größe. */
export type RegisterManifest = Pick<UiModulManifest, 'name' | 'version' | 'art' | 'titel'
  | 'faehigkeiten' | 'darstellung'>;

export interface RegisterEintrag {
  readonly manifest: RegisterManifest;
  readonly komponente: Type<unknown>;
  /** Paket U3-0: nur bei nachgeladenen Modulen — der Name ihres Custom Elements
   *  (`boerdi-ui-<name>`); `komponente` ist dann der gemeinsame Platzhalter. */
  readonly element?: string;
}

export type ModulRegister = Readonly<Record<string, RegisterEintrag>>;

export const UI_MODUL_REGISTER = new InjectionToken<ModulRegister>('UI_MODUL_REGISTER', {
  providedIn: 'root',
  factory: () => MODUL_REGISTER,
});
