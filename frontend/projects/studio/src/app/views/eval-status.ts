/**
 * Der Status eines Eval-Laufs, beschriftet (C1-d4b2).
 *
 * Eigenes Modul, weil ZWEI Ansichten dieselbe Abbildung brauchen: die Liste
 * (`eval-runs`) und das Detail (`eval-run-detail`). Bis C1-d4b2 trug jede ihre
 * eigene Kopie — dieselben vier Zeilen zweimal, und damit zwei Orte, an denen
 * ein neuer Backend-Status vergessen werden kann.
 *
 * **Erlaubnisliste statt zusammengesetztem Schlüssel.** `'evalRuns.status.' +
 * status` gäbe bei einem unbekannten Status den Schlüssel selbst als
 * Beschriftung aus; so kommt der rohe Wert durch — sichtbar statt erfunden.
 *
 * `completed` und `done` führen auf denselben Text: das Backend schreibt
 * beides, gemeint ist dasselbe.
 */
import type { Translate } from '../i18n/studio-language.service';

const STATUS_KEYS: Readonly<Record<string, string>> = {
  running: 'evalRuns.status.running',
  done: 'evalRuns.status.done',
  completed: 'evalRuns.status.done',
  failed: 'evalRuns.status.failed',
};

/** Beschriftung des Status, oder der rohe Wert — ein unbekannter Status muss
 *  sichtbar bleiben. */
export function evalStatusLabel(status: string, t: Translate): string {
  const key = STATUS_KEYS[status];
  return key ? t(key) : status;
}
