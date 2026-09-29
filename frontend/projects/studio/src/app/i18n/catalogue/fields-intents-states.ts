/**
 * Feldtexte (ST-1) der Seite „Dimensionen", Bereiche Intents
 * (`04-intents/intents`) und Gesprächszustände (`04-states/states`).
 *
 * Schlüsselschema wie in allen `fields-*.ts`: `feld.<Modell>.<feld>.{label,hint}`
 * (siehe `fields-layer-doc.ts`). Beide Bereiche wirken fast nur über den
 * Klassifikator-Prompt (`services/classify_prompt_blocks.py`), und den gibt es
 * nur in der Muster-Engine — die Agent-Schleife klassifiziert nicht
 * (`graph/nodes/assess.py`). Ausnahmen: Rolle und Anweisung einer Phase stehen
 * im Antwort-Prompt (`services/response_prompt_builder.py`), die Anweisung auch
 * im Prompt der Quick-Replies; die Folgephasen sind reine Messung
 * (`domain/state_machine.py`, dort mit `auto_correct=False` aufgerufen).
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_INTENTS_STATES: CataloguePart = {
  de: {
    // ── Intents ─────────────────────────────────────────────────────
    'feld.IntentsArea.intents.label': 'Intents',
    'feld.IntentsArea.intents.hint':
      'Die Absichten, zwischen denen der Klassifikator je Nachricht wählt, etwa I03 für die '
      + 'Suche. Jeder Eintrag steht samt Beispielen und Abgrenzungen in dessen Prompt. Nur '
      + 'Muster-Engine: die Agent-Schleife klassifiziert nicht.',
    'feld.IntentDef.id.label': 'Kennung',
    'feld.IntentDef.id.hint':
      'Etwa I05. Mit dieser Kennung antwortet der Klassifikator; Code und andere Bereiche wie '
      + 'Personas verweisen auf sie. Eine bestehende Kennung umzubenennen bricht diese Verweise.',
    'feld.IntentDef.label.label': 'Anzeigename',
    'feld.IntentDef.label.hint':
      'Kurzer Name, etwa Wissensfrage. Steht im Klassifikator-Prompt neben der Kennung, in den '
      + 'Debug-Angaben, den Qualitätslogs und den Auswahllisten des Studios.',
    'feld.IntentDef.description.label': 'Beschreibung',
    'feld.IntentDef.description.hint':
      'Was diese Absicht abdeckt, in ein bis zwei Sätzen. Steht im Klassifikator-Prompt; die '
      + 'Evaluation nutzt sie als Erwartung an die Antwort.',
    'feld.IntentDef.examples.label': 'Beispielsätze',
    'feld.IntentDef.examples.hint':
      'Typische Nutzersätze für diese Absicht. Die ersten sechs stehen als Beispiele im '
      + 'Klassifikator-Prompt, weitere werden nicht genutzt.',
    'feld.IntentDef.trigger_verbs.label': 'Auslösewörter',
    'feld.IntentDef.trigger_verbs.hint':
      'Wörter und Wendungen, die stark für diese Absicht sprechen, etwa „was bedeutet". Die '
      + 'ersten 20 stehen im Klassifikator-Prompt, Negativ-Auslöser gehen vor. Auch die '
      + 'Evaluation liest sie.',
    'feld.IntentDef.negative_triggers.label': 'Negativ-Auslöser',
    'feld.IntentDef.negative_triggers.hint':
      'Wendungen, die diese Absicht ausschließen, je mit Umleitung auf eine andere. Die ersten '
      + 'acht stehen im Klassifikator-Prompt; dort gehen sie den Auslösewörtern vor.',
    'feld.IntentDef.discriminators.label': 'Abgrenzungen',
    'feld.IntentDef.discriminators.hint':
      'Regeln gegen Verwechslung mit einer anderen Absicht: vs (deren Kennung), rule '
      + '(Faustregel), example_a und example_b (Beispielsätze). Die ersten acht stehen im '
      + 'Klassifikator-Prompt.',
    'feld.NegativeTrigger.phrase.label': 'Wendung',
    'feld.NegativeTrigger.phrase.hint':
      'Die ausschließende Wendung, etwa „was kannst du". Üblich ist | zwischen Alternativen; '
      + 'der Klassifikator liest sie als Text, der Code prüft sie nicht selbst.',
    'feld.NegativeTrigger.redirect_to.label': 'Umleiten auf',
    'feld.NegativeTrigger.redirect_to.hint':
      'Kennung der Absicht, die stattdessen gilt, etwa I03. Steht mit Pfeil hinter der '
      + 'Wendung im Klassifikator-Prompt; leer bleibt es beim bloßen Ausschluss.',
    'feld.NegativeTrigger.rationale.label': 'Begründung',
    'feld.NegativeTrigger.rationale.hint':
      'Warum umgeleitet wird, in einem Satz. Steht hinter der Wendung im Klassifikator-Prompt.',
    'feld.NegativeTrigger.when.label': 'Bedingung',
    'feld.NegativeTrigger.when.hint':
      'Wann die Umleitung gilt, frei formuliert (etwa „co-occurs: erklär"). Steht als '
      + '„(wenn …)" im Klassifikator-Prompt; der Code prüft sie nicht.',

    // ── Gesprächszustände ───────────────────────────────────────────
    'feld.StatesArea.states.label': 'Gesprächszustände',
    'feld.StatesArea.states.hint':
      'Die Phasen eines Gesprächs; der Klassifikator wählt je Nachricht eine, etwa S2 Klärung. '
      + 'Die Phase formt Antwort und Quick-Replies. Die Agent-Schleife wählt keine Phase.',
    'feld.StateDef.id.label': 'Kennung',
    'feld.StateDef.id.hint':
      'Etwa S2. Mit dieser Kennung antwortet der Klassifikator; Code und der feste Teil des '
      + 'Klassifikator-Prompts setzen S1 bis S3 voraus (S3 = Aktion). Umbenennen bricht das.',
    'feld.StateDef.label.label': 'Anzeigename',
    'feld.StateDef.label.hint':
      'Kurzer Name, etwa Klärung. Steht neben der Kennung im Klassifikator-, Antwort- und '
      + 'Quick-Reply-Prompt sowie in den Debug-Angaben und den Qualitätslogs.',
    'feld.StateDef.description.label': 'Beschreibung',
    'feld.StateDef.description.hint':
      'Was diese Phase ausmacht, in ein bis zwei Sätzen. Steht im Klassifikator-Prompt.',
    'feld.StateDef.role.label': 'Rolle des Bots',
    'feld.StateDef.role.hint':
      'Was der Bot in dieser Phase tut, in einem Satz. Steht im Antwort-Prompt der '
      + 'Muster-Engine als „Rolle in dieser Phase".',
    'feld.StateDef.bot_directive.label': 'Phasen-Anweisung',
    'feld.StateDef.bot_directive.hint':
      'Handlungsanweisung für diese Phase, etwa „genau eine Rückfrage". Steht im Antwort-Prompt '
      + 'der Muster-Engine und im Prompt der Quick-Replies. Leer: ein allgemeiner Standardsatz.',
    'feld.StateDef.next_likely.label': 'Übliche Folgephasen',
    'feld.StateDef.next_likely.hint':
      'Phasen, die meist folgen, etwa S3 und S2. Nur zur Messung: ein Wechsel außerhalb der '
      + 'Liste wird in Qualitätslogs und Evaluation als unplausibel markiert, nicht korrigiert.',
    'feld.StateDef.selection_criteria.label': 'Wahl-Kriterien',
    'feld.StateDef.selection_criteria.hint':
      'Wann der Klassifikator diese Phase wählen soll, als Stichpunkte. Stehen im '
      + 'Klassifikator-Prompt unter „Wahl-Kriterien".',
  },
  en: {
    // ── Intents ─────────────────────────────────────────────────────
    'feld.IntentsArea.intents.label': 'Intents',
    'feld.IntentsArea.intents.hint':
      'The intentions the classifier chooses between for each message, such as I03 for '
      + 'search. Each entry goes into its prompt with examples and distinctions. Pattern '
      + 'engine only: the agent loop does not classify.',
    'feld.IntentDef.id.label': 'Identifier',
    'feld.IntentDef.id.hint':
      'For example I05. The classifier answers with this identifier; code and other areas such '
      + 'as personas refer to it. Renaming an existing identifier breaks these references.',
    'feld.IntentDef.label.label': 'Display name',
    'feld.IntentDef.label.hint':
      'Short name, such as Wissensfrage. Appears next to the identifier in the classifier '
      + 'prompt, in the debug details, the quality logs and the selection lists of the Studio.',
    'feld.IntentDef.description.label': 'Description',
    'feld.IntentDef.description.hint':
      'What this intention covers, in one or two sentences. Goes into the classifier prompt; '
      + 'the evaluation uses it as the expectation for the answer.',
    'feld.IntentDef.examples.label': 'Example sentences',
    'feld.IntentDef.examples.hint':
      'Typical user sentences for this intention. The first six go into the classifier prompt '
      + 'as examples; further ones are not used.',
    'feld.IntentDef.trigger_verbs.label': 'Trigger phrases',
    'feld.IntentDef.trigger_verbs.hint':
      'Words and phrases that strongly point to this intention, such as "was bedeutet". The '
      + 'first 20 go into the classifier prompt; negative triggers take precedence. The '
      + 'evaluation reads them too.',
    'feld.IntentDef.negative_triggers.label': 'Negative triggers',
    'feld.IntentDef.negative_triggers.hint':
      'Phrases that rule this intention out, each with a redirect to another one. The first '
      + 'eight go into the classifier prompt, where they take precedence over the trigger phrases.',
    'feld.IntentDef.discriminators.label': 'Distinctions',
    'feld.IntentDef.discriminators.hint':
      'Rules against confusion with another intention: vs (its identifier), rule (rule of '
      + 'thumb), example_a and example_b (example sentences). The first eight go into the '
      + 'classifier prompt.',
    'feld.NegativeTrigger.phrase.label': 'Phrase',
    'feld.NegativeTrigger.phrase.hint':
      'The excluding phrase, such as "was kannst du". A | between alternatives is common; the '
      + 'classifier reads it as text, the code does not check it itself.',
    'feld.NegativeTrigger.redirect_to.label': 'Redirect to',
    'feld.NegativeTrigger.redirect_to.hint':
      'Identifier of the intention that applies instead, such as I03. Appears with an arrow '
      + 'after the phrase in the classifier prompt; if empty, the phrase only excludes.',
    'feld.NegativeTrigger.rationale.label': 'Rationale',
    'feld.NegativeTrigger.rationale.hint':
      'Why the redirect applies, in one sentence. Appears after the phrase in the classifier '
      + 'prompt.',
    'feld.NegativeTrigger.when.label': 'Condition',
    'feld.NegativeTrigger.when.hint':
      'When the redirect applies, in free text (such as a word the message must also '
      + 'contain). Appears as "(wenn …)" in the classifier prompt; the code does not check it.',

    // ── Conversation states ─────────────────────────────────────────
    'feld.StatesArea.states.label': 'Conversation states',
    'feld.StatesArea.states.hint':
      'The phases of a conversation; the classifier picks one per message, such as S2 '
      + 'clarification. The phase shapes the answer and the quick replies. The agent loop does '
      + 'not pick a phase.',
    'feld.StateDef.id.label': 'Identifier',
    'feld.StateDef.id.hint':
      'For example S2. The classifier answers with this identifier; code and the fixed part of '
      + 'the classifier prompt assume S1 to S3 (S3 = action). Renaming breaks that.',
    'feld.StateDef.label.label': 'Display name',
    'feld.StateDef.label.hint':
      'Short name, such as Clarification. Appears next to the identifier in the classifier, '
      + 'answer and quick-reply prompts, in the debug details and in the quality logs.',
    'feld.StateDef.description.label': 'Description',
    'feld.StateDef.description.hint':
      'What marks this phase, in one or two sentences. Goes into the classifier prompt.',
    'feld.StateDef.role.label': 'Bot role',
    'feld.StateDef.role.hint':
      'What the bot does in this phase, in one sentence. Appears in the answer prompt of the '
      + 'pattern engine as "Rolle in dieser Phase".',
    'feld.StateDef.bot_directive.label': 'Phase directive',
    'feld.StateDef.bot_directive.hint':
      'Instruction for this phase, such as "exactly one follow-up question". Appears in the '
      + 'answer prompt of the pattern engine and in the quick-reply prompt. Empty: a generic '
      + 'default sentence.',
    'feld.StateDef.next_likely.label': 'Likely next states',
    'feld.StateDef.next_likely.hint':
      'States that usually follow, such as S3 and S2. For measurement only: a change outside '
      + 'the list is flagged as implausible in quality logs and evaluation, not corrected.',
    'feld.StateDef.selection_criteria.label': 'Selection criteria',
    'feld.StateDef.selection_criteria.hint':
      'When the classifier should pick this phase, as bullet points. They go into the '
      + 'classifier prompt under "Wahl-Kriterien".',
  },
};
