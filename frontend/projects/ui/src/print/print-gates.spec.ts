// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import {
  hatDokumentBox, isLearningPath, isPrintableCanvasMaterial, printableCanvasLabel,
} from './print-gates';

/** Deutscher Übersetzer — pinnt den bisherigen Wortlaut über den Katalog. */
const t = createTranslator(DE, DE);

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
    expect(printableCanvasLabel(bot(SENTINEL), t)).toBe('Bruchrechnen Klasse 6');
  });

  it('leerer Titel → Material-Typ', () => {
    expect(printableCanvasLabel(bot('<!-- boerdi:printable-canvas|Quiz| -->'), t)).toBe('Quiz');
  });

  it('kein Sentinel / beide Felder leer → "Material"', () => {
    expect(printableCanvasLabel(bot('Normale Antwort'), t)).toBe('Material');
    expect(printableCanvasLabel(bot('<!-- boerdi:printable-canvas|| -->'), t)).toBe('Material');
  });

  it('nur der Rückfall kommt aus dem Übersetzer — Titel und Typ sind Backend-Daten (C1-b3)', () => {
    const en = createTranslator({ 'chat.print.canvasFallback': 'Material (EN)' }, DE);
    expect(printableCanvasLabel(bot('Normale Antwort'), en)).toBe('Material (EN)');
    expect(printableCanvasLabel(bot(SENTINEL), en)).toBe('Bruchrechnen Klasse 6');
  });
});

describe('hatDokumentBox (U1-b)', () => {
  const bot = (mehr: Partial<ChatMessage>): ChatMessage =>
    ({ sender: 'bot', content: '> **Lernpfad: Brüche', ...mehr }) as ChatMessage;
  const block = (modul: string) => ({
    block_id: 'b0000001', modul, version: 1, art: 'anzeigen' as const, daten: {}, text: '', status: 'nur_anzeige' as const,
  });

  it('erkennt den Inhaltsrahmen-Block', () => {
    expect(hatDokumentBox(bot({ ui: { ui_bloecke: [block('ui_inhaltsrahmen')] } }))).toBe(true);
  });

  it('andere Module und leere Nachrichten zählen nicht', () => {
    expect(hatDokumentBox(bot({ ui: { ui_bloecke: [block('ui_linkbox')] } }))).toBe(false);
    expect(hatDokumentBox(bot({}))).toBe(false);
  });
});
