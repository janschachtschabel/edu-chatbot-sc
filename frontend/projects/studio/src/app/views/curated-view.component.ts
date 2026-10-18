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
  ChangeDetectionStrategy, Component, computed, inject, input, signal, viewChildren,
} from '@angular/core';

import { EffectsApi, type Engine } from '../core/effects-api.service';
import { StudioAnsicht } from '../core/studio-ansicht.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { StudioView } from '../studio-views';
import { AgentProbeComponent } from './agent-probe.component';
import { AnredeComponent } from './anrede.component';
import { MaterialTypenComponent } from './material-typen.component';
import { AgentPromptComponent } from './agent-prompt.component';
import { AgentSkillsComponent } from './agent-skills.component';
import { AgentTesterComponent } from './agent-tester.component';
import { AgentToolsComponent } from './agent-tools.component';
import { AreaSectionComponent } from './area-section.component';
import { CuratedTabsComponent } from './curated-tabs.component';
import {
  type CuratedAreaSection, type CuratedPanelSection, curatedView, isAreaSection,
} from './curated-views';
import { GroupSectionComponent } from './group-section.component';
import { MasterSkillComponent } from './master-skill.component';
import { McpRegistryComponent } from './mcp-registry.component';
import { PrivacyPurgeComponent } from './privacy-purge.component';
import { RagAreasComponent } from './rag-areas.component';
import { RagIngestComponent } from './rag-ingest.component';
import { RetentionComponent } from './retention.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';
import { warnOnUnload } from './unsaved-changes.guard';

/** One rendered row of the page, already narrowed to the shape it renders as. */
type Entry =
  | { readonly kind: 'area'; readonly key: string;
      readonly area: CuratedAreaSection; readonly first: boolean }
  | { readonly kind: 'panel'; readonly key: string;
      readonly panel: CuratedPanelSection; readonly first: boolean };

/** Bereiche, die die Materialformat-Liste mitliest (Aliase, Vorrang). */
const MATERIAL_NEBENBEREICHE = new Set(['05-canvas/type-aliases', '05-canvas/persona-priorities']);

@Component({
  selector: 'studio-curated-view',
  imports: [
    AreaSectionComponent, CuratedTabsComponent, GroupSectionComponent,
    RagAreasComponent, RagIngestComponent, McpRegistryComponent, AgentTesterComponent,
    MasterSkillComponent, PrivacyPurgeComponent, RetentionComponent, AgentToolsComponent,
    AgentSkillsComponent, AgentPromptComponent, AgentProbeComponent, AnredeComponent,
    MaterialTypenComponent, TabBarComponent,
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

  private readonly effectsApi = inject(EffectsApi);
  private readonly effects = this.effectsApi.effects;
  private readonly ansicht = inject(StudioAnsicht).ansicht;

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

  /** Paket 13 (E6): die Vorgabe-Maschine steht in `01-base/engine`. Nach ihrem Speichern gilt
   *  die neue sofort — Plaketten, Banner und eine Ansicht ohne eigene Wahl folgen ihr, nicht
   *  erst nach dem nächsten Seitenwechsel. */
  gespeichert(area: string): void {
    if (area === '01-base/engine') void this.effectsApi.refresh();
    if (MATERIAL_NEBENBEREICHE.has(area)) {
      for (const liste of this.materialTypen()) void liste.nebenbereicheNeu();
    }
  }

  readonly sections = viewChildren(AreaSectionComponent);
  readonly groupSections = viewChildren(GroupSectionComponent);
  readonly mcpSections = viewChildren(McpRegistryComponent);
  /** Paket 14 (D3): der Entwurf eines Materialtyps zählt für den Verlassen-Schutz mit —
   *  ebenso eine ungespeicherte Anrede (Review #2). */
  readonly materialTypen = viewChildren(MaterialTypenComponent);
  readonly anreden = viewChildren(AnredeComponent);
  /** Paket 15: die Werkzeug-Schalter sind ein ungespeicherter Stand der MCP-Server-Liste. */
  readonly werkzeuge = viewChildren(AgentToolsComponent);
  /** ST-4c: eine Seite mit `layout: 'tabs'` hängt ihre Abschnitte in die
   *  Reiter-Komponente — deren `dirty` zählt hier mit. */
  readonly tabbed = viewChildren(CuratedTabsComponent);
  readonly tabSections = computed(
    () => (this.definition()?.sections ?? []).filter(isAreaSection));

  /** For the leave guard: any panel with unsaved edits, open or collapsed —
   *  every kind that HAS a save button, or a dirty one would leave without a
   *  word. The RAG panels are not here on purpose: their actions (ingest,
   *  delete) are immediate, so they are never in an unsaved state — nor is
   *  the purge panel (ST-6). */
  readonly dirty = computed(() =>
    [...this.sections(), ...this.groupSections(), ...this.mcpSections(), ...this.tabbed(),
      ...this.materialTypen(), ...this.anreden(), ...this.werkzeuge()]
      .some((section) => section.dirty()),
  );

  /**
   * The sections pre-sorted into the two shapes the template renders. A
   * template cannot apply a type guard, so the narrowing happens here and the
   * template only switches on `kind`.
   */
  readonly entries = computed<readonly Entry[]>(() => {
    // Paket 16, C8: was im Arbeitsbereich zuerst gehört, rückt nach vorn (stabil).
    const ansicht = this.ansicht();
    const alle = this.definition()?.sections ?? [];
    const sections = [
      ...alle.filter((s) => isAreaSection(s) && s.zuerstIn === ansicht),
      ...alle.filter((s) => !(isAreaSection(s) && s.zuerstIn === ansicht)),
    ];
    // Paket 15: mit Reitern öffnet der erste Abschnitt JEDES Reiters.
    const erster = (index: number) =>
      sections.findIndex((s) => s.reiter === sections[index].reiter) === index;
    return sections.map((section, index) =>
      isAreaSection(section)
        ? { kind: 'area', key: section.area, area: section, first: erster(index) }
        : { kind: 'panel', key: section.panel, panel: section, first: erster(index) },
    );
  });

  // ── Paket 15: Reiter über den Abschnitten ──────────────────────────
  readonly reiterTabs = computed<readonly TabDef[]>(() =>
    (this.definition()?.reiter ?? []).map((r) => ({ id: r.id, label: this.t(r.labelKey) })));
  private readonly gewaehlterReiter = signal('');
  readonly aktiverReiter = computed(() => {
    const ids = this.reiterTabs().map((r) => r.id);
    return ids.includes(this.gewaehlterReiter()) ? this.gewaehlterReiter() : (ids[0] ?? '');
  });

  /** Die Abschnitte je Reiter (ohne Reiter: ein Block ohne Kennung). */
  readonly bloecke = computed<readonly { id: string; entries: readonly Entry[] }[]>(() => {
    const tabs = this.reiterTabs();
    if (tabs.length === 0) return [{ id: '', entries: this.entries() }];
    return tabs.map((tab) => ({
      id: tab.id,
      entries: this.entries().filter((entry) => reiterVon(entry) === tab.id),
    }));
  });

  waehleReiter(id: string): void {
    this.gewaehlterReiter.set(id);
  }

  /** Der erste Abschnitt eines Reiters öffnet erst, wenn sein Reiter sichtbar ist — sonst
   *  lüden alle Reiter beim Aufruf der Seite ihre Daten. */
  offen(entry: Entry): boolean {
    return entry.first && this.sichtbar(entry);
  }

  /** Ohne Reiter ist jeder Abschnitt sichtbar; mit Reitern nur die des offenen. */
  sichtbar(entry: Entry): boolean {
    return this.reiterTabs().length === 0 || reiterVon(entry) === this.aktiverReiter();
  }

  constructor() {
    warnOnUnload(() => this.dirty());
  }
}

function reiterVon(entry: Entry): string | undefined {
  return entry.kind === 'area' ? entry.area.reiter : entry.panel.reiter;
}
