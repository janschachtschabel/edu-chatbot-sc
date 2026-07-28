import { signal } from '@angular/core';

import { resolveGuideNavUrl } from '../session/link-handoff';

/** Seams der Lotsen-Navigation. */
export interface GuideNavContext {
  /** Lotsen-Modus aktiv? Ohne ihn wird kein Banner gezeigt. */
  guideMode: () => boolean;
  /** Gemergte Trusted-Domain-Liste (T7-Guard). */
  trustedDomains: () => string[];
  /** Session-ID für den Cross-Origin-Handoff. */
  sessionId: () => string | undefined;
}

/**
 * GuideNav — vom Bot vorgeschlagene Navigation, mit ausdrücklicher Zustimmung.
 * Port von ALT `widget.component.ts` (handlePageAction 575-594, confirm/cancel
 * 598-608, navigateToGuideUrl 670-679, _resolveGuideNavUrl 685-691).
 *
 * Zwei Sicherheitsnetze übereinander: wir verlassen die Host-Seite nie ohne
 * einen Klick des Nutzers, UND das Ziel muss den T7-Guard passieren
 * (`resolveGuideNavUrl`: http(s) + Trusted-Host, sonst fail-closed). Das schützt
 * die einbettende Seite davor, dass eine injizierte `navigate`-Page-Action sie
 * auf ein beliebiges Ziel schickt (Phishing, `javascript:`/`data:`).
 */
export class GuideNav {
  /** Aktuelles Vorschlags-Ziel; `null` blendet das Banner aus. */
  readonly target = signal<{ url: string; label: string } | null>(null);

  constructor(private readonly ctx: GuideNavContext) {}

  /** Backend-`page_action` verarbeiten. Nur `navigate` ist hier relevant — alle
   *  anderen Actions verteilt die Chat-Shell als CustomEvents an die Host-Seite. */
  handlePageAction(pa: { action: string; payload: any } | null | undefined): void {
    if (!pa || !pa.action) return;
    if (pa.action !== 'navigate') return;
    if (!this.ctx.guideMode()) return;
    const p = pa.payload || {};
    const url = typeof p.url === 'string' ? p.url.trim() : '';
    const label = typeof p.label === 'string' ? p.label : (p.title || '');
    if (!url) return;
    this.target.set({ url, label: label || url });
  }

  /** „Bring mich hin" — Banner abräumen und (falls freigegeben) navigieren. */
  confirm(): void {
    const t = this.target();
    if (!t) return;
    this.target.set(null);
    this.navigate(t.url);
  }

  /** „Hier bleiben" — Banner wegblenden. */
  cancel(): void {
    this.target.set(null);
  }

  /** Same-Tab-Sprung, nur wenn der T7-Guard die URL freigibt. */
  private navigate(url: string): void {
    const finalUrl = resolveGuideNavUrl(url, {
      trustedDomains: this.ctx.trustedDomains(),
      sessionId: this.ctx.sessionId(),
      guideMode: this.ctx.guideMode(),
    });
    if (!finalUrl) return;
    try {
      window.location.href = finalUrl;
    } catch {
      // Fallback für sandboxed iframes, die direkte Navigation blocken.
      window.open(finalUrl, '_self', 'noopener');
    }
  }
}
