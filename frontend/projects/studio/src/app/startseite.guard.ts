/**
 * Die Startseite des Arbeitsbereichs (Paket 14; Review PR #18).
 *
 * Ein Wächter auf der leeren Kind-Route statt einer Umleitung: Angular löst Umleitungen auf,
 * bevor es `canActivate` prüft — abgemeldet holte die Umleitung die Vorgabe des Servers (401),
 * fiel auf die Agent-Übersicht zurück, und erst danach schickte `authGuard` zur Anmeldung, mit
 * `from=/agent-uebersicht`. Kind-Wächter laufen nach dem des Elternteils und nur, wenn der
 * durchlässt.
 *
 * Ohne Wahl steht der Arbeitsbereich erst mit der Vorgabe des Servers fest — darauf wird gewartet.
 */
import { inject } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';

import { StudioAnsicht } from './core/studio-ansicht.service';
import { startView } from './studio-views';

export const startseiteGuard: CanActivateFn = () => {
  // Vor dem `await` holen: danach gibt es keinen Injektionskontext mehr.
  const router = inject(Router);
  return inject(StudioAnsicht).ermittle()
    .then((ansicht) => router.createUrlTree(['/', startView(ansicht)]));
};
