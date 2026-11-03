/**
 * Regeln des Themenbaums für Kinder und Nachladen (Paket U1-h, Plan §18 H-11) — ohne Angular,
 * damit die Komponente nur Darstellung und Bedienung trägt.
 *
 * **Bekannt oder unbekannt.** Der Server holt je Abruf zwei Ebenen (`depth: 2`): Ein Knoten, der
 * als Knoten einer Antwort kam (erste Ebene des Blocks oder eines nachgeladenen Zweigs), bringt
 * seine Kinder mit — fehlen sie, hat er keine. Ein Kind dieser Knoten (zweite Ebene) kam ohne
 * eigene Kinder: ob es Unterthemen hat, weiß erst ein neuer Abruf. Gekürzte Zweige (`mehr`)
 * zeigen die mitgelieferten Kinder und laden beim Aufklappen die volle Liste.
 *
 * **Grenze:** bis {@link HOECHSTE_EBENE}; tiefer lädt und zeigt der Baum nichts (Einrückung bei
 * 320 px), „In WLO öffnen“ zeigt dann alles. Auch mitgelieferte Kinder eines Knotens auf dieser
 * Ebene bleiben verborgen (Review U1-h, Befund 6).
 *
 * **Kreise:** Kommt in einem nachgeladenen Zweig ein Vorfahr wieder vor (Sammlungen können sich
 * im Repositorium gegenseitig enthalten), steht er dort als Blatt — sonst wüchse der Baum ohne
 * Ende, weil der Zustand je Kennung gilt (Review U1-h, Befund 4).
 */

/** Ein Knoten laut manifest.json (`$defs.blatt`); erste Ebene mit `kinder` (`$defs.knoten`). */
export interface ThemenbaumBlatt {
  readonly id: string;
  readonly titel: string;
  readonly url?: string;
  readonly anzahl?: number;
  readonly mehr?: boolean;
}

export interface ThemenbaumKnoten extends ThemenbaumBlatt {
  readonly kinder?: readonly ThemenbaumBlatt[];
}

/** Tiefste sichtbare Ebene; bis zu ihr wird nachgeladen. */
export const HOECHSTE_EBENE = 8;

/** Zustand eines Zweigs je Knoten-Kennung. `nochmal: false` nach 403 (hier nicht angeboten);
 *  `gedrosselt` nach 429 (zu viele Anfragen — eigener Text, neuer Versuch erlaubt). */
export type ZweigZustand =
  | { readonly status: 'laedt' }
  | { readonly status: 'fehler'; readonly nochmal: boolean; readonly gedrosselt?: boolean }
  | { readonly status: 'fertig'; readonly knoten: readonly ThemenbaumKnoten[]; readonly mehr: boolean };

/** Ein sichtbarer Eintrag. `pfad` = Positionen ab der Wurzel (`"0"`, `"0-1"`, `"0-1-2"` …). */
export interface Eintrag {
  readonly pfad: string;
  readonly knoten: ThemenbaumBlatt;
  readonly ebene: number;
  readonly eltern: string | null;
  readonly posinset: number;
  readonly setsize: number;
  /** Hat Kinder oder kann sie laden — dann trägt der Eintrag `aria-expanded`. */
  readonly aufklappbar: boolean;
  /** Aufklappen lädt (noch nicht geladen, lädt gerade nicht, nicht gesperrt, nicht zu tief). */
  readonly ladbar: boolean;
  readonly zustand: 'laedt' | 'fehler' | 'gedrosselt' | 'leer' | null;
  readonly nochmal: boolean;
  /** „weitere“: der Zweig ist gekürzt. */
  readonly mehr: boolean;
  /** Nur bei offenen Einträgen gefüllt. */
  readonly kinder: readonly Eintrag[];
}

/** Die Kinder eines Knotens: nachgeladen, mitgeliefert (nur bei bekannten) oder keine; dazu,
 *  ob deren eigene Kinder bekannt sind. */
export function kinderVon(
  knoten: ThemenbaumKnoten, bekannt: boolean, zweig: ZweigZustand | undefined,
): { readonly liste: readonly ThemenbaumKnoten[]; readonly bekannt: boolean } {
  if (zweig?.status === 'fertig') return { liste: zweig.knoten, bekannt: true };
  return { liste: bekannt ? knoten.kinder ?? [] : [], bekannt: false };
}

/** Wo eine Liste im Baum steht: Ebene, Pfad des Elternknotens, ob die Kinder ihrer Knoten
 *  bekannt sind, und die Kennungen der Vorfahren (Kreise). */
interface Ort {
  readonly ebene: number;
  readonly eltern: string | null;
  readonly bekannt: boolean;
  readonly vorfahren: ReadonlySet<string>;
}

const WURZEL: Ort = { ebene: 1, eltern: null, bekannt: true, vorfahren: new Set() };

function zustandVon(zweig: ZweigZustand | undefined, leer: boolean): Eintrag['zustand'] {
  if (zweig?.status === 'laedt') return 'laedt';
  if (zweig?.status === 'fehler') return zweig.gedrosselt ? 'gedrosselt' : 'fehler';
  return zweig?.status === 'fertig' && leer ? 'leer' : null;
}

/** Der sichtbare Baum ab einer Liste. */
export function ebenen(
  liste: readonly ThemenbaumKnoten[], offen: ReadonlySet<string>, zweige: ReadonlyMap<string, ZweigZustand>,
  ort: Ort = WURZEL,
): Eintrag[] {
  const { ebene, eltern, bekannt, vorfahren } = ort;
  return liste.map((knoten, i) => {
    const pfad = eltern === null ? `${i}` : `${eltern}-${i}`;
    const lage = { pfad, knoten, ebene, eltern, posinset: i + 1, setsize: liste.length };
    if (vorfahren.has(knoten.id)) {
      // Ein Vorfahr im eigenen Zweig: ein Blatt, sonst klappte er sich selbst endlos auf.
      return { ...lage, aufklappbar: false, ladbar: false, zustand: null, nochmal: false, mehr: false, kinder: [] };
    }
    const zweig = zweige.get(knoten.id);
    const geladen = zweig?.status === 'fertig' ? zweig : null;
    const kinder = kinderVon(knoten, bekannt, zweig);
    const mehr = geladen ? geladen.mehr : knoten.mehr === true;
    const gesperrt = zweig?.status === 'fehler' && !zweig.nochmal;
    const tiefer = ebene < HOECHSTE_EBENE;
    const kannLaden = !geladen && !gesperrt && tiefer && (!bekannt || mehr);
    const aufklappbar = tiefer && (kinder.liste.length > 0 || kannLaden);
    return {
      ...lage,
      aufklappbar,
      ladbar: kannLaden && zweig?.status !== 'laedt',
      zustand: zustandVon(zweig, !kinder.liste.length),
      nochmal: zweig?.status === 'fehler' && zweig.nochmal,
      mehr,
      kinder: aufklappbar && offen.has(knoten.id)
        ? ebenen(kinder.liste, offen, zweige, {
          ebene: ebene + 1, eltern: pfad, bekannt: kinder.bekannt, vorfahren: new Set(vorfahren).add(knoten.id),
        })
        : [],
    };
  });
}

/** Alle sichtbaren Einträge in Lesereihenfolge. */
export function flach(baum: readonly Eintrag[]): Eintrag[] {
  return baum.flatMap((e) => [e, ...flach(e.kinder)]);
}

function istBlatt(wert: unknown): wert is ThemenbaumBlatt {
  const k = wert as Partial<ThemenbaumBlatt> | null;
  return !!k && typeof k === 'object' && typeof k.id === 'string' && typeof k.titel === 'string';
}

/** Die Knoten eines nachgeladenen Zweigs (Form der Block-Daten) — `null`, wenn die Antwort keine
 *  Liste trägt. Unbrauchbare Einträge fallen weg, Kinder ebenso. */
export function zweigKnoten(roh: Record<string, unknown>): ThemenbaumKnoten[] | null {
  const liste = roh['knoten'];
  if (!Array.isArray(liste)) return null;
  return liste.filter(istBlatt).map((k: ThemenbaumKnoten) => {
    const { kinder, ...rest } = k;
    return Array.isArray(kinder) ? { ...rest, kinder: kinder.filter(istBlatt) } : rest;
  });
}
