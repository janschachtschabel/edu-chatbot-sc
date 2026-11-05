/**
 * Bearbeitungsregeln des Strukturentwurfs (Paket U2-e, Plan 2026-11-04 T-11) — ohne Angular.
 *
 * Bäume sind unveränderlich: jede Regel gibt einen neuen Baum zurück (unberührte Zweige bleiben
 * dieselben Objekte) oder eine {@link Ablehnung} mit Grund, den die Komponente ansagt. Die
 * Deckel sind die des Manifests (`eingabe`/`antwort`) und des Backends
 * (`ui_module/strukturentwurf.py`): sonst verwürfe der Server die Antwort still.
 */

export interface EntwurfKnoten {
  readonly id: string;
  readonly titel: string;
  readonly beschreibung?: string;
  readonly keywords?: readonly string[];
  readonly fach?: string;
  readonly bildungsstufe?: string;
  readonly wlo_id?: string;
  readonly ausstehend?: boolean;
  readonly kinder?: readonly EntwurfKnoten[];
}

export type Baum = readonly EntwurfKnoten[];

export const HOECHSTE_TIEFE = 4;
export const HOECHSTENS_OBEN = 30;
export const HOECHSTENS_KINDER = 15;
export const HOECHSTENS_KNOTEN = 250;
export const TITEL_ZEICHEN = 120;
export const BESCHREIBUNG_ZEICHEN = 300;
export const KEYWORDS = 8;
export const KEYWORD_ZEICHEN = 40;

export type Grund = 'tiefe' | 'kinder' | 'gesamt' | 'oben' | 'unten' | 'erster' | 'oberste' | 'fehlt';
export interface Ablehnung { readonly grund: Grund }

export interface Fund {
  readonly knoten: EntwurfKnoten;
  readonly ebene: number;
  readonly eltern: string | null;
  readonly index: number;
  readonly geschwister: Baum;
}

export function finde(baum: Baum, id: string, ebene = 1, eltern: string | null = null): Fund | null {
  for (const [index, knoten] of baum.entries()) {
    if (knoten.id === id) return { knoten, ebene, eltern, index, geschwister: baum };
    const tiefer = finde(knoten.kinder ?? [], id, ebene + 1, knoten.id);
    if (tiefer) return tiefer;
  }
  return null;
}

export function anzahl(baum: Baum): number {
  return baum.reduce((n, k) => n + 1 + anzahl(k.kinder ?? []), 0);
}

/** Ebenen eines Zweigs samt ihm selbst (ein Blatt: 1). */
function hoehe(k: EntwurfKnoten): number {
  return 1 + Math.max(0, ...(k.kinder ?? []).map(hoehe));
}

const grenze = (ebene: number): number => (ebene === 1 ? HOECHSTENS_OBEN : HOECHSTENS_KINDER);

function mitKindern(k: EntwurfKnoten, kinder: Baum): EntwurfKnoten {
  const { kinder: _alt, ausstehend: _offen, ...rest } = k;
  return kinder.length ? { ...rest, kinder } : rest;
}

/** Die Geschwisterliste, in der `id` steht, durch `f` ersetzen — der Rest bleibt gleich. */
function inListe(baum: Baum, id: string, f: (liste: Baum, i: number) => Baum): Baum | null {
  const i = baum.findIndex((k) => k.id === id);
  if (i >= 0) return f(baum, i);
  for (const [j, k] of baum.entries()) {
    const neu = k.kinder ? inListe(k.kinder, id, f) : null;
    if (neu) return baum.map((x, n) => (n === j ? mitKindern(x, neu) : x));
  }
  return null;
}

const ersetzt = (liste: Baum, i: number, ...neu: EntwurfKnoten[]): Baum =>
  [...liste.slice(0, i), ...neu, ...liste.slice(i + 1)];

export function setzeFelder(
  baum: Baum, id: string, felder: { titel?: string; beschreibung?: string; keywords?: readonly string[] },
): Baum | Ablehnung {
  const neu = inListe(baum, id, (liste, i) => {
    const k: Record<string, unknown> = { ...liste[i], ...felder };
    if (k['beschreibung'] === '') delete k['beschreibung'];
    if (Array.isArray(k['keywords']) && !(k['keywords'] as unknown[]).length) delete k['keywords'];
    return ersetzt(liste, i, k as unknown as EntwurfKnoten);
  });
  return neu ?? { grund: 'fehlt' };
}

/** Einen Punkt einfügen: als letzten Unterpunkt von `id` (`kind`) oder direkt nach `id`
 *  (`danach`); `id: null` hängt ihn oben an. */
export function hinzufuegen(
  baum: Baum, id: string | null, wo: 'kind' | 'danach', neu: EntwurfKnoten,
): { readonly baum: Baum; readonly id: string } | Ablehnung {
  if (anzahl(baum) >= HOECHSTENS_KNOTEN) return { grund: 'gesamt' };
  if (id === null) return baum.length >= HOECHSTENS_OBEN ? { grund: 'kinder' } : { baum: [...baum, neu], id: neu.id };
  const fund = finde(baum, id);
  if (!fund) return { grund: 'fehlt' };
  if (wo === 'kind') {
    if (fund.ebene >= HOECHSTE_TIEFE) return { grund: 'tiefe' };
    if ((fund.knoten.kinder?.length ?? 0) >= HOECHSTENS_KINDER) return { grund: 'kinder' };
    const ergebnis = inListe(baum, id, (liste, i) =>
      ersetzt(liste, i, mitKindern(liste[i], [...(liste[i].kinder ?? []), neu])));
    return { baum: ergebnis ?? baum, id: neu.id };
  }
  if (fund.geschwister.length >= grenze(fund.ebene)) return { grund: 'kinder' };
  const ergebnis = inListe(baum, id, (liste, i) => ersetzt(liste, i, liste[i], neu));
  return { baum: ergebnis ?? baum, id: neu.id };
}

/** Einen Punkt samt Unterpunkten löschen; `fokus`: der nächste, sonst der vorige Geschwister,
 *  sonst der Elternpunkt. */
export function loeschen(baum: Baum, id: string): { readonly baum: Baum; readonly fokus: string | null } | Ablehnung {
  const fund = finde(baum, id);
  if (!fund) return { grund: 'fehlt' };
  const g = fund.geschwister;
  const fokus = g[fund.index + 1]?.id ?? g[fund.index - 1]?.id ?? fund.eltern;
  return { baum: inListe(baum, id, (liste, i) => ersetzt(liste, i)) ?? baum, fokus };
}

export function verschieben(baum: Baum, id: string, richtung: -1 | 1): Baum | Ablehnung {
  const fund = finde(baum, id);
  if (!fund) return { grund: 'fehlt' };
  const ziel = fund.index + richtung;
  if (ziel < 0) return { grund: 'oben' };
  if (ziel >= fund.geschwister.length) return { grund: 'unten' };
  return inListe(baum, id, (liste, i) => {
    const neu = [...liste];
    [neu[i], neu[ziel]] = [neu[ziel], neu[i]];
    return neu;
  }) ?? baum;
}

/** Zum letzten Unterpunkt des Punkts davor machen — der ganze Zweig muss in die Tiefe passen. */
export function einruecken(baum: Baum, id: string): Baum | Ablehnung {
  const fund = finde(baum, id);
  if (!fund) return { grund: 'fehlt' };
  if (fund.index === 0) return { grund: 'erster' };
  if (fund.ebene + hoehe(fund.knoten) > HOECHSTE_TIEFE) return { grund: 'tiefe' };
  const davor = fund.geschwister[fund.index - 1];
  if ((davor.kinder?.length ?? 0) >= HOECHSTENS_KINDER) return { grund: 'kinder' };
  return inListe(baum, id, (liste, i) => [
    ...liste.slice(0, i - 1),
    mitKindern(davor, [...(davor.kinder ?? []), liste[i]]),
    ...liste.slice(i + 1),
  ]) ?? baum;
}

/** Zum Geschwister direkt nach seinem Elternpunkt machen. */
export function ausruecken(baum: Baum, id: string): Baum | Ablehnung {
  const fund = finde(baum, id);
  if (!fund) return { grund: 'fehlt' };
  if (fund.eltern === null) return { grund: 'oberste' };
  const eltern = finde(baum, fund.eltern) as Fund;
  if (eltern.geschwister.length >= grenze(eltern.ebene)) return { grund: 'kinder' };
  return inListe(baum, eltern.knoten.id, (liste, i) => {
    const ohne = (liste[i].kinder ?? []).filter((k) => k.id !== id);
    const elternNeu = ohne.length ? { ...liste[i], kinder: ohne } : (({ kinder: _k, ...rest }) => rest)(liste[i]);
    return ersetzt(liste, i, elternNeu, fund.knoten);
  }) ?? baum;
}

let zaehler = 0;

/** Eine neue Kennung, die im Baum noch nicht vorkommt (Form wie im Manifest). */
export function neueKennung(baum: Baum): string {
  const vergeben = new Set<string>();
  const sammeln = (b: Baum): void => b.forEach((k) => { vergeben.add(k.id); sammeln(k.kinder ?? []); });
  sammeln(baum);
  let kennung: string;
  do {
    zaehler += 1;
    kennung = `n${Date.now().toString(36)}${zaehler.toString(36)}`;
  } while (vergeben.has(kennung));
  return kennung;
}

/** Für die Antwort: Titel ohne überzählige Leerzeichen und nie leer (das Schema verlangt einen —
 *  sonst verwürfe der Server die Antwort still), Beschreibungen ohne Rand. */
export function bereinigt(baum: Baum, ersatz: string): Baum {
  return baum.map((k) => {
    const titel = k.titel.replace(/\s+/g, ' ').trim().slice(0, TITEL_ZEICHEN) || ersatz;
    const beschreibung = k.beschreibung?.trim().slice(0, BESCHREIBUNG_ZEICHEN);
    const { beschreibung: _b, kinder, ...rest } = k;
    return {
      ...rest, titel,
      ...(beschreibung ? { beschreibung } : {}),
      ...(kinder?.length ? { kinder: bereinigt(kinder, ersatz) } : {}),
    };
  });
}
