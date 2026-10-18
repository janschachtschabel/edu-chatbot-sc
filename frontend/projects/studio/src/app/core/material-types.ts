/**
 * Materialformate (Paket 14, D1) — die reinen Regeln hinter der Seite.
 *
 * Gespeichert wird über den Bereichs-Endpunkt (`/config/data/05-canvas/material-types`); der
 * Server prüft dort das Modell. Hier stehen die Prüfungen, die das Studio vor dem Speichern
 * sagen kann (wie das alte Studio: Kennung, Eindeutigkeit, Name, Kategorie), und die
 * Querbezüge für die Vorschau:
 *
 * - **Aliase** (`05-canvas/type-aliases`): die Beschriftung ist zugleich der Chip-Text, der
 *   beim Klick zurückkommt. Ohne Alias auf diesen Typ fällt die Wahl still auf `auto` — der
 *   Wächter `test_material_type_labels` prüft das im Seed, die Vorschau sagt es beim Pflegen.
 *   Abgeglichen wird wie im Lader: `strip().lower()`.
 * - **Vorrang** (`05-canvas/persona-priorities`): analytische Typen stehen bei den
 *   `analytical_personas` vorn, didaktische bei allen übrigen.
 */

export const KATEGORIEN = ['didaktisch', 'analytisch'] as const;
export type Kategorie = (typeof KATEGORIEN)[number];

export interface MaterialTyp {
  readonly id: string;
  readonly label: string;
  readonly label_en?: string;
  readonly emoji?: string;
  readonly category: string;
  readonly structure?: string;
}

/** Prüffehler als Katalog-Endungen (`materialFormate.fehler.<code>`). */
export type Pruefung = 'id.format' | 'id.doppelt' | 'label.leer' | 'kategorie';

const KENNUNG = /^[a-z0-9_]+$/;

/**
 * Prüft einen Entwurf gegen die Liste. `original` ist die Kennung des bearbeiteten Eintrags
 * (`null` beim Anlegen) — der eigene Eintrag zählt nicht als Doppel.
 */
export function pruefe(
  alle: readonly MaterialTyp[], entwurf: MaterialTyp, original: string | null,
): readonly Pruefung[] {
  const fehler: Pruefung[] = [];
  if (!KENNUNG.test(entwurf.id)) fehler.push('id.format');
  else if (entwurf.id !== original && alle.some((t) => t.id === entwurf.id)) fehler.push('id.doppelt');
  if (!entwurf.label.trim()) fehler.push('label.leer');
  if (!(KATEGORIEN as readonly string[]).includes(entwurf.category)) fehler.push('kategorie');
  return fehler;
}

const schluessel = (text: string): string => text.trim().toLowerCase();

/** Die Aliase, die auf diesen Typ zeigen — sortiert. */
export function aliaseFuer(id: string, aliase: Readonly<Record<string, string>>): readonly string[] {
  return Object.entries(aliase).filter(([, ziel]) => ziel === id).map(([alias]) => alias).sort();
}

/** Chip-Texte (Name, Name en), zu denen kein Alias auf diesen Typ zeigt. */
export function fehlendeAliase(
  typ: MaterialTyp, aliase: Readonly<Record<string, string>>,
): readonly string[] {
  return [typ.label, typ.label_en ?? '']
    .filter((text) => text.trim())
    .filter((text) => aliase[schluessel(text)] !== typ.id)
    .map((text) => text.trim());
}

export type VorrangFall = 'nur' | 'ausser' | 'alle' | 'keine';

/**
 * Für wen der Typ vorn steht: analytisch → nur die analytischen Zielgruppen, didaktisch → alle
 * außer ihnen. Ohne analytische Zielgruppen steht ein analytischer Typ für niemanden vorn.
 */
export function vorrang(
  typ: MaterialTyp, analytisch: readonly string[],
): { readonly fall: VorrangFall; readonly personas: readonly string[] } {
  const personas = [...analytisch];
  if (typ.category === 'analytisch') return { fall: personas.length ? 'nur' : 'keine', personas };
  return { fall: personas.length ? 'ausser' : 'alle', personas };
}
