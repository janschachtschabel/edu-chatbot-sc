/**
 * Die zehn kuratierten Konfigurations-Seiten (C1-d3d): Einleitung je Seite,
 * Überschrift und Kurztext je Abschnitt.
 *
 * Diese Texte standen bis C1-d3d fertig ausformuliert in `views/curated-views.ts`
 * — auf Modulebene, also eingefroren in der Sprache, die beim Laden des Moduls
 * galt. Dieselbe Klasse wie `CONFIRM_LEAVE` (C1-d3a), der Routen-Titel (C1-d2),
 * `PREVIEW_CONTEXT_KINDS` (C1-d3b) und `SOURCES` (C1-d3c), nur zwanzigmal so
 * gross. `curated-views.ts` trägt jetzt nur noch Struktur: Slug, Bereichs-
 * schlüssel, Gruppen-/Feature-Markierung — und Katalog-Schlüssel.
 *
 * Die beiden Texte der Seiten-Hülle (`curated.crumb`, `curated.empty`) sind aus
 * `views.ts` hierher gezogen: sie gehören derselben Komponente und derselben
 * Frage („wo steht der Text der kuratierten Seiten?").
 *
 * Schlüsselschema `curated.<slug>.<abschnitt>.{label,hint}`. Der zweite Teil ist
 * der Routen-Slug, der dritte ein kurzer, sprechender Name — nicht der
 * Bereichsschlüssel, denn `05-canvas/type-aliases` als Schlüsselbestandteil
 * bände den Text an einen Dateipfad, der sich ändern darf.
 */
import type { CataloguePart } from './catalogue-part';

export const CURATED: CataloguePart = {
  de: {
    // ── Hülle der kuratierten Seite ─────────────────────────────────
    'curated.crumb': 'Konfiguration',
    'curated.empty':
      'Für diese Seite ist noch keine Zusammenstellung hinterlegt. Über „Alle '
      + 'Bereiche" sind alle Konfigurationsbereiche erreichbar.',

    // ── Begrüßung ───────────────────────────────────────────────────
    'curated.begruessung.intro':
      'Der erste Eindruck im Widget: die Begrüßungsblase und die Chips darunter. '
      + 'Ein Chip kann die Web-Tour starten — dafür muss „tour_reply" wörtlich einem '
      + 'der Quick-Replies entsprechen.',
    'curated.begruessung.welcome.label': 'Begrüßung & Start-Chips',
    'curated.begruessung.welcome.hint':
      'Begrüßungstext, Quick-Replies und der Chip, der die Web-Tour startet.',

    // ── Kontext-Aktionen ────────────────────────────────────────────
    'curated.kontextAktionen.intro':
      'Was Boerdi anbietet, wenn er von selbst auf einer Seite auftaucht — je nach '
      + 'Seitentyp (Sammlung, Inhalt, Themenseite) eine eigene Ansprache und eigene Pills.',
    'curated.kontextAktionen.actions.label': 'Proaktive Begrüßung & Pills',
    'curated.kontextAktionen.actions.hint':
      'An/aus, Melde-Adresse, Ansprache und Pills je Seitentyp, Kuratier-Prompt.',

    // ── Identität ───────────────────────────────────────────────────
    'curated.identitaet.intro':
      'Wer Boerdi ist und wo seine Grenzen liegen. Das Sicherheitslevel ganz oben '
      + 'entscheidet, welche Prüfungen überhaupt laufen — alles Weitere feilt daran.',
    'curated.identitaet.safety.label': 'Sicherheit',
    'curated.identitaet.safety.hint':
      'Stufe, Presets, Krisen- und PII-Begriffe, Schwellen und Rate-Limits.',
    'curated.identitaet.persona.label': 'Grundpersona',
    'curated.identitaet.persona.hint': 'Haltung, Stimme und Selbstverständnis in jeder Antwort.',
    'curated.identitaet.guardrails.label': 'Leitplanken',
    'curated.identitaet.guardrails.hint': 'Was Boerdi nicht tut, und wie er das sagt.',
    'curated.identitaet.policy.label': 'Regelwerk',
    'curated.identitaet.policy.hint':
      'Regeln, die Muster und Werkzeuge je Situation erlauben oder sperren.',

    // ── Domänen-Wissen ──────────────────────────────────────────────
    'curated.domainWissen.intro':
      'Was Boerdi über die Plattform und ihre Inhalte weiß. Diese Texte gehen als '
      + 'Systemwissen in jede Antwort ein — je konkreter, desto weniger rät das Modell.',
    'curated.domainWissen.rules.label': 'Domänen-Regeln',
    'curated.domainWissen.rules.hint': 'Fachliche Leitplanken für Antworten in dieser Domäne.',
    'curated.domainWissen.platform.label': 'Plattform-Wissen',
    'curated.domainWissen.platform.hint':
      'Wie WirLernenOnline aufgebaut ist: Bereiche, Begriffe, Wege.',
    'curated.domainWissen.tour.label': 'Web-Tour',
    'curated.domainWissen.tour.hint': 'Stationen der geführten Tour, ihre Gruppen und Einstiege.',

    // ── Material-Formate ────────────────────────────────────────────
    'curated.materialFormate.intro':
      'Welche Materialarten Boerdi erzeugen kann und woran er erkennt, dass jemand '
      + 'eine davon möchte.',
    'curated.materialFormate.types.label': 'Material-Typen',
    'curated.materialFormate.types.hint': 'Die erzeugbaren Formate mit Beschreibung und Vorlage.',
    'curated.materialFormate.aliases.label': 'Bezeichnungen',
    'curated.materialFormate.aliases.hint':
      'Alltagswörter, die auf einen Typ zeigen („Test" → Quiz).',
    'curated.materialFormate.create.label': 'Auslöser: neu erstellen',
    'curated.materialFormate.create.hint': 'Formulierungen, die als Auftrag zum Erstellen gelten.',
    'curated.materialFormate.edit.label': 'Auslöser: überarbeiten',
    'curated.materialFormate.edit.hint':
      'Formulierungen, die sich auf ein bestehendes Dokument beziehen.',
    'curated.materialFormate.priorities.label': 'Vorrang je Persona',
    'curated.materialFormate.priorities.hint':
      'Welche Typen für welche Zielgruppe zuerst vorgeschlagen werden.',

    // ── Gesprächsmuster ─────────────────────────────────────────────
    'curated.patterns.intro':
      'Die Gesprächsmuster: je ein Dokument mit Kopfdaten und Anweisungstext. '
      + 'Welches Muster greift, entscheidet der LLM-Hint — hier steht, was es dann tut.',
    'curated.patterns.patterns.label': 'Gesprächsmuster',
    'curated.patterns.patterns.hint':
      'Auslöser, Abgrenzung, Ton, Werkzeuge und Anweisungstext je Muster.',

    // ── Dimensionen ─────────────────────────────────────────────────
    'curated.dimensionen.intro': 'Die Achsen, an denen Boerdi ein Gespräch einordnet.',
    'curated.dimensionen.personas.label': 'Personas',
    'curated.dimensionen.personas.hint': 'Zielgruppen mit Ansprache, Zielen und typischen Anliegen.',
    'curated.dimensionen.intents.label': 'Intents',
    'curated.dimensionen.intents.hint': 'Absichten, die der Klassifikator unterscheidet.',
    'curated.dimensionen.states.label': 'Gesprächszustände',
    'curated.dimensionen.states.hint': 'Phasen eines Dialogs und die erlaubten Übergänge.',
    'curated.dimensionen.entities.label': 'Entitäten',
    'curated.dimensionen.entities.hint':
      'Erkannte Größen wie Fach oder Bildungsstufe, mit Beispielen.',
    'curated.dimensionen.signals.label': 'Signale',
    'curated.dimensionen.signals.hint': 'Feine Hinweise im Text, die die Antwort nachjustieren.',
    'curated.dimensionen.tone.label': 'Tonalität',
    'curated.dimensionen.tone.hint': 'Wie sich die Ansprache je Persona verschiebt.',

    // ── Anzeige ─────────────────────────────────────────────────────
    'curated.anzeige.intro':
      'Wie Ergebnisse im Widget erscheinen: welche Boxen, wie viele Einträge, '
      + 'welche Kopfzeilen-Links — und was kleine Geräte davon abweichend bekommen.',
    'curated.anzeige.display.label': 'Darstellungsregeln',
    'curated.anzeige.display.hint': 'Boxen, Grenzen und Textlängen der Ergebnisdarstellung.',
    'curated.anzeige.header.label': 'Kopfzeilen-Navigation',
    'curated.anzeige.header.hint': 'Die Links, die das Widget oben anbietet.',
    'curated.anzeige.devices.label': 'Geräte',
    'curated.anzeige.devices.hint': 'Abweichende Grenzen für kleine Bildschirme.',

    // ── Datenschutz ─────────────────────────────────────────────────
    'curated.datenschutz.intro':
      'Was mitgeschrieben wird und wie lange. Weniger Logging heißt weniger '
      + 'Auswertung — die Analyse-Ansichten zeigen dann entsprechend weniger.',
    'curated.datenschutz.privacy.label': 'Datenschutz',
    'curated.datenschutz.privacy.hint': 'Welche Inhalte überhaupt gespeichert werden dürfen.',
    'curated.datenschutz.qualityLog.label': 'Qualitäts-Logging',
    'curated.datenschutz.qualityLog.hint':
      'Umfang der Protokolle, aus denen die Analyse gespeist wird.',

    // ── Wissen ──────────────────────────────────────────────────────
    'curated.wissen.intro':
      'Woher der Bot Wissen holt: eigene Dokumente (RAG) und die MCP-Server, über '
      + 'die er WirLernenOnline durchsucht. Ein Wissensbereich entsteht mit dem '
      + 'ersten Dokument darin — angelegt wird er nicht, er wird befüllt.',
    'curated.wissen.areas.label': 'Wissensbereiche',
    'curated.wissen.areas.hint':
      'Was aktuell in der Datenbank liegt, mit Dokumenten und Abschnitten.',
    'curated.wissen.ingest.label': 'Dokumente hinzufügen',
    'curated.wissen.ingest.hint': 'Datei, Webseite oder Text einlesen und in einen Bereich legen.',
    'curated.wissen.ragConfig.label': 'Bereichs-Einstellungen',
    'curated.wissen.ragConfig.hint':
      '„always" legt einen Bereich in jeden Prompt, „on-demand" nur bei Bedarf.',
    'curated.wissen.mcp.label': 'MCP-Server',
    'curated.wissen.mcp.hint': 'Werkzeug-Server, die der Bot im Gespräch aufrufen darf.',

    'curated.agent.intro':
      'Zwei Wege, einen Zug zu beantworten. Die Muster-Engine ist der Bestand: '
      + 'Klassifikator, Musterwahl, gebundene Werkzeugliste. Die Agent-Schleife '
      + 'überlässt dem Modell alles — Systemprompt plus voller Werkzeugkatalog, '
      + 'kein Muster, kein Klassifikator. Die Vorgabe ist „Muster-Engine", und '
      + 'das ist eine Zusage: ohne Pflege ändert sich am ausgelieferten Chatbot '
      + 'nichts.',
    'curated.agent.engine.label': 'Welche Maschine antwortet',
    'curated.agent.engine.hint':
      'Umschalter und die Deckel der Schleife (Runden, Frist, Token-Budget, Schreibrecht).',
    'curated.agent.tester.label': 'Agent testen',
    'curated.agent.tester.hint':
      'Eine Aufgabe stellen und das Ergebnis ansehen — ohne Chat, ohne Sitzung.',
  },

  en: {
    'curated.crumb': 'Configuration',
    'curated.empty':
      'No selection has been set up for this page yet. Every configuration area '
      + 'is reachable through “All areas”.',

    'curated.begruessung.intro':
      'The first impression in the widget: the greeting bubble and the chips below '
      + 'it. A chip can start the site tour — for that, “tour_reply” has to match one '
      + 'of the quick replies word for word.',
    'curated.begruessung.welcome.label': 'Greeting & starting chips',
    'curated.begruessung.welcome.hint':
      'Greeting text, quick replies, and the chip that starts the site tour.',

    'curated.kontextAktionen.intro':
      'What Boerdi offers when it appears on a page of its own accord — its own '
      + 'wording and its own pills per page kind (collection, content, topic page).',
    'curated.kontextAktionen.actions.label': 'Proactive greeting & pills',
    'curated.kontextAktionen.actions.hint':
      'On/off, report address, wording and pills per page kind, curation prompt.',

    'curated.identitaet.intro':
      'Who Boerdi is and where its limits are. The safety level at the top decides '
      + 'which checks run at all — everything below only refines that.',
    'curated.identitaet.safety.label': 'Safety',
    'curated.identitaet.safety.hint':
      'Level, presets, crisis and PII terms, thresholds and rate limits.',
    'curated.identitaet.persona.label': 'Base persona',
    'curated.identitaet.persona.hint': 'Attitude, voice and self-image in every answer.',
    'curated.identitaet.guardrails.label': 'Guardrails',
    'curated.identitaet.guardrails.hint': 'What Boerdi does not do, and how it says so.',
    'curated.identitaet.policy.label': 'Policy',
    'curated.identitaet.policy.hint':
      'Rules that allow or block patterns and tools per situation.',

    'curated.domainWissen.intro':
      'What Boerdi knows about the platform and its content. These texts go into '
      + 'every answer as system knowledge — the more concrete, the less the model guesses.',
    'curated.domainWissen.rules.label': 'Domain rules',
    'curated.domainWissen.rules.hint': 'Subject-matter guardrails for answers in this domain.',
    'curated.domainWissen.platform.label': 'Platform knowledge',
    'curated.domainWissen.platform.hint':
      'How WirLernenOnline is built: areas, terms, routes.',
    'curated.domainWissen.tour.label': 'Site tour',
    'curated.domainWissen.tour.hint': 'Stops of the guided tour, their groups and entry points.',

    'curated.materialFormate.intro':
      'Which kinds of material Boerdi can produce, and how it recognises that '
      + 'someone wants one of them.',
    'curated.materialFormate.types.label': 'Material types',
    'curated.materialFormate.types.hint':
      'The formats that can be produced, with description and template.',
    'curated.materialFormate.aliases.label': 'Names',
    'curated.materialFormate.aliases.hint':
      'Everyday words that point at a type (“test” → quiz).',
    'curated.materialFormate.create.label': 'Trigger: create new',
    'curated.materialFormate.create.hint': 'Phrasings that count as an order to create something.',
    'curated.materialFormate.edit.label': 'Trigger: revise',
    'curated.materialFormate.edit.hint': 'Phrasings that refer to an existing document.',
    'curated.materialFormate.priorities.label': 'Priority per persona',
    'curated.materialFormate.priorities.hint':
      'Which types are suggested first for which audience.',

    'curated.patterns.intro':
      'The conversation patterns: one document each, with head fields and an '
      + 'instruction text. Which pattern applies is the LLM hint’s decision — what it '
      + 'then does is written here.',
    'curated.patterns.patterns.label': 'Conversation patterns',
    'curated.patterns.patterns.hint':
      'Trigger, delimitation, tone, tools and instruction text per pattern.',

    'curated.dimensionen.intro': 'The axes along which Boerdi places a conversation.',
    'curated.dimensionen.personas.label': 'Personas',
    'curated.dimensionen.personas.hint':
      'Audiences with their wording, goals and typical concerns.',
    'curated.dimensionen.intents.label': 'Intents',
    'curated.dimensionen.intents.hint': 'Intentions the classifier tells apart.',
    'curated.dimensionen.states.label': 'Conversation states',
    'curated.dimensionen.states.hint': 'Phases of a dialogue and the permitted transitions.',
    'curated.dimensionen.entities.label': 'Entities',
    'curated.dimensionen.entities.hint':
      'Recognised quantities such as subject or education level, with examples.',
    'curated.dimensionen.signals.label': 'Signals',
    'curated.dimensionen.signals.hint': 'Faint hints in the text that readjust the answer.',
    'curated.dimensionen.tone.label': 'Tone',
    'curated.dimensionen.tone.hint': 'How the wording shifts per persona.',

    'curated.anzeige.intro':
      'How results appear in the widget: which boxes, how many entries, which '
      + 'header links — and what small devices get instead.',
    'curated.anzeige.display.label': 'Display rules',
    'curated.anzeige.display.hint': 'Boxes, limits and text lengths of the result display.',
    'curated.anzeige.header.label': 'Header navigation',
    'curated.anzeige.header.hint': 'The links the widget offers at the top.',
    'curated.anzeige.devices.label': 'Devices',
    'curated.anzeige.devices.hint': 'Differing limits for small screens.',

    'curated.datenschutz.intro':
      'What is recorded and for how long. Less logging means less analysis — the '
      + 'analysis views then show correspondingly less.',
    'curated.datenschutz.privacy.label': 'Privacy',
    'curated.datenschutz.privacy.hint': 'Which content may be stored at all.',
    'curated.datenschutz.qualityLog.label': 'Quality logging',
    'curated.datenschutz.qualityLog.hint': 'Extent of the logs that feed the analysis.',

    'curated.wissen.intro':
      'Where the bot gets knowledge from: its own documents (RAG) and the MCP '
      + 'servers it searches WirLernenOnline through. A knowledge area comes into '
      + 'being with its first document — it is not created, it is filled.',
    'curated.wissen.areas.label': 'Knowledge areas',
    'curated.wissen.areas.hint':
      'What currently lies in the database, with documents and sections.',
    'curated.wissen.ingest.label': 'Add documents',
    'curated.wissen.ingest.hint': 'Ingest a file, a web page or text and put it into an area.',
    'curated.wissen.ragConfig.label': 'Area settings',
    'curated.wissen.ragConfig.hint':
      '“always” puts an area into every prompt, “on-demand” only when needed.',
    'curated.wissen.mcp.label': 'MCP servers',
    'curated.wissen.mcp.hint': 'Tool servers the bot may call during a conversation.',

    'curated.agent.intro':
      'Two ways to answer a turn. The pattern engine is what ships: classifier, '
      + 'pattern selection, a bound tool list. The agent loop leaves everything '
      + 'to the model — system prompt plus the full tool catalogue, no pattern, '
      + 'no classifier. The default is “pattern engine”, and that is a promise: '
      + 'without maintenance nothing about the shipped chatbot changes.',
    'curated.agent.engine.label': 'Which engine answers',
    'curated.agent.engine.hint':
      'The switch and the loop’s caps (rounds, deadline, token budget, write mode).',
    'curated.agent.tester.label': 'Test the agent',
    'curated.agent.tester.hint':
      'Give it a task and look at the result — no chat, no session.',
  },
};
