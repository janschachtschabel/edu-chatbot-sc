/**
 * Wo ein Bereich wirkt (ST-5): der Hinweis im Kopf jedes Abschnitts und das
 * Banner einer Seite, die die Vorgabe-Maschine nicht nutzt.
 *
 * Die Maschinen heißen wie beim Umschalter (`feld.EngineArea.mode.wahl.*`),
 * damit Seite und Formular dieselben Namen tragen.
 */
import type { CataloguePart } from './catalogue-part';

export const EFFECTS: CataloguePart = {
  de: {
    'effect.label': 'Wirkt in',
    'effect.engine.pattern': 'Muster-Maschine',
    'effect.engine.agent': 'Agent-Schleife',
    'effect.partial': '{engine} (teilweise)',
    'effect.crisisOnly': '{engine} (nur Krisen-Züge)',
    'effect.nowhere': 'Wirkt derzeit in keiner Maschine',
    'effect.bannerCrisis':
      'Die Vorgabe-Maschine ist die {engine} — dort wirken die Einstellungen dieser Seite nur '
      + 'bei Krisen- und Drohungs-Zügen; die beantwortet immer die {other}.',
    'effect.banner':
      'Die Vorgabe-Maschine ist die {engine} — dort wirkt keine Einstellung dieser Seite. '
      + 'Sie gelten nur, wenn eine Einbettung die {other} wählt.',
    'effect.bannerNowhere': 'Die Einstellungen dieser Seite wirken derzeit in keiner Maschine.',
  },
  en: {
    'effect.label': 'Takes effect in',
    'effect.engine.pattern': 'Pattern engine',
    'effect.engine.agent': 'Agent loop',
    'effect.partial': '{engine} (partly)',
    'effect.crisisOnly': '{engine} (crisis turns only)',
    'effect.nowhere': 'Currently takes effect in neither engine',
    'effect.bannerCrisis':
      'The default engine is the {engine} — this page’s settings only take effect there on '
      + 'crisis and threat turns, which the {other} always answers.',
    'effect.banner':
      'The default engine is the {engine} — none of this page’s settings take effect there. '
      + 'They only apply when an embedding chooses the {other}.',
    'effect.bannerNowhere': 'The settings on this page currently take effect in neither engine.',
  },
};
