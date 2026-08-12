/**
 * Die Trends-Ansicht (C1-d4c) — der vierte Teil der Evaluation, nach
 * `evaluation.ts` (Hülle + Lauf-Liste), `eval-detail.ts` und `eval-pattern.ts`.
 *
 * **Die gesprochene Zusammenfassung ist der Grund für den Zuschnitt.** Sie war
 * bis hierher in der Komponente zusammengesetzt — Beschriftung, ein Komma, eine
 * Zahl, ein Richtungswort, ein Nachsatz. Genau die Bauart, die C1-d3a beim
 * Zustands-Streifen abgestellt hat: die Wortstellung gehört der Übersetzung.
 * Hier steht deshalb der GANZE Satz je Fall im Katalog, und die Richtung ist ein
 * eigener Eintrag, der eingesetzt wird.
 *
 * Drei Fälle und nicht zwei plus Mehrzahl: „ein Lauf" sagt etwas ANDERES als
 * „über N Läufe … gestiegen" — bei einem einzigen Punkt gibt es keine Richtung.
 * Das ist ein Inhalts-Unterschied, keine Grammatik, und `say.many` ist damit nie
 * für die Anzahl 1 zuständig. Ein `.one` dazu wäre ein Eintrag, der nie
 * gerendert werden kann.
 *
 * NICHT hier:
 *
 *  - **Der Name der Ansicht.** `eval.tab.trends` steht im Reiter der Hülle; der
 *    Zustands-Streifen liest ihn mit, wie die Pattern-Nutzung seit C1-d4b3.
 *  - **„Aktualisieren"** und sein Ladezustand: `action.refresh` /
 *    `action.refreshing` aus `shared.ts`.
 *
 * `evalTrends.col.turns` steht bewusst NEBEN `evalPattern.col.turns` und
 * `bars.unit`, obwohl alle drei „Turns" heissen. Es sind drei verschiedene
 * Tabellen; sie an einen Eintrag zu binden hiesse, dass eine Übersetzung die
 * beiden anderen mitzieht. Beide Tabellen DIESER Ansicht teilen sich den
 * Eintrag dagegen sehr wohl — dort ist es dieselbe Spalte.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_TRENDS: CataloguePart = {
  de: {
    // ── Zustand ─────────────────────────────────────────────────────
    'evalTrends.empty':
      'Noch kein abgeschlossener Lauf. Trends entstehen aus fertigen Läufen — '
      + 'starte einen Gold-Flow- oder generativen Lauf.',
    'evalTrends.noData': 'Keine Daten',

    // ── Score-Verlauf ───────────────────────────────────────────────
    'evalTrends.scores.caption': 'Ø Judge-Score je Lauf',
    'evalTrends.scores.none': 'Ø Judge-Score: keine bewerteten Läufe.',
    'evalTrends.scores.some':
      'Ø Judge-Score: aktuell {value} über {count} bewertete Läufe. '
      + 'Werte in der Tabelle darunter.',

    /** Zwei Auszeichnungen mitten im Satz (C1-d4b2): der Name der Tabellenspalte
     *  als Code, die Lauf-Art als Hervorhebung. */
    'evalTrends.note':
      'Die fünf Klassifikations-Serien unten stammen aus '
      + '`classification_metrics` — das schreibt nur ein *generativer* Lauf. '
      + 'Hier liegen bisher nur Gold-Flow-Läufe, deshalb sind sie leer. Der '
      + 'Ø-Score oben umfasst beide Lauf-Arten.',

    // ── Die vier Serien ─────────────────────────────────────────────
    'evalTrends.rate.cache': 'Cache-Hit-Rate',
    'evalTrends.rate.cache.hint':
      'Anteil der Prompt-Tokens, die aus dem Provider-Cache kamen.',
    'evalTrends.rate.match': 'LLM-Pattern-Übereinstimmung',
    'evalTrends.rate.match.hint':
      'Wie oft der LLM-Pattern-Hint mit der Engine-Wahl übereinstimmte.',
    'evalTrends.rate.persona': 'Persona-Trefferquote',
    'evalTrends.rate.persona.hint':
      'Anteil der Turns, in denen die erkannte Persona der erwarteten entsprach.',
    'evalTrends.rate.intent': 'Intent-Trefferquote',
    'evalTrends.rate.intent.hint':
      'Anteil der Turns, in denen der erkannte Intent dem erwarteten entsprach.',

    // ── Gesprochene Zusammenfassung eines Diagramms ─────────────────
    'evalTrends.say.none': '{label}: keine Daten.',
    'evalTrends.say.one': '{label}: aktuell {value}, ein Lauf.',
    'evalTrends.say.many':
      '{label}: aktuell {value}, über {count} Läufe von {first} {direction}. '
      + 'Werte in der Tabelle darunter.',
    'evalTrends.dir.up': 'gestiegen',
    'evalTrends.dir.down': 'gefallen',
    'evalTrends.dir.flat': 'unverändert',

    // ── Tabelle aller Werte ─────────────────────────────────────────
    'evalTrends.table.caption': 'Alle Werte je Lauf — älteste zuerst',
    'evalTrends.col.run': 'Lauf',
    'evalTrends.col.when': 'Zeitpunkt',
    'evalTrends.col.kind': 'Art',
    'evalTrends.col.turns': 'Turns',
    'evalTrends.col.score': 'Ø Score',

    // ── Ausklapper: Tool-Compliance je Pattern ──────────────────────
    'evalTrends.patterns.summary': 'Tool-Compliance je Pattern ({count})',
    'evalTrends.patterns.hint':
      'Anteil der Turns, in denen das Pattern genau die Tools aufrief, die für '
      + 'es konfiguriert sind.',
    'evalTrends.patterns.caption': 'Letzter Lauf je Pattern',
    'evalTrends.patterns.col.pattern': 'Pattern',
    'evalTrends.patterns.col.rate': 'Quote',
    'evalTrends.patterns.col.ok': 'passend',
    'evalTrends.patterns.col.trend': 'Verlauf',
    'evalTrends.spark.one':
      'Verlauf über {count} Lauf; die Quote des letzten Laufs steht in der '
      + 'Zelle links.',
    'evalTrends.spark.other':
      'Verlauf über {count} Läufe; die Quote des letzten Laufs steht in der '
      + 'Zelle links.',
  },

  en: {
    'evalTrends.empty':
      'No finished run yet. Trends grow out of completed runs — start a '
      + 'gold-flow or a generative run.',
    'evalTrends.noData': 'No data',

    'evalTrends.scores.caption': 'Avg judge score per run',
    'evalTrends.scores.none': 'Avg judge score: no judged runs.',
    'evalTrends.scores.some':
      'Avg judge score: currently {value} over {count} judged runs. '
      + 'Values in the table below.',

    'evalTrends.note':
      'The five classification series below come from `classification_metrics` '
      + '— only a *generative* run writes those. So far this installation has '
      + 'gold-flow runs only, which is why they are empty. The average score '
      + 'above covers both kinds of run.',

    'evalTrends.rate.cache': 'Cache hit rate',
    'evalTrends.rate.cache.hint':
      'Share of the prompt tokens that came out of the provider cache.',
    'evalTrends.rate.match': 'LLM pattern match',
    'evalTrends.rate.match.hint':
      'How often the LLM pattern hint agreed with the engine’s choice.',
    'evalTrends.rate.persona': 'Persona hit rate',
    'evalTrends.rate.persona.hint':
      'Share of the turns whose detected persona was the expected one.',
    'evalTrends.rate.intent': 'Intent hit rate',
    'evalTrends.rate.intent.hint':
      'Share of the turns whose detected intent was the expected one.',

    'evalTrends.say.none': '{label}: no data.',
    'evalTrends.say.one': '{label}: currently {value}, one run.',
    'evalTrends.say.many':
      '{label}: currently {value}, {direction} from {first} over {count} runs. '
      + 'Values in the table below.',
    'evalTrends.dir.up': 'up',
    'evalTrends.dir.down': 'down',
    'evalTrends.dir.flat': 'unchanged',

    'evalTrends.table.caption': 'Every value per run — oldest first',
    'evalTrends.col.run': 'Run',
    'evalTrends.col.when': 'Time',
    'evalTrends.col.kind': 'Kind',
    'evalTrends.col.turns': 'Turns',
    'evalTrends.col.score': 'Avg score',

    'evalTrends.patterns.summary': 'Tool compliance per pattern ({count})',
    'evalTrends.patterns.hint':
      'Share of the turns in which the pattern called exactly the tools it is '
      + 'configured for.',
    'evalTrends.patterns.caption': 'Last run per pattern',
    'evalTrends.patterns.col.pattern': 'Pattern',
    'evalTrends.patterns.col.rate': 'Rate',
    'evalTrends.patterns.col.ok': 'matching',
    'evalTrends.patterns.col.trend': 'Trend',
    'evalTrends.spark.one':
      'Trend over {count} run; the rate of the last run is in the cell to the '
      + 'left.',
    'evalTrends.spark.other':
      'Trend over {count} runs; the rate of the last run is in the cell to the '
      + 'left.',
  },
};
