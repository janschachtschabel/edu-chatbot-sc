/**
 * Input-Routing der Chat-Shell (8-4S-d2b) — bildet rohe Quick-Reply-/Guide-
 * Strings und Bot-`navigate`-Wünsche auf Shell-Aktionen ab. Reine Funktionen
 * hinter einem `InputRoutingContext` (Muster `SendMessageContext`), damit die
 * Weiche ohne TestBed testbar ist und die Shell-Komponente schlank bleibt (die
 * Komponente hält nur dünne Delegates + den window-Navigations-Seiteneffekt).
 *
 * Logik verbatim aus ALT chat.component.ts:571-592 (onQuickReply-Weiche),
 * 627-630 (Guide-QR → URL) und 1104-1109 (T-3-Resolver). KEINE Logik-Änderung;
 * der env-Arg von ALTs `sendMessage(label, undefined, action, params)` entfällt,
 * weil die Shell-`sendMessage` `pageContextEnv` intern liest.
 */
import { actionQuickReplyLabel, isActionQuickReply, parseActionQuickReply } from '../chips/action-qr';
import { guideQuickReplyUrl } from '../chips/guide-qr';
import { TOUR_START_LABEL } from '../controllers/tour.controller';
import { resolveGuideNavUrl } from '../session/link-handoff';

/** Live-Zustand/Aktionen der Shell, die das Routing braucht (deferred Arrows). */
export interface InputRoutingContext {
  /** `[tourReply]` — Studio-Tour-Chip-Text (leer → kein Chip startet die Tour). */
  tourReply: () => string;
  /** ALT-Compat-Konstante (immer true). */
  guideModeActive: boolean;
  /** Effektive Trusted-Host-Liste (Kern-WLO + `[trustedHosts]`). */
  trustedDomains: () => readonly string[];
  /** Aktuelle Session-ID (für den Cross-TLD-`?bsid=`-Handoff). */
  sessionId: () => string;
  /** Web-Tour starten (Delegate auf `TourController`). */
  startTour: () => void;
  /** Normalen bzw. Direct-Action-Turn senden. */
  sendMessage: (text?: string, action?: string, params?: Record<string, any>) => void;
}

/** Standard-Quick-Reply-Weiche: Web-Tour-Start | Action-Pill | Textnachricht. */
export function routeQuickReply(reply: string, ctx: InputRoutingContext): void {
  if (reply === TOUR_START_LABEL || (ctx.tourReply() && reply === ctx.tourReply())) {
    ctx.startTour();
    return;
  }
  if (isActionQuickReply(reply)) {
    const parsed = parseActionQuickReply(reply);
    if (parsed) ctx.sendMessage(parsed.label, parsed.action, parsed.params);
    else ctx.sendMessage(actionQuickReplyLabel(reply)); // kaputtes JSON → Label als Text
    return;
  }
  ctx.sendMessage(reply);
}

/** Ziel-URL eines Guide-QR (`__guide__|Label|url`); '' = kein Guide-QR / keine URL. */
export function guideQuickReplyTarget(qr: string, ctx: InputRoutingContext): string {
  return guideQuickReplyUrl(qr, ctx.guideModeActive);
}

/** T-3-Guard (Audit 2026-07-09): sichere Ziel-URL einer Bot-`navigate`-Aktion —
 *  nur http(s) + Trusted-Host (bei Cross-Origin mit `?bsid=`/`bgm`), sonst
 *  `null` (fail-closed). Der window-Sprung bleibt Sache der Komponente. */
export function resolveGuideNavTarget(url: string | undefined, ctx: InputRoutingContext): string | null {
  return resolveGuideNavUrl(url || '', {
    trustedDomains: ctx.trustedDomains(),
    sessionId: ctx.sessionId(),
    guideMode: ctx.guideModeActive,
  });
}
