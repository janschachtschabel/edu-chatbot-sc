/**
 * Wirkung je Feld (Rundgang 3): „Wirkt in …“ galt je Bereich und stimmte an Abschnitten mit
 * Feld-Ausschnitt nicht. Die Ausnahmen kommen aus dem Backend (`FIELD_EFFECTS` in
 * `domain/area_effects.py`); hier wird nur zusammengefasst und gekennzeichnet.
 */
import type { AreaEffects, EffectLevel, Engine } from './effects-api.service';

type Wirkung = Readonly<Record<Engine, EffectLevel>>;

const ENGINES: readonly Engine[] = ['pattern', 'agent'];

/** Plakette an einem Feld, dessen Wirkung vom offenen Arbeitsbereich abweicht. */
export type FeldPlakette = 'nurMuster' | 'nurAgent' | 'nurKrise' | 'nurExtern' | 'ohneWirkung';

function feldWirkung(effects: AreaEffects, area: string, pfad: string): Wirkung | undefined {
  return effects.fields?.[area]?.[pfad];
}

/**
 * Die Wirkung eines Abschnitts: ohne Ausschnitt die des Bereichs; mit Ausschnitt die gemeinsame
 * der gezeigten Felder (ein Feld ohne Ausnahme zählt mit der des Bereichs), wo sie auseinander-
 * gehen „teilweise“. `null` ohne Zuordnung.
 */
export function abschnittsWirkung(
  effects: AreaEffects | null, area: string, felder: readonly string[] | undefined,
): Wirkung | null {
  const bereich = effects?.areas[area];
  if (!effects || !bereich) return null;
  if (!felder?.length) return bereich;
  const je = felder.map((pfad) => feldWirkung(effects, area, pfad) ?? bereich);
  return Object.fromEntries(ENGINES.map((engine) => {
    const stufen = new Set(je.map((w) => w[engine]));
    return [engine, stufen.size === 1 ? [...stufen][0] : 'teilweise'];
  })) as Record<Engine, EffectLevel>;
}

/** Die Plakette für genau diesen Pfad (nicht für seine Kinder), sonst `null`. */
export function feldPlakette(
  effects: AreaEffects | null, area: string, pfad: string, ansicht: Engine,
): FeldPlakette | null {
  const wirkung = effects ? feldWirkung(effects, area, pfad) : undefined;
  if (!wirkung) return null;
  if (wirkung.pattern === 'keine' && wirkung.agent === 'keine') return 'ohneWirkung';
  if (ansicht === 'pattern') {
    if (wirkung.pattern !== 'keine') return null;
    // Review A-2: „nur Agent“ wäre für den Krisentext falsch — der Chat im Agent-Modus
    // antwortet mit M01, den Text liest nur `/api/agent`.
    if (wirkung.agent === 'extern') return 'nurExtern';
    if (wirkung.agent === 'krise') return 'nurKrise';
    return 'nurAgent';
  }
  switch (wirkung.agent) {
    case 'keine': return 'nurMuster';
    case 'krise': return 'nurKrise';
    case 'extern': return 'nurExtern';
    default: return null;
  }
}
