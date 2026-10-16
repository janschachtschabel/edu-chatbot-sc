/**
 * Werk und eigene Fassung je Konfigurationsbereich (Paket 12) — Karte der Ansicht „Sicherung“.
 *
 * Bedienung so knapp wie möglich: Vorauswahl „Angepasst“ (was abweicht oder eine stillgelegte
 * eigene Fassung hat), je Zeile ein Kennzeichen als Text und genau die passenden Knöpfe.
 * Umschalten fragt nicht nach — es verliert nichts: die andere Fassung liegt still, und der
 * Gegenknopf steht danach in derselben Zeile (das „Rückgängig“). Den Status rechnet der Server
 * (`services/werkfassung.py`), hier wird nur angezeigt und gefiltert.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ActionState } from '../core/action-state';
import { AsyncData, describeApiError } from '../core/async-data';
import {
  FassungenApi, type FassungListe, type FassungStatus, type FassungZeile, type FassungZiel,
} from '../core/fassungen-api.service';
import { injectFocus } from '../core/inject-focus';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';

export type FassungFilter = 'angepasst' | 'neu' | 'alle';

interface Unterschiede {
  readonly gelebt: readonly string[];
  readonly eigene: readonly string[];
}

/** Was „angepasst“ heißt: weicht ab, ist gelöscht, gehört nicht zum Werk — oder hat eine eigene
 *  Fassung stillgelegt (sonst verschwände die Zeile mit ihrem „Rückgängig“ nach dem Umschalten). */
const ANGEPASST: ReadonlySet<FassungStatus> = new Set<FassungStatus>(
  ['eigen', 'eigen-neues-werk', 'nur-eigen', 'werk-entfernt', 'werk-fehlt']);

function passt(z: FassungZeile, filter: FassungFilter): boolean {
  if (filter === 'alle') return true;
  if (filter === 'neu') return z.status === 'eigen-neues-werk';
  return ANGEPASST.has(z.status) || z.hat_eigene_fassung;
}

@Component({
  selector: 'studio-fassungen-panel',
  imports: [AsyncStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fassungen-panel.component.html',
  styleUrl: './fassungen-panel.component.scss',
})
export class FassungenPanelComponent {
  private readonly api = inject(FassungenApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly liste = new AsyncData<FassungListe>(() => this.api.list(), this.t);
  readonly action = new ActionState(this.t);
  private readonly focus = injectFocus();

  readonly filter = signal<FassungFilter>('angepasst');
  readonly filters: readonly FassungFilter[] = ['angepasst', 'neu', 'alle'];

  readonly available = computed(() => this.liste.value()?.available ?? true);
  readonly alle = computed(() => this.liste.value()?.bereiche ?? []);
  readonly zeilen = computed(() => this.alle().filter((z) => passt(z, this.filter())));
  readonly zaehlung = computed(() => {
    const alle = this.alle();
    return {
      werk: alle.filter((z) => z.status === 'werk' || z.status === 'werk-veraltet').length,
      eigen: alle.filter((z) => z.status === 'eigen' || z.status === 'eigen-neues-werk').length,
      neu: alle.filter((z) => z.status === 'eigen-neues-werk').length,
    };
  });

  /** Aufgeklappter Vergleich: Bereich → Zeilen ohne Kopf (gelebt und stillgelegt gegen Werk),
   *  `null` = lädt, Text = Fehler. */
  private readonly offen = signal<ReadonlyMap<string, Unterschiede | string | null>>(new Map());

  constructor() {
    void this.liste.reload();
  }

  setFilter(f: FassungFilter): void {
    this.filter.set(f);
  }

  /** Was die Zeile anbietet — genau eine Hauptaktion, plus „Eigene Fassung verwenden“, wenn eine
   *  stillliegt. */
  hauptaktion(z: FassungZeile): FassungZiel | 'restore' | null {
    switch (z.status) {
      case 'eigen':
      case 'eigen-neues-werk':
        // Liegt schon eine eigene Fassung still, ginge mit „Werk“ eine verloren — der Server
        // weist das ab (Review #1); angeboten wird nur der Tausch.
        return z.hat_eigene_fassung ? null : 'werk';
      case 'werk-veraltet':
        return 'werk';
      case 'werk-entfernt':
      case 'werk-fehlt':
        return 'restore';
      default:
        return null;
    }
  }

  hatVergleich(z: FassungZeile): boolean {
    return z.status === 'eigen' || z.status === 'eigen-neues-werk' || z.status === 'werk-veraltet'
      || z.hat_eigene_fassung;
  }

  istOffen(area: string): boolean {
    return this.offen().has(area);
  }

  vergleichszeilen(area: string): Unterschiede | null {
    const wert = this.offen().get(area);
    return wert !== null && typeof wert === 'object' ? wert : null;
  }

  vergleichsfehler(area: string): string {
    const wert = this.offen().get(area);
    return typeof wert === 'string' ? wert : '';
  }

  async umschalten(z: FassungZeile, ziel: FassungZiel): Promise<void> {
    const ok = await this.action.run(`${ziel}:${z.area}`, async () => {
      await this.api.umschalten(z.area, ziel, z.version);
      return this.t(meldung(z, ziel), { area: z.area });
    });
    this.schliessen(z.area);
    await this.liste.reload();
    // Nach dem Umschalten steht der Gegenknopf in derselben Zeile — dorthin, sonst zur Überschrift.
    if (ok) this.focus(`${zeile(z.area)} .fs-aktion`, '#fs-title');
  }

  async vergleichUmschalten(z: FassungZeile): Promise<void> {
    if (this.istOffen(z.area)) {
      this.schliessen(z.area);
      return;
    }
    this.setzeOffen(z.area, null);
    try {
      const v = await this.api.vergleich(z.area);
      // Die ersten zwei Zeilen sind die Kopfzeilen (`--- werk` …) — sagt die Legende schon.
      this.setzeOffen(z.area, {
        gelebt: v.zeilen.slice(2), eigene: (v.zeilen_eigene ?? []).slice(2),
      });
    } catch (err) {
      this.setzeOffen(z.area, describeApiError(err, this.t));
    }
  }

  async werksabgleich(): Promise<void> {
    await this.action.run('abgleich', async () => {
      const r = await this.api.werksabgleich();
      const nachtrag = r.uebersprungen > 0 || r.konflikt > 0
        ? ' ' + this.t('fassungen.abgleichNachtrag', { ...r }) : '';
      return this.t('fassungen.abgleichDone', { ...r }) + nachtrag;
    });
    await this.liste.reload();
  }

  /** CSS-Klasse der Diff-Zeile — die Bedeutung trägt das Zeichen am Zeilenanfang, nicht die Farbe. */
  zeilenart(zeile: string): string {
    if (zeile.startsWith('+')) return 'fs-diff-plus';
    if (zeile.startsWith('-')) return 'fs-diff-minus';
    if (zeile.startsWith('@@')) return 'fs-diff-hunk';
    return '';
  }

  private setzeOffen(area: string, wert: Unterschiede | string | null): void {
    const neu = new Map(this.offen());
    neu.set(area, wert);
    this.offen.set(neu);
  }

  private schliessen(area: string): void {
    if (!this.offen().has(area)) return;
    const neu = new Map(this.offen());
    neu.delete(area);
    this.offen.set(neu);
  }
}

/** Was nach dem Umschalten gemeldet wird — nach dem, was wirklich geschah (Review 2 #6): bei
 *  veraltetem Werk wird nichts stillgelegt, nur aktualisiert. */
function meldung(z: FassungZeile, ziel: FassungZiel): string {
  if (ziel === 'geprueft') return 'fassungen.switchedGeprueft';
  if (ziel === 'eigen') return 'fassungen.switchedEigen';
  if (z.version === null) return 'fassungen.restored';
  return z.status === 'werk-veraltet' ? 'fassungen.updatedWerk' : 'fassungen.switchedWerk';
}

/** Die Zeile eines Bereichs. Bereichsnamen sind Pfade aus `[a-z0-9-_/]` — im Selektor unbedenklich,
 *  trotzdem mit `CSS.escape`, wo es den Browser gibt. */
function zeile(area: string): string {
  const wert = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(area) : area;
  return `[data-area="${wert}"]`;
}
