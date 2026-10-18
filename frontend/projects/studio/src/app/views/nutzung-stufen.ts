/**
 * Farbstufen der Nutzung (Studio-Rundgang 2026-10-18) — rein, ohne DOM.
 *
 * Die Zellen nennen ihre genaue Zahl; die Tönung ordnet sie höchstens vier Bereichen zu, deren
 * Grenzen aus den vorkommenden Zahlen kommen: ein Viertel des Höchstwerts, gerundet auf den
 * nächsten Wert 1, 2 oder 5 mal einer Zehnerpotenz. So stehen in der Legende runde Bereiche
 * („5–9“, „ab 15“) statt krummer, und der Verlauf reicht bis zur dunkelsten Stufe.
 */

export interface NutzungStufe {
  readonly von: number;
  /** Obere Grenze einschließlich; `null` für die offene letzte Stufe („ab …“). */
  readonly bis: number | null;
}

const ANZAHL = 4;

/** Die Zahl der Form 1, 2 oder 5 × 10ⁿ, die `x` im Verhältnis am nächsten liegt — mindestens 1.
 *  Abgerundet (4,75 → 2) fielen bei einem Höchstwert von 19 alle Zellen ab 6 in die dunkelste
 *  Stufe; zum nächsten gerundet (4,75 → 5) trägt der Verlauf bis oben. */
function rund(x: number): number {
  if (x < 1) return 1;
  const potenz = 10 ** Math.floor(Math.log10(x));
  const kandidaten = [1, 2, 5, 10].map((f) => f * potenz);
  return kandidaten.reduce((best, k) =>
    (Math.abs(Math.log(k / x)) < Math.abs(Math.log(best / x)) ? k : best));
}

export function nutzungStufen(werte: readonly number[]): readonly NutzungStufe[] {
  const max = Math.max(0, ...werte);
  if (max === 0) return [];
  const schritt = rund(max / ANZAHL);
  const untergrenzen = [...new Set(
    Array.from({ length: ANZAHL }, (_, i) => Math.max(1, i * schritt)),
  )].filter((g) => g <= max);
  return untergrenzen.map((von, i) => ({
    von,
    bis: i + 1 < untergrenzen.length ? untergrenzen[i + 1] - 1 : null,
  }));
}

/** 0 für keine Züge, sonst die Stufe (1-basiert) des Bereichs, in den `n` fällt. */
export function stufeVon(n: number, stufen: readonly NutzungStufe[]): number {
  if (n <= 0) return 0;
  let stufe = 0;
  stufen.forEach((s, i) => {
    if (n >= s.von) stufe = i + 1;
  });
  return stufe;
}
