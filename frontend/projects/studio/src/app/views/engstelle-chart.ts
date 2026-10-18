/**
 * Die Engstelle eines Lasttests (Paket 16, D4) — rein, ohne DOM.
 *
 * Gezeigt wird die Stufe mit der höchsten Parallelität: dort zeigt sich, was unter Last
 * knapp wird. Je Anfrageart die Teile mit Anteil > 0 in fester Folge (die Farbe eines Teils
 * bleibt so über alle Zeilen gleich) und der größte Teil beim Namen.
 */
import {
  type StageResult, ZEIT_KATEGORIEN, type ZeitKategorie,
} from '../core/loadtest-api.service';

type Art = StageResult['by_kind'][string];

export interface EngstellenTeil {
  readonly kategorie: ZeitKategorie;
  readonly anteil: number;
  readonly ms: number;
}

export interface EngstellenArt {
  readonly kind: string;
  readonly teile: readonly EngstellenTeil[];
  readonly groesste: ZeitKategorie;
}

export interface Engstelle {
  readonly concurrency: number;
  readonly arten: readonly EngstellenArt[];
}

export function engstelle(
  stages: readonly Pick<StageResult, 'concurrency' | 'by_kind'>[],
): Engstelle | null {
  const stufe = [...stages].sort((a, b) => b.concurrency - a.concurrency)[0];
  if (!stufe) return null;
  const arten = Object.entries(stufe.by_kind)
    .map(([kind, art]) => artTeile(kind, art))
    .filter((art): art is EngstellenArt => art !== null)
    .sort((a, b) => a.kind.localeCompare(b.kind));
  return arten.length > 0 ? { concurrency: stufe.concurrency, arten } : null;
}

function artTeile(kind: string, art: Art): EngstellenArt | null {
  const teile = ZEIT_KATEGORIEN
    .map((kategorie) => ({
      kategorie, anteil: art.anteile?.[kategorie] ?? 0, ms: art.zeiten_ms?.[kategorie] ?? 0,
    }))
    .filter((teil) => teil.anteil > 0);
  if (teile.length === 0) return null;
  const groesste = teile.reduce((a, b) => (b.anteil > a.anteil ? b : a)).kategorie;
  return { kind, teile, groesste };
}
