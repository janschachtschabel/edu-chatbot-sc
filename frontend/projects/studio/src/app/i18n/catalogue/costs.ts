/**
 * Die Kostenschau (K5) — Zeitraum, Summenband, Betrag, zwei Tabellen.
 *
 * **Zwei Beschriftungen tragen Fachwissen, nicht nur einen Namen.** OpenAI
 * zählt `cached_tokens` INNERHALB von `prompt_tokens` und `reasoning_tokens`
 * INNERHALB von `completion_tokens`. Wer sie addiert, zahlt doppelt — deshalb
 * heissen die beiden Spalten „davon Cache" und „davon Reasoning" und nicht
 * bloss „Cache" und „Reasoning". Dieselbe Falle benennt der Plan als die
 * häufigste; sie am Bildschirm zu entschärfen kostet zwei Wörter.
 *
 * **`costs.amount.partial` ist Pflicht, keine Zierde.** Der Betrag deckt nur
 * die bepreisten Modelle. Stünde er allein, läse sich eine Teilsumme als
 * Gesamtsumme — und zwar umso überzeugender, je gepflegter die Tafel wirkt.
 *
 * Was NICHT hier steht: „Aktualisieren"/„Wird geladen …" (`action.refresh*` in
 * `shared.ts`), der Zustands-Streifen (`async.*` ebenda) und der Name der
 * Ansicht selbst (`view.kosten.label` in `views.ts`, wo ihn auch die
 * Navigation liest).
 */
import type { CataloguePart } from './catalogue-part';

export const COSTS: CataloguePart = {
  de: {
    'costs.intro':
      'Was der Bot in einem Zeitraum verbraucht hat: Token getrennt nach Eingabe, '
      + 'Cache, Ausgabe und Reasoning, dazu der Betrag nach der gepflegten '
      + 'Preistafel.',

    // ── Zeitraum ────────────────────────────────────────────────────
    'costs.period.legend': 'Zeitraum',
    'costs.from.label': 'Von',
    'costs.to.label': 'Bis',
    /** Beide Grenzen zählen mit — ohne den Satz läse man „bis 11.08." als
     *  „bis zum Beginn des 11.08." und wunderte sich über den fehlenden Tag. */
    'costs.period.hint': 'Beide Tage zählen vollständig mit.',

    // ── Betrag ──────────────────────────────────────────────────────
    'costs.amount.label': 'Betrag',
    'costs.amount.none': 'Für kein Modell ist ein Preis gepflegt.',
    /** Anderer Grund als `none`, gleiche Folge. Ohne den Unterschied pflegt
     *  die Redaktion nach einem Tippfehler nach und wundert sich. */
    'costs.amount.broken': 'Die Preistafel ist nicht lesbar und wird ignoriert.',
    'costs.amount.partial': 'Teilsumme — ohne {models}',
    'costs.amount.where':
      'Preise pflegst du unter *Alle Bereiche* im Bereich `01-base/pricing`, '
      + 'je Million Token.',

    // ── Summenband ──────────────────────────────────────────────────
    'costs.band.prompt': 'Eingabe',
    'costs.band.cached': 'davon Cache',
    'costs.band.completion': 'Ausgabe',
    'costs.band.reasoning': 'davon Reasoning',
    'costs.band.calls': 'LLM-Aufrufe',

    // ── Tabellen ────────────────────────────────────────────────────
    'costs.models.caption': 'Je Modell',
    'costs.sessions.caption': 'Teuerste Sitzungen des Zeitraums',
    /** Ohne gepflegte Preise ordnet die Liste nach Token — sonst wäre sie
     *  beim ersten Blick auf eine frische Anlage unsortiert. */
    'costs.sessions.hint':
      'Ohne gepflegte Preise nach Token geordnet, nicht nach Betrag.',
    'costs.col.model': 'Modell',
    'costs.col.session': 'Sitzung',
    'costs.col.calls': 'Aufrufe',
    'costs.col.prompt': 'Eingabe',
    'costs.col.cached': 'davon Cache',
    'costs.col.completion': 'Ausgabe',
    'costs.col.reasoning': 'davon Reasoning',
    'costs.col.amount': 'Betrag',
    /** Eine Zelle ohne Preis. Ein leeres Feld läse sich als Anzeigefehler. */
    'costs.noPrice': 'kein Preis',

    'costs.empty':
      'In diesem Zeitraum wurde kein Modell aufgerufen. Zahlen entstehen mit dem '
      + 'ersten Chat-Zug.',
  },

  en: {
    'costs.intro':
      'What the bot consumed in a period: tokens split into input, cache, output '
      + 'and reasoning, plus the amount from the maintained price table.',

    'costs.period.legend': 'Period',
    'costs.from.label': 'From',
    'costs.to.label': 'To',
    'costs.period.hint': 'Both days count in full.',

    'costs.amount.label': 'Amount',
    'costs.amount.none': 'No model has a maintained price.',
    'costs.amount.broken': 'The price table is unreadable and is being ignored.',
    'costs.amount.partial': 'Partial sum — without {models}',
    'costs.amount.where':
      'Prices are maintained under *All areas* in the `01-base/pricing` area, '
      + 'per million tokens.',

    'costs.band.prompt': 'Input',
    'costs.band.cached': 'of which cached',
    'costs.band.completion': 'Output',
    'costs.band.reasoning': 'of which reasoning',
    'costs.band.calls': 'LLM calls',

    'costs.models.caption': 'By model',
    'costs.sessions.caption': 'Most expensive sessions of the period',
    'costs.sessions.hint':
      'Ordered by tokens rather than amount while no prices are maintained.',
    'costs.col.model': 'Model',
    'costs.col.session': 'Session',
    'costs.col.calls': 'Calls',
    'costs.col.prompt': 'Input',
    'costs.col.cached': 'of which cached',
    'costs.col.completion': 'Output',
    'costs.col.reasoning': 'of which reasoning',
    'costs.col.amount': 'Amount',
    'costs.noPrice': 'no price',

    'costs.empty':
      'No model was called in this period. Numbers appear with the first chat turn.',
  },
};
