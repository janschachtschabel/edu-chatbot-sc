/**
 * Eine Ablauf-Karte des Lauf-Details (Paket 13, F4): wie ein Golden-Ablauf lief.
 *
 * Kopf mit Kennzahlen, die Ablauf-Skalen als Balken MIT Zahl (der Balken ist Zierde), das
 * Statement und die Auffälligkeiten des Judge. Aufgeklappt je Zug: Anwendungsfall, Zug-Noten,
 * Notiz, harte Prüfungen (verfehlte beim Namen), Werkzeuge und die Zeit je Schritt. Die volle
 * Antwort des Chatbots steht weiter in der Zug-Tabelle darunter — hier nicht doppelt.
 *
 * Die Karte ist Sprungziel (`#ablauf-<id>`, `tabindex="-1"`) für Problemliste und Matrix;
 * `anwendungsfall` (aus der Matrix Zielgruppe × Anwendungsfall) klappt die Züge auf und
 * markiert die passenden.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { type AblaufAuswertung, stufe } from '../core/eval-auswertung';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { TranscriptConv, TranscriptTurn } from './eval-transcript';
import { catLabel } from './gold-scorecard';

/** Reihenfolge wie im Judge (`prompts_v2.ABLAUF_SKALEN`), Gesamt vorn. */
const ABLAUF_SKALEN = [
  'gesamt', 'zielgruppe', 'anliegen', 'angebot', 'werkzeuge', 'verlauf', 'qualitaet', 'sicherheit',
] as const;
const ZUG_SKALEN = ['anliegen', 'angebot', 'qualitaet', 'ton', 'gesamt'] as const;
/** Werkzeuge, die nur die Muster-Maschine intern führt (wie `prompts_v2._INTERN`). */
const INTERN = new Set(['respond_to_user', 'select_top_cards']);

interface Note {
  readonly text: string;
  readonly stufe: string;
}

@Component({
  selector: 'studio-eval-ablauf-karte',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-ablauf-karte.component.html',
  styleUrl: './eval-ablauf-karte.component.scss',
})
export class EvalAblaufKarteComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);

  readonly ablauf = input.required<AblaufAuswertung>();
  readonly conv = input<TranscriptConv | null>(null);
  /** Gewählter Anwendungsfall aus der Matrix; `null` = keine Hervorhebung. */
  readonly anwendungsfall = input<string | null>(null);

  readonly kennzeile = computed(() => {
    const a = this.ablauf();
    return this.t('evalV2.karte.kennzeile', {
      zielgruppe: a.zielgruppe || '—', ok: a.harte_quote.bestanden, total: a.harte_quote.geprueft,
      p50: a.latenz_p50_ms === null ? '—' : this.fmt.seconds(a.latenz_p50_ms),
    });
  });

  readonly skalen = computed(() => {
    const a = this.ablauf();
    const noten: Record<string, number | null> = { ...a.skalen, gesamt: a.gesamt };
    return ABLAUF_SKALEN.filter((k) => typeof noten[k] === 'number').map((k) => {
      const note = noten[k] as number;
      return {
        name: this.t(`evalV2.skala.${k}`), zahl: this.fmt.decimal(note), stufe: stufe(note),
        breite: `${(note / 5) * 100}%`,
      };
    });
  });

  readonly zuege = computed(() => (this.conv()?.turns ?? []).map((zug, i) => this.zeile(zug, i)));

  private zeile(zug: TranscriptTurn, index: number) {
    const checks = Object.entries(zug.golden?.checks ?? {});
    const verfehlt = checks.filter(([, ok]) => !ok).map(([k]) => catLabel(k, this.t));
    const werkzeuge = [...new Set((zug.debug?.tools_called ?? [])
      .map((roh) => roh.split(' ', 1)[0]).filter((name) => name && !INTERN.has(name)))];
    const zeiten = Object.entries(zug.debug?.token_usage?.zeiten_ms ?? {})
      .filter(([name]) => !name.includes('.'));
    const summe = zeiten.reduce((s, [, ms]) => s + ms, 0);
    return {
      nr: index + 1,
      fall: zug.anwendungsfall ?? '',
      user: zug.user ?? '',
      fehler: zug.error ?? '',
      judgeFehler: zug.judge_failed ?? '',
      noten: this.zugNoten(zug),
      notiz: zug.judge?.notiz ?? '',
      pruefungen: checks.length === 0 ? '' : this.t('evalV2.karte.pruefungen', {
        ok: checks.length - verfehlt.length, total: checks.length,
      }),
      verfehlt: verfehlt.length ? this.t('evalV2.karte.verfehlt', { liste: verfehlt.join(', ') }) : '',
      werkzeuge: werkzeuge.length
        ? this.t('evalV2.karte.werkzeuge', { liste: werkzeuge.join(', ') })
        : this.t('evalV2.karte.keineWerkzeuge'),
      zeitText: zeiten.length ? this.t('evalV2.karte.zeiten', {
        liste: zeiten.map(([name, ms]) => `${name} ${this.fmt.seconds(ms)}`).join(' · '),
      }) : '',
      segmente: summe > 0 ? zeiten.map(([name, ms]) => ({ name, breite: `${(ms / summe) * 100}%` })) : [],
    };
  }

  private zugNoten(zug: TranscriptTurn): readonly Note[] {
    const judge = zug.judge;
    if (!judge) return [];
    return ZUG_SKALEN.flatMap((k) => {
      const note = judge[k];
      return typeof note === 'number' ? [{
        text: this.t('evalV2.note', { skala: this.t(`evalV2.skala.${k}`), note: this.fmt.decimal(note) }),
        stufe: stufe(note),
      }] : [];
    });
  }
}
