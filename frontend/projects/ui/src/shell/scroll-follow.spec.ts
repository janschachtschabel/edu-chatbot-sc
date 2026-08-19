// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ScrollFollowController } from './scroll-follow';

/**
 * Scroll-/Auto-Follow-Controller (8-4S-e2): der DOM-Scroll-Cluster aus ALT
 * chat.component.ts (scrollToBottom/scrollToLatest/_setupAutoFollowTail/
 * scrollToMessage/ngAfterViewChecked-Konsum/ngOnDestroy-Cleanup) als eigenständige
 * Klasse mit Container-Seam. Getestet deterministisch mit Fake-Element +
 * Fake-`MutationObserver` (kein jsdom-Layout, kein Timing-Assert).
 */

function fakeEl(scrollHeight = 500): any {
  return {
    scrollTop: 0, scrollHeight, clientHeight: 100,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  };
}

class FakeMutationObserver {
  static instances: FakeMutationObserver[] = [];
  observe = vi.fn();
  disconnect = vi.fn();
  constructor(public cb: unknown) { FakeMutationObserver.instances.push(this); }
}

describe('ScrollFollowController (8-4S-e2)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('scrollToBottom: mit Container → scrollTop=scrollHeight; ohne Container → No-Op', () => {
    const el = fakeEl(320);
    new ScrollFollowController({ container: () => el }).scrollToBottom();
    expect(el.scrollTop).toBe(320);
    expect(() => new ScrollFollowController({ container: () => undefined }).scrollToBottom()).not.toThrow();
  });

  it('afterViewChecked: scrollTargetId → scrollToMessage(einmal), danach geleert', () => {
    const target = { scrollIntoView: vi.fn() };
    const getById = vi.spyOn(document, 'getElementById').mockReturnValue(target as unknown as HTMLElement);
    const ctrl = new ScrollFollowController({ container: () => undefined });
    ctrl.setScrollTarget('m1');
    ctrl.afterViewChecked();
    expect(getById).toHaveBeenCalledWith('msg-m1');
    expect(target.scrollIntoView).toHaveBeenCalledTimes(1);
    ctrl.afterViewChecked(); // Ziel bereits verbraucht
    expect(target.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it('afterViewChecked: nach scrollToLatest scrollt der nächste Render ans Ende, Flag danach verbraucht', () => {
    vi.stubGlobal('MutationObserver', FakeMutationObserver);
    const el = fakeEl(500);
    const ctrl = new ScrollFollowController({ container: () => el });
    ctrl.scrollToLatest();  // Sofort-Scroll + Flag + Auto-Follow
    el.scrollTop = 0;       // zurücksetzen, um den Flag-Konsum zu beweisen
    ctrl.afterViewChecked();
    expect(el.scrollTop).toBe(500);
    el.scrollTop = 0;
    ctrl.afterViewChecked(); // Flag schon geleert → kein erneuter Scroll
    expect(el.scrollTop).toBe(0);
  });

  it('scrollToLatest richtet einen Auto-Follow-Observer ein; destroy trennt ihn ohne Throw', () => {
    vi.stubGlobal('MutationObserver', FakeMutationObserver);
    FakeMutationObserver.instances = [];
    const el = fakeEl(500);
    const ctrl = new ScrollFollowController({ container: () => el });
    ctrl.scrollToLatest();
    expect(el.addEventListener).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true });
    expect(FakeMutationObserver.instances).toHaveLength(1);
    expect(FakeMutationObserver.instances[0].observe).toHaveBeenCalled();
    expect(() => ctrl.destroy()).not.toThrow();
    expect(FakeMutationObserver.instances[0].disconnect).toHaveBeenCalled();
    expect(el.removeEventListener).toHaveBeenCalledWith('scroll', expect.any(Function));
  });

  it('destroy ohne vorherige Aktivierung: kein Throw', () => {
    expect(() => new ScrollFollowController({ container: () => undefined }).destroy()).not.toThrow();
  });
});

describe('Auto-Follow haengt am View-Leben, nicht am Panel-Oeffnen (Befund 2026-08-19)', () => {
  // `instances` ist statisch und ueberlebt den describe darueber — ohne dieses
  // Leeren zaehlte dieser Block fremde Beobachter mit und haenge an der
  // Testreihenfolge.
  beforeEach(() => { FakeMutationObserver.instances.length = 0; });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    FakeMutationObserver.instances.length = 0;
  });

  it('afterViewChecked schaltet den Tail-Follow scharf, ohne dass jemand scrollToLatest ruft', () => {
    // Der Fehler: `_setupAutoFollowTail` hing allein in `scrollToLatest`, und das
    // laeuft nur beim Panel-OEFFNEN (`setExpanded`), beim History-Restore oder
    // per Host-API. Startet das Panel schon offen (`initExpanded` umgeht
    // `setExpanded` bewusst) und gibt es keinen Verlauf, hing der Beobachter nie
    // — die Ansicht folgte der wachsenden Antwort nicht.
    vi.stubGlobal('MutationObserver', FakeMutationObserver);
    const el = fakeEl(500);
    const ctrl = new ScrollFollowController({ container: () => el });

    ctrl.afterViewChecked();

    expect(FakeMutationObserver.instances).toHaveLength(1);
    expect(FakeMutationObserver.instances[0].observe).toHaveBeenCalledWith(
      el, { childList: true, subtree: true, characterData: true },
    );
  });

  it('eine Mutation zieht die Ansicht ans Ende — der eigentliche Zweck', () => {
    vi.stubGlobal('MutationObserver', FakeMutationObserver);
    const el = fakeEl(500);
    const ctrl = new ScrollFollowController({ container: () => el });
    ctrl.afterViewChecked();

    el.scrollHeight = 900;                    // Antwort waechst
    (FakeMutationObserver.instances[0].cb as () => void)();
    expect(el.scrollTop).toBe(900);
  });

  it('ohne Container passiert nichts — und beim naechsten Durchlauf klappt es', () => {
    vi.stubGlobal('MutationObserver', FakeMutationObserver);
    const el = fakeEl(500);
    let vorhanden = false;
    const ctrl = new ScrollFollowController({ container: () => (vorhanden ? el : undefined) });

    ctrl.afterViewChecked();                  // vor dem ersten Render
    expect(FakeMutationObserver.instances).toHaveLength(0);

    vorhanden = true;
    ctrl.afterViewChecked();                  // Template ist da
    expect(FakeMutationObserver.instances).toHaveLength(1);
  });

  it('nur EIN Beobachter, egal wie oft geprueft oder zusaetzlich scrollToLatest kommt', () => {
    vi.stubGlobal('MutationObserver', FakeMutationObserver);
    const ctrl = new ScrollFollowController({ container: () => fakeEl(500) });
    ctrl.afterViewChecked();
    ctrl.afterViewChecked();
    ctrl.scrollToLatest();
    expect(FakeMutationObserver.instances).toHaveLength(1);
  });
});
