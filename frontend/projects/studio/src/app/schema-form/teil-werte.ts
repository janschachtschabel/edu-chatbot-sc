/**
 * Paket K2c-3: die Regeln hinter der Tabelle „Argumente“ eines Ablaufschritts — ohne DOM.
 *
 * Ein Objekt Name → Wert (Schema-Auszeichnung `x-widget: teil-werte`): jeder Wert ist ein fester
 * Text, ein Teil des Vorgangs (`{"$teil": "<name>"}`, liest der Treiber beim Lauf) oder sonst JSON.
 * Die Tabelle zeigt je Zeile Name, Art und Wert; was sie nicht als Text oder Teil lesen kann,
 * bleibt als JSON-Zeile erhalten — nichts geht beim Öffnen verloren.
 *
 * Paket K2d-1: ein Verweis mit Pfad (`{"$teil": "volltext", "pfad": "outputs.markdown"}`) ist eine
 * Teil-Zeile mit dem Wert `volltext.outputs.markdown` — ein Name eines Teils hat keinen Punkt
 * (`teil_verweise.NAME`), das erste Glied ist also der Teil, der Rest der Pfad.
 */

export type TeilArt = 'text' | 'teil' | 'json';

export interface TeilZeile {
  readonly name: string;
  readonly art: TeilArt;
  /** Text, Name des Teils oder JSON-Text — je nach Art. */
  readonly wert: string;
}

/** Wie der Treiber einen Verweis erkennt (`services/teil_verweise.SCHLUESSEL`). */
export const TEIL_SCHLUESSEL = '$teil';

export const PFAD_SCHLUESSEL = 'pfad';

/** Genau die Regel des Treibers (`teil_verweise.verweis`): `$teil` mit einem Text, dazu höchstens
 *  `pfad` mit einem Text (K2d-1). Alles andere bleibt JSON. */
export function istTeil(wert: unknown): wert is { readonly $teil: string; readonly pfad?: string } {
  if (typeof wert !== 'object' || wert === null || Array.isArray(wert)) return false;
  const w = wert as Record<string, unknown>;
  const schluessel = Object.keys(w);
  if (typeof w[TEIL_SCHLUESSEL] !== 'string') return false;
  return schluessel.length === 1
    || (schluessel.length === 2 && typeof w[PFAD_SCHLUESSEL] === 'string');
}

/** Der Wert einer Teil-Zeile: der Name, mit Pfad `name.pfad`. */
function teilText(w: { readonly $teil: string; readonly pfad?: string }): string {
  return w.pfad === undefined ? w.$teil : `${w.$teil}.${w.pfad}`;
}

/** Der Verweis zu einer Teil-Zeile — das erste Glied ist der Teil, der Rest (wenn da) der Pfad. */
function verweisAus(text: string): Record<string, string> {
  const punkt = text.indexOf('.');
  return punkt < 0
    ? { [TEIL_SCHLUESSEL]: text }
    : { [TEIL_SCHLUESSEL]: text.slice(0, punkt), [PFAD_SCHLUESSEL]: text.slice(punkt + 1) };
}

/** Die Zeilen eines gespeicherten Werts; kein Objekt → keine Zeilen (die JSON-Ansicht zeigt ihn). */
export function zeilenAus(wert: unknown): TeilZeile[] {
  if (typeof wert !== 'object' || wert === null || Array.isArray(wert)) return [];
  return Object.entries(wert as Record<string, unknown>).map(([name, w]) => {
    // Review K2c-3 (2), Befund 2: ein Text mit Zeilenumbruch verlöre ihn in einem einzeiligen Feld
    // (`<input>` streicht ihn) — er steht verlustfrei als JSON-Zeile da.
    if (typeof w === 'string' && !/[\r\n]/.test(w)) return { name, art: 'text', wert: w };
    // Review K2d-1, Befund 4: ein Name mit Punkt (ungültig, die Prüfung meldet ihn) sähe als
    // `name.pfad` aus wie ein Verweis mit Pfad — beim nächsten Schreiben würde er still einer.
    // Review K2d-1 (2), Befund 3: ein Umbruch in Name oder Pfad (ungültig, die Prüfung meldet ihn)
    // ginge im einzeiligen Feld still verloren.
    if (istTeil(w) && !w.$teil.includes('.') && !/[\r\n]/.test(teilText(w))) {
      return { name, art: 'teil', wert: teilText(w) };
    }
    return { name, art: 'json', wert: JSON.stringify(w) };
  });
}

/** Ob ein gespeicherter Wert sich als Tabelle zeigen lässt (ein Objekt oder nichts). Ein Verweis
 *  auf einen ganzen Teil (`daten: {$teil: draft}`, `treiber._daten`) ist KEIN Objekt mit einem
 *  Eintrag „$teil“ — als Zeile bearbeitet, wäre er kein Verweis mehr (Review K2c-3, Befund 1). */
export function alsTabelleLesbar(wert: unknown): boolean {
  if (istTeil(wert)) return false;
  return wert === undefined || wert === null
    || (typeof wert === 'object' && !Array.isArray(wert));
}

export type ZeilenFehler =
  | { readonly art: 'name_leer'; readonly zeile: number }
  | { readonly art: 'name_doppelt'; readonly zeile: number; readonly name: string }
  | { readonly art: 'teil_leer'; readonly zeile: number }
  | { readonly art: 'json'; readonly zeile: number };

/** Der Wert aus den Zeilen — oder der erste Fehler, der ihn verhindert (dann wird nichts
 *  geschrieben: ein halber Stand in der Tabelle soll das Dokument nicht still verändern). Ohne Zeilen
 *  `null` — nicht `{}`: die Fassung eines Ablaufs lässt nur `None` weg (Review K2c-3, Befund 7).
 *  Namen und Teile bleiben, wie sie getippt sind (Befund 6: kein stilles Umbenennen); nur ein Name
 *  aus Leerzeichen gilt als leer. */
export function wertAus(zeilen: readonly TeilZeile[]): { wert: Record<string, unknown> | null } | { fehler: ZeilenFehler } {
  if (!zeilen.length) return { wert: null };
  // Review K2c-3 (2), Befund 5: erst sammeln, dann `Object.fromEntries` — eine Zuweisung
  // `wert['__proto__'] = …` setzte den Prototyp statt einen Eintrag.
  const eintraege = new Map<string, unknown>();
  for (const [i, z] of zeilen.entries()) {
    const name = z.name;
    if (!name.trim()) return { fehler: { art: 'name_leer', zeile: i } };
    if (eintraege.has(name)) return { fehler: { art: 'name_doppelt', zeile: i, name } };
    if (z.art === 'text') eintraege.set(name, z.wert);
    else if (z.art === 'teil') {
      if (!z.wert.trim()) return { fehler: { art: 'teil_leer', zeile: i } };
      eintraege.set(name, verweisAus(z.wert));
    } else {
      try {
        eintraege.set(name, JSON.parse(z.wert));
      } catch {
        return { fehler: { art: 'json', zeile: i } };
      }
    }
  }
  return { wert: Object.fromEntries(eintraege) };
}

/**
 * Die Teile, die die Schritte VOR diesem bereitstellen (`schreibt`, `agent.ausgabe`) — gelesen aus
 * dem ganzen Dokument entlang des Pfads (`…, 'schritte', j, 'argumente'`). Ohne `schritte` im Pfad
 * keine. Nur Text-Namen, je einmal, in Reihenfolge.
 */
export function vorigeTeile(dokument: unknown, pfad: readonly (string | number)[]): string[] {
  const k = pfad.lastIndexOf('schritte');
  const j = pfad[k + 1];
  if (k < 0 || typeof j !== 'number') return [];
  let knoten: unknown = dokument;
  for (const teil of pfad.slice(0, k + 1)) {
    if (typeof knoten !== 'object' || knoten === null) return [];
    knoten = (knoten as Record<string | number, unknown>)[teil];
  }
  if (!Array.isArray(knoten)) return [];
  const aus: string[] = [];
  for (const schritt of knoten.slice(0, j)) {
    if (typeof schritt !== 'object' || schritt === null) continue;
    const s = schritt as Record<string, unknown>;
    const agent = s['agent'] as Record<string, unknown> | undefined;
    for (const name of [s['schreibt'], agent?.['ausgabe']]) {
      if (typeof name === 'string' && name.trim() && !aus.includes(name.trim())) aus.push(name.trim());
    }
  }
  return aus;
}
