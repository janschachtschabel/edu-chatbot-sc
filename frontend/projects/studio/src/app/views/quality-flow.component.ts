/**
 * The conversation flow (9-5c): which phases turns sat in, and which phase
 * followed which.
 *
 * Three ranked tables from one payload, all rendered by `QualityBarsComponent` —
 * a transition is a key with a count, exactly like a distribution, so the
 * component that already does that is fed a `{"S2 → S3": 7}` map instead of
 * hand-building a second set of bars. ALT drew its own flex bars here, twice,
 * with the label column pinned to 200px and `text-overflow: ellipsis` — which
 * silently cut the very ids the table exists to show.
 *
 * Self-loops stay separate, as in ALT: two S2 turns in a row means a second slot
 * was missing, which is a different observation from a move between phases.
 *
 * ALT's `properTrans.slice(0, 20)` is not ported — it cannot fire. Three phases
 * are configured (S1 Orientierung, S2 Klärung, S3 Aktion), so there are at most
 * nine ordered pairs. ALT's legend also still explains sub-phases ("S3 Suche" →
 * "S3 Ergebnis-Kuratierung") that were folded into S3 Aktion; the text here
 * names the three phases that exist.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked,
} from '@angular/core';

import { AsyncData } from '../core/async-data';
import { formatWhole } from '../core/format';
import { QualityApi, type QualityScope, type StateFlow } from '../core/quality-api.service';
import { AsyncStateComponent } from './async-state.component';
import { QualityBarsComponent } from './quality-bars.component';

/** ALT's defaults for the two knobs. */
const DEFAULT_DAYS = 30;
const DEFAULT_MIN_COUNT = 1;

@Component({
  selector: 'studio-quality-flow',
  imports: [AsyncStateComponent, QualityBarsComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './quality-flow.component.html',
  styleUrl: './quality-flow.component.scss',
})
export class QualityFlowComponent {
  private readonly api = inject(QualityApi);

  readonly scope = input.required<QualityScope>();

  readonly days = signal(DEFAULT_DAYS);
  readonly minCount = signal(DEFAULT_MIN_COUNT);

  readonly flow = new AsyncData<StateFlow>(
    () => this.api.stateTransitions(this.scope(), this.days(), this.minCount()));

  readonly value = computed(() => this.flow.value());

  /** No turn carried a state in the window — nothing to show, not even phases. */
  readonly isEmpty = computed(() => this.value()?.total_turns === 0);

  readonly distribution = computed(() => this.value()?.state_distribution ?? {});

  /** A move between two different phases: "S2 → S3". */
  readonly moves = computed(() => this.toMap((t) => t.prev !== t.next));

  /** The same phase twice in a row — a second slot round, another canvas edit. */
  readonly repeats = computed(() => this.toMap((t) => t.prev === t.next));

  readonly hasMoves = computed(() => Object.keys(this.moves()).length > 0);
  readonly hasRepeats = computed(() => Object.keys(this.repeats()).length > 0);

  constructor() {
    effect(() => {
      this.scope();
      this.days();
      this.minCount();
      untracked(() => void this.flow.reload());
    });
  }

  reload(): void {
    void this.flow.reload();
  }

  onDays(value: string): void {
    this.days.set(Math.max(1, Number.parseInt(value, 10) || DEFAULT_DAYS));
  }

  onMinCount(value: string): void {
    this.minCount.set(Math.max(1, Number.parseInt(value, 10) || DEFAULT_MIN_COUNT));
  }

  whole(value: number): string {
    return formatWhole(value);
  }

  /**
   * The transitions as a ranked-table map. (prev, next) pairs are unique in the
   * payload, so no key can collide.
   */
  private toMap(keep: (t: StateFlow['transitions'][number]) => boolean): Record<string, number> {
    const out: Record<string, number> = {};
    for (const transition of this.value()?.transitions ?? []) {
      if (!keep(transition)) continue;
      const key = transition.prev === transition.next
        ? `${transition.prev} ↻`
        : `${transition.prev} → ${transition.next}`;
      out[key] = transition.count;
    }
    return out;
  }
}
