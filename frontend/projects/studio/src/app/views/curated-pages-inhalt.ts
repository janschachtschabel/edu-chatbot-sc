/**
 * Die kuratierten Seiten für Inhalte (9-4b): Begrüßung, Kontext-Aktionen, Tour & Lotse
 * (gemeinsam) sowie Identität, Domänenwissen, Materialformate, Muster, Dimensionen
 * (Muster-Arbeitsbereich, Paket 14).
 *
 * Aus `curated-views.ts` herausgelöst (Paket 6), das über 300 Zeilen stand; die
 * Regeln für diese Daten stehen dort im Kopf. Die Reihenfolge der Seiten und
 * ihrer Abschnitte ist unverändert.
 */
import type { CuratedView } from './curated-views';

export const INHALT_SEITEN: readonly CuratedView[] = [
  {
    slug: 'begruessung',
    introKey: 'curated.begruessung.intro',
    sections: [
      {
        area: '01-base/welcome-config',
        labelKey: 'curated.begruessung.welcome.label',
        hintKey: 'curated.begruessung.welcome.hint',
      },
    ],
  },
  {
    slug: 'kontext-aktionen',
    introKey: 'curated.kontextAktionen.intro',
    sections: [
      {
        area: '01-base/context-actions',
        zugeklappt: true,
        labelKey: 'curated.kontextAktionen.actions.label',
        hintKey: 'curated.kontextAktionen.actions.hint',
        // Rundgang 3: Technik, Besuchertexte je Sprache, interne KI-Anweisung — nicht gemischt.
        gruppen: [
          { id: 'technik', labelKey: 'curated.kontextAktionen.gruppe.technik', felder: ['context_actions.enabled', 'context_actions.report_url', 'context_actions.own_hosts'] },
          { id: 'begruessung', labelKey: 'curated.kontextAktionen.gruppe.begruessung', felder: ['context_actions.greetings'] },
          { id: 'begruessungEn', labelKey: 'curated.kontextAktionen.gruppe.begruessungEn', felder: ['context_actions.greetings_en'] },
          { id: 'pills', labelKey: 'curated.kontextAktionen.gruppe.pills', felder: ['context_actions.pills'] },
          { id: 'dublette', labelKey: 'curated.kontextAktionen.gruppe.dublette', felder: ['context_actions.duplicate_greeting', 'context_actions.duplicate_pill_label'] },
          { id: 'dubletteEn', labelKey: 'curated.kontextAktionen.gruppe.dubletteEn', felder: ['context_actions.duplicate_greeting_en', 'context_actions.duplicate_pill_label_en'] },
          { id: 'ki', labelKey: 'curated.kontextAktionen.gruppe.ki', felder: ['context_actions.curate_prompt'] },
        ],
      },
    ],
  },
  {
    slug: 'identitaet',
    introKey: 'curated.identitaet.intro',
    // Rundgang 3: Reiter wie auf „Rolle & Schutz“ im Agent-Arbeitsbereich.
    reiter: [
      { id: 'sicherheit', labelKey: 'curated.schutz.reiter.sicherheit' },
      { id: 'persona', labelKey: 'curated.schutz.reiter.persona' },
      { id: 'regeln', labelKey: 'curated.schutz.reiter.regeln' },
    ],
    sections: [
      {
        area: '01-base/safety-config',
        reiter: 'sicherheit',
        sprung: { labelKey: 'curated.sprung.safetyLogs', slug: 'safety-logs' },
        labelKey: 'curated.identitaet.safety.label',
        hintKey: 'curated.identitaet.safety.hint',
        feature: 'safety-level',
      },
      {
        area: '01-base/base-persona',
        reiter: 'persona',
        labelKey: 'curated.identitaet.persona.label',
        hintKey: 'curated.identitaet.persona.hint',
      },
      {
        area: '01-base/guardrails',
        reiter: 'regeln',
        labelKey: 'curated.identitaet.guardrails.label',
        hintKey: 'curated.identitaet.guardrails.hint',
      },
      {
        area: '01-base/policy',
        reiter: 'regeln',
        labelKey: 'curated.identitaet.policy.label',
        hintKey: 'curated.identitaet.policy.hint',
      },
    ],
  },
  {
    slug: 'domain-wissen',
    introKey: 'curated.domainWissen.intro',
    sections: [
      {
        area: '02-domain/domain-rules',
        labelKey: 'curated.domainWissen.rules.label',
        hintKey: 'curated.domainWissen.rules.hint',
      },
      {
        area: '02-domain/wlo-plattform-wissen',
        labelKey: 'curated.domainWissen.platform.label',
        hintKey: 'curated.domainWissen.platform.hint',
      },
    ],
  },
  {
    // Paket 14: Tour und Lotse wirken in beiden Maschinen — vorher auf „Domänenwissen“, das
    // nur noch im Muster-Arbeitsbereich steht.
    slug: 'fuehrung',
    introKey: 'curated.fuehrung.intro',
    // Paket 15: drei Dinge, drei Reiter — die Tour, der Lotse und seine Regeln.
    reiter: [
      { id: 'tour', labelKey: 'curated.fuehrung.reiter.tour' },
      { id: 'lotse', labelKey: 'curated.fuehrung.reiter.lotse' },
      { id: 'regeln', labelKey: 'curated.fuehrung.reiter.regeln' },
    ],
    sections: [
      {
        area: '01-base/website-tour',
        zugeklappt: true,
        reiter: 'tour',
        labelKey: 'curated.domainWissen.tour.label',
        hintKey: 'curated.domainWissen.tour.hint',
        // Rundgang 3: in der Reihenfolge, in der die Tour läuft — Start und Texte zuerst, dann
        // die Website, die Besuchergruppen und ihre Wege.
        gruppen: [
          { id: 'start', labelKey: 'curated.fuehrung.gruppe.start', felder: ['website_tour.enabled', 'website_tour.trigger_phrases', 'website_tour.start_label'] },
          { id: 'texte', labelKey: 'curated.fuehrung.gruppe.texte', felder: ['website_tour.intro', 'website_tour.intro_en', 'website_tour.entry', 'website_tour.nudge', 'website_tour.nudge_en', 'website_tour.explore', 'website_tour.explore_en'] },
          { id: 'website', labelKey: 'curated.fuehrung.gruppe.website', felder: ['website_tour.base_host', 'website_tour.home_path', 'website_tour.content_hub', 'website_tour.contact_hub'] },
          { id: 'gruppen', labelKey: 'curated.fuehrung.gruppe.gruppen', felder: ['website_tour.groups'] },
          { id: 'links', labelKey: 'curated.fuehrung.gruppe.links', felder: ['website_tour.content_sublinks', 'website_tour.contact_links'] },
          { id: 'schritte', labelKey: 'curated.fuehrung.gruppe.schritte', felder: ['website_tour.steps'] },
          { id: 'doku', labelKey: 'curated.fuehrung.gruppe.doku', felder: ['website_tour.flows'] },
        ],
      },
      // ST-9: der Lotse zeigt wie die Web-Tour Wege auf die Plattform — bis
      // dahin nur als Dateiname unter „Alle Bereiche“ zu finden.
      {
        area: '01-base/guide-mode',
        zugeklappt: true,
        reiter: 'lotse',
        labelKey: 'curated.domainWissen.guideMode.label',
        hintKey: 'curated.domainWissen.guideMode.hint',
      },
      {
        area: '02-domain/guide-rules',
        zugeklappt: true,
        reiter: 'regeln',
        labelKey: 'curated.domainWissen.guideRules.label',
        hintKey: 'curated.domainWissen.guideRules.hint',
      },
    ],
  },
  {
    slug: 'material-formate',
    introKey: 'curated.materialFormate.intro',
    sections: [
      {
        // Paket 14 (D3): Liste und Detail mit gerenderter Vorschau statt eines Formulars über
        // alle 19 Typen — wie das alte Studio, dazu Querbezüge zu Aliasen und Vorrang.
        panel: 'material-typen',
        labelKey: 'curated.materialFormate.typen.label',
        hintKey: 'curated.materialFormate.typen.hint',
      },
      {
        area: '05-canvas/type-aliases',
        labelKey: 'curated.materialFormate.aliases.label',
        hintKey: 'curated.materialFormate.aliases.hint',
      },
      {
        area: '05-canvas/persona-priorities',
        labelKey: 'curated.materialFormate.priorities.label',
        hintKey: 'curated.materialFormate.priorities.hint',
      },
    ],
  },
  {
    slug: 'patterns',
    introKey: 'curated.patterns.intro',
    sections: [
      {
        area: '03-patterns',
        kind: 'group',
        labelKey: 'curated.patterns.patterns.label',
        hintKey: 'curated.patterns.patterns.hint',
        feature: 'pattern-tabs',
      },
    ],
  },
  {
    slug: 'dimensionen',
    introKey: 'curated.dimensionen.intro',
    // ST-4c (Paket 6): Reiter mit Zählern und eine Kopfkarte wie in ALT.
    layout: 'tabs',
    sections: [
      {
        area: '04-personas',
        kind: 'group',
        labelKey: 'curated.dimensionen.personas.label',
        hintKey: 'curated.dimensionen.personas.hint',
        count: 'personas',
        // Paket 15: die Anrede steht auf „Zielgruppen“ (gemeinsam) — hier nicht noch einmal.
        ohneFelder: ['frontmatter.formality'],
      },
      {
        area: '04-intents/intents',
        labelKey: 'curated.dimensionen.intents.label',
        hintKey: 'curated.dimensionen.intents.hint',
        count: 'intents',
      },
      {
        area: '04-states/states',
        labelKey: 'curated.dimensionen.states.label',
        hintKey: 'curated.dimensionen.states.hint',
        count: 'states',
      },
      {
        area: '04-entities/entities',
        labelKey: 'curated.dimensionen.entities.label',
        hintKey: 'curated.dimensionen.entities.hint',
        count: 'entities',
      },
      // ST-9: welche Wörter NICHT als Thema zählen — gehört zu den Entitäten.
      {
        area: '01-base/placeholder-topics',
        labelKey: 'curated.dimensionen.placeholderTopics.label',
        hintKey: 'curated.dimensionen.placeholderTopics.hint',
      },
      {
        area: '04-signals/signal-modulations',
        labelKey: 'curated.dimensionen.signals.label',
        hintKey: 'curated.dimensionen.signals.hint',
        count: 'signals',
      },
      {
        area: '01-base/tone-modifiers',
        labelKey: 'curated.dimensionen.tone.label',
        hintKey: 'curated.dimensionen.tone.hint',
      },
      // ST-9: feste Anker der Einordnung, zuletzt — sie übersteuern die Achsen
      // darüber und setzen voraus, dass man diese kennt.
      {
        area: '01-base/classify-overrides',
        labelKey: 'curated.dimensionen.classifyOverrides.label',
        hintKey: 'curated.dimensionen.classifyOverrides.hint',
      },
    ],
  },
];
