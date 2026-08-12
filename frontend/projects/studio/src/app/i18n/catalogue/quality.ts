/**
 * Die Analyse-Ansicht (C1-d4d1): Hülle, Übersicht und Problem-Diagnose.
 *
 * **Ein Teil für drei Bauteile**, weil es EIN Panel ist: die Diagnose-Blöcke
 * stehen im Übersichts-Reiter, nicht daneben — `quality-overview.component.html`
 * rendert `<studio-quality-diagnosis>` als letzten Abschnitt. Die Hülle kommt
 * dazu, weil ihre Reiter-Namen die Panels benennen, die hier beschrieben werden.
 * Die drei übrigen Reiter (Matrix, Fluss, Logs) folgen mit C1-d4d2 in eigenen
 * Teilen; sie teilen mit diesem nur Lehnwörter, die ohnehin gleich lauten.
 *
 * **Was NICHT hier steht:** der Krümel „Auswertung" und die Überschrift
 * „Analyse" — beide stehen als `nav.group.auswertung` und `view.analyse.label`
 * schon im Rumpf-Katalog (`views.ts`) und benennen dort dieselbe Ansicht. Ein
 * zweiter Eintrag hiesse, dass die Navigation und die Seite selbst auseinander
 * laufen können. Ebenso fehlen „Aktualisieren"/„Wird geladen …" — die stehen
 * als `action.refresh*` in `shared.ts`.
 *
 * **`Leere Entities` steht EINMAL** (`qual.emptyEntities`) und wird an zwei
 * Stellen gelesen: als Kennzahl-Name und als Substantiv des Zustands-Streifens.
 * Es ist dieselbe Sache, nicht zwei gleichlautende.
 *
 * **`<em>` wird zu `*…*` und damit zu `<strong>`.** `splitRich` kennt nur
 * `strong` und `code`; der eine kursive Fachbegriff im Hilfetext wird dadurch
 * fett statt kursiv. Bewusst kein dritter Marker: die vier übrigen `<em>` im
 * Studio stehen sämtlich in der Referenz-Prosa (C1-d5), die der Nutzer
 * zurückgestellt hat — eine Erweiterung ohne heutigen Verbraucher.
 */
import type { CataloguePart } from './catalogue-part';

export const QUALITY: CataloguePart = {
  de: {
    // ── Hülle ───────────────────────────────────────────────────────
    'qual.intro':
      'Wie der Bot einordnet und antwortet: Kennzahlen und Problem-Diagnosen, die '
      + 'Pattern-Wahl je Persona und Intent, der Verlauf über die Phasen und die '
      + 'einzelnen Turns.',
    'qual.scope.legend': 'Datenbasis',
    'qual.scope.all': 'Alle',
    'qual.scope.all.hint': 'Echte Gespräche und Eval-Läufe zusammen',
    'qual.scope.production': 'Produktion',
    'qual.scope.production.hint': 'Nur echte Gespräche',
    'qual.scope.eval': 'Nur Eval',
    'qual.scope.eval.hint': 'Nur simulierte Eval-Turns',
    'qual.tab.overview': 'Übersicht',
    'qual.tab.matrix': 'Routing-Matrix',
    'qual.tab.flow': 'Gesprächs-Flow',
    'qual.tab.logs': 'Logs',

    // ── Übersicht: Kennzahlen ───────────────────────────────────────
    'qual.stats.label': 'Kennzahlen',
    'qual.stats.empty':
      'Noch keine Turns aufgezeichnet. Sobald jemand mit dem Widget chattet, sammeln '
      + 'sich hier Verteilungen und Diagnosen.',
    'qual.kpi.turns': 'Turns gesamt',
    'qual.kpi.confidence': 'Ø Confidence',
    'qual.kpi.degradation': 'Degradation-Rate',
    /** Kennzahl-Name UND Substantiv des Zustands-Streifens — siehe Kopf. */
    'qual.emptyEntities': 'Leere Entities',
    'qual.kpi.length': 'Ø Antwortlänge',
    'qual.kpi.chars': 'Zeichen',
    'qual.note':
      'Ohne Score-Phase: die Pattern-Wahl folgt seit Welle E v4 direkt dem Hinweis des '
      + 'Classifiers, statt Kandidaten gegeneinander zu bewerten. „Ø Score-Gap" und '
      + '„Tight Races" wären deshalb für jeden Turn 0 und werden hier nicht angezeigt. '
      + 'Uneindeutige Zuordnungen sieht man stattdessen unter „Unsichere Einordnung" '
      + 'und in der Routing-Matrix.',
    'qual.hints.title': 'Auffällig',
    /** Der GANZE Satz, nicht Bruchstück-plus-Wert: bis C1-d4d1 setzte die
     *  Komponente ihn aus zwei Zeichenketten und dem Prozentwert zusammen. */
    'qual.hint.degradation':
      'Degradation-Rate bei {value} — Pflicht-Slots der betroffenen Patterns prüfen.',
    'qual.hint.emptyEntities':
      '{value} der Turns ohne erkannte Entities — Entity-Erkennung im Classifier prüfen.',
    'qual.chart.patterns': 'Pattern-Verteilung',
    'qual.chart.intents': 'Intent-Verteilung',

    // ── Übersicht: Problem-Diagnose ─────────────────────────────────
    'qual.diag.title': 'Problem-Diagnose',
    /** Zwei unabhängige Anzahlen in einer Kopfzeile: zwei Wortgruppen, in
     *  `qual.diag.counts` eingesetzt. Eine Schlüssel-Matrix aus vier Sätzen
     *  wäre die falsche Antwort — dieselbe Bauart wie `evalPattern.combos`. */
    'qual.diag.turns.one': '{count} Turn',
    'qual.diag.turns.other': '{count} Turns',
    'qual.diag.groups.one': '{count} Muster',
    'qual.diag.groups.other': '{count} Muster',
    'qual.diag.counts': '{turns} · {groups}',

    'qual.diag.degradation.name': 'Degradation — fehlende Slots führen zu Rückfragen',
    'qual.diag.degradation.help':
      'Ein Pattern *degradiert*, wenn es seine reguläre Antwort aufgibt und stattdessen '
      + 'nachfragt, weil Pflicht-Slots leer sind — etwa M10 Canvas-Create ohne `thema` '
      + 'oder `material_typ`. Häufige Kombinationen aus Pattern und fehlendem Slot '
      + 'zeigen, wo sich Slot-Erkennung oder Fragetechnik zu verbessern lohnt.',
    'qual.diag.degradation.label': 'Degradationen',
    'qual.diag.degradation.empty':
      'Keine Degradationen im gewählten Bereich — alle Pflicht-Slots waren gefüllt.',
    'qual.diag.noPattern': '(ohne Pattern)',
    'qual.diag.missing': 'Fehlend:',
    /** Ein Schlüssel für BEIDE Drilldown-Knöpfe: der Satz ist derselbe, nur das
     *  Eingesetzte unterscheidet sich (Pattern-Kennung oder Intent-Kennung). */
    'qual.diag.drill': 'Turns zu {id} anzeigen',
    'qual.diag.thisPattern': 'diesem Muster',

    'qual.diag.entities.name':
      'Leere Entities — der Turn lieferte keine verwertbaren Angaben',
    'qual.diag.entities.help':
      'Diese Turns wurden einem Intent zugeordnet, aber die Entity-Erkennung fand nichts '
      + '— weder Thema noch Stufe noch Fach. Sammelt sich das bei einem Intent, ist meist '
      + 'der Classifier-Prompt für diesen Fall zu unspezifisch.',
    'qual.diag.entities.empty':
      'Jeder Turn im gewählten Bereich lieferte mindestens eine Entity.',
    'qual.diag.noIntent': '(ohne Intent)',
    'qual.diag.pattern': 'Pattern',
    'qual.diag.persona': 'Persona',
    'qual.diag.thisIntent': 'diesem Intent',

    'qual.diag.low.name': 'Unsichere Einordnung — niedrige Confidence',
    'qual.diag.low.help':
      'Einzelne Turns, bei denen sich der Classifier seiner Einordnung am wenigsten '
      + 'sicher war — unsicherste zuerst. Anders als die beiden Blöcke darüber ist das '
      + 'keine Gruppierung, sondern eine Liste echter Turns.',
    'qual.diag.low.label': 'Unsichere Turns',
    'qual.diag.low.empty':
      'Kein Turn lag unter der Schwelle — der Classifier war durchgehend sicher.',
    'qual.diag.low.count': '{turns} unter {threshold}',
    'qual.diag.confidence': 'Confidence',
  },

  en: {
    'qual.intro':
      'How the bot classifies and answers: key figures and problem diagnostics, the '
      + 'pattern choice per persona and intent, the course across the phases, and the '
      + 'individual turns.',
    'qual.scope.legend': 'Data basis',
    'qual.scope.all': 'All',
    'qual.scope.all.hint': 'Real conversations and eval runs together',
    'qual.scope.production': 'Production',
    'qual.scope.production.hint': 'Real conversations only',
    'qual.scope.eval': 'Eval only',
    'qual.scope.eval.hint': 'Simulated eval turns only',
    'qual.tab.overview': 'Overview',
    'qual.tab.matrix': 'Routing matrix',
    'qual.tab.flow': 'Conversation flow',
    'qual.tab.logs': 'Logs',

    'qual.stats.label': 'Key figures',
    'qual.stats.empty':
      'No turns recorded yet. As soon as someone chats with the widget, distributions '
      + 'and diagnostics collect here.',
    'qual.kpi.turns': 'Turns total',
    'qual.kpi.confidence': 'Avg confidence',
    'qual.kpi.degradation': 'Degradation rate',
    'qual.emptyEntities': 'Empty entities',
    'qual.kpi.length': 'Avg answer length',
    'qual.kpi.chars': 'characters',
    'qual.note':
      'No score phase: since wave E v4 the pattern choice follows the hint of the '
      + 'classifier directly instead of scoring candidates against each other. '
      + '"Avg score gap" and "Tight races" would therefore be 0 for every turn and are '
      + 'not shown here. Ambiguous assignments show up under "Uncertain classification" '
      + 'and in the routing matrix instead.',
    'qual.hints.title': 'Notable',
    'qual.hint.degradation':
      'Degradation rate at {value} — check the required slots of the patterns concerned.',
    'qual.hint.emptyEntities':
      '{value} of turns without recognised entities — check entity recognition in the '
      + 'classifier.',
    'qual.chart.patterns': 'Pattern distribution',
    'qual.chart.intents': 'Intent distribution',

    'qual.diag.title': 'Problem diagnostics',
    'qual.diag.turns.one': '{count} turn',
    'qual.diag.turns.other': '{count} turns',
    'qual.diag.groups.one': '{count} pattern',
    'qual.diag.groups.other': '{count} patterns',
    'qual.diag.counts': '{turns} · {groups}',

    'qual.diag.degradation.name': 'Degradation — missing slots lead to follow-up questions',
    'qual.diag.degradation.help':
      'A pattern *degrades* when it gives up its regular answer and asks back instead, '
      + 'because required slots are empty — M10 Canvas-Create without `thema` or '
      + '`material_typ`, for instance. Frequent combinations of pattern and missing slot '
      + 'show where slot recognition or questioning technique is worth improving.',
    'qual.diag.degradation.label': 'Degradations',
    'qual.diag.degradation.empty':
      'No degradations in the chosen scope — every required slot was filled.',
    'qual.diag.noPattern': '(no pattern)',
    'qual.diag.missing': 'Missing:',
    'qual.diag.drill': 'Show turns for {id}',
    'qual.diag.thisPattern': 'this pattern',

    'qual.diag.entities.name': 'Empty entities — the turn yielded no usable details',
    'qual.diag.entities.help':
      'These turns were assigned an intent, but entity recognition found nothing — no '
      + 'topic, no level, no subject. If this piles up on one intent, the classifier '
      + 'prompt for that case is usually too unspecific.',
    'qual.diag.entities.empty':
      'Every turn in the chosen scope yielded at least one entity.',
    'qual.diag.noIntent': '(no intent)',
    'qual.diag.pattern': 'Pattern',
    'qual.diag.persona': 'Persona',
    'qual.diag.thisIntent': 'this intent',

    'qual.diag.low.name': 'Uncertain classification — low confidence',
    'qual.diag.low.help':
      'Individual turns where the classifier was least sure of its classification — '
      + 'least certain first. Unlike the two blocks above this is not a grouping but a '
      + 'list of real turns.',
    'qual.diag.low.label': 'Uncertain turns',
    'qual.diag.low.empty':
      'No turn fell below the threshold — the classifier was confident throughout.',
    'qual.diag.low.count': '{turns} below {threshold}',
    'qual.diag.confidence': 'Confidence',
  },
};
