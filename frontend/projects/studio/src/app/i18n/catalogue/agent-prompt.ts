/**
 * Die Vorschau „Was das Modell zuerst liest“ (ST-8d) auf der Seite „Agent &
 * Maschine“: der Abschnitt und die Glieder der Kette eines Chat-Zugs.
 *
 * Aus `agent-center.ts` herausgelöst (Paket 7), als jene Datei die Größen-
 * Richtlinie erreichte und der Seitenkontext zwei Glieder bekam. Die Kennungen
 * der Glieder spiegeln `agent_prompt_preview.JE_ZUG` im Backend.
 */
import type { CataloguePart } from './catalogue-part';

export const AGENT_PROMPT: CataloguePart = {
  de: {
    'curated.agent.prompt.label': 'Was das Modell zuerst liest',
    'curated.agent.prompt.hint':
      'Der Anfang der Kette eines Chat-Zugs im Agent-Modus: eigene Regeln, dann der '
      + 'Master-Skill, dann was jeder Zug dazulegt.',
    'agentPrompt.language': 'Widget-Sprache',
    'agentPrompt.language.de': 'Deutsch',
    'agentPrompt.language.en': 'Englisch',
    'agentPrompt.loading': 'Vorschau wird gebaut …',
    'agentPrompt.intro':
      'Die ersten beiden Glieder stehen in jedem Zug gleich da und liegen im gecachten Anfang; '
      + 'die übrigen hängen am einzelnen Zug.',
    'agentPrompt.showText': 'Wortlaut anzeigen',
    'agentPrompt.textLabel': 'Wortlaut: {name}',
    'agentPrompt.chars.one': '{n} Zeichen',
    'agentPrompt.chars.other': '{n} Zeichen',
    'agentPrompt.checksum': '{chars} im Prompt · Prüfsumme des Dokuments {sum}',
    'agentPrompt.skill.off': 'Aus: der Agent arbeitet ohne Master-Skill.',
    'agentPrompt.skill.no_node': 'An, aber kein Knoten gepflegt (MASTER_SKILL_NODE_ID).',
    'agentPrompt.skill.failed': 'An, aber nicht geladen: {error}. Der Zug läuft ohne.',
    'agentPrompt.step.head': 'Kopf: Rolle, Anrede, Grenzen, Sprache',
    'agentPrompt.step.master_skill': 'Master-Skill',
    'agentPrompt.step.result_schema': 'Satz zum Ergebnis-Schema',
    'agentPrompt.when.result_schema':
      'Wird an den Kopf gehängt, wenn die Einbettung ein Ergebnis-Schema erklärt.',
    'agentPrompt.step.host_capabilities': 'Grenzen der Einbettung',
    'agentPrompt.when.host_capabilities':
      'Wenn die Einbettung etwas einschränkt (tool-mode, Gliederung der Ergebnisse).',
    // Paket B (Plan 2026-09-29, umgesetzt in Paket 7): der Seitenkontext in zwei
    // Gliedern — Regeln im gecachten Systemteil, Daten gerahmt vor dem Verlauf.
    'agentPrompt.step.page_rules': 'Regeln zum Seitenkontext',
    'agentPrompt.when.page_rules':
      'Wenn die Seite Kontext liefert: ein fester Text, für jede Seite gleich — deshalb im '
      + 'gecachten Systemteil.',
    'agentPrompt.step.host_instruction': 'Auftrag der Gastanwendung',
    'agentPrompt.when.host_instruction': 'Wenn die einbettende Anwendung einen Auftrag mitgibt.',
    'agentPrompt.step.skill_hints': 'Hinweis auf Skills aus dem Gespräch',
    'agentPrompt.when.skill_hints': 'Wenn das Gespräch freigegebene Skills kennt oder einer läuft.',
    'agentPrompt.step.page_data': 'Seitenkontext (Daten)',
    'agentPrompt.when.page_data':
      'Wenn die Seite eine Sammlung, einen Inhalt, eine Themenseite oder sichtbaren Text '
      + 'liefert: als Daten gerahmt, als erste Nachricht nach dem Systemteil — vor dem '
      + 'vorab geholten Katalog und dem Verlauf.',
    'agentPrompt.step.history': 'Verlauf',
    'agentPrompt.when.history': 'Bis zu zehn frühere Nachrichten, in der Größe gedeckelt.',
    'agentPrompt.step.prefetch': 'Vorab geholter Freigabe-Katalog',
    'agentPrompt.when.prefetch':
      'Wenn die Seite eine Sammlung zeigt: ihre Skills, bevor das Modell danach fragen könnte.',
    'agentPrompt.step.last_shown': 'Zuletzt gezeigt',
    'agentPrompt.when.last_shown':
      'Wenn die Person in den letzten drei Antworten etwas gesehen hat: die angezeigten Karten mit '
      + 'Kennung und bis zu drei Dokumente (zusammen höchstens 6 000 Zeichen, Kürzungen vermerkt) — '
      + 'als Daten gerahmt am Anfang ihrer Nachricht, für Bezüge wie „der erste Treffer“.',
    'agentPrompt.step.message': 'Nachricht der Person',
    'agentPrompt.when.message': 'Immer, als letztes Glied.',
    // Paket 9: gezählt wie für eine Person ohne Anmeldung (``schreiben_erlaubt``).
    'agentPrompt.tools.one':
      'Dazu geht {count} Werkzeug-Beschreibung mit {chars} Zeichen mit — in jeder Runde; '
      + 'gezählt für eine Person ohne Anmeldung (angemeldet kommen die schreibenden dazu).',
    'agentPrompt.tools.other':
      'Dazu gehen {count} Werkzeug-Beschreibungen mit {chars} Zeichen mit — in jeder Runde; '
      + 'gezählt für eine Person ohne Anmeldung (angemeldet kommen die schreibenden dazu).',
  },
  en: {
    'curated.agent.prompt.label': 'What the model reads first',
    'curated.agent.prompt.hint':
      'The start of the chain of a chat turn in agent mode: our own rules, then the master '
      + 'skill, then what each turn adds.',
    'agentPrompt.language': 'Widget language',
    'agentPrompt.language.de': 'German',
    'agentPrompt.language.en': 'English',
    'agentPrompt.loading': 'Building the preview …',
    'agentPrompt.intro':
      'The first two links are the same in every turn and sit in the cached start; the others '
      + 'depend on the single turn.',
    'agentPrompt.showText': 'Show the wording',
    'agentPrompt.textLabel': 'Wording: {name}',
    'agentPrompt.chars.one': '{n} character',
    'agentPrompt.chars.other': '{n} characters',
    'agentPrompt.checksum': '{chars} in the prompt · document checksum {sum}',
    'agentPrompt.skill.off': 'Off: the agent works without the master skill.',
    'agentPrompt.skill.no_node': 'On, but no node maintained (MASTER_SKILL_NODE_ID).',
    'agentPrompt.skill.failed': 'On, but not loaded: {error}. The turn runs without it.',
    'agentPrompt.step.head': 'Head: role, form of address, limits, language',
    'agentPrompt.step.master_skill': 'Master skill',
    'agentPrompt.step.result_schema': 'Sentence on the result schema',
    'agentPrompt.when.result_schema':
      'Appended to the head when the embedding declares a result schema.',
    'agentPrompt.step.host_capabilities': 'Limits of the embedding',
    'agentPrompt.when.host_capabilities':
      'When the embedding restricts something (tool-mode, grouping of results).',
    'agentPrompt.step.page_rules': 'Rules for the page context',
    'agentPrompt.when.page_rules':
      'When the page provides context: one fixed text, the same for every page — hence in the '
      + 'cached system part.',
    'agentPrompt.step.host_instruction': 'Task of the host application',
    'agentPrompt.when.host_instruction': 'When the embedding application passes a task.',
    'agentPrompt.step.skill_hints': 'Hint at skills from the conversation',
    'agentPrompt.when.skill_hints': 'When the conversation knows approved skills or one is running.',
    'agentPrompt.step.page_data': 'Page context (data)',
    'agentPrompt.when.page_data':
      'When the page shows a collection, a content item, a topic page or visible text: framed '
      + 'as data, as the first message after the system part — before the prefetched '
      + 'catalogue and the history.',
    'agentPrompt.step.history': 'History',
    'agentPrompt.when.history': 'Up to ten earlier messages, capped in size.',
    'agentPrompt.step.prefetch': 'Prefetched approval catalogue',
    'agentPrompt.when.prefetch':
      'When the page shows a collection: its skills, before the model could ask for them.',
    'agentPrompt.step.last_shown': 'Last shown',
    'agentPrompt.when.last_shown':
      'When the person saw something in the last three answers: the cards shown, with their '
      + 'identifiers, and up to three documents (6,000 characters in total, cuts marked) — framed '
      + 'as data at the start of their message, for references like “the first hit”.',
    'agentPrompt.step.message': 'The person’s message',
    'agentPrompt.when.message': 'Always, as the last link.',
    'agentPrompt.tools.one':
      'Plus {count} tool description with {chars} characters — in every round; counted for '
      + 'a person who is not signed in (signed-in people also get the writing tools).',
    'agentPrompt.tools.other':
      'Plus {count} tool descriptions with {chars} characters — in every round; counted for '
      + 'a person who is not signed in (signed-in people also get the writing tools).',
  },
};
