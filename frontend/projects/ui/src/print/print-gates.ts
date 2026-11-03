/**
 * Print-Gates (8-4S-f1) — die Prädikate, die im Message-Row-Template
 * entscheiden, welche Druck-Leiste eine Bot-Bubble bekommt, plus der Druck-
 * Trigger. Bodies verbatim aus ALT chat.component.ts
 * (859-863, 883-893, 901-904, 910-916).
 *
 * Wohnen hier statt in der Shell, weil sie rein über `ChatMessage` arbeiten und
 * den `PRINTABLE_CANVAS_RE`-Sentinel des Print-Moduls lesen — dieselbe
 * Verantwortung („druckbarer Inhalt: erkennen + auslösen"), eigene Datei, weil
 * `print-utils.ts` nach C1-b4 über der ≤300-Schwelle lag (395 Z.; seit Paket 9
 * steht der Lernpfad-Druck in `print-lernpfad.ts`).
 */
import type { ModulRegister } from '@boerdi/ui-module';
import { INHALTSRAHMEN } from '@boerdi/ui-module/_vertrag/modul-namen';

import { ChatMessage } from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';
import { modulDarstellbar } from '../ui-bloecke/modul-darstellbar';
import { printLearningPath } from './print-lernpfad';
import { PRINTABLE_CANVAS_RE, printCanvasMaterial } from './print-utils';

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
 * Trägt die Nachricht einen Inhaltsrahmen-Block, den sein Modul zeigt (mit eigenem Druckknopf)?
 * Dann bekommt sie keine zusätzliche Druckleiste. Bei einer fremden Hauptversion steht nur die
 * Textfassung — dann bleibt die Leiste (Review U1 gesamt).
 */
export function hatDokumentBox(msg: ChatMessage, register: ModulRegister): boolean {
  return modulDarstellbar(msg, INHALTSRAHMEN, register);
}

/**
 * Erkennt Canvas-Material (Arbeitsblatt, Quiz, Bericht, …), das inline gelandet
 * ist, weil der Host `canvas-enabled="false"` setzt. Lernpfade haben ihren
 * eigenen Detektor + Button und sind hier ausgeschlossen, damit dieselbe
 * Nachricht nicht zwei Druck-Buttons bekommt.
 */
export function isPrintableCanvasMaterial(msg: ChatMessage): boolean {
  if (msg.sender !== 'bot') return false;
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
 * Druck-Fassade fürs Message-Row-Template (8-4S-f3): Gates + Trigger unter einem
 * Namen, damit die Shell nicht sechs identische Delegate-Methoden trägt, nur um
 * freie Funktionen im Template erreichbar zu machen (Angular-Templates können
 * keine Modul-Funktionen aufrufen). Reine Funktionsreferenzen — kein Zustand.
 */
export const SHELL_PRINT = {
  hatDokumentBox,
  isLearningPath,
  isPrintableCanvasMaterial,
  printableCanvasLabel,
  printCanvasMaterial,
  printLearningPath,
} as const;
