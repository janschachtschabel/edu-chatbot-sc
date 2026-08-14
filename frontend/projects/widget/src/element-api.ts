/**
 * Element-JS-API des Custom Elements `<boerdi-chat>` (8-5h).
 *
 * `createCustomElement` spiegelt `input()`s auf Attribute/Properties und
 * `output()`s auf DOM-Events — aber es reicht KEINE beliebigen Komponenten-
 * Methoden durch. Der §5.5-Embed-Kontrakt verspricht der Host-Seite aber genau
 * das:
 *
 *     document.querySelector('boerdi-chat').openChatbot()
 *
 * Also legen wir die versprochenen Methoden auf den Element-Prototyp und
 * delegieren an die Komponenten-Instanz, die `NgElement` in einem privaten Feld
 * hält. Dieses Feld ist ein Implementierungsdetail von `@angular/elements` —
 * daher der defensive Zugriff und der ehrliche `undefined`-Fallback: ruft eine
 * Host-Seite die API, bevor das Element aufgewertet ist, bekommt sie ein No-Op
 * statt einer Exception.
 *
 * Eigene Datei (nicht in `widget-main.ts`): dort läuft der Bootstrap als
 * Top-Level-Seiteneffekt, ein Import in Tests würde eine echte Angular-App
 * starten. So bleibt die Regel testbar.
 */

/** Minimalvertrag, den wir vom `NgElement` brauchen. Absichtlich schmal — wir
 *  lesen genau ein privates Feld und nichts sonst. */
export interface NgElementLike {
  _ngElementStrategy?: {
    componentRef?: { instance?: Record<string, unknown> } | null;
  };
}

/** Methoden, die das Element an die Komponente durchreicht (§5.5 JS-API).
 *  `resetSession`/`updateContext` sind die V4-Ergänzungen.
 *
 *  `replaceContext` kam 2026-08-14 dazu (Befund der Plugin-Entwickler): in
 *  einer Erweiterungs-Seitenleiste gibt es weder den Attribut-Weg (nur in
 *  `ngOnInit` gelesen) noch den URL-Wächter (die Adresse der Leiste ändert sich
 *  nie). Blieb `updateContext` — das MERGT, also überleben der Host aus der
 *  Erkennung und die IDs des vorigen Tabs jeden Wechsel. Der ersetzende Weg
 *  existierte im Code (`onSpaContextChange`), nur nicht nach außen. */
export const FORWARDED_METHODS = [
  'openChatbot',
  'closeChatbot',
  'toggleChatbot',
  'isChatbotOpen',
  'resetSession',
  'updateContext',
  'replaceContext',
  'startTask',
] as const;

/** Komponenten-Instanz hinter einem `NgElement`, oder `undefined` solange das
 *  Element noch nicht aufgewertet/verbunden ist. */
export function componentOf(element: NgElementLike): Record<string, unknown> | undefined {
  return element?._ngElementStrategy?.componentRef?.instance;
}

/** Legt die Public-API-Methoden auf den Element-Prototyp. Vorhandene Namen
 *  werden nicht überschrieben — falls `@angular/elements` künftig selbst etwas
 *  gleichnamiges mitbringt, gewinnt dessen Implementierung. */
export function patchElementApi(prototype: object): void {
  for (const name of FORWARDED_METHODS) {
    if (name in prototype) continue;
    (prototype as Record<string, unknown>)[name] =
      function forwarded(this: NgElementLike, ...args: unknown[]): unknown {
        const instance = componentOf(this);
        const method = instance?.[name];
        if (typeof method !== 'function') return undefined;
        return (method as (...a: unknown[]) => unknown).apply(instance, args);
      };
  }
}
