/**
 * Backend status in the header (P9-2).
 *
 * Three deliberate improvements over ALT (page.tsx:274-293, :412-417):
 *  - it POLLS. ALT derived the dot from one `GET /api/config/elements` on mount
 *    and never re-checked, so a backend that died mid-session still showed
 *    "Verbunden" until the next save failed.
 *  - it asks `/health`, the endpoint that means "is the backend up", instead of
 *    a config endpoint that happened to be loaded anyway.
 *  - it has an 'unknown' state. ALT initialised to `false`, so every page load
 *    showed a red "Offline" dot for the whole first round-trip.
 *
 * `role="status"` + polite live region so the flip is announced; ALT's dot was an
 * empty `<span>` with no accessible name and no live region at all.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';

import { StudioApi } from '../core/studio-api.service';

type Health = 'unknown' | 'online' | 'offline';

const POLL_MS = 10_000;

const LABELS: Record<Health, string> = {
  unknown: 'Verbindung wird geprüft',
  online: 'Verbunden',
  offline: 'Offline',
};

@Component({
  selector: 'studio-status-indicator',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="status" role="status">
      <span class="dot" [class]="'dot--' + health()" aria-hidden="true"></span>
      <!-- The text is the accessible name; the dot only repeats it in colour,
           so status is never signalled by colour alone (SC 1.4.1). -->
      <span class="label">{{ label() }}</span>
    </span>
  `,
  styles: `
    .status {
      display: inline-flex;
      align-items: center;
      gap: var(--st-2);
      font-size: 0.8125rem;
      color: var(--st-text-muted);
      white-space: nowrap;
    }
    .dot {
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 50%;
      flex: none;
    }
    .dot--unknown { background: var(--st-unknown-dot); }
    .dot--online { background: var(--st-ok-dot); }
    .dot--offline { background: var(--st-danger-dot); }
  `,
})
export class StatusIndicatorComponent implements OnInit {
  private readonly api = inject(StudioApi);
  private readonly destroyRef = inject(DestroyRef);

  readonly health = signal<Health>('unknown');
  readonly label = () => LABELS[this.health()];

  ngOnInit(): void {
    void this.check();
    const timer = setInterval(() => void this.check(), POLL_MS);
    this.destroyRef.onDestroy(() => clearInterval(timer));
  }

  private async check(): Promise<void> {
    try {
      await this.api.get('/health');
      this.health.set('online');
    } catch {
      // Any failure — unreachable, 5xx, or a 401 on the way through the BFF —
      // means the editor cannot save right now. One honest state for all of them.
      this.health.set('offline');
    }
  }
}
