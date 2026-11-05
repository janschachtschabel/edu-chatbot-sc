// @vitest-environment jsdom
import { ChangeDetectionStrategy, Component, inject, input, provideZonelessChangeDetection } from '@angular/core';
import { type ComponentFixture, TestBed } from '@angular/core/testing';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MODUL_HOST, UI_MODUL_REGISTER, type ModulKontext, type ModulRegister, type UiBlock } from '@boerdi/ui-module';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { UiBloeckeComponent } from './ui-bloecke.component';
import { type HostSeams, type ShellAntworten, type ShellTreffer, WidgetModulHost } from './widget-modul-host';

/** Was `zweig` dem Testmodul zurückgab (U1-h). */
const ZWEIG_ERHALTEN: Record<string, unknown>[] = [];

/** Testmodul: zeigt seine Daten und seinen Kontext, bietet „Herunterladen“ über den Host. */
@Component({
  selector: 'ui-test-modul',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<p class="test-modul" [attr.data-nur-lesen]="kontext().nurLesen"
                [attr.data-skala]="kontext().schriftSkala">{{ daten()['text'] }}</p>
             <div class="test-md" [innerHTML]="md()"></div>
             <button type="button" class="test-laden" (click)="laden()">laden</button>
             <button type="button" class="test-drucken" (click)="drucken()">drucken</button>
             <span class="test-link" [attr.data-href]="verweis().href" [attr.data-hinweis]="verweis().hinweis"></span>
             <span class="test-treffer" [attr.data-kacheln]="umgebung().kacheln"
                   [attr.data-regeln]="kontext().anzeigeRegeln ? 'ja' : 'nein'"
                   [attr.data-karten-href]="kartenHref()" [attr.data-karten-hinweis]="kartenHinweis()"></span>
             <button type="button" class="test-volltext" (click)="volltext()">volltext</button>
             <button type="button" class="test-baum" (click)="baum()">baum</button>
             <button type="button" class="test-mehr" (click)="mehrLaden()">mehr</button>
             <button type="button" class="test-falsch" (click)="falsch()">falsch</button>`,
})
class TestModul {
  readonly daten = input.required<Record<string, unknown>>();
  readonly kontext = input.required<ModulKontext>();
  private readonly host = inject(MODUL_HOST);
  laden(): void { this.host.herunterladen('probe.md', 'text/markdown', '# Probe'); }
  verweis() { return this.host.link('https://wirlernenonline.de/x'); }
  umgebung() { return this.host.treffer(); }
  /** Was die Trefferboxen über den Kontext der Shell aus einer Karten-Adresse machen. */
  kartenHref() { return (this.umgebung().kontext as typeof VERWEISE).withBsid('https://fremd.example/k'); }
  kartenHinweis() { return (this.umgebung().kontext as typeof VERWEISE).externalLinkWarning('https://fremd.example/k'); }
  volltext(): void { this.host.aktion('volltext', { nodeId: 'n1', title: 'T' }); }
  baum(): void { void this.host.zweig('n2').then((d) => ZWEIG_ERHALTEN.push(d)); }
  mehrLaden(): void { this.host.aktion('mehrLaden', { blockId: 'gleich-anderswo' }); }
  falsch(): void { (this.host.aktion as (n: string, p: object) => void)('quatsch', {}); }
  drucken(): void { this.host.drucken('Probe-Titel', '## Abschnitt'); }
  md() { return this.host.markdown('**fett**'); }
}

/** Abfragendes Testmodul (U1-d1): antwortet über den Host, zeigt „beschäftigt“. */
@Component({
  selector: 'ui-test-frage',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<button type="button" class="test-antworten" [attr.data-beschaeftigt]="host.beschaeftigt()"
                     (click)="host.antworten({ gewaehlt: ['a'] }, 'Antwort A')">antworten</button>`,
})
class TestFrage {
  readonly daten = input.required<Record<string, unknown>>();
  readonly kontext = input.required<ModulKontext>();
  protected readonly host = inject(MODUL_HOST);
}

// Seit U1-d1 gilt je Block nur, was das Manifest unter `faehigkeiten` nennt (eigener Host).
const ALLES = ['herunterladen', 'drucken', 'oeffnen', 'nachladen'] as const;
const REGISTER: ModulRegister = {
  ui_test: { manifest: { name: 'ui_test', version: 2, art: 'anzeigen', titel: { de: 'Test' }, faehigkeiten: ALLES },
             komponente: TestModul },
  ui_unten: {
    manifest: { name: 'ui_unten', version: 2, art: 'anzeigen', titel: { de: 'Unten' }, faehigkeiten: ALLES,
                darstellung: { platz: 'unten' } },
    komponente: TestModul,
  },
  ui_ohne: { manifest: { name: 'ui_ohne', version: 2, art: 'anzeigen', titel: { de: 'Ohne' } }, komponente: TestModul },
  ui_frage: {
    manifest: { name: 'ui_frage', version: 1, art: 'abfragen', titel: { de: 'Frage' }, faehigkeiten: ['antworten'] },
    komponente: TestFrage,
  },
};

function block(mehr: Partial<UiBlock> = {}): UiBlock {
  return { block_id: 'b0000001', modul: 'ui_test', version: 2, art: 'anzeigen',
           daten: { text: 'Hallo Modul' }, text: 'Textfassung', status: 'nur_anzeige', ...mehr };
}

const TREFFER = {
  kontext: {
    kennung: 'shell',
    withBsid: (url: string | null | undefined) => `${url}?bsid=s1`,
    externalLinkWarning: (url: string | null | undefined) => (url?.includes('fremd') ? 'Externe Seite' : ''),
  },
  kacheln: () => true, beschaeftigt: () => false,
  volltext: vi.fn(), sammlung: vi.fn(), lernpfad: vi.fn(), alsEntwurf: vi.fn(), mehrLaden: vi.fn(),
  zweig: vi.fn(async (nodeId: string) => ({ knoten: [{ id: `${nodeId}-1`, titel: 'Gleichungen' }] })),
} satisfies ShellTreffer;

const ANTWORTEN = vi.fn<ShellAntworten>();

const VERWEISE = {
  withBsid: (url: string | null | undefined) => `${url}?bsid=s1`,
  externalLinkWarning: (url: string | null | undefined) => (url?.includes('fremd') ? 'Externe Seite' : ''),
};

async function render(
  bloecke: UiBlock[], displayRules: Record<string, unknown> | null = null, platz: 'oben' | 'unten' = 'oben',
): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [UiBloeckeComponent],
    providers: [provideZonelessChangeDetection(), { provide: UI_MODUL_REGISTER, useValue: REGISTER }],
  });
  const sanitizer = TestBed.inject(DomSanitizer);
  const f = TestBed.createComponent(UiBloeckeComponent);
  f.componentRef.setInput('bloecke', bloecke);
  f.componentRef.setInput('sprache', 'de');
  f.componentRef.setInput('translate', createTranslator(DE, DE));
  f.componentRef.setInput('displayRules', displayRules);
  f.componentRef.setInput('verweise', VERWEISE);
  f.componentRef.setInput('platz', platz);
  f.componentRef.setInput('treffer', TREFFER);
  f.componentRef.setInput('nachrichtId', 'm1');
  f.componentRef.setInput('antworten', ANTWORTEN);
  f.componentRef.setInput('renderMarkdown', (c: string): SafeHtml => sanitizer.bypassSecurityTrustHtml(`<p class="md">${c}</p>`));
  await f.whenStable();
  fixture = f;
  return f.nativeElement as HTMLElement;
}

let fixture: ComponentFixture<UiBloeckeComponent>;

async function renderNeu(bloecke: UiBlock[], displayRules: Record<string, unknown> | null = null): Promise<HTMLElement> {
  TestBed.resetTestingModule();
  return render(bloecke, displayRules);
}

afterEach(() => { TestBed.resetTestingModule(); vi.restoreAllMocks(); ANTWORTEN.mockReset(); });

describe('UiBloeckeComponent', () => {
  it('rendert ein registriertes Modul mit seinen Daten', async () => {
    const el = await render([block()]);
    expect(el.querySelector('.test-modul')?.textContent).toBe('Hallo Modul');
    expect(el.querySelector('.ui-block__text')).toBeNull();      // keine Textfassung
  });

  it('zeigt die Textfassung, wenn das Modul fehlt', async () => {
    const el = await render([block({ modul: 'ui_unbekannt' })]);
    expect(el.querySelector('.test-modul')).toBeNull();
    expect(el.querySelector('.md')?.textContent).toBe('Textfassung');
  });

  it('zeigt die Textfassung, wenn die Version nicht passt', async () => {
    const el = await render([block({ version: 1 })]);
    expect(el.querySelector('.test-modul')).toBeNull();
    expect(el.querySelector('.md')?.textContent).toBe('Textfassung');
  });

  it('mehrere Blöcke in der Reihenfolge der Antwort', async () => {
    const el = await render([block({ block_id: 'b0000001', daten: { text: 'eins' } }),
                             block({ block_id: 'b0000002', modul: 'ui_fehlt', text: 'zwei' }),
                             block({ block_id: 'b0000003', daten: { text: 'drei' } })]);
    const texte = [...el.querySelectorAll('.ui-block')].map((b) => b.textContent ?? '');
    expect(texte.length).toBe(3);
    expect(texte[0]).toContain('eins');
    expect(texte[1].trim()).toBe('zwei');
    expect(texte[2]).toContain('drei');
  });

  it('beantwortete und veraltete Blöcke sind nur lesend', async () => {
    const el = await render([block({ art: 'abfragen', status: 'beantwortet', antwort: { wert: 'a' } }),
                             block({ block_id: 'b0000002', status: 'veraltet' }),
                             block({ block_id: 'b0000003', art: 'abfragen', status: 'offen' })]);
    const nurLesen = [...el.querySelectorAll('.test-modul')].map((p) => p.getAttribute('data-nur-lesen'));
    expect(nurLesen).toEqual(['true', 'true', 'false']);
  });

  it('stellt den Modul-Host bereit: Herunterladen bietet eine Datei an', async () => {
    const url = vi.fn(() => 'blob:probe');
    const frei = vi.fn();
    const vorher = { createObjectURL: URL.createObjectURL, revokeObjectURL: URL.revokeObjectURL };
    Object.assign(URL, { createObjectURL: url, revokeObjectURL: frei });
    try {
      let imDokument = false;
      const klick = vi.spyOn(HTMLAnchorElement.prototype, 'click')
        .mockImplementation(function (this: HTMLAnchorElement) { imDokument = this.isConnected; });
      const el = await render([block()]);
      vi.useFakeTimers({ toFake: ['setTimeout'] });
      (el.querySelector('.test-laden') as HTMLButtonElement).click();
      expect(url).toHaveBeenCalledTimes(1);
      expect(klick).toHaveBeenCalledTimes(1);
      const a = klick.mock.contexts[0] as HTMLAnchorElement;
      expect(a.download).toBe('probe.md');
      // Firefox folgt einem download-Anker nur, wenn er im Dokument haengt; danach wieder weg.
      expect(imDokument).toBe(true);
      expect(a.isConnected).toBe(false);
      // Manche Browser lesen die Blob-Adresse erst nach dem Klick — Freigabe daher verzögert.
      expect(frei).not.toHaveBeenCalled();
      vi.advanceTimersByTime(60_000);
      expect(frei).toHaveBeenCalledWith('blob:probe');
    } finally {
      Object.assign(URL, vorher);
      vi.useRealTimers();
    }
  });

  it('ein Block ohne daten zeigt die Textfassung, ohne text bleibt sie leer (alter Verlauf)', async () => {
    const roh = { block_id: 'b0000009', modul: 'ui_test', version: 2, art: 'anzeigen', status: 'nur_anzeige' };
    const mitText = await render([{ ...roh, text: 'Fassung' } as unknown as UiBlock]);
    expect(mitText.querySelector('.test-modul')).toBeNull();
    expect(mitText.querySelector('.ui-block__text')?.textContent).toContain('Fassung');
    const ohneModul = await renderNeu([{ ...roh, modul: 'ui_fehlt' } as unknown as UiBlock]);
    expect(ohneModul.querySelector('.ui-block')?.textContent?.trim()).toBe('');
  });

  it('Drucken öffnet die Druckansicht mit Titel und Markdown', async () => {
    const geschrieben: string[] = [];
    vi.stubGlobal('open', () => ({
      document: { write: (html: string) => { geschrieben.push(html); }, close: () => {} },
      addEventListener: () => {}, setTimeout: () => 0, print: () => {},
    }));
    try {
      const el = await render([block()]);
      (el.querySelector('.test-drucken') as HTMLButtonElement).click();
      expect(geschrieben.length).toBe(1);
      expect(geschrieben[0]).toContain('<title>Probe-Titel</title>');
      expect(geschrieben[0]).toContain('lang="de"');
      expect(geschrieben[0]).toContain('Abschnitt');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('Markdown rendert der Host mit dem Renderer der Shell', async () => {
    const el = await render([block()]);
    expect(el.querySelector('.test-md .md')?.textContent).toBe('**fett**');
  });

  it('die Schriftskala kommt aus den Anzeige-Regeln, begrenzt auf 0,7–1', async () => {
    const skala = async (regeln: Record<string, unknown> | null) =>
      (await renderNeu([block()], regeln)).querySelector('.test-modul')?.getAttribute('data-skala');
    expect(await skala(null)).toBe('0.85');
    expect(await skala({ inline_documents: { font_size_percent: 70 } })).toBe('0.7');
    expect(await skala({ inline_documents: { font_size_percent: 150 } })).toBe('1');
  });

  it('zeigt nur die Blöcke seines Platzes; ohne Angabe gilt oben', async () => {
    const zwei = [block(), block({ block_id: 'b0000002', modul: 'ui_unten' })];
    const oben = await renderNeu(zwei);
    expect([...oben.querySelectorAll('.ui-block')].map((e) => e.getAttribute('data-modul'))).toEqual(['ui_test']);
    TestBed.resetTestingModule();
    const unten = await render(zwei, null, 'unten');
    expect([...unten.querySelectorAll('.ui-block')].map((e) => e.getAttribute('data-modul'))).toEqual(['ui_unten']);
  });

  it('ein Platz ohne Blöcke nimmt keinen Raum ein', async () => {
    const el = await render([block()], null, 'unten');
    expect(el.hidden).toBe(true);
  });

  it('der Host baut Links wie die Shell: Sitzungs-Kennung und Hinweis', async () => {
    const el = await render([block()]);
    const link = el.querySelector('.test-link') as HTMLElement;
    expect(link.getAttribute('data-href')).toBe('https://wirlernenonline.de/x?bsid=s1');
    expect(link.getAttribute('data-hinweis')).toBe('');
  });

  it('Treffer-Umgebung, Anzeige-Regeln und die Volltext-Aktion kommen von der Shell', async () => {
    const el = await render([block()], { groups: { materialien_max: 4 } });
    const t = el.querySelector('.test-treffer') as HTMLElement;
    expect(t.getAttribute('data-kacheln')).toBe('true');
    expect(t.getAttribute('data-regeln')).toBe('ja');
    (el.querySelector('.test-volltext') as HTMLButtonElement).click();
    expect(TREFFER.volltext).toHaveBeenCalledWith('n1', 'T');
  });

  it('U1-h: Unterthemen nachladen geht an die Shell, die Daten kommen ins Modul zurück', async () => {
    const el = await render([block()]);
    (el.querySelector('.test-baum') as HTMLButtonElement).click();
    expect(TREFFER.zweig).toHaveBeenCalledWith('n2');
    await vi.waitFor(() => expect(ZWEIG_ERHALTEN).toEqual([{ knoten: [{ id: 'n2-1', titel: 'Gleichungen' }] }]));
  });

  it('„mehr laden“ geht an die eigene Nachricht — nicht über die Block-Kennung', async () => {
    const el = await render([block()]);
    (el.querySelector('.test-mehr') as HTMLButtonElement).click();
    expect(TREFFER.mehrLaden).toHaveBeenCalledWith('m1');
  });

  it('ein unbekannter Aktionsname scheitert mit Warnung, nicht als Ausnahme', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const el = await render([block()]);
    expect(() => (el.querySelector('.test-falsch') as HTMLButtonElement).click()).not.toThrow();
    expect(warn).toHaveBeenCalledWith('boerdi: unbekannte Modul-Aktion', 'quatsch');
  });

  it('U1-d1: ohne Fähigkeit im Manifest lädt ein Modul nichts herunter und baut keinen Link', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const url = vi.fn(() => 'blob:x');
    const vorher = URL.createObjectURL;
    Object.assign(URL, { createObjectURL: url });
    try {
      const el = await render([block({ modul: 'ui_ohne' })]);
      (el.querySelector('.test-laden') as HTMLButtonElement).click();
      expect(url).not.toHaveBeenCalled();
      expect(el.querySelector('.test-link')?.getAttribute('data-href')).toBe('');
      expect(warn).toHaveBeenCalledWith('boerdi: Modul-Fähigkeit fehlt', 'herunterladen', 'b0000001');
    } finally {
      Object.assign(URL, { createObjectURL: vorher });
    }
  });

  it('ohne Fähigkeit oeffnen baut auch der Treffer-Kontext keine Adressen (Review U1 gesamt, Befund 4)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const mit = (await render([block()])).querySelector('.test-treffer')!;
    expect(mit.getAttribute('data-karten-href')).toBe('https://fremd.example/k?bsid=s1');
    expect(mit.getAttribute('data-karten-hinweis')).toBe('Externe Seite');
    const ohne = (await renderNeu([block({ modul: 'ui_ohne' })])).querySelector('.test-treffer')!;
    expect(ohne.getAttribute('data-karten-href')).toBe('');
    expect(ohne.getAttribute('data-karten-hinweis')).toBe('');
    // Darstellung bleibt: Kacheln und „beschäftigt“ kommen weiter von der Shell.
    expect(ohne.getAttribute('data-kacheln')).toBe('true');
  });

  it('U1-d1: eine Antwort geht mit Nachricht und Kennung DIESES Blocks an die Shell', async () => {
    const el = await render([
      block({ block_id: 'b0000011', modul: 'ui_frage', version: 1, art: 'abfragen', status: 'offen' }),
      block({ block_id: 'b0000012', modul: 'ui_frage', version: 1, art: 'abfragen', status: 'offen' }),
    ]);
    const knoepfe = el.querySelectorAll<HTMLButtonElement>('.test-antworten');
    knoepfe[1].click();
    expect(ANTWORTEN).toHaveBeenCalledWith({
      nachrichtId: 'm1', blockId: 'b0000012', daten: { gewaehlt: ['a'] }, text: 'Antwort A' });
    // „beschäftigt“ kommt aus dem Zug der Shell.
    expect(knoepfe[0].getAttribute('data-beschaeftigt')).toBe('false');
  });

  it('U1-d1: neue Blöcke derselben Kennung behalten ihre Modul-Instanz (eigener Zustand bleibt)', async () => {
    const el = await render([block()]);
    const vorher = el.querySelector('.test-modul');
    fixture.componentRef.setInput('bloecke', [block({ daten: { text: 'neu' } })]);
    await fixture.whenStable();
    const nachher = el.querySelector('.test-modul');
    expect(nachher?.textContent).toBe('neu');
    expect(nachher).toBe(vorher);
  });

  it('ohne Blöcke rendert nichts', async () => {
    const el = await render([]);
    expect(el.querySelectorAll('.ui-block').length).toBe(0);
  });
});

describe('WidgetModulHost.link — nur http(s) (Review U1 gesamt, Befund 3)', () => {
  const host = new WidgetModulHost({ verweise: () => VERWEISE } as unknown as HostSeams);

  it('andere Schemata und relative Adressen ergeben keinen Link', () => {
    for (const url of ['javascript:alert(1)', ' JavaScript:alert(1)', 'data:text/html,<b>x</b>', 'mailto:a@b.de',
      'ftp://wirlernenonline.de/x', '/relativ', '//fremd.example/x', 'vbscript:x', '']) {
      expect(host.link(url), url).toEqual({ href: '', hinweis: '' });
    }
  });

  it('http und https gehen durch die Link-Regeln der Shell', () => {
    expect(host.link('https://wirlernenonline.de/x')).toEqual({ href: 'https://wirlernenonline.de/x?bsid=s1', hinweis: '' });
    expect(host.link('HTTP://fremd.example/y')).toEqual({ href: 'HTTP://fremd.example/y?bsid=s1', hinweis: 'Externe Seite' });
  });
});
