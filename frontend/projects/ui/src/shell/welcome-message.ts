/**
 * Die feste Startnachricht des Widgets (2026-10-01 aus `lifecycle.ts` gelöst).
 *
 * Eine Änderungs-Ursache: welche Begrüßung samt Einstiegs-Chips das Widget
 * selbst zeigt. Die Kontext-Begrüßung des Backends ist ein anderer Weg
 * (`ContextGreetingController`) und bleibt draußen.
 */
import { WloCard } from '../cards/card-types';
import { ChatMessage } from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';

/** Katalog-Schlüssel der vier Einstiegs-Quick-Replies (ALT 337-342) — greifen
 *  nur, wenn `startReplies` leer ist. Die Reihenfolge ist die von ALT. */
const DEFAULT_REPLY_KEYS = [
  'greeting.reply.aiAge',
  'greeting.reply.search',
  'greeting.reply.tour',
  'greeting.reply.about',
];

/** Was die Startnachricht von der Shell braucht — eine Teilmenge des
 *  `LifecycleContext`, der Lebenszyklus reicht seinen Kontext durch. */
export interface WelcomeContext {
  greeting: () => string;
  startReplies: () => string[];
  /** `show-welcome` — `false` heißt: leerer Chat. */
  showWelcome: () => boolean;
  t: TranslateFn;
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[], quickReplies?: string[],
  ) => string;
  updateMessages: (updater: (msgs: ChatMessage[]) => ChatMessage[]) => void;
  hasUserMessages: () => boolean;
}

export class WelcomeMessage {
  /** ID der zuletzt gezeigten Startnachricht — woran `relocalize` sie erkennt. */
  private _id: string | null = null;

  constructor(private readonly ctx: WelcomeContext) {}

  /** Zentrale Begrüßung mit Einstiegs-Quick-Replies. Verbatim aus ALT 322-344,
   *  davor das Tor aus `show-welcome` (2026-08-14).
   *
   *  Der Ausstieg sitzt HIER und nicht bei den drei Aufrufern, weil sie alle
   *  dasselbe meinen — Erstaufruf, Neustart, leerer Verlauf. Ein Tor je
   *  Aufrufer wäre dreimal dieselbe Bedingung und beim vierten vergessen. */
  show(): void {
    if (!this.ctx.showWelcome()) return;
    const text = this.ctx.greeting() || this.ctx.t('greeting.default');
    const replies = (this.ctx.startReplies() && this.ctx.startReplies().length)
      ? this.ctx.startReplies()
      : DEFAULT_REPLY_KEYS.map(k => this.ctx.t(k));
    this._id = this.ctx.addBotMessage(text, false, undefined, replies);
  }

  /** Nach einem Sprachwechsel: die Startnachricht in der neuen Sprache zeigen,
   *  statt die alte stehen zu lassen (Paket 1, T2).
   *
   *  Nur, solange sie die einzige Nachricht ist und noch keine Frage gestellt
   *  wurde — danach ist sie Verlauf. Der Kontext-Gruß des Backends ist eine
   *  andere Nachricht: ihn speichert der Server, er bleibt stehen. */
  relocalize(): void {
    const id = this._id;
    if (!id || this.ctx.hasUserMessages()) return;
    let allein = false;
    this.ctx.updateMessages((msgs) => {
      allein = msgs.length === 1 && msgs[0].id === id;
      return allein ? [] : msgs;
    });
    if (allein) this.show();
  }
}
