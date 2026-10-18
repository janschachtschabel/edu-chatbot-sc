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
  /** Judge v1: `total` 0–1 und `notes`. Seit Paket 13 (Judge v2) zusätzlich die Zug-Skalen
   *  als Zahlen 1–5, `gesamt` und `notiz` — `total`/`notes` bleiben für ältere Leser. */
  readonly judge?: {
    readonly total?: number; readonly notes?: string;
    readonly gesamt?: number; readonly notiz?: string;
    readonly anliegen?: number; readonly angebot?: number;
    readonly qualitaet?: number; readonly ton?: number;
  };
  readonly judge_failed?: string;
  /** Paket 13 (B): der Anwendungsfall dieses Zugs aus dem Golden-Ablauf. */
  readonly anwendungsfall?: string;
  readonly latency_ms?: number;
  readonly golden?: { readonly checks?: Readonly<Record<string, boolean>> };
  readonly debug?: {
    readonly tools_called?: readonly string[];
    readonly token_usage?: { readonly zeiten_ms?: Readonly<Record<string, number>> };
  };
}

export interface TranscriptConv {
  readonly flow_id?: string;
  readonly title?: string;
  readonly persona_id?: string;
  readonly intent_id?: string;
  /** Paket 13: die Zielgruppe des Golden-Ablaufs. */
  readonly zielgruppe?: string;
  readonly turns?: readonly TranscriptTurn[];
}
