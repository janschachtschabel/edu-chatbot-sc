/**
 * Der Reiter „Routing-Matrix" der Analyse (C1-d4d2).
 *
 * Eigener Teil, weil es ein eigenes Panel ist — die Regel, die C1-d4d1 gesetzt
 * hat. Mit `quality.ts` teilt er nur Lehnwörter, die ohnehin gleich lauten.
 *
 * **Was NICHT hier steht:** der Name des Panels. Überschrift des
 * Zustands-Streifens ist `qual.tab.matrix` aus der Hülle — dieselbe Sache, ein
 * Eintrag. Ebenso `action.refresh*` aus `shared.ts`.
 *
 * **`{scope}` bleibt der rohe Bezeichner** (`all`/`production`/`eval`), wie im
 * Bestand. Ihn auf `qual.scope.*` zu legen wäre eine Verbesserung, keine
 * Übersetzung — notiert als Nacharbeit, nicht hier eingebaut.
 */
import type { CataloguePart } from './catalogue-part';

export const QUALITY_MATRIX: CataloguePart = {
  de: {
    /** Die Anzahl wählt die Form, der formatierte Text füllt `{count}` —
     *  der Bestand gruppierte die Tausender, das bleibt so. */
    'qualMatrix.total.one': 'Aggregiert aus {count} Turn ({scope}).',
    'qualMatrix.total.other': 'Aggregiert aus {count} Turns ({scope}).',
    'qualMatrix.minSamples': 'Min-Samples pro Zelle',
    'qualMatrix.empty':
      'Keine Persona-Intent-Kombination erreicht die Schwelle von {count} Min-Samples. '
      + 'Senke die Schwelle oder sammle mehr Turns.',
    'qualMatrix.caption':
      'Gewinner-Pattern je Persona und Intent. Pro Zelle: das dominanteste Pattern, sein '
      + 'Anteil an der Zelle, die Zahl der Samples und — falls vorhanden — die '
      + 'konkurrierenden Patterns.',
    'qualMatrix.samples.one': '{count} Sample',
    'qualMatrix.samples.other': '{count} Samples',
    /** Anteil und Anzahl in einer Zeile — kein Wort darin, nur Trenner und
     *  Reihenfolge, wie `qual.diag.counts`. */
    'qualMatrix.cell': '{share} · {samples}',
    'qualMatrix.alt': 'auch: {list}',
    /** Nur für Screenreader: der Zeiger benennt die Aktion für die Maus, ein
     *  Screenreader braucht sie gesagt. */
    'qualMatrix.drill': 'Logs zu {id} anzeigen',
    'qualMatrix.noSamples': 'keine Samples',
    'qualMatrix.legend':
      'Ein kurzer Balken heißt: mehrere Patterns konkurrieren in dieser Zelle — die '
      + 'Zuordnung ist dort unsicher. „—" heißt: für diese Persona-Intent-Kombination '
      + 'liegen keine Samples vor, die Abdeckung hat dort eine Lücke.',
  },

  en: {
    'qualMatrix.total.one': 'Aggregated from {count} turn ({scope}).',
    'qualMatrix.total.other': 'Aggregated from {count} turns ({scope}).',
    'qualMatrix.minSamples': 'Min samples per cell',
    'qualMatrix.empty':
      'No persona-intent pair reaches the threshold of {count} min samples. Lower the '
      + 'threshold or collect more turns.',
    'qualMatrix.caption':
      'Winning pattern per persona and intent. Per cell: the most dominant pattern, its '
      + 'share of the cell, the number of samples and — where present — the competing '
      + 'patterns.',
    'qualMatrix.samples.one': '{count} sample',
    'qualMatrix.samples.other': '{count} samples',
    'qualMatrix.cell': '{share} · {samples}',
    'qualMatrix.alt': 'also: {list}',
    'qualMatrix.drill': 'Show logs for {id}',
    'qualMatrix.noSamples': 'no samples',
    'qualMatrix.legend':
      'A short bar means several patterns compete in this cell — the assignment is '
      + 'uncertain there. "—" means no samples exist for this persona-intent pair, so '
      + 'the coverage has a gap there.',
  },
};
