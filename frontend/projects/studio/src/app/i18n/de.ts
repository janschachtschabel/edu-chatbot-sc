/**
 * Deutscher Katalog des Studios (C1-d1) — Basis und Rückfall.
 *
 * Getrennt vom Widget-Katalog (`ui/src/i18n/de.ts`), und zwar vollständig: die
 * beiden Oberflächen teilen keinen einzigen sichtbaren Text, und ein
 * gemeinsamer Katalog hiesse, das Widget-Bundle um Studio-Texte zu vergrössern,
 * die dort nie erscheinen. Der `I18n`-Kern nimmt seinen Basis-Katalog deshalb
 * seit C1-d1 als Argument.
 *
 * **Seit C1-d3b eine Fassade.** Die Texte selbst stehen je Bereich in
 * `catalogue/` — beide Sprachen beieinander, damit ihre Schlüsselgleichheit
 * beim Schreiben sichtbar ist. Diese Datei setzt sie nur noch zusammen; alle
 * Importstellen von `STUDIO_DE` blieben davon unberührt.
 *
 * Die Reihenfolge der Teile ist bedeutungslos, weil kein Schlüssel doppelt
 * vorkommen darf — `catalogue/parts.spec.ts` hält das fest. Ohne diese Prüfung
 * wäre `Object.assign` ein stiller Textverlust: der zweite Teil überschriebe
 * den ersten in beiden Sprachen gleichermassen, und `en.spec.ts` bliebe grün.
 */
import type { Catalogue } from '@boerdi/ui';

import { STUDIO_PARTS } from './catalogue/parts';

export const STUDIO_DE: Catalogue = Object.assign(
  {},
  ...STUDIO_PARTS.map((teil) => teil.de),
) as Catalogue;
