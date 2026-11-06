/**
 * Die Methoden des Block-Hosts als einfaches, eingefrorenes Objekt für ein Custom Element (U3-0).
 *
 * Der Block-Host (`BlockModulHost` der Shell) lässt schon nur die Fähigkeiten aus dem Manifest zu;
 * die Brücke prüft nichts zusätzlich, sie reicht nur weiter. Eingefroren, damit ein Modul den Host
 * anderer Module nicht verändern kann; ohne `markdown` und `treffer`, weil deren Rückgabewerte an
 * Angular hängen.
 *
 * Keine Sicherheitsgrenze zwischen Modulen (Querschnitts-Review FE-9): `element.host` ist eine
 * öffentliche Eigenschaft, und jedes Bündel im selben Fenster könnte den Host eines anderen Blocks
 * aufrufen. Vertretbar, weil nur eigene, per SRI geprüfte Bündel laden.
 */
import type { ModulHost } from '../_vertrag/modul-host';
import type { ElementHost } from './element-vertrag';

export const ELEMENT_HOST_METHODEN = [
  'herunterladen', 'drucken', 'link', 'aktion', 'beschaeftigt', 'antworten', 'vormerken', 'zweig',
  'hochladen', 'ablegen', 'auftrag',
] as const satisfies readonly (keyof ElementHost)[];

export function hostBruecke(host: ModulHost): ElementHost {
  const bruecke: Record<string, unknown> = {};
  for (const name of ELEMENT_HOST_METHODEN) {
    const methode = host[name] as (...args: unknown[]) => unknown;
    bruecke[name] = (...args: unknown[]) => methode.apply(host, args);
  }
  return Object.freeze(bruecke) as unknown as ElementHost;
}
