/**
 * Die Zug-Tabelle eines Gold-Laufs (aus `eval-run-detail` gelöst, Paket 6):
 * je Flow seine Züge mit Soll, Ist und den Prüfungen, darunter die Quote des
 * Flows; ein geöffneter Zug zeigt die Bot-Antwort und was beobachtet wurde —
 * die Stelle, an der ALT sie zeigte.
 *
 * Der geöffnete Zug gehört dem Lauf: wechselt `runId`, schließt er; ein
 * Neuladen desselben Laufs lässt ihn offen. Darum kommt die Kennung mit — die
 * Metriken allein sind nach jedem Neuladen ein neues Objekt.
 *
 * ALT defects not ported: the per-turn row was a `<tr onClick>` — the densest
 * information in the view, unreachable without a mouse (now a `<button>` in the
 * first cell with `aria-expanded`); and its rate colours (`#16a34a`/`#d97706`/
 * `#dc2626` on white ≈ 3.4 / 2.9 / 4.0∶1) miss AA for the small text they were
 * used on, so the checked `--st-*-text` trio carries them instead — the number
 * is always spelled out beside the colour anyway.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked,
} from '@angular/core';
import type { RichSegment } from '@boerdi/ui';

import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { TranscriptConv } from './eval-transcript';
import {
  catLabel, flowGroups, hardCats, hardRate, type GoldMetrics, type GoldPerTurn,
} from './gold-scorecard';
import { RichTextComponent } from './rich-text.component';

@Component({
  selector: 'studio-eval-gold-turns',
  imports: [RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-gold-turns.component.html',
  styleUrl: './eval-gold-turns.component.scss',
})
export class EvalGoldTurnsComponent {
  /** Zahlen in der aktiven Sprache (C1-d4f). */
  private readonly fmt = inject(StudioFormat);

  private readonly lang = inject(StudioLanguageService);

  protected readonly t = this.lang.t;

  /** Zerlegt einen Satz mit Auszeichnung in Stücke (C1-d4b2). */
  protected readonly rich = this.lang.rich;

  readonly runId = input.required<string>();
  readonly metrics = input.required<GoldMetrics>();
  /** Die Gespräche des Laufs — nur für die Bot-Antwort eines geöffneten Zugs. */
  readonly conversations = input.required<readonly TranscriptConv[]>();

  /** Which `flow·turn` row is open; '' = none. */
  readonly openTurn = signal('');

  readonly groups = computed(() => flowGroups(this.metrics().per_turn ?? []));

  /** Spalten der Turn-Tabelle aus den Kategorien DES Laufs (Review-Nachlauf
   *  2026-08-22): die Liste war hartkodiert v1 — ein v2-Lauf hatte keine
   *  Werkzeug-Soll-Spalte und zwei tote (Persona/Intent). ``hardCats`` liefert
   *  für gespeicherte v1-Läufe exakt die alte Liste. */
  readonly cats = computed(() => hardCats(this.metrics()));

  /** Bot answers by `flow·turn`, for the row a reader opens. */
  private readonly botByTurn = computed(() => {
    const index = new Map<string, string>();
    for (const conv of this.conversations()) {
      const flow = conv.flow_id || conv.persona_id || '?';
      (conv.turns ?? []).forEach((turn, i) => {
        index.set(this.turnKey(flow, i + 1), turn.bot ?? '');
      });
    }
    return index;
  });

  constructor() {
    // Ein anderer Lauf: der geöffnete Zug gehörte dem vorigen.
    effect(() => {
      this.runId();
      untracked(() => this.openTurn.set(''));
    });
  }

  /** v1 hat Persona/Intent-Solls, v2 Register/Struktur — die Kompaktspalte
   *  zeigt, was der Lauf wirklich behauptet hat. */
  sollText(turn: GoldPerTurn): string {
    if (this.cats().includes('persona')) {
      return `${this.expected(turn, 'persona')}/${this.expected(turn, 'intent')}`;
    }
    return `${this.expected(turn, 'register')} · ${this.expected(turn, 'structure')}`;
  }

  istText(turn: GoldPerTurn): string {
    if (this.cats().includes('persona')) {
      return `${this.observed(turn, 'persona')}/${this.observed(turn, 'intent')}/`;
    }
    return `${this.observed(turn, 'register')} · `;
  }

  turnKey(flow: string, turn: number): string {
    return `${flow}·${turn}`;
  }

  toggleTurn(key: string): void {
    this.openTurn.update((current) => (current === key ? '' : key));
  }

  isOpen(key: string): boolean {
    return this.openTurn() === key;
  }

  botText(key: string): string {
    return this.botByTurn().get(key) || this.t('evalDetail.noBotText');
  }

  flowRate(flow: string): string {
    const { ok, total, rate } = hardRate(this.metrics().per_flow?.[flow], this.cats());
    if (rate === null) return this.t('evalDetail.flowNothing');
    return this.t('evalDetail.flowRate', { rate: this.fmt.percent(rate, 0), ok, total });
  }

  /** `null` means the check was not asserted for this turn, not that it failed. */
  checkGlyph(value: boolean | null | undefined): string {
    return value === true ? '✓' : value === false ? '✗' : '–';
  }

  checkWord(value: boolean | null | undefined): string {
    if (value === true) return this.t('evalDetail.check.passed');
    return this.t(value === false ? 'evalDetail.check.failed' : 'evalDetail.check.skipped');
  }

  checkClass(value: boolean | null | undefined): string {
    return value === true ? 'erd-ok' : value === false ? 'erd-bad' : 'erd-none';
  }

  label(category: string): string {
    return catLabel(category, this.t);
  }

  observed(turn: GoldPerTurn, key: string): string {
    return this.field(turn.observed, key);
  }

  expected(turn: GoldPerTurn, key: string): string {
    return this.field(turn.expected, key);
  }

  /** Die geöffnete Zeile als EIN Satz: bis C1-d4b2 stand er als sechs
   *  Bruchstücke im Template, deren Reihenfolge der Übersetzung gehört. */
  turnDetail(turn: GoldPerTurn): readonly RichSegment[] {
    return this.rich('evalDetail.turnDetail', {
      mustOffer: this.expected(turn, 'must_offer'),
      sie: this.observed(turn, 'sie'),
      du: this.observed(turn, 'du'),
      cards: this.observed(turn, 'cards'),
      idocs: this.observed(turn, 'idocs'),
      qr: this.observed(turn, 'qr'),
    });
  }

  /** AG-5: die Skills, die der Zug geladen hat, als eine Zeile — leer, wenn
   *  keiner geladen wurde (dann steht die Zeile gar nicht erst da). */
  skills(turn: GoldPerTurn): string {
    const liste = turn.observed['skills'];
    return Array.isArray(liste)
      ? liste.filter((s): s is string => typeof s === 'string' && s !== '').join(', ')
      : '';
  }

  private field(source: Readonly<Record<string, unknown>>, key: string): string {
    const value = source[key];
    return value === undefined || value === null || value === '' ? '–' : String(value);
  }
}
