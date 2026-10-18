/**
 * Eine farbige Notenmatrix des Lauf-Details (Paket 13, F3) — Zielgruppe × Anwendungsfall,
 * Ablauf × Skala und Persona × Intent nutzen dieselbe Komponente.
 *
 * Wie ALTs Matrix, aber lesbar ohne Farbe: jede Zelle trägt die Zahl (und die Anzahl der
 * Urteile), die Stufe steht im zugänglichen Namen und in der Legende; leere Zellen sind
 * schraffiert statt grau (grau las sich in ALT wie „mittel“). Gefüllte Zellen sind Knöpfe —
 * Tastatur und Fokus von der Plattform — und melden die Wahl (`waehle`): das Detail springt
 * damit zum Ablauf bzw. filtert die Ablauf-Karten.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { type Stufe, stufe } from '../core/eval-auswertung';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

export interface MatrixZelle {
  readonly note: number | null;
  /** Anzahl der Urteile hinter dem Mittel; fehlt bei Einzelnoten (Ablauf × Skala). */
  readonly n?: number;
}

export type MatrixDaten = Readonly<Record<string, Readonly<Record<string, MatrixZelle>>>>;

export interface MatrixWahl {
  readonly zeile: string;
  readonly spalte: string;
}

const STUFEN: readonly Stufe[] = ['sehr-gut', 'gut', 'mittel', 'schwach', 'leer'];

interface Zelle {
  readonly spalte: string;
  readonly stufe: Stufe;
  readonly text: string;
  readonly name: string;
  readonly waehlbar: boolean;
}

@Component({
  selector: 'studio-eval-matrix',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-matrix.component.html',
  styleUrl: './eval-matrix.component.scss',
})
export class EvalMatrixComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);

  readonly titel = input.required<string>();
  readonly zeilenKopf = input.required<string>();
  readonly daten = input.required<MatrixDaten>();
  /** Feste Spaltenfolge (etwa die Skalen); sonst alphabetisch aus den Daten. */
  readonly spaltenFolge = input<readonly string[] | null>(null);

  readonly waehle = output<MatrixWahl>();

  readonly stufen = STUFEN;

  readonly spalten = computed<readonly string[]>(() => {
    const fest = this.spaltenFolge();
    if (fest) return fest;
    const alle = new Set<string>();
    for (const werte of Object.values(this.daten())) for (const s of Object.keys(werte)) alle.add(s);
    return [...alle].sort();
  });

  readonly zeilen = computed(() => Object.keys(this.daten()).sort().map((zeile) => ({
    zeile,
    zellen: this.spalten().map((spalte) => this.zelle(zeile, spalte)),
  })));

  private zelle(zeile: string, spalte: string): Zelle {
    const wert = this.daten()[zeile]?.[spalte];
    const note = wert?.note ?? null;
    const s = stufe(note);
    if (note === null) {
      return { spalte, stufe: s, text: '—', name: this.t('evalV2.stufe.leer'), waehlbar: false };
    }
    const text = this.fmt.decimal(note);
    const params = { zeile, spalte, note: text, stufe: this.t(`evalV2.stufe.${s}`) };
    const name = wert?.n === undefined
      ? this.t('evalV2.zelleOhneN', params)
      : this.t('evalV2.zelle', { ...params, n: wert.n });
    return { spalte, stufe: s, text, name, waehlbar: true };
  }
}
