import { describe, expect, it, vi } from 'vitest';

import type { ModulHost } from '../_vertrag/modul-host';
import { ELEMENT_HOST_METHODEN, hostBruecke } from './host-bruecke';

function host(): ModulHost {
  return {
    herunterladen: vi.fn(), drucken: vi.fn(), markdown: vi.fn(), link: vi.fn(() => ({ href: 'h', hinweis: '' })),
    treffer: vi.fn(), aktion: vi.fn(), beschaeftigt: vi.fn(() => true), antworten: vi.fn(),
    vormerken: vi.fn(), zweig: vi.fn(async () => ({ knoten: [] })),
  } as unknown as ModulHost;
}

describe('hostBruecke (U3-0)', () => {
  it('gibt einem Custom Element nur die rahmenlosen Methoden, nicht markdown/treffer', () => {
    const bruecke = hostBruecke(host());
    expect(Object.keys(bruecke).sort()).toEqual([...ELEMENT_HOST_METHODEN].sort());
    expect('markdown' in bruecke).toBe(false);
    expect('treffer' in bruecke).toBe(false);
  });

  it('reicht Aufrufe samt Argumenten an den Block-Host weiter', async () => {
    const h = host();
    const bruecke = hostBruecke(h);
    bruecke.antworten({ a: 1 }, 'Text');
    bruecke.vormerken(null);
    expect(bruecke.beschaeftigt()).toBe(true);
    await expect(bruecke.zweig('n1')).resolves.toEqual({ knoten: [] });
    expect(h.antworten).toHaveBeenCalledWith({ a: 1 }, 'Text');
    expect(h.vormerken).toHaveBeenCalledWith(null);
    expect(h.zweig).toHaveBeenCalledWith('n1');
  });

  it('ist eingefroren — ein Modul kann sich keine Methode dazuschreiben', () => {
    const bruecke = hostBruecke(host()) as unknown as Record<string, unknown>;
    expect(Object.isFrozen(bruecke)).toBe(true);
    expect(() => { bruecke['markdown'] = () => ''; }).toThrow();
  });
});
