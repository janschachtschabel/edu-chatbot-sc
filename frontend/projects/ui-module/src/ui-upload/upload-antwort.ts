/**
 * Was `ui_upload` als Antwort schickt (Paket U3-1a, Plan §16.5): der Ordnerbaum mit Zahlen, die Zahlen
 * je Rolle, Warnungen und — falls markiert — das Strukturdokument. Seit U3-2c kann ein markiertes
 * Strukturdokument gelesen werden; dann trug die Antwort dessen Befund (`dokument`). Seit Plan
 * 2026-11-17, Paket U4 antwortet das Modul mit `aktion: "bereitgestellt"` und `ort`
 * (`upload-chat.ts`, `upload-uebertragen.ts`). Ordnernamen sind eine Zeile und höchstens 120 Zeichen; der Baum hat höchstens
 * `MAX_KNOTEN` Ordner (darüber Warnung `zu_viele_ordner`).
 *
 * Plan 2026-11-16, TG-3a (Datenmodell, G-E1): jeder Ordner trägt seine Dateien (`dateiliste`) — je
 * Datei die feste Nummer `i` (Stelle in `Erfassung.dateien`, stabil über die ganze Auswahl; dieselbe
 * Nummer schickt die Übertragung nach WLO mit, TG-3b), Name, Endung, Größe und Rolle. Binärdaten
 * nie. Systemdateien (`.DS_Store` …) fehlen wie im Baum der Ansicht; ihre Nummern bleiben frei. Ein
 * gekürzter Name (über 120 Zeichen) meldet `namen_gekuerzt` — keine stille Kürzung. Höchstens 500
 * Dateien kappt schon `erfasse` (`zu_viele`).
 */
import type { AblageRolle } from '../_vertrag/modul-host';
import type { Erfassung, OrdnerKnoten, Rolle, Warnung } from './upload-erfassen';
import { istGliederung, strukturZahl } from './upload-rollen';

export const MAX_KNOTEN = 500;
const MAX_NAME = 120;

// Plan 2026-11-16, TG-1 (G-E4): ohne `ordner_als_entwurf` — das Feld kennt kein Ziel mehr.
// Plan 2026-11-17, Paket U4: `bereitgestellt` (Feld `ort`) ist die Antwort des einen Upload-Wegs;
// `dokument` und `uebertragen` schickt das Modul nicht mehr, alte Antworten zeigt es noch an.
export type AntwortAktion = 'erfasst' | 'dokument' | 'uebertragen' | 'bereitgestellt';
export type AntwortWarnung = Warnung | 'zu_viele_ordner' | 'namen_gekuerzt';

/** TG-3a: eine Datei im Ordner — `i` ist ihre feste Nummer in der Auswahl. Review TG-3a–c, R3-4:
 *  eine ignorierte Datei geht ohne Namen mit (Datensparsamkeit) — nur Nummer, Endung, Größe. */
export interface AntwortDatei {
  readonly i: number;
  readonly name?: string;
  /** Kleingeschrieben, nur Buchstaben und Ziffern, höchstens 10; leer ohne Endung. */
  readonly endung: string;
  readonly groesse: number;
  readonly rolle: Rolle;
}

export interface AntwortOrdner {
  readonly name: string;
  /** Inhalte und Strukturdokument direkt in diesem Ordner (ohne ignorierte). */
  readonly dateien: number;
  /** dasselbe samt aller Unterordner */
  readonly alle_dateien: number;
  readonly kinder: readonly AntwortOrdner[];
  /** TG-3a: die Dateien direkt in diesem Ordner (auch ignorierte, ohne Systemdateien). */
  readonly dateiliste: readonly AntwortDatei[];
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
    readonly upload_id: string; readonly name: string; readonly format: string;
    readonly befund: {
      readonly seiten: number | null; readonly woerter: number; readonly abschnitte: number;
      readonly gliederung_art: string; readonly warnungen: readonly string[];
    };
    readonly vorschau: readonly string[];
  };
  /** Plan 2026-11-16, TG-3e, nur mit `aktion: "dokument"` und mehr als einem gelesenen Dokument:
   *  alle in Lesereihenfolge (das erste steht zugleich in `dokument`). */
  readonly dokumente?: readonly NonNullable<UploadAntwort['dokument']>[];
  /** Paket U4, nur mit `aktion: "bereitgestellt"`: wo verarbeitet wurde. */
  readonly ort?: 'chat' | 'wlo' | 'namen';
  /** Paket U4, nur mit `ort` chat oder wlo: je bereitgestellte Datei die Nummer `i` der Auswahl, die
   *  Rolle und bei chat die `upload_id` (nicht lesbare bzw. nicht abgelegte Dateien fehlen). */
  readonly dateien?: readonly { readonly i: number; readonly rolle: AblageRolle; readonly upload_id?: string }[];
  /** U3-3b, mit `aktion: "uebertragen"` bzw. `bereitgestellt` und `ort: "wlo"`: nur Zahlen der Ablage. */
  readonly ablage?: {
    readonly layout: 'ordner' | 'flach'; readonly gesamt: number; readonly abgelegt: number;
    readonly unklar: number; readonly fehler: number; readonly abgebrochen: number;
    readonly ordner_verweigert: boolean; readonly vorgang_abgelegt: boolean;
    /** Review P2, Befund 1: hielt der Server das Häkchen fest (ältere Antworten: fehlt)? */
    readonly erschliessen?: boolean;
  };
}

export function einZeiler(name: string): string {
  // Nach Codepunkten kürzen: ein Emoji an Stelle 120 bliebe sonst ein halbes Zeichen.
  return Array.from(name.replace(/\s+/g, ' ').trim()).slice(0, MAX_NAME).join('');
}

/** Wird `name` von `einZeiler` gekürzt? */
function zuLang(name: string): boolean {
  return Array.from(name.replace(/\s+/g, ' ').trim()).length > MAX_NAME;
}

/** Die Endung für die Antwort: nach dem letzten Punkt (nicht am Anfang), sonst leer. */
export function endungVon(name: string): string {
  const punkt = name.lastIndexOf('.');
  const endung = punkt > 0 ? name.slice(punkt + 1).toLowerCase() : '';
  return /^[a-z0-9]{1,10}$/.test(endung) ? endung : '';
}

/** Review TG-3a–c, NIT: ein Dateiname nur aus Leerzeichen wird ein Platzhalter (`ohneName`, je
 *  Sprache „(ohne Namen)“ / „(no name)“) — leer verwürfe das Schema die ganze Antwort. */
export function antwortDaten<T>(e: Erfassung<T>, aktion: AntwortAktion, ohneName = '(ohne Namen)'): UploadAntwort {
  const zaehlt = (i: number): boolean => e.dateien[i].rolle !== 'ignorieren';
  let knoten = 0;
  let gekappt = false;
  let ordner = 0;
  let gekuerzt = false;

  function datei(i: number): AntwortDatei[] {
    const d = e.dateien[i];
    if (d.grund === 'system') return [];
    // R3-4: ausgeschlossen heißt ohne Namen — er geht nicht an den Chat
    if (d.rolle === 'ignorieren') return [{ i, endung: endungVon(d.name), groesse: d.groesse, rolle: d.rolle }];
    if (zuLang(d.name)) gekuerzt = true;
    return [{ i, name: einZeiler(d.name) || ohneName, endung: endungVon(d.name), groesse: d.groesse, rolle: d.rolle }];
  }

  function baue(k: OrdnerKnoten): AntwortOrdner {
    knoten++;
    if (k.name) ordner++;
    if (zuLang(k.name)) gekuerzt = true;
    const kinder: AntwortOrdner[] = [];
    let alle = k.dateien.filter(zaehlt).length;
    for (const kind of k.ordner) {
      const unten = summe(kind);
      alle += unten;
      if (knoten < MAX_KNOTEN) kinder.push(baue(kind));
      else gekappt = true;
    }
    return {
      name: einZeiler(k.name), dateien: k.dateien.filter(zaehlt).length, alle_dateien: alle, kinder,
      dateiliste: k.dateien.flatMap(datei),
    };
  }
  function summe(k: OrdnerKnoten): number {
    return k.dateien.filter(zaehlt).length + k.ordner.reduce((s, o) => s + summe(o), 0);
  }

  const struktur = baue(e.wurzel);
  const zaehlen = (rolle: string): number => e.dateien.filter((d) => d.rolle === rolle).length;
  // P1 (Plan 2026-11-20): `beides` ist Strukturdokument; `inhalte` zählt nur reines Material, so
  // bleibt `inhalte + strukturdokumente` die Zahl der verwendeten Dateien
  const sd = e.dateien.find((d) => istGliederung(d.rolle));
  const warnungen: AntwortWarnung[] = [...e.warnungen];
  if (gekappt) warnungen.push('zu_viele_ordner');
  if (gekuerzt || (sd && zuLang(sd.name))) warnungen.push('namen_gekuerzt');
  return {
    aktion,
    struktur,
    zahlen: {
      ordner, dateien: e.dateien.length, inhalte: zaehlen('inhalt'), ignoriert: zaehlen('ignorieren'),
      strukturdokumente: strukturZahl(e),
      bytes: e.dateien.reduce((s, d) => s + (d.rolle === 'ignorieren' ? 0 : d.groesse), 0),
    },
    strukturdokument: sd
      ? { name: einZeiler(sd.name) || ohneName, groesse: sd.groesse, endung: endungVon(sd.name) }
      : null,
    warnungen,
  };
}
