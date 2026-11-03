/**
 * Zustand abfragender UI-Blöcke im Widget (Paket U1-d1).
 *
 * Der Server schließt die offene Frage mit jedem Zug der Person (`services/ui_antwort`) und leitet
 * im Verlauf `beantwortet`/`veraltet` ab (`ui_module/antwort.status_ableiten`). Das Widget zieht
 * sofort nach: der beantwortete Block zeigt nur noch die Antwort, jede andere offene Frage wird
 * veraltet. Reine Funktionen über der Nachrichtenliste; unveränderte Nachrichten behalten ihre
 * Identität (OnPush, `track`).
 */
import type { UiBlock } from '@boerdi/ui-module';

import type { ChatMessage } from '../grouping/message-types';

function mitBloecken(
  msgs: ChatMessage[], aendern: (msg: ChatMessage, block: UiBlock) => UiBlock,
): ChatMessage[] {
  let geaendert = false;
  const neu = msgs.map((msg) => {
    const bloecke = msg.ui?.ui_bloecke;
    if (!bloecke?.length) return msg;
    const ersetzt = bloecke.map((b) => aendern(msg, b));
    if (ersetzt.every((b, i) => b === bloecke[i])) return msg;
    geaendert = true;
    return { ...msg, ui: { ...msg.ui, ui_bloecke: ersetzt } };
  });
  return geaendert ? neu : msgs;
}

const offen = (b: UiBlock) => b.art === 'abfragen' && b.status === 'offen';

/** Den Block `blockId` der Nachricht `nachrichtId` als beantwortet vermerken — nur, solange er offen ist. */
export function alsBeantwortet(
  msgs: ChatMessage[], nachrichtId: string, blockId: string, antwort: Record<string, unknown>,
): ChatMessage[] {
  return mitBloecken(msgs, (msg, b) =>
    msg.id === nachrichtId && b.block_id === blockId && offen(b)
      ? { ...b, status: 'beantwortet', antwort } : b);
}

/** Review U1-d1, Befund 7: Der Zug mit der Antwort kam nie beim Server an (Netz, Fehlerblase ohne
 *  `connected`) — die lokal beantwortete Frage ist wieder offen; dort ist sie es ja auch. */
export function wiederOffen(msgs: ChatMessage[], nachrichtId: string, blockId: string): ChatMessage[] {
  return mitBloecken(msgs, (msg, b) =>
    msg.id === nachrichtId && b.block_id === blockId && b.art === 'abfragen' && b.status === 'beantwortet'
      ? { ...b, status: 'offen', antwort: null } : b);
}

/** Jede noch offene Frage ist ab dem nächsten Zug der Person veraltet. */
export function offeneFragenSchliessen(msgs: ChatMessage[]): ChatMessage[] {
  return mitBloecken(msgs, (_msg, b) => (offen(b) ? { ...b, status: 'veraltet' } : b));
}
