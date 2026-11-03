/**
 * Der Katalog der UI-Module, wie das Studio ihn liest (Paket U1-f): `GET /api/config/ui-module`.
 *
 * Nur lesend. Die Schalter stehen im Bereich, den die Antwort nennt (`bereich`), und werden über
 * `ConfigApi.data`/`saveData` gelesen und geschrieben — mit Version wie jeder Bereich.
 */
import { Injectable, inject } from '@angular/core';

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
}

export interface UiModulKatalog {
  /** Der Bereich, in dem die Schalter stehen (`01-base/display-rules`). */
  readonly bereich: string;
  readonly module: readonly UiModulEintrag[];
}

@Injectable({ providedIn: 'root' })
export class UiModuleApi {
  private readonly api = inject(StudioApi);

  katalog(): Promise<UiModulKatalog> {
    return this.api.get<UiModulKatalog>('/config/ui-module');
  }
}
