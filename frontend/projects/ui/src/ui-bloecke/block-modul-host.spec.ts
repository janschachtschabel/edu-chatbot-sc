import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ModulFaehigkeit } from '@boerdi/ui-module';

import { BlockModulHost } from './block-modul-host';
import type { WidgetModulHost } from './widget-modul-host';

/**
 * Paket U1-d1 (d1-8, aus U1-b1 verschoben): jeder Block bekommt einen eigenen Host. Er kennt die
 * Block-Kennung und lässt nur die Fähigkeiten aus dem Manifest zu — `herunterladen`, `drucken`,
 * `oeffnen` (Link, Aktionen), `antworten`. Fehlt eine, passiert nichts außer einer Warnung.
 * Markdown, Treffer-Umgebung und „beschäftigt“ sind Darstellung und immer erlaubt.
 */
function basis() {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), markdown: vi.fn(() => 'md'),
    link: vi.fn(() => ({ href: 'https://x/?bsid=1', hinweis: '' })),
    treffer: vi.fn(() => ({ kontext: null, kacheln: false, beschaeftigt: true })),
    beschaeftigt: vi.fn(() => true),
    aktion: vi.fn(), antwortSenden: vi.fn(), vormerken: vi.fn(),
    zweig: vi.fn(async (nodeId: string) => ({ knoten: [{ id: `${nodeId}-1`, titel: 'Kind' }] })),
    ablegen: vi.fn(async () => ({ stand: 'stored' })),
    auftrag: vi.fn(async () => ({ stand: 'laeuft' })),
  };
}

function host(faehigkeiten: readonly ModulFaehigkeit[] | undefined, b = basis()) {
  return { b, h: new BlockModulHost(b as unknown as WidgetModulHost, 'b0000007', faehigkeiten) };
}

afterEach(() => vi.restoreAllMocks());

describe('BlockModulHost', () => {
  it('mit Fähigkeit geht der Aufruf an den Widget-Host', () => {
    const { b, h } = host(['herunterladen', 'drucken', 'oeffnen', 'antworten']);
    h.herunterladen('a.md', 'text/markdown', '#');
    h.drucken('T', '#');
    expect(h.link('https://x/')).toEqual({ href: 'https://x/?bsid=1', hinweis: '' });
    h.aktion('volltext', { nodeId: 'n', title: 't' });
    h.aktion('mehrLaden', { blockId: 'b0000007' });
    h.antworten({ gewaehlt: ['a'] }, 'A');
    expect(b.herunterladen).toHaveBeenCalledWith('a.md', 'text/markdown', '#');
    expect(b.drucken).toHaveBeenCalledWith('T', '#');
    expect(b.aktion).toHaveBeenCalledWith('volltext', { nodeId: 'n', title: 't' });
    expect(b.aktion).toHaveBeenCalledWith('mehrLaden', { blockId: 'b0000007' });
    // Die Antwort trägt die Kennung DIESES Blocks — das Modul nennt sie nicht selbst.
    expect(b.antwortSenden).toHaveBeenCalledWith('b0000007', { gewaehlt: ['a'] }, 'A');
  });

  it('U2: vormerken gehört zur Fähigkeit `antworten` und trägt die Block-Kennung', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const mit = host(['antworten']);
    mit.h.vormerken({ knoten: [] });
    mit.h.vormerken(null);
    expect(mit.b.vormerken).toHaveBeenNthCalledWith(1, 'b0000007', { knoten: [] });
    expect(mit.b.vormerken).toHaveBeenNthCalledWith(2, 'b0000007', null);
    const ohne = host(['herunterladen']);
    ohne.h.vormerken({ knoten: [] });
    expect(ohne.b.vormerken).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith('boerdi: Modul-Fähigkeit fehlt', 'antworten', 'b0000007');
  });

  it('U1-h: mit Fähigkeit `nachladen` geht `zweig` an den Widget-Host und kommt mit Daten zurück', async () => {
    const { b, h } = host(['nachladen']);
    await expect(h.zweig('n3')).resolves.toEqual({ knoten: [{ id: 'n3-1', titel: 'Kind' }] });
    expect(b.zweig).toHaveBeenCalledWith('n3');
  });

  it('U3-3b: `ablegen` gehört zur Fähigkeit `hochladen` und trägt die Block-Kennung', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const mit = host(['hochladen']);
    const schritt = { schritt: 'abschluss', batchToken: 'tok-1234567890' } as const;
    await expect(mit.h.ablegen(schritt)).resolves.toEqual({ stand: 'stored' });
    expect(mit.b.ablegen).toHaveBeenCalledWith('b0000007', schritt);
    const ohne = host(['antworten']);
    await expect(ohne.h.ablegen(schritt)).rejects.toMatchObject({ status: 403, code: 'aus' });
    expect(ohne.b.ablegen).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith('boerdi: Modul-Fähigkeit fehlt', 'hochladen', 'b0000007');
  });

  it('K1b: `auftrag` gehört zur Fähigkeit `auftrag`', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const mit = host(['auftrag']);
    const schritt = { schritt: 'stand', ablauf: 'lesen', kuerzel: '0123456789ab' } as const;
    await expect(mit.h.auftrag(schritt)).resolves.toEqual({ stand: 'laeuft' });
    expect(mit.b.auftrag).toHaveBeenCalledWith(schritt);
    const ohne = host(['hochladen']);
    await expect(ohne.h.auftrag(schritt)).rejects.toMatchObject({ status: 403, code: 'aus' });
    expect(ohne.b.auftrag).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith('boerdi: Modul-Fähigkeit fehlt', 'auftrag', 'b0000007');
  });

  it('U1-h: ohne Fähigkeit `nachladen` lehnt `zweig` ab, ohne zu laden', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { b, h } = host(['oeffnen']);
    // Review U1-h, Befund 9: mit Status 403 — das Modul bietet dann keinen neuen Versuch an.
    await expect(h.zweig('n3')).rejects.toMatchObject({ status: 403 });
    expect(b.zweig).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith('boerdi: Modul-Fähigkeit fehlt', 'nachladen', 'b0000007');
  });

  it('ohne Fähigkeit passiert nichts, nur eine Warnung', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { b, h } = host([]);
    h.herunterladen('a.md', 'text/markdown', '#');
    h.drucken('T', '#');
    h.aktion('sammlung', { nodeId: 'n', title: 't' });
    h.antworten({ gewaehlt: ['a'] }, 'A');
    expect(h.link('https://x/')).toEqual({ href: '', hinweis: '' });
    for (const f of [b.herunterladen, b.drucken, b.aktion, b.antwortSenden, b.link]) {
      expect(f).not.toHaveBeenCalled();
    }
    expect(warn).toHaveBeenCalledWith('boerdi: Modul-Fähigkeit fehlt', 'antworten', 'b0000007');
    expect(warn).toHaveBeenCalledTimes(5);
  });

  it('ohne Angabe im Manifest gilt: keine Fähigkeit', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { b, h } = host(undefined);
    h.antworten({ gewaehlt: ['a'] }, 'A');
    expect(b.antwortSenden).not.toHaveBeenCalled();
  });

  it('Markdown, Treffer-Umgebung und „beschäftigt“ sind immer erlaubt', () => {
    const { b, h } = host([]);
    expect(h.markdown('**x**')).toBe('md');
    expect(h.treffer().beschaeftigt).toBe(true);
    expect(h.beschaeftigt()).toBe(true);
    expect(b.markdown).toHaveBeenCalledWith('**x**');
  });
});
