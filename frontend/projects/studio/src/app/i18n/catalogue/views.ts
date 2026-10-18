/**
 * Die Ansichts-Registry (C1-d2): Gruppenüberschriften der Navigation, die
 * Ansichten mit Kurztext (seit Paket 14 je Arbeitsbereich), die Texte der Rahmen-Ansichten und die drei
 * Dokumenttitel von Routen ohne Registry-Zeile.
 */
import type { CataloguePart } from './catalogue-part';

export const VIEWS: CataloguePart = {
  de: {
    // ── Gruppen der Navigation ──────────────────────────────────────
    // Paket 14: je Arbeitsbereich zuerst dessen eigener Block, dann die gemeinsamen Gruppen.
    'nav.group.agent': 'Agent',
    'nav.group.muster': 'Muster',
    'nav.group.gemeinsam': 'Gemeinsam',
    'nav.group.auswertung': 'Auswertung',
    'nav.group.system': 'System',

    // ── Die 20 Ansichten ────────────────────────────────────────────
    // Reihenfolge wie in `studio-views.ts`. Der Slug bleibt deutsch und
    // unverändert — er ist eine Adresse, kein Text.
    'view.uebersicht.label': 'Übersicht',
    'view.uebersicht.desc': 'Start, Architektur & Status',
    'view.begruessung.label': 'Begrüßung',
    'view.begruessung.desc': 'Start-Text & Start-Quick-Replies',
    'view.kontext-aktionen.label': 'Kontext-Aktionen',
    'view.kontext-aktionen.desc': 'Proaktive Begrüßung + Pills je Seitentyp',
    'view.identitaet.label': 'Identität & Schutz',
    'view.identitaet.desc': 'Sicherheitslevel, Basis-Persona, Leitplanken, Regelwerk',
    'view.domain-wissen.label': 'Domänenwissen',
    'view.domain-wissen.desc': 'Domänenregeln & Plattform-Wissen',
    'view.patterns.label': 'Patterns',
    'view.patterns.desc': 'Gesprächsmuster',
    'view.dimensionen.label': 'Dimensionen',
    'view.dimensionen.desc': 'Personas, Intents, Zustände, Entities',
    'view.material-formate.label': 'Materialformate',
    'view.material-formate.desc': 'Materialtypen mit Vorschau, Aliase, Prioritäten',
    'view.wissen.label': 'Wissen',
    'view.wissen.desc': 'RAG-Bereiche & MCP-Tools',
    'view.sessions.label': 'Sessions',
    'view.sessions.desc': 'Gesprächsverläufe',
    'view.analyse.label': 'Analyse',
    'view.analyse.desc': 'Pattern-/Intent-Verteilung, Diagnose',
    'view.evaluation.label': 'Evaluation',
    'view.evaluation.desc': 'Persona-Dialoge & Gold-Flows',
    'view.lasttest.label': 'Lasttest',
    'view.lasttest.desc': 'Skalierbarkeit & Ressourcen',
    'view.safety-logs.label': 'Safety-Logs',
    'view.safety-logs.desc': 'Risiko-Events & Rate-Limits',
    'view.kosten.label': 'Kosten',
    'view.nutzung.label': 'Nutzung',
    'view.nutzung.desc': 'Besuch, Tageszeit, Geräte und Sprachen',
    'view.kosten.desc': 'Token & Betrag je Zeitraum',
    'view.anzeige.label': 'Anzeige',
    'view.anzeige.desc': 'Boxen, Schriftgrößen, Geräte-Limits',
    'view.datenschutz.label': 'Datenschutz',
    'view.datenschutz.desc': 'Logging & Purge',
    'view.bereiche.label': 'Alle Bereiche',
    'view.bereiche.desc': 'Jede Konfigurationsdatei, generisch editierbar',
    'view.sicherung.label': 'Sicherung',
    'view.sicherung.desc': 'Werksfassung, Snapshots & Backup',
    'view.vorschau.label': 'Vorschau',
    'view.vorschau.desc': 'Das echte Widget mit dieser Konfiguration',
    // Paket 14: der Agent-Arbeitsbereich und die neuen gemeinsamen Seiten
    'view.agent-uebersicht.label': 'Übersicht',
    'view.agent-uebersicht.desc': 'Status, Master-Skill, Architektur, Testseiten',
    'view.agent-rolle.label': 'Rolle & Schutz',
    'view.agent-rolle.desc': 'Sicherheit, Rolle, Grenzen, Regeln, Schutzantworten',
    'view.agent-prompt.label': 'Prompt & Probelauf',
    'view.agent-prompt.desc': 'Prompt-Kette, Master-Skill-Text, Testläufe',
    'view.fuehrung.label': 'Tour & Lotse',
    'view.fuehrung.desc': 'Website-Tour und Lotsen-Modus',
    'view.zielgruppen.label': 'Zielgruppen',
    'view.zielgruppen.desc': 'Anrede je Zielgruppe (du/Sie)',
    'view.werkzeuge.label': 'Werkzeuge',
    'view.werkzeuge.desc': 'Alle Werkzeuge, Herkunft, an/aus',
    'view.skills.label': 'Skills',
    'view.skills.desc': 'Master-Skill, Skill-Register, Skill-Brücke',
    'view.betrieb.label': 'Betrieb',
    'view.betrieb.desc': 'Vorgabe-Maschine & Betriebsschalter',

    // ── Rahmen-Ansichten ────────────────────────────────────────────
    /** Platzhalter für eine Ansicht, die ein späteres Paket baut. Das Paket
     *  ist ein Platzhalterwert, kein eingebauter Satzteil — sonst wäre der
     *  Satz nur als Bruchstück übersetzbar. */
    'view.placeholder.note':
      'Diese Ansicht wird mit Paket {paket} gebaut. Die Konfiguration selbst ist '
      + 'im Backend bereits vollständig vorhanden.',
    'notFound.title': 'Seite nicht gefunden',
    'notFound.text': 'Diese Adresse gehört zu keiner Studio-Ansicht.',
    'notFound.link': 'Zur Startseite',
    /** Brotkrume über dem Titel jeder kuratierten Konfigurations-Ansicht. */

    // ── Dokumenttitel ohne eigene Ansicht ───────────────────────────
    // Die 19 Ansichts-Titel bauen sich aus `view.<slug>.label`; diese drei
    // Routen haben keine Registry-Zeile. Das Suffix ist `studio.title`.
    'route.login': 'Anmelden',
    'route.notFound': 'Nicht gefunden',
    /** Rückfall, wenn die Wildcard-Route keinen Bereichs-Pfad mitbringt. */
    'route.area': 'Bereich',
  },

  en: {
    'nav.group.agent': 'Agent',
    'nav.group.muster': 'Patterns',
    'nav.group.gemeinsam': 'Shared',
    // Nicht „Evaluation" und nicht „Analysis": beide Wörter sind hier schon
    // Namen einzelner Ansichten IN dieser Gruppe, und zwei Einträge derselben
    // Navigation dürften nicht gleich heissen.
    'nav.group.auswertung': 'Monitoring',
    'nav.group.system': 'System',

    'view.uebersicht.label': 'Overview',
    'view.uebersicht.desc': 'Start, architecture & status',
    'view.begruessung.label': 'Greeting',
    'view.begruessung.desc': 'Opening message & starting quick replies',
    'view.kontext-aktionen.label': 'Context actions',
    'view.kontext-aktionen.desc': 'Proactive greeting + pills per page type',
    'view.identitaet.label': 'Identity & safeguards',
    'view.identitaet.desc': 'Safety level, base persona, guardrails, policy',
    'view.domain-wissen.label': 'Domain knowledge',
    'view.domain-wissen.desc': 'Domain rules & platform knowledge',
    'view.patterns.label': 'Patterns',
    'view.patterns.desc': 'Conversation patterns',
    'view.dimensionen.label': 'Dimensions',
    'view.dimensionen.desc': 'Personas, intents, states, entities',
    'view.material-formate.label': 'Material formats',
    'view.material-formate.desc': 'Material types with preview, aliases, priorities',
    'view.wissen.label': 'Knowledge',
    'view.wissen.desc': 'RAG areas & MCP tools',
    'view.sessions.label': 'Sessions',
    'view.sessions.desc': 'Conversation transcripts',
    'view.analyse.label': 'Analysis',
    'view.analyse.desc': 'Pattern/intent distribution, diagnostics',
    'view.evaluation.label': 'Evaluation',
    'view.evaluation.desc': 'Persona dialogues & gold flows',
    'view.lasttest.label': 'Load test',
    'view.lasttest.desc': 'Scalability & resources',
    'view.safety-logs.label': 'Safety logs',
    'view.safety-logs.desc': 'Risk events & rate limits',
    'view.kosten.label': 'Costs',
    'view.nutzung.label': 'Usage',
    'view.nutzung.desc': 'Visits, time of day, devices and languages',
    'view.kosten.desc': 'Tokens & amount per period',
    'view.anzeige.label': 'Display',
    'view.anzeige.desc': 'Boxes, font sizes, device limits',
    'view.datenschutz.label': 'Privacy',
    'view.datenschutz.desc': 'Logging & purge',
    'view.bereiche.label': 'All areas',
    'view.bereiche.desc': 'Every configuration file, generically editable',
    'view.sicherung.label': 'Backup',
    'view.sicherung.desc': 'Factory version, snapshots & backup',
    'view.vorschau.label': 'Preview',
    'view.vorschau.desc': 'The real widget with this configuration',
    'view.agent-uebersicht.label': 'Overview',
    'view.agent-uebersicht.desc': 'Status, master skill, architecture, test pages',
    'view.agent-rolle.label': 'Role & safety',
    'view.agent-rolle.desc': 'Safety, role, limits, rules, protective answers',
    'view.agent-prompt.label': 'Prompt & test run',
    'view.agent-prompt.desc': 'Prompt chain, master skill text, test runs',
    'view.fuehrung.label': 'Tour & guide',
    'view.fuehrung.desc': 'Website tour and guide mode',
    'view.zielgruppen.label': 'Audiences',
    'view.zielgruppen.desc': 'Form of address per audience',
    'view.werkzeuge.label': 'Tools',
    'view.werkzeuge.desc': 'All tools, origin, on/off',
    'view.skills.label': 'Skills',
    'view.skills.desc': 'Master skill, skill registry, skill bridge',
    'view.betrieb.label': 'Operation',
    'view.betrieb.desc': 'Default engine & operating switches',

    'view.placeholder.note':
      'This view is built in package {paket}. The configuration itself is already '
      + 'complete in the backend.',
    'notFound.title': 'Page not found',
    'notFound.text': 'This address does not belong to any studio view.',
    'notFound.link': 'Go to the start page',

    'route.login': 'Sign in',
    'route.notFound': 'Not found',
    'route.area': 'Area',
  },
};
