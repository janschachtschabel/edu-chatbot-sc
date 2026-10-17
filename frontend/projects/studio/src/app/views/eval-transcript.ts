/**
 * Ein gespeichertes Gespräch eines Eval-Laufs, so weit das Studio es liest.
 *
 * Zwei Leser: das Lauf-Detail zeigt bei Läufen ohne Gold-Metriken den Verlauf,
 * die Zug-Tabelle eines Gold-Laufs holt daraus die Bot-Antwort eines Zugs.
 */

/** One turn of a persisted conversation, as much of it as this view reads. */
export interface TranscriptTurn {
  readonly user?: string;
  readonly bot?: string;
  readonly error?: string;
  readonly judge?: { readonly total?: number; readonly notes?: string };
}

export interface TranscriptConv {
  readonly flow_id?: string;
  readonly title?: string;
  readonly persona_id?: string;
  readonly intent_id?: string;
  readonly turns?: readonly TranscriptTurn[];
}
