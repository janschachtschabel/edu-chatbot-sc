/**
 * Die beiden Symbole des Strukturentwurfs (Paket BU-2, BU-g): `viewBox` und Pfad wie
 * `ICONS.edit_note` und `ICONS.chevron_right` aus `@boerdi/ui/icons/icons` — die Spec prüft das.
 * Eigene Konstanten, weil ein Import von `ICONS` alle Symbole ins nachgeladene Bündel zöge.
 *
 * Als Daten und mit `createElementNS` gebaut, nie über `innerHTML` (Querschnitts-Review Q-3): auf
 * einer Gastseite mit Trusted Types (`require-trusted-types-for 'script'`) wirft eine
 * String-Zuweisung an `innerHTML` — der Lader unterstützt solche Seiten ausdrücklich.
 */
export interface Zeichen {
  readonly viewBox: string;
  readonly d: string;
}

export const SYMBOL: Zeichen = {
  viewBox: '0 -960 960 960',
  d: 'M200-200h57l391-391-57-57-391 391v57Zm0 80q-17 0-28.5-11.5T160-160v-104q0-16 6-30.5t18-25.5l560-560q11-11 25.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T912-705L353-146q-11 12-25.5 18.5T297-120H200Zm200-320h160v-80H400v80Zm0 160h160v-80H400v80Z',
};

export const PFEIL: Zeichen = {
  viewBox: '0 -960 960 960',
  d: 'M504-480 320-664l56-56 240 240-240 240-56-56 184-184Z',
};

const SVG = 'http://www.w3.org/2000/svg';

/** Das Symbol als `<svg>` (1em groß, `currentColor` — wie die Symbole des Widgets). */
export function svgSymbol(symbol: Zeichen, dok: Document = document): SVGSVGElement {
  const svg = dok.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', symbol.viewBox);
  svg.setAttribute('height', '1em');
  svg.setAttribute('width', '1em');
  svg.setAttribute('fill', 'currentColor');
  const pfad = dok.createElementNS(SVG, 'path');
  pfad.setAttribute('d', symbol.d);
  svg.append(pfad);
  return svg;
}
