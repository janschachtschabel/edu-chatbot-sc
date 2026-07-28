// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ChatMessage, InlineDocument } from '../grouping/message-types';
import {
  isLearningPath, isPrintableCanvasMaterial, printableCanvasLabel, printInlineDocument,
} from './print-gates';

/**
 * Print-Gates (8-4S-f1) — verbatim aus ALT chat.component.ts:859-916. Diese
 * Prädikate entscheiden im Message-Row-Template, welche Druck-Leiste eine
 * Bot-Bubble bekommt; sie sind rein über `ChatMessage` und gehören daher zum
 * Print-Modul, nicht in die Shell.
 */

function bot(content: string, extra: Partial<ChatMessage> = {}): ChatMessage {
  return { id: 'x', sender: 'bot', content, timestamp: new Date(), ...extra };
}

const SENTINEL = '<!-- boerdi:printable-canvas|Arbeitsblatt|Bruchrechnen Klasse 6 -->';

describe('isLearningPath (ALT 859-863)', () => {
  it('erkennt den Blockquote-Marker `**Lernpfad:` (case-insensitive)', () => {
    expect(isLearningPath(bot('> **Lernpfad: Bruchrechnen**\n\nText'))).toBe(true);
    expect(isLearningPath(bot('> **lernpfad: x**'))).toBe(true);
  });

  it('erkennt den Schritt-Header `### Schritt 1` (multiline)', () => {
    expect(isLearningPath(bot('Intro\n\n### Schritt 1: Start'))).toBe(true);
    expect(isLearningPath(bot('# Schritt 2'))).toBe(true);
  });

  it('false für user-Bubbles, leeren Inhalt und normalen Text', () => {
    expect(isLearningPath({ ...bot('> **Lernpfad: x**'), sender: 'user' })).toBe(false);
    expect(isLearningPath(bot(''))).toBe(false);
    expect(isLearningPath(bot('Hier sind ein paar Materialien.'))).toBe(false);
  });
});

describe('isPrintableCanvasMaterial (ALT 883-893)', () => {
  it('true sobald eine InlineDocument-Box da ist (Welle E, unabhängig vom Inhalt)', () => {
    const docs: InlineDocument[] = [{ kind: 'ki_material', title: 'T', content: 'c' }];
    expect(isPrintableCanvasMaterial(bot('kurzer Intro-Text', { inlineDocuments: docs }))).toBe(true);
    expect(isPrintableCanvasMaterial(bot('', { inlineDocuments: docs }))).toBe(true);
  });

  it('Fallback ohne Box: Sentinel im Inhalt → true', () => {
    expect(isPrintableCanvasMaterial(bot(SENTINEL + '\n\n# Arbeitsblatt'))).toBe(true);
  });

  it('Lernpfade ausgeschlossen (haben ihren eigenen Button) — keine 2 Druck-Leisten', () => {
    expect(isPrintableCanvasMaterial(bot(SENTINEL + '\n\n> **Lernpfad: x**'))).toBe(false);
  });

  it('false für user-Bubbles, leeren Inhalt und Text ohne Sentinel', () => {
    expect(isPrintableCanvasMaterial({ ...bot(SENTINEL), sender: 'user' })).toBe(false);
    expect(isPrintableCanvasMaterial(bot(''))).toBe(false);
    expect(isPrintableCanvasMaterial(bot('Normale Antwort'))).toBe(false);
  });
});

describe('printableCanvasLabel (ALT 910-916)', () => {
  it('Titel gewinnt vor Typ', () => {
    expect(printableCanvasLabel(bot(SENTINEL))).toBe('Bruchrechnen Klasse 6');
  });

  it('leerer Titel → Material-Typ', () => {
    expect(printableCanvasLabel(bot('<!-- boerdi:printable-canvas|Quiz| -->'))).toBe('Quiz');
  });

  it('kein Sentinel / beide Felder leer → "Material"', () => {
    expect(printableCanvasLabel(bot('Normale Antwort'))).toBe('Material');
    expect(printableCanvasLabel(bot('<!-- boerdi:printable-canvas|| -->'))).toBe('Material');
  });
});

describe('printInlineDocument (ALT 901-904)', () => {
  // Gemockt wird nur die Browser-Grenze (`window.open`), nicht das Print-Modul:
  // ein `vi.spyOn` auf den ESM-Export greift nicht, weil esbuild den Import
  // direkt bindet. So läuft der echte Pfad bis in das geschriebene HTML.
  function captureOpen(): { written: string[] } {
    const written: string[] = [];
    const fakeWin = {
      document: { write: (html: string) => { written.push(html); }, close: () => {} },
    };
    vi.stubGlobal('open', () => fakeWin);
    return { written };
  }

  afterEach(() => vi.unstubAllGlobals());

  it('druckt doc.content unter doc.title', () => {
    const { written } = captureOpen();
    printInlineDocument({ title: 'Mein Lernpfad', content: '# Inhalt', kind: 'lernpfad' });
    expect(written.length).toBe(1);
    expect(written[0]).toContain('<title>Mein Lernpfad</title>');
    expect(written[0]).toContain('Inhalt');
  });

  it('ohne Titel → Fallback-Label der kind (inlineDocFallbackLabel)', () => {
    const { written } = captureOpen();
    printInlineDocument({ title: '', content: '# Inhalt', kind: 'lernpfad' });
    expect(written[0]).toContain('<title>Lernpfad</title>');
  });

  it('ohne Inhalt: No-Op (kein Druckfenster für eine leere Box)', () => {
    const { written } = captureOpen();
    printInlineDocument({ title: 'T', content: '', kind: 'lernpfad' });
    expect(written).toEqual([]);
  });
});
