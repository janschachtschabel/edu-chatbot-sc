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
    aktion: vi.fn(), antwortSenden: vi.fn(),
    zweig: vi.fn(async (nodeId: string) => ({ knoten: [{ id: `${nodeId}-1`, titel: 'Kind' }] })),
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

  it('U1-h: mit Fähigkeit `nachladen` geht `zweig` an den Widget-Host und kommt mit Daten zurück', async () => {
    const { b, h } = host(['nachladen']);
    await expect(h.zweig('n3')).resolves.toEqual({ knoten: [{ id: 'n3-1', titel: 'Kind' }] });
    expect(b.zweig).toHaveBeenCalledWith('n3');
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
