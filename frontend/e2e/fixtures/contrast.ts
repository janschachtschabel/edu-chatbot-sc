/**
 * Kontrast-Messer für den E2E-Lauf (U4d).
 *
 * Warum im Browser und nicht als Unit-Test: der Kontrast eines Textes steht
 * nirgends im Quelltext. Er entsteht erst aus `light-dark()`, `color-mix()`,
 * geerbten Farben, halbdurchsichtigen Flächen und der Frage, welcher Vorfahr
 * überhaupt eine deckende Fläche trägt. jsdom rechnet davon nichts aus.
 *
 * Zwei Kniffe, ohne die die Messung falsche Zahlen liefert:
 *
 * 1. **Canvas statt Textparser.** `getComputedStyle` gibt für `color-mix()`
 *    und `light-dark()` `oklab(…)` zurück. Ein Regex-Parser liest das nicht.
 *    Die Farbe auf ein 1×1-Canvas zu malen und den Pixel zurückzulesen liefert
 *    genau den Wert, den der Nutzer sieht — inklusive jeder Farbraum-Umrechnung
 *    des Browsers.
 * 2. **Fläche über Vorfahren suchen, durch Shadow-Grenzen hindurch.** Die
 *    meisten Bauteile setzen keine eigene Fläche. `parentElement` ist an der
 *    Shadow-Wurzel `null`; der Weg nach oben geht dann über `.host`.
 *
 * Gemessen wird **nur eigener Text** (direkte Textknoten). Sonst zählte jede
 * Zeile so oft, wie sie Vorfahren hat, und die Fundliste wäre unlesbar.
 *
 * Grenze, bewusst: geprüft wird SC 1.4.3 (Textkontrast). SC 1.4.11
 * (Bedienelement-Ränder ≥ 3:1) misst dieses Werkzeug nicht — Ränder haben
 * keinen Textknoten. Die Ränder der Kopfzeile sind in U4b von Hand belegt.
 */
import { Page } from '@playwright/test';

export interface Kontrastbefund {
  /** Tag + Klassen, so wie sie im DOM stehen — zum Wiederfinden. */
  sel: string;
  /** Die ersten Zeichen des eigenen Textes. */
  text: string;
  /** Gemessenes Verhältnis. */
  r: number;
  /** Geforderter Wert: 3 für großen Text, sonst 4,5 (SC 1.4.3). */
  soll: number;
  fg: string;
  bg: string;
  px: number;
  /** Gesetzt, wenn die Fläche nicht messbar war (z. B. Verlauf statt Farbe). */
  unmessbar?: string;
}

/**
 * Alle sichtbaren Texte im Shadow-DOM des Widgets messen.
 *
 * Läuft komplett in der Seite; der Rumpf darf deshalb nichts aus dem
 * Node-Modul schließen.
 */
export async function textkontraste(page: Page): Promise<Kontrastbefund[]> {
  return page.evaluate(() => {
    const cv = document.createElement('canvas');
    cv.width = cv.height = 1;
    const ctx = cv.getContext('2d', { willReadFrequently: true })!;

    /** CSS-Farbe → [r, g, b, a] über einen echten Pixel. */
    function farbe(wert: string): [number, number, number, number] {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = '#000';
      ctx.fillStyle = wert;
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return [d[0], d[1], d[2], d[3] / 255];
    }

    /** Relative Leuchtdichte nach WCAG 2.x. */
    function leuchte(c: number[]): number {
      const f = (k: number) => {
        const v = k / 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
      };
      return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
    }

    function verhaeltnis(vorne: number[], hinten: number[]): number {
      const a = leuchte(vorne);
      const b = leuchte(hinten);
      return +(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)).toFixed(2));
    }

    /** Halbdurchsichtige Farbe über eine deckende legen. */
    function ueber(vorne: [number, number, number, number], hinten: number[]): number[] {
      const a = vorne[3];
      return [0, 1, 2].map((i) => Math.round(vorne[i] * a + hinten[i] * (1 - a)));
    }

    /** Nach oben, auch über die Shadow-Grenze. */
    function darueber(el: Element): Element | null {
      if (el.parentElement) return el.parentElement;
      const wurzel = el.getRootNode();
      return wurzel instanceof ShadowRoot ? wurzel.host : null;
    }

    /** Erste deckende Fläche über `el`, halbdurchsichtige unterwegs gemischt. */
    function flaeche(el: Element): { rgb: number[]; unmessbar?: string } {
      let cur: Element | null = el;
      while (cur) {
        const cs = getComputedStyle(cur);
        if (cs.backgroundImage !== 'none') {
          // Ein Verlauf oder Bild hat keine EINE Farbe. Lieber ehrlich melden
          // als eine Zahl erfinden, die zufällig passt.
          return { rgb: [255, 255, 255], unmessbar: `background-image auf ${cur.tagName.toLowerCase()}` };
        }
        const c = farbe(cs.backgroundColor);
        if (c[3] >= 0.999) return { rgb: [c[0], c[1], c[2]] };
        if (c[3] > 0) {
          const unten = darueber(cur);
          const basis = unten ? flaeche(unten) : { rgb: [255, 255, 255] };
          return { rgb: ueber(c, basis.rgb), unmessbar: basis.unmessbar };
        }
        cur = darueber(cur);
      }
      return { rgb: [255, 255, 255] };
    }

    function* alle(wurzel: ParentNode): Generator<Element> {
      for (const el of Array.from(wurzel.querySelectorAll('*'))) {
        yield el;
        if (el.shadowRoot) yield* alle(el.shadowRoot);
      }
    }

    const host = document.querySelector('boerdi-chat')!;
    const befunde: Kontrastbefund[] = [];

    for (const el of alle(host.shadowRoot!)) {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) continue;

      const eigen = Array.from(el.childNodes)
        .filter((n) => n.nodeType === Node.TEXT_NODE && n.textContent!.trim())
        .map((n) => n.textContent!.trim())
        .join(' ');
      if (!eigen) continue;

      const bg = flaeche(el);
      const roh = farbe(cs.color);
      const fg = roh[3] < 0.999 ? ueber(roh, bg.rgb) : [roh[0], roh[1], roh[2]];

      const px = parseFloat(cs.fontSize);
      const fett = +cs.fontWeight >= 700;
      const klassen = typeof el.className === 'string' && el.className.trim()
        ? '.' + el.className.trim().split(/\s+/).join('.')
        : '';

      befunde.push({
        sel: el.tagName.toLowerCase() + klassen,
        text: eigen.slice(0, 40),
        r: verhaeltnis(fg, bg.rgb),
        soll: px >= 24 || (fett && px >= 18.66) ? 3 : 4.5,
        fg: `rgb(${fg.join(',')})`,
        bg: `rgb(${bg.rgb.join(',')})`,
        px,
        ...(bg.unmessbar ? { unmessbar: bg.unmessbar } : {}),
      });
    }
    return befunde;
  });
}

/** Nur die Verstöße, schwächster zuerst, je Selektor der schlechteste Fall. */
export function verstoesse(befunde: Kontrastbefund[]): Kontrastbefund[] {
  const je = new Map<string, Kontrastbefund>();
  for (const b of befunde) {
    if (b.r >= b.soll) continue;
    const alt = je.get(b.sel);
    if (!alt || alt.r > b.r) je.set(b.sel, b);
  }
  return [...je.values()].sort((a, b) => a.r - b.r);
}

/** Fundliste als lesbare Zeilen für die Fehlermeldung. */
export function bericht(funde: Kontrastbefund[]): string {
  return funde
    .map((f) => `  ${f.r}:1 (soll ${f.soll}:1)  ${f.sel}  ${f.fg} auf ${f.bg}  „${f.text}"`)
    .join('\n');
}
