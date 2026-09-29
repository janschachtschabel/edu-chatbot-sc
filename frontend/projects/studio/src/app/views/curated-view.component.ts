/**
 * A curated config view (9-4b): the areas that belong to one editorial job,
 * on one page, each as its own disclosure panel.
 *
 * The component is the same for every such view — what differs is data, and
 * that lives in `curated-views.ts`. ALT wrote one React component per view;
 * nine of them together were mostly the same "load area, render fields, save"
 * repeated with different labels.
 *
 * Each panel saves its own area. There is deliberately no "save everything"
 * button: the store writes one area per request, so a combined save would be
 * several requests that can half-fail, and the page would have to explain
 * which half.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, viewChildren,
} from '@angular/core';

import { EffectsApi, type Engine } from '../core/effects-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { StudioView } from '../studio-views';
import { AgentProbeComponent } from './agent-probe.component';
import { AgentPromptComponent } from './agent-prompt.component';
import { AgentSkillsComponent } from './agent-skills.component';
import { AgentTesterComponent } from './agent-tester.component';
import { AgentToolsComponent } from './agent-tools.component';
import { AreaSectionComponent } from './area-section.component';
import {
  type CuratedAreaSection, type CuratedPanelSection, curatedView, isAreaSection,
} from './curated-views';
import { GroupSectionComponent } from './group-section.component';
import { MasterSkillComponent } from './master-skill.component';
import { McpRegistryComponent } from './mcp-registry.component';
import { PrivacyPurgeComponent } from './privacy-purge.component';
import { RagAreasComponent } from './rag-areas.component';
import { RagIngestComponent } from './rag-ingest.component';
import { warnOnUnload } from './unsaved-changes.guard';

/** One rendered row of the page, already narrowed to the shape it renders as. */
type Entry =
  | { readonly kind: 'area'; readonly key: string;
      readonly area: CuratedAreaSection; readonly first: boolean }
  | { readonly kind: 'panel'; readonly key: string;
      readonly panel: CuratedPanelSection; readonly first: boolean };

@Component({
  selector: 'studio-curated-view',
  imports: [
    AreaSectionComponent, GroupSectionComponent,
    RagAreasComponent, RagIngestComponent, McpRegistryComponent, AgentTesterComponent,
    MasterSkillComponent, PrivacyPurgeComponent, AgentToolsComponent, AgentSkillsComponent,
    AgentPromptComponent, AgentProbeComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './curated-view.component.html',
  styleUrl: './curated-view.component.scss',
})
export class CuratedViewComponent {
  /** Bound from the route's `data.view` (withComponentInputBinding). */
  readonly view = input.required<StudioView>();

  protected readonly t = inject(StudioLanguageService).t;

  readonly definition = computed(() => curatedView(this.view().slug));

  private readonly effects = inject(EffectsApi).effects;

  /**
   * ST-5: nutzt die Vorgabe-Maschine KEINE Einstellung dieser Seite, sagt die
   * Seite es oben — statt dass man es an jedem Abschnitt einzeln abliest.
   * Panels zählen nicht mit (keine Config-Bereiche); ein Bereich ohne
   * Zuordnung macht das Banner still, statt es zu raten.
   */
  readonly banner = computed(() => {
    const effects = this.effects();
    const areas = (this.definition()?.sections ?? []).filter(isAreaSection);
    if (!effects || areas.length === 0) return '';
    const wirkung = areas.map((section) => effects.areas[section.area]);
    if (wirkung.some((w) => !w)) return '';
    const other: Engine = effects.engine === 'pattern' ? 'agent' : 'pattern';
    const namen = {
      engine: this.t(`effect.engine.${effects.engine}`),
      other: this.t(`effect.engine.${other}`),
    };
    const aktiv = wirkung.map((w) => w[effects.engine]);
    if (!aktiv.every((level) => level === 'keine' || level === 'krise')) return '';
    // Krisen-Züge beantwortet auch unter der Agent-Schleife der Muster-Weg
    // (SF-1): „wirkt dort nicht" wäre für diese Seite falsch.
    if (aktiv.includes('krise')) return this.t('effect.bannerCrisis', namen);
    return wirkung.every((w) => w[other] === 'keine')
      ? this.t('effect.bannerNowhere')
      : this.t('effect.banner', namen);
  });

  readonly sections = viewChildren(AreaSectionComponent);
  readonly groupSections = viewChildren(GroupSectionComponent);
  readonly mcpSections = viewChildren(McpRegistryComponent);

  /** For the leave guard: any panel with unsaved edits, open or collapsed —
   *  every kind that HAS a save button, or a dirty one would leave without a
   *  word. The RAG panels are not here on purpose: their actions (ingest,
   *  delete) are immediate, so they are never in an unsaved state — nor is
   *  the purge panel (ST-6). */
  readonly dirty = computed(() =>
    [...this.sections(), ...this.groupSections(), ...this.mcpSections()]
      .some((section) => section.dirty()),
  );

  /**
   * The sections pre-sorted into the two shapes the template renders. A
   * template cannot apply a type guard, so the narrowing happens here and the
   * template only switches on `kind`.
   */
  readonly entries = computed<readonly Entry[]>(() =>
    (this.definition()?.sections ?? []).map((section, index) =>
      isAreaSection(section)
        ? { kind: 'area', key: section.area, area: section, first: index === 0 }
        : { kind: 'panel', key: section.panel, panel: section, first: index === 0 },
    ),
  );

  constructor() {
    warnOnUnload(() => this.dirty());
  }
}
