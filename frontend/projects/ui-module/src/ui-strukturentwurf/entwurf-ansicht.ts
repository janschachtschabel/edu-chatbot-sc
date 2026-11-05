/**
 * Der sichtbare Baum des Strukturentwurfs (Paket U2-e) — ohne Angular. Anders als im Bestand gibt
 * es kein Nachladen: alle Kinder sind bekannt; aufklappbar ist, wer Unterpunkte hat. Ebene,
 * Position und Größe je Gruppe für `aria-level`/`aria-posinset`/`aria-setsize`. Der Zustand
 * (offen, aktiv) gilt je Knoten-Kennung, damit er Verschieben und Einrücken übersteht.
 */
import type { BaumEintrag } from '../_baum/baum-tasten';
import type { Baum, EntwurfKnoten } from './entwurf-regeln';

export interface EntwurfEintrag extends BaumEintrag {
  readonly knoten: EntwurfKnoten;
  readonly ebene: number;
  readonly posinset: number;
  readonly setsize: number;
  readonly kinder: readonly EntwurfEintrag[];
}

export function ansicht(
  baum: Baum, offen: ReadonlySet<string>, ebene = 1, eltern: string | null = null,
): EntwurfEintrag[] {
  return baum.map((knoten, i) => {
    const pfad = eltern === null ? `${i}` : `${eltern}-${i}`;
    const aufklappbar = (knoten.kinder?.length ?? 0) > 0;
    return {
      pfad, knoten, ebene, eltern, posinset: i + 1, setsize: baum.length, aufklappbar,
      kinder: aufklappbar && offen.has(knoten.id) ? ansicht(knoten.kinder ?? [], offen, ebene + 1, pfad) : [],
    };
  });
}

/** Alle Kennungen mit Unterpunkten — für „Alles aufklappen“. */
export function alleMitKindern(baum: Baum): string[] {
  return baum.flatMap((k) => (k.kinder?.length ? [k.id, ...alleMitKindern(k.kinder)] : []));
}

/** Die Vorfahren einer Kennung (zum Aufklappen, damit ein verschobener Punkt sichtbar bleibt). */
export function vorfahren(baum: Baum, id: string, pfad: readonly string[] = []): string[] | null {
  for (const k of baum) {
    if (k.id === id) return [...pfad];
    const tiefer = vorfahren(k.kinder ?? [], id, [...pfad, k.id]);
    if (tiefer) return tiefer;
  }
  return null;
}

/** Schlagworte aus einem Eingabefeld: durch Komma getrennt, ohne Leere und Doppelte, gedeckelt. */
export function schlagworte(text: string, hoechstens: number, zeichen: number): string[] {
  const aus: string[] = [];
  for (const teil of text.split(',')) {
    const wort = teil.trim().replace(/\s+/g, ' ').slice(0, zeichen);
    if (wort && !aus.some((a) => a.toLowerCase() === wort.toLowerCase())) aus.push(wort);
  }
  return aus.slice(0, hoechstens);
}
