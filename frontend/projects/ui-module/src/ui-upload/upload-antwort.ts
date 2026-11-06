/**
 * Was `ui_upload` als Antwort schickt (Paket U3-1a, Plan §16.5): der Ordnerbaum mit Zahlen, die Zahlen
 * je Rolle, Warnungen und — falls markiert — das Strukturdokument. **Keine Dateinamen**: sie bleiben im
 * Browser, kein Schritt in U3-1 braucht sie. Seit U3-2c kann ein markiertes Strukturdokument gelesen
 * werden (`upload-dokument.ts`); dann trägt die Antwort dessen Befund (`dokument`). Ordnernamen sind eine Zeile und höchstens 120 Zeichen; der
 * Baum hat höchstens `MAX_KNOTEN` Ordner (darüber Warnung `zu_viele_ordner`).
 */
import type { Erfassung, OrdnerKnoten, Warnung } from './upload-erfassen';

export const MAX_KNOTEN = 500;
const MAX_NAME = 120;

export type AntwortAktion = 'erfasst' | 'ordner_als_entwurf' | 'dokument' | 'uebertragen';
export type AntwortWarnung = Warnung | 'zu_viele_ordner';

export interface AntwortOrdner {
  readonly name: string;
  /** Inhalte und Strukturdokument direkt in diesem Ordner (ohne ignorierte). */
  readonly dateien: number;
  /** dasselbe samt aller Unterordner */
  readonly alle_dateien: number;
  readonly kinder: readonly AntwortOrdner[];
}

export interface UploadAntwort {
  readonly aktion: AntwortAktion;
  readonly struktur: AntwortOrdner;
  readonly zahlen: {
    readonly ordner: number; readonly dateien: number; readonly inhalte: number;
    readonly ignoriert: number; readonly strukturdokumente: number; readonly bytes: number;
  };
  readonly strukturdokument: { readonly name: string; readonly groesse: number; readonly endung: string } | null;
  readonly warnungen: readonly AntwortWarnung[];
  /** U3-2c, nur mit `aktion: "dokument"`: der Befund des gelesenen Dokuments (kein Text). */
  readonly dokument?: {
    readonly upload_id: string; readonly name: string; readonly format: string; readonly ziel: string;
    readonly befund: {
      readonly seiten: number | null; readonly woerter: number; readonly abschnitte: number;
      readonly gliederung_art: string; readonly warnungen: readonly string[];
    };
    readonly vorschau: readonly string[];
  };
  /** U3-3b, nur mit `aktion: "uebertragen"`: nur Zahlen der Ablage im persönlichen Bereich. */
  readonly ablage?: {
    readonly layout: 'ordner' | 'flach'; readonly gesamt: number; readonly abgelegt: number;
    readonly unklar: number; readonly fehler: number; readonly abgebrochen: number;
    readonly ordner_verweigert: boolean; readonly vorgang_abgelegt: boolean;
  };
}

export function einZeiler(name: string): string {
  // Nach Codepunkten kürzen: ein Emoji an Stelle 120 bliebe sonst ein halbes Zeichen.
  return Array.from(name.replace(/\s+/g, ' ').trim()).slice(0, MAX_NAME).join('');
}

export function antwortDaten<T>(e: Erfassung<T>, aktion: AntwortAktion): UploadAntwort {
  const zaehlt = (i: number): boolean => e.dateien[i].rolle !== 'ignorieren';
  let knoten = 0;
  let gekappt = false;
  let ordner = 0;

  function baue(k: OrdnerKnoten): AntwortOrdner {
    knoten++;
    if (k.name) ordner++;
    const kinder: AntwortOrdner[] = [];
    let alle = k.dateien.filter(zaehlt).length;
    for (const kind of k.ordner) {
      const unten = summe(kind);
      alle += unten;
      if (knoten < MAX_KNOTEN) kinder.push(baue(kind));
      else gekappt = true;
    }
    return { name: einZeiler(k.name), dateien: k.dateien.filter(zaehlt).length, alle_dateien: alle, kinder };
  }
  function summe(k: OrdnerKnoten): number {
    return k.dateien.filter(zaehlt).length + k.ordner.reduce((s, o) => s + summe(o), 0);
  }

  const struktur = baue(e.wurzel);
  const zaehlen = (rolle: string): number => e.dateien.filter((d) => d.rolle === rolle).length;
  const sd = e.dateien.find((d) => d.rolle === 'struktur');
  const warnungen: AntwortWarnung[] = [...e.warnungen];
  if (gekappt) warnungen.push('zu_viele_ordner');
  return {
    aktion,
    struktur,
    zahlen: {
      ordner, dateien: e.dateien.length, inhalte: zaehlen('inhalt'), ignoriert: zaehlen('ignorieren'),
      strukturdokumente: zaehlen('struktur'),
      bytes: e.dateien.reduce((s, d) => s + (d.rolle === 'ignorieren' ? 0 : d.groesse), 0),
    },
    strukturdokument: sd
      ? { name: einZeiler(sd.name), groesse: sd.groesse, endung: (sd.name.split('.').pop() ?? '').toLowerCase().slice(0, 8) }
      : null,
    warnungen,
  };
}
