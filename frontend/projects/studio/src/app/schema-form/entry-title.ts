/**
 * Der Titel eines Eintrags in einer Liste von Objekten (ST-3, Liste│Editor).
 *
 * Aus dem ersten nicht leeren Feld unter `title`, `label`, `name`, `id` — in
 * dieser Reihenfolge, weil ein Titel mehr sagt als eine Kennung („Lehrkraft
 * plant Stunde" statt „GV-LEH-1"). Nur Felder, die das MODELL kennt: ein
 * gleichnamiger Schlüssel aus dem Rohtext ist Beifang, kein Titel. Ohne
 * Kandidaten der Rückfall des Aufrufers („Eintrag 3").
 *
 * Eine Heuristik statt eines Hinweises je Modell (`x-item-title` in §9.1): sie
 * trifft alle Listen des Bestands; ein Hinweis kommt erst, wenn sie irrt.
 */
import type { SchemaField } from './schema-to-fields';

const TITLE_KEYS = ['title', 'label', 'name', 'id'] as const;

export function entryTitle(item: SchemaField, value: unknown, fallback: string): string {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fallback;
  const known = new Set((item.children ?? []).map((child) => child.key));
  const record = value as Record<string, unknown>;
  for (const key of TITLE_KEYS) {
    const text = record[key];
    if (known.has(key) && typeof text === 'string' && text.trim()) return text.trim();
  }
  return fallback;
}
