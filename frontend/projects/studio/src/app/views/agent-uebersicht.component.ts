/**
 * Die Agent-Übersicht (Paket 14, C1) — Startseite des Agent-Arbeitsbereichs.
 *
 * Von oben nach unten: mit welcher Maschine der Server antwortet (und wo man das ändert), der
 * Master-Skill — das bestehende Panel, aufgeklappt, mit Zustand, NodeID, Stand und den Links
 * ins Repositorium und in den md-editor —, ein Wegweiser zu den Agent-Seiten und der letzte
 * fertige Lauf der Agent-Schleife. Eine Liste mit klarer Reihenfolge, kein Kachelraster.
 *
 * Das Master-Skill-Panel steht auch auf „Skills“ (seit Paket 15): dort zum Pflegen, hier als
 * Zustand. Ein zweiter, schmalerer Nachbau hätte dieselben Felder ein zweites Mal gepflegt.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AsyncData } from '../core/async-data';
import { EffectsApi } from '../core/effects-api.service';
import { EvalApi } from '../core/eval-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import { MasterSkillComponent } from './master-skill.component';

/** Wohin der Wegweiser führt — Ziel und Katalog-Schlüssel der Kurzbeschreibung. */
const WEGE: readonly { readonly slug: string; readonly descKey: string }[] = [
  { slug: 'agent-rolle', descKey: 'view.agent-rolle.desc' },
  { slug: 'agent-prompt', descKey: 'view.agent-prompt.desc' },
  // Paket 15: gemeinsame Seiten — sie gelten auch für die Muster-Maschine.
  { slug: 'werkzeuge', descKey: 'view.werkzeuge.desc' },
  { slug: 'skills', descKey: 'view.skills.desc' },
  { slug: 'evaluation', descKey: 'agentUebersicht.wege.evaluation' },
];

const MASTER_SKILL: CuratedPanelSection = {
  panel: 'master-skill',
  labelKey: 'curated.agent.masterSkill.label',
  hintKey: 'curated.agent.masterSkill.hint',
};

@Component({
  selector: 'studio-agent-uebersicht',
  imports: [MasterSkillComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-uebersicht.component.html',
  styleUrl: './agent-uebersicht.component.scss',
})
export class AgentUebersichtComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);
  private readonly effects = inject(EffectsApi).effects;
  private readonly evalApi = inject(EvalApi);

  readonly masterSkill = MASTER_SKILL;
  readonly wege = WEGE;

  readonly zustand = computed(() => {
    const engine = this.effects()?.engine;
    return this.t(engine === 'agent' ? 'agentUebersicht.zustand.agent'
      : engine === 'pattern' ? 'agentUebersicht.zustand.pattern'
        : 'agentUebersicht.zustand.unbekannt');
  });

  readonly laeufe = new AsyncData(() => this.evalApi.runs('agent'), this.t);

  /** Der jüngste fertige Lauf — ein laufender hat noch keine Note. */
  readonly letzterLauf = computed(() => {
    const lauf = (this.laeufe.value() ?? []).find((r) => r.status === 'done');
    if (!lauf) return null;
    return this.t('agentUebersicht.lauf.text', {
      datum: this.fmt.dateTime(lauf.created_at),
      score: lauf.avg_score === null ? '—' : this.fmt.decimal(lauf.avg_score),
    });
  });

  constructor() {
    void this.laeufe.reload();
  }
}
