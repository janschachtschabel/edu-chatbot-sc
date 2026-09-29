/**
 * Die Maschine eines Eval-Laufs, beschriftet (ST-7a).
 *
 * Eigenes Modul, weil Liste, Verlauf, Detail und Vergleich dieselbe Abbildung
 * brauchen — wie `eval-status.ts` für den Status. Die Maschinen heißen wie am
 * Umschalter und in den Wirkungs-Hinweisen (`effect.engine.*`), damit das
 * Studio überall dieselben zwei Namen trägt.
 *
 * **Erlaubnisliste statt zusammengesetztem Schlüssel:** ein unbekannter Wert
 * des Backends kommt roh durch — sichtbar statt erfunden. `''` heißt, der Lauf
 * hat seine Maschine nie festgehalten (vor ST-7 mit Server-Vorgabe gestartet).
 */
import type { Translate } from '../i18n/studio-language.service';

const ENGINE_KEYS: Readonly<Record<string, string>> = {
  pattern: 'effect.engine.pattern',
  agent: 'effect.engine.agent',
  // Nur in Läufen vor K1-1 (2026-09-27), etwa der K0-Messung.
  hybrid: 'evalEngine.hybrid',
  '': 'evalEngine.unknown',
};

export function engineLabel(engine: string, t: Translate): string {
  const key = ENGINE_KEYS[engine];
  return key ? t(key) : engine;
}
