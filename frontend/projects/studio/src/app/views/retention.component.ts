/**
 * Aufbewahrung der Gesprächsverläufe und Protokolle (Paket 8, A), Panel der
 * Datenschutz-Seite.
 *
 * Bis Paket 8 stand die Frist nur als Feld im Formular, und niemand löschte;
 * jetzt löscht das Backend alle sechs Stunden, was älter ist
 * (`services/aufbewahrung.py`); seit dem Nutzer-Entscheid vom 2026-10-09 auch
 * Nachrichten und Sitzungsgedächtnis (Vorgabe 30 Tage), seit Paket 9 (V7) auch
 * den Gesprächsstand ruhender Sitzungen. Das Panel zeigt je Bereich, was die
 * Frist gerade bedeutet — wie viele Einträge fällig sind, wie alt der älteste
 * ist — und zieht den nächsten Lauf auf Wunsch vor.
 *
 * EINE Rückfrage, nicht zwei wie beim Löschen über alle Sitzungen: der Lauf
 * löscht nur, was der Takt ohnehin bald löschen würde. Sie zählt beim
 * Scharfschalten neu und nennt die Zahl (Paket 9) — die Frist kann sich seit dem
 * Öffnen geändert haben, und gelöscht wird mit der neuen. Fokus wie dort: beim
 * Scharfschalten auf „Abbrechen“, danach zurück auf den Knopf.
 */
import {
  ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, signal,
} from '@angular/core';

import { ActionState } from '../core/action-state';
import { AsyncData } from '../core/async-data';
import { injectFocus } from '../core/inject-focus';
import {
  type RetentionCounts, type RetentionLog, type RetentionRow, SessionsApi,
} from '../core/sessions-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

/** Reihenfolge im Ergebnissatz — die des Backends. */
const LOG_ORDER: readonly RetentionLog[] = [
  'messages', 'memory', 'session_state', 'safety_logs', 'quality_logs',
];

@Component({
  selector: 'studio-retention',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './retention.component.html',
  styleUrl: './retention.component.scss',
})
export class RetentionComponent {
  private readonly sessions = inject(SessionsApi);
  private readonly lang = inject(StudioLanguageService);
  private readonly destroyRef = inject(DestroyRef);
  /** Fokus nach dem Rendern; in einer zerstörten Ansicht keiner (NG0911, Paket 9). */
  private readonly focus = injectFocus();
  private readonly fmt = inject(StudioFormat);
  protected readonly t = this.lang.t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly action = new ActionState(this.t);
  readonly armed = signal(false);
  /** Bleibt beim Neuladen stehen — die Zahlen springen nicht auf „lädt“. */
  readonly overview = new AsyncData<readonly RetentionRow[]>(
    () => this.sessions.retention(), this.t,
  );

  /** Was der Lauf jetzt löschen würde; ohne frische Zählung der allgemeine Satz. */
  readonly confirmText = computed(() => {
    if (this.overview.loading()) return this.t('retention.counting');
    const rows = this.overview.value();
    if (this.overview.error() || !rows) return this.t('retention.confirmUncounted');
    const due: RetentionCounts = Object.fromEntries(
      rows.filter((row) => row.tage > 0).map((row) => [row.bereich, row.faellig]),
    );
    const parts = this.countParts(due);
    return parts.length
      ? this.t('retention.confirm', { list: this.lang.list(parts) })
      : this.t('retention.confirmNothing');
  });

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
    void this.overview.reload();
  }

  period(row: RetentionRow): string {
    return row.tage > 0
      ? this.lang.plural('retention.days', row.tage)
      : this.t('retention.unlimited');
  }

  /** Ohne Frist wird nie etwas fällig — „0 Einträge“ hieße „gerade nichts“. */
  due(row: RetentionRow): string {
    return row.tage > 0
      ? this.lang.plural('retention.due', row.faellig)
      : this.t('retention.neverDue');
  }

  oldest(row: RetentionRow): string {
    return row.aeltester ? this.fmt.dateTime(row.aeltester) : this.t('retention.empty');
  }

  arm(): void {
    this.armed.set(true);
    this.focus('.rt-cancel');
    void this.overview.reload();
  }

  disarm(): void {
    this.armed.set(false);
    this.focus('.rt-start');
  }

  async run(): Promise<void> {
    if (this.action.busy()) return;
    this.armed.set(false);
    const ok = await this.action.run('run', async () =>
      this.describe(await this.sessions.runRetention()));
    // Wer die Seite inzwischen verlassen hat, bekommt weder Fokus noch neue Zahlen.
    if (this.destroyRef.destroyed) return;
    this.focus('.rt-start');
    // Nach Erfolg sind die Zahlen veraltet; nach einem Fehlschlag hat sich nichts geändert.
    if (ok) void this.overview.reload();
  }

  private describe(counts: RetentionCounts): string {
    const parts = this.countParts(counts);
    return parts.length
      ? this.t('retention.done', { list: this.lang.list(parts) })
      : this.t('retention.nothing');
  }

  private countParts(counts: RetentionCounts): string[] {
    return LOG_ORDER
      .map((log) => [log, counts[log] ?? 0] as const)
      .filter(([, count]) => count > 0)
      .map(([log, count]) => this.lang.plural(`retention.count.${log}`, count));
  }
}
