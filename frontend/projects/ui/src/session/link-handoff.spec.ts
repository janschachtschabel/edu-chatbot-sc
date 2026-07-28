import { describe, expect, it, vi } from 'vitest';

import { generateSessionId } from './session-id';
import { maybeRewriteOutgoingLink, resolveGuideNavUrl } from './link-handoff';

/**
 * Charakterisierung des Cross-TLD-Link-Handoffs — Verbatim-Port aus ALT
 * `widget/link-handoff.ts` (dort kein Standalone-Spec, gepinnt über die
 * WidgetComponent-Spec). Sicherheitskritisch: `resolveGuideNavUrl` ist der
 * T7-Open-Redirect-Guard (fail-closed). Der Plain-Left-Click-Pfad von
 * `maybeRewriteOutgoingLink` setzt `window.location.href` — in jsdom nicht
 * navigierbar → hier über die NICHT-navigierenden Pfade gedeckt (Intercept,
 * Trusted-Skip, Same-Origin-Skip, Middle-Click-href-Rewrite); die reale
 * Same-Tab-Navigation bleibt live/E2E (8-7).
 */
const TRUSTED = ['wirlernenonline.de'];
const sid = generateSessionId();

function anchorEvent(href: string, opts: { button?: number; target?: string } = {}): { e: MouseEvent; anchor: HTMLAnchorElement } {
  const anchor = document.createElement('a');
  anchor.href = href;
  if (opts.target) anchor.target = opts.target;
  const e = new MouseEvent('click', { button: opts.button ?? 1, cancelable: true });
  Object.defineProperty(e, 'target', { value: anchor, enumerable: true });
  return { e, anchor };
}

describe('resolveGuideNavUrl (T7 Open-Redirect-Guard, fail-closed)', () => {
  const ctx = { trustedDomains: TRUSTED, sessionId: sid, guideMode: true };

  it('leere URL → null', () => {
    expect(resolveGuideNavUrl('', ctx)).toBeNull();
  });

  it('javascript:/data: (kein http[s]) → null', () => {
    expect(resolveGuideNavUrl('javascript:alert(1)', ctx)).toBeNull();
    expect(resolveGuideNavUrl('data:text/html,<x>', ctx)).toBeNull();
  });

  it('untrusted Host → null', () => {
    expect(resolveGuideNavUrl('https://evil.com/phish', ctx)).toBeNull();
  });

  it('trusted, cross-origin, gültige Session → bsid + bgm=1 angehängt', () => {
    const out = resolveGuideNavUrl('https://wirlernenonline.de/mathe', ctx);
    expect(out).not.toBeNull();
    const u = new URL(out!);
    expect(u.searchParams.get('bsid')).toBe(sid);
    expect(u.searchParams.get('bgm')).toBe('1');
  });

  it('guideMode=false → bgm=0', () => {
    const out = resolveGuideNavUrl('https://wirlernenonline.de/mathe', { ...ctx, guideMode: false });
    expect(new URL(out!).searchParams.get('bgm')).toBe('0');
  });

  it('same-origin → unverändert, KEIN bsid/bgm (hat schon Cookie/localStorage)', () => {
    const sameOrigin = window.location.origin + '/seite?x=1';
    const out = resolveGuideNavUrl(sameOrigin, { trustedDomains: [window.location.hostname], sessionId: sid, guideMode: true });
    expect(out).not.toBeNull();
    expect(out).not.toContain('bsid');
    expect(out).not.toContain('bgm');
  });
});

describe('maybeRewriteOutgoingLink', () => {
  it('kein Anchor im Ziel-Pfad → No-Op, kein Throw', () => {
    const div = document.createElement('div');
    const e = new MouseEvent('click', { cancelable: true });
    Object.defineProperty(e, 'target', { value: div, enumerable: true });
    expect(() =>
      maybeRewriteOutgoingLink(e, {
        trustedDomains: TRUSTED, sessionId: sid,
        interceptEduSharingLinks: false, onInterceptedLink: () => {},
      }),
    ).not.toThrow();
  });

  it('Intercept-Modus + /edu-sharing-Pfad → onInterceptedLink(path+search) + preventDefault', () => {
    const { e, anchor } = anchorEvent('https://repo.example/edu-sharing/components/render?id=1', { button: 0 });
    const onIntercept = vi.fn();
    maybeRewriteOutgoingLink(e, {
      trustedDomains: TRUSTED, sessionId: sid,
      interceptEduSharingLinks: true, onInterceptedLink: onIntercept,
    });
    expect(onIntercept).toHaveBeenCalledWith('/edu-sharing/components/render?id=1');
    expect(e.defaultPrevented).toBe(true);
    // Kein bsid-Rewrite auf der href, weil vorher returned.
    expect(anchor.href).not.toContain('bsid');
  });

  it('untrusted Host → kein bsid-Rewrite', () => {
    const { e, anchor } = anchorEvent('https://evil.com/x');
    maybeRewriteOutgoingLink(e, {
      trustedDomains: TRUSTED, sessionId: sid,
      interceptEduSharingLinks: false, onInterceptedLink: () => {},
    });
    expect(anchor.href).not.toContain('bsid');
  });

  it('same-origin → kein bsid-Rewrite (Skip vor Whitelist)', () => {
    const { e, anchor } = anchorEvent(window.location.origin + '/seite');
    maybeRewriteOutgoingLink(e, {
      trustedDomains: [window.location.hostname], sessionId: sid,
      interceptEduSharingLinks: false, onInterceptedLink: () => {},
    });
    expect(anchor.href).not.toContain('bsid');
  });

  it('trusted cross-origin + Middle-Click + gültige Session → anchor.href bekommt bsid (keine Navigation)', () => {
    const { e, anchor } = anchorEvent('https://wirlernenonline.de/mathe', { button: 1 });
    maybeRewriteOutgoingLink(e, {
      trustedDomains: TRUSTED, sessionId: sid,
      interceptEduSharingLinks: false, onInterceptedLink: () => {},
    });
    expect(anchor.href).toContain('bsid=' + sid);
    expect(e.defaultPrevented).toBe(false); // Middle-Click: kein preventDefault, nur href-Mutation
  });
});
