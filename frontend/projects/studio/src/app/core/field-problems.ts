/**
 * Prüffehler des Servers, einer Stelle im Dokument zugeordnet (ST-2e).
 *
 * `PUT /api/config/data/{area}` antwortet auf ein Dokument, das das
 * Bereichsmodell nicht besteht, mit 422 und einer Liste `{loc, msg, type, ctx?}`
 * (`backend/src/boerdi/api/config.py`). Bis ST-2e klebte das Studio diese
 * Liste zu EINER englischen Zeile unter dem Formular zusammen, ohne Markierung
 * am Feld. Hier wird sie zu Einträgen mit Dokumentpfad, die das Formular an ihr
 * Feld hängt, und zu einem Satz in der Sprache des Studios.
 */
import type { Translate } from '../i18n/studio-language.service';

export interface FieldProblem {
  /** Pfad im Dokument, wie ihn auch `ValuePath` führt. */
  readonly path: readonly (string | number)[];
  /** pydantic-Fehlerart, etwa `greater_than_equal`. */
  readonly type: string;
  /** Die englische Meldung des Servers — Rückfall für unbekannte Arten. */
  readonly msg: string;
  /** Die Grenze oder die erwarteten Werte; nur einfache Werte. */
  readonly ctx: Readonly<Record<string, string | number | boolean>>;
}

/** Arten mit eigenem Satz im Katalog (`validation.<art>`); der Rest nennt den Server. */
const KNOWN = new Set([
  'greater_than_equal', 'less_than_equal', 'greater_than', 'less_than',
  'int_parsing', 'int_type', 'int_from_float', 'float_parsing', 'float_type',
  'string_type', 'bool_parsing', 'bool_type', 'literal_error', 'missing',
  'list_type', 'dict_type', 'model_type', 'string_pattern_mismatch',
]);

/** Grenzen, die als Zahl lokal formatiert werden („0,3" statt „0.3"). */
const NUMERIC_CTX = new Set(['ge', 'le', 'gt', 'lt']);

/**
 * Der Wert, ohne den ein Satz nicht stehen kann. Fehlt er in `ctx` — ein
 * Backend vor ST-2e schickt keins —, gilt die Meldung des Servers; sonst
 * stünde „Mindestens {ge}." am Feld (im Browser gefunden).
 */
const NEEDS: Readonly<Record<string, string>> = {
  greater_than_equal: 'ge', less_than_equal: 'le', greater_than: 'gt', less_than: 'lt',
  literal_error: 'expected',
};

/** Die Einträge einer 422-Antwort; was keiner ist, fällt still weg. */
export function parseProblems(detail: unknown): FieldProblem[] {
  if (!Array.isArray(detail)) return [];
  const out: FieldProblem[] = [];
  for (const entry of detail) {
    if (!entry || typeof entry !== 'object') continue;
    const { loc, msg, type, ctx } = entry as Record<string, unknown>;
    if (!Array.isArray(loc) || loc.length === 0) continue;
    const segments = loc.filter(
      (s): s is string | number => typeof s === 'string' || typeof s === 'number',
    );
    // Nur die Hülle einer Anfrageprüfung (`body.data.…`) fällt weg — ein
    // Markdown-Dokument hat einen ECHTEN Schlüssel `body`.
    const path = segments[0] === 'body' && segments[1] === 'data' ? segments.slice(2) : segments;
    out.push({
      path,
      type: typeof type === 'string' ? type : '',
      msg: typeof msg === 'string' ? msg : '',
      ctx: plainCtx(ctx),
    });
  }
  return out;
}

function plainCtx(raw: unknown): Record<string, string | number | boolean> {
  if (!raw || typeof raw !== 'object') return {};
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>).filter(
      (entry): entry is [string, string | number | boolean] =>
        ['string', 'number', 'boolean'].includes(typeof entry[1]),
    ),
  );
}

/** Der Vergleichsschlüssel eines Pfads — dieselbe Form an Formular und Fehler. */
export function pathKey(path: readonly (string | number)[]): string {
  return path.join('.');
}

/**
 * Ein Satz für die Person am Formular: „Mindestens 70." statt „Input should be
 * greater than or equal to 70". Unbekannte Arten nennen die Meldung des
 * Servers, statt sie zu verschweigen.
 */
export function describeProblem(
  problem: FieldProblem,
  t: Translate,
  number: (value: number) => string,
): string {
  const needed = NEEDS[problem.type];
  if (!KNOWN.has(problem.type) || (needed && !(needed in problem.ctx))) {
    return t('validation.other', { msg: problem.msg });
  }
  const params: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(problem.ctx)) {
    params[key] = NUMERIC_CTX.has(key) && typeof value === 'number' ? number(value) : String(value);
  }
  return t(`validation.${problem.type}`, params);
}
