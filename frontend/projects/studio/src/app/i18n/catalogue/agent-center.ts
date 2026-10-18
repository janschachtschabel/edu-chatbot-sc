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
      + 'kann. Die Spalte „Anbieten“ schaltet Werkzeuge der MCP-Server ein und aus.',

    'agentTools.loading': 'Werkzeugliste wird geladen …',
    'agentTools.summary.one':
      'Ein gewöhnlicher Chat-Zug im Agent-Modus bekommt {offered} von {count} Werkzeug.',
    'agentTools.summary.other':
      'Ein gewöhnlicher Chat-Zug im Agent-Modus bekommt {offered} von {count} Werkzeugen.',
    'agentTools.caption':
      'Werkzeuge der Agent-Schleife nach Art: ob ein gewöhnlicher Zug sie bekommt und wann sie '
      + 'fehlen. „Anbieten“ schreibt die Server-Liste; jede andere Sperre wird dort gepflegt, '
      + 'wo sie steht.',
    'agentTools.col.tool': 'Werkzeug',
    'agentTools.col.herkunft': 'Herkunft',
    'agentTools.col.anbieten': 'Anbieten',
    'agentTools.herkunft.eingebaut': 'Eingebaut',
    'agentTools.herkunft.wlo': 'WLO-MCP',
    'agentTools.herkunft.fremd': 'Fremd-MCP',
    'agentTools.schalter': '{name} dem Modell anbieten',
    'agentTools.schalter.fest': 'fest',
    'agentTools.schalter.laedt': 'wird geladen …',
    'agentTools.schalter.unbekannt': 'unbekannt',
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
    'agentTools.group.external': 'Extern',
    'agentTools.group.external.hint':
      'lesende Werkzeuge weiterer MCP-Server, übernommen unter Wissen → MCP-Server',
    'agentTools.group.virtual': 'Virtuell',
    'agentTools.group.virtual.hint': 'beantwortet der Server selbst, nicht sperrbar',
    'agentTools.pageLink': 'Seite {page}',
    'agentTools.signal.pii': 'persönliche Daten in der Nachricht',
    'agentTools.lock.hidden':
      'Abgeschaltet (search_skill von Haus aus) — hier in der Spalte „Anbieten“ einschaltbar.',
    'agentTools.lock.needsAccess':
      'Nur mit persönlicher WLO-Anmeldung — oder mit dem Gastkonto, wenn es unter '
      + '„Betrieb“ schreiben darf.',
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
  },
  en: {
    'curated.agent.tools.label': 'Tools and locks',
    'curated.agent.tools.hint':
      'Which tools the agent gets in a chat turn and what can take one of them away. '
      + 'The “Offer” column switches tools of the MCP servers on and off.',

    'agentTools.loading': 'Loading the tool list …',
    'agentTools.summary.one': 'A plain chat turn in agent mode gets {offered} of {count} tool.',
    'agentTools.summary.other': 'A plain chat turn in agent mode gets {offered} of {count} tools.',
    'agentTools.caption':
      'Tools of the agent loop by kind: whether a plain turn gets them and when they are '
      + 'missing. “Offer” writes the server list; every other lock is maintained where it '
      + 'lives.',
    'agentTools.col.tool': 'Tool',
    'agentTools.col.herkunft': 'Origin',
    'agentTools.col.anbieten': 'Offer',
    'agentTools.herkunft.eingebaut': 'Built-in',
    'agentTools.herkunft.wlo': 'WLO MCP',
    'agentTools.herkunft.fremd': 'External MCP',
    'agentTools.schalter': 'Offer {name} to the model',
    'agentTools.schalter.fest': 'fixed',
    'agentTools.schalter.laedt': 'loading …',
    'agentTools.schalter.unbekannt': 'unknown',
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
    'agentTools.group.external': 'External',
    'agentTools.group.external.hint': 'read-only tools of further MCP servers, adopted under Knowledge → MCP servers',
    'agentTools.group.virtual': 'Virtual',
    'agentTools.group.virtual.hint': 'answered by the server itself, cannot be locked',
    'agentTools.pageLink': 'Page {page}',
    'agentTools.signal.pii': 'personal data in the message',
    'agentTools.lock.hidden':
      'Switched off (search_skill by default) — switch it on here in the “Offer” column.',
    'agentTools.lock.needsAccess':
      'Only with a personal WLO sign-in — or with the guest account, if it may write '
      + '(see “Operation”).',
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
  },
};
