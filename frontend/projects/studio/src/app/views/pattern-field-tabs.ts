/**
 * Die Reiter des Pattern-Formulars (A7) — ALTs Gliederung, nachgemessen.
 *
 * Ein Pattern-Dokument hat 21 Kopf-Felder plus den Anweisungstext. In einem
 * Fieldset ist das eine Wand; ALT hat sie deshalb in fünf Reiter geschnitten
 * (`studio/src/components/PatternEditor.tsx:388-406`), und diese Gliederung
 * wird hier übernommen — Reihenfolge und Beschriftungen wörtlich.
 *
 * **Was NICHT übernommen ist, und warum:**
 *  - ALT rendert `short_purpose`, `output_mode` und `card_text_link_required`
 *    in KEINEM Reiter — sie waren dort nicht editierbar. NEUs generisches
 *    Formular zeigt sie heute; ein wörtlicher Port hätte drei Felder versteckt.
 *    Sie stehen deshalb bei ihrer Bedeutung (Identität bzw. Antwort-Form).
 *  - `id` zeigt ALT nur als Überschrift. Hier ist es ein Feld wie jedes andere
 *    und steht in „Identität".
 *  - Fünf ALT-Felder (`card_text_mode`, `default_detail`, `format_primary`,
 *    `format_follow_up`, `quick_replies_max`) gibt es im NEU-Modell nicht;
 *    sie fehlen hier, weil sie nirgends existieren.
 *
 * Beobachtet, aber bewusst nicht gefolgt: der Judge im Backend bündelt
 * `response_type` mit `default_length`/`output_mode` unter „Antwort-Form"
 * (`services/eval/judge.py:68-79`). ALT hat `response_type` in „Identität" —
 * und A7 ist die Wiederherstellung von ALTs Gliederung, nicht ihre Revision.
 */
import { fieldPaths } from '../schema-form/pick-fields';
import type { SchemaField } from '../schema-form/schema-to-fields';

export interface FieldTab {
  /** Auch das Id-Suffix der Reiterleiste: `#tab-<id>` steuert `#panel-<id>`. */
  readonly id: string;
  readonly label: string;
  /** Dokument-Pfade in Schema-Reihenfolge (siehe `pickFields`). */
  readonly paths: readonly string[];
}

/** Der Schnitt, ohne die Frage, ob es die Felder gibt. */
const TAB_TABLE: readonly { id: string; label: string; keys: readonly string[] }[] = [
  {
    id: 'pf-identitaet', label: 'Identität',
    keys: ['id', 'label', 'short_purpose', 'priority', 'response_type'],
  },
  {
    id: 'pf-antwortform', label: 'Antwort-Form',
    keys: [
      'default_tone', 'default_length', 'output_mode', 'quick_replies_mode',
      'card_text_link_required',
    ],
  },
  { id: 'pf-tools', label: 'Tools & Wissen', keys: ['sources', 'rag_areas', 'tools'] },
  { id: 'pf-slots', label: 'Slots & Degradation', keys: ['precondition_slots'] },
  {
    id: 'pf-anweisungen', label: 'Anweisungen',
    keys: [
      'core_rule', 'when_to_use', 'when_not_to_use', 'trigger_phrases', 'discriminators',
      'forbidden_phrases', 'anti_patterns', 'body',
    ],
  },
];

/** Reiter für den Auffang-Korb — erscheint nur, wenn er etwas enthält. */
const EXTRA_TAB = { id: 'pf-weitere', label: 'Weitere' };

/**
 * Die Reiter für dieses Schema: leere fallen weg, unbekannte Felder landen in
 * „Weitere". Damit kann ein Reiter-Schnitt weder etwas verstecken noch Inhalt
 * behaupten, den es nicht gibt.
 */
export function patternFieldTabs(root: SchemaField): readonly FieldTab[] {
  const available = fieldPaths(root);
  const taken = new Set<string>();

  const tabs: FieldTab[] = [];
  for (const { id, label, keys } of TAB_TABLE) {
    // Nach dem Schema gefiltert, nicht nach der Tabelle: die Reihenfolge im
    // Formular ist überall die des Schemas.
    const paths = available.filter((path) => keys.includes(lastSegment(path)));
    paths.forEach((path) => taken.add(path));
    if (paths.length > 0) tabs.push({ id, label, paths });
  }

  const rest = available.filter((path) => !taken.has(path));
  if (rest.length > 0) tabs.push({ ...EXTRA_TAB, paths: rest });
  return tabs;
}

function lastSegment(path: string): string {
  const cut = path.lastIndexOf('.');
  return cut < 0 ? path : path.slice(cut + 1);
}
