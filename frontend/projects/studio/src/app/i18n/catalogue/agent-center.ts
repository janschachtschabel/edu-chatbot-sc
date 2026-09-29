/**
 * Die Agent-Steuerzentrale (ST-8): die Panels, die ST-8 auf der Seite „Agent &
 * Maschine" neben Umschalter, Master-Skill und Tester stellt.
 *
 * Die Abschnittstexte (`curated.agent.*`) stehen hier und nicht in `curated.ts`:
 * jene Datei liegt schon über der Größen-Richtlinie (Aufräumpunkt im Plan).
 */
import type { CataloguePart } from './catalogue-part';

export const AGENT_CENTER: CataloguePart = {
  de: {
    'curated.agent.tools.label': 'Werkzeuge und Sperren',
    'curated.agent.tools.hint':
      'Welche Werkzeuge der Agent in einem Chat-Zug bekommt und was ihm eines davon nehmen '
      + 'kann. Nur lesend.',

    'agentTools.loading': 'Werkzeugliste wird geladen …',
    'agentTools.summary.one':
      'Ein gewöhnlicher Chat-Zug im Agent-Modus bekommt {offered} von {count} Werkzeug.',
    'agentTools.summary.other':
      'Ein gewöhnlicher Chat-Zug im Agent-Modus bekommt {offered} von {count} Werkzeugen.',
    'agentTools.caption':
      'Werkzeuge der Agent-Schleife nach Art: ob ein gewöhnlicher Zug sie bekommt und wann sie '
      + 'fehlen. Gesperrt wird, wo die Sperre steht — diese Liste ändert nichts.',
    'agentTools.col.tool': 'Werkzeug',
    'agentTools.col.offered': 'Im Zug',
    'agentTools.col.locks': 'Wann es fehlt',
    'agentTools.offered.yes': 'ja',
    'agentTools.offered.no': 'nein',
    'agentTools.noLocks': 'immer dabei',
    'agentTools.diversion':
      'Erkennt die Sicherheitsprüfung eine Krise, eine Drohung oder eine harte Sperre der '
      + 'Moderation, antwortet statt der Schleife das Schutzmuster — in diesem Zug gibt es dann '
      + 'kein Werkzeug. Die Sperren unten gelten für Züge, in denen die Schleife antwortet.',
    'agentTools.group.read': 'Lesend',
    'agentTools.group.read.hint': 'Repositorium und Web',
    'agentTools.group.curation': 'Kuratierend',
    'agentTools.group.curation.hint': 'schreiben im Repositorium, brauchen einen hinterlegten Zugang',
    'agentTools.group.virtual': 'Virtuell',
    'agentTools.group.virtual.hint': 'beantwortet der Server selbst, nicht sperrbar',
    'agentTools.pageLink': 'Seite {page}',
    'agentTools.signal.pii': 'persönliche Daten in der Nachricht',
    'agentTools.lock.never': 'Nie angeboten: der Weg zu einer Anleitung führt über ihre Sammlung.',
    'agentTools.lock.needsAccess': 'Fehlt ohne hinterlegten Zugang zum Repositorium.',
    'agentTools.lock.toolMode': 'Fehlt in Einbettungen mit tool-mode {modes}.',
    'agentTools.lock.safetyFixed':
      'Fällt weg, wenn das Regex-Gate {signals} erkennt (fest im Code).',
    'agentTools.lock.policy.one': 'Fällt weg, wenn die Policy-Regel {rules} greift.',
    'agentTools.lock.policy.other': 'Fällt weg, wenn eine der Policy-Regeln {rules} greift.',
    'agentTools.lock.knowledgeAreas': 'Nur mit mindestens einem Wissensbereich für den Agenten.',
    'agentTools.lock.hostSchema': 'Nur wenn die Einbettung ein Ergebnis-Schema erklärt.',

    'curated.agent.skills.label': 'Skill-Verzeichnis',
    'curated.agent.skills.hint':
      'Welche Skills eine Sammlung für den Agenten freigibt — aus ihrem Registry-Dokument im '
      + 'Repositorium.',
    'agentSkills.field': 'Sammlungs-ID',
    'agentSkills.fieldHint':
      'Die Kennung (nodeId) einer Sammlung — in der Adresse ihrer Seite im Repositorium '
      + 'hinter „id=“.',
    'agentSkills.lookup': 'Skills anzeigen',
    'agentSkills.loading': 'Wird geholt …',
    'agentSkills.error.empty': 'Bitte eine Sammlungs-ID eingeben.',
    'agentSkills.error.format':
      'Nur die Kennung: Buchstaben, Ziffern und Bindestriche, höchstens 64 Zeichen — ohne '
      + 'Adresse drumherum.',
    'agentSkills.loaded': 'Verzeichnis geladen.',
    'agentSkills.document': 'Registry-Dokument:',
    'agentSkills.newTab': '(öffnet einen neuen Tab)',
    'agentSkills.count.one': '{count} freigegebener Skill',
    'agentSkills.count.other': '{count} freigegebene Skills',
    'agentSkills.truncated':
      'Die Liste ist womöglich unvollständig: der Server hat die Suche oder die Liste gekappt.',
    'agentSkills.context': 'Kontext: {context}',
    'agentSkills.keywords': 'Stichworte: {keywords}',
    'agentSkills.unresolved': 'Im Dokument genannt, aber nicht gefunden',
    'agentSkills.unresolvedNoNode': '{title} — ohne Kennung im Dokument',
    'agentSkills.reason.no_registry':
      'Diese Sammlung führt kein Registry-Dokument — sie gibt keine Skills frei.',
    'agentSkills.reason.collection_not_found': 'Eine Sammlung mit dieser Kennung gibt es nicht.',
    'agentSkills.reason.unreadable': 'Das Registry-Dokument ließ sich nicht lesen.',
    'agentSkills.reason.unknown': 'Kein Verzeichnis ({reason}).',
    'agentSkills.mode': 'Suchen nach',
    'agentSkills.mode.collection': 'Sammlungs-ID',
    'agentSkills.mode.term': 'Suchbegriff',
    'agentSkills.termField': 'Suchbegriff',
    'agentSkills.termHint': 'Findet Skills im Bestand des MCP-Servers, unabhängig von einer Sammlung.',
    'agentSkills.search': 'Skills suchen',
    'agentSkills.searching': 'Wird gesucht …',
    'agentSkills.error.termEmpty': 'Bitte einen Suchbegriff eingeben.',
    'agentSkills.error.termLong': 'Höchstens {max} Zeichen.',
    'agentSkills.searchOff':
      'Die Suche per Suchbegriff ist auf dem MCP-Server nicht aktiv — weiter geht es über die '
      + 'Kennung einer Sammlung.',
    'agentSkills.found.one': '{count} Skill gefunden',
    'agentSkills.found.other': '{count} Skills gefunden',
    'agentSkills.noHits': 'Keine Skills zu „{query}“ gefunden.',
    'agentSkills.searchTruncated':
      'Es können mehr als {count} Skills passen; ein genauerer Suchbegriff grenzt die Liste ein.',
    'agentSkills.edit': 'Bearbeiten',
    'agentSkills.editOf': ': {title} im Editor',

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
    'agentPrompt.step.page_context': 'Seitenkontext',
    'agentPrompt.when.page_context':
      'Wenn die Seite eine Sammlung, einen Inhalt oder eine Themenseite zeigt.',
    'agentPrompt.step.host_instruction': 'Auftrag der Gastanwendung',
    'agentPrompt.when.host_instruction': 'Wenn die einbettende Anwendung einen Auftrag mitgibt.',
    'agentPrompt.step.skill_hints': 'Hinweis auf Skills aus dem Gespräch',
    'agentPrompt.when.skill_hints': 'Wenn das Gespräch freigegebene Skills kennt oder einer läuft.',
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
    'agentPrompt.tools.one':
      'Dazu geht {count} Werkzeug-Beschreibung mit {chars} Zeichen mit — in jeder Runde.',
    'agentPrompt.tools.other':
      'Dazu gehen {count} Werkzeug-Beschreibungen mit {chars} Zeichen mit — in jeder Runde.',
  },
  en: {
    'curated.agent.tools.label': 'Tools and locks',
    'curated.agent.tools.hint':
      'Which tools the agent gets in a chat turn and what can take one of them away. '
      + 'Read-only.',

    'agentTools.loading': 'Loading the tool list …',
    'agentTools.summary.one': 'A plain chat turn in agent mode gets {offered} of {count} tool.',
    'agentTools.summary.other': 'A plain chat turn in agent mode gets {offered} of {count} tools.',
    'agentTools.caption':
      'Tools of the agent loop by kind: whether a plain turn gets them and when they are '
      + 'missing. A lock is set where it lives — this list changes nothing.',
    'agentTools.col.tool': 'Tool',
    'agentTools.col.offered': 'In the turn',
    'agentTools.col.locks': 'When it is missing',
    'agentTools.offered.yes': 'yes',
    'agentTools.offered.no': 'no',
    'agentTools.noLocks': 'always there',
    'agentTools.diversion':
      'If the safety check detects a crisis, a threat or a hard block by the moderation, the '
      + 'protective pattern answers instead of the loop — that turn has no tool at all. The locks '
      + 'below apply to turns the loop answers.',
    'agentTools.group.read': 'Reading',
    'agentTools.group.read.hint': 'repository and web',
    'agentTools.group.curation': 'Curating',
    'agentTools.group.curation.hint': 'write to the repository, need a stored access',
    'agentTools.group.virtual': 'Virtual',
    'agentTools.group.virtual.hint': 'answered by the server itself, cannot be locked',
    'agentTools.pageLink': 'Page {page}',
    'agentTools.signal.pii': 'personal data in the message',
    'agentTools.lock.never': 'Never offered: the way to a guide leads through its collection.',
    'agentTools.lock.needsAccess': 'Missing without a stored access to the repository.',
    'agentTools.lock.toolMode': 'Missing in embeddings with tool-mode {modes}.',
    'agentTools.lock.safetyFixed':
      'Dropped when the regex gate detects {signals} (fixed in code).',
    'agentTools.lock.policy.one': 'Dropped when the policy rule {rules} applies.',
    'agentTools.lock.policy.other': 'Dropped when one of the policy rules {rules} applies.',
    'agentTools.lock.knowledgeAreas': 'Only with at least one knowledge area for the agent.',
    'agentTools.lock.hostSchema': 'Only when the embedding declares a result schema.',

    'curated.agent.skills.label': 'Skill directory',
    'curated.agent.skills.hint':
      'Which skills a collection approves for the agent — from its registry document in the '
      + 'repository.',
    'agentSkills.field': 'Collection ID',
    'agentSkills.fieldHint':
      'The identifier (nodeId) of a collection — in the address of its page in the repository, '
      + 'after “id=”.',
    'agentSkills.lookup': 'Show skills',
    'agentSkills.loading': 'Fetching …',
    'agentSkills.error.empty': 'Please enter a collection ID.',
    'agentSkills.error.format':
      'Only the identifier: letters, digits and hyphens, at most 64 characters — without the '
      + 'address around it.',
    'agentSkills.loaded': 'Directory loaded.',
    'agentSkills.document': 'Registry document:',
    'agentSkills.newTab': '(opens a new tab)',
    'agentSkills.count.one': '{count} approved skill',
    'agentSkills.count.other': '{count} approved skills',
    'agentSkills.truncated':
      'The list may be incomplete: the server capped the search or the list.',
    'agentSkills.context': 'Context: {context}',
    'agentSkills.keywords': 'Keywords: {keywords}',
    'agentSkills.unresolved': 'Named in the document but not found',
    'agentSkills.unresolvedNoNode': '{title} — no identifier in the document',
    'agentSkills.reason.no_registry':
      'This collection has no registry document — it approves no skills.',
    'agentSkills.reason.collection_not_found': 'There is no collection with this identifier.',
    'agentSkills.reason.unreadable': 'The registry document could not be read.',
    'agentSkills.reason.unknown': 'No directory ({reason}).',
    'agentSkills.mode': 'Search by',
    'agentSkills.mode.collection': 'Collection ID',
    'agentSkills.mode.term': 'Search term',
    'agentSkills.termField': 'Search term',
    'agentSkills.termHint': 'Finds skills the MCP server knows about, independent of any collection.',
    'agentSkills.search': 'Search skills',
    'agentSkills.searching': 'Searching …',
    'agentSkills.error.termEmpty': 'Please enter a search term.',
    'agentSkills.error.termLong': 'At most {max} characters.',
    'agentSkills.searchOff':
      'Search by term is not active on the MCP server — continue with the identifier of a '
      + 'collection.',
    'agentSkills.found.one': '{count} skill found',
    'agentSkills.found.other': '{count} skills found',
    'agentSkills.noHits': 'No skills found for “{query}”.',
    'agentSkills.searchTruncated': 'More than {count} skills may match; a more specific term narrows the list.',
    'agentSkills.edit': 'Edit',
    'agentSkills.editOf': ': {title} in the editor',

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
    'agentPrompt.step.page_context': 'Page context',
    'agentPrompt.when.page_context': 'When the page shows a collection, a content item or a topic page.',
    'agentPrompt.step.host_instruction': 'Task of the host application',
    'agentPrompt.when.host_instruction': 'When the embedding application passes a task.',
    'agentPrompt.step.skill_hints': 'Hint at skills from the conversation',
    'agentPrompt.when.skill_hints': 'When the conversation knows approved skills or one is running.',
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
      'Plus {count} tool description with {chars} characters — in every round.',
    'agentPrompt.tools.other':
      'Plus {count} tool descriptions with {chars} characters — in every round.',
  },
};
