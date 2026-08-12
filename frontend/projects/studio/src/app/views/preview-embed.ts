/**
 * Der Seitenkontext, den die Live-Vorschau dem Widget vorgibt (A6-Rest, 9-6).
 *
 * Auf einer echten Host-Seite erkennt das Widget den Kontext selbst
 * (`page-context-detector.ts`). Im Studio ist das nutzlos bis irreführend: dort
 * würde es die Studio-URL, den Studio-Titel und den Studio-DOM einsammeln und
 * als „Seite des Besuchers" ans Backend schicken. Die Vorschau schaltet die
 * Erkennung deshalb ab (`auto-context="false"`) und baut den Kontext hier —
 * mit denselben Schlüsselpaaren, die der Detektor auf der echten Seite bildet.
 *
 * Angeboten werden nur die drei Seitentypen, auf die das Backend proaktiv
 * reagiert: `_GREETABLE_KINDS = ("collection", "content", "topic")` in
 * `graph/nodes/context_greeting.py:47`. `subject` und `search` kennt der
 * Prompt-Block zwar, aber sie lösen weder Begrüßung noch Pills aus — sie hier
 * anzubieten hieße, eine Wirkung zu versprechen, die ausbleibt.
 */

export interface PreviewContextKind {
  readonly id: string;
  /** Der Schlüssel im Seitenkontext; leer beim Typ „kein Kontext". */
  readonly field: string;
  /**
   * Katalog-Schlüssel der Auswahl-Beschriftung.
   *
   * Der Schlüssel, nicht der Text (C1-d3b): eine fertige Zeichenkette auf
   * Modulebene friert in der Sprache ein, die beim Laden des Moduls galt.
   * Und ausgeschrieben statt `'preview.kind.' + id` zusammengesetzt — eine
   * Erlaubnisliste wie `SWITCH_LABEL_KEY`: ein zur Laufzeit gebauter Schlüssel
   * gäbe bei einem neuen Seitentyp den Schlüssel selbst als Beschriftung aus.
   */
  readonly labelKey: string;
  /** Katalog-Schlüssel der Feld-Beschriftung; leer beim Typ „kein Kontext". */
  readonly fieldLabelKey: string;
  /** Beispiel im Feld — Form, nicht Inhalt (kein echter Datensatz). */
  readonly example: string;
}

export const PREVIEW_CONTEXT_KINDS: readonly PreviewContextKind[] = [
  {
    id: 'kein', field: '',
    labelKey: 'preview.kind.kein', fieldLabelKey: '', example: '',
  },
  {
    id: 'topic', field: 'topic_page_slug',
    labelKey: 'preview.kind.topic', fieldLabelKey: 'preview.field.topic', example: 'eiszeit',
  },
  {
    id: 'collection', field: 'collection_id',
    labelKey: 'preview.kind.collection', fieldLabelKey: 'preview.field.collection',
    example: '00000000-0000-0000-0000-000000000000',
  },
  {
    id: 'content', field: 'node_id',
    labelKey: 'preview.kind.content', fieldLabelKey: 'preview.field.content',
    example: '00000000-0000-0000-0000-000000000000',
  },
];

/** Woher der Kontext stammt — macht Vorschau-Sitzungen in den Auswertungen
 *  unterscheidbar. Der Detektor schreibt an dieser Stelle `url:/themenseite`. */
const DETECTION_SOURCE = 'studio:vorschau';

/**
 * Der Seitenkontext für das Embed, oder `null` wenn keiner geschickt werden
 * soll. Ein `page_kind` ohne ID/Slug wäre ein halber Kontext: das Backend könnte
 * nichts auflösen, die Begrüßung bliebe aus, und die Vorschau sähe aus, als sei
 * die Konfiguration kaputt.
 */
export function buildPreviewContext(kindId: string, value: string): Record<string, string> | null {
  const kind = PREVIEW_CONTEXT_KINDS.find((k) => k.id === kindId);
  const trimmed = value.trim();
  if (!kind?.field || !trimmed) return null;
  return { page_kind: kind.id, [kind.field]: trimmed, detection_source: DETECTION_SOURCE };
}
