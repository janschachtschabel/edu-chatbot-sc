/**
 * Die Seite „UI-Module“ (Paket U1-f, Plan §16): Liste aus dem Katalog links, rechts Angaben aus
 * dem Manifest, die Schalter „aktiv“ / „für den Agenten“ und die Vorschau mit den Beispielen.
 *
 * Die Schalter schreiben den Bereich `01-base/display-rules` (`display_rules.ui_module`) über den
 * Bereichs-Endpunkt — das GANZE Dokument, bedingt auf die gelesene Version. Ein Speichern gilt für
 * alle geänderten Module (wie die Werkzeug-Schalter). Ein 409 erscheint in der Konflikt-
 * Komponente; „Trotzdem speichern“ liest den neuen Stand und setzt nur die hier umgelegten
 * Schalter darauf — eine Änderung an anderen Anzeige-Regeln (Seite „Anzeige“) oder an Schaltern
 * anderer Module geht dabei nicht verloren (Review U1-f, #2).
 *
 * Geladen erst beim Aufklappen, wie die übrigen Panels.
 */
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal, untracked,
} from '@angular/core';

import { describeApiError } from '../core/async-data';
import { type AreaDocument, ConfigApi, saveCondition } from '../core/config-api.service';
import { type SaveConflict, StudioApiError } from '../core/studio-api-error';
import { UiModuleApi } from '../core/ui-module-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';
import { SaveConflictComponent } from './save-conflict.component';
import {
  type Feld, type UiModulEintrag, type UiModulKatalog, feldUebersicht, mitSchalter, mitUmschaltungen,
  schalterAus, zustand,
} from './ui-module';
import { UiModulVorschauComponent } from './ui-modul-vorschau.component';

@Component({
  selector: 'studio-ui-module',
  imports: [SaveConflictComponent, UiModulVorschauComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './ui-module.component.html',
  styleUrl: './ui-module.component.scss',
})
export class UiModuleComponent {
  private readonly api = inject(UiModuleApi);
  private readonly config = inject(ConfigApi);
  private readonly lang = inject(StudioLanguageService);
  private readonly dokument = inject(DOCUMENT);
  protected readonly t = this.lang.t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly katalog = signal<UiModulKatalog | null>(null);
  /** Das gespeicherte Bereichsdokument samt Version. */
  readonly doc = signal<AreaDocument | null>(null);
  /** Der Entwurf: dasselbe Dokument mit den umgelegten Schaltern. */
  readonly entwurf = signal<Readonly<Record<string, unknown>> | null>(null);
  readonly laedt = signal(false);
  readonly ladeFehler = signal('');
  readonly busy = signal(false);
  readonly fehler = signal('');
  readonly status = signal('');
  readonly konflikt = signal<SaveConflict | null>(null);
  readonly gewaehlt = signal('');

  readonly module = computed(() => this.katalog()?.module ?? []);
  readonly eintrag = computed<UiModulEintrag | null>(
    () => this.module().find((m) => m.name === this.gewaehlt()) ?? this.module().at(0) ?? null);

  private readonly gespeicherteSchalter = computed(() => schalterAus(this.doc()?.data ?? null));
  readonly schalter = computed(() => schalterAus(this.entwurf()));
  readonly dirty = computed(
    () => !!this.entwurf() && JSON.stringify(this.schalter()) !== JSON.stringify(this.gespeicherteSchalter()));

  readonly eingabe = computed<readonly Feld[]>(() => feldUebersicht(this.eintrag()?.manifest.eingabe));
  readonly antwort = computed<readonly Feld[]>(() => feldUebersicht(this.eintrag()?.manifest.antwort));

  private gestartet = false;

  constructor() {
    effect(() => {
      if (this.open()) untracked(() => this.ensureLoaded());
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  private ensureLoaded(): void {
    if (this.gestartet) return;
    this.gestartet = true;
    void this.laden();
  }

  async laden(): Promise<void> {
    this.laedt.set(true);
    this.ladeFehler.set('');
    try {
      const katalog = await this.api.katalog();
      const doc = await this.config.data(katalog.bereich);
      this.katalog.set(katalog);
      this.uebernehmen(doc);
    } catch (err) {
      this.ladeFehler.set(describeApiError(err, this.t));
    } finally {
      this.laedt.set(false);
    }
  }

  /** Die Vorschau kommt als eigener Chunk; fehlt er (Netz weg, Studio neu ausgeliefert), hilft
   *  nur ein Neuladen der Seite (Review U1-f, #4). */
  seiteNeuLaden(): void {
    this.dokument.defaultView?.location.reload();
  }

  titel(e: UiModulEintrag): string {
    const titel = e.manifest.titel;
    return (this.lang.i18n.locale() === 'en' ? titel.en : undefined) || titel.de;
  }

  /** Der Zustand in der Liste: an, aus, nur Muster, fest — und „geändert“ bei Entwurf. */
  zustandText(e: UiModulEintrag): string {
    if (!e.schaltbar.aktiv) return this.t('uiModule.zustand.fest');
    const z = zustand(e, this.schalter());
    if (!z.aktiv) return this.t('uiModule.zustand.aus');
    return z.agent === false ? this.t('uiModule.zustand.ohneAgent') : this.t('uiModule.zustand.an');
  }

  geaendert(e: UiModulEintrag): boolean {
    return JSON.stringify(zustand(e, this.schalter())) !== JSON.stringify(zustand(e, this.gespeicherteSchalter()));
  }

  zustandVon(e: UiModulEintrag): { readonly aktiv: boolean; readonly agent: boolean | null } {
    return zustand(e, this.schalter());
  }

  waehle(name: string): void {
    this.gewaehlt.set(name);
  }

  setze(e: UiModulEintrag, art: 'aktiv' | 'agent', an: boolean): void {
    const entwurf = this.entwurf();
    if (!entwurf) return;
    this.entwurf.set(mitSchalter(entwurf, e.name, art, an));
    this.status.set('');
  }

  verwerfen(): void {
    if (this.konflikt()) {
      // Nach einem Konflikt ist der gemerkte Stand veraltet — neu vom Server (wie die Werkzeuge).
      this.konflikt.set(null);
      void this.neuLaden();
      return;
    }
    this.entwurf.set(this.doc()?.data ?? null);
    this.status.set('');
  }

  async speichern(): Promise<void> {
    const doc = this.doc();
    const entwurf = this.entwurf();
    if (!doc || !entwurf || this.busy()) return;
    await this.schreibe(entwurf, doc.version);
  }

  /** Nach einem Konflikt: den neuen Stand lesen und nur die umgelegten Schalter daraufsetzen. */
  async erzwingen(): Promise<void> {
    const bereich = this.katalog()?.bereich;
    if (!bereich || this.busy()) return;
    this.busy.set(true);
    try {
      const neu = await this.config.data(bereich);
      const daten = mitUmschaltungen(neu.data, this.gespeicherteSchalter(), this.schalter());
      this.busy.set(false);
      await this.schreibe(daten, neu.version);
    } catch (err) {
      this.fehler.set(describeApiError(err, this.t));
      this.busy.set(false);
    }
  }

  async neuLaden(): Promise<void> {
    const bereich = this.katalog()?.bereich;
    if (!bereich) return void this.laden();
    try {
      this.uebernehmen(await this.config.data(bereich));
      this.konflikt.set(null);
    } catch (err) {
      this.fehler.set(describeApiError(err, this.t));
    }
  }

  private async schreibe(daten: Readonly<Record<string, unknown>>, version: number | null | undefined): Promise<void> {
    const bereich = this.katalog()?.bereich;
    if (!bereich) return;
    this.busy.set(true);
    this.fehler.set('');
    this.status.set('');
    try {
      this.uebernehmen(await this.config.saveData(bereich, { ...daten }, saveCondition(version)));
      this.konflikt.set(null);
      this.status.set(this.t('uiModule.gespeichert'));
    } catch (err) {
      if (err instanceof StudioApiError && err.status === 409) {
        this.konflikt.set(err.conflict ?? { version: null, updatedBy: null, updatedAt: null });
      } else {
        this.fehler.set(describeApiError(err, this.t));
      }
    } finally {
      this.busy.set(false);
    }
  }

  private uebernehmen(doc: AreaDocument): void {
    this.doc.set(doc);
    this.entwurf.set(doc.data);
  }

  // ── Angaben aus dem Manifest ─────────────────────────────────────────
  faehigkeiten(e: UiModulEintrag): string {
    const liste = e.manifest.faehigkeiten ?? [];
    return liste.length === 0 ? this.t('uiModule.angabe.faehigkeiten.keine')
      : this.lang.list(liste.map((f) => this.t(`uiModule.faehigkeit.${f}`)));
  }

  datenquelle(e: UiModulEintrag): string {
    const quelle = e.manifest.datenquelle;
    if (!quelle) return this.t('uiModule.angabe.datenquelle.keine');
    return this.t('uiModule.angabe.datenquelle.wert', {
      werkzeug: quelle.werkzeug, argumente: this.lang.listOr([...quelle.argumente]),
    });
  }

  agentAngabe(e: UiModulEintrag): string {
    if (e.abgeleitet) return this.t('uiModule.angabe.agent.abgeleitet');
    return this.t(e.manifest.agent ? 'uiModule.angabe.agent.ja' : 'uiModule.angabe.agent.nein');
  }

  platz(e: UiModulEintrag): string {
    return this.t(`uiModule.angabe.platz.${e.manifest.darstellung?.platz === 'unten' ? 'unten' : 'oben'}`);
  }

  textfassung(e: UiModulEintrag): string {
    const { vorlage, feld } = e.manifest.textfassung;
    return feld ? `${vorlage} (${feld})` : vorlage;
  }
}
