/**
 * Englischer Katalog des Studios (C1-d1).
 *
 * Schlüsselgleich mit `de.ts` — `en.spec.ts` hält das fest, samt Platzhaltern
 * und der Zusage, dass kein Text unübersetzt aus dem Deutschen stehenblieb.
 * Der Rückfall je Schlüssel ist die Sicherung gegen Lücken, kein Freibrief.
 *
 * Wie `de.ts` seit C1-d3b eine Fassade über `catalogue/` — dieselbe Liste,
 * dieselbe Reihenfolge, nur die andere Sprache je Teil.
 */
import type { Catalogue } from '@boerdi/ui';

import { STUDIO_PARTS } from './catalogue/parts';

export const STUDIO_EN: Catalogue = Object.assign(
  {},
  ...STUDIO_PARTS.map((teil) => teil.en),
) as Catalogue;
