import { describe, expect, it } from 'vitest';

import { ausEintraegen, erfasse, GRENZEN, type Quelle } from './upload-erfassen';

const G = { ...GRENZEN, maxDateien: 5, maxTiefe: 3, maxBytesDatei: 1000 };

function q(relPfad: string, size = 10, type = 'application/pdf'): Quelle<string> {
  return { relPfad, name: relPfad.split('/').pop() ?? relPfad, size, type, handle: relPfad };
}

describe('erfasse (U3-1a)', () => {
  it('baut aus relativen Pfaden einen Ordnerbaum mit der Wurzel des gewählten Ordners', () => {
    const e = erfasse([q('Physik/Mechanik/hebel.pdf'), q('Physik/plan.docx'), q('Physik/Mechanik/kraft.pdf')], G);
    expect(e.wurzel.name).toBe('Physik');
    expect(e.wurzel.dateien.map((i) => e.dateien[i].name)).toEqual(['plan.docx']);
    expect(e.wurzel.ordner.map((o) => o.name)).toEqual(['Mechanik']);
    expect(e.wurzel.ordner[0].dateien.map((i) => e.dateien[i].name)).toEqual(['hebel.pdf', 'kraft.pdf']);
    expect(e.warnungen).toEqual([]);
  });

  it('mehrere Wurzeln oder lose Dateien bekommen eine gemeinsame Wurzel „Auswahl“', () => {
    const e = erfasse([q('a.pdf'), q('B/c.pdf')], G);
    expect(e.wurzel.name).toBe('');
    expect(e.wurzel.ordner.map((o) => o.name)).toEqual(['B']);
    expect(e.wurzel.dateien).toHaveLength(1);
  });

  it('Systemdateien sind ignoriert, ohne Warnung', () => {
    const e = erfasse([q('P/.DS_Store'), q('P/Thumbs.db'), q('P/~$entwurf.docx'), q('P/desktop.ini'), q('P/x.pdf')], G);
    expect(e.dateien.filter((d) => d.rolle === 'ignorieren').map((d) => d.name).sort())
      .toEqual(['.DS_Store', 'Thumbs.db', 'desktop.ini', '~$entwurf.docx']);
    expect(e.warnungen).toEqual([]);
  });

  it('leere und zu große Dateien sind ignoriert und gemeldet', () => {
    const e = erfasse([q('P/leer.pdf', 0), q('P/riesig.pdf', 5000), q('P/gut.pdf')], G);
    expect(e.dateien.find((d) => d.name === 'leer.pdf')).toMatchObject({ rolle: 'ignorieren', grund: 'leer' });
    expect(e.dateien.find((d) => d.name === 'riesig.pdf')).toMatchObject({ rolle: 'ignorieren', grund: 'zu_gross' });
    expect([...e.warnungen].sort()).toEqual(['leer', 'zu_gross']);
  });

  it('über der Höchstzahl: die ersten nach Pfad, Rest weg, Warnung', () => {
    const e = erfasse(['f', 'b', 'd', 'a', 'e', 'c', 'g'].map((n) => q(`P/${n}.pdf`)), G);
    expect(e.dateien.map((d) => d.name)).toEqual(['a.pdf', 'b.pdf', 'c.pdf', 'd.pdf', 'e.pdf']);
    expect(e.warnungen).toEqual(['zu_viele']);
  });

  it('zu tiefe Ordner werden in der tiefsten erlaubten Ebene zusammengefasst', () => {
    const e = erfasse([q('P/a/b/c/d/x.pdf')], G);
    const ebene3 = e.wurzel.ordner[0].ordner[0].ordner[0];
    expect(ebene3.name).toBe('c');
    expect(ebene3.ordner).toEqual([]);
    expect(ebene3.dateien).toHaveLength(1);
    expect(e.warnungen).toEqual(['zu_tief']);
  });

  it('Pfade mit .., . oder Steuerzeichen werden verworfen und gemeldet', () => {
    const e = erfasse([q('P/../x.pdf'), q('P/./y.pdf'), q('P/\u0007z.pdf'), q('P/ok.pdf')], G);
    expect(e.dateien.map((d) => d.name)).toEqual(['ok.pdf']);
    expect(e.warnungen).toEqual(['ungueltiger_pfad']);
  });

  it('Backslashes (Windows) gelten als Trenner', () => {
    const e = erfasse([q('P\\Sub\\x.pdf')], G);
    expect(e.wurzel.ordner[0].name).toBe('Sub');
  });

  it('nichts erfasst: leere Wurzel ohne Warnung', () => {
    const e = erfasse([], G);
    expect(e.dateien).toEqual([]);
    expect(e.wurzel.ordner).toEqual([]);
  });
});

describe('ausEintraegen (Drag & Drop, U3-1a)', () => {
  /** Nachbau der FileSystem-API: Ordner liefern ihre Einträge in Stücken (Chrome höchstens 100). */
  function datei(name: string, size = 10) {
    return { isFile: true, isDirectory: false, name,
      file: (ok: (f: File) => void) => ok(new File([new Uint8Array(size)], name, { type: 'application/pdf' })) };
  }
  function ordner(name: string, kinder: unknown[], stueck = 2) {
    return { isFile: false, isDirectory: true, name,
      createReader: () => {
        let rest = [...kinder];
        return { readEntries: (ok: (e: unknown[]) => void) => { const teil = rest.slice(0, stueck); rest = rest.slice(stueck); ok(teil); } };
      } };
  }

  it('liest Ordner rekursiv und vollständig, auch wenn sie in Stücken liefern', async () => {
    const quellen = await ausEintraegen([ordner('P', [datei('a.pdf'), datei('b.pdf'), datei('c.pdf'), ordner('S', [datei('d.pdf')])])] as never);
    expect(quellen.map((x) => x.relPfad).sort()).toEqual(['P/S/d.pdf', 'P/a.pdf', 'P/b.pdf', 'P/c.pdf']);
    expect(quellen[0].handle).toBeInstanceOf(File);
  });

  it('hört nach der Höchstzahl auf zu lesen', async () => {
    const viele = Array.from({ length: 20 }, (_, i) => datei(`d${i}.pdf`));
    const quellen = await ausEintraegen([ordner('P', viele, 5)] as never, 7);
    expect(quellen).toHaveLength(7);
  });
});
