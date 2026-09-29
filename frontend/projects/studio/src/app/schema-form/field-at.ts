/**
 * Das Feld, das einen Dokumentpfad darstellt — `null`, wenn keins es tut (ST-2e).
 *
 * Damit weiß das Formular, welche Prüfmeldung des Servers an einem Feld stehen
 * kann und welche über dem Formular stehen muss. Eine Gruppe führt über den
 * Schlüssel ihres Kindes weiter, eine Liste bei einer Zahl über ihr
 * Element-Muster, eine Map bei jedem Schlüssel über ihr Eintrags-Muster.
 */
import type { SchemaField } from './schema-to-fields';

export function fieldAt(
  root: SchemaField,
  path: readonly (string | number)[],
): SchemaField | null {
  let field: SchemaField | undefined = root;
  for (const segment of path) {
    if (!field) return null;
    switch (field.kind) {
      case 'group':
        field = field.children?.find((child) => child.key === String(segment));
        break;
      case 'list':
        field = typeof segment === 'number' ? field.item : undefined;
        break;
      case 'map':
        field = field.item;
        break;
      default:
        return null;
    }
  }
  return field ?? null;
}
