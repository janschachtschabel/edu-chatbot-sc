/**
 * Der Arbeitsbereich des Studios (Paket 13 E2, Paket 14): Umschalter im Kopf und der Hinweis auf
 * einer Seite des anderen Arbeitsbereichs.
 *
 * Die Maschinen heißen kurz (`ansicht.*`) — im Umschalter der Kopfzeile wie im Hinweis auf einer
 * Seite des anderen Arbeitsbereichs; die langen Namen (`effect.engine.*`) tragen die Plaketten.
 */
import type { CataloguePart } from './catalogue-part';

export const ANSICHT: CataloguePart = {
  de: {
    'ansicht.legend': 'Arbeitsbereich',
    'ansicht.agent': 'Agent',
    'ansicht.pattern': 'Muster',
    'ansicht.hint':
      'Zeigt die Seiten des gewählten Betriebsmodus und die gemeinsamen. Auf einer Seite des '
      + 'bisherigen Arbeitsbereichs führt der Wechsel zu dessen Startseite.',
    'arbeitsbereich.fremd': 'Diese Seite gehört zum Arbeitsbereich „{bereich}“.',
    'arbeitsbereich.wechseln': 'Zum Arbeitsbereich „{bereich}“ wechseln',
  },
  en: {
    'ansicht.legend': 'Workspace',
    'ansicht.agent': 'Agent',
    'ansicht.pattern': 'Patterns',
    'ansicht.hint':
      'Shows the pages of the chosen operating mode and the shared ones. On a page of the '
      + 'previous workspace, switching leads to its start page.',
    'arbeitsbereich.fremd': 'This page belongs to the “{bereich}” workspace.',
    'arbeitsbereich.wechseln': 'Switch to the “{bereich}” workspace',
  },
};
