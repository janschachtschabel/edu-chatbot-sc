/**
 * Feldtexte (ST-1) der Seite „Dimensionen“, Bereich Personas (`04-personas`).
 * Alle sechs Zielgruppen P-AND … P-RED teilen ein Modell, darum stehen ihre Texte
 * einmal hier.
 *
 * Schlüsselschema wie in allen `fields-*.ts`: `feld.<Modell>.<feld>.{label,hint}`
 * (siehe `fields-layer-doc.ts`). Die Muster-Engine liest die Kopfangaben an drei
 * Stellen: im Klassifikator-Prompt (`services/classify_prompt_blocks.py`), im
 * Persona-Block des Antwort-Prompts (`services/config_loader/personas.py`) und als
 * Tonalität (`services/config_loader/tone.py` → `phase3_modulate`). Die
 * Agent-Schleife klassifiziert nicht und liest nur Anzeigename und Anrede
 * (`services/agent_kopf.py`). Was keiner dieser Leser anfasst — die Beispiele
 * einer Abgrenzung, die typischen Anliegen —, nennt der Hilfetext als nicht
 * ausgewertet. Begründung und Bedingung eines Anti-Markers stehen seit 2026-09-27
 * im Klassifikator-Prompt.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_PERSONAS: CataloguePart = {
  de: {
    // ── Dokument ────────────────────────────────────────────────────
    'feld.PersonaArea.frontmatter.label': 'Kopfangaben',
    'feld.PersonaArea.frontmatter.hint':
      'Erkennungsmerkmale für den Klassifikator sowie Ton, Anrede und Regeln für die Antwort. '
      + 'Wirkt in der Muster-Engine; die Agent-Schleife nutzt davon nur Anzeigename und Anrede.',
    'feld.PersonaArea.body.label': 'Ausführliche Beschreibung',
    'feld.PersonaArea.body.hint':
      'Porträt der Zielgruppe in Markdown; eine Titelzeile (# …) am Anfang fällt weg. '
      + 'Schließt den Persona-Block im Antwort-Prompt der Muster-Engine ab.',

    // ── Kopfangaben ─────────────────────────────────────────────────
    'feld.PersonaFrontmatter.element.label': 'Art',
    'feld.PersonaFrontmatter.element.hint': 'Art des Bausteins, hier persona. Nur beschreibend.',
    'feld.PersonaFrontmatter.id.label': 'Kennung',
    'feld.PersonaFrontmatter.id.hint':
      'Kennung wie P-LEH; der Klassifikator vergibt sie, und manche Regeln im Code hängen an '
      + 'ihr (P-AND ist der Rückfall). Der Dokumentname muss passen (P-LEH → leh), sonst '
      + 'fehlen ihre Angaben im Antwort-Prompt.',
    'feld.PersonaFrontmatter.label.label': 'Anzeigename',
    'feld.PersonaFrontmatter.label.hint':
      'Name wie „Lehrkraft“. Steht im Klassifikator- und im Antwort-Prompt, in den '
      + 'Qualitätslogs und in der Anrede-Liste der Agent-Schleife.',
    'feld.PersonaFrontmatter.description.label': 'Kurzbeschreibung',
    'feld.PersonaFrontmatter.description.hint':
      'Ein Satz zur Zielgruppe und ihrer Ansprache. Hilft dem Klassifikator bei der Zuordnung '
      + 'und steht im Persona-Block des Antwort-Prompts; auch die Evaluation liest ihn.',
    'feld.PersonaFrontmatter.tone.label': 'Ton',
    'feld.PersonaFrontmatter.tone.hint':
      'Grundton, etwa kollegial, warm oder formell. Steht im Persona-Block und gilt statt des '
      + 'Mustertons, wenn das Muster sachlich, neutral oder nichts vorgibt oder „Vorrang vor '
      + 'Muster“ gesetzt ist; leer: locker.',
    'feld.PersonaFrontmatter.length_bias.label': 'Längen-Neigung',
    'feld.PersonaFrontmatter.length_bias.hint':
      'Verschiebt die Länge aus dem Muster: über +0,15 eine Stufe länger, unter −0,15 eine '
      + 'kürzer (kurz, mittel, lang). Begrenzt auf −0,3 bis +0,3; die Zahl steht zusätzlich im '
      + 'Persona-Block.',
    'feld.PersonaFrontmatter.formality.label': 'Anrede',
    'feld.PersonaFrontmatter.formality.hint':
      'Wie der Bot anredet: siezen, duzen, neutral (ohne direkte Anrede) oder wie_user '
      + '(Vorgabe je Zielgruppe unter Anzeige → Geräte). Wirkt auch in der Agent-Schleife; die '
      + 'Muster-Engine liest neutral wie wie_user.',
    'feld.PersonaFrontmatter.card_text_mode.label': 'Kacheltext-Modus',
    'feld.PersonaFrontmatter.card_text_mode.hint':
      'Umgang mit Materialkacheln: minimal verlangt eine kurze Einleitung ohne wiederholte '
      + 'Titel, reference nennt Materialien im Text, ordnet sie ein und verlinkt sie, highlight '
      + 'hebt ein bis zwei begründet hervor. explanation aus älteren Ständen gilt als '
      + 'highlight; leer oder unbekannt: minimal.',
    'feld.PersonaFrontmatter.override.label': 'Vorrang vor Muster',
    'feld.PersonaFrontmatter.override.hint':
      'Ist es gesetzt, gelten Ton und Kacheltext-Modus der Zielgruppe auch dann, wenn das '
      + 'Muster eigene vorgibt. Länge und Anrede betrifft es nicht, sie wirken immer.',
    'feld.PersonaFrontmatter.positive_markers.label': 'Positiv-Marker',
    'feld.PersonaFrontmatter.positive_markers.hint':
      'Wörter und Wendungen, an denen der Klassifikator die Zielgruppe erkennt, etwa „meine '
      + 'Klasse“. Bis zu 40 stehen im Klassifikator-Prompt; die Evaluation baut daraus '
      + 'Testgespräche.',
    'feld.PersonaFrontmatter.anti_markers.label': 'Anti-Marker',
    'feld.PersonaFrontmatter.anti_markers.hint':
      'Wendungen, die nicht für diese Zielgruppe sprechen, wahlweise mit Umleitung auf eine '
      + 'andere. Bis zu 20 stehen je Zeile mit Umleitung, Bedingung und Begründung im '
      + 'Klassifikator-Prompt, als Schutz vor Fehlzuordnung.',
    'feld.AntiMarker.phrase.label': 'Wendung',
    'feld.AntiMarker.phrase.hint':
      'Die Wendung selbst, etwa „mein Kind“; ohne sie entfällt der Eintrag. Sie steht wörtlich '
      + 'im Klassifikator-Prompt, Varianten mit | liest nur das Modell.',
    'feld.AntiMarker.redirect_to.label': 'Umleiten auf',
    'feld.AntiMarker.redirect_to.hint':
      'Die Zielgruppe, die stattdessen gemeint ist, etwa P-ELT. Steht als Pfeil hinter der '
      + 'Wendung im Klassifikator-Prompt; leer heißt: kein Treffer für diese Zielgruppe, ohne '
      + 'Ziel — wie es gemeint ist, sagt dann die Begründung.',
    'feld.AntiMarker.rationale.label': 'Begründung',
    'feld.AntiMarker.rationale.hint':
      'Warum die Wendung täuscht, etwa „Allein kein Lehrkraft-Signal“. Steht hinter der '
      + 'Wendung im Klassifikator-Prompt; bei Einträgen ohne Umleitung sagt erst sie, wie der '
      + 'Eintrag gemeint ist.',
    'feld.AntiMarker.when.label': 'Bedingung',
    'feld.AntiMarker.when.hint':
      'Einschränkung, wann der Eintrag gilt, etwa „ohne Klassenbezug“. Steht als „(wenn …)“ '
      + 'hinter der Wendung im Klassifikator-Prompt; der Code prüft sie nicht, das Modell liest '
      + 'sie.',
    'feld.PersonaFrontmatter.discriminators.label': 'Abgrenzungen',
    'feld.PersonaFrontmatter.discriminators.hint':
      'Unterscheidung von leicht verwechselbaren Zielgruppen. Bis zu acht stehen mit Kennung '
      + 'und Regel im Klassifikator-Prompt; die Beispiele stehen dort nicht.',
    'feld.PersonaDiscriminator.vs.label': 'Andere Zielgruppe',
    'feld.PersonaDiscriminator.vs.hint':
      'Die Zielgruppe, gegen die abgegrenzt wird, etwa P-LER. Ohne sie entfällt der Eintrag.',
    'feld.PersonaDiscriminator.rule.label': 'Regel',
    'feld.PersonaDiscriminator.rule.hint':
      'Woran sich beide unterscheiden, etwa „ich plane“ gegen „ich lerne“. Steht hinter der '
      + 'Kennung im Klassifikator-Prompt.',
    'feld.PersonaDiscriminator.example_a.label': 'Beispiel',
    'feld.PersonaDiscriminator.example_a.hint':
      'Beispielsatz, der zu dieser Zielgruppe gehört. Nur beschreibend: der '
      + 'Klassifikator-Prompt enthält ihn nicht.',
    'feld.PersonaDiscriminator.example_b.label': 'Gegenbeispiel',
    'feld.PersonaDiscriminator.example_b.hint':
      'Beispielsatz, der zur anderen Zielgruppe gehört. Nur beschreibend: der '
      + 'Klassifikator-Prompt enthält ihn nicht.',
    'feld.PersonaFrontmatter.goals.label': 'Ziele',
    'feld.PersonaFrontmatter.goals.hint':
      'Was die Zielgruppe erreichen will, je Zeile ein Ziel. Steht als Liste „Ziele“ im '
      + 'Persona-Block des Antwort-Prompts.',
    'feld.PersonaFrontmatter.rules.label': 'Regeln',
    'feld.PersonaFrontmatter.rules.hint':
      'Antwortregeln für diese Zielgruppe, etwa „Max. 1 Rückfrage pro Turn“. Stehen als Liste '
      + 'im Persona-Block des Antwort-Prompts; die Evaluation liest die ersten sechs.',
    'feld.PersonaFrontmatter.typical_intents.label': 'Typische Anliegen',
    'feld.PersonaFrontmatter.typical_intents.hint':
      'Intents, mit denen die Zielgruppe meist kommt, etwa I03. Wird derzeit nicht ausgewertet.',
  },
  en: {
    // ── Document ────────────────────────────────────────────────────
    'feld.PersonaArea.frontmatter.label': 'Header',
    'feld.PersonaArea.frontmatter.hint':
      'Markers for the classifier plus tone, form of address and rules for the answer. '
      + 'Effective in the pattern engine; the agent loop uses only the display name and the '
      + 'form of address.',
    'feld.PersonaArea.body.label': 'Full description',
    'feld.PersonaArea.body.hint':
      'Portrait of the persona in Markdown; a leading title line (# …) is dropped. It closes '
      + 'the persona block in the answer prompt of the pattern engine.',

    // ── Header ──────────────────────────────────────────────────────
    'feld.PersonaFrontmatter.element.label': 'Kind',
    'feld.PersonaFrontmatter.element.hint':
      'Kind of building block, here persona. Descriptive only.',
    'feld.PersonaFrontmatter.id.label': 'Identifier',
    'feld.PersonaFrontmatter.id.hint':
      'Identifier such as P-LEH; the classifier assigns it, and some rules in the code depend '
      + 'on it (P-AND is the fallback). The document name must match (P-LEH → leh), otherwise '
      + 'its details are missing from the answer prompt.',
    'feld.PersonaFrontmatter.label.label': 'Display name',
    'feld.PersonaFrontmatter.label.hint':
      'Name such as “Lehrkraft”. Appears in the classifier and answer prompts, in the quality '
      + 'logs and in the agent loop’s list of forms of address.',
    'feld.PersonaFrontmatter.description.label': 'Short description',
    'feld.PersonaFrontmatter.description.hint':
      'One sentence about the persona and how to address it. Helps the classifier assign it '
      + 'and appears in the persona block of the answer prompt; the evaluation reads it too.',
    'feld.PersonaFrontmatter.tone.label': 'Tone',
    'feld.PersonaFrontmatter.tone.hint':
      'Base tone, such as kollegial, warm or formell. Appears in the persona block and replaces '
      + 'the pattern tone when the pattern sets sachlich, neutral or nothing, or when '
      + '“Override pattern” is set; empty: locker.',
    'feld.PersonaFrontmatter.length_bias.label': 'Length bias',
    'feld.PersonaFrontmatter.length_bias.hint':
      'Shifts the length set by the pattern: above +0.15 one step longer, below −0.15 one step '
      + 'shorter (kurz, mittel, lang). Limited to −0.3 to +0.3; the number also appears in the '
      + 'persona block.',
    'feld.PersonaFrontmatter.formality.label': 'Form of address',
    'feld.PersonaFrontmatter.formality.hint':
      'How the bot addresses people: siezen (formal), duzen (informal), neutral (no direct '
      + 'address) or wie_user (per-persona default under Display → Devices). The agent loop '
      + 'uses it too; the pattern engine reads neutral as wie_user.',
    'feld.PersonaFrontmatter.card_text_mode.label': 'Card text mode',
    'feld.PersonaFrontmatter.card_text_mode.hint':
      'Handling of material cards: minimal asks for a short intro without repeated titles, '
      + 'reference names, places and links materials in the text, highlight singles out one or '
      + 'two with a reason. explanation from older versions counts as highlight; empty or '
      + 'unknown: minimal.',
    'feld.PersonaFrontmatter.override.label': 'Override pattern',
    'feld.PersonaFrontmatter.override.hint':
      'When set, the persona’s tone and card text mode apply even if the pattern specifies its '
      + 'own. Length and form of address are not affected; they always apply.',
    'feld.PersonaFrontmatter.positive_markers.label': 'Positive markers',
    'feld.PersonaFrontmatter.positive_markers.hint':
      'Words and phrases by which the classifier recognises the persona, such as “meine '
      + 'Klasse”. Up to 40 appear in the classifier prompt; the evaluation builds test '
      + 'dialogues from them.',
    'feld.PersonaFrontmatter.anti_markers.label': 'Anti-markers',
    'feld.PersonaFrontmatter.anti_markers.hint':
      'Phrases that do not indicate this persona, optionally with a redirect to another one. '
      + 'Up to 20 appear one per line with redirect, condition and rationale in the classifier '
      + 'prompt, as protection against misassignment.',
    'feld.AntiMarker.phrase.label': 'Phrase',
    'feld.AntiMarker.phrase.hint':
      'The phrase itself, such as “mein Kind”; without it the entry is dropped. It appears '
      + 'verbatim in the classifier prompt; variants separated by | are read only by the model.',
    'feld.AntiMarker.redirect_to.label': 'Redirect to',
    'feld.AntiMarker.redirect_to.hint':
      'The persona meant instead, such as P-ELT. Appears as an arrow after the phrase in the '
      + 'classifier prompt; empty means: no match for this persona, without a target — the '
      + 'rationale then says how it is meant.',
    'feld.AntiMarker.rationale.label': 'Rationale',
    'feld.AntiMarker.rationale.hint':
      'Why the phrase is misleading, such as “Allein kein Lehrkraft-Signal” (alone no teacher '
      + 'signal). Appears after the phrase in the classifier prompt; for entries without a '
      + 'redirect it is what says how the entry is meant.',
    'feld.AntiMarker.when.label': 'Condition',
    'feld.AntiMarker.when.hint':
      'Restriction on when the entry applies, such as “ohne Klassenbezug”. Appears as “(wenn '
      + '…)” after the phrase in the classifier prompt; the code does not check it, the model '
      + 'reads it.',
    'feld.PersonaFrontmatter.discriminators.label': 'Distinctions',
    'feld.PersonaFrontmatter.discriminators.hint':
      'How to tell the persona apart from easily confused ones. Up to eight appear with '
      + 'identifier and rule in the classifier prompt; the examples do not.',
    'feld.PersonaDiscriminator.vs.label': 'Other persona',
    'feld.PersonaDiscriminator.vs.hint':
      'The persona it is distinguished from, such as P-LER. Without it the entry is dropped.',
    'feld.PersonaDiscriminator.rule.label': 'Rule',
    'feld.PersonaDiscriminator.rule.hint':
      'What tells the two apart, such as “ich plane” versus “ich lerne”. Appears after the '
      + 'identifier in the classifier prompt.',
    'feld.PersonaDiscriminator.example_a.label': 'Example',
    'feld.PersonaDiscriminator.example_a.hint':
      'Example sentence that belongs to this persona. Descriptive only: the classifier prompt '
      + 'does not contain it.',
    'feld.PersonaDiscriminator.example_b.label': 'Counterexample',
    'feld.PersonaDiscriminator.example_b.hint':
      'Example sentence that belongs to the other persona. Descriptive only: the classifier '
      + 'prompt does not contain it.',
    'feld.PersonaFrontmatter.goals.label': 'Goals',
    'feld.PersonaFrontmatter.goals.hint':
      'What the persona wants to achieve, one goal per line. Appears as the “Ziele” (goals) '
      + 'list in the persona block of the answer prompt.',
    'feld.PersonaFrontmatter.rules.label': 'Rules',
    'feld.PersonaFrontmatter.rules.hint':
      'Answer rules for this persona, such as “At most one follow-up question per turn”. Appear '
      + 'as a list in the persona block of the answer prompt; the evaluation reads the first six.',
    'feld.PersonaFrontmatter.typical_intents.label': 'Typical intents',
    'feld.PersonaFrontmatter.typical_intents.hint':
      'Intents the persona usually comes with, such as I03. Currently not evaluated.',
  },
};
