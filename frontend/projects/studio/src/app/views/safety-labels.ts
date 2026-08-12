/**
 * Names for the safety pipeline's own vocabulary (9-5b), in the active language.
 *
 * Shared by the list and the detail panel, because a risk level that reads
 * "Hoch" in one and "high" in the other is two bugs waiting to be reported as
 * one. Both maps fall back to the raw key: the backend appends mapped legal
 * categories (`safety/service.py:113`) that this list cannot enumerate, and an
 * unknown key shown verbatim beats an empty cell.
 *
 * Der Übersetzer kommt als Parameter herein (C1-d4e3), wie bei `evalStatusLabel`
 * und `loadtestStatusLabel`: dieses Modul hat keinen Injector, und bis dahin
 * froren die beiden Karten die Sprache ein, die beim Laden des Moduls galt.
 */
import type { Translate } from '../i18n/studio-language.service';

const RISK_KEYS: Readonly<Record<string, string>> = {
  low: 'sfl.risk.low',
  medium: 'sfl.risk.medium',
  high: 'sfl.risk.high',
};

const LEGAL_KEYS: Readonly<Record<string, string>> = {
  strafrecht: 'sfl.legal.strafrecht',
  jugendschutz: 'sfl.legal.jugendschutz',
  persoenlichkeitsrechte: 'sfl.legal.persoenlichkeitsrechte',
  datenschutz: 'sfl.legal.datenschutz',
};

export function riskLabel(level: string, t: Translate): string {
  const key = RISK_KEYS[level];
  return key ? t(key) : level;
}

export function legalLabel(flag: string, t: Translate): string {
  const key = LEGAL_KEYS[flag];
  return key ? t(key) : flag;
}

export function legalLabels(
  flags: readonly string[], t: Translate, separator = ', ',
): string {
  return flags.map((flag) => legalLabel(flag, t)).join(separator);
}
