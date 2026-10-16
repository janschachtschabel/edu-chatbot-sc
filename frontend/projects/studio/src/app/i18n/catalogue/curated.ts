/**
 * Die kuratierten Konfigurations-Seiten für Inhalte (C1-d3d): Einleitung je
 * Seite, Überschrift und Kurztext je Abschnitt. Die Betriebs-Seiten (Anzeige,
 * Datenschutz, Kosten/Evaluation, Wissen, Agent) stehen seit Paket 6 in
 * `curated-betrieb.ts` — wie die Seiten selbst in `views/curated-pages-*.ts`.
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
      'Was Boerdi über die Plattform weiß und wohin er auf ihr führt. Die Wissenstexte '
      + 'gehen als Systemwissen in jede Antwort ein — je konkreter, desto weniger rät das '
      + 'Modell. Web-Tour und Lotse zeigen Wege zu Seiten.',
    'curated.domainWissen.rules.label': 'Domänen-Regeln',
    'curated.domainWissen.rules.hint': 'Fachliche Leitplanken für Antworten in dieser Domäne.',
    'curated.domainWissen.platform.label': 'Plattform-Wissen',
    'curated.domainWissen.platform.hint':
      'Wie WirLernenOnline aufgebaut ist: Bereiche, Begriffe, Wege.',
    'curated.domainWissen.tour.label': 'Web-Tour',
    'curated.domainWissen.tour.hint': 'Stationen der geführten Tour, ihre Gruppen und Einstiege.',
    // ST-9: der Lotse, neben der Web-Tour (bis dahin nur unter „Alle Bereiche“)
    'curated.domainWissen.guideMode.label': 'Lotse',
    'curated.domainWissen.guideMode.hint':
      'Knöpfe „Bring mich hin“ unter Antworten und Sprungziele an Karten: wie viele, zu '
      + 'welchen Hosts und Domains.',
    'curated.domainWissen.guideRules.label': 'Lotsen-Regeln',
    'curated.domainWissen.guideRules.hint':
      'Feste Sprungziele: passt eine Nachricht auf eine Regel, bietet der Lotse die '
      + 'hinterlegte Seite an. Änderungen wirken erst nach einem Neustart des Backends.',

    // ── Material-Formate ────────────────────────────────────────────
    'curated.materialFormate.intro':
      'Welche Materialarten Boerdi erzeugen kann und woran er erkennt, dass jemand '
      + 'eine davon möchte.',
    'curated.materialFormate.types.label': 'Material-Typen',
    'curated.materialFormate.types.hint': 'Die erzeugbaren Formate mit Beschreibung und Vorlage.',
    'curated.materialFormate.aliases.label': 'Bezeichnungen',
    'curated.materialFormate.aliases.hint':
      'Alltagswörter, die auf einen Typ zeigen („Test" → Quiz).',
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
    // ST-4c (Paket 6): die Kopfkarte der Reiter-Seite — je Achse Zahl und Zweck
    'curated.card.label': 'Die Achsen der Einordnung',
    'curated.card.unavailable': 'Die Zahlen ließen sich nicht laden.',
    'curated.card.personas.one': '{count} Persona — wer fragt',
    'curated.card.personas.other': '{count} Personas — wer fragt',
    'curated.card.intents.one': '{count} Intent — was die Person will',
    'curated.card.intents.other': '{count} Intents — was die Person will',
    'curated.card.states.one': '{count} Gesprächszustand — wo das Gespräch steht',
    'curated.card.states.other': '{count} Gesprächszustände — wo das Gespräch steht',
    'curated.card.entities.one': '{count} Entität — Fach, Stufe, Thema, Medientyp',
    'curated.card.entities.other': '{count} Entitäten — Fach, Stufe, Thema, Medientyp',
    'curated.card.signals.one': '{count} Signal — Stimmung, Erfahrung, Eile, Skepsis',
    'curated.card.signals.other': '{count} Signale — Stimmung, Erfahrung, Eile, Skepsis',
    'curated.dimensionen.personas.label': 'Personas',
    'curated.dimensionen.personas.hint': 'Zielgruppen mit Ansprache, Zielen und typischen Anliegen.',
    'curated.dimensionen.intents.label': 'Intents',
    'curated.dimensionen.intents.hint': 'Absichten, die der Klassifikator unterscheidet.',
    'curated.dimensionen.states.label': 'Gesprächszustände',
    'curated.dimensionen.states.hint': 'Phasen eines Dialogs und die erlaubten Übergänge.',
    'curated.dimensionen.entities.label': 'Entitäten',
    'curated.dimensionen.entities.hint':
      'Erkannte Größen wie Fach oder Bildungsstufe, mit Beispielen.',
    'curated.dimensionen.placeholderTopics.label': 'Platzhalter-Themen',
    'curated.dimensionen.placeholderTopics.hint':
      'Wörter wie „Thema“ oder „Material“, die nicht als echtes Thema zählen.',
    'curated.dimensionen.signals.label': 'Signale',
    'curated.dimensionen.signals.hint': 'Feine Hinweise im Text, die die Antwort nachjustieren.',
    'curated.dimensionen.tone.label': 'Tonalität',
    'curated.dimensionen.tone.hint': 'Wie sich die Ansprache je Persona verschiebt.',
    'curated.dimensionen.classifyOverrides.label': 'Feste Anker der Einordnung',
    'curated.dimensionen.classifyOverrides.hint':
      'Regeln und Beispiele für Persona, Intent und Muster. Sie stehen im Prompt des '
      + 'Klassifikators; erzwungen wird nichts.',
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
      'What Boerdi knows about the platform and where it leads people on it. The knowledge '
      + 'texts go into every answer as system knowledge — the more concrete, the less the '
      + 'model guesses. Site tour and guide show the way to pages.',
    'curated.domainWissen.rules.label': 'Domain rules',
    'curated.domainWissen.rules.hint': 'Subject-matter guardrails for answers in this domain.',
    'curated.domainWissen.platform.label': 'Platform knowledge',
    'curated.domainWissen.platform.hint':
      'How WirLernenOnline is built: areas, terms, routes.',
    'curated.domainWissen.tour.label': 'Site tour',
    'curated.domainWissen.tour.hint': 'Stops of the guided tour, their groups and entry points.',
    'curated.domainWissen.guideMode.label': 'Guide',
    'curated.domainWissen.guideMode.hint':
      '“Take me there” buttons under answers and jump targets on cards: how many, to which '
      + 'hosts and domains.',
    'curated.domainWissen.guideRules.label': 'Guide rules',
    'curated.domainWissen.guideRules.hint':
      'Fixed jump targets: when a message matches a rule, the guide offers the stored page. '
      + 'Changes only take effect after a backend restart.',

    'curated.materialFormate.intro':
      'Which kinds of material Boerdi can produce, and how it recognises that '
      + 'someone wants one of them.',
    'curated.materialFormate.types.label': 'Material types',
    'curated.materialFormate.types.hint':
      'The formats that can be produced, with description and template.',
    'curated.materialFormate.aliases.label': 'Names',
    'curated.materialFormate.aliases.hint':
      'Everyday words that point at a type (“test” → quiz).',
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
    'curated.card.label': 'The axes of classification',
    'curated.card.unavailable': 'The counts could not be loaded.',
    'curated.card.personas.one': '{count} persona — who is asking',
    'curated.card.personas.other': '{count} personas — who is asking',
    'curated.card.intents.one': '{count} intent — what the person wants',
    'curated.card.intents.other': '{count} intents — what the person wants',
    'curated.card.states.one': '{count} conversation state — where the conversation stands',
    'curated.card.states.other': '{count} conversation states — where the conversation stands',
    'curated.card.entities.one': '{count} entity — subject, level, topic, media type',
    'curated.card.entities.other': '{count} entities — subject, level, topic, media type',
    'curated.card.signals.one': '{count} signal — mood, experience, haste, scepticism',
    'curated.card.signals.other': '{count} signals — mood, experience, haste, scepticism',
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
    'curated.dimensionen.placeholderTopics.label': 'Placeholder topics',
    'curated.dimensionen.placeholderTopics.hint':
      'Words such as “topic” or “material” that do not count as a real topic.',
    'curated.dimensionen.signals.label': 'Signals',
    'curated.dimensionen.signals.hint': 'Faint hints in the text that readjust the answer.',
    'curated.dimensionen.tone.label': 'Tone',
    'curated.dimensionen.tone.hint': 'How the wording shifts per persona.',
    'curated.dimensionen.classifyOverrides.label': 'Fixed classification anchors',
    'curated.dimensionen.classifyOverrides.hint':
      'Rules and examples for persona, intent and pattern. They go into the classifier '
      + 'prompt; nothing is enforced.',
  },
};
