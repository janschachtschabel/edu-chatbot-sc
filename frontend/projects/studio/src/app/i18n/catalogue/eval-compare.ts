/**
 * Läufe vergleichen (ST-7c): die Auswahl in der Lauf-Liste und die
 * Vergleichstafel.
 *
 * Die Zeilen folgen dem K0-Bericht (`evals/engine_matrix_report.py`), damit
 * Studio und Bericht auf der Platte dasselbe sagen. Die Warnungen kommen als
 * Codes vom Server (`services/eval/engine_compare.py`) und werden hier erst
 * zu Sätzen.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_COMPARE: CataloguePart = {
  de: {
    // ── Auswahl in der Lauf-Liste ───────────────────────────────────
    'evalCompare.pick': 'Vergleichen',
    /** Zugänglicher Name des Kästchens — jede Zeile trägt dasselbe Wort. */
    'evalCompare.pickFor': 'Vergleichen — Lauf {id}',
    'evalCompare.chosen.one': '{count} Lauf zum Vergleich gewählt',
    'evalCompare.chosen.other': '{count} Läufe zum Vergleich gewählt',
    'evalCompare.start': 'Gewählte vergleichen',
    'evalCompare.needTwo': 'Ein Vergleich braucht mindestens zwei Läufe.',
    'evalCompare.full': 'Mehr als {max} Läufe vergleicht das Studio nicht.',
    'evalCompare.clear': 'Auswahl aufheben',

    // ── Tafel ───────────────────────────────────────────────────────
    'evalCompare.title.one': 'Vergleich von {count} Lauf',
    'evalCompare.title.other': 'Vergleich von {count} Läufen',
    'evalCompare.close': 'Vergleich schließen',
    'evalCompare.state': 'Vergleich',
    'evalCompare.computing':
      'Rechnet … die Textnähe vergleicht jede Antwort mit jeder, bei mehreren Läufen '
      + 'dauert das einige Sekunden.',
    'evalCompare.warnings': 'Hinweise zum Vergleich',
    'evalCompare.caption': 'Kennzahlen je Maschine — gerechnet wie in der Maschinen-Messung',
    'evalCompare.col.criterion': 'Kennzahl',
    'evalCompare.col.engine.one': '{engine} ({count} Lauf)',
    'evalCompare.col.engine.other': '{engine} ({count} Läufe)',
    'evalCompare.legend':
      '„–“ heißt: nicht gemessen — etwa ohne Judge, mit nur einem Lauf je Maschine '
      + 'oder ohne gepflegten Preis.',

    'evalCompare.row.runs': 'Läufe',
    'evalCompare.row.hardRate': 'Harte Quote (Spanne der Läufe)',
    'evalCompare.row.axis': 'Judge: {axis}',
    'evalCompare.row.agreement': 'Übereinstimmung der Checks',
    'evalCompare.row.toolJaccard': 'Ähnlichkeit der Werkzeuge',
    'evalCompare.row.textSimilarity': 'Textnähe',
    'evalCompare.row.judgeSpread': 'Streuung „Auftrag erfüllt“',
    'evalCompare.row.speed': 'Dauer je Zug (p50 / p95)',
    'evalCompare.row.over30': 'Anteil über 30 s',
    'evalCompare.row.over90': 'Züge über 90 s',
    'evalCompare.row.tokens': 'Token je Zug (Eingabe / gecacht / Ausgabe)',
    'evalCompare.row.costPerTurn': 'Kosten je Zug',
    'evalCompare.row.robustness': 'Chat-Fehler / Judge-Ausfälle / leer / Ersatz',
    'evalCompare.row.safe': 'SAFE-Flows: harte Quote',
    'evalCompare.row.frei': 'FREI-Flows: harte Quote / Auftrag erfüllt',
    'evalCompare.hint.agreement':
      'Anteil der Züge mit gleichem Prüfergebnis in allen Wiederholungen',
    'evalCompare.hint.toolJaccard': 'gleiche Werkzeuge je Zug über die Wiederholungen, 1 = gleich',
    'evalCompare.hint.textSimilarity': 'Ähnlichkeit der Antworttexte je Zug, 1 = gleich',
    'evalCompare.hint.judgeSpread': 'Schwankung der Judge-Note je Zug — kleiner ist stabiler',

    // ── Regel R2(a), Plan §5.4 ──────────────────────────────────────
    'evalCompare.r2a.title': 'Hat die Muster-Maschine einen messbaren Vorteil? (Regel R2a)',
    'evalCompare.r2a.yes': 'Die Muster-Maschine zeigt einen messbaren Vorteil: {reasons}.',
    'evalCompare.r2a.no':
      'Die Muster-Maschine zeigt keinen messbaren Vorteil — weder 10 Punkte stabiler noch '
      + 'mindestens 30 % billiger oder schneller.',
    'evalCompare.r2a.missing': 'Die Regel braucht Läufe für beide Maschinen.',
    'evalCompare.r2a.factors':
      'Muster gegen Agent: Übereinstimmung {agreement} Prozentpunkte · Kosten ×{cost} · '
      + 'p50 ×{p50}',
    'evalCompare.r2b':
      'Ob eine Einbettung genau diesen Vorteil braucht (R2b), beantwortet keine Zahl. '
      + 'Liegen Unterschiede innerhalb der Spanne der Läufe, gewinnt die einfachere '
      + 'Architektur (R3).',
    'evalCompare.reason.stabiler': 'stabiler',
    'evalCompare.reason.billiger': 'billiger',
    'evalCompare.reason.schneller': 'schneller',

    // ── Warnungen (Codes des Servers) ───────────────────────────────
    'evalCompare.warn.not_found': 'Den Lauf {run} gibt es nicht mehr — er zählt nicht.',
    'evalCompare.warn.not_done': '{run} ist nicht fertig ({status}) und zählt nicht.',
    'evalCompare.warn.engine_unknown':
      'Bei {run} ist die Maschine unbekannt — der Lauf zählt nicht.',
    'evalCompare.warn.price_missing':
      'Kein Preis gepflegt für {models} — die Kostenzeile bleibt leer.',
    'evalCompare.warn.pricing_unreadable':
      'Die Preistafel ist nicht lesbar — die Kostenzeile bleibt leer.',
    'evalCompare.warn.conditions_differ':
      'Die Läufe liefen unter verschiedenen Bedingungen — siehe unten.',
    'evalCompare.warn.master_skill_off':
      'Ohne Master-Skill gemessen: {runs} — der Agent lief ohne seine Anleitung.',

    // ── Messbedingungen ─────────────────────────────────────────────
    'evalCompare.conditions.title': 'Messbedingungen',
    'evalCompare.condition':
      '{runs}: {provider} · {model} · Judge {judge} · Master-Skill {skill} · Deckel {limits}',
    'evalCompare.skill.on': 'an ({sha})',
    'evalCompare.skill.off': 'aus ({sha})',
    'evalCompare.skill.unknown': 'unbekannt',
    'evalCompare.limits': '{rounds} Runden, {seconds} s, {tokens} Token',
  },
  en: {
    'evalCompare.pick': 'Compare',
    'evalCompare.pickFor': 'Compare — run {id}',
    'evalCompare.chosen.one': '{count} run chosen for comparison',
    'evalCompare.chosen.other': '{count} runs chosen for comparison',
    'evalCompare.start': 'Compare chosen runs',
    'evalCompare.needTwo': 'A comparison needs at least two runs.',
    'evalCompare.full': 'The studio compares at most {max} runs.',
    'evalCompare.clear': 'Clear selection',

    'evalCompare.title.one': 'Comparison of {count} run',
    'evalCompare.title.other': 'Comparison of {count} runs',
    'evalCompare.close': 'Close comparison',
    'evalCompare.state': 'Comparison',
    'evalCompare.computing':
      'Computing … the text similarity compares every answer with every other; with '
      + 'several runs this takes a few seconds.',
    'evalCompare.warnings': 'Notes on this comparison',
    'evalCompare.caption': 'Figures per engine — computed as in the engine measurement',
    'evalCompare.col.criterion': 'Figure',
    'evalCompare.col.engine.one': '{engine} ({count} run)',
    'evalCompare.col.engine.other': '{engine} ({count} runs)',
    'evalCompare.legend':
      '“–” means: not measured — for instance without a judge, with only one run per '
      + 'engine or without a maintained price.',

    'evalCompare.row.runs': 'Runs',
    'evalCompare.row.hardRate': 'Hard rate (range across runs)',
    'evalCompare.row.axis': 'Judge: {axis}',
    'evalCompare.row.agreement': 'Check agreement',
    'evalCompare.row.toolJaccard': 'Tool similarity',
    'evalCompare.row.textSimilarity': 'Text similarity',
    'evalCompare.row.judgeSpread': 'Spread of “task fulfilled”',
    'evalCompare.row.speed': 'Duration per turn (p50 / p95)',
    'evalCompare.row.over30': 'Share above 30 s',
    'evalCompare.row.over90': 'Turns above 90 s',
    'evalCompare.row.tokens': 'Tokens per turn (input / cached / output)',
    'evalCompare.row.costPerTurn': 'Cost per turn',
    'evalCompare.row.robustness': 'Chat errors / judge failures / empty / fallback',
    'evalCompare.row.safe': 'SAFE flows: hard rate',
    'evalCompare.row.frei': 'FREE flows: hard rate / task fulfilled',
    'evalCompare.hint.agreement': 'Share of turns with the same check result in every repeat',
    'evalCompare.hint.toolJaccard': 'Same tools per turn across the repeats, 1 = identical',
    'evalCompare.hint.textSimilarity': 'Similarity of the answer texts per turn, 1 = identical',
    'evalCompare.hint.judgeSpread': 'Variation of the judge score per turn — smaller is steadier',

    'evalCompare.r2a.title': 'Does the pattern engine have a measurable edge? (rule R2a)',
    'evalCompare.r2a.yes': 'The pattern engine shows a measurable edge: {reasons}.',
    'evalCompare.r2a.no':
      'The pattern engine shows no measurable edge — neither 10 points steadier nor at '
      + 'least 30 % cheaper or faster.',
    'evalCompare.r2a.missing': 'The rule needs runs for both engines.',
    'evalCompare.r2a.factors':
      'Pattern against agent: agreement {agreement} percentage points · cost ×{cost} · '
      + 'p50 ×{p50}',
    'evalCompare.r2b':
      'Whether an embedding needs exactly this edge (R2b) is not a question numbers can '
      + 'answer. If differences lie within the range of the runs, the simpler architecture '
      + 'wins (R3).',
    'evalCompare.reason.stabiler': 'steadier',
    'evalCompare.reason.billiger': 'cheaper',
    'evalCompare.reason.schneller': 'faster',

    'evalCompare.warn.not_found': 'Run {run} no longer exists — it does not count.',
    'evalCompare.warn.not_done': '{run} has not finished ({status}) and does not count.',
    'evalCompare.warn.engine_unknown':
      'The engine of {run} is unknown — the run does not count.',
    'evalCompare.warn.price_missing':
      'No price maintained for {models} — the cost row stays empty.',
    'evalCompare.warn.pricing_unreadable':
      'The price table is unreadable — the cost row stays empty.',
    'evalCompare.warn.conditions_differ':
      'The runs measured under different conditions — see below.',
    'evalCompare.warn.master_skill_off':
      'Measured without the master skill: {runs} — the agent ran without its instructions.',

    'evalCompare.conditions.title': 'Measurement conditions',
    'evalCompare.condition':
      '{runs}: {provider} · {model} · judge {judge} · master skill {skill} · caps {limits}',
    'evalCompare.skill.on': 'on ({sha})',
    'evalCompare.skill.off': 'off ({sha})',
    'evalCompare.skill.unknown': 'unknown',
    'evalCompare.limits': '{rounds} rounds, {seconds} s, {tokens} tokens',
  },
};
