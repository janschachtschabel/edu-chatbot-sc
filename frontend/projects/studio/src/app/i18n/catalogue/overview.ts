/**
 * Die Startseite (C1-d4a): Kopf, Status-Streifen, die sechs Schicht-Karten und
 * die Betriebs-Karten.
 *
 * Die Schicht-Karten standen bis hierher als fertige Sätze in
 * `views/overview-cards.ts` — der sechste eingefrorene Konstanten-Fall nach
 * `CONFIRM_LEAVE`, dem Routen-Titel, `PREVIEW_CONTEXT_KINDS`, `SOURCES` und
 * `curated-views.ts`. Ihre Zahlen kamen aus Zeichenketten-Verkettung
 * (`${counts.patterns} Patterns`); jetzt tragen sie `{patterns}` als
 * Platzhalter, damit die Wortstellung der Sprache gehört und nicht dem Code.
 *
 * **Seit C1-d5d auch die vier Erklär-Karten am Fuss der Seite** („So entscheidet
 * der Bot", „Verknüpfungen", „Tonalitäts-Modifier", „3-Stufen-Eskalation"). Sie
 * waren als Fachprosa mit `<code>`-Auszeichnung mitten im Satz auf C1-d5
 * vertagt und standen bis dahin auf Englisch deutsch da — der Rückfall je
 * Schlüssel, wie im Entwurf vorgesehen. Sie bleiben hier und wandern nicht in
 * einen `reference-*`-Teil: gerendert werden sie von `overview.component.html`,
 * und ein Bauteil gehört dem Panel, das es rendert.
 *
 * **Zwei Verweise haben dabei ihre Wortgruppe bekommen** (`links.1.link`,
 * `tone.link`). Einer stand mitten im Satz, einer sogar in einer Klammer
 * („siehe Dimensionen"). Beides ist dasselbe Muster wie in C1-d4a und C1-d5b1:
 * der Verweis trägt eine vollständige Wortgruppe, statt dass ein Satz um das
 * `<a>` herum zerschnitten wird. Der deutsche Text ändert sich dadurch an einer
 * Stelle sichtbar — die Klammer wandert ans Satzende.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const OVERVIEW: CataloguePart = {
  de: {
    'overview.crumb': 'Start',
    'overview.title': 'Übersicht',
    'overview.intro':
      'Der Chatbot wird über sechs Architektur-Schichten konfiguriert; darunter '
      + 'steht der laufende Betrieb. Alle Änderungen wirken live, ohne '
      + 'Backend-Neustart.',
    'overview.tab.uebersicht': 'Übersicht',
    'overview.tab.referenz': 'Architektur & Referenz',

    // ── Status-Streifen ─────────────────────────────────────────────
    'overview.status.title': 'Status',
    /** Nur der Lade-Zustand des Knopfs; „Aktualisieren" selbst kommt aus
     *  `shared.ts`. C1-d4a legte es hier ein zweites Mal an, obwohl
     *  `action.refresh` seit C1-d3a genau dafür bereitstand (bemerkt in
     *  C1-d4b). */
    'overview.refreshing': 'Lädt …',
    'overview.backend': 'Backend',
    'overview.providerUnknown': 'Provider unbekannt',
    'overview.factory': 'Werkseinstellungen',
    'overview.factory.none': 'kein Werksstand gesichert',
    'overview.factory.noneHint': 'Ohne ihn gibt es kein „Zurück auf Anfang“.',
    /** Mehrzahl über `plural()`: „1 weiterer Snapshot" beugt das Adjektiv mit,
     *  nicht nur das Substantiv. Die Null-Form ist ein eigener Satz, weil
     *  „0 weitere Snapshots" niemand schreibt. */
    'overview.snapshots.zero': 'keine weiteren Snapshots',
    'overview.snapshots.one': '{count} weiterer Snapshot',
    'overview.snapshots.other': '{count} weitere Snapshots',
    'overview.eval': 'Letzte Eval',
    'overview.eval.score': 'Score {value}',
    'overview.eval.meta': '{turns} Turns · {ago}',
    'overview.eval.none': 'noch keine',
    /** Der ganze Aufruf ist die Verweis-Beschriftung. Bis C1-d4a stand nur
     *  „Evaluation öffnen" im Link und „und einen Lauf starten" daneben — ein
     *  Satz aus zwei Bruchstücken, und für einen Screenreader ein Verweis, der
     *  sein Ziel nur halb nennt. */
    'overview.eval.start': 'Evaluation öffnen und einen Lauf starten',

    // ── Abschnitte und Karten ───────────────────────────────────────
    'overview.section.architecture': 'Architektur',
    'overview.section.ops': 'Betrieb & Datenschutz',
    'overview.layer': 'Schicht {num} — {label}',

    'overview.layer.identitaet.headline': 'Wer ist der Chatbot? Was darf er nie tun?',
    'overview.layer.identitaet.primary': 'Persona · Guardrails · Safety · Policy',
    'overview.layer.identitaet.tag.persona': 'Basis-Persona',
    'overview.layer.identitaet.tag.guardrails': 'Guardrails',
    'overview.layer.identitaet.tag.safety': 'Safety-Preset',
    'overview.layer.identitaet.tag.policy': 'Policy-Regeln',

    'overview.layer.domain.headline': 'Was weiß der Chatbot über WLO und seine Umgebung?',
    'overview.layer.domain.primary': 'Plattform-Wissen · Domain-Regeln',
    'overview.layer.domain.tag.rules': 'Domain-Rules',
    'overview.layer.domain.tag.wlo': 'WLO-Fachwissen',
    'overview.layer.domain.tag.tour': 'Web-Tour',

    'overview.layer.patterns.headline': 'Der LLM-Hint wählt das passende Pattern.',
    'overview.layer.patterns.primary': '{patterns} Patterns',
    'overview.layer.patterns.tag.retrieve': 'Inhalte abrufen',
    'overview.layer.patterns.tag.create': 'Material-Erstellung',
    'overview.layer.patterns.tag.research': 'Recherche',
    'overview.layer.patterns.tag.safety': 'Safety-Pattern',

    'overview.layer.dimensionen.headline': 'Wie wird jeder Nutzer-Input klassifiziert?',
    'overview.layer.dimensionen.primary': '{personas} Personas · {intents} Intents',
    'overview.layer.dimensionen.tag.states': '{states} States',
    'overview.layer.dimensionen.tag.entities': '{entities} Entities',
    'overview.layer.dimensionen.tag.signals': '{signals} Signale',
    'overview.layer.dimensionen.tag.turnCount': 'Turn-Count',
    'overview.layer.dimensionen.tag.tone': 'Tonalitäts-Modifier',

    'overview.layer.material.headline': 'Wie sieht KI-generierter Inhalt im Chat aus?',
    'overview.layer.material.primary': '18 Material-Typen',
    'overview.layer.material.tag.didactic': '13 didaktisch',
    'overview.layer.material.tag.analytic': '5 analytisch',
    'overview.layer.material.tag.aliases': 'Typ-Aliase',
    'overview.layer.material.tag.triggers': 'Edit-/Create-Trigger',

    'overview.layer.wissen.headline': 'Welche Quellen liefern Faktenwissen zur Laufzeit?',
    'overview.layer.wissen.primary': 'RAG + MCP-Tools',
    'overview.layer.wissen.tag.alwaysOn': 'Always-on RAG',
    'overview.layer.wissen.tag.onDemand': 'On-Demand RAG',
    'overview.layer.wissen.tag.mcp': 'MCP-Server',
    'overview.layer.wissen.tag.topics': 'Themenseiten-Resolver',

    // ── Die vier Erklär-Karten am Fuss der Seite (C1-d5d) ───────────
    'overview.info.decide.title': 'So entscheidet der Bot',
    'overview.info.decide.1':
      '*Klassifikation:* Jeder Input wird in Intent, Persona, State und Entities '
      + 'eingeordnet. Fehlende Pflicht-Slots lösen eine gezielte Rückfrage aus.',
    'overview.info.decide.2':
      '*Pattern-Wahl:* Der LLM-Hint bestimmt das passende Pattern, '
      + '`classify-overrides.yaml` ist der deterministische Hard-Anker.',
    'overview.info.decide.3':
      '*Modulate:* Ton, Länge und Format werden anhand der aktiven Signale und '
      + 'der Persona-Tonalität nachjustiert.',

    'overview.info.links.title': 'Verknüpfungen',
    'overview.info.links.1':
      '*Patterns* referenzieren Personas, Intents, States und Signale —',
    /** Der Verweis trägt eine vollständige Wortgruppe statt nur des
     *  Ansichtsnamens (Muster aus C1-d4a). */
    'overview.info.links.1.link': 'editierbar unter Patterns',
    'overview.info.links.2':
      '*Tonalitäts-Modifier* stecken im Frontmatter jeder Persona (`tone`, '
      + '`length_bias`, `formality`, `card_text_mode`). Die Persona steuert die '
      + 'Tonalität, nicht die Pattern-Wahl.',
    'overview.info.links.3':
      '*Material-Formate* greifen nur bei den Intents I05 (Create) und I06 (Edit).',
    'overview.info.links.4':
      '*Inhalte abrufen (I03)* gilt für Themenseiten, Sammlungen und '
      + 'Einzelinhalte; die Pattern-Wahl läuft über Anker-Wörter und Persona.',

    'overview.info.tone.title': 'Tonalitäts-Modifier',
    /** Die Klammer „(siehe Dimensionen)" stand bis C1-d5d MITTEN im Satz. Sie
     *  ist ans Ende gewandert, damit der Verweis eine eigene Wortgruppe tragen
     *  kann — ein Satz, der um ein `<a>` herum zerschnitten wird, überlässt die
     *  Wortstellung dem Template. */
    'overview.info.tone.text':
      'Jede Persona trägt im Frontmatter die fünf Felder `tone`, `length_bias`, '
      + '`formality`, `card_text_mode` und `override`. Der Antwort-Prompt wendet '
      + 'sie an — die Tonalität liegt damit zentral pro Persona statt doppelt in '
      + 'jedem Pattern.',
    'overview.info.tone.link': 'nachzusehen unter Dimensionen',

    'overview.info.escalation.title': '3-Stufen-Eskalation',
    'overview.info.escalation.text':
      'In `02-domain/domain-rules.md` verankert: bei Anfragen außerhalb von WLO '
      + 'folgt der Bot dem Schema *direkter Treffer → Adjacent (query_knowledge) '
      + '→ ehrliche Degradation mit Kontaktweg*. Die Few-Shot-Beispiele dazu '
      + 'stehen im Prompt.',
  },
  en: {
    'overview.crumb': 'Home',
    'overview.title': 'Overview',
    'overview.intro':
      'The chatbot is configured through six architecture layers; below them '
      + 'sits day-to-day operation. Every change takes effect live, without '
      + 'restarting the backend.',
    'overview.tab.uebersicht': 'Overview',
    'overview.tab.referenz': 'Architecture & reference',

    'overview.status.title': 'Status',
    'overview.refreshing': 'Loading …',
    'overview.backend': 'Backend',
    'overview.providerUnknown': 'Provider unknown',
    'overview.factory': 'Factory settings',
    'overview.factory.none': 'no factory state saved',
    'overview.factory.noneHint': 'Without it there is no way back to the start.',
    'overview.snapshots.zero': 'no further snapshots',
    'overview.snapshots.one': '{count} further snapshot',
    'overview.snapshots.other': '{count} further snapshots',
    'overview.eval': 'Last eval',
    'overview.eval.score': 'Score {value}',
    'overview.eval.meta': '{turns} turns · {ago}',
    'overview.eval.none': 'none yet',
    'overview.eval.start': 'Open evaluation and start a run',

    'overview.section.architecture': 'Architecture',
    'overview.section.ops': 'Operations & privacy',
    'overview.layer': 'Layer {num} — {label}',

    'overview.layer.identitaet.headline': 'Who is the chatbot? What must it never do?',
    'overview.layer.identitaet.primary': 'Persona · guardrails · safety · policy',
    'overview.layer.identitaet.tag.persona': 'Base persona',
    'overview.layer.identitaet.tag.guardrails': 'Guardrails',
    'overview.layer.identitaet.tag.safety': 'Safety preset',
    'overview.layer.identitaet.tag.policy': 'Policy rules',

    'overview.layer.domain.headline': 'What does the chatbot know about WLO and its context?',
    'overview.layer.domain.primary': 'Platform knowledge · domain rules',
    'overview.layer.domain.tag.rules': 'Domain rules',
    'overview.layer.domain.tag.wlo': 'WLO expertise',
    'overview.layer.domain.tag.tour': 'Web tour',

    'overview.layer.patterns.headline': 'The LLM hint picks the matching pattern.',
    'overview.layer.patterns.primary': '{patterns} patterns',
    'overview.layer.patterns.tag.retrieve': 'Retrieve content',
    'overview.layer.patterns.tag.create': 'Material creation',
    'overview.layer.patterns.tag.research': 'Research',
    'overview.layer.patterns.tag.safety': 'Safety pattern',

    'overview.layer.dimensionen.headline': 'How is every user input classified?',
    'overview.layer.dimensionen.primary': '{personas} personas · {intents} intents',
    'overview.layer.dimensionen.tag.states': '{states} states',
    'overview.layer.dimensionen.tag.entities': '{entities} entities',
    'overview.layer.dimensionen.tag.signals': '{signals} signals',
    'overview.layer.dimensionen.tag.turnCount': 'Turn count',
    'overview.layer.dimensionen.tag.tone': 'Tone modifiers',

    'overview.layer.material.headline': 'What does AI-generated content look like in the chat?',
    'overview.layer.material.primary': '18 material types',
    'overview.layer.material.tag.didactic': '13 didactic',
    'overview.layer.material.tag.analytic': '5 analytic',
    'overview.layer.material.tag.aliases': 'Type aliases',
    'overview.layer.material.tag.triggers': 'Edit/create triggers',

    'overview.layer.wissen.headline': 'Which sources supply factual knowledge at runtime?',
    'overview.layer.wissen.primary': 'RAG + MCP tools',
    'overview.layer.wissen.tag.alwaysOn': 'Always-on RAG',
    'overview.layer.wissen.tag.onDemand': 'On-demand RAG',
    'overview.layer.wissen.tag.mcp': 'MCP servers',
    'overview.layer.wissen.tag.topics': 'Topic-page resolver',

    'overview.info.decide.title': 'How the bot decides',
    'overview.info.decide.1':
      '*Classification:* every input is sorted into intent, persona, state and '
      + 'entities. Missing required slots trigger a targeted follow-up question.',
    'overview.info.decide.2':
      '*Pattern choice:* the LLM hint determines the fitting pattern, '
      + '`classify-overrides.yaml` is the deterministic hard anchor.',
    'overview.info.decide.3':
      '*Modulate:* tone, length and format are adjusted from the active signals '
      + 'and the persona’s tone.',

    'overview.info.links.title': 'Connections',
    'overview.info.links.1':
      '*Patterns* reference personas, intents, states and signals —',
    'overview.info.links.1.link': 'editable under Patterns',
    'overview.info.links.2':
      '*Tone modifiers* sit in the frontmatter of every persona (`tone`, '
      + '`length_bias`, `formality`, `card_text_mode`). The persona steers the '
      + 'tone, not the pattern choice.',
    'overview.info.links.3':
      '*Material formats* apply only to the intents I05 (create) and I06 (edit).',
    'overview.info.links.4':
      '*Retrieving content (I03)* covers topic pages, collections and individual '
      + 'items; the pattern choice runs through anchor words and the persona.',

    'overview.info.tone.title': 'Tone modifiers',
    'overview.info.tone.text':
      'Every persona carries the five fields `tone`, `length_bias`, `formality`, '
      + '`card_text_mode` and `override` in its frontmatter. The answer prompt '
      + 'applies them — the tone therefore lives centrally per persona instead of '
      + 'twice over in every pattern.',
    'overview.info.tone.link': 'to be found under Dimensionen',

    'overview.info.escalation.title': 'Three-step escalation',
    'overview.info.escalation.text':
      'Anchored in `02-domain/domain-rules.md`: for requests outside WLO the bot '
      + 'follows the scheme *direct hit → adjacent (query_knowledge) → honest '
      + 'degradation with a way to get in touch*. The few-shot examples for it '
      + 'are in the prompt.',
  },
};
