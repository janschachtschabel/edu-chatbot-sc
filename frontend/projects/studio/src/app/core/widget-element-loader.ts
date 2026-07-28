/**
 * Lädt das Custom Element `<boerdi-chat>` in die Studio-Seite (A6-Rest, 9-6).
 *
 * Das Element kommt aus DIESEM Workspace (§5.6 „Widget-Element aus demselben
 * Workspace"), nicht über `<script src="/widget/boerdi-widget.js">`: diese
 * Backend-Route ist bis heute ein P7-Stub (`api/widget.py` → 501), und selbst
 * fertig gebaut wäre sie das ausgelieferte Bundle — also genau die Quelle der
 * Fehlerklasse „Studio neu, Widget alt". Ein Import aus dem Workspace zeigt den
 * Stand, den derselbe Build gebaut hat.
 *
 * Eigene Datei mit DI, damit die View testbar bleibt: der Import startet eine
 * zweite Angular-Anwendung (`createApplication` in `widget-main.ts`), die in
 * jsdom nichts zu suchen hat. Die Tests der View ersetzen diese Naht.
 */
import { Injectable } from '@angular/core';

const ELEMENT_NAME = 'boerdi-chat';

/** Nach dieser Zeit gilt der Bootstrap als gescheitert. Grund: `widget-main.ts`
 *  fängt seinen eigenen Fehler ab und loggt ihn nur — ohne Frist bliebe die
 *  Vorschau für immer bei „wird geladen …" stehen und behauptete Fortschritt,
 *  den es nicht gibt. */
const BOOT_TIMEOUT_MS = 15_000;

/**
 * Wartet auf die Registrierung des Elements, aber nicht ewig.
 *
 * @throws wenn nach `timeoutMs` nichts registriert ist.
 */
export async function waitForElement(name: string, timeoutMs: number): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      customElements.whenDefined(name),
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error(`<${name}> wurde nicht registriert`)), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

@Injectable({ providedIn: 'root' })
export class WidgetElementLoader {
  async load(): Promise<void> {
    // Dynamisch, damit das Widget ein eigener Lazy-Chunk bleibt: wer die
    // Vorschau nie öffnet, lädt es nicht.
    await import('../../../../widget/src/widget-main');
    await waitForElement(ELEMENT_NAME, BOOT_TIMEOUT_MS);
  }
}
