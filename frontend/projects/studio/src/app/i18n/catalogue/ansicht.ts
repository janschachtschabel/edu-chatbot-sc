/**
 * Der Arbeitsbereich des Studios (Paket 13 E2, Paket 14): Umschalter im Kopf und der Hinweis auf
 * einer Seite des anderen Arbeitsbereichs.
 *
 * Die Maschinen heißen kurz — der Umschalter steht in der Kopfzeile; die langen Namen
 * (`effect.engine.*`) stehen im Hinweis.
 */
import type { CataloguePart } from './catalogue-part';

export const ANSICHT: CataloguePart = {
  de: {
    'ansicht.legend': 'Arbeitsbereich',
    'ansicht.agent': 'Agent',
    'ansicht.pattern': 'Muster',
    'ansicht.hint': 'Zeigt die Seiten des gewählten Betriebsmodus und die gemeinsamen.',
    'arbeitsbereich.fremd': 'Diese Seite gehört zum Arbeitsbereich „{bereich}“.',
    'arbeitsbereich.wechseln': 'Zum Arbeitsbereich „{bereich}“ wechseln',
  },
  en: {
    'ansicht.legend': 'Workspace',
    'ansicht.agent': 'Agent',
    'ansicht.pattern': 'Patterns',
    'ansicht.hint': 'Shows the pages of the chosen operating mode and the shared ones.',
    'arbeitsbereich.fremd': 'This page belongs to the “{bereich}” workspace.',
    'arbeitsbereich.wechseln': 'Switch to the “{bereich}” workspace',
  },
};
