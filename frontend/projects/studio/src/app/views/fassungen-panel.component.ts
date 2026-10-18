/**
 * Werk und eigene Fassung je Konfigurationsbereich (Paket 12) — Karte der Ansicht „Sicherung“.
 *
 * Bedienung so knapp wie möglich: Vorauswahl „Angepasst“ (was abweicht oder eine stillgelegte
 * eigene Fassung hat), je Zeile ein Kennzeichen als Text und der Schalter „Aktiv: Werksfassung ·
 * Eigene Fassung“ (Paket 16 — vorher je Lage ein anders beschrifteter Knopf, der Rundgang fand
 * nicht, was gerade gilt). Umschalten fragt nicht nach — es verliert nichts: die andere Fassung
 * liegt still, der Schalter führt zurück. Den Status rechnet der Server
 * (`services/werkfassung.py`), hier wird nur angezeigt und gefiltert.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ActionState } from '../core/action-state';
import { AsyncData } from '../core/async-data';
import {
  FassungenApi, type FassungListe, type FassungStatus, type FassungZeile, type FassungZiel,
} from '../core/fassungen-api.service';
import { injectFocus } from '../core/inject-focus';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { AsyncStateComponent } from './async-state.component';
import { FassungVergleichComponent } from './fassung-vergleich.component';

export type FassungFilter = 'angepasst' | 'neu' | 'alle';

/** Was neben dem Schalter angeboten wird. */
export type Zusatzaktion = 'aktualisieren' | 'restore' | 'tauschen' | null;

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
  imports: [AsyncStateComponent, FassungVergleichComponent, RouterLink],
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
  readonly ziele: readonly FassungZiel[] = ['werk', 'eigen'];

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

  /** Bereiche mit aufgeklapptem Vergleich — der lädt selbst (`studio-fassung-vergleich`). */
  private readonly offen = signal<ReadonlySet<string>>(new Set());

  constructor() {
    void this.liste.reload();
  }

  setFilter(f: FassungFilter): void {
    this.filter.set(f);
  }

  /** Welche Fassung gilt — `null`, wenn der Bereich gelöscht ist oder fehlt. */
  aktiv(z: FassungZeile): FassungZiel | null {
    switch (z.status) {
      case 'werk':
      case 'werk-veraltet':
        return 'werk';
      case 'eigen':
      case 'eigen-neues-werk':
      case 'nur-eigen':
        return 'eigen';
      default:
        return null;
    }
  }

  /** Ob der Schalter auf `ziel` wechseln kann. Zur Werksfassung nicht, wenn schon eine eigene
   *  stillliegt — eine ginge verloren, der Server weist es ab (Review #1); dann bleibt der Tausch.
   *  Zur eigenen nur, wenn eine stillliegt. */
  kannWechseln(z: FassungZeile, ziel: FassungZiel): boolean {
    const aktiv = this.aktiv(z);
    if (aktiv === null || aktiv === ziel) return aktiv === ziel;
    if (ziel === 'werk') return z.status !== 'nur-eigen' && !z.hat_eigene_fassung;
    return z.hat_eigene_fassung;
  }

  /** Was neben dem Schalter steht — höchstens eine Aktion. */
  zusatzaktion(z: FassungZeile): Zusatzaktion {
    if (z.status === 'werk-veraltet') return 'aktualisieren';
    if (z.status === 'werk-entfernt' || z.status === 'werk-fehlt') return 'restore';
    if (this.aktiv(z) === 'eigen' && z.hat_eigene_fassung) return 'tauschen';
    return null;
  }

  /** Warum „Eigene Fassung“ nicht wählbar ist — nur, wenn die Werksfassung gilt. */
  ohneEigene(z: FassungZeile): boolean {
    return this.aktiv(z) === 'werk' && !z.hat_eigene_fassung;
  }

  /** Review A-7: warum „Werksfassung“ nicht wählbar ist — zwei eigene Fassungen. */
  zweiEigene(z: FassungZeile): boolean {
    return this.aktiv(z) === 'eigen' && z.hat_eigene_fassung && z.status !== 'nur-eigen';
  }

  /** Ob ein gesperrter Schalter einen Satz mit seinem Grund hat. */
  gesperrtGrund(z: FassungZeile, ziel: FassungZiel): boolean {
    return !this.kannWechseln(z, ziel)
      && (this.ohneEigene(z) || this.zweiEigene(z) || z.status === 'nur-eigen');
  }

  hatVergleich(z: FassungZeile): boolean {
    return z.status === 'eigen' || z.status === 'eigen-neues-werk' || z.status === 'werk-veraltet'
      || z.hat_eigene_fassung;
  }

  /** Den Editor gibt es nur für einen Bereich, der in der Datenbank steht. */
  editorLink(z: FassungZeile): readonly string[] | null {
    return z.version === null ? null : ['/bereich', ...z.area.split('/')];
  }

  istOffen(area: string): boolean {
    return this.offen().has(area);
  }

  async wechseln(z: FassungZeile, ziel: FassungZiel): Promise<void> {
    if (this.aktiv(z) === ziel || !this.kannWechseln(z, ziel)) return;
    await this.umschalten(z, ziel);
  }

  async umschalten(z: FassungZeile, ziel: FassungZiel): Promise<void> {
    const ok = await this.action.run(`${ziel}:${z.area}`, async () => {
      await this.api.umschalten(z.area, ziel, z.version);
      return this.t(meldung(z, ziel), { area: z.area });
    });
    this.schliessen(z.area);
    await this.liste.reload();
    // Nach dem Umschalten zum jetzt gedrückten Schalter derselben Zeile, sonst zur Überschrift.
    if (ok) this.focus(`${zeile(z.area)} .fs-wahl[aria-pressed="true"]`, '#fs-title');
  }

  vergleichUmschalten(z: FassungZeile): void {
    const neu = new Set(this.offen());
    if (!neu.delete(z.area)) neu.add(z.area);
    this.offen.set(neu);
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

  private schliessen(area: string): void {
    if (!this.offen().has(area)) return;
    const neu = new Set(this.offen());
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
