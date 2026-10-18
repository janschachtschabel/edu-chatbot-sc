/**
 * Welche Felder eines Dokuments ein Abschnitt zeigt (Paket 14 `felder`, Paket 15 `ohneFelder`).
 *
 * Gespeichert wird immer das ganze Dokument; der Ausschnitt bestimmt nur, was das Formular
 * zeigt (`pickFields`). `null` = alle Felder.
 */
import type { JsonSchema } from '../schema-form/json-schema';
import { fieldPaths } from '../schema-form/pick-fields';
import { rootField } from '../schema-form/schema-to-fields';
import type { CuratedAreaSection } from './curated-views';

export function feldAusschnitt(
  schema: JsonSchema | null, section: Pick<CuratedAreaSection, 'felder' | 'ohneFelder'>,
): readonly string[] | null {
  if (section.felder) return section.felder;
  if (!section.ohneFelder || !schema) return null;
  const ohne = new Set(section.ohneFelder);
  return fieldPaths(rootField(schema)).filter((pfad) => !ohne.has(pfad));
}
