/**
 * Print-Gates (8-4S-f1) — die Prädikate, die im Message-Row-Template
 * entscheiden, welche Druck-Leiste eine Bot-Bubble bekommt, plus der Druck-
 * Trigger der InlineDocument-Box. Bodies verbatim aus ALT chat.component.ts
 * (859-863, 883-893, 901-904, 910-916).
 *
 * Wohnen hier statt in der Shell, weil sie rein über `ChatMessage` arbeiten und
 * den `PRINTABLE_CANVAS_RE`-Sentinel des Print-Moduls lesen — dieselbe
 * Verantwortung („druckbarer Inhalt: erkennen + auslösen"), eigene Datei, weil
 * `print-utils.ts` schon über der ≤300-Schwelle liegt (395 Z. nach C1-b4).
 */
import { inlineDocFallbackLabel } from '../inline-doc/inline-doc';
import { ChatMessage } from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';
import {
  PRINTABLE_CANVAS_RE, printCanvasMaterial, printLearningPath, printMarkdownDocument,
} from './print-utils';

/**
 * Erkennt, ob eine Bot-Nachricht ein Lernpfad ist. Beide Marker erzeugt
 * `generate_learning_path_text` im Backend verbatim: das eröffnende Blockquote
 * „> **Lernpfad:" und der „### Schritt 1"-Header.
 */
export function isLearningPath(msg: ChatMessage): boolean {
  if (msg.sender !== 'bot' || !msg.content) return false;
  const c = msg.content;
  return /\*\*Lernpfad:/i.test(c) || /^#{1,3}\s*Schritt\s*\d/mi.test(c);
}

/**
 * Erkennt Canvas-Material (Arbeitsblatt, Quiz, Bericht, …), das inline gelandet
 * ist, weil der Host `canvas-enabled="false"` setzt. Lernpfade haben ihren
 * eigenen Detektor + Button und sind hier ausgeschlossen, damit dieselbe
 * Nachricht nicht zwei Druck-Buttons bekommt.
 */
export function isPrintableCanvasMaterial(msg: ChatMessage): boolean {
  if (msg.sender !== 'bot') return false;
  // Welle E (2026-05-24): jede InlineDocument-Box (ki_material / lernpfad /
  // edit / bericht / remix) ist druckbar. Der Sentinel-im-`msg.content`-Pfad
  // bleibt als Fallback für ältere Messages (z.B. aus dem Session-Restore).
  const docs = msg.inlineDocuments || [];
  if (docs.length > 0) return true;
  if (!msg.content) return false;
  if (isLearningPath(msg)) return false;
  return PRINTABLE_CANVAS_RE.test(msg.content);
}

/**
 * Lesbares Label des Canvas-Materials („Arbeitsblatt", „Quiz", „Material") —
 * Titel des Druckdialogs bzw. Beschriftung der Legacy-Druck-Leiste.
 *
 * Nur der Rückfall kommt aus dem Katalog (C1-b3): Typ und Titel stehen im
 * Backend-Sentinel und sind Inhalt, kein Oberflächentext.
 */
export function printableCanvasLabel(msg: ChatMessage, t: TranslateFn): string {
  const m = (msg.content || '').match(PRINTABLE_CANVAS_RE);
  if (!m) return t('chat.print.canvasFallback');
  const type = (m[1] || '').trim();
  const title = (m[2] || '').trim();
  return title || type || t('chat.print.canvasFallback');
}

/**
 * Welle E (2026-05-24): Druck-Trigger direkt aus der InlineDocument-Box. Nutzt
 * `doc.title` als Print-Header und `doc.content` als Markdown-Body — kein
 * Sentinel-Parse nötig.
 */
export function printInlineDocument(
  doc: { title: string; content: string; kind: string },
  t: TranslateFn,
): void {
  if (!doc || !doc.content) return;
  printMarkdownDocument(doc.title || inlineDocFallbackLabel(doc.kind, t), doc.content, t);
}

/**
 * Druck-Fassade fürs Message-Row-Template (8-4S-f3): Gates + Trigger unter einem
 * Namen, damit die Shell nicht sechs identische Delegate-Methoden trägt, nur um
 * freie Funktionen im Template erreichbar zu machen (Angular-Templates können
 * keine Modul-Funktionen aufrufen). Reine Funktionsreferenzen — kein Zustand.
 */
export const SHELL_PRINT = {
  isLearningPath,
  isPrintableCanvasMaterial,
  printableCanvasLabel,
  printInlineDocument,
  printCanvasMaterial,
  printLearningPath,
} as const;
