/**
 * Feldtexte (ST-1) der Seite „Dimensionen“, Bereiche „Feste Anker der Einordnung“
 * (`01-base/classify-overrides`) und „Platzhalter-Themen“ (`01-base/placeholder-topics`).
 *
 * Schlüsselschema wie in allen `fields-*.ts` (siehe `fields-layer-doc.ts`).
 * Die Anker wirken nicht deterministisch: `services/classify_prompt.py` schreibt
 * sie als Regeln und Beispiele in den Klassifikator-Prompt, entscheiden tut das
 * Sprachmodell. Nicht in den Prompt kommen die `id` beider Regelarten und die
 * Beschreibung einer Persona-Regel, von `topic_overrides` nur zwei Unterschlüssel.
 * `pattern_disambiguators_legacy` liest niemand: der Lader
 * (`services/config_loader/classification.py`) fragt nach `pattern_disambiguators`,
 * einem Schlüssel, den das Modell nicht führt. Die Platzhalter-Themen greifen
 * dagegen hart: `graph/nodes/merge.py` leert ein erkanntes Thema, das auf der
 * Liste steht oder zu kurz ist.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_KLASSIFIKATION: CataloguePart = {
  de: {
    // ── Feste Anker der Einordnung (01-base/classify-overrides) ─────
    'feld.ClassifyOverridesArea.persona_overrides.label': 'Persona-Regeln',
    'feld.ClassifyOverridesArea.persona_overrides.hint':
      'Regeln, bei welchen Wörtern der Klassifikator welche Persona wählen soll. Im '
      + 'Klassifikator-Prompt stehen sie als Vorrang-Regeln; das Sprachmodell wendet sie an, der '
      + 'Code erzwingt nichts.',
    'feld.ClassifyOverridesArea.intent_overrides.label': 'Intent-Regeln',
    'feld.ClassifyOverridesArea.intent_overrides.hint':
      'Regeln, bei welchen Wörtern der Klassifikator welchen Intent wählen soll, etwa „suche“ → '
      + 'I03. Im Klassifikator-Prompt stehen sie als Vorrang-Regeln; der Code erzwingt nichts.',
    'feld.ClassifyOverridesArea.intent_conflict_rule.label': 'Konfliktregel',
    'feld.ClassifyOverridesArea.intent_conflict_rule.hint':
      'Freitext, wie zu entscheiden ist, wenn mehrere Intent-Regeln passen, etwa „das erste Verb '
      + 'gewinnt“. Steht als Konflikt-Regel im Klassifikator-Prompt; leer entfällt sie.',
    'feld.ClassifyOverridesArea.topic_overrides.label': 'Themen-Regeln',
    'feld.ClassifyOverridesArea.topic_overrides.hint':
      'Nur zwei Einträge wirken, je mit den ersten 8 Werten im Klassifikator-Prompt: '
      + 'phantom_topic_phrases.phrases (etwa „ein Thema“ → Thema leer) und '
      + 'fach_as_topic_fallback.triggers (nur ein Fach genannt → Fach auch als Thema).',
    'feld.ClassifyOverridesArea.pattern_disambiguators_legacy.label':
      'Alte Muster-Abgrenzungen',
    'feld.ClassifyOverridesArea.pattern_disambiguators_legacy.hint':
      'Frühere zentrale Regeln zur Abgrenzung von Mustern. Wird derzeit nicht ausgewertet: '
      + 'Abgrenzungen stehen heute im jeweiligen Muster unter „Abgrenzungen“.',
    'feld.ClassifyOverridesArea.few_shot_examples.label': 'Zuordnungsbeispiele',
    'feld.ClassifyOverridesArea.few_shot_examples.hint':
      'Beispielsätze mit erwartetem Intent und Muster. Alle stehen als verbindliche Beispiele im '
      + 'Klassifikator-Prompt: bei ähnlichen Eingaben soll das Modell dasselbe Muster wählen.',

    // ── Zuordnungsbeispiel (FewShotExample) ─────────────────────────
    'feld.FewShotExample.input.label': 'Beispielsatz',
    'feld.FewShotExample.input.hint':
      'Der Satz, wie eine Person ihn schreiben würde, etwa „Hast du was zu Klimawandel?“. Steht '
      + 'mit erwartetem Intent und Muster im Prompt.',
    'feld.FewShotExample.intent.label': 'Erwarteter Intent',
    'feld.FewShotExample.intent.hint':
      'Intent, den der Klassifikator für diesen Satz wählen soll, etwa I03.',
    'feld.FewShotExample.pattern.label': 'Erwartetes Muster',
    'feld.FewShotExample.pattern.hint':
      'Muster, das für diesen Satz gewählt werden soll, etwa M06.',
    'feld.FewShotExample.note.label': 'Anmerkung',
    'feld.FewShotExample.note.hint':
      'Kurze Begründung, etwa „gefilterte Suche“. Steht in Klammern hinter dem Beispiel; leer '
      + 'entfällt sie.',

    // ── Intent-Regel (IntentOverride) ───────────────────────────────
    'feld.IntentOverride.id.label': 'Kennung',
    'feld.IntentOverride.id.hint':
      'Name der Regel, etwa i03_search_verbs. Nur zur Übersicht: der Klassifikator-Prompt '
      + 'enthält ihn nicht.',
    'feld.IntentOverride.description.label': 'Beschreibung',
    'feld.IntentOverride.description.hint':
      'Wofür die Regel steht, etwa „Such-Verben“. Eröffnet die Regelzeile im '
      + 'Klassifikator-Prompt.',
    'feld.IntentOverride.intent.label': 'Ziel-Intent',
    'feld.IntentOverride.intent.hint':
      'Intent, den der Klassifikator bei diesen Auslösern wählen soll, etwa I05.',
    'feld.IntentOverride.triggers.label': 'Auslöser',
    'feld.IntentOverride.triggers.hint':
      'Wörter und Wendungen, die für den Intent sprechen, etwa „erstelle“. Die ersten 14 stehen '
      + 'im Prompt; ohne Auslöser fehlt die ganze Regel dort.',

    // ── Persona-Regel (PersonaOverride) ─────────────────────────────
    'feld.PersonaOverride.id.label': 'Kennung',
    'feld.PersonaOverride.id.hint':
      'Name der Regel, etwa p_elt_self_id. Nur zur Übersicht: der Klassifikator-Prompt enthält '
      + 'ihn nicht.',
    'feld.PersonaOverride.description.label': 'Beschreibung',
    'feld.PersonaOverride.description.hint':
      'Wofür die Regel steht. Nur zur Übersicht: anders als bei Intent-Regeln steht sie nicht '
      + 'im Klassifikator-Prompt.',
    'feld.PersonaOverride.persona.label': 'Ziel-Persona',
    'feld.PersonaOverride.persona.hint':
      'Persona, die der Klassifikator bei diesen Merkmalen wählen soll, etwa P-ELT.',
    'feld.PersonaOverride.triggers.label': 'Auslöser',
    'feld.PersonaOverride.triggers.hint':
      'Wörter und Wendungen, die auf die Persona deuten, etwa „mein Kind“. Die ersten 12 stehen '
      + 'im Prompt.',
    'feld.PersonaOverride.except_explicit_role.label': 'Ausnahmen bei Selbstauskunft',
    'feld.PersonaOverride.except_explicit_role.hint':
      'Selbstauskünfte, bei denen die Regel nicht gelten soll, etwa „ich bin Lehrer:in“. Stehen '
      + 'als Ausnahme hinter der Regel im Prompt.',
    'feld.PersonaOverride.requires_all.label': 'Alle erforderlich',
    'feld.PersonaOverride.requires_all.hint':
      'Wörter, die alle vorkommen sollen, damit die Regel gilt, etwa „meine Klasse“. Stehen als '
      + '„alle von […]“ in der Regelzeile.',
    'feld.PersonaOverride.requires_any.label': 'Eines erforderlich',
    'feld.PersonaOverride.requires_any.hint':
      'Wörter, von denen mindestens eines vorkommen soll, etwa „unterrichten“ oder „planen“. '
      + 'Stehen als „eines von […]“ in der Regelzeile.',

    // ── Platzhalter-Themen (01-base/placeholder-topics) ─────────────
    'feld.PlaceholderTopicsArea.placeholder_topics.label': 'Platzhalter-Wörter',
    'feld.PlaceholderTopicsArea.placeholder_topics.hint':
      'Wörter wie „Thema“ oder „etwas“, die kein Thema sind: lautet ein erkanntes Thema genau so '
      + '(Groß-/Kleinschreibung egal), bleibt es leer. Leer = eingebaute Liste.',
    'feld.PlaceholderTopicsArea.min_topic_length.label': 'Mindestlänge Thema',
    'feld.PlaceholderTopicsArea.min_topic_length.hint':
      'Ein erkanntes Thema mit weniger Zeichen gilt als Platzhalter und bleibt leer. Vorgabe 3, '
      + 'damit Kürzel wie „OER“ gelten; 0 schaltet die Prüfung ab, Werte über 10 gelten als 10.',
  },
  en: {
    // ── Fixed classification anchors (01-base/classify-overrides) ───
    'feld.ClassifyOverridesArea.persona_overrides.label': 'Persona rules',
    'feld.ClassifyOverridesArea.persona_overrides.hint':
      'Rules telling the classifier which persona to choose for which words. They go into the '
      + 'classifier prompt as priority rules; the language model applies them, the code '
      + 'enforces nothing.',
    'feld.ClassifyOverridesArea.intent_overrides.label': 'Intent rules',
    'feld.ClassifyOverridesArea.intent_overrides.hint':
      'Rules telling the classifier which intent to choose for which words, such as “suche” → '
      + 'I03. They go into the classifier prompt as priority rules; the code enforces nothing.',
    'feld.ClassifyOverridesArea.intent_conflict_rule.label': 'Conflict rule',
    'feld.ClassifyOverridesArea.intent_conflict_rule.hint':
      'Free text on how to decide when several intent rules match, such as “the first verb '
      + 'wins”. Goes into the classifier prompt as the conflict rule; left out if empty.',
    'feld.ClassifyOverridesArea.topic_overrides.label': 'Topic rules',
    'feld.ClassifyOverridesArea.topic_overrides.hint':
      'Only two entries count, each with its first 8 values in the classifier prompt: '
      + 'phantom_topic_phrases.phrases (such as “ein Thema” → topic empty) and '
      + 'fach_as_topic_fallback.triggers (only a subject named → subject also as topic).',
    'feld.ClassifyOverridesArea.pattern_disambiguators_legacy.label':
      'Legacy pattern distinctions',
    'feld.ClassifyOverridesArea.pattern_disambiguators_legacy.hint':
      'Former central rules for telling patterns apart. Currently not evaluated: distinctions '
      + 'now live in each pattern under “Distinctions”.',
    'feld.ClassifyOverridesArea.few_shot_examples.label': 'Few-shot examples',
    'feld.ClassifyOverridesArea.few_shot_examples.hint':
      'Example sentences with the expected intent and pattern. All go into the classifier '
      + 'prompt as binding examples: for similar input the model should choose the same pattern.',

    // ── Few-shot example (FewShotExample) ───────────────────────────
    'feld.FewShotExample.input.label': 'Example sentence',
    'feld.FewShotExample.input.hint':
      'The sentence as a person would write it, such as “Hast du was zu Klimawandel?”. Goes '
      + 'into the prompt with the expected intent and pattern.',
    'feld.FewShotExample.intent.label': 'Expected intent',
    'feld.FewShotExample.intent.hint':
      'Intent the classifier should choose for this sentence, such as I03.',
    'feld.FewShotExample.pattern.label': 'Expected pattern',
    'feld.FewShotExample.pattern.hint':
      'Pattern that should be chosen for this sentence, such as M06.',
    'feld.FewShotExample.note.label': 'Note',
    'feld.FewShotExample.note.hint':
      'Short reason, such as “gefilterte Suche”. Goes in brackets after the example; left out '
      + 'if empty.',

    // ── Intent rule (IntentOverride) ────────────────────────────────
    'feld.IntentOverride.id.label': 'Identifier',
    'feld.IntentOverride.id.hint':
      'Name of the rule, such as i03_search_verbs. For overview only: the classifier prompt '
      + 'does not contain it.',
    'feld.IntentOverride.description.label': 'Description',
    'feld.IntentOverride.description.hint':
      'What the rule stands for, such as “Such-Verben”. Opens the rule line in the classifier '
      + 'prompt.',
    'feld.IntentOverride.intent.label': 'Target intent',
    'feld.IntentOverride.intent.hint':
      'Intent the classifier should choose for these triggers, such as I05.',
    'feld.IntentOverride.triggers.label': 'Triggers',
    'feld.IntentOverride.triggers.hint':
      'Words and phrases that point to the intent, such as “erstelle”. The first 14 go into the '
      + 'prompt; without triggers the whole rule is missing there.',

    // ── Persona rule (PersonaOverride) ──────────────────────────────
    'feld.PersonaOverride.id.label': 'Identifier',
    'feld.PersonaOverride.id.hint':
      'Name of the rule, such as p_elt_self_id. For overview only: the classifier prompt does '
      + 'not contain it.',
    'feld.PersonaOverride.description.label': 'Description',
    'feld.PersonaOverride.description.hint':
      'What the rule stands for. For overview only: unlike with intent rules, it does not go '
      + 'into the classifier prompt.',
    'feld.PersonaOverride.persona.label': 'Target persona',
    'feld.PersonaOverride.persona.hint':
      'Persona the classifier should choose for these cues, such as P-ELT.',
    'feld.PersonaOverride.triggers.label': 'Triggers',
    'feld.PersonaOverride.triggers.hint':
      'Words and phrases that point to the persona, such as “mein Kind”. The first 12 go into '
      + 'the prompt.',
    'feld.PersonaOverride.except_explicit_role.label': 'Self-description exceptions',
    'feld.PersonaOverride.except_explicit_role.hint':
      'Self-descriptions for which the rule should not apply, such as “ich bin Lehrer:in”. They '
      + 'go into the prompt as an exception after the rule.',
    'feld.PersonaOverride.requires_all.label': 'All required',
    'feld.PersonaOverride.requires_all.hint':
      'Words that should all occur for the rule to apply, such as “meine Klasse”. They appear '
      + 'in the rule line as “alle von […]”.',
    'feld.PersonaOverride.requires_any.label': 'One required',
    'feld.PersonaOverride.requires_any.hint':
      'Words of which at least one should occur, such as “unterrichten” or “planen”. They '
      + 'appear in the rule line as “eines von […]”.',

    // ── Placeholder topics (01-base/placeholder-topics) ─────────────
    'feld.PlaceholderTopicsArea.placeholder_topics.label': 'Placeholder words',
    'feld.PlaceholderTopicsArea.placeholder_topics.hint':
      'Words such as “Thema” or “etwas” that are not a topic: if a recognised topic is exactly '
      + 'one of them (case-insensitive), it is left empty. Empty = built-in list.',
    'feld.PlaceholderTopicsArea.min_topic_length.label': 'Minimum topic length',
    'feld.PlaceholderTopicsArea.min_topic_length.hint':
      'A recognised topic with fewer characters counts as a placeholder and is left empty. '
      + 'Default 3, so that abbreviations such as “OER” count; 0 switches the check off, values '
      + 'above 10 count as 10.',
  },
};
