/**
 * German names for the safety pipeline's own vocabulary (9-5b).
 *
 * Shared by the list and the detail panel, because a risk level that reads
 * "Hoch" in one and "high" in the other is two bugs waiting to be reported as
 * one. Both maps fall back to the raw key: the backend appends mapped legal
 * categories (`safety/service.py:113`) that this list cannot enumerate, and an
 * unknown key shown verbatim beats an empty cell.
 */

const RISK_LABELS: Record<string, string> = {
  low: 'Niedrig',
  medium: 'Mittel',
  high: 'Hoch',
};

const LEGAL_LABELS: Record<string, string> = {
  strafrecht: 'Strafrecht',
  jugendschutz: 'Jugendschutz',
  persoenlichkeitsrechte: 'Persönlichkeitsrechte',
  datenschutz: 'Datenschutz',
};

export function riskLabel(level: string): string {
  return RISK_LABELS[level] ?? level;
}

export function legalLabel(flag: string): string {
  return LEGAL_LABELS[flag] ?? flag;
}

export function legalLabels(flags: readonly string[], separator = ', '): string {
  return flags.map(legalLabel).join(separator);
}
