// ERZEUGT von `npm run module:register` — nicht von Hand ändern. Nur fürs Studio importieren,
// nie im Widget (jeder import() hier würde dort ein zweites Bündel erzeugen).

export const NACHLADE_QUELLEN: Readonly<Record<string, () => Promise<unknown>>> = {
  ui_fortschritt: () => import('./ui-fortschritt/ui-fortschritt.element'),
  ui_strukturabgleich: () => import('./ui-strukturabgleich/ui-strukturabgleich.element'),
  ui_strukturentwurf: () => import('./ui-strukturentwurf/ui-strukturentwurf.element'),
  ui_upload: () => import('./ui-upload/ui-upload.element'),
};
