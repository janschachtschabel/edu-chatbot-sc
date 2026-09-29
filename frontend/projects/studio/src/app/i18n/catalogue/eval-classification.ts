/**
 * Die Muster-Tafeln im Lauf-Detail (ST-7d): Kennzahlen, Konfusionsmatrizen und
 * Werkzeugtreue je Muster aus `summary.classification_metrics`.
 *
 * Die Kennzahlen heißen wie im ALT (Persona-, Intent-, Muster-Trefferquote,
 * Werkzeugtreue) und sind alle Quoten, damit sie nebeneinander vergleichbar
 * bleiben.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_CLASSIFICATION: CataloguePart = {
  de: {
    'evalClass.title': 'Muster-Tafeln: Kennzahlen, Konfusionsmatrizen, Werkzeugtreue',
    'evalClass.hint':
      'Wie die Muster-Maschine klassifiziert und Muster wählt. Persona und Intent zählen '
      + 'nur, wo der Lauf ein Soll vorgibt — Gold-Flows v2 tun das nicht.',
    /** Treffer = der Judge nennt das Muster mindestens passend (1 von 2). */
    'evalClass.kpi.pattern': 'Muster-Trefferquote',
    'evalClass.kpi.hint': 'Hinweis = Endwahl',
    'evalClass.kpi.tools': 'Werkzeugtreue',
    'evalClass.kpi.persona': 'Persona-Trefferquote',
    'evalClass.kpi.intent': 'Intent-Trefferquote',
    'evalClass.notMeasured': 'nicht gemessen',
    'evalClass.value.one': '{rate} ({count} Zug)',
    'evalClass.value.other': '{rate} ({count} Züge)',
    'evalClass.fullyFitting': 'davon voll passend: {rate}',
    'evalClass.matrix.persona': 'Persona — Soll (Zeile) × erkannt (Spalte)',
    'evalClass.matrix.intent': 'Intent — Soll (Zeile) × erkannt (Spalte)',
    'evalClass.matrix.pattern': 'Muster — LLM-Hinweis (Zeile) × Endwahl (Spalte)',
    'evalClass.corner.expected': 'Soll ↓ · erkannt →',
    'evalClass.corner.hint': 'Hinweis ↓ · Endwahl →',
    'evalClass.tools.caption':
      'Werkzeugtreue je Muster — rief der Zug die Werkzeuge, die das Muster verlangt?',
    'evalClass.tools.pattern': 'Muster',
    'evalClass.tools.ok': 'eingehalten',
    'evalClass.tools.rate': 'Quote',
  },
  en: {
    'evalClass.title': 'Pattern panels: key figures, confusion matrices, tool compliance',
    'evalClass.hint':
      'How the pattern engine classifies and picks patterns. Persona and intent only count '
      + 'where the run sets a target — gold flows v2 do not.',
    'evalClass.kpi.pattern': 'Pattern hit rate',
    'evalClass.kpi.hint': 'Hint = final choice',
    'evalClass.kpi.tools': 'Tool compliance',
    'evalClass.kpi.persona': 'Persona hit rate',
    'evalClass.kpi.intent': 'Intent hit rate',
    'evalClass.notMeasured': 'not measured',
    'evalClass.value.one': '{rate} ({count} turn)',
    'evalClass.value.other': '{rate} ({count} turns)',
    'evalClass.fullyFitting': 'fully fitting: {rate}',
    'evalClass.matrix.persona': 'Persona — target (row) × detected (column)',
    'evalClass.matrix.intent': 'Intent — target (row) × detected (column)',
    'evalClass.matrix.pattern': 'Pattern — LLM hint (row) × final choice (column)',
    'evalClass.corner.expected': 'target ↓ · detected →',
    'evalClass.corner.hint': 'hint ↓ · final →',
    'evalClass.tools.caption':
      'Tool compliance per pattern — did the turn call the tools the pattern requires?',
    'evalClass.tools.pattern': 'Pattern',
    'evalClass.tools.ok': 'complied',
    'evalClass.tools.rate': 'Rate',
  },
};
