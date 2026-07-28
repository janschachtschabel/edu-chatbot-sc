/**
 * Ein Ausschnitt des Feld-Baums, für Formulare mit Reitern (A7).
 *
 * Der Renderer bindet jedes Feld an einen Pfad im Dokument, nicht an eine
 * Position im Baum (`schema-to-fields.ts`). Ein Ausschnitt ist deshalb
 * ungefährlich: was hier fehlt, wird nur nicht angezeigt — gespeichert wird
 * weiterhin das ganze Dokument.
 *
 * Zwei Ebenen genügen: die Bereichsdokumente mit Reitern sind
 * `{frontmatter: {…}, body: "…"}`. Ein Pfad meint entweder ein Wurzel-Feld
 * (`body`) oder ein Kind einer Wurzel-Gruppe (`frontmatter.label`).
 */
import type { SchemaField } from './schema-to-fields';

/**
 * Die Wurzel-Gruppe, auf die genannten Pfade reduziert. Die Reihenfolge bleibt
 * die des Schemas — ein Formular soll in jedem Reiter gleich gelesen werden.
 * Unbekannte Pfade werden ignoriert: eine veraltete Tabelle darf das Formular
 * nicht zerlegen.
 */
export function pickFields(root: SchemaField, paths: ReadonlySet<string>): SchemaField {
  const children = (root.children ?? []).flatMap((child) => {
    if (paths.has(child.key)) return [child];
    if (child.kind !== 'group') return [];
    const kept = (child.children ?? []).filter((leaf) => paths.has(`${child.key}.${leaf.key}`));
    return kept.length > 0 ? [{ ...child, children: kept }] : [];
  });
  return { ...root, children };
}

/**
 * Jeder Pfad, den ein Reiter aufnehmen kann — Kinder einer Wurzel-Gruppe
 * einzeln, alles andere als Ganzes. Grundlage der Vollständigkeits-Prüfung:
 * kein Feld darf zwischen den Reitern verschwinden.
 */
export function fieldPaths(root: SchemaField): readonly string[] {
  return (root.children ?? []).flatMap((child) =>
    child.kind === 'group'
      ? (child.children ?? []).map((leaf) => `${child.key}.${leaf.key}`)
      : [child.key],
  );
}
