/**
 * Das Profil eines Eval-Laufs im Detail (ST-7b): Judge je Achse, Dauer, Token
 * und Kosten, Robustheit.
 *
 * Die Achsen heißen nach dem, was der Judge bewertet, nicht nach ihren
 * Schlüsseln (`auftrag_erfuellt` …) — die stehen im Judge-Prompt.
 *
 * Robustheit als „Name: Zahl": „1 Judge-Ausfälle" wäre falsch, und vier
 * Mehrzahl-Paare für eine Kennzahlenzeile stünden in keinem Verhältnis.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_PROFILE: CataloguePart = {
  de: {
    'evalProfile.title': 'Profil des Laufs',
    'evalProfile.hint':
      'Gerechnet wie im Maschinen-Vergleich; die Kosten nach der Preistafel unter „Kosten“.',
    'evalProfile.axesCaption': 'Judge je Achse (Mittelwert, Skala 0–2)',
    'evalProfile.col.axis': 'Achse',
    'evalProfile.col.value': 'Mittelwert',
    'evalProfile.axis.auftrag_erfuellt': 'Auftrag erfüllt',
    'evalProfile.axis.intent_fit': 'Passt zur Absicht',
    'evalProfile.axis.persona_tone': 'Ton für die Zielgruppe',
    'evalProfile.axis.info_quality': 'Informationsqualität',
    'evalProfile.axis.safety': 'Sicherheit',
    'evalProfile.axis.pattern_match': 'Muster passt',
    /** Ohne Wert: die Achse gab es in diesem Lauf nicht (Agent-Züge haben kein
     *  Muster, `auftrag_erfuellt` braucht ein Soll im Flow). */
    'evalProfile.notJudged': 'nicht bewertet',
    'evalProfile.weak': '{value} (schwach)',
    'evalProfile.speed': 'Dauer je Zug',
    'evalProfile.speedText':
      'p50 {p50} · p95 {p95} · {over30} über 30 s · {over90} über 90 s',
    'evalProfile.tokens': 'Token je Zug',
    'evalProfile.tokensText': '{prompt} Eingabe, davon {cached} gecacht · {completion} Ausgabe',
    'evalProfile.cost': 'Kosten',
    'evalProfile.costText': '{perTurn} je Zug · {total} gesamt',
    'evalProfile.noPrice':
      'Kein Preis gepflegt für {models} — die Kosten bleiben leer, bis die Preistafel '
      + 'unter „Kosten“ das Modell kennt.',
    'evalProfile.noPricing': 'Die Preistafel ist nicht lesbar — keine Kosten.',
    'evalProfile.robustness': 'Robustheit',
    'evalProfile.robustnessText':
      'Chat-Fehler: {errors} · Judge-Ausfälle: {judge} · leere Antworten: {empty} · '
      + 'Ersatzantworten: {fallback}',
    'evalProfile.robustnessNoJudge':
      'Chat-Fehler: {errors} · leere Antworten: {empty} · Ersatzantworten: {fallback}',
  },
  en: {
    'evalProfile.title': 'Run profile',
    'evalProfile.hint':
      'Computed as in the engine comparison; costs from the price table under “Costs”.',
    'evalProfile.axesCaption': 'Judge per axis (mean, scale 0–2)',
    'evalProfile.col.axis': 'Axis',
    'evalProfile.col.value': 'Mean',
    'evalProfile.axis.auftrag_erfuellt': 'Task fulfilled',
    'evalProfile.axis.intent_fit': 'Fits the intent',
    'evalProfile.axis.persona_tone': 'Tone for the audience',
    'evalProfile.axis.info_quality': 'Information quality',
    'evalProfile.axis.safety': 'Safety',
    'evalProfile.axis.pattern_match': 'Pattern fits',
    'evalProfile.notJudged': 'not judged',
    'evalProfile.weak': '{value} (weak)',
    'evalProfile.speed': 'Duration per turn',
    'evalProfile.speedText':
      'p50 {p50} · p95 {p95} · {over30} above 30 s · {over90} above 90 s',
    'evalProfile.tokens': 'Tokens per turn',
    'evalProfile.tokensText': '{prompt} input, {cached} of them cached · {completion} output',
    'evalProfile.cost': 'Cost',
    'evalProfile.costText': '{perTurn} per turn · {total} total',
    'evalProfile.noPrice':
      'No price maintained for {models} — costs stay empty until the price table under '
      + '“Costs” knows the model.',
    'evalProfile.noPricing': 'The price table is unreadable — no costs.',
    'evalProfile.robustness': 'Robustness',
    'evalProfile.robustnessText':
      'Chat errors: {errors} · Judge failures: {judge} · Empty answers: {empty} · '
      + 'Fallback answers: {fallback}',
    'evalProfile.robustnessNoJudge':
      'Chat errors: {errors} · Empty answers: {empty} · Fallback answers: {fallback}',
  },
};
