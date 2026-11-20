/**
 * Der Katalog der UI-Module, wie das Studio ihn liest (Paket U1-f): `GET /api/config/ui-module`.
 *
 * Nur lesend. Die Schalter stehen im Bereich, den die Antwort nennt (`bereich`), und werden über
 * `ConfigApi.data`/`saveData` gelesen und geschrieben — mit Version wie jeder Bereich.
 */
import { Injectable, inject, signal } from '@angular/core';

import type { UiModulManifest } from '@boerdi/ui-module';

import { StudioApi } from './studio-api.service';

/** Ein Modul des Katalogs. */
export interface UiModulEintrag {
  readonly name: string;
  readonly manifest: UiModulManifest;
  /** Welche Schalter gelten: `aktiv` fehlt beim festen Inhaltsrahmen, `agent` bei Modulen ohne
   *  eigenes Werkzeug (abgeleitete, Inhaltsrahmen). */
  readonly schaltbar: { readonly aktiv: boolean; readonly agent: boolean };
  /** Entsteht ohne Aufruf aus der fertigen Antwort (Trefferliste, Linkbox). */
  readonly abgeleitet: boolean;
  /** Zweites Review P4–P6, MINOR 2: die `daten` eines Ablauf-Schritts sind Parameter des Diensts
   *  (`dienst.parameter`, heute nur `ui_upload`) — bei den übrigen Blockdaten nach `eingabe`. */
  readonly daten_sind_parameter?: boolean;
}

export interface UiModulKatalog {
  /** Der Bereich, in dem die Schalter stehen (`01-base/display-rules`). */
  readonly bereich: string;
  readonly module: readonly UiModulEintrag[];
}

@Injectable({ providedIn: 'root' })
export class UiModuleApi {
  private readonly api = inject(StudioApi);

  private readonly geladen = signal<ReadonlyMap<string, UiModulManifest>>(new Map());
  private laufend: Promise<void> | null = null;

  /** Plan 2026-11-20, P6: die Manifeste nach Namen — für die Parameter-Hilfe unter „Daten“ eines
   *  Modul-Schritts. Nur Module mit `daten_sind_parameter` (zweites Review P4–P6, MINOR 2): bei den
   *  übrigen beschriebe `dienst.parameter` nicht, was die Daten des Schritts sind. Leer, solange
   *  nichts geladen ist. */
  readonly manifeste = this.geladen.asReadonly();

  katalog(): Promise<UiModulKatalog> {
    return this.api.get<UiModulKatalog>('/config/ui-module');
  }

  /** Holt die Manifeste einmal je Sitzung (wie `ChoicesApi.prime`). Ein Fehlschlag bleibt still:
   *  die Hilfe fehlt dann, das Formular bleibt bedienbar; ein späterer Aufruf versucht es neu. */
  manifesteLaden(): Promise<void> {
    this.laufend ??= this.katalog()
      .then((k) => this.geladen.set(new Map(
        k.module.filter((m) => m.daten_sind_parameter === true).map((m) => [m.name, m.manifest]))))
      .catch(() => {
        this.laufend = null;
      });
    return this.laufend;
  }
}
