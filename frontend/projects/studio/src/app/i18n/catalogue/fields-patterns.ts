/**
 * Feldtexte (ST-1) der Seite „Patterns“, Bereich Gesprächsmuster (`03-patterns`).
 * Alle zwanzig Muster M01–M20 teilen ein Modell, darum stehen ihre Texte einmal hier.
 *
 * Schlüsselschema wie in allen `fields-*.ts`: `feld.<Modell>.<feld>.{label,hint}`
 * (siehe `fields-layer-doc.ts`). Die Kopfangaben wirken nur in der Muster-Engine:
 * `domain/pattern_engine.py` macht aus ihnen ein `PatternDef` und über
 * `phase3_modulate` die Vorgaben des Zuges. Die Agent-Schleife wählt kein Muster,
 * außer die Sicherheit erzwingt eine Schutzantwort (`services/engine_choice.py`).
 * Zwei Stolpersteine, die die Hilfetexte deshalb offen nennen: was `PatternDef` nicht
 * kennt, fällt still weg (bis 2026-09-27 traf das `output_mode`), und `tools` kommt
 * immer als Liste an — ein leeres Feld heißt „keine“, nicht „alle“
 * (`services/response_tool_selection.py`). `rag_areas` unterscheidet seit Paket 4 (C6)
 * dagegen „nie gesetzt“ (alle Bereiche) von der leeren Liste (keine,
 * `domain/route_head.py`); das Formular zeigt beides gleich, der Hilfetext nennt es.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_PATTERNS: CataloguePart = {
  de: {
    // ── Dokument ────────────────────────────────────────────────────
    'feld.PatternArea.frontmatter.label': 'Kopfangaben',
    'feld.PatternArea.frontmatter.hint':
      'Wann der Klassifikator das Muster wählt und wie die Antwort entsteht: Ton, Länge, '
      + 'Werkzeuge, Regeln. Wirkt in der Muster-Engine; die Agent-Schleife nutzt Muster nur '
      + 'für die Schutzantworten bei Krise und Drohung.',
    'feld.PatternArea.body.label': 'Anweisungstext',
    'feld.PatternArea.body.hint':
      'Die ausführliche Anweisung in Markdown; eine Titelzeile (# …) am Anfang fällt weg. '
      + 'Steht verbindlich im Antwort-Prompt der Muster-Engine und am Schluss noch einmal als '
      + 'Erinnerung.',

    // ── Kopfangaben ─────────────────────────────────────────────────
    'feld.PatternFrontmatter.id.label': 'Kennung',
    'feld.PatternFrontmatter.id.hint':
      'Kennung wie M05, über die der Klassifikator das Muster wählt; ohne sie wird es nicht '
      + 'geladen. Einige Abläufe im Code hängen an festen Kennungen, etwa M01, M03 oder M09; '
      + 'wählt der Klassifikator keins, gilt M15, ohne M15 dann M03.',
    'feld.PatternFrontmatter.label.label': 'Anzeigename',
    'feld.PatternFrontmatter.label.hint':
      'Name wie „Material-Suche gefiltert“. Steht neben der Kennung im Klassifikator-Prompt, '
      + 'als Musterkopf und in der Schlusserinnerung des Antwort-Prompts und in den '
      + 'Qualitätslogs.',
    'feld.PatternFrontmatter.short_purpose.label': 'Zweck',
    'feld.PatternFrontmatter.short_purpose.hint':
      'Ein Satz, was das Muster leistet; er beschreibt es dem Klassifikator, bei leerem Feld '
      + 'tut das der Anfang der Kernregel. Auch vorab erzeugte Quick-Replies und die '
      + 'Evaluation lesen ihn.',
    'feld.PatternFrontmatter.priority.label': 'Priorität',
    'feld.PatternFrontmatter.priority.hint':
      'Gewicht aus der Vorlage, höher heißt wichtiger (M01: 999). Wird derzeit nicht '
      + 'ausgewertet: das Muster wählt der Klassifikator, nicht diese Zahl.',
    'feld.PatternFrontmatter.default_tone.label': 'Ton',
    'feld.PatternFrontmatter.default_tone.hint':
      'Ton der Antwort, etwa warm oder kollegial. Bei sachlich, neutral oder leer gilt der Ton '
      + 'der Zielgruppe, ebenso wenn diese „Vorrang vor Muster“ setzt; ein Signal kann ihn '
      + 'ersetzen.',
    'feld.PatternFrontmatter.default_length.label': 'Länge',
    'feld.PatternFrontmatter.default_length.hint':
      'Grundlänge der Antwort: kurz, mittel oder lang; andere Werte wie standard und ein '
      + 'leeres Feld zählen als mittel. Die Längen-Neigung der Zielgruppe oder ein Signal kann '
      + 'sie verschieben.',
    'feld.PatternFrontmatter.response_type.label': 'Antworttyp',
    'feld.PatternFrontmatter.response_type.hint':
      'Art der Antwort, etwa answer, cards, question oder refusal. Steht als Hinweis im '
      + 'Antwort-Prompt und in der Evaluation; die Darstellung im Widget schaltet es nicht um.',
    'feld.PatternFrontmatter.core_rule.label': 'Kernregel',
    'feld.PatternFrontmatter.core_rule.hint':
      'Die verbindliche Hauptregel des Musters. Steht als harte Kernregel im Antwort-Prompt '
      + 'und in der Evaluation; ist der Zweck leer, liest der Klassifikator ihren Anfang.',
    'feld.PatternFrontmatter.when_to_use.label': 'Einsatzfälle',
    'feld.PatternFrontmatter.when_to_use.hint':
      'Situationen, in denen das Muster passt, je Zeile eine. Die ersten fünf stehen im '
      + 'Klassifikator-Prompt und als Begründung im Antwort-Prompt; die Evaluation liest sie '
      + 'auch.',
    'feld.PatternFrontmatter.when_not_to_use.label': 'Ausschlussfälle',
    'feld.PatternFrontmatter.when_not_to_use.hint':
      'Situationen, in denen ein anderes Muster passt, gern mit Verweis (→ M06). Die ersten '
      + 'fünf stehen im Klassifikator-Prompt; die Evaluation liest sie auch.',
    'feld.PatternFrontmatter.trigger_phrases.label': 'Typische Nutzersätze',
    'feld.PatternFrontmatter.trigger_phrases.hint':
      'Sätze, mit denen Nutzende dieses Muster typischerweise auslösen. Die ersten fünf stehen '
      + 'als Beispiele im Klassifikator-Prompt.',
    'feld.PatternFrontmatter.discriminators.label': 'Abgrenzungen',
    'feld.PatternFrontmatter.discriminators.hint':
      'Unterscheidung von leicht verwechselbaren Mustern. Bis zu fünf stehen als '
      + 'Entscheidungshilfe im Klassifikator-Prompt; Einträge ohne Nachbarmuster oder Regel '
      + 'fallen weg.',
    'feld.PatternDiscriminator.vs.label': 'Nachbarmuster',
    'feld.PatternDiscriminator.vs.hint':
      'Das Muster, gegen das abgegrenzt wird, etwa M06. Ohne Angabe entfällt der ganze Eintrag.',
    'feld.PatternDiscriminator.rule.label': 'Regel',
    'feld.PatternDiscriminator.rule.hint':
      'Woran sich die beiden Muster unterscheiden, etwa „Filter genannt → M05, nur Thema → '
      + 'M06“. Steht im Klassifikator-Prompt und in der Evaluation; ohne Regel entfällt der '
      + 'Eintrag.',
    'feld.PatternDiscriminator.example.label': 'Beispiel',
    'feld.PatternDiscriminator.example.hint':
      'Freiwilliges Beispiel zur Regel, etwa zwei Sätze mit ihrer Zuordnung. Steht hinter der '
      + 'Regel im Klassifikator-Prompt; die Evaluation liest es nicht.',
    'feld.PatternFrontmatter.output_mode.label': 'Ausgabemodus',
    'feld.PatternFrontmatter.output_mode.hint':
      'Antwortform aus der Vorlage, etwa clarify, generate oder rerender. Im Chat wirkt '
      + 'davon nur rerender: Der zuletzt erzeugte Inhalt steht dann zum Überarbeiten im '
      + 'Antwort-Prompt (M11). Die Evaluation liest das Feld als erwartete Form.',
    'feld.PatternFrontmatter.sources.label': 'Quellen',
    'feld.PatternFrontmatter.sources.hint':
      'Erlaubte Quellen: mcp (WLO-Suche), rag (Wissensdatenbank), llm (nicht eigens geprüft); '
      + 'fehlt das Feld, gilt mcp. Ohne rag keine Wissensdatenbank, ohne mcp keine vorab '
      + 'gestartete Suche; Werkzeuge gibt nur die Werkzeugliste frei.',
    'feld.PatternFrontmatter.rag_areas.label': 'Wissensbereiche',
    'feld.PatternFrontmatter.rag_areas.hint':
      'Wissensbereiche, die das Muster durchsuchen darf, Namen wie unter Wissen. Wirkt nur '
      + 'mit rag unter Quellen, always-Bereiche werden vorab geholt. Nie gesetzt heißt alle '
      + 'Bereiche, eine geleerte Liste heißt keine.',
    'feld.PatternFrontmatter.tools.label': 'Werkzeuge',
    'feld.PatternFrontmatter.tools.hint':
      'Werkzeuge, die das Modell in diesem Muster aufrufen darf; leer heißt keine '
      + 'WLO-Werkzeuge. Schreibende nur mit Zugang zum MCP-Server; zu Suchwerkzeugen kommen '
      + 'lookup_wlo_vocabulary und get_node_details dazu.',
    'feld.PatternFrontmatter.precondition_slots.label': 'Pflichtangaben',
    'feld.PatternFrontmatter.precondition_slots.hint':
      'Angaben, die vorliegen müssen, bevor das Muster arbeitet, etwa thema. Fehlt eine, sperrt '
      + 'der Bot die Werkzeuge und fragt zuerst danach; leer heißt keine Vorbedingung.',
    'feld.PatternFrontmatter.card_text_link_required.label': 'Nur genannte Kacheln',
    'feld.PatternFrontmatter.card_text_link_required.hint':
      'Zeigt nur die Kacheln, deren Material der Antworttext nennt oder verlinkt. Wirkt '
      + 'derzeit nur auf dem Lernpfad-Schnellweg; aus oder leer: alle gefundenen Kacheln.',
    'feld.PatternFrontmatter.quick_replies_mode.label': 'Quick-Reply-Modus',
    'feld.PatternFrontmatter.quick_replies_mode.hint':
      'Wann Antwortvorschläge entstehen: exact nach der Antwort, speculative parallel dazu mit '
      + 'Rückfall auf exact, none gar nicht; feste Knöpfe wie Slot-Optionen bleiben. Leer: '
      + 'exact.',
    'feld.PatternFrontmatter.forbidden_phrases.label': 'Verbotene Formulierungen',
    'feld.PatternFrontmatter.forbidden_phrases.hint':
      'Wortlaute, die die Antwort nicht enthalten darf, etwa Floskeln. Stehen als Verbotsliste '
      + 'im Antwort-Prompt und in der Evaluation; herausgefiltert wird nichts.',
    'feld.PatternFrontmatter.anti_patterns.label': 'Anti-Muster',
    'feld.PatternFrontmatter.anti_patterns.hint':
      'Vorgehensweisen, die das Muster meiden soll, etwa „keine Filter-Frage stellen“. Stehen '
      + 'als Liste im Antwort-Prompt und in der Evaluation.',
  },
  en: {
    // ── Document ────────────────────────────────────────────────────
    'feld.PatternArea.frontmatter.label': 'Header',
    'feld.PatternArea.frontmatter.hint':
      'When the classifier picks the pattern and how the answer is built: tone, length, '
      + 'tools, rules. Effective in the pattern engine; the agent loop uses patterns only for '
      + 'the safety answers on crisis and threat.',
    'feld.PatternArea.body.label': 'Instruction text',
    'feld.PatternArea.body.hint':
      'The detailed instruction in Markdown; a leading title line (# …) is dropped. It is '
      + 'binding in the answer prompt of the pattern engine and repeated at the end as a '
      + 'reminder.',

    // ── Header ──────────────────────────────────────────────────────
    'feld.PatternFrontmatter.id.label': 'Identifier',
    'feld.PatternFrontmatter.id.hint':
      'Identifier such as M05, through which the classifier picks the pattern; without it the '
      + 'pattern is not loaded. Some flows in the code depend on fixed identifiers, such as '
      + 'M01, M03 or M09; if the classifier picks none, M15 applies, without M15 then M03.',
    'feld.PatternFrontmatter.label.label': 'Display name',
    'feld.PatternFrontmatter.label.hint':
      'Name such as “Material-Suche gefiltert”. Appears next to the identifier in the '
      + 'classifier prompt, as the pattern heading and in the final reminder of the answer '
      + 'prompt and in the quality logs.',
    'feld.PatternFrontmatter.short_purpose.label': 'Purpose',
    'feld.PatternFrontmatter.short_purpose.hint':
      'One sentence on what the pattern does; it describes the pattern to the classifier, or '
      + 'the start of the core rule does if it is empty. Pre-generated quick replies and the '
      + 'evaluation read it too.',
    'feld.PatternFrontmatter.priority.label': 'Priority',
    'feld.PatternFrontmatter.priority.hint':
      'Weight from the template, higher means more important (M01: 999). Currently not '
      + 'evaluated: the classifier picks the pattern, not this number.',
    'feld.PatternFrontmatter.default_tone.label': 'Tone',
    'feld.PatternFrontmatter.default_tone.hint':
      'Tone of the answer, such as warm or kollegial. With sachlich, neutral or empty the '
      + 'persona’s tone applies, likewise when the persona sets “Override pattern”; a signal '
      + 'can replace it.',
    'feld.PatternFrontmatter.default_length.label': 'Length',
    'feld.PatternFrontmatter.default_length.hint':
      'Base length of the answer: kurz, mittel or lang (short, medium, long); other values '
      + 'such as standard and an empty field count as mittel. The persona’s length bias or a '
      + 'signal can shift it.',
    'feld.PatternFrontmatter.response_type.label': 'Response type',
    'feld.PatternFrontmatter.response_type.hint':
      'Kind of answer, such as answer, cards, question or refusal. Appears as a hint in the '
      + 'answer prompt and in the evaluation; it does not switch the display in the widget.',
    'feld.PatternFrontmatter.core_rule.label': 'Core rule',
    'feld.PatternFrontmatter.core_rule.hint':
      'The binding main rule of the pattern. Appears as a hard core rule in the answer prompt '
      + 'and in the evaluation; if the purpose is empty, the classifier reads its beginning.',
    'feld.PatternFrontmatter.when_to_use.label': 'Use cases',
    'feld.PatternFrontmatter.when_to_use.hint':
      'Situations in which the pattern fits, one per line. The first five appear in the '
      + 'classifier prompt and as the rationale in the answer prompt; the evaluation reads '
      + 'them too.',
    'feld.PatternFrontmatter.when_not_to_use.label': 'Excluded cases',
    'feld.PatternFrontmatter.when_not_to_use.hint':
      'Situations in which another pattern fits, ideally with a pointer (→ M06). The first '
      + 'five appear in the classifier prompt; the evaluation reads them too.',
    'feld.PatternFrontmatter.trigger_phrases.label': 'Typical user phrases',
    'feld.PatternFrontmatter.trigger_phrases.hint':
      'Sentences with which users typically trigger this pattern. The first five appear as '
      + 'examples in the classifier prompt.',
    'feld.PatternFrontmatter.discriminators.label': 'Distinctions',
    'feld.PatternFrontmatter.discriminators.hint':
      'How to tell the pattern apart from easily confused ones. Up to five appear as decision '
      + 'aids in the classifier prompt; entries without another pattern or rule are dropped.',
    'feld.PatternDiscriminator.vs.label': 'Other pattern',
    'feld.PatternDiscriminator.vs.hint':
      'The pattern it is distinguished from, such as M06. Without it the whole entry is '
      + 'dropped.',
    'feld.PatternDiscriminator.rule.label': 'Rule',
    'feld.PatternDiscriminator.rule.hint':
      'What tells the two patterns apart, such as “filter given → M05, topic only → M06”. '
      + 'Appears in the classifier prompt and in the evaluation; without a rule the entry is '
      + 'dropped.',
    'feld.PatternDiscriminator.example.label': 'Example',
    'feld.PatternDiscriminator.example.hint':
      'Optional example for the rule, such as two sentences with their assignment. Appears '
      + 'after the rule in the classifier prompt; the evaluation does not read it.',
    'feld.PatternFrontmatter.output_mode.label': 'Output mode',
    'feld.PatternFrontmatter.output_mode.hint':
      'Answer form from the template, such as clarify, generate or rerender. In the chat only '
      + 'rerender has an effect: the most recently generated content is then put into the '
      + 'answer prompt for revision (M11). The evaluation reads the field as the expected form.',
    'feld.PatternFrontmatter.sources.label': 'Sources',
    'feld.PatternFrontmatter.sources.hint':
      'Allowed sources: mcp (WLO search), rag (knowledge base), llm (not checked separately); '
      + 'if the field is missing, mcp applies. No rag means no knowledge base, no mcp no '
      + 'pre-started search; only the tool list grants tools.',
    'feld.PatternFrontmatter.rag_areas.label': 'Knowledge areas',
    'feld.PatternFrontmatter.rag_areas.hint':
      'Knowledge areas the pattern may search, named as under Knowledge. Only effective with '
      + 'rag under sources, always areas are fetched in advance. Never set means all areas, '
      + 'an emptied list means none.',
    'feld.PatternFrontmatter.tools.label': 'Tools',
    'feld.PatternFrontmatter.tools.hint':
      'Tools the model may call in this pattern; empty means no WLO tools. Writing tools only '
      + 'with access to the MCP server; search tools automatically bring lookup_wlo_vocabulary '
      + 'and get_node_details.',
    'feld.PatternFrontmatter.precondition_slots.label': 'Required details',
    'feld.PatternFrontmatter.precondition_slots.hint':
      'Details that must be known before the pattern works, such as thema. If one is missing, '
      + 'the bot locks its tools and asks for it first; empty means no precondition.',
    'feld.PatternFrontmatter.card_text_link_required.label': 'Only mentioned cards',
    'feld.PatternFrontmatter.card_text_link_required.hint':
      'Shows only the cards whose material the answer text names or links. Currently only '
      + 'effective on the learning-path shortcut; off or empty: all cards found.',
    'feld.PatternFrontmatter.quick_replies_mode.label': 'Quick reply mode',
    'feld.PatternFrontmatter.quick_replies_mode.hint':
      'When quick replies are generated: exact after the answer, speculative in parallel with '
      + 'a fallback to exact, none not at all; fixed buttons such as slot options remain. '
      + 'Empty: exact.',
    'feld.PatternFrontmatter.forbidden_phrases.label': 'Forbidden phrases',
    'feld.PatternFrontmatter.forbidden_phrases.hint':
      'Wordings the answer must not contain, such as stock phrases. Appear as a prohibition '
      + 'list in the answer prompt and in the evaluation; nothing is filtered out.',
    'feld.PatternFrontmatter.anti_patterns.label': 'Anti-patterns',
    'feld.PatternFrontmatter.anti_patterns.hint':
      'Approaches the pattern should avoid, such as “do not ask a filter question”. Appear as '
      + 'a list in the answer prompt and in the evaluation.',
  },
};
