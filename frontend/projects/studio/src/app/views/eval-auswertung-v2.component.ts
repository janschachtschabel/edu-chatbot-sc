/**
 * Die Auswertung mit dem Judge v2 im Lauf-Detail (Paket 13, F7) — in der Reihenfolge des Plans
 * (§5.6): Messbedingungen, Kennzahlen, Kurzbericht, Matrizen, Problemliste, Abläufe, Zeiten.
 *
 * Eigene Komponente, damit das Lauf-Detail nur entscheidet, OB sie erscheint (Golden-Lauf mit
 * `auswertung`). Hier liegt der Zustand, den die Teile teilen: die gewählte Zelle der Matrix
 * Zielgruppe × Anwendungsfall filtert die Ablauf-Karten; Problemliste und Matrix Ablauf × Skala
 * springen zur Karte.
 *
 * Persona × Intent zeigt nur, was die Muster-Maschine erkannte — in der Agent-Ansicht fällt
 * die Matrix weg (Paket 13, E).
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, computed, inject,
  input, signal,
} from '@angular/core';

import type { EvalRunDetail } from '../core/eval-api.service';
import { type AuswertungV2, kurzberichtAus, messbedingungenAus } from '../core/eval-auswertung';
import { StudioAnsicht } from '../core/studio-ansicht.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { EvalAblaufKarteComponent } from './eval-ablauf-karte.component';
import { EvalMatrixComponent, type MatrixDaten, type MatrixWahl } from './eval-matrix.component';
import { EvalMessbedingungenComponent } from './eval-messbedingungen.component';
import { EvalProblemlisteComponent } from './eval-problemliste.component';
import type { TranscriptConv } from './eval-transcript';
import { EvalZeitenComponent } from './eval-zeiten.component';

/** Spalten der Matrix Ablauf × Skala in der Reihenfolge des Judge, Gesamt zuletzt. */
const SKALEN = [
  'zielgruppe', 'anliegen', 'angebot', 'werkzeuge', 'verlauf', 'qualitaet', 'sicherheit', 'gesamt',
];

function notenMatrix(m: AuswertungV2['matrix_zielgruppe_anwendungsfall']): MatrixDaten {
  return Object.fromEntries(Object.entries(m).map(([zeile, spalten]) => [zeile,
    Object.fromEntries(Object.entries(spalten).map(([s, z]) => [s, { note: z.mittel, n: z.n }]))]));
}

@Component({
  selector: 'studio-eval-auswertung-v2',
  imports: [
    EvalAblaufKarteComponent, EvalMatrixComponent, EvalMessbedingungenComponent,
    EvalProblemlisteComponent, EvalZeitenComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-auswertung-v2.component.html',
  styleUrl: './eval-auswertung-v2.component.scss',
})
export class EvalAuswertungV2Component {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);
  private readonly ansicht = inject(StudioAnsicht);
  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly injector = inject(Injector);

  readonly run = input.required<EvalRunDetail>();

  readonly auswertung = computed(() => this.run().auswertung as AuswertungV2);
  private readonly summary = computed(() => this.run().summary ?? {});
  readonly mb = computed(() => messbedingungenAus(this.summary()));
  readonly fassung = computed(() => String(this.summary()['judge_fassung'] ?? ''));
  readonly bericht = computed(() => kurzberichtAus(this.summary()));

  readonly za = computed(() => notenMatrix(this.auswertung().matrix_zielgruppe_anwendungsfall));
  readonly pi = computed(() => notenMatrix(this.auswertung().matrix_persona_intent));
  readonly ablaufSkala = computed<MatrixDaten>(() => Object.fromEntries(
    Object.entries(this.auswertung().matrix_ablauf_skala).map(([ablauf, skalen]) => [ablauf,
      Object.fromEntries(Object.entries(skalen).map(([s, note]) => [s, { note }]))])));
  readonly skalenFolge = computed(() => {
    const vorhanden = new Set(Object.values(this.ablaufSkala()).flatMap((z) => Object.keys(z)));
    return SKALEN.filter((s) => vorhanden.has(s));
  });
  readonly zeigtPi = computed(
    () => this.ansicht.zeigt(['pattern']) && Object.keys(this.pi()).length > 0);

  readonly kennzahlen = computed(() => {
    const g = this.auswertung().gesamt;
    const note = (n: number | null): string => (n === null ? '—' : this.fmt.decimal(n));
    const sek = (ms: number | null): string => (ms === null ? '—' : this.fmt.seconds(ms));
    return [
      { label: 'evalV2.k.gesamt', wert: note(g.gesamt_mittel) },
      { label: 'evalV2.k.zugMittel', wert: note(g.zug_mittel) },
      { label: 'evalV2.k.hart', wert: `${g.harte_quote.bestanden}/${g.harte_quote.geprueft}` },
      { label: 'evalV2.k.latenz', wert: `${sek(g.latenz.p50_ms)} / ${sek(g.latenz.p95_ms)}` },
      { label: 'evalV2.k.kostenZug', wert: this.geld(g.kosten_je_zug) },
      { label: 'evalV2.k.judgeKosten', wert: this.geld(g.judge_kosten) },
      { label: 'evalV2.k.fehler', wert: `${g.chat_fehler} / ${g.judge_fehler}` },
      { label: 'evalV2.k.umfang', wert: `${g.ablaeufe} / ${g.zuege}` },
    ];
  });

  /** Gewählte Zelle der Matrix Zielgruppe × Anwendungsfall. */
  readonly filter = signal<MatrixWahl | null>(null);

  readonly karten = computed(() => {
    const filter = this.filter();
    const convs = (this.run().conversations ?? []) as readonly TranscriptConv[];
    return this.auswertung().je_ablauf
      .filter((a) => !filter || a.zielgruppe === filter.zeile)
      .map((a) => ({ ablauf: a, conv: convs.find((c) => c.flow_id === a.flow_id) ?? null }));
  });

  private geld(betrag: number | null): string {
    if (betrag === null) return this.t('evalV2.k.ohnePreis');
    const waehrung = this.run().profile?.currency;
    return waehrung ? this.fmt.money(String(betrag), waehrung) : this.fmt.decimal(betrag);
  }

  waehleZa(wahl: MatrixWahl): void {
    this.filter.set(wahl);
  }

  filterAus(): void {
    this.filter.set(null);
  }

  /** Zur Karte springen; ein gesetzter Filter, der sie verbirgt, fällt vorher weg. */
  springe(flowId: string): void {
    const ziel = this.auswertung().je_ablauf.find((a) => a.flow_id === flowId);
    if (ziel && this.filter() && this.filter()!.zeile !== ziel.zielgruppe) this.filter.set(null);
    afterNextRender(() => {
      // Über die Kennung vergleichen statt sie in einen Selektor zu setzen: eine Ablauf-ID ist
      // Konfiguration und könnte Zeichen tragen, die ein Selektor anders liest.
      const karte = Array.from((this.host.nativeElement as HTMLElement)
        .querySelectorAll<HTMLElement>('studio-eval-ablauf-karte section'))
        .find((section) => section.id === `ablauf-${flowId}`);
      karte?.scrollIntoView?.({ block: 'start' });
      karte?.focus();
    }, { injector: this.injector });
  }
}
