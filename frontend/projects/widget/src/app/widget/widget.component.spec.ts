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
    // Seit C1-c ist die Sprache eine Eingabe wie jede andere: jsdom meldet
    // `navigator.language === 'en-US'`, die Hülle spräche also standardmässig
    // englisch. Diese Suite charakterisiert den deutschen Wortlaut, also stellt
    // sie eine deutsche Seite her — die Quelle, die dafür da ist. Ein eigener
    // Test nimmt das `[lang]` wieder weg und belegt die Browser-Quelle.
    sessionStorage.clear();
    document.documentElement.setAttribute('lang', 'de');
    history.replaceState({}, '', '/');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    TestBed.configureTestingModule({
      imports: [WidgetComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    sessionStorage.clear();
    document.documentElement.removeAttribute('lang');
  });

  it('hat genau diese 25 Host-Attribute (§5.5-Kontrakt)', () => {
    // Der Attribut-Satz IST der öffentliche Vertrag der Web-Komponente, und er
    // steht zusätzlich in der Studio-Architektur-Referenz
    // (`projects/studio/src/app/views/widget-contract-data.ts`, HOST_ATTRIBUTES).
    // Ändert sich der Satz hier, muss die Referenz mit — ein dokumentiertes
    // Attribut, das seinen Konsumenten nie erreicht, ist in diesem Projekt schon
    // zweimal passiert (`data-position` 8-5, `inline-result-grouping` 8-7).
    const inputs = (reflectComponentType(WidgetComponent)?.inputs ?? [])
      .map((i) => i.templateName).sort();
    expect(inputs).toEqual([
      'apiUrl', 'autoContext', 'embedMode', 'emitGuideSuggestion', 'emitRoutingDebug',
      'engine', 'greeting', 'initialState', 'inlineResultGrouping',
      'interceptEduSharingLinks', 'language', 'pageContext', 'persistSession', 'position',
      'primaryColor', 'sessionCookieDomain', 'sessionCookieMaxAge', 'sessionKey',
      'showCards', 'showDebugButton', 'showLanguageButtons', 'size', 'theme', 'ticket',
      'trustedDomains',
    ]);
  });

  // ── `ticket` — die Betriebsform „das Repositorium bettet ein" ────────────
  it('sammelt das Ticket einmal ein und tilgt das Attribut aus dem DOM', () => {
    // md-editor-Regel „ein Ticket darf nirgends liegenbleiben", hier fürs DOM:
    // nach dem Boot sieht weder eine Serialisierung der Seite noch ein spätes
    // Skript der Gastseite den Wert am Element. Der WERT überlebt in
    // `ticketOnce`, weil das Tilgen über die Element-Brücke den Input leert —
    // die Shell bekäme ihn sonst nie.
    const f = mount();
    (f.nativeElement as HTMLElement).setAttribute('ticket', 'TICKET_abc123def456');
    f.componentRef.setInput('ticket', 'TICKET_abc123def456');
    f.detectChanges();

    expect(f.componentInstance.ticketOnce()).toBe('TICKET_abc123def456');
    expect((f.nativeElement as HTMLElement).getAttribute('ticket')).toBeNull();
  });

  it('ohne Ticket bleibt alles, wie es war — kein leerer Tilgungs-Lauf', () => {
    const f = mount();
    f.detectChanges();
    expect(f.componentInstance.ticketOnce()).toBe('');
  });

  // ── U4a: `theme` ───────────────────────────────────────────────────────
  // Das Widget folgte bisher ausschliesslich dem geerbten `color-scheme` der
  // Gastseite. Das bleibt die Vorgabe; `theme` ist der Ausweg fuer Gastseiten,
  // die selbst keins setzen (oder das falsche).
  //
  // Gesetzt wird der Inline-Stil am HOST-Element, nicht — wie bei `embed-mode`
  // und `size` — eine Host-Klasse mit CSS-Regel dahinter: dort haengen jeweils
  // viele Regeln an der Stufe, hier ist es genau EINE Deklaration mit einem
  // Wert. Der Inline-Stil ist ausserdem das, was der Test wirklich beobachten
  // kann; eine Klasse belegte nur die Markierung, nicht ihre Wirkung (jsdom
  // wertet keine Stylesheets aus).

  it('theme="dark" setzt color-scheme am Host — die Token im Shadow-Root erben es', () => {
    const f = mount();
    f.componentRef.setInput('theme', 'dark');
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).style.colorScheme).toBe('dark');
  });

  it('theme="light" ebenso', () => {
    const f = mount();
    f.componentRef.setInput('theme', 'light');
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).style.colorScheme).toBe('light');
  });

  it('ohne theme (und bei Unfug) setzt das Widget nichts — die Gastseite entscheidet', () => {
    const f = mount();
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).style.colorScheme).toBe('');
    f.componentRef.setInput('theme', 'nachtmodus');
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).style.colorScheme).toBe('');
  });

  it('theme laesst sich zur Laufzeit wieder auf auto zuruecknehmen', () => {
    // Eine Gastseite mit eigenem Hell/Dunkel-Umschalter setzt das Attribut um.
    // Bliebe der alte Wert als Inline-Stil stehen, waere das Widget dauerhaft
    // von der Seite abgekoppelt — genau die Falle, die `null` (statt `'light'`)
    // als Auto-Wert vermeidet.
    const f = mount();
    f.componentRef.setInput('theme', 'dark');
    f.detectChanges();
    f.componentRef.setInput('theme', 'auto');
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).style.colorScheme).toBe('');
  });

  // ── U1: rahmenloser Einbettungs-Modus ──────────────────────────────────
  // `embed-mode="frameless"` ist der Einbau IN eine fremde Oberfläche: die
  // Gastanwendung stellt Rahmen und Navigation, das Widget nur Verlauf und
  // Eingabe. Deshalb entfallen FAB, Kopfzeile und Panel-Rahmen — und das
  // Lazy-Mount-Gate MUSS offen sein, denn es gibt keinen Knopf, der es öffnet.

  it('embed-mode="frameless": kein FAB, keine Kopfzeile, Chat sofort da', () => {
    const f = mount();
    f.componentRef.setInput('embedMode', 'frameless');
    f.detectChanges();
    const root = rootOf(f);
    expect(root.querySelector('.boerdi-fab')).toBeNull();
    expect(root.querySelector('.boerdi-panel-header')).toBeNull();
    expect(root.querySelector('boerdi-chat-shell')).not.toBeNull();
  });

  it('embed-mode="frameless" markiert die Hülle, damit das SCSS greifen kann', () => {
    const f = mount();
    f.componentRef.setInput('embedMode', 'frameless');
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-widget--frameless')).not.toBeNull();
  });

  // U2a — Größenstufe. Das Attribut setzt nur den ANFANG; danach gehört die
  // Stufe dem Panel, weil der Umschalter in der Eingabezeile sie verändert.

  it('size="large" startet auf der großen Stufe und markiert die Hülle', () => {
    const f = mount();
    f.componentRef.setInput('size', 'large');
    f.componentRef.setInput('embedMode', 'frameless'); // Panel ohne Klick sichtbar
    f.detectChanges();
    expect(f.componentInstance.sizeStep()).toBe('large');
    expect(rootOf(f).querySelector('.boerdi-widget--large')).not.toBeNull();
  });

  it('ohne size bleibt es klein — Bestands-Embeds ändern sich nicht', () => {
    const f = mount();
    f.componentRef.setInput('embedMode', 'frameless');
    f.detectChanges();
    expect(f.componentInstance.sizeStep()).toBe('small');
    expect(rootOf(f).querySelector('.boerdi-widget--large')).toBeNull();
  });

  it('unbekannte size fällt auf „klein"', () => {
    const f = mount();
    f.componentRef.setInput('size', 'riesig');
    f.detectChanges();
    expect(f.componentInstance.sizeStep()).toBe('small');
  });

  it('toggleSize() schaltet die Stufe und die Markierung um', () => {
    const f = mount();
    f.componentRef.setInput('embedMode', 'frameless');
    f.detectChanges();
    f.componentInstance.toggleSize();
    f.detectChanges();
    expect(f.componentInstance.sizeStep()).toBe('large');
    expect(rootOf(f).querySelector('.boerdi-widget--large')).not.toBeNull();
  });

  it('rahmenlos fordert die Shell NICHT auf, den Größen-Knopf zu zeigen', () => {
    // Dort bestimmt die Gastanwendung die Maße — ein Knopf „vergrößern", der
    // nichts vergrößert, wäre eine Lüge.
    const f = mount();
    f.componentRef.setInput('embedMode', 'frameless');
    f.detectChanges();
    expect(rootOf(f).querySelector('.btn-size')).toBeNull();
  });

  // U6 — Reihenfolge der Kopfzeilen-Symbole. Die Navigations-Knöpfe (Startseite,
  // Fachportale, Suche) kommen aus der Redaktions-Config und stehen jetzt VORN,
  // abgesetzt von den code-gebundenen Umschaltern; Schließen bleibt ganz rechts.

  it('Navigations-Knöpfe stehen vor den code-gebundenen Umschaltern', () => {
    const f = mount();
    f.componentRef.setInput('showDebugButton', true);
    (f.componentInstance as unknown as { guide: { headerNavButtons: { set: (v: unknown[]) => void } } })
      .guide.headerNavButtons.set([
        { id: 'home', label: 'Startseite', icon: 'home', url: 'https://x.test/' },
      ]);
    f.detectChanges();
    (rootOf(f).querySelector('.boerdi-fab') as HTMLElement).click();
    f.detectChanges();
    const kinder = Array.from(rootOf(f).querySelector('.boerdi-header-actions')!.children);
    const navIdx = kinder.findIndex((c) => c.classList.contains('boerdi-nav-group'));
    const schliessen = kinder.findIndex((c) => c.classList.contains('boerdi-close'));
    expect(navIdx, 'Navigations-Gruppe vorhanden').toBeGreaterThanOrEqual(0);
    expect(navIdx, 'Gruppe ganz vorn').toBe(0);
    expect(schliessen, 'Schließen ganz rechts').toBe(kinder.length - 1);
  });

  it('unbekannter embed-mode fällt auf „panel" — ein Tippfehler der Gastseite darf nichts kaputt machen', () => {
    const f = mount();
    f.componentRef.setInput('embedMode', 'vollbild');
    f.detectChanges();
    const root = rootOf(f);
    expect(root.querySelector('.boerdi-fab')).not.toBeNull();
    expect(root.querySelector('boerdi-chat-shell')).toBeNull();
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

  // ── U4b: Kopfzeile auf einer M3-Fläche statt auf dem Markenband ────────
  // Bis U4b war die Kopfzeile ein dunkelblaues Band mit weißer Schrift — ein
  // fester Hellwert je Farbe, der das geerbte `color-scheme` bewusst ignorierte.
  // Diese beiden Tests pinnen die Umkehrung an ihrer Wurzel: kein `#fff` und
  // keine Markenfarbe mehr als FLÄCHE, sondern die Systemtoken. Sie sehen keine
  // Farben (jsdom rendert nicht) — sie sehen, aus welcher QUELLE die Farbe
  // kommt, und genau das ist die Eigenschaft, die hell und dunkel zugleich
  // trägt. Der gemessene Kontrast steht im Plan (U4b, beide Schemata).
  function styleOf(f: ComponentFixture<WidgetComponent>): string {
    return Array.from(rootOf(f).querySelectorAll('style')).map(s => s.textContent ?? '').join('\n');
  }
  /** Der Regelblock eines Selektors aus dem ausgelieferten Stylesheet. */
  function ruleBlock(css: string, selector: string): string {
    const at = css.indexOf(selector + '{') >= 0 ? selector + '{' : selector + ' {';
    const start = css.indexOf(at);
    return start < 0 ? '' : css.slice(start, css.indexOf('}', start));
  }

  it('Kopfzeile ist eine M3-Fläche, kein Markenband mehr (U4b)', () => {
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    const block = ruleBlock(styleOf(f), '.boerdi-panel-header');
    expect(block, 'Regelblock .boerdi-panel-header nicht gefunden').not.toBe('');
    expect(block).toContain('--mat-sys-surface-container');
    expect(block).toContain('--mat-sys-on-surface');
    expect(block).not.toContain('--boerdi-primary');
    expect(block).not.toMatch(/#fff|255,\s*255,\s*255/);
  });

  it('kein fester Weißwert mehr in Kopfzeile und Aktions-Knöpfen (U4b)', () => {
    // Weiß war nur richtig, solange DAHINTER garantiert Dunkelblau lag. Auf
    // einer hellen Fläche verschwinden Symbol, Rand und Fokusring — lautlos.
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    const css = styleOf(f);
    // `.boerdi-owl-mini` steht bewusst NICHT in dieser Liste: die weiße Scheibe
    // hinter dem Logo ist der Kontrastträger für ein Bild mit festen eigenen
    // Farben — dieselbe begründete Ausnahme wie beim FAB. Ein Bild kann nicht
    // mitkippen, also kippt sein Untergrund auch nicht.
    for (const selector of [
      '.boerdi-action-btn', '.boerdi-action-btn.is-on', '.boerdi-action-btn.is-off',
      '.boerdi-action-btn--neutral', '.boerdi-close',
    ]) {
      const block = ruleBlock(css, selector);
      expect(block, `Regelblock ${selector} nicht gefunden`).not.toBe('');
      expect(block, `${selector} trägt noch einen festen Weißwert`)
        .not.toMatch(/#fff|255,\s*255,\s*255/);
    }
  });

  it('FAB und Schließen-Button tragen ein aria-label (Icon-only-Buttons)', () => {
    const f = mount();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Chat öffnen');
    (rootOf(f).querySelector('.boerdi-fab') as HTMLElement).click();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-close')?.getAttribute('aria-label')).toBe('Schließen');
  });

  it('rendert die Hülle beim Sprachwechsel neu (C1-b1, seit C1-c über den echten Knopf)', () => {
    // Die übrigen Tests hier belegen nur den deutschen Wortlaut — dass die
    // Bindungen tatsächlich AUF DIE SPRACHE reagieren, würden sie auch dann
    // bestehen, wenn die Texte weiterhin fest im Template stünden.
    //
    // Bis C1-b4 musste dieser Test dafür eine eigene `I18n`-Instanz
    // unterschieben. Seit C1-c gibt es den Umschalter, also fährt er den
    // Produktionsweg — und belegt damit zugleich den eingebauten EN-Katalog.
    const f = mount();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Chat öffnen');

    f.componentInstance.toggleLanguage();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Open chat');
  });

  it('reicht die Sprache bis in die Chat-Shell durch (C1-b2)', () => {
    // Die Kette Hülle → `[translate]` → Shell-Template ist die eigentliche
    // Verdrahtung von C1-b2. Sie hier zu prüfen ist der einzige Weg, sie als
    // GANZE zu belegen — die Shell-Specs sehen nur ihre eigene Seite davon.
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    expect(rootOf(f).querySelector('.btn-send')?.getAttribute('aria-label')).toBe('Senden');

    f.componentInstance.toggleLanguage();
    f.detectChanges();
    expect(rootOf(f).querySelector('.btn-send')?.getAttribute('aria-label')).toBe('Send');
  });

  it('der Umschalter sitzt in der Kopfzeile und nennt die Zielsprache (C1-c)', () => {
    const f = mount();
    f.componentRef.setInput('initialState', 'expanded');
    f.detectChanges();
    const knopf = rootOf(f).querySelector('.boerdi-lang-btn') as HTMLElement;
    expect(knopf).not.toBeNull();
    expect(knopf.getAttribute('aria-label')).toBe('Auf Englisch umschalten');
    expect(knopf.textContent?.trim()).toBe('EN');
    // Das Kürzel ist Zierat wie die Icons der Nachbarknöpfe; der zugängliche
    // Name ist der ganze Satz.
    expect(knopf.querySelector('.boerdi-lang-code')?.getAttribute('aria-hidden')).toBe('true');

    knopf.click();
    f.detectChanges();
    expect(knopf.getAttribute('aria-label')).toBe('Switch to German');
    expect(knopf.textContent?.trim()).toBe('DE');
  });

  it('language="en" schaltet die Oberfläche um (Element-Attribut, C1-c)', () => {
    const f = mount();
    f.componentRef.setInput('language', 'en');
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Open chat');
  });

  it('ohne Attribut und ohne [lang] entscheidet der Browser (C1-c)', () => {
    // jsdom meldet `en-US`. Die übrigen Tests dieser Suite setzen deshalb
    // `<html lang="de">` — dieser hier nimmt es weg und belegt damit, dass die
    // schwächste Quelle wirklich angeschlossen ist.
    document.documentElement.removeAttribute('lang');
    const f = mount();
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Open chat');
  });

  it('die Nutzerwahl schlägt das Attribut — auch wenn der Host es neu setzt', () => {
    // Ohne das spränge die Sprache beim nächsten Rendern zurück, und der
    // Umschalter wirkte wie ein Fehler.
    const f = mount();
    f.componentRef.setInput('language', 'en');
    f.detectChanges();
    f.componentInstance.toggleLanguage();          // Nutzer will Deutsch
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Chat öffnen');

    f.componentRef.setInput('language', 'en');     // Host setzt erneut
    f.detectChanges();
    expect(rootOf(f).querySelector('.boerdi-fab')?.getAttribute('aria-label')).toBe('Chat öffnen');
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
    sessionStorage.clear();
    document.documentElement.setAttribute('lang', 'de');  // siehe oben (C1-c)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    TestBed.configureTestingModule({
      imports: [WidgetComponent],
      providers: [provideZonelessChangeDetection()],
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
    document.documentElement.removeAttribute('lang');
  });

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

// ── C1-g1b: das Widget waehlt je Schluessel ─────────────────────────────
// Der Server liefert beide Fassungen (C1-g1a); die Wahl faellt hier, weil die
// Sprache zur Laufzeit umschaltbar ist und der Boot-Abruf nur einmal laeuft.

describe('WidgetComponent Config-Sprache (C1-g1b)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
  });
  afterEach(() => vi.unstubAllGlobals());

  function withConfig(f: ComponentFixture<WidgetComponent>): void {
    const c = f.componentInstance as any;
    c.guide.configGreeting.set('Moin');
    c.guide.configGreetingEn.set('Hello');
    c.guide.startReplies.set(['Tour']);
    c.guide.startRepliesEn.set(['Tour EN']);
    c.guide.headerNavButtons.set([
      { id: 'h', label: 'Startseite', label_en: 'Home', icon: 'home',
        url: 'https://x.example', new_tab: false },
      { id: 'k', label: 'Ohne EN', label_en: '', icon: 'home',
        url: 'https://y.example', new_tab: false },
    ]);
  }

  it('deutsche Oberflaeche zeigt die deutsche Fassung', () => {
    const f = mount();
    withConfig(f);
    const c = f.componentInstance as any;
    expect(c.configGreeting()).toBe('Moin');
    expect(c.startReplies()).toEqual(['Tour']);
    expect(c.headerNavLabel(c.headerNavButtons()[0])).toBe('Startseite');
  });

  it('englische Oberflaeche zeigt die englische Fassung', () => {
    const f = mount();
    withConfig(f);
    const c = f.componentInstance as any;
    c.lang.i18n.setLocale('en');
    expect(c.configGreeting()).toBe('Hello');
    expect(c.startReplies()).toEqual(['Tour EN']);
    expect(c.headerNavLabel(c.headerNavButtons()[0])).toBe('Home');
  });

  it('ein leeres englisches Feld faellt auf das deutsche zurueck', () => {
    const f = mount();
    withConfig(f);
    const c = f.componentInstance as any;
    c.lang.i18n.setLocale('en');
    // „nicht gepflegt" heisst deutsch — nicht leer. Dieselbe Regel wie im
    // Backend-Loader (C1-g1a).
    expect(c.headerNavLabel(c.headerNavButtons()[1])).toBe('Ohne EN');
  });
});
