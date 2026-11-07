/**
 * „Einbettende Seiten“ auf der Vorschau-Seite (Plan 2026-11-07, R4).
 *
 * Welche Seiten das Widget einbetten dürfen, steht in `CORS_ORIGINS` dieses Backends. Seit dem
 * MCP-Stand vom 07.11.2026 muss dieselbe Liste am MCP-Server als `TICKET_ALLOWED_ORIGINS`
 * stehen, sonst tauscht keine dieser Seiten mehr ein Ticket. Und die Herkunft, auf die die
 * Anmeldung zurückkehrt, gehört dort in `WIDGET_OAUTH_ORIGINS`. Der Abschnitt macht den
 * Abgleich sichtbar; ändern lässt sich hier nichts (beides sind Betriebs-Einstellungen).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { AsyncData } from '../core/async-data';
import { OverviewApi, type HealthInfo } from '../core/overview-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-einbettung-herkuenfte',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './einbettung-herkuenfte.component.html',
  styleUrl: './einbettung-herkuenfte.component.scss',
})
export class EinbettungHerkuenfteComponent {
  private readonly api = inject(OverviewApi);
  protected readonly t = inject(StudioLanguageService).t;

  /** Die Herkunft, unter der Studio und Backend erreichbar sind (`api-url` der Vorschau). */
  readonly backendHerkunft = input.required<string>();

  readonly health = new AsyncData<HealthInfo>(() => this.api.health(), this.t);
  readonly einbettung = computed(() => this.health.value()?.einbettung ?? null);
  /** Was der MCP-Server als Herkunft annimmt — dieselbe Regel wie dort (`ticket-origins.ts`). */
  private readonly geprueft = computed(() => (this.einbettung()?.herkuenfte ?? []).map((h) => ({
    eintrag: h, herkunft: webHerkunft(h) })));
  /** Die Liste, wie sie am MCP-Server stehen soll — nur, was er annimmt; kommagetrennt. */
  readonly alsListe = computed(() => [...new Set(this.geprueft()
    .map((g) => g.herkunft).filter((h): h is string => h !== null))].join(','));
  /** Einträge, die der MCP-Server verwürfe (`*`, ohne `https://` …). Stünden NUR solche in der
   *  Liste, ließe er keine Seite mehr tauschen — deshalb nicht in die kopierbare Zeile. */
  readonly verworfen = computed(() => this.geprueft()
    .filter((g) => g.herkunft === null).map((g) => g.eintrag));

  constructor() {
    void this.health.reload();
  }
}

/** Die Herkunft einer `http(s)`-Adresse, sonst `null` — wie der MCP-Server sie bildet. */
export function webHerkunft(eintrag: string): string | null {
  try {
    const url = new URL(eintrag);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.origin : null;
  } catch {
    return null;
  }
}
