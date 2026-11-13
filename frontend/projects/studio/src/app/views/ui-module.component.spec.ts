// @vitest-environment jsdom
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, DeferBlockBehavior, DeferBlockState, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';

import entscheidung from '@boerdi/ui-module/ui-entscheidung/manifest.json';
import inhaltsrahmen from '@boerdi/ui-module/ui-inhaltsrahmen/manifest.json';
import linkbox from '@boerdi/ui-module/ui-linkbox/manifest.json';

import { STUDIO_LOCALE_STORAGE_KEY, StudioLanguageService } from '../i18n/studio-language.service';
import { UiModuleComponent } from './ui-module.component';

/**
 * Paket U1-f: die Seite „UI-Module“ — Liste aus dem Katalog, Angaben aus dem Manifest, Schalter
 * „aktiv“ und „für den Agenten“, gespeichert im Bereich `01-base/display-rules` über den
 * Bereichs-Endpunkt (ganzes Dokument, bedingt auf die Version), Konflikt wie überall.
 */
const KATALOG = '/studio/api/config/ui-module';
const BEREICH = '/studio/api/config/data/01-base/display-rules';
const MODULE = [
  { name: 'ui_entscheidung', manifest: entscheidung, schaltbar: { aktiv: true, agent: true }, abgeleitet: false },
  { name: 'ui_inhaltsrahmen', manifest: inhaltsrahmen, schaltbar: { aktiv: false, agent: false }, abgeleitet: false },
  { name: 'ui_linkbox', manifest: linkbox, schaltbar: { aktiv: true, agent: false }, abgeleitet: true },
];
const DOKUMENT = { display_rules: { groups: { webseiten_max: 3 } }, fremd: { bleibt: true } };
const KONFLIKT = {
  detail: { message: 'Inzwischen geändert.', version: 12, updated_by: 'studio-form',
    updated_at: '2026-11-03T10:00:00+00:00' },
};

const tick = (): Promise<unknown> => new Promise((r) => setTimeout(r, 0));
const norm = (t: string | null | undefined): string => (t ?? '').replace(/\s+/g, ' ').trim();

describe('UiModuleComponent (Paket U1-f)', () => {
  let fixture: ComponentFixture<UiModuleComponent>;
  let el: HTMLElement;
  let http: HttpTestingController;
  let t: (key: string, params?: Record<string, string | number>) => string;

  async function settle(): Promise<void> {
    await tick();
    await fixture.whenStable();
    await tick();
    await fixture.whenStable();
  }

  async function laden(doc: object = DOKUMENT, version: number | null = 7): Promise<void> {
    http.expectOne(KATALOG).flush({ bereich: '01-base/display-rules', module: MODULE });
    await settle();
    http.expectOne(BEREICH).flush({ area: '01-base/display-rules', type: 'yaml', version, data: doc });
    await settle();
  }

  const eintraege = () => Array.from(el.querySelectorAll<HTMLButtonElement>('.um-eintrag'));
  const knopf = (text: string) => Array.from(el.querySelectorAll<HTMLButtonElement>('button'))
    .find((b) => norm(b.textContent) === text)!;
  const schalter = (name: 'aktiv' | 'agent') =>
    el.querySelector<HTMLInputElement>(`input[data-schalter="${name}"]`);

  async function waehle(name: string): Promise<void> {
    eintraege().find((b) => b.dataset['modul'] === name)!.click();
    await settle();
  }

  async function klick(input: HTMLInputElement): Promise<void> {
    input.click();
    await settle();
  }

  beforeEach(async () => {
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(), provideRouter([]),
      ],
    });
    fixture = TestBed.createComponent(UiModuleComponent);
    fixture.componentRef.setInput('section', {
      panel: 'ui-module', labelKey: 'curated.uiModule.panel.label', hintKey: 'curated.uiModule.panel.hint',
    });
    fixture.componentRef.setInput('open', true);
    http = TestBed.inject(HttpTestingController);
    t = TestBed.inject(StudioLanguageService).t;
    el = fixture.nativeElement as HTMLElement;
    document.body.appendChild(el);
    await fixture.whenStable();
  });

  const ABLAUF_LISTE = '/studio/api/config/ablaeufe';
  const ablauf = (id: string, module: string[], aktiv = true) => ({
    key: `06-ablaeufe/${id}`, id, titel: { de: id.toUpperCase() }, aktiv, ausloeser: [], module,
    befunde: 0, lesbar: true });

  it('AS-2c: nennt je Modul die Abläufe, die es zeigen, mit Verweis auf den Ablauf', async () => {
    await laden();
    http.expectOne(ABLAUF_LISTE).flush({ ablaeufe: [
      ablauf('wahl', ['ui_entscheidung']), ablauf('still', ['ui_entscheidung'], false), ablauf('anders', ['ui_upload'])] });
    await settle();
    const links = Array.from(el.querySelectorAll<HTMLAnchorElement>('.um-ablaeufe a'));
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/ablaeufe?ablauf=wahl', '/ablaeufe?ablauf=still']);
    expect(norm(el.querySelector('.um-ablaeufe')?.textContent)).toContain(t('ablaeufe.notiz.aus'));
    await waehle('ui_linkbox');
    expect(el.querySelector('.um-ablaeufe')).toBeNull();
    expect(norm(el.querySelector('.um-detail')?.textContent)).toContain(t('uiModule.ablaeufe.keine'));
  });

  it('AS-2c: kommt die Liste der Abläufe nicht, sagt es die Stelle — der Rest bleibt', async () => {
    await laden();
    http.expectOne(ABLAUF_LISTE).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle();
    expect(norm(el.querySelector('.um-detail')?.textContent)).toContain(t('uiModule.ablaeufe.fehler'));
    expect(schalter('aktiv')).not.toBeNull();
    knopf(t('async.retry')).click();
    await settle();
    http.expectOne(ABLAUF_LISTE).flush({ ablaeufe: [ablauf('wahl', ['ui_entscheidung'])] });
    await settle();
    expect(el.querySelectorAll('.um-ablaeufe a').length).toBe(1);
  });

  it('AS-2c: ?modul=<name> (vom Ablauf her) wählt das Modul', async () => {
    await TestBed.inject(Router).navigateByUrl('/?modul=ui_linkbox');
    await laden();
    expect(eintraege()[2].getAttribute('aria-current')).toBe('true');
  });

  it('lädt erst beim Öffnen und zeigt solange den Ladezustand', async () => {
    expect(norm(el.querySelector('[aria-busy="true"]')?.textContent)).toBe(t('uiModule.laedt'));
    await laden();
    expect(el.querySelector('[aria-busy="true"]')).toBeNull();
  });

  it('listet jedes Modul mit Titel, Name und Zustand; das erste ist gewählt', async () => {
    await laden();
    expect(eintraege().map((b) => b.dataset['modul'])).toEqual(['ui_entscheidung', 'ui_inhaltsrahmen', 'ui_linkbox']);
    expect(norm(eintraege()[0].textContent)).toContain('Entscheidung');
    expect(norm(eintraege()[0].textContent)).toContain('ui_entscheidung');
    expect(norm(eintraege()[0].textContent)).toContain(t('uiModule.zustand.an'));
    expect(norm(eintraege()[1].textContent)).toContain(t('uiModule.zustand.fest'));
    expect(eintraege()[0].getAttribute('aria-current')).toBe('true');
    expect(norm(el.querySelector('.um-detail h4')?.textContent)).toContain('Entscheidung');
  });

  it('zeigt die Angaben aus dem Manifest samt Eingabe und Antwort', async () => {
    await laden();
    const text = norm(el.querySelector('.um-detail')?.textContent);
    expect(text).toContain(entscheidung.beschreibung);
    expect(text).toContain(t('uiModule.eingabe'));
    expect(text).toContain(t('uiModule.antwort'));
    expect(text).toContain('optionen');
    expect(text).toContain('gewaehlt');
    expect(el.querySelectorAll('.um-felder th[scope="col"]').length).toBeGreaterThan(0);
  });

  it('nennt die Systemwerte des Inhaltsrahmens und zeigt ihn fest, ohne Schalter', async () => {
    await laden();
    await waehle('ui_inhaltsrahmen');
    expect(schalter('aktiv')).toBeNull();
    expect(schalter('agent')).toBeNull();
    const text = norm(el.querySelector('.um-detail')?.textContent);
    expect(text).toContain(t('uiModule.schalter.aktiv.fest'));
    expect(text).toContain('schreib_vorschau');
  });

  it('ein abgeleitetes Modul hat nur den Schalter „aktiv“', async () => {
    await laden();
    await waehle('ui_linkbox');
    expect(schalter('aktiv')).not.toBeNull();
    expect(schalter('agent')).toBeNull();
    expect(norm(el.querySelector('.um-detail')?.textContent)).toContain(t('uiModule.schalter.agent.keins'));
  });

  it('Schalter haben Namen, Rolle und Beschreibung', async () => {
    await laden();
    for (const art of ['aktiv', 'agent'] as const) {
      const input = schalter(art)!;
      expect(input.getAttribute('role')).toBe('switch');
      expect(input.closest('label')?.textContent?.trim()).toBeTruthy();
      const beschreibung = input.getAttribute('aria-describedby');
      expect(beschreibung && document.getElementById(beschreibung)?.textContent?.trim()).toBeTruthy();
    }
  });

  it('ein Schalter ändert erst den Entwurf; Speichern schreibt das ganze Dokument mit Version', async () => {
    await laden();
    await klick(schalter('agent')!);
    expect(norm(eintraege()[0].textContent)).toContain(t('uiModule.zustand.geaendert'));
    expect(fixture.componentInstance.dirty()).toBe(true);
    knopf(t('editor.save')).click();
    const req = http.expectOne(BEREICH);
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({
      data: { display_rules: { groups: { webseiten_max: 3 },
        ui_module: { aus: [], agent_aus: ['ui_entscheidung'] } }, fremd: { bleibt: true } },
      expected_version: 7,
    });
    req.flush({ area: '01-base/display-rules', type: 'yaml', version: 8, data: req.request.body.data });
    await settle();
    expect(fixture.componentInstance.dirty()).toBe(false);
    expect(norm(el.querySelector('.cs-status')?.textContent)).toBe(t('uiModule.gespeichert'));
    expect(norm(eintraege()[0].textContent)).toContain(t('uiModule.zustand.ohneAgent'));
  });

  it('R3-g (WCAG 2.4.3): nach dem Speichern steht der Fokus auf der Statuszeile, nicht auf body', async () => {
    await laden();
    await klick(schalter('agent')!);
    const speichern = knopf(t('editor.save'));
    speichern.focus();
    speichern.click();
    const req = http.expectOne(BEREICH);
    req.flush({ area: '01-base/display-rules', type: 'yaml', version: 8, data: req.request.body.data });
    await settle();
    expect(document.activeElement?.classList.contains('cs-status')).toBe(true);
    expect(document.activeElement?.getAttribute('tabindex')).toBe('-1');
  });

  it('Querschnitts-Review R1–R4, Befund 3: nach einem Fehler steht der Fokus auf der Meldung', async () => {
    await laden();
    await klick(schalter('agent')!);
    const speichern = knopf(t('editor.save'));
    speichern.focus();
    speichern.click();
    speichern.blur();      // „focus fixup“ des Browsers: der gesperrte Knopf verliert den Fokus (jsdom nicht)
    http.expectOne(BEREICH).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle();
    expect(document.activeElement?.classList.contains('um-speicherfehler')).toBe(true);
  });

  it('aktiv aus sperrt den Agent-Schalter und sagt warum', async () => {
    await laden();
    await klick(schalter('aktiv')!);
    expect(schalter('agent')!.disabled).toBe(true);
    expect(schalter('agent')!.checked).toBe(false);
    expect(norm(el.querySelector('.um-detail')?.textContent)).toContain(t('uiModule.schalter.agent.erstAktiv'));
  });

  it('Verwerfen holt den gespeicherten Stand zurück', async () => {
    await laden({ display_rules: { ui_module: { aus: ['ui_linkbox'] } } });
    await waehle('ui_linkbox');
    expect(schalter('aktiv')!.checked).toBe(false);
    await klick(schalter('aktiv')!);
    expect(schalter('aktiv')!.checked).toBe(true);
    knopf(t('editor.discard')).click();
    await settle();
    expect(schalter('aktiv')!.checked).toBe(false);
    expect(fixture.componentInstance.dirty()).toBe(false);
  });

  it('ohne gespeichertes Dokument legt Speichern es an', async () => {
    await laden({}, null);
    await klick(schalter('aktiv')!);
    knopf(t('editor.save')).click();
    const req = http.expectOne(BEREICH);
    expect(req.request.body).toEqual({
      data: { display_rules: { ui_module: { aus: ['ui_entscheidung'], agent_aus: [] } } }, create: true });
    req.flush({ area: '01-base/display-rules', type: 'yaml', version: 1, data: req.request.body.data });
    await settle();
  });

  it('ein Konflikt behält den Entwurf; „Trotzdem speichern“ setzt ihn auf den neuen Stand', async () => {
    await laden();
    await klick(schalter('agent')!);
    knopf(t('editor.save')).click();
    http.expectOne(BEREICH).flush(KONFLIKT, { status: 409, statusText: 'Conflict' });
    await settle();
    expect(el.querySelector('studio-save-conflict')).not.toBeNull();
    expect(fixture.componentInstance.dirty()).toBe(true);

    knopf(t('conflict.force')).click();
    await settle();
    // Erst der neue Stand — eine andere Änderung (hier webseiten_max) bleibt erhalten.
    http.expectOne(BEREICH).flush({ area: '01-base/display-rules', type: 'yaml', version: 12,
      data: { display_rules: { groups: { webseiten_max: 9 } } } });
    await settle();
    const req = http.expectOne(BEREICH);
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({
      data: { display_rules: { groups: { webseiten_max: 9 },
        ui_module: { aus: [], agent_aus: ['ui_entscheidung'] } } },
      expected_version: 12,
    });
    req.flush({ area: '01-base/display-rules', type: 'yaml', version: 13, data: req.request.body.data });
    await settle();
    expect(el.querySelector('studio-save-conflict')).toBeNull();
    expect(fixture.componentInstance.dirty()).toBe(false);
  });

  // Review U1 gesamt, Befund 14: eine Fehlermeldung blieb nach „Neu laden“, „Verwerfen“ und neuen
  // Umschaltungen stehen, obwohl der Grund vorbei war.
  it('Lesefehler bei „Trotzdem speichern“, danach „Neu laden“ räumt die Meldung', async () => {
    await laden();
    await klick(schalter('agent')!);
    knopf(t('editor.save')).click();
    http.expectOne(BEREICH).flush(KONFLIKT, { status: 409, statusText: 'Conflict' });
    await settle();
    knopf(t('conflict.force')).click();
    await settle();
    http.expectOne(BEREICH).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle();
    expect(el.querySelector('.cs-state--error')).not.toBeNull();

    knopf(t('conflict.reload')).click();
    await settle();
    http.expectOne(BEREICH).flush({ area: '01-base/display-rules', type: 'yaml', version: 12, data: DOKUMENT });
    await settle();
    expect(el.querySelector('.cs-state--error')).toBeNull();
  });

  it('eine Fehlermeldung weicht beim Umschalten und beim Verwerfen', async () => {
    await laden();
    await klick(schalter('agent')!);
    knopf(t('editor.save')).click();
    http.expectOne(BEREICH).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle();
    expect(el.querySelector('.cs-state--error')).not.toBeNull();
    await klick(schalter('agent')!);
    expect(el.querySelector('.cs-state--error')).toBeNull();

    await klick(schalter('agent')!);
    knopf(t('editor.save')).click();
    http.expectOne(BEREICH).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle();
    expect(el.querySelector('.cs-state--error')).not.toBeNull();
    knopf(t('editor.discard')).click();
    await settle();
    expect(el.querySelector('.cs-state--error')).toBeNull();
  });

  it('„Trotzdem speichern“ überträgt nur die eigenen Umschaltungen — fremde bleiben (Review U1-f, #2)', async () => {
    await laden({ display_rules: { ui_module: { aus: ['ui_linkbox'], agent_aus: [] } } });
    await klick(schalter('agent')!);
    knopf(t('editor.save')).click();
    http.expectOne(BEREICH).flush(KONFLIKT, { status: 409, statusText: 'Conflict' });
    await settle();
    knopf(t('conflict.force')).click();
    await settle();
    // Inzwischen: die Linkbox wieder an, der Themenbaum für den Agenten aus.
    http.expectOne(BEREICH).flush({ area: '01-base/display-rules', type: 'yaml', version: 12,
      data: { display_rules: { ui_module: { aus: [], agent_aus: ['ui_themenbaum'], notiz: 'x' } } } });
    await settle();
    const req = http.expectOne(BEREICH);
    expect(req.request.body).toEqual({
      data: { display_rules: { ui_module: { aus: [], agent_aus: ['ui_entscheidung', 'ui_themenbaum'],
        notiz: 'x' } } },
      expected_version: 12,
    });
    req.flush({ area: '01-base/display-rules', type: 'yaml', version: 13, data: req.request.body.data });
    await settle();
  });

  it('eine zurückgenommene Umschaltung überträgt nichts (Review U1-f, #2)', async () => {
    await laden({ display_rules: { ui_module: { aus: [], agent_aus: [] } } });
    await klick(schalter('agent')!);
    await klick(schalter('agent')!);
    await klick(schalter('aktiv')!);
    knopf(t('editor.save')).click();
    http.expectOne(BEREICH).flush(KONFLIKT, { status: 409, statusText: 'Conflict' });
    await settle();
    knopf(t('conflict.force')).click();
    await settle();
    http.expectOne(BEREICH).flush({ area: '01-base/display-rules', type: 'yaml', version: 12,
      data: { display_rules: { ui_module: { aus: ['ui_linkbox'], agent_aus: ['ui_entscheidung'] } } } });
    await settle();
    const req = http.expectOne(BEREICH);
    // „aktiv“ aus kommt dazu; „für den Agenten“ hin und zurück ist keine Änderung — der fremde
    // Eintrag bleibt.
    expect(req.request.body.data.display_rules.ui_module).toEqual({
      aus: ['ui_entscheidung', 'ui_linkbox'], agent_aus: ['ui_entscheidung'] });
    req.flush({ area: '01-base/display-rules', type: 'yaml', version: 13, data: req.request.body.data });
    await settle();
  });

  it('Texte aus dem Manifest sind als deutsch ausgezeichnet (WCAG 3.1.2, Review U1-f, #5)', async () => {
    await laden();
    expect(el.querySelector('.um-beschreibung')?.getAttribute('lang')).toBe('de');
    const listen = [...el.querySelectorAll('.um-punkte')];
    expect(listen.length).toBe(2);
    expect(listen.every((l) => l.getAttribute('lang') === 'de')).toBe(true);
    const beschreibungen = [...el.querySelectorAll('.um-felder tbody td [lang="de"]')];
    expect(beschreibungen.length).toBeGreaterThan(0);
    expect(norm(beschreibungen[0].textContent)).toBe(
      (entscheidung.eingabe.properties as Record<string, { description: string }>)['frage'].description);
  });

  it('die rollbare Feldtabelle ist erreichbar und benannt (Review U1-f, #8)', async () => {
    await laden();
    const rahmen = [...el.querySelectorAll<HTMLElement>('.um-tabelle')];
    expect(rahmen.length).toBe(2);
    for (const r of rahmen) {
      expect(r.getAttribute('tabindex')).toBe('0');
      expect(r.getAttribute('role')).toBe('region');
      const name = document.getElementById(r.getAttribute('aria-labelledby') ?? '');
      expect(norm(name?.textContent)).toBeTruthy();
    }
    expect(norm(document.getElementById(rahmen[0].getAttribute('aria-labelledby')!)?.textContent))
      .toBe(t('uiModule.eingabe'));
  });

  it('ein Ladefehler zeigt den Grund und „Erneut versuchen“', async () => {
    http.expectOne(KATALOG).flush({ detail: 'kaputt' }, { status: 500, statusText: 'Server Error' });
    await settle();
    expect(el.querySelector('[role="alert"]')).not.toBeNull();
    knopf(t('async.retry')).click();
    await laden();
    expect(eintraege().length).toBe(3);
  });

  it('ein leerer Katalog sagt es', async () => {
    http.expectOne(KATALOG).flush({ bereich: '01-base/display-rules', module: [] });
    await settle();
    http.expectOne(BEREICH).flush({ area: '01-base/display-rules', type: 'yaml', version: 1, data: {} });
    await settle();
    expect(norm(el.textContent)).toContain(t('uiModule.leer'));
    // Review U1-f, #10: kein interner Pfad in der Oberfläche.
    expect(t('uiModule.leer')).toBe('Der Katalog enthält keine UI-Module.');
  });

  it('die Vorschau des gewählten Moduls steht im Detail', async () => {
    await laden();
    expect(el.querySelector('.um-detail studio-ui-modul-vorschau')).not.toBeNull();
  });

  it('lässt sich die Vorschau nicht laden, stehen Hinweis und „Seite neu laden“ (Review U1-f, #4)', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(), provideHttpClient(withXhr()),
        provideHttpClientTesting(), provideRouter([]),
      ],
      deferBlockBehavior: DeferBlockBehavior.Manual,
    });
    fixture = TestBed.createComponent(UiModuleComponent);
    fixture.componentRef.setInput('section', {
      panel: 'ui-module', labelKey: 'curated.uiModule.panel.label', hintKey: 'curated.uiModule.panel.hint',
    });
    fixture.componentRef.setInput('open', true);
    http = TestBed.inject(HttpTestingController);
    el = fixture.nativeElement as HTMLElement;
    document.body.appendChild(el);
    await fixture.whenStable();
    await laden();
    const [vorschau] = await fixture.getDeferBlocks();
    await vorschau.render(DeferBlockState.Error);
    await settle();
    const hinweis = el.querySelector('.um-detail [role="alert"]');
    expect(norm(hinweis?.textContent)).toContain(t('uiModule.vorschau.ladeFehler'));
    expect(knopf(t('uiModule.vorschau.neuLaden'))).toBeTruthy();
    expect(el.querySelector('studio-ui-modul-vorschau')).toBeNull();
  });
});
