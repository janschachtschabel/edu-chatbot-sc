import { computed, signal } from '@angular/core';

import { HeaderNavButton, parseGuideModeConfig } from './guide-mode-config';
import { mergeTrustedDomains } from '../session/trusted-host';

/** Seams des Config-Boots — Host-Attribute und der Chat-Client der Shell. */
export interface GuideBootContext {
  /** `api-url`-Attribut (Basis-URL des Backends). */
  apiUrl: () => string;
  /** `trusted-domains`-Attribut des Hosts (Komma-/Space-getrennt). */
  attrTrustedDomains: () => string;
}

/**
 * GuideBoot — holt beim Widget-Start `GET /api/config/guide-mode` und hält, was
 * daraus folgt: Trusted-Domain-Liste (Backend + Host-Attribut, gemergt und
 * gecacht), Kopfzeilen-Nav-Buttons und die Studio-Begrüßung.
 * Port von ALT `widget.component.ts` (initGuideMode 624-654,
 * _parsedTrustedDomains 415-419).
 *
 * Welle E: der Lotsen-Toggle ist entfernt — `guideMode` ist konstant `true`.
 * Auf nicht-allow-listed Hosts ignoriert das Backend den Modus ohnehin
 * (Sicherheitsnetz in `card_pipeline.build_card_link`).
 *
 * simplify: ALT stieß nach dem async Boot `cdr.markForCheck()` an, damit
 * `[trustedHosts]` neu ausgewertet wird. Hier ist die gemergte Liste ein
 * `computed` — das Neu-Auswerten der Bindung plant Angular dadurch von allein.
 * ALT-ABWEICHUNG: damit wirkt auch ein NACH dem Boot gesetztes
 * `trusted-domains`-Attribut (ALTs Null-Cache ignorierte das stillschweigend).
 *
 * Diese Klasse SCHREIBT das Guide-Env nicht in den Chat-Client: die Shell mountet
 * lazy (erst beim ersten Öffnen) und existiert beim Auflösen von `load()` in der
 * Regel noch nicht. Sie legt es in `guideMode`/`guideHost` ab; die Hülle zieht es
 * per Effect nach, sobald die Shell da ist.
 */
export class GuideBoot {
  /** Lotsen-Modus (konstant `true`, Welle E). Wird gelesen, wo ALT es liest:
   *  Cross-TLD-Handoff und der `navigate`-Banner-Guard. */
  readonly guideMode = signal(true);
  /** Ob der Modus auf diesem Host verfügbar ist (konstant `true`, Welle E). */
  readonly guideModeAvailable = signal(true);
  /** Optionale Kopfzeilen-Nav-Buttons (Studio: header-nav.yaml). Leer = keine. */
  readonly headerNavButtons = signal<HeaderNavButton[]>([]);
  /** Begrüßung aus der Studio-Config; leer → Fallback der Chat-Shell. */
  readonly configGreeting = signal('');
  /** Start-Quick-Replies aus der Studio-Config; leer → Default-4 der Shell. */
  readonly startReplies = signal<string[]>([]);
  /** Label des Tour-Chips aus der Studio-Config. */
  readonly tourReply = signal('');
  /** Hostname-Schnappschuss fürs Guide-Env jeder Anfrage — damit das Backend
   *  weiß, ob es `guide_url` an ausgehende Karten hängen darf (ALT `guideHost`).
   *  Signal, weil die Hülle es erst an die später gemountete Shell weitergibt. */
  readonly guideHost = signal('');

  /** Backend-Liste aus `load()`. Das Host-Attribut darf sie ERGÄNZEN, aber
   *  keine Einträge entfernen — so kann ein Stored-XSS auf einer Host-Seite die
   *  Backend-Allow-Liste nicht umgehen (Defense-in-Depth). */
  private readonly _backendTrustedDomains = signal<string[]>([]);

  /** Gemergte Whitelist (lower-case) als `computed`.
   *
   *  ALT hielt hier einen manuellen Null-Cache, den nur `initGuideMode()`
   *  invalidierte — mit zwei Folgen: (1) `[trustedHosts]` wurde nach dem async
   *  Boot nicht neu ausgewertet (ALT brauchte dafür `cdr.markForCheck()`),
   *  (2) ein später gesetztes `trusted-domains`-Attribut wirkte gar nicht.
   *  Ein `computed` löst beides und ist im zoneless Betrieb Pflicht: ein
   *  Signal-Write beim Lesen aus dem Template wirft `NG0600`. */
  private readonly _merged = computed(() => mergeTrustedDomains(
    this._backendTrustedDomains(), this.ctx.attrTrustedDomains(),
  ));

  constructor(private readonly ctx: GuideBootContext) {}

  /** Gemergte Whitelist (lower-case). Merge-Logik in `session/trusted-host.ts`. */
  trustedDomains(): string[] {
    return this._merged();
  }

  /** Config vom Backend holen und anwenden. Fehler sind kein Show-Stopper —
   *  dann arbeitet die Cross-TLD-Brücke nur ohne Backend-Trusted-Domains.
   *  Verbatim ALT 624-654. */
  async load(): Promise<void> {
    try {
      const apiBase = (this.ctx.apiUrl() || '').replace(/\/+$/, '');
      const resp = await fetch(`${apiBase}/api/config/guide-mode`);
      if (resp.ok) {
        // `null` je Feld heißt „nicht in der Response" → Signal unangetastet.
        const cfg = parseGuideModeConfig(await resp.json());
        if (cfg.trustedDomains !== null) this._backendTrustedDomains.set(cfg.trustedDomains);
        if (cfg.headerNav !== null) this.headerNavButtons.set(cfg.headerNav);
        if (cfg.greeting !== null) this.configGreeting.set(cfg.greeting);
        if (cfg.startReplies !== null) this.startReplies.set(cfg.startReplies);
        if (cfg.tourReply !== null) this.tourReply.set(cfg.tourReply);
      }
    } catch {
      // Backend nicht erreichbar — bewusst geschluckt, siehe Doc-Kommentar.
    }
    this.guideMode.set(true);
    this.guideModeAvailable.set(true);
    let host = '';
    try { host = (window?.location?.hostname || '').toLowerCase(); } catch { /* ignore */ }
    this.guideHost.set(host);
  }
}
