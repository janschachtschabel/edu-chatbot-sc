import { provideZonelessChangeDetection, reflectComponentType } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatShellComponent } from '@boerdi/ui';

import { WidgetComponent } from './widget.component';

/**
 * Widget-Hülle (8-5g). Charakterisierung dessen, was ALT über die Komponente
 * gefahren hat und hier nicht schon in den `ui/widget/`-Modulen gepinnt ist:
 * die Lotsen-Banner-Logik (ALT-Block „Lotsen-Banner (handlePageAction)",
 * spec:123-162), das Attribut→Zustand-Mapping und die gerenderte Chrome.
 *
 * ALT hat das Rendern bewusst NICHT getestet („würde die ChatComponent booten"
 * → Netzwerk). Hier geht das: die Shell hängt am Lazy-Mount-Gate, also rendert
 * bei geschlossenem Panel nur der FAB — ohne jeden Netzwerkpfad. `fetch` wird
 * trotzdem gestubbt, weil `ngOnInit` den Config-Boot anstößt.
 */
function mount(): ComponentFixture<WidgetComponent> {
  return TestBed.createComponent(WidgetComponent);
}

/** Shadow-Root, wenn vorhanden — sonst das Host-Element. */
function rootOf(f: ComponentFixture<WidgetComponent>): ParentNode {
  const host = f.nativeElement as HTMLElement;
  return host.shadowRoot ?? host;
}

describe('WidgetComponent', () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState({}, '', '/');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    TestBed.configureTestingModule({
      imports: [WidgetComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

  it('hat genau diese 18 Host-Attribute (§5.5-Kontrakt)', () => {
    // Der Attribut-Satz IST der öffentliche Vertrag der Web-Komponente, und er
    // steht zusätzlich in der Studio-Architektur-Referenz
    // (`projects/studio/src/app/views/reference-data.ts`, HOST_ATTRIBUTES).
    // Ändert sich der Satz hier, muss die Referenz mit — ein dokumentiertes
    // Attribut, das seinen Konsumenten nie erreicht, ist in diesem Projekt schon
    // zweimal passiert (`data-position` 8-5, `inline-result-grouping` 8-7).
    const inputs = (reflectComponentType(WidgetComponent)?.inputs ?? [])
      .map((i) => i.templateName).sort();
    expect(inputs).toEqual([
      'apiUrl', 'autoContext', 'emitGuideSuggestion', 'emitRoutingDebug', 'greeting',
      'initialState', 'inlineResultGrouping', 'interceptEduSharingLinks', 'pageContext',
      'persistSession', 'position', 'primaryColor', 'sessionCookieDomain',
      'sessionCookieMaxAge', 'sessionKey', 'showDebugButton', 'showLanguageButtons',
      'trustedDomains',
    ]);
  });

  it('rendert geschlossen nur den FAB (Lazy-Mount-Gate zu — keine Chat-Shell)', () => {
    const f = mount();
    f.detectChanges();
    const root = rootOf(f);
    expect(root.querySelector('.boerdi-fab')).not.toBeNull();
    expect(root.querySelector('.boerdi-panel')).toBeNull();
    expect(root.querySelector('boerdi-chat-shell')).toBeNull();
  });

  it('FAB-Klick öffnet das Panel samt Kopfzeile; der FAB verschwindet', () => {
    const f = mount();
    f.detectChanges();
    (rootOf(f).querySelector('.boerdi-fab') as HTMLElement).click();
    f.detectChanges();
    const root = rootOf(f);
    expect(root.querySelector('.boerdi-panel')).not.toBeNull();
    expect(root.querySelector('.boerdi-panel-header')).not.toBeNull();
    expect(root.querySelector('.boerdi-fab')).toBeNull();
  });

  it('offenes Panel enthält die Chat-Shell — und ihre Stile landen im Shadow-Root', () => {
    // Die Shell nutzt Emulated Encapsulation, die Hülle Shadow DOM. Dass Angular
    // die Stile verschachtelter Komponenten in den Shadow-Root injiziert, ist die
    // Voraussetzung dafür, dass der Chat im Widget überhaupt gestylt aussieht —
    // darum hier explizit geprüft und nicht angenommen.
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    const root = rootOf(f);
    expect(root.querySelector('boerdi-chat-shell')).not.toBeNull();
    expect(root.querySelector('.chat-wrapper')).not.toBeNull();
    const css = Array.from(root.querySelectorAll('style')).map(s => s.textContent ?? '').join('\n');
    expect(css).toContain('.chat-wrapper');   // Shell-Stile
    expect(css).toContain('.boerdi-panel');   // Hüllen-Stile
  });

  it('Panel bleibt nach dem Schließen im DOM, nur versteckt (Zustand überlebt)', () => {
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    (rootOf(f).querySelector('.boerdi-close') as HTMLElement).click();
    f.detectChanges();
    const panel = rootOf(f).querySelector('.boerdi-panel');
    expect(panel).not.toBeNull();
    expect(panel?.classList.contains('boerdi-panel--hidden')).toBe(true);
  });

  it('Kopfzeilen-Status wird angesagt (role="status", 8-6)', () => {
    // „denkt nach …" / „spricht …" steht AUSSERHALB des `role="log"`-Bereichs
    // und wäre für Screenreader sonst stumm — es ist aber die einzige Rückmeldung,
    // dass der Bot arbeitet bzw. gerade vorliest.
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    const holder = rootOf(f).querySelector('.boerdi-title-text');
    expect(holder?.getAttribute('role')).toBe('status');
    expect(holder?.getAttribute('aria-live')).toBe('polite');
  });

  it('Kopfzeilen-Buttons und FAB haben einen eigenen Fokus-Ring (8-6, SC 2.4.7)', () => {
    // Auf dem dunkelblauen Panel-Kopf ist der Browser-Standardring kaum
    // sichtbar; ALT hatte `:focus-visible` nur am Eulen-Kopf.
    const f = mount();
    f.detectChanges();
    const css = Array.from(rootOf(f).querySelectorAll('style')).map(s => s.textContent ?? '').join('\n');
    expect(css).toContain('.boerdi-action-btn:focus-visible');
    expect(css).toContain('.boerdi-close:focus-visible');
    expect(css).toContain('.boerdi-fab:focus-visible');
  });

  it('FAB und Schließen-Button tragen ein aria-label (Icon-only-Buttons)', () => {
    const f = mount();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Chat öffnen');
    (rootOf(f).querySelector('.boerdi-fab') as HTMLElement).click();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-close')?.getAttribute('aria-label')).toBe('Schließen');
  });

  it('primary-color landet validiert auf der Host-Custom-Property', () => {
    const f = mount();
    f.componentRef.setInput('primaryColor', '#0b7285');
    f.detectChanges();
    const host = f.nativeElement as HTMLElement;
    expect(host.style.getPropertyValue('--boerdi-primary')).toBe('#0b7285');
    // Ungültige Eingabe der Host-Seite räumt den Override ab (CSS-Default greift).
    f.componentRef.setInput('primaryColor', 'url(javascript:alert(1))');
    f.detectChanges();
    expect(host.style.getPropertyValue('--boerdi-primary')).toBe('');
  });

  it('initial-state="expanded" startet offen', () => {
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    expect(f.componentInstance.isChatbotOpen()).toBe(true);
  });

  it('spätere initial-state-Änderung schaltet um (ALT ngOnChanges, !firstChange)', () => {
    const f = mount();
    f.detectChanges();
    expect(f.componentInstance.isChatbotOpen()).toBe(false);
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    expect(f.componentInstance.isChatbotOpen()).toBe(true);
    f.componentRef.setInput('initialState', 'collapsed');
    f.detectChanges();
    expect(f.componentInstance.isChatbotOpen()).toBe(false);
  });

  it('Public API: open/close/toggle/isChatbotOpen sind idempotent', () => {
    const f = mount();
    f.detectChanges();
    const c = f.componentInstance;
    c.openChatbot();
    c.openChatbot();
    expect(c.isChatbotOpen()).toBe(true);
    c.toggleChatbot();
    expect(c.isChatbotOpen()).toBe(false);
    c.closeChatbot();
    expect(c.isChatbotOpen()).toBe(false);
  });

  it('Escape schließt das offene Panel, bei geschlossenem ist es ein No-Op', () => {
    const f = mount();
    f.detectChanges();
    const c = f.componentInstance;
    c.onEscapeKey();
    expect(c.isChatbotOpen()).toBe(false);
    c.openChatbot();
    c.onEscapeKey();
    expect(c.isChatbotOpen()).toBe(false);
  });

  it('Guide-Env erreicht die Shell auch beim Default-Embed (Lazy-Mount)', async () => {
    // Die Shell hängt am Lazy-Gate: beim Default `initial-state="collapsed"` ist
    // sie beim Auflösen des Config-Boots noch nicht gemountet. Ein direkter
    // `this.shell()?.setGuideEnv(...)` wäre dort still verschluckt worden — der
    // Chat-Client hätte dauerhaft `guide_mode: false` gesendet und damit den
    // Backend-Default `True` überschrieben (Lotsen-Modus aus für die häufigste
    // Embed-Variante). Deshalb zieht ein Effect es nach dem Mount nach.
    //
    // Spion am Prototyp, nicht an der Instanz: die Instanz existiert erst nach
    // dem Öffnen, der Aufruf soll aber unabhängig vom Zeitpunkt sichtbar sein.
    const spy = vi.spyOn(ChatShellComponent.prototype, 'setGuideEnv');
    const f = mount();
    f.detectChanges();
    await Promise.resolve();          // GuideBoot.load() auflösen lassen
    expect(spy).not.toHaveBeenCalled();   // noch keine Shell → nichts zu setzen

    f.componentInstance.openChatbot();
    f.detectChanges();
    await Promise.resolve();
    f.detectChanges();

    expect(spy).toHaveBeenCalled();
    expect(spy.mock.calls.at(-1)?.[0]).toBe(true);   // guide_mode
    spy.mockRestore();
  });

  it('inline-result-grouping="false" erreicht die Shell (sonst totes Host-Attribut)', () => {
    // Gefunden von e2e/chat.spec.ts: die Shell hat das Attribut seit 8-2i, die
    // Hülle reichte es aber nicht durch — am echten Embed war das flache
    // Karten-Grid also unerreichbar (gleiche Falle wie `data-position` in 8-5).
    const f = mount();
    f.componentRef.setInput('inlineResultGrouping', 'false');
    f.componentInstance.openChatbot();
    f.detectChanges();
    expect(f.componentInstance.shell()?.inlineResultGroupingBool).toBe(false);
  });

  it('resolvedPageContext trägt den widget-Marker (Backend-Session-Klassifizierung)', () => {
    const f = mount();
    f.detectChanges();
    expect(f.componentInstance.resolvedPageContext()['widget']).toBe(true);
  });
});

describe('WidgetComponent Lotsen-Banner (handlePageAction)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    TestBed.configureTestingModule({
      imports: [WidgetComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('navigate setzt das Banner-Target und trimmt die URL', () => {
    const c = mount().componentInstance;
    c.handlePageAction({ action: 'navigate', payload: { url: '  https://x.example/a  ', label: 'Ziel' } });
    expect(c.guideNavTarget()).toEqual({ url: 'https://x.example/a', label: 'Ziel' });
  });

  it('Label-Fallback-Kette: label → title → URL', () => {
    const c = mount().componentInstance;
    c.handlePageAction({ action: 'navigate', payload: { url: 'https://x.example', title: 'Titel' } });
    expect(c.guideNavTarget()?.label).toBe('Titel');
    c.handlePageAction({ action: 'navigate', payload: { url: 'https://y.example' } });
    expect(c.guideNavTarget()?.label).toBe('https://y.example');
  });

  it('ignoriert leere URLs, fremde Actions und null-Payloads', () => {
    const c = mount().componentInstance;
    c.handlePageAction({ action: 'navigate', payload: { url: '   ' } });
    c.handlePageAction({ action: 'open_canvas', payload: { url: 'https://x.example' } });
    c.handlePageAction({ action: 'navigate', payload: null });
    expect(c.guideNavTarget()).toBeNull();
  });

  it('cancelGuideNav blendet das Banner aus', () => {
    const c = mount().componentInstance;
    c.handlePageAction({ action: 'navigate', payload: { url: 'https://x.example', label: 'Z' } });
    c.cancelGuideNav();
    expect(c.guideNavTarget()).toBeNull();
  });

  it('Banner rendert Label + beide Buttons und räumt bei „Hier bleiben" ab', () => {
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    f.componentInstance.handlePageAction({
      action: 'navigate', payload: { url: 'https://x.example', label: 'Fachportal' },
    });
    f.detectChanges();
    const banner = rootOf(f).querySelector('.boerdi-nav-banner');
    expect(banner?.getAttribute('role')).toBe('alert');
    expect(banner?.textContent).toContain('Fachportal');
    const buttons = Array.from(banner?.querySelectorAll('button') ?? []);
    expect(buttons.map(b => b.textContent?.trim())).toEqual(['Bring mich hin', 'Hier bleiben']);
    (buttons[1] as HTMLElement).click();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-nav-banner')).toBeNull();
  });

  it('confirmGuideNav navigiert NICHT auf untrusted Ziele (T7, fail-closed)', () => {
    const c = mount().componentInstance;
    const before = window.location.href;
    c.handlePageAction({ action: 'navigate', payload: { url: 'https://evil.example/phish' } });
    c.confirmGuideNav();
    expect(c.guideNavTarget()).toBeNull();
    expect(window.location.href).toBe(before);
  });
});
