/**
 * Die Agent-Übersicht (Paket 14, C1; Rundgang 3) — Startseite des Agent-Arbeitsbereichs.
 *
 * Von oben nach unten: mit welcher Maschine der Server antwortet (und wo man das ändert), die
 * Statusleiste wie im Muster-Bereich — Modell, Grundstand, letzter Lauf, hier nur der
 * Agent-Schleife —, der Master-Skill, der Weg einer Frage durch die Agent-Schleife mit Sprüngen
 * zu den Seiten, die ihn steuern, und die Testseiten des Widgets.
 *
 * Das Master-Skill-Panel steht auch auf „Skills“ (seit Paket 15): dort zum Pflegen, hier als
 * Zustand. Ein zweiter, schmalerer Nachbau hätte dieselben Felder ein zweites Mal gepflegt.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EffectsApi } from '../core/effects-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import { MasterSkillComponent } from './master-skill.component';
import { StatusStripComponent } from './status-strip.component';

/** Der Weg einer Frage durch die Agent-Schleife — Schicht für Schicht mit der steuernden Seite. */
const SCHICHTEN: readonly { readonly id: string; readonly slug: string }[] = [
  { id: 'sicherheit', slug: 'agent-rolle' },
  { id: 'rolle', slug: 'agent-rolle' },
  { id: 'skill', slug: 'skills' },
  { id: 'werkzeuge', slug: 'werkzeuge' },
  { id: 'wissen', slug: 'wissen' },
  { id: 'antwort', slug: 'anzeige' },
];

/** Die Testseiten des Widgets (`api/widget.py`) — vom Backend selbst ausgeliefert. */
const TESTSEITEN: readonly { readonly id: string; readonly href: string }[] = [
  { id: 'start', href: '/widget/' },
  { id: 'inline', href: '/widget/inline' },
  { id: 'classic', href: '/widget/classic' },
  { id: 'frameless', href: '/widget/frameless' },
];

const MASTER_SKILL: CuratedPanelSection = {
  panel: 'master-skill',
  labelKey: 'curated.agent.masterSkill.label',
  hintKey: 'curated.agent.masterSkill.hint',
};

@Component({
  selector: 'studio-agent-uebersicht',
  imports: [MasterSkillComponent, RouterLink, StatusStripComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-uebersicht.component.html',
  styleUrl: './agent-uebersicht.component.scss',
})
export class AgentUebersichtComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly effects = inject(EffectsApi).effects;

  readonly masterSkill = MASTER_SKILL;
  readonly schichten = SCHICHTEN;
  readonly testseiten = TESTSEITEN;

  readonly zustand = computed(() => {
    const engine = this.effects()?.engine;
    return this.t(engine === 'agent' ? 'agentUebersicht.zustand.agent'
      : engine === 'pattern' ? 'agentUebersicht.zustand.pattern'
        : 'agentUebersicht.zustand.unbekannt');
  });
}
