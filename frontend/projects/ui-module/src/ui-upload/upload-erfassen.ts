/**
 * Ordner und Dateien im Browser erfassen (Paket U3-1a) — reine Regeln ohne DOM.
 *
 * Nichts davon verlässt das Gerät: aus Pfaden, Größen und Typen entsteht der Ordnerbaum, den das
 * Modul zeigt. Jede Datei bekommt eine Rolle (`inhalt`, `struktur`, `ignorieren`); ignoriert sind
 * Systemdateien, leere und zu große Dateien. Über der Höchstzahl bleiben die ersten nach Pfad, zu tiefe
 * Ordner werden in der tiefsten erlaubten Ebene zusammengefasst, Pfade mit `..`, `.` oder Steuerzeichen
 * verworfen. Was dabei wegfällt, steht als Warnung im Ergebnis.
 */

export type Rolle = 'inhalt' | 'struktur' | 'ignorieren';
export type Warnung = 'zu_viele' | 'zu_tief' | 'zu_gross' | 'leer' | 'ungueltiger_pfad';
/** Warum eine Datei ignoriert bleibt: Systemdateien ohne Warnung, leere und zu große mit. */
export type Grund = 'system' | 'leer' | 'zu_gross';

export interface Grenzen {
  readonly maxDateien: number;
  readonly maxTiefe: number;
  readonly maxBytesDatei: number;
}

export const GRENZEN: Grenzen = { maxDateien: 500, maxTiefe: 8, maxBytesDatei: 50 * 1024 * 1024 };

/** Eine Datei, wie sie aus Dateiauswahl oder Drag & Drop kommt; `handle` ist das `File` (Tests: beliebig). */
export interface Quelle<T> {
  readonly relPfad: string;
  readonly name: string;
  readonly size: number;
  readonly type: string;
  readonly handle: T;
}

export interface ErfassteDatei<T> {
  readonly name: string;
  /** Pfad der Datei ab der Wurzel, mit `/`. */
  readonly relPfad: string;
  readonly groesse: number;
  readonly typ: string;
  readonly rolle: Rolle;
  /** Warum die Datei immer ignoriert bleibt; ohne Grund kann die Person die Rolle wählen. */
  readonly grund?: Grund;
  readonly handle: T;
}

export interface OrdnerKnoten {
  /** Leer bei der künstlichen Wurzel (mehrere Ordner oder lose Dateien). */
  readonly name: string;
  readonly pfad: string;
  readonly ordner: readonly OrdnerKnoten[];
  /** Indizes in `Erfassung.dateien`, direkt in diesem Ordner. */
  readonly dateien: readonly number[];
}

export interface Erfassung<T> {
  readonly wurzel: OrdnerKnoten;
  readonly dateien: readonly ErfassteDatei<T>[];
  readonly warnungen: readonly Warnung[];
}

const SYSTEM = /^(\.ds_store|thumbs\.db|desktop\.ini|~\$.*|\..*)$/i;
// eslint-disable-next-line no-control-regex
const STEUERZEICHEN = /[\u0000-\u001f\u007f]/;
const MAX_PFAD = 500;

function segmente(relPfad: string): string[] | null {
  if (relPfad.length > MAX_PFAD) return null;
  const teile = relPfad.replace(/\\/g, '/').split('/');
  if (teile.some((s) => s === '' || s === '.' || s === '..' || STEUERZEICHEN.test(s))) return null;
  return teile;
}

interface Bau { name: string; pfad: string; ordner: Map<string, Bau>; dateien: number[] }

function neuerOrdner(name: string, pfad: string): Bau {
  return { name, pfad, ordner: new Map(), dateien: [] };
}

function fest(b: Bau): OrdnerKnoten {
  const ordner = [...b.ordner.values()].sort((x, y) => (x.name < y.name ? -1 : x.name > y.name ? 1 : 0)).map(fest);
  return { name: b.name, pfad: b.pfad, ordner, dateien: b.dateien };
}

export function erfasse<T>(quellen: readonly Quelle<T>[], g: Grenzen = GRENZEN): Erfassung<T> {
  const warnungen = new Set<Warnung>();
  const gueltig: { teile: string[]; q: Quelle<T> }[] = [];
  for (const q of quellen) {
    const teile = segmente(q.relPfad);
    if (teile) gueltig.push({ teile, q });
    else warnungen.add('ungueltiger_pfad');
  }
  gueltig.sort((a, b) => (a.q.relPfad < b.q.relPfad ? -1 : a.q.relPfad > b.q.relPfad ? 1 : 0));
  if (gueltig.length > g.maxDateien) {
    gueltig.length = g.maxDateien;
    warnungen.add('zu_viele');
  }

  // Eine gemeinsame Wurzel nur, wenn alle Dateien im selben obersten Ordner liegen.
  const ersteOrdner = new Set(gueltig.map(({ teile }) => (teile.length > 1 ? teile[0] : '')));
  const eigeneWurzel = ersteOrdner.size === 1 && !ersteOrdner.has('');
  const wurzelName = eigeneWurzel ? [...ersteOrdner][0] : '';
  const wurzel = neuerOrdner(wurzelName, wurzelName);

  const dateien: ErfassteDatei<T>[] = [];
  for (const { teile, q } of gueltig) {
    const ordnerTeile = teile.slice(eigeneWurzel ? 1 : 0, -1);
    if (ordnerTeile.length > g.maxTiefe) warnungen.add('zu_tief');
    let ort = wurzel;
    for (const name of ordnerTeile.slice(0, g.maxTiefe)) {
      let kind = ort.ordner.get(name);
      if (!kind) {
        kind = neuerOrdner(name, ort.pfad ? `${ort.pfad}/${name}` : name);
        ort.ordner.set(name, kind);
      }
      ort = kind;
    }
    const name = teile[teile.length - 1];
    let rolle: Rolle = 'inhalt';
    let grund: Grund | undefined;
    if (SYSTEM.test(name)) grund = 'system';
    else if (q.size === 0) grund = 'leer';
    else if (q.size > g.maxBytesDatei) grund = 'zu_gross';
    if (grund) rolle = 'ignorieren';
    if (grund && grund !== 'system') warnungen.add(grund);
    ort.dateien.push(dateien.length);
    dateien.push({ name, relPfad: teile.join('/'), groesse: q.size, typ: q.type, rolle, ...(grund ? { grund } : {}), handle: q.handle });
  }
  return { wurzel: fest(wurzel), dateien, warnungen: [...warnungen] };
}

/** Datei-Auswahl (`<input type=file [webkitdirectory]>`) → Quellen. */
export function ausDateiliste(liste: ArrayLike<File>): Quelle<File>[] {
  return Array.from(liste, (f) => ({
    relPfad: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name,
    name: f.name, size: f.size, type: f.type, handle: f,
  }));
}

/* Die FileSystem-Einträge aus Drag & Drop, nur was hier gebraucht wird. */
interface Eintrag { readonly isFile: boolean; readonly isDirectory: boolean; readonly name: string }
interface DateiEintrag extends Eintrag { file(ok: (f: File) => void, fehler?: (e: unknown) => void): void }
interface OrdnerEintrag extends Eintrag {
  createReader(): { readEntries(ok: (e: Eintrag[]) => void, fehler?: (e: unknown) => void): void };
}

/**
 * Drag & Drop (`DataTransferItem.webkitGetAsEntry()`) → Quellen. Ordner liefern ihre Einträge in
 * Stücken; gelesen wird, bis ein leeres Stück kommt oder `grenze` Dateien beisammen sind (der Aufrufer
 * gibt `maxDateien + 1`, damit `erfasse` „zu viele“ erkennt).
 */
export async function ausEintraegen(eintraege: readonly Eintrag[], grenze = GRENZEN.maxDateien + 1): Promise<Quelle<File>[]> {
  const quellen: Quelle<File>[] = [];
  async function besuche(e: Eintrag, pfad: string): Promise<void> {
    if (quellen.length >= grenze) return;
    if (e.isFile) {
      const f = await new Promise<File>((ok, fehler) => (e as DateiEintrag).file(ok, fehler));
      quellen.push({ relPfad: pfad, name: f.name, size: f.size, type: f.type, handle: f });
    } else if (e.isDirectory) {
      const leser = (e as OrdnerEintrag).createReader();
      for (;;) {
        const stueck = await new Promise<Eintrag[]>((ok, fehler) => leser.readEntries(ok, fehler));
        if (!stueck.length) break;
        for (const kind of stueck) {
          if (quellen.length >= grenze) return;
          await besuche(kind, `${pfad}/${kind.name}`);
        }
      }
    }
  }
  for (const e of eintraege) await besuche(e, e.name);
  return quellen;
}
