/**
 * The evaluation dashboard (9-5d) — the shell that makes its panels reachable.
 *
 * Three tabs: the runs (list + both start forms + the per-run detail), the
 * cross-run trends, and the pattern usage. A panel mounts on its first visit and
 * then stays, so switching tabs does not re-fetch; each panel owns its own
 * `AsyncData` (9-5a rule: one per endpoint).
 *
 * Both start forms live in the same panel as the list rather than in a tab of
 * their own: a run takes minutes, and its only progress display is that list.
 * Since the 2026-08-22 feedback they sit COLLAPSED BELOW it — whoever opens the
 * page wants the active run, not the flow list of the next start. The shell
 * wires them together — the list is what knows whether a run is in flight (the
 * backend allows one and answers 409), so `busy` is derived from it instead of
 * each start panel reading the same endpoint again.
 */
import {
  ChangeDetectionStrategy, Component, Injector, afterNextRender, computed, effect, inject,
  signal, untracked, viewChild,
} from '@angular/core';

import { StudioAnsicht } from '../core/studio-ansicht.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { DASHBOARD_SECTIONS } from './area-homes';
import { AreaSectionComponent } from './area-section.component';
import { EvalCompareComponent } from './eval-compare.component';
import { EvalGenerativeStartComponent } from './eval-generative-start.component';
import { EvalGoldenStartComponent } from './eval-golden-start.component';
import { EvalPatternUsageComponent } from './eval-pattern-usage.component';
import { EvalRunDetailComponent } from './eval-run-detail.component';
import { EvalRunsComponent } from './eval-runs.component';
import { EvalTrendsComponent } from './eval-trends.component';
import { TabBarComponent, type TabDef } from './tab-bar.component';
import { warnOnUnload } from './unsaved-changes.guard';

/**
 * Nur die Kennungen und ihre Schlüssel — die Beschriftungen entstehen erst beim
 * Rendern (C1-d4b). Standen sie hier fertig, fröre die Sprache ein, die beim
 * Laden des Moduls gerade galt.
 */
const TAB_KEYS: readonly { readonly id: string; readonly labelKey: string }[] = [
  { id: 'laeufe', labelKey: 'eval.tab.laeufe' },
  { id: 'trends', labelKey: 'eval.tab.trends' },
  { id: 'pattern', labelKey: 'eval.tab.pattern' },
  // ST-9: die Flows neben den Läufen, die sie abspielen
  { id: 'goldflows', labelKey: 'eval.tab.goldflows' },
];

@Component({
  selector: 'studio-evaluation',
  imports: [
    TabBarComponent, EvalRunsComponent, EvalTrendsComponent,
    EvalGenerativeStartComponent, EvalGoldenStartComponent, EvalRunDetailComponent,
    EvalPatternUsageComponent, AreaSectionComponent, EvalCompareComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './evaluation.component.html',
  styleUrl: './evaluation.component.scss',
})
export class EvaluationComponent {
  protected readonly t = inject(StudioLanguageService).t;

  private readonly injector = inject(Injector);

  private readonly ansicht = inject(StudioAnsicht).ansicht;
  /** Paket 15 (A5): die Pattern-Nutzung gehört zur Muster-Maschine — nur dort ein Reiter. */
  readonly musterBereich = computed(() => this.ansicht() === 'pattern');

  readonly tabs = computed<readonly TabDef[]>(() => TAB_KEYS
    .filter((tab) => tab.id !== 'pattern' || this.musterBereich())
    .map((tab) => ({ id: tab.id, label: this.t(tab.labelKey) })));

  readonly active = signal(TAB_KEYS[0].id);

  private readonly runsPanel = viewChild(EvalRunsComponent);

  /** Nur montiert, solange ein Lauf geöffnet ist — deshalb ein Signal. */
  private readonly detailPanel = viewChild(EvalRunDetailComponent);

  private readonly goldenStart = viewChild(EvalGoldenStartComponent);

  /** Die Gold-Flows als Bereich (ST-9) — derselbe Abschnitt wie auf den
   *  Konfigurationsseiten, mit Speichern, Verwerfen und Rohtext. */
  readonly goldFlowsSection = DASHBOARD_SECTIONS.evaluation[0];
  readonly goldFlows = viewChild(AreaSectionComponent);
  /** Für den Verlassen-Schutz: die Seite bearbeitet seit ST-9 einen Bereich. */
  readonly dirty = computed(() => this.goldFlows()?.dirty() ?? false);

  constructor() {
    warnOnUnload(() => this.dirty());
    // Wechselt der Arbeitsbereich zum Agent, während die Pattern-Nutzung offen ist. Sie gilt dann
    // auch als ungeöffnet — sonst lüde sie beim Zurückwechseln verborgen neu (Review-Runde 2).
    effect(() => {
      if (this.musterBereich()) return;
      untracked(() => {
        if (this.active() === 'pattern') this.active.set(TAB_KEYS[0].id);
        if (this.visited().has('pattern')) {
          this.visited.update((seen) => new Set([...seen].filter((id) => id !== 'pattern')));
        }
      });
    });
  }

  /** The run list polls while anything runs; that is the honest source. */
  readonly busy = computed(() => this.runsPanel()?.isPolling() ?? false);

  private readonly visited = signal<ReadonlySet<string>>(new Set([TAB_KEYS[0].id]));

  /** Whether a panel has been opened at least once and may stay mounted. */
  readonly shows = computed(() => {
    const seen = this.visited();
    return (id: string): boolean => seen.has(id);
  });

  select(id: string): void {
    // Wer von den Gold-Flows kommt, hat sie womöglich geändert: das
    // Start-Formular liest seine Flow-Liste selbst und nur einmal.
    if (this.active() === 'goldflows' && id !== 'goldflows') {
      void this.goldenStart()?.flowList.reload();
    }
    this.active.set(id);
    if (!this.visited().has(id)) {
      this.visited.update((seen) => new Set(seen).add(id));
    }
  }

  /** A fresh run is missing from the list until it re-reads. */
  onStarted(): void {
    this.runsPanel()?.reload();
  }

  /** Which run the detail panel shows; '' = none. Owned here, because the list
   *  only ever names a run and the panel must survive the list re-reading. */
  readonly openRun = signal('');

  openDetail(id: string): void {
    this.openRun.update((current) => (current === id ? '' : id));
  }

  /** Schließt das Detail und holt den Fokus zur Zeile seines Laufs zurück —
   *  das Detail stand unter der ganzen Liste. */
  closeDetail(): void {
    const id = this.openRun();
    this.openRun.set('');
    if (id) {
      afterNextRender(() => this.runsPanel()?.focusRow(id), { injector: this.injector });
    }
  }

  /** ST-7c: welche Läufe der Vergleich zeigt; leer = keiner offen. */
  readonly compareIds = signal<readonly string[]>([]);

  openCompare(ids: readonly string[]): void {
    this.compareIds.set(ids);
  }

  closeCompare(): void {
    this.compareIds.set([]);
  }

  /** Löschungen aus der Liste (Befund 2026-08-22): das offene Detail eines
   *  gelöschten Laufs zeigte sonst nur noch „run not found". `null` = Sammel-
   *  Löschung, deren Treffer die Liste nicht kennt — dann vorsorglich zu. */
  onRunDeleted(id: string | null): void {
    if (id === null || id === this.openRun()) this.closeDetail();
  }

  /** Gestoppte Läufe (Befund 2026-08-22): das Panel ist eine Momentaufnahme
   *  und zeigte nach dem Stopp weiter „läuft". Schließen wäre hier falsch —
   *  der Teilstand bleibt ja erhalten —, also neu lesen. */
  onRunStopped(id: string): void {
    if (id === this.openRun()) this.detailPanel()?.reload();
  }
}
