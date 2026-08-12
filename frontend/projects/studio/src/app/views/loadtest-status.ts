/**
 * Der Status eines Lasttest-Laufs, beschriftet (C1-d4e1).
 *
 * Eigenes Modul aus demselben Grund wie `eval-status.ts`: ZWEI Ansichten
 * brauchen dieselbe Abbildung — die Lauf-Liste (`loadtest`) und das Lauf-Panel
 * (`loadtest-run`). Bis hierher trug jede ihre eigene, wortgleiche Kopie.
 *
 * **Erlaubnisliste statt zusammengesetztem Schlüssel.** `'lt.status.' + status`
 * gäbe bei einem unbekannten Status den Schlüssel selbst als Beschriftung aus;
 * so kommt der rohe Wert durch — sichtbar statt erfunden. Genau das tat der
 * Bestand mit seinem `return status` am Ende, und das bleibt.
 */
import type { Translate } from '../i18n/studio-language.service';

const STATUS_KEYS: Readonly<Record<string, string>> = {
  running: 'lt.status.running',
  completed: 'lt.status.completed',
  failed: 'lt.status.failed',
};

/** Beschriftung des Status, oder der rohe Wert — ein unbekannter Status muss
 *  sichtbar bleiben. */
export function loadtestStatusLabel(status: string, t: Translate): string {
  const key = STATUS_KEYS[status];
  return key ? t(key) : status;
}
