/**
 * Löschen über ALLE Sitzungen und Datenbank-Wartung (ST-6), als Panel der
 * Datenschutz-Seite.
 *
 * ALT hatte beides auf seiner Datenschutz-Seite (drei Lösch-Karten, zwei
 * `window.confirm()`); im NEU gab es bis ST-6 die Endpunkte, aber keine
 * Bedienung. Die Rückfrage steht inline wie in den Schreib-Panels der
 * Sicherung (`_ops-panel.scss`), für die Lösch-Karten aber zweistufig: sie
 * löschen für alle Sitzungen und unwiderruflich, und die Studio-Sicherung
 * umfasst nur die Konfiguration. Das Aufräumen (VACUUM) zerstört nichts und
 * fragt einmal.
 *
 * Der Fokus geht beim Scharfschalten auf „Abbrechen" — die harmlose Wahl, wie
 * im Warn-Dialog (APG alertdialog) — und nach Abbruch oder Abschluss zurück auf
 * den Knopf der Karte: der gedrückte Knopf verschwindet, und ohne das landete
 * der Fokus auf dem `<body>`.
 */
import {
  ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, signal,
} from '@angular/core';

import { ActionState } from '../core/action-state';
import { describeApiError } from '../core/async-data';
import { injectFocus } from '../core/inject-focus';
import {
  type DbStats, type PurgeCounts, type PurgeScope, SessionsApi,
} from '../core/sessions-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

type CardId = 'inhalte' | 'sitzungen' | 'alles';

interface PurgeCard {
  readonly id: CardId;
  readonly scope: PurgeScope;
}

const CONTENT = { messages: true, memory: true, quality_logs: true } as const;

/** Jede Karte nimmt die vorige und eines mehr — ALTs drei Karten. */
const PURGE_CARDS: readonly PurgeCard[] = [
  { id: 'inhalte', scope: { ...CONTENT, safety_logs: false, sessions: false } },
  { id: 'sitzungen', scope: { ...CONTENT, safety_logs: false, sessions: true } },
  { id: 'alles', scope: { ...CONTENT, safety_logs: true, sessions: true } },
];

/** Reihenfolge im Ergebnissatz — die, in der `purge_all` die Tabellen leert. */
const COUNT_ORDER: readonly (keyof PurgeScope)[] = [
  'messages', 'memory', 'quality_logs', 'safety_logs', 'sessions',
];

/** Welche Rückfrage offen ist. `db` = das Aufräumen, das nur Stufe 1 kennt. */
interface Armed {
  readonly card: CardId | 'db';
  readonly step: 1 | 2;
}

@Component({
  selector: 'studio-privacy-purge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './privacy-purge.component.html',
  styleUrl: './privacy-purge.component.scss',
})
export class PrivacyPurgeComponent {
  private readonly sessions = inject(SessionsApi);
  private readonly lang = inject(StudioLanguageService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly focusAfterRender = injectFocus();
  protected readonly t = this.lang.t;
  protected readonly fmt = inject(StudioFormat);

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly cards = PURGE_CARDS;
  readonly action = new ActionState(this.t);
  /** Eine Rückfrage zugleich: eine zweite Karte scharf zu schalten schließt die erste. */
  readonly armed = signal<Armed | null>(null);

  readonly stats = signal<DbStats | null>(null);
  readonly statsError = signal('');

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  private ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.loadStats();
  }

  async loadStats(): Promise<void> {
    this.statsError.set('');
    try {
      this.stats.set(await this.sessions.dbStats());
    } catch (err) {
      this.statsError.set(describeApiError(err, this.t));
    }
  }

  /** Die offene Stufe dieser Karte, 0 = keine. */
  step(card: CardId | 'db'): 0 | 1 | 2 {
    const armed = this.armed();
    return armed?.card === card ? armed.step : 0;
  }

  arm(card: CardId | 'db'): void {
    this.armed.set({ card, step: 1 });
    this.focus(card, '.pp-cancel');
  }

  advance(card: CardId): void {
    this.armed.set({ card, step: 2 });
    this.focus(card, '.pp-cancel');
  }

  disarm(card: CardId | 'db'): void {
    this.armed.set(null);
    this.focus(card, '.pp-start');
  }

  async purge(card: PurgeCard): Promise<void> {
    if (this.action.busy()) return;
    this.armed.set(null);
    const ok = await this.action.run(card.id, async () =>
      this.describe(await this.sessions.purge(card.scope)));
    this.afterAction(card.id, ok);
  }

  async optimize(): Promise<void> {
    if (this.action.busy()) return;
    this.armed.set(null);
    const ok = await this.action.run('db', async () => {
      const result = await this.sessions.optimize();
      return this.t('purge.db.done', {
        before: this.fmt.bytes(result.before_bytes),
        after: this.fmt.bytes(result.after_bytes),
      });
    });
    this.afterAction('db', ok);
  }

  /** Nach Erfolg ist die Größe veraltet; nach einem Fehlschlag hat sich nichts geändert.
   *  Wer die Seite inzwischen verlassen hat, bekommt beides nicht (Paket 9). */
  private afterAction(card: CardId | 'db', ok: boolean): void {
    if (this.destroyRef.destroyed) return;
    this.focus(card, '.pp-start');
    if (ok) void this.loadStats();
  }

  private describe(counts: PurgeCounts): string {
    const parts = COUNT_ORDER
      .map((table) => [table, counts[table] ?? 0] as const)
      .filter(([, count]) => count > 0)
      .map(([table, count]) => this.lang.plural(`purge.count.${table}`, count));
    return parts.length
      ? this.t('purge.done', { list: this.lang.list(parts) })
      : this.t('purge.nothing');
  }

  private focus(card: CardId | 'db', selector: string): void {
    this.focusAfterRender(`[data-card="${card}"] ${selector}`);
  }
}
