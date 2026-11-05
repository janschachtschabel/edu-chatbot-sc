/**
 * Cards-/Pagination-Aktionen (Sammlung durchstöbern, Lernpfad generieren,
 * Karten-Fenster erweitern, Nachladen) — extrahiert aus
 * ``chat.component.ts`` (Frontend-Split, 2026-07-09).
 *
 * Plain functions — die Aktionen halten keinen eigenen State; alles lebt
 * in der Message-Liste der Komponente. Live-Zustand kommt als
 * :class:`CollectionActionsContext` mit deferred Arrows herein (Muster
 * ``TourContext``): ``api``/``sessionId``/``isLoading``/``messages``
 * werden pro Aufruf frisch gelesen — die Bestands-Spec ersetzt
 * ``comp.api`` NACH Konstruktion durch einen Instanz-Fake, deshalb darf
 * hier nichts eager gebunden werden. Bodies verbatim übernommen —
 * KEINE Logik-Änderung. NEU: Imports umgehängt (``WloCard`` → ``../cards``,
 * Response-/Message-Modell → ``../grouping/message-types``).
 *
 * C1-b4: übersetzt werden die **Fehler-Bubbles**, nicht die gesendeten Texte
 * (``Inhalte der Sammlung "…"`` usw.). Letztere sind die Anweisung ans Backend
 * bzw. Modell — deutsch nach dem C1-Entscheid „Sprachdirektive im Prompt" — und
 * stehen so auch im gespeicherten Verlauf; eine Übersetzung machte die Historie
 * sprachabhängig.
 */
import { TREFFERLISTE } from '@boerdi/ui-module/_vertrag/modul-namen';

import { WloCard } from '../cards/card-types';
import {
  ChatMessage, ChatResponse, DebugInfo, PaginationInfo, UiInfo,
  QueryMetaEntry, WebLink, TopicPageView,
} from '../grouping/message-types';
import type { TranslateFn } from '../i18n/i18n';
import { fehlerKurz } from '../obs/fehler-kurz';
import { drosselHinweis, fristHinweis } from '../stream/http-fehler';
import { sitzungsWache } from '../session/session-id';

/** Live-Zustand/Seiteneffekte der ChatComponent, die die Aktionen
 *  brauchen — als deferred Arrows (Muster: ``TourContext``). */
export interface CollectionActionsContext {
  /** ``ApiService.sendMessage`` mit LIVE-``sessionId`` der Komponente.
   *  Arg-Reihenfolge wie ``ApiService.sendMessage`` ab Position 2
   *  (message, env, action, actionParams). */
  sendMessage: (
    message: string, env: any, action?: string,
    actionParams?: Record<string, any>,
  ) => Promise<ChatResponse>;
  /** LIVE-Sitzungs-ID: ein Vorgang gehört der Sitzung, in der er begann
   *  (`sitzungsWache`, Paket 3 T6). */
  sessionId: () => string;
  /** Globales ``isLoading``-Flag der Komponente (Turn-Serialisierung). */
  isLoading: () => boolean;
  setLoading: (v: boolean) => void;
  /** Message-Signal der Komponente: Snapshot-Read + Update-Reducer. */
  messages: () => ChatMessage[];
  updateMessages: (updater: (msgs: ChatMessage[]) => ChatMessage[]) => void;
  /** Message-State-Reducer der Komponente (Signaturen unverändert). */
  addBotMessage: (
    content: string, isLoading?: boolean, cards?: WloCard[],
    quickReplies?: string[], ui?: UiInfo,
    pagination?: PaginationInfo | null, queryMetas?: QueryMetaEntry[],
    webLinks?: WebLink[],
    displayRules?: Record<string, any>, topicPage?: TopicPageView | null,
  ) => string;
  removeMessage: (id: string) => void;
  /** Setzt ``scrollTargetId`` (konsumiert in ``ngAfterViewChecked``). */
  setScrollTarget: (id: string) => void;
  /** Setzt ``latestDebug`` (Debug-Panel). */
  /** Debug-Panel: Debug-Block (nur mit Freigabe, sonst `null`) und `ui` der Antwort. */
  setLatestDebug: (debug: DebugInfo | null | undefined, ui?: UiInfo) => void;
  /** Komponenten-``dispatchPageAction`` (host callback + Output + window-Event). */
  dispatchPageAction: (pa: { action: string; payload: any } | null | undefined) => void;
  /** ``messagesContainer?.nativeElement`` — LIVE (ViewChild füllt sich
   *  erst nach dem ersten Render); ``undefined`` toleriert. */
  messagesContainer: () => HTMLElement | undefined;
  /** Übersetzer für die Fehler-Bubbles (C1-b4). Über den Kontext wie alles
   *  andere hier — die Aktionen sind Modul-Funktionen ohne eigenen Zustand. */
  t: TranslateFn;
  /** U1-h: Unterthemen eines Knotens (`ChatApiClient.themenbaumZweig` mit LIVE-Sitzung). */
  ladeZweig: (nodeId: string, signal?: AbortSignal) => Promise<Record<string, unknown>>;
}

/** Was eine Karten-Aktion ausmacht: gesendeter Text (bleibt deutsch — er ist die Anweisung ans
 *  Backend, kein Oberflächentext), Direktaktion samt Parametern, Fehlertext und Protokollzeile. */
interface KartenAktionAuftrag {
  readonly nachricht: string;
  readonly aktion: string;
  readonly parameter: Record<string, string>;
  readonly fehlerSchluessel: string;
  readonly protokoll: string;
}

/** Der gemeinsame Ablauf der Karten-Aktionen: Loading-Bubble → sendMessage → Render →
 *  Scroll/Debug/PageAction, im Fehlerfall die übersetzte Fehler-Bubble. Seit U1-e eine Stelle
 *  statt vier fast wortgleicher Kopien (Upgrade-Pfad des früheren `simplify:`-Vermerks). */
async function runCardAction(
  auftrag: KartenAktionAuftrag, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  if (ctx.isLoading()) return;
  const veraltet = sitzungsWache(() => ctx.sessionId());
  ctx.setLoading(true);
  const loadingId = ctx.addBotMessage('', true);

  try {
    const resp = await ctx.sendMessage(auftrag.nachricht, undefined, auftrag.aktion, auftrag.parameter);
    if (veraltet()) return;
    ctx.removeMessage(loadingId);
    const botMsgId = ctx.addBotMessage(resp.content, false, resp.cards, resp.quick_replies, resp.ui, resp.pagination, undefined, resp.web_links, resp.display_rules);
    ctx.setScrollTarget(botMsgId);
    ctx.setLatestDebug(resp.debug, resp.ui);
    ctx.dispatchPageAction(resp.page_action);
  } catch (err) {
    if (veraltet()) return;
    console.warn(`boerdi: ${auftrag.protokoll} —`, fehlerKurz(err));
    ctx.removeMessage(loadingId);
    const errId = ctx.addBotMessage(
      drosselHinweis(ctx.t, err) ?? fristHinweis(ctx.t, err)
        ?? ctx.t(auftrag.fehlerSchluessel, { title }));
    ctx.setScrollTarget(errId);
  }
  ctx.setLoading(false);
}

/** Inhalte einer Sammlung als neuen Bot-Turn laden (Card-Button „Inhalte zeigen"). */
export function browseCollection(
  nodeId: string, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  return runCardAction({
    nachricht: `Inhalte der Sammlung "${title}"`, aktion: 'browse_collection',
    parameter: { collection_id: nodeId, title }, fehlerSchluessel: 'error.browseCollection',
    protokoll: 'Sammlung nicht geladen',
  }, title, ctx);
}

/** Volltext EINES Materials als neuen Bot-Turn holen (Card-Button
 *  „Inhalt anzeigen", M17).
 *
 *  Hinter `show_content_text` läuft bewusst KEIN Antwort-LLM: die Aktion
 *  liefert den Text unverändert als Inhaltsrahmen-Block (`ui.ui_bloecke`; Begründung im
 *  Backend-Modul `services/content_text_action.py`). Für diese Seite heißt
 *  das: nichts Besonderes zu tun — die Box steht an derselben Stelle der
 *  Render-Argumente wie bei M09/M10. */
export function showContentText(
  nodeId: string, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  return runCardAction({
    nachricht: `Inhalt von "${title}"`, aktion: 'show_content_text',
    parameter: { node_id: nodeId, title }, fehlerSchluessel: 'error.contentText',
    protokoll: 'Inhaltstext nicht geladen',
  }, title, ctx);
}

/** Lernpfad zu einer Sammlung generieren (Card-Button „Lernpfad"). */
export function generateLearningPath(
  nodeId: string, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  return runCardAction({
    nachricht: `Lernpfad für "${title}"`, aktion: 'generate_learning_path',
    parameter: { collection_id: nodeId, title }, fehlerSchluessel: 'error.learningPath',
    protokoll: 'Lernpfad nicht erzeugt',
  }, title, ctx);
}

/** Eine Sammlung als bearbeitbaren Strukturentwurf öffnen (Paket U2, „Als Entwurf bearbeiten“ im
 *  Themenbaum): neuer Zug ohne KI über die Direktaktion `edit_collection_as_draft`; die Antwort
 *  trägt einen `ui_strukturentwurf`-Block. */
export function editCollectionAsDraft(
  nodeId: string, title: string, ctx: CollectionActionsContext,
): Promise<void> {
  return runCardAction({
    nachricht: `Gliederung "${title}" als Entwurf bearbeiten`, aktion: 'edit_collection_as_draft',
    parameter: { collection_id: nodeId, title }, fehlerSchluessel: 'error.draftFromCollection',
    protokoll: 'Entwurf nicht geladen',
  }, title, ctx);
}

/** Unterthemen eines Knotens im Themenbaum (Paket U1-h): das Modul hängt sie in denselben Baum.
 *  Kein Zug — keine Blase, kein Laden-Zustand der Shell (geht auch während eines Zugs). Bis U1-h
 *  öffnete die Direktaktion `show_collection_tree` einen neuen Baum als Antwort darunter.
 *  Wechselt die Sitzung während des Ladens, gehört das Ergebnis nicht mehr hierher
 *  (`sitzungsWache`): dann lehnt der Aufruf ab. Fehler gehen samt `status` an das Modul.
 *  `signal` bricht den Abruf ab (die Shell, wenn das Widget entfernt wird). */
export async function themenbaumZweig(
  nodeId: string, ctx: CollectionActionsContext, signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const veraltet = sitzungsWache(() => ctx.sessionId());
  let daten: Record<string, unknown>;
  try {
    daten = await ctx.ladeZweig(nodeId, signal);
  } catch (err) {
    // U2 (Plan 2026-11-04 T-18): Art und HTTP-Status in die Konsole — ein Proxy vor dem Backend,
    // der `/api/ui/*` nicht durchreicht, zeigt sich als 404/405/502 (nie der Text, Paket 18E).
    console.warn('boerdi: Unterthemen nicht geladen —', fehlerKurz(err));
    throw err;
  }
  if (veraltet()) throw new Error('boerdi: Sitzung gewechselt — Zweig verworfen');
  return daten;
}

/** „Mehr anzeigen": Karten-Fenster einer Message um 5 erweitern.
 *
 *  Old visibleCardCount merken, damit wir nach dem Render zur ERSTEN
 *  neu enthüllten Card scrollen können — ohne den Scroll-Hint wirken
 *  die zusätzlichen Cards für den User "unsichtbar", weil sie unter
 *  der Scroll-Region des Messages-Containers erscheinen und die
 *  Pagination-Bar (mit aktualisierter "X von Y"-Zahl) den einzigen
 *  sofort sichtbaren Effekt zeigt. */
export function showMoreCards(msgId: string, ctx: CollectionActionsContext): void {
  const msg = ctx.messages().find(m => m.id === msgId);
  const previousCount = msg?.visibleCardCount || 5;
  ctx.updateMessages(all => all.map(m => {
    if (m.id !== msgId || !m.cards) return m;
    const newCount = previousCount + 5;
    return { ...m, visibleCardCount: newCount };
  }));
  // Nach Angular-Re-Render zur ersten neu enthüllten Card scrollen.
  // setTimeout(0) gibt der Change-Detection eine Tick Zeit, das DOM zu
  // aktualisieren. ``block: 'center'`` sorgt dafür, dass die Card
  // mittig in den Viewport rückt — der User sieht eindeutig dass neue
  // Inhalte aufgetaucht sind.
  setTimeout(() => {
    try {
      const container = ctx.messagesContainer();
      if (!container) return;
      // Alle wlo-card-wrapper innerhalb der Message finden (per msg.id-Anchor).
      const msgEl = container.querySelector(`#msg-${msgId}`);
      if (!msgEl) return;
      const cards = msgEl.querySelectorAll('.wlo-card-wrapper');
      // Erste neu enthüllte Card = Index previousCount (0-based).
      const target = cards[previousCount] as HTMLElement | undefined;
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } catch { /* never break a click handler */ }
  }, 0);
}

/** Die Trefferliste eines `ui` mit den nachgeladenen Karten und der neuen Seitenangabe. */
function mitNeuenKarten(ui: UiInfo, karten: WloCard[], seiten: PaginationInfo | null): UiInfo {
  if (!ui.ui_bloecke?.some((b) => b.modul === TREFFERLISTE)) return ui;
  return {
    ...ui,
    ui_bloecke: ui.ui_bloecke.map((b) =>
      b.modul === TREFFERLISTE ? { ...b, daten: { ...b.daten, karten, seiten } } : b),
  };
}

/** Pagination: weitere Inhalte einer Sammlung nachladen (Load more).
 *  Merged die neuen Cards in die BESTEHENDE Message (kein neuer Turn). */
export async function loadMore(msgId: string, ctx: CollectionActionsContext): Promise<void> {
  const msgs = ctx.messages();
  const msg = msgs.find(m => m.id === msgId);
  if (!msg?.pagination || !msg.pagination.has_more || ctx.isLoading()) return;

  const p = msg.pagination;
  const newSkip = p.skip_count + p.page_size;

  const veraltet = sitzungsWache(() => ctx.sessionId());
  ctx.setLoading(true);

  try {
    const resp = await ctx.sendMessage(
      `Weitere Inhalte von "${p.collection_title}"`,
      undefined,
      'browse_collection',
      { collection_id: p.collection_id, title: p.collection_title, skip_count: newSkip },
    );
    if (veraltet()) return;

    // Append new cards to existing message and reveal them immediately
    ctx.updateMessages(all => all.map(m => {
      if (m.id !== msgId) return m;
      const merged: WloCard[] = [...(m.cards || []), ...(resp.cards || [])];
      return {
        ...m,
        cards: merged,
        visibleCardCount: merged.length,
        pagination: resp.pagination || undefined,
        content: resp.content,
        // U1-c2b: die Trefferliste zeigt ihren Block — er bekommt dieselben Karten und Seiten.
        ui: m.ui && mitNeuenKarten(m.ui, merged, resp.pagination ?? null),
      };
    }));
  } catch (err) {
    if (veraltet()) return;
    // Review 2026-10-30: nur die Art des Fehlers — sein Text kann Antwortinhalt tragen.
    console.error('Load more failed:', fehlerKurz(err));
    // Paket 19 (Audit 2026-10-31 N-34): sonst scheiterte „Weitere laden“ still —
    // der Knopf stand wieder da, ohne dass jemand wusste, warum nichts kam.
    const errId = ctx.addBotMessage(
      drosselHinweis(ctx.t, err) ?? fristHinweis(ctx.t, err)
        ?? ctx.t('error.browseCollection', { title: p.collection_title }));
    ctx.setScrollTarget(errId);
  }

  ctx.setLoading(false);
}
