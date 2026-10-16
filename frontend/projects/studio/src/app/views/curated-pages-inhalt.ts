/**
 * Die kuratierten Seiten für Inhalte (9-4b): Begrüßung, Kontext-Aktionen,
 * Identität, Domain-Wissen, Material-Formate, Muster, Dimensionen.
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
        labelKey: 'curated.kontextAktionen.actions.label',
        hintKey: 'curated.kontextAktionen.actions.hint',
      },
    ],
  },
  {
    slug: 'identitaet',
    introKey: 'curated.identitaet.intro',
    sections: [
      {
        area: '01-base/safety-config',
        labelKey: 'curated.identitaet.safety.label',
        hintKey: 'curated.identitaet.safety.hint',
        feature: 'safety-level',
      },
      {
        area: '01-base/base-persona',
        labelKey: 'curated.identitaet.persona.label',
        hintKey: 'curated.identitaet.persona.hint',
      },
      {
        area: '01-base/guardrails',
        labelKey: 'curated.identitaet.guardrails.label',
        hintKey: 'curated.identitaet.guardrails.hint',
      },
      {
        area: '01-base/policy',
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
      {
        area: '01-base/website-tour',
        labelKey: 'curated.domainWissen.tour.label',
        hintKey: 'curated.domainWissen.tour.hint',
      },
      // ST-9: der Lotse zeigt wie die Web-Tour Wege auf die Plattform — bis
      // dahin nur als Dateiname unter „Alle Bereiche“ zu finden.
      {
        area: '01-base/guide-mode',
        labelKey: 'curated.domainWissen.guideMode.label',
        hintKey: 'curated.domainWissen.guideMode.hint',
      },
      {
        area: '02-domain/guide-rules',
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
        area: '05-canvas/material-types',
        labelKey: 'curated.materialFormate.types.label',
        hintKey: 'curated.materialFormate.types.hint',
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
