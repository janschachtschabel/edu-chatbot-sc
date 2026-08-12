/**
 * Die Ansichts-Registry (C1-d2): Gruppenüberschriften der Navigation, die 20
 * Ansichten mit Kurztext, die Texte der Rahmen-Ansichten und die drei
 * Dokumenttitel von Routen ohne Registry-Zeile.
 */
import type { CataloguePart } from './catalogue-part';

export const VIEWS: CataloguePart = {
  de: {
    // ── Gruppen der Navigation ──────────────────────────────────────
    // „start" trägt bewusst keine Überschrift: die Übersicht steht als
    // einziger Eintrag über der ersten Gruppe.
    'nav.group.konfiguration': 'Konfiguration',
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
    'view.identitaet.desc': 'Sicherheitslevel, Persona, Leitplanken, Regelwerk',
    'view.domain-wissen.label': 'Domain-Wissen',
    'view.domain-wissen.desc': 'Plattform-Wissen, Web-Tour',
    'view.patterns.label': 'Patterns',
    'view.patterns.desc': 'Gesprächsmuster',
    'view.dimensionen.label': 'Dimensionen',
    'view.dimensionen.desc': 'Personas, Intents, States, Entities',
    'view.material-formate.label': 'Material-Formate',
    'view.material-formate.desc': 'Material-Typen, Aliase, Trigger',
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
    'view.kosten.desc': 'Token & Betrag je Zeitraum',
    'view.anzeige.label': 'Anzeige',
    'view.anzeige.desc': 'Boxen, Schriftgrößen, Geräte-Limits',
    'view.datenschutz.label': 'Datenschutz',
    'view.datenschutz.desc': 'Logging & Purge',
    'view.bereiche.label': 'Alle Bereiche',
    'view.bereiche.desc': 'Jede Konfigurationsdatei, generisch editierbar',
    'view.sicherung.label': 'Sicherung',
    'view.sicherung.desc': 'Snapshots, Backup & Werksstand',
    'view.vorschau.label': 'Vorschau',
    'view.vorschau.desc': 'Das echte Widget mit dieser Konfiguration',

    // ── Rahmen-Ansichten ────────────────────────────────────────────
    /** Platzhalter für eine Ansicht, die ein späteres Paket baut. Das Paket
     *  ist ein Platzhalterwert, kein eingebauter Satzteil — sonst wäre der
     *  Satz nur als Bruchstück übersetzbar. */
    'view.placeholder.note':
      'Diese Ansicht wird mit Paket {paket} gebaut. Die Konfiguration selbst ist '
      + 'im Backend bereits vollständig vorhanden.',
    'notFound.title': 'Seite nicht gefunden',
    'notFound.text': 'Diese Adresse gehört zu keiner Studio-Ansicht.',
    'notFound.link': 'Zur Übersicht',
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
    'nav.group.konfiguration': 'Configuration',
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
    'view.identitaet.desc': 'Safety level, persona, guardrails, policy',
    'view.domain-wissen.label': 'Domain knowledge',
    'view.domain-wissen.desc': 'Platform knowledge, website tour',
    'view.patterns.label': 'Patterns',
    'view.patterns.desc': 'Conversation patterns',
    'view.dimensionen.label': 'Dimensions',
    'view.dimensionen.desc': 'Personas, intents, states, entities',
    'view.material-formate.label': 'Material formats',
    'view.material-formate.desc': 'Material types, aliases, triggers',
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
    'view.kosten.desc': 'Tokens & amount per period',
    'view.anzeige.label': 'Display',
    'view.anzeige.desc': 'Boxes, font sizes, device limits',
    'view.datenschutz.label': 'Privacy',
    'view.datenschutz.desc': 'Logging & purge',
    'view.bereiche.label': 'All areas',
    'view.bereiche.desc': 'Every configuration file, generically editable',
    'view.sicherung.label': 'Backup',
    'view.sicherung.desc': 'Snapshots, backup & factory state',
    'view.vorschau.label': 'Preview',
    'view.vorschau.desc': 'The real widget with this configuration',

    'view.placeholder.note':
      'This view is built in package {paket}. The configuration itself is already '
      + 'complete in the backend.',
    'notFound.title': 'Page not found',
    'notFound.text': 'This address does not belong to any studio view.',
    'notFound.link': 'Go to the overview',

    'route.login': 'Sign in',
    'route.notFound': 'Not found',
    'route.area': 'Area',
  },
};
