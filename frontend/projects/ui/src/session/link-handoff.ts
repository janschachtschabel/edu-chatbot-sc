/**
 * Cross-TLD-Link-Handoff — extrahiert aus ``widget.component.ts``
 * (Widget-Split Schritt 4, 2026-07-09): der Klick-Interceptor für den
 * ``?bsid=``-Rewrite ausgehender Links und der T7-Guard/Resolver für
 * Bot-getriebene ``navigate``-Page-Actions.
 *
 * ⚠️ Security-relevant: :func:`resolveGuideNavUrl` ist der Client-Guard
 * gegen offene Weiterleitung (T7, Audit 2026-07-05) — gepinnt durch die
 * Bestands-Spec (``WidgetComponent navigate-Guard (T7)``) über den
 * gleichnamigen Komponenten-Delegate. :func:`maybeRewriteOutgoingLink`
 * ist durch den Spec-Block „Outgoing-Link-Rewrite" gepinnt. Der
 * Komponenten-State (Trusted-Merge-Cache, chatRef.sessionId, guideMode,
 * EventEmitter) kommt als :class:`LinkHandoffContext` herein. Bodies
 * verbatim übernommen — KEINE Logik-Änderung.
 *
 * NEU (boerdi-chat, Shell-Prereq 8-4S-0b): in `ui/session/` neben seine
 * Bausteine gelegt; Imports umgehängt auf die portierten Fns (`isTrustedHost`
 * → `./trusted-host`, `isValidSessionId` → `./session-id`) — gleiche Semantik.
 */

import { isTrustedHost } from './trusted-host';
import { isValidSessionId } from './session-id';

/** Kontext-Schnappschuss der WidgetComponent für einen einzelnen
 *  Klick/Resolve — bewusst pro Aufruf frisch gebaut, damit async
 *  nachgeladene Trusted-Domains (initGuideMode) sofort greifen. */
export interface LinkHandoffContext {
  /** Gemergte Trusted-Liste (Backend + HTML-Attribut, normalisiert). */
  trustedDomains: readonly string[];
  /** Aktuelle Session-ID aus dem Chat-Component (Quelle der Wahrheit —
   *  konsolidiert Stufe-A-Pickup, Cookie und localStorage). */
  sessionId: string | undefined;
}

/** Zusatz-Kontext für den Klick-Interceptor. */
export interface OutgoingLinkContext extends LinkHandoffContext {
  /** Embed-Attribut ``intercept-edu-sharing-links`` (roher Input-Wert,
   *  strikte ``true``/``'true'``-Koerzierung wie im Original). */
  interceptEduSharingLinks: boolean | string;
  /** Wird statt Navigation gerufen (path+search), wenn der Intercept-
   *  Modus greift — die Komponente emittet darüber ``linkClicked``. */
  onInterceptedLink: (pathAndSearch: string) => void;
}

/** Click-Handler-Kern: hängt ?bsid=<sessionId> an Links zu trusted hosts
 *  an (Anchor-href-Mutation für Middle-/Modifier-Click, explizite
 *  Navigation für plain Left-Click — Details in den Inline-Kommentaren).
 *  Fängt ALLE Fehler — nie einen User-Klick kaputt machen. */
export function maybeRewriteOutgoingLink(e: Event, ctx: OutgoingLinkContext): void {
  try {
    // Find the closest <a href="..."> from the click target — manche Sites
    // wrappen Links in span/div, MouseEvent.target ist dann nicht der Anchor.
    let el = e.target as HTMLElement | null;
    while (el && el.tagName !== 'A') {
      el = el.parentElement;
      if (!el || el === document.body) return;
    }
    const anchor = el as HTMLAnchorElement | null;
    if (!anchor || !anchor.href) return;

    // URL parsen — wenn das fehlschlägt (mailto:, javascript:, …), nichts tun.
    let target: URL;
    try { target = new URL(anchor.href, window.location.href); }
    catch { return; }
    if (target.protocol !== 'http:' && target.protocol !== 'https:') return;

    // Intercept mode: suppress navigation, emit the direct link instead.
    if (ctx.interceptEduSharingLinks === true || ctx.interceptEduSharingLinks === 'true') {
      const linkTarget: string = target.pathname + (target.search || '');
      if (linkTarget.includes('/edu-sharing')) {
        e.preventDefault();
        ctx.onInterceptedLink(linkTarget);
        return;
      }
    }

    // Nicht selbst-rewriten: Sprünge auf dieselbe Origin können einfach
    // localStorage / Cookie nutzen — bsid würde nur unnötig die URL füllen.
    if (target.origin === window.location.origin) return;

    // Ziel in Whitelist?
    if (!isTrustedHost(target.hostname, ctx.trustedDomains)) return;

    const sid = ctx.sessionId;
    if (!isValidSessionId(sid)) return;

    // Schon vorhanden? Nicht doppelt setzen.
    if (target.searchParams.has('bsid')) return;

    target.searchParams.set('bsid', sid!);
    const finalUrl = target.toString();
    // Anchor-href IMMER aktualisieren — für Middle-Click und Modifier-Click
    // (Ctrl/Cmd/Shift) nutzt der Browser die Anchor-href, um den Link in
    // einem neuen Tab/Fenster zu öffnen; die sollen ebenfalls den
    // ``bsid``-Param tragen.
    anchor.href = finalUrl;
    // Plain Left-Click ohne Modifier auf same-tab-Links: EXPLIZIT
    // navigieren statt auf den Browser-Default zu hoffen. Manche
    // Tracking-Blocker (Brave Shield, strict-mode Privacy-Erweiterungen)
    // frieren die ``anchor.href`` zum Klick-Start ein und ignorieren
    // spätere Mutationen — der erste Klick verpufft, erst der zweite
    // folgt der neuen URL. Manuelle Navigation via ``window.location.href``
    // umgeht dieses Behavior.
    //
    // Wichtig: NUR für same-tab-Links (kein ``target`` oder ``target="_self"``).
    // Karten-Buttons mit ``target="_blank"`` sollen weiterhin in einem neuen
    // Tab öffnen — das machen sie via Browser-Default mit der (jetzt
    // mutierten) ``anchor.href``. Würden wir hier ``window.location.href``
    // setzen, wäre das eine same-tab-Navigation und der Endnutzer würde
    // die Host-Seite verlieren.
    const tgt = (anchor.target || '').toLowerCase();
    const isSameTab = tgt === '' || tgt === '_self';
    if (
      isSameTab
      && e instanceof MouseEvent
      && e.button === 0
      && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey
    ) {
      e.preventDefault();
      window.location.href = finalUrl;
    }
  } catch { /* never break user clicks */ }
}

/** Prüft + baut die Ziel-URL für eine Bot-``navigate``-Action.
 *
 *  T7 (Audit 2026-07-05): Client-Guard gegen offene Weiterleitung — die
 *  Host-Seite folgt einer bot-/MCP-gelieferten URL nur, wenn sie **http(s)**
 *  ist UND der Host auf der Trusted-Liste steht (dieselbe Prüfung wie
 *  ``maybeRewriteOutgoingLink`` / ``headerNavHrefWithBsid``). Alles andere
 *  (``javascript:``/``data:``, untrusted Host, unparsebar) → ``null`` =
 *  keine Navigation (fail-closed).
 *
 *  Cross-Origin-Handoff: bei echtem Origin-Wechsel werden zwei Parameter
 *  angehängt, damit die Session auf der Zielseite weiterläuft:
 *  - ``bsid=<session-id>`` — Cross-TLD-Session-Bridge (bestehender
 *    Mechanismus aus ``maybeRewriteOutgoingLink``).
 *  - ``bgm=1/0`` — Lotsen-Modus-Toggle; ohne das Flag wäre der Wert in
 *    localStorage origin-isoliert und auf der neuen Domain weg. Bewusst
 *    auch bei Toggle=aus mitgeschickt.
 *  Beide werden auf der Zielseite gelesen, sofort aus der URL entfernt
 *  (kein Bookmark-Leak) und in Cookie/localStorage übernommen.
 */
export function resolveGuideNavUrl(
  url: string,
  ctx: LinkHandoffContext & { guideMode: boolean },
): string | null {
  if (!url) return null;
  let target: URL;
  try {
    target = new URL(url, window.location.href);
  } catch {
    return null;  // unparsebar → nicht navigieren
  }
  if (target.protocol !== 'http:' && target.protocol !== 'https:') return null;
  if (!isTrustedHost(target.hostname.toLowerCase(), ctx.trustedDomains)) return null;

  // Nur Handoff bei echtem Origin-Wechsel — same-origin hat schon Zugriff
  // auf Cookie/localStorage und braucht keine URL-Params.
  if (target.origin !== window.location.origin) {
    const sid = ctx.sessionId;
    if (isValidSessionId(sid) && !target.searchParams.has('bsid')) {
      target.searchParams.set('bsid', sid!);
    }
    if (!target.searchParams.has('bgm')) {
      target.searchParams.set('bgm', ctx.guideMode ? '1' : '0');
    }
  }
  return target.toString();
}
