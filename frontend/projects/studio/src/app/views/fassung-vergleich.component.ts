/**
 * Der aufgeklappte Vergleich einer Zeile der Karte „Werk und eigene Fassung“ (Paket 16, C6).
 *
 * Zuerst die Unterschiede je Feld als Tabelle *Feld · Werksfassung · Eigene Fassung* — lesbar ohne
 * YAML-Kenntnis —, der Zeilen-Vergleich (`difflib`) bleibt als Rohansicht dahinter. Liegt eine
 * eigene Fassung still, folgt sie genauso. Lädt beim Aufklappen selbst; die Karte merkt sich nur,
 * welche Zeilen offen sind.
 */
import { ChangeDetectionStrategy, Component, inject, input, type OnInit } from '@angular/core';

import { AsyncData } from '../core/async-data';
import { FassungenApi, type FeldUnterschied, type Vergleich } from '../core/fassungen-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

/** Ein Vergleich gegen die Werksfassung — gelebt oder stillgelegt. */
export interface VergleichsTeil {
  readonly art: 'gelebt' | 'eigene';
  readonly felder: readonly FeldUnterschied[];
  readonly weitere: number;
  /** Ohne die zwei Kopfzeilen (`--- werk` …) — die sagt die Legende. */
  readonly zeilen: readonly string[];
}

export function vergleichsTeile(v: Vergleich): readonly VergleichsTeil[] {
  const gelebt: VergleichsTeil = {
    art: 'gelebt', felder: v.felder ?? [], zeilen: v.zeilen.slice(2),
    weitere: Math.max(0, (v.felder_gesamt ?? 0) - (v.felder?.length ?? 0)),
  };
  const zeilenEigene = (v.zeilen_eigene ?? []).slice(2);
  if (zeilenEigene.length === 0) return [gelebt];
  return [gelebt, {
    art: 'eigene', felder: v.felder_eigene ?? [], zeilen: zeilenEigene,
    weitere: Math.max(0, (v.felder_eigene_gesamt ?? 0) - (v.felder_eigene?.length ?? 0)),
  }];
}

@Component({
  selector: 'studio-fassung-vergleich',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fassung-vergleich.component.html',
  styleUrl: './fassung-vergleich.component.scss',
})
export class FassungVergleichComponent implements OnInit {
  private readonly api = inject(FassungenApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly area = input.required<string>();

  readonly vergleich = new AsyncData<readonly VergleichsTeil[]>(
    async () => vergleichsTeile(await this.api.vergleich(this.area())), this.t);

  ngOnInit(): void {
    void this.vergleich.reload();
  }

  weitere(anzahl: number): string {
    return this.lang.plural('fassungen.felderWeitere', anzahl, { count: anzahl });
  }

  /** CSS-Klasse der Diff-Zeile — die Bedeutung trägt das Zeichen am Zeilenanfang, nicht die Farbe. */
  zeilenart(zeile: string): string {
    if (zeile.startsWith('+')) return 'fs-diff-plus';
    if (zeile.startsWith('-')) return 'fs-diff-minus';
    if (zeile.startsWith('@@')) return 'fs-diff-hunk';
    return '';
  }
}
