/**
 * Abstands-Messer für den senkrechten Rhythmus der UI-Module (2026-11-03).
 *
 * Gemessen wird der SICHTBARE Weißraum zwischen Textzeilen — nicht der Abstand der Zeilen-Boxen.
 * Eine Box trägt Polster, Mindesthöhe und halben Zeilenabstand mit sich; zwei Boxen mit gleichem
 * Box-Abstand können deshalb sehr verschieden weit auseinander WIRKEN (genau das war der Befund:
 * die Frage klebte an der ersten Möglichkeit, die Möglichkeiten standen weit auseinander).
 *
 * Kniff: pro Textknoten ein `Range` und dessen `getClientRects()` — das sind die Inline-Boxen der
 * Glyphen (Schrift-Oberkante bis -Unterkante), unabhängig von `line-height`, Polster und Höhe der
 * umgebenden Box. Reine Leerraum-Knoten zählen nicht; Symbole (SVG) auch nicht, sie sind kein Text.
 */
import { Locator } from '@playwright/test';

/** Oberste und unterste Glyphenkante aller Textzeilen in einem Element (px, Viewport). */
export interface Textkante {
  oben: number;
  unten: number;
}

export async function textkante(ort: Locator): Promise<Textkante> {
  return ort.evaluate((el) => {
    const gang = el.ownerDocument.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const kanten: DOMRect[] = [];
    for (let k = gang.nextNode(); k; k = gang.nextNode()) {
      if (!k.textContent?.trim()) continue;
      const bereich = el.ownerDocument.createRange();
      bereich.selectNodeContents(k);
      kanten.push(...Array.from(bereich.getClientRects()).filter((r) => r.width > 0 && r.height > 0));
    }
    if (!kanten.length) throw new Error(`kein sichtbarer Text in <${el.tagName.toLowerCase()} class="${el.className}">`);
    return { oben: Math.min(...kanten.map((r) => r.top)), unten: Math.max(...kanten.map((r) => r.bottom)) };
  });
}

/** Box-Kanten eines Elements (für Felder und Knöpfe — dort ist der Rand das Sichtbare). */
export async function boxkante(ort: Locator): Promise<Textkante> {
  return ort.evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { oben: r.top, unten: r.bottom };
  });
}

/** Weißraum von der Unterkante von `a` bis zur Oberkante von `b`, auf 0,1 px gerundet. */
export function luecke(a: Textkante, b: Textkante): number {
  return Math.round((b.oben - a.unten) * 10) / 10;
}

/** Toleranz für „etwa gleich“: drei Pixel, darunter sieht niemand einen Unterschied. */
export const TOLERANZ_PX = 3;
