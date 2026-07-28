/**
 * What a load-test profile will actually be when the backend has had it (9-5e).
 *
 * The backend does not just accept or reject: `validate_profile`
 * (`backend/src/boerdi/services/loadtest.py`) silently CLAMPS — stages above 32
 * come down, everything past the sixth stage is dropped, requests per stage cap
 * at 60. ALT showed the typed numbers and the total computed from them, so
 * "1, 2, 4, 8, 16, 32, 64" promised 7 stages and 448 requests while the run did
 * 6 stages and 200. Since every request is a real LLM call, the form has to say
 * what will happen, not what was typed.
 *
 * The four caps are mirrored here on purpose and named with their source. There
 * is no endpoint that publishes them; a copy that says where it came from beats
 * a number in a sentence, which is what ALT had.
 */

export const MAX_STAGES = 6;
export const MAX_CONCURRENCY = 32;
export const MAX_REQUESTS_PER_STAGE = 60;
export const MAX_TOTAL_REQUESTS = 200;
export const MIN_THRESHOLD_S = 1;
export const MAX_THRESHOLD_S = 120;

export interface ProfileDraft {
  /** Free text, as typed: "1, 2, 4, 8". */
  readonly stagesText: string;
  readonly requestsPerStage: number;
  readonly thresholdS: number;
  readonly mix: Readonly<Record<string, number>>;
}

export interface EffectiveProfile {
  readonly stages: readonly number[];
  readonly requestsPerStage: number;
  readonly thresholdS: number;
  readonly mix: Record<string, number>;
  readonly totalRequests: number;
  /** Empty when the backend would accept this; otherwise why it would not. */
  readonly problem: string;
  /** What the backend would change without saying so. */
  readonly adjustments: readonly string[];
}

/** Comma-separated concurrencies; anything that is not a positive number is dropped. */
export function parseStages(text: string): number[] {
  return text
    .split(',')
    .map((part) => Number.parseInt(part.trim(), 10))
    .filter((n) => Number.isFinite(n) && n > 0);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function effectiveProfile(draft: ProfileDraft): EffectiveProfile {
  const adjustments: string[] = [];
  const parsed = parseStages(draft.stagesText);

  const kept = parsed.slice(0, MAX_STAGES);
  if (parsed.length > MAX_STAGES) {
    adjustments.push(`Nur die ersten ${MAX_STAGES} Stufen laufen.`);
  }
  const stages = kept.map((s) => clamp(s, 1, MAX_CONCURRENCY));
  if (kept.some((s) => s > MAX_CONCURRENCY)) {
    adjustments.push(`Parallelität ist bei ${MAX_CONCURRENCY} gedeckelt.`);
  }

  const rpsRaw = Number.isFinite(draft.requestsPerStage) ? draft.requestsPerStage : 0;
  const requestsPerStage = clamp(Math.trunc(rpsRaw) || 1, 1, MAX_REQUESTS_PER_STAGE);
  if (rpsRaw > MAX_REQUESTS_PER_STAGE) {
    adjustments.push(`Höchstens ${MAX_REQUESTS_PER_STAGE} Requests pro Stufe.`);
  }

  const thrRaw = Number.isFinite(draft.thresholdS) ? draft.thresholdS : 0;
  const thresholdS = clamp(thrRaw || MIN_THRESHOLD_S, MIN_THRESHOLD_S, MAX_THRESHOLD_S);

  const mix: Record<string, number> = {};
  for (const [key, weight] of Object.entries(draft.mix)) {
    const w = clamp(Math.trunc(Number.isFinite(weight) ? weight : 0), 0, 10);
    if (w > 0) mix[key] = w;
  }

  const totalRequests = stages.length * requestsPerStage;

  return {
    stages, requestsPerStage, thresholdS, mix, totalRequests,
    adjustments,
    problem: problemWith(stages, totalRequests, mix),
  };
}

/** The three things `validate_profile` refuses outright, in its own words. */
function problemWith(
  stages: readonly number[], totalRequests: number, mix: Record<string, number>,
): string {
  if (stages.length === 0) {
    return 'Mindestens eine Stufe nötig — z. B. „1, 2, 4".';
  }
  if (totalRequests > MAX_TOTAL_REQUESTS) {
    return `Profil zu groß: ${totalRequests} Requests gesamt (Limit ${MAX_TOTAL_REQUESTS}). `
      + 'Stufenzahl oder Requests pro Stufe reduzieren.';
  }
  if (Object.keys(mix).length === 0) {
    return 'Der Mix darf nicht leer sein — mindestens eine Kategorie braucht ein Gewicht.';
  }
  return '';
}
