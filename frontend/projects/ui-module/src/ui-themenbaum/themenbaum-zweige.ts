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
 * **Nicht lesbar (N5):** Der Server kennzeichnet einen Knoten, dessen Unterthemen er gerade nicht
 * lesen konnte (`nicht_lesbar: "ausfall"`) oder mit dieser Anmeldung nicht lesen durfte
 * (`"gesperrt"`). Ohne das Kennzeichen sähe er aus wie ein Thema ohne Unterthemen. Bei einem Ausfall
 * lädt das Aufklappen neu — auch auf der ersten Ebene, deren Kinder sonst als bekannt gelten.
 * Abgelehnt bleibt abgelehnt: kein Auf/Zu, kein Abruf — bis ein neuer Baum kommt, auch nach einem
 * Wechsel der Anmeldung. Dasselbe gilt, wenn erst das Aufklappen die Ablehnung meldet
 * (`{ knoten: [], nicht_lesbar: "gesperrt" }`). Auf der tiefsten Ebene steht kein Hinweis: dort
 * zeigt der Baum ohnehin keine Unterthemen.
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
  /** N5: die Unterthemen ließen sich gerade nicht lesen (`ausfall`) bzw. das Repository gibt sie
   *  nicht heraus (`gesperrt`). */
  readonly nicht_lesbar?: 'ausfall' | 'gesperrt';
}

export interface ThemenbaumKnoten extends ThemenbaumBlatt {
  readonly kinder?: readonly ThemenbaumBlatt[];
}

/** Tiefste sichtbare Ebene; bis zu ihr wird nachgeladen. */
export const HOECHSTE_EBENE = 8;

/** Zustand eines Zweigs je Knoten-Kennung. `nochmal: false` nach 403 (hier nicht angeboten);
 *  `gedrosselt` nach 429 (zu viele Anfragen — eigener Text, neuer Versuch erlaubt); `gesperrt`,
 *  wenn das Aufklappen meldet, dass das Repository den Zweig mit dieser Anmeldung nicht herausgibt. */
export type ZweigZustand =
  | { readonly status: 'laedt' }
  | { readonly status: 'gesperrt' }
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
  readonly zustand: 'laedt' | 'fehler' | 'gedrosselt' | 'leer' | 'ungelesen' | 'gesperrt' | null;
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

function zustandVon(
  zweig: ZweigZustand | undefined, leer: boolean, knoten: ThemenbaumBlatt, tiefer: boolean,
): Eintrag['zustand'] {
  if (zweig?.status === 'laedt') return 'laedt';
  if (zweig?.status === 'fehler') return zweig.gedrosselt ? 'gedrosselt' : 'fehler';
  if (zweig?.status === 'gesperrt') return 'gesperrt';
  if (zweig?.status === 'fertig') return leer ? 'leer' : null;
  // Noch nichts nachgeladen: es gilt, was der Server am Knoten gemeldet hat (N5) — nur, wo der
  // Baum Unterthemen zeigen könnte („Aufklappen lädt neu“ wäre auf der tiefsten Ebene falsch).
  if (!tiefer) return null;
  if (knoten.nicht_lesbar === 'gesperrt') return 'gesperrt';
  return knoten.nicht_lesbar === 'ausfall' ? 'ungelesen' : null;
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
    // Kein Abruf: hier nicht angeboten (403 u. a.) oder nicht zugänglich (N5).
    const gesperrt = (zweig?.status === 'fehler' && !zweig.nochmal) || zweig?.status === 'gesperrt'
      || (!zweig && knoten.nicht_lesbar === 'gesperrt');
    const tiefer = ebene < HOECHSTE_EBENE;
    // N5: nach einem Ausfall lohnt ein neuer Versuch, auch wenn die Kinder sonst als bekannt gelten.
    const kannLaden = !geladen && !gesperrt && tiefer && (!bekannt || mehr || knoten.nicht_lesbar === 'ausfall');
    const aufklappbar = tiefer && (kinder.liste.length > 0 || kannLaden);
    return {
      ...lage,
      aufklappbar,
      ladbar: kannLaden && zweig?.status !== 'laedt',
      zustand: zustandVon(zweig, !kinder.liste.length, knoten, tiefer),
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

/** Alle sichtbaren Einträge in Lesereihenfolge — seit U2 aus dem gemeinsamen Baum-Kern. */
export { flach } from '../_baum/baum-tasten';

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
