/**
 * Die Namen der Ereignisse, die das Widget an die Gastseite feuert — und der
 * Doppelversand unter den alten Namen (U5a, 2026-08-09).
 *
 * **Warum diese Datei existiert.** Die vier Namen standen bis dahin als
 * Zeichenketten an vier verschiedenen Stellen (zwei in `host-events.ts`, zwei
 * in der Chat-Shell) plus in den Zuhörern der Widget-Hülle. Ein Umbenennen
 * hieße, sie alle gleichzeitig richtig zu treffen; die Doppelung während der
 * Übergangszeit hieße, sie alle zu verdoppeln. Beides gehört an EINE Stelle.
 *
 * **Warum der Doppelversand.** Der ALTE Chatbot feuert `badboerdi:…`; während
 * P11 laufen beide parallel, und es gibt Einbettungen, die auf den alten Namen
 * hören. Jedes Ereignis geht deshalb zweimal raus — neu zuerst (das ist der
 * Vertrag), alt hinterher (das ist die Nachsicht). Nach dem Cutover fällt
 * `legacyName` samt zweitem Versand ersatzlos weg; die Aufrufer bleiben, wie
 * sie sind.
 *
 * **Wer NICHT doppelt hört.** Die Widget-Hülle hört auf zwei dieser Ereignisse
 * als Rückfallweg für ihre eigene Chat-Shell (`host-bridges.ts`). Sie hört
 * ausschließlich auf den NEUEN Namen: die Shell feuert beide, und ein zweiter
 * Zuhörer würde jede Seiten-Aktion doppelt ausführen.
 */

/** Die vier Ereignisse. Reihenfolge = Reihenfolge der Vertragstabelle im
 *  Studio (`widget-contract-data.ts`) und der Demo-Seite. */
export const HOST_EVENTS = {
  guideSuggestion: 'boerdi:guide-suggestion',
  routingDebug: 'boerdi:routing-debug',
  queryMeta: 'boerdi:query-meta',
  pageAction: 'boerdi:page-action',
} as const;

export type HostEventName = (typeof HOST_EVENTS)[keyof typeof HOST_EVENTS];

/** Der Name, unter dem der ALTE Chatbot dasselbe Ereignis feuert. Reine
 *  Ableitung — es gibt keine zweite Liste, die auseinanderlaufen könnte. */
export function legacyName(name: HostEventName): string {
  return 'bad' + name;
}

/** Ein Host-Ereignis feuern — neu und (Übergangszeit) alt.
 *
 *  `bubbles`/`composed` wie gehabt: das Widget lebt in einem Shadow-Root, ohne
 *  beides käme nichts an der Gastseite an. */
export function dispatchHostEvent(name: HostEventName, detail: unknown): void {
  for (const eventName of [name, legacyName(name)]) {
    window.dispatchEvent(new CustomEvent(eventName, {
      detail,
      bubbles: true,
      composed: true,
    }));
  }
}
