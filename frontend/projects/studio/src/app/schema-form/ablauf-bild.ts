/**
 * AS-2b (Plan 2026-11-09): die Geometrie des Ablaufbilds aus der Schrittfolge (`ablauf-folge.ts`).
 *
 * Je Schritt ein Kasten untereinander, in der Reihenfolge der Liste. Der reguläre Weg zum nächsten
 * Schritt ist eine gerade Linie; Sprünge, Regeln einer Verzweigung und „bei Fehler“ sind Bögen rechts
 * daneben, je Bogen auf einer eigenen Spur, damit sie sich nicht überdecken. Ein Pfeil auf ein Ziel,
 * das es nicht gibt, hat keinen Bogen — sein Kasten ist markiert (die Schrittfolge nennt das Ziel).
 * Rein, ohne Angular; die Komponente zeichnet nur.
 */
import type { FolgeZeile } from './ablauf-folge';

export const KASTEN_B = 190;
export const KASTEN_H = 34;
const ABSTAND = 22;
export const RAND = 8;
export const SPUR = 14;
const BESCHRIFTUNG = 120;

export interface Kasten {
  readonly nr: number;
  readonly id: string;
  readonly typ: string;
  readonly x: number;
  readonly y: number;
  readonly breite: number;
  readonly hoehe: number;
  /** Ein Pfeil des Schritts zeigt auf ein Ziel, das es nicht gibt. */
  readonly unbekannt: boolean;
}

export interface Linie {
  readonly von: number;
  readonly nach: number;
  readonly art: 'weiter' | 'regel' | 'fehler' | 'wahl' | 'freitext';
  /** Der reguläre Weg zum nächsten Schritt — eine gerade Linie statt eines Bogens. */
  readonly gerade: boolean;
  /** Die Spur eines Bogens (0…); bei geraden Linien 0. */
  readonly spur: number;
  /** Nur `regel`: welche Bedingung (Review AS-2, Befund 11 — kein Zauberwert `sonst`). */
  readonly bedingung?: 'sonst' | 'teil' | 'gewaehlt' | 'wert' | 'seite';
  /** Der Wert der Bedingung (Wahl oder Teil); sonst leer. */
  readonly beschriftung: string;
}

export interface Bild {
  readonly kaesten: readonly Kasten[];
  readonly linien: readonly Linie[];
  readonly breite: number;
  readonly hoehe: number;
}

export function bildAus(folge: readonly FolgeZeile[]): Bild {
  const index = new Map<string, number>();
  // wie der Treiber (`{s.id: i …}`): bei doppelten Kennungen gilt die letzte — die Prüfung meldet sie
  for (const z of folge) if (z.id) index.set(z.id, z.nr);
  const kaesten: Kasten[] = folge.map((z) => ({
    nr: z.nr, id: z.id, typ: z.typ, x: RAND, y: RAND + z.nr * (KASTEN_H + ABSTAND),
    breite: KASTEN_B, hoehe: KASTEN_H,
    unbekannt: z.pfeile.some((p) => p.ziel !== '' && !p.bekannt),
  }));
  const linien: Linie[] = [];
  let spuren = 0;
  for (const z of folge) {
    for (const p of z.pfeile) {
      const nach = index.get(p.ziel);
      if (nach === undefined || !p.bekannt) continue;
      const gerade = p.art === 'weiter' && nach === z.nr + 1;
      const bedingung = p.art !== 'regel' ? undefined : p.sonst ? 'sonst' : p.wennTeil ? 'teil'
        : p.wennWert ? 'wert' : p.wennSeite ? 'seite' : 'gewaehlt';
      const beschriftung = bedingung === 'teil' ? (p.wennTeil ?? '') : bedingung === 'wert' ? (p.wennWert?.quelle ?? '')
        : bedingung === 'seite' ? (p.wennSeite ?? '')
        : bedingung === 'gewaehlt' ? (p.wennGewaehlt ?? '') : p.art === 'wahl' ? (p.label ?? '') : '';
      linien.push({ von: z.nr, nach, art: p.art, gerade, spur: gerade ? 0 : spuren++,
                    ...(bedingung ? { bedingung } : {}), beschriftung });
    }
  }
  return {
    kaesten, linien,
    breite: RAND + KASTEN_B + (spuren + 1) * SPUR + BESCHRIFTUNG,
    hoehe: RAND * 2 + Math.max(folge.length, 1) * (KASTEN_H + ABSTAND),
  };
}
