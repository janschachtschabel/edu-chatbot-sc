/**
 * Aus den Formularfeldern der Agent-Ansicht wird ein `AgentRequest`.
 *
 * Reine Logik, von der Ansicht getrennt — dieselbe Trennung wie bei
 * `preview-embed.ts`: was hier passiert, ist prüfbar, ohne ein DOM zu bauen,
 * und es ist die Stelle, an der ein Fehler dem Nutzer VOR dem Absenden gesagt
 * wird statt als 422 danach.
 *
 * Die Prüfungen spiegeln `backend/src/boerdi/api/schemas_agent.py`. Sie
 * ersetzen sie nicht — der Server prüft ohnehin nochmal, und er hat recht.
 * Sie sparen dem Nutzer nur den Umweg über eine Fehlermeldung, die von seiner
 * Anweisung handelt, obwohl es um ein Formularfeld geht.
 */

/** `MAX_NODE_IDS` in `schemas_agent.py` — die Obergrenze von `get_nodes_details`. */
export const MAX_NODE_IDS = 50;

/** Die Felder, wie die Ansicht sie hält — Text, ausser dem einen Haken. */
export interface AgentFormValues {
  readonly instruction: string;
  readonly collectionId: string;
  readonly nodeIds: string;
  readonly resultSchema: string;
  readonly writeMode: string;
  readonly locale: string;
  /** `allow_curation`; im Backend `True`, also hier gesetzt = Vorgabe. */
  readonly allowCuration: boolean;
}

/** Der Rumpf, den `POST /api/agent` erwartet. */
export interface AgentRequestBody {
  readonly instruction: string;
  readonly collection_id?: string;
  readonly node_ids?: readonly string[];
  readonly result_schema?: Record<string, unknown>;
  readonly write_mode?: string;
  readonly locale?: string;
  readonly allow_curation?: boolean;
}

export interface BuiltRequest {
  readonly request: AgentRequestBody | null;
  /** Katalog-Schlüssel der Meldung; `null` wenn alles passt. */
  readonly error: string | null;
}

/**
 * Knoten-IDs aus einem Textfeld.
 *
 * Zeilen, Kommas und Leerzeichen gelten alle als Trenner: wer IDs aus einer
 * Tabelle oder aus edu-sharing kopiert, bekommt mal das eine, mal das andere.
 * Doubletten fallen weg (sie kosteten je einen Abruf), die Reihenfolge bleibt.
 */
export function parseNodeIds(roh: string): readonly string[] {
  const gesehen = new Set<string>();
  for (const teil of roh.split(/[\s,]+/)) {
    if (teil) gesehen.add(teil);
  }
  return [...gesehen];
}

function parseSchema(roh: string): Record<string, unknown> | 'invalid' {
  try {
    const gelesen: unknown = JSON.parse(roh);
    // Ein Objekt, nicht irgendein JSON: `result_schema` ist im Backend ein
    // dict. Eine Liste parst sauber und wäre trotzdem falsch.
    if (!gelesen || typeof gelesen !== 'object' || Array.isArray(gelesen)) return 'invalid';
    return gelesen as Record<string, unknown>;
  } catch {
    return 'invalid';
  }
}

/**
 * Der Rumpf für einen Lauf — oder die Meldung, warum es keinen gibt.
 *
 * Leere Felder werden WEGGELASSEN statt als `""` geschickt: `collection_id: ""`
 * liesse das Backend eine Sammlung mit leerer ID auflösen wollen, und
 * `write_mode: ""` fiele durch die Literal-Prüfung.
 */
export function buildAgentRequest(werte: AgentFormValues): BuiltRequest {
  const instruction = werte.instruction.trim();
  if (!instruction) return { request: null, error: 'agent.error.instruction' };

  const request: Record<string, unknown> = { instruction };

  const collection = werte.collectionId.trim();
  if (collection) request.collection_id = collection;

  const nodes = parseNodeIds(werte.nodeIds);
  if (nodes.length > MAX_NODE_IDS) {
    return { request: null, error: 'agent.error.tooManyNodes' };
  }
  if (nodes.length > 0) request.node_ids = nodes;

  const schemaRoh = werte.resultSchema.trim();
  if (schemaRoh) {
    const schema = parseSchema(schemaRoh);
    // Ein unlesbares Schema wird verweigert, NICHT weggelassen: der Lauf liefe
    // sonst, kostete Geld und lieferte kein strukturiertes Ergebnis — ohne dass
    // jemand den Grund sähe.
    if (schema === 'invalid') return { request: null, error: 'agent.error.schema' };
    request.result_schema = schema;
  }

  if (werte.writeMode) request.write_mode = werte.writeMode;
  if (werte.locale) request.locale = werte.locale;
  // Nur die ABWEICHUNG von der Vorgabe reist mit. `allow_curation: true`
  // mitzuschicken sagte nichts — und überstimmte still eine Vorgabe, falls sie
  // im Backend je auf `False` wechselt. Dieselbe Linie wie bei den leeren Feldern.
  if (!werte.allowCuration) request.allow_curation = false;

  return { request: request as unknown as AgentRequestBody, error: null };
}
