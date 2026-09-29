/**
 * Die Spur eines Zugs, gelesen (ST-8a).
 *
 * `turn_persist` legt sie seit AG-1 in den Debug-Block jeder Antwort: je Runde
 * der Agent-Schleife eine Zeile `agent_round` (`services/agent_trace.py`), zum
 * Schluss `agent_stop`, und seit AG-5 in jeder Maschine `skill` für die
 * Anleitung, die der Zug geholt hat. Das Studio zeigte davon bis ST-8 nichts.
 *
 * **Jedes Feld wird geprüft statt vertraut.** Der Block ist gespeichertes JSON
 * aus allen Ständen seit P7. Eine Zeile ohne `data` oder ein Text, wo eine Zahl
 * stehen sollte, wird zu null Token und keinem Werkzeug — nie zu einer
 * erfundenen Zahl und nie zu einer Ausnahme, die den ganzen Verlauf leert.
 *
 * Reine Logik, ohne DOM prüfbar — dieselbe Trennung wie `pattern-panels.ts`.
 */
import type { Translate } from '../i18n/studio-language.service';

export interface TraceCall {
  readonly name: string;
  /** Nur die Namen: die Werte speichert der Server nicht (Nutzerinhalt). */
  readonly args: readonly string[];
}

export interface TraceRound {
  readonly round: number;
  readonly tools: readonly TraceCall[];
  readonly durationMs: number;
  readonly promptTokens: number;
  readonly cachedTokens: number;
  readonly completionTokens: number;
}

export interface TraceStop {
  readonly reason: string;
  readonly rounds: number;
  readonly durationMs: number;
}

export interface TraceSkill {
  readonly title: string;
  readonly nodeId: string;
}

export interface TurnTrace {
  readonly rounds: readonly TraceRound[];
  readonly stop: TraceStop | null;
  readonly skills: readonly TraceSkill[];
}

export interface TurnTokens {
  readonly prompt: number;
  /** Davon aus dem Cache — in `prompt` enthalten, nicht zusätzlich. */
  readonly cached: number;
  readonly completion: number;
}

type Row = Readonly<Record<string, unknown>>;

function isRow(value: unknown): value is Row {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Eine nicht-negative endliche Zahl, sonst 0. */
function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
}

function positiveInt(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function calls(value: unknown): TraceCall[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRow).flatMap((call) => {
    const name = text(call['name']);
    if (!name) return [];
    const args = Array.isArray(call['argumente'])
      ? call['argumente'].filter((arg): arg is string => typeof arg === 'string')
      : [];
    return [{ name, args }];
  });
}

function round(data: Row, entry: Row, position: number): TraceRound {
  return {
    round: positiveInt(data['runde']) ?? position,
    tools: calls(data['werkzeuge']),
    durationMs: count(data['dauer_ms'] ?? entry['duration_ms']),
    promptTokens: count(data['prompt_tokens']),
    cachedTokens: count(data['cached_tokens']),
    completionTokens: count(data['completion_tokens']),
  };
}

/** Runden, Ende und geholte Anleitungen aus `debug.trace`. */
export function readTrace(trace: unknown): TurnTrace {
  const rounds: TraceRound[] = [];
  const skills: TraceSkill[] = [];
  let stopEntry: { data: Row; entry: Row } | null = null;
  if (!Array.isArray(trace)) return { rounds, stop: null, skills };
  for (const entry of trace) {
    if (!isRow(entry)) continue;
    const data = isRow(entry['data']) ? entry['data'] : {};
    if (entry['step'] === 'agent_round') {
      rounds.push(round(data, entry, rounds.length + 1));
    } else if (entry['step'] === 'agent_stop') {
      stopEntry = { data, entry };
    } else if (entry['step'] === 'skill') {
      const nodeId = text(data['node_id']);
      if (nodeId) skills.push({ title: text(data['titel']) || nodeId, nodeId });
    }
  }
  const stop = stopEntry && {
    reason: text(stopEntry.data['stop_reason']),
    // Fehlt die Zahl, zählen die Runden-Zeilen — die stehen ja da.
    rounds: positiveInt(stopEntry.data['runden']) ?? rounds.length,
    durationMs: count(stopEntry.entry['duration_ms']),
  };
  return { rounds, stop, skills };
}

/** Die Token des ganzen Zugs aus `debug.token_usage` — `null`, wo nichts gebucht wurde. */
export function readTokens(usage: unknown): TurnTokens | null {
  if (!isRow(usage)) return null;
  const tokens = {
    prompt: count(usage['prompt_tokens']),
    cached: count(usage['cached_tokens']),
    completion: count(usage['completion_tokens']),
  };
  return tokens.prompt + tokens.completion > 0 ? tokens : null;
}

/**
 * Die Ende-Gründe von `agent_loop` plus der Schutz-Stopp des Auftrags-Endpunkts.
 * Eine `Map`, damit ein Grund wie `toString` nicht den Objekt-Prototyp trifft.
 */
const STOP_KEYS: ReadonlyMap<string, string> = new Map([
  ['text', 'trace.stop.text'],
  ['submit', 'trace.stop.submit'],
  ['deadline', 'trace.stop.deadline'],
  ['token_budget', 'trace.stop.token_budget'],
  ['max_iterations', 'trace.stop.max_iterations'],
  ['no_progress', 'trace.stop.no_progress'],
  ['empty', 'trace.stop.empty'],
  ['error', 'trace.stop.error'],
  ['safety', 'trace.stop.safety'],
]);

/** Erlaubnisliste wie `engineLabel`: ein unbekannter Grund kommt roh durch. */
export function stopReasonLabel(reason: string, t: Translate): string {
  const key = STOP_KEYS.get(reason);
  return key ? t(key) : reason;
}
