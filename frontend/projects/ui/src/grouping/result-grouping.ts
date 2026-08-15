/**
 * Grouped-Result-Display — reine Funktionen für den Inline-Result-Grouping-
 * Modus (`inline-result-grouping="true"`): separate Boxen für Themenseiten /
 * Sammlungen / Materialien / Webseiten-Inhalte + Search-CTA statt flacher
 * Liste.
 *
 * Verbatim-Port des ALT `chat/result-grouping.utils.ts` (dort aus
 * `chat.component.ts` extrahiert, Frontend-Split 2026-07-09). Imports
 * umgehängt: `WloCard` + card-Helfer aus `../cards/*`, `ChatMessage` aus dem
 * schmalen `./message-types`. `GroupingContext` kapselt den Instanz-State,
 * den die Funktionen lesen (`withBsid`/`externalLinkWarning` — in NEU aus
 * `session/trusted-host`), als expliziten Parameter. KEINE Logik-Änderung.
 *
 * Fidelity-Port-Ausnahme zur ≤300-Zeilen-Regel: bewusst als EINE Datei
 * gehalten (wie ALT), damit die 1:1-Zuordnung erhalten bleibt — die
 * Funktionen bilden eine kohärente Feature-Einheit (ein Änderungsgrund: die
 * Grouping-Anzeige).
 */
import { WloCard } from '../cards/card-types';
import {
  getCardPrimaryUrl, isThemenseite, isSammlung, isInhalt, getContentTypeLabel,
} from '../cards/card-utils';
import type { TranslateFn } from '../i18n/i18n';
import { ChatMessage } from './message-types';

/** Instanz-State der ChatComponent, den die Grouping-Funktionen lesen —
 *  als explizite Funktions-Parameter statt ``this.``-Zugriff. */
export interface GroupingContext {
  /** ``ChatComponent._withBsid`` — hängt ``?bsid=<sessionId>`` an URLs zu
   *  Trusted-Hosts an (Cross-TLD-Session-Handoff). */
  withBsid: (url: string | null | undefined) => string;
  /** ``ChatComponent.externalLinkWarning`` — Warntooltip für Hosts
   *  außerhalb der Trusted-Liste, ``''`` wenn keiner nötig. */
  externalLinkWarning: (url: string | null | undefined) => string;
  /**
   * Übersetzer der Shell (C1-b2). Steht hier und nicht als eigener Input an
   * jeder Komponente, weil dieser Kontext ohnehin der Weg ist, auf dem die
   * drei Grouping-Renderer instanzgebundene Helfer bekommen — und weil die
   * reinen Label-Funktionen dieser Datei (C1-b3) denselben Zugang brauchen
   * werden. Ein zweiter Weg daneben wäre eine Quelle für Drift.
   */
  t: TranslateFn;
}

/**
 * Kontext für die Renderer, die den Such-Absprung zeigen. Erweitert den reinen
 * {@link GroupingContext} um die eine Host-Trust-Abfrage, die nur die
 * Target-Entscheidung der CTA braucht (`_self` vs. `_blank`, ALT
 * `ChatComponent.isHostTrusted`). Die Chat-Shell (8-4) baut ihn aus
 * `session/trusted-host` (sessionId + effektive Trusted-Liste) und reicht ihn
 * als Input herein — analog zum präsentationalen Schnitt des WloCard-Tiles
 * (8-2f), wo der Elternteil die Session-/Trust-Logik besitzt.
 *
 * Steht hier und nicht mehr in `result-groups.component` (U6b, 2026-08-09):
 * seit der Absprung auch unter dem Kachelraster hängt, brauchen ihn zwei
 * Renderer. Die Gruppen-Box importiert schon einen Typ AUS `cards/`; die
 * Gegenrichtung hätte einen Ring geschlossen.
 */
export interface ResultGroupsContext extends GroupingContext {
  /** ALT `ChatComponent.isHostTrusted(host)` = `isTrustedHost(host, effektive
   *  Trusted-Domains)`, gebunden an die Instanz-Liste. */
  isTrustedHost: (host: string) => boolean;
}

/** Dedup-Key für Gruppen-Items. Eine Karte gilt als duplikat-gleich
 *  wenn entweder ``node_id`` matched ODER der normalisierte Titel
 *  (lowercase, getrimmt) gleich ist. Hintergrund (User-Feedback
 *  2026-05-21): kombinierte Tool-Calls (search_wlo_collections +
 *  search_wlo_topic_pages + Prefetch) können denselben Datensatz unter
 *  verschiedenen Node-IDs liefern (z.B. "Winkelsummen" 2× nebeneinander
 *  in der Sammlungen-Box). Ein reiner node_id-Dedup wie in der
 *  Backend-Merge-Logik reicht dann nicht. */
export function _dedupKey(c: WloCard): { id: string; title: string } {
  const id = (c.node_id || '').trim();
  const title = (c.title || '').trim().toLowerCase().replace(/\s+/g, ' ');
  return { id, title };
}

/** Filtert eine Card-Liste auf max. N Treffer und entfernt Duplikate
 *  per ``node_id`` ODER normalisiertem Titel. Reihenfolge bleibt erhalten,
 *  d.h. der ERSTE Treffer mit einem bestimmten Titel gewinnt — meist
 *  ist das der relevanteste (Sortierung kommt aus dem Backend-Re-Rank). */
export function _dedupTake(cards: WloCard[], n: number): WloCard[] {
  const out: WloCard[] = [];
  const seenIds = new Set<string>();
  const seenTitles = new Set<string>();
  for (const c of cards) {
    const k = _dedupKey(c);
    if (k.id && seenIds.has(k.id)) continue;
    if (k.title && seenTitles.has(k.title)) continue;
    if (k.id) seenIds.add(k.id);
    if (k.title) seenTitles.add(k.title);
    out.push(c);
    if (out.length >= n) break;
  }
  return out;
}

/** Liest einen Box-Limit-Wert aus den Display-Rules der Message.
 *  Welle E (2026-05-23): pro Box-Typ (themenseiten/sammlungen/
 *  materialien/webseiten) konfigurierbar via Studio (display-rules.yaml
 *  → groups). Fallback ist die alte Default-3.
 */
export function _groupLimit(msg: ChatMessage, key: string, fallback = 3): number {
  const v = (msg.displayRules as any)?.['groups']?.[key];
  const n = typeof v === 'number' ? v : parseInt(v, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

/** Top N Themenseiten der Bot-Antwort — dedupliziert per node_id +
 *  normalisiertem Titel (siehe ``_dedupTake``). Default kommt aus
 *  display_rules.groups.themenseiten_max. */
export function groupedTopicCards(msg: ChatMessage, n?: number): WloCard[] {
  if (!msg.cards) return [];
  const limit = n ?? _groupLimit(msg, 'themenseiten_max');
  return _dedupTake(msg.cards.filter(c => isThemenseite(c)), limit);
}

/** Top N Sammlungen — dedupliziert per node_id + normalisiertem Titel.
 *  Default aus display_rules.groups.sammlungen_max.
 *
 *  Enthält seit 15.08.2026 AUCH Sammlungen mit kuratierter Themenseite
 *  (`node_type: 'topic_page'`). Die sind fachlich Sammlungen, waren hier
 *  aber nie zu sehen: `_infer_node_type` etikettiert sie um, und jede
 *  Sammlungs-Prüfung verlangte `collection`. Live-Befund „Optik" — von vier
 *  Optik-Sammlungen fehlten genau die zwei mit Themenseite. Sie stehen jetzt
 *  in beiden Kästen, hier mit `collection_link` als Ziel.
 *
 *  Reine Sammlungen zuerst: sie haben NUR diesen Kasten, Themenseiten stehen
 *  ohnehin schon im eigenen. Ohne die Umsortierung würden Themenseiten sie
 *  aus dem Deckel drängen — das Backend liefert sie vorne in der Liste. */
export function groupedCollectionCards(msg: ChatMessage, n?: number): WloCard[] {
  if (!msg.cards) return [];
  const limit = n ?? _groupLimit(msg, 'sammlungen_max');
  const rein = msg.cards.filter(c => isSammlung(c));
  const mitThemenseite = msg.cards.filter(c => isThemenseite(c));
  return _dedupTake([...rein, ...mitThemenseite], limit);
}

/** Anzahl Einzelinhalte (Content-Cards), die per Search-CTA verfügbar
 *  bleiben würden — fürs UI-Label "X Einzelinhalte in der Suche". */
export function groupedContentCardsCount(msg: ChatMessage): number {
  if (!msg.cards) return 0;
  return msg.cards.filter(c => isInhalt(c)).length;
}

/** Einzelinhalte (Materialien) als eigene Gruppen-Box rendern.
 *  Welle E (2026-05-23): Bisher landeten Einzelinhalte fälschlicherweise
 *  in der Webseiten-Inhalte-Box (web_links), obwohl sie eigene OER-
 *  Ressourcen sind. Default aus display_rules.groups.materialien_max. */
export function groupedContentCards(msg: ChatMessage, n?: number): WloCard[] {
  if (!msg.cards) return [];
  const limit = n ?? _groupLimit(msg, 'materialien_max');
  return _dedupTake(msg.cards.filter(c => isInhalt(c)), limit);
}

/** Wählt die "haupt"-relevante MCP-Such-URL aus den Query-Metadata.
 *  Bevorzugt search_wlo_content > search_wlo_collections > erste mit
 *  nicht-leerer search_url. Liefert ``''`` wenn keine vorhanden.
 *
 *  Welle C.5 (2026-05-21): Fallback — wenn KEINE der Metas ein
 *  ``search_url`` mitliefert (kann passieren wenn der Bot nur
 *  ``search_wlo_collections`` / ``search_wlo_topic_pages`` aufgerufen hat
 *  und das MCP für diese Tools die ``searchUrl`` nicht ausspielt), bauen
 *  wir die URL aus ``repository_url`` + ``search_term`` selbst zusammen.
 *  Damit erscheint die Such-CTA auch in Turns ohne Einzelinhalt-Suche.
 *  Reihenfolge (alle bleiben im edu-sharing/openeduhub-Ökosystem —
 *  wirlernenonline.de/?s=… wird NICHT mehr genutzt, der WP-Endpoint
 *  ist instabil und nicht für Such-Targeting gedacht):
 *    1. Erstes ``search_wlo_content``-Meta mit URL
 *    2. Erstes Collections-/Topic-Pages-Meta mit URL
 *    3. Jedes Meta mit nicht-leerem search_url
 *    4. ``repository_url`` aus Metas + ``/components/search?query=<term>``
 *    5. Gar nichts (leerer String → CTA versteckt) */
export function groupedSearchUrl(msg: ChatMessage, ctx: GroupingContext): string {
  const metas = msg.queryMetas || [];
  if (!metas.length) return '';
  const byTool = (t: string) => metas.find(m => m.tool_name === t && m.search_url);
  const direct = (
    byTool('search_wlo_content')?.search_url
    || byTool('search_wlo_collections')?.search_url
    || byTool('search_wlo_topic_pages')?.search_url
    || metas.find(m => m.search_url)?.search_url
    || ''
  );
  if (direct) return ctx.withBsid(direct);
  // ── Fallback-Komposition (nur edu-sharing) ──────────────────
  // Nimm den ersten nicht-leeren search_term aus den Metas (die Tools
  // schreiben den User-Suchbegriff alle gleich rein, search_wlo_content/
  // collections/topic_pages teilen sich das Schema).
  const termMeta = metas.find(m => m.search_term?.trim());
  const term = (termMeta?.search_term || '').trim();
  if (!term) return '';
  const repoMeta = metas.find(m => m.repository_url?.trim());
  const repo = (repoMeta?.repository_url || '').trim().replace(/\/+$/, '');
  if (!repo) {
    // Ohne repository_url kein Fallback — wir leiten NICHT auf
    // wirlernenonline.de/?s=… um (WP wirft 500). Eher CTA verstecken.
    return '';
  }
  const q = encodeURIComponent(term);
  return ctx.withBsid(`${repo}/edu-sharing/components/search?query=${q}`);
}

/** Such-Begriff für das Search-CTA-Label. Falls in den Metas vorhanden,
 *  zeigen wir ihn an ("Alle Treffer zu „Klimawandel" in der Suche"). */
export function groupedSearchTerm(msg: ChatMessage): string {
  const metas = msg.queryMetas || [];
  const m = metas.find(x => x.search_term?.trim());
  return (m?.search_term || '').trim();
}

/** Sichtbarer Bot-Text. Bei aktivem ``inline-result-grouping`` werden
 *  jene Markdown-Bullet-Links aus dem ``content`` rausgestrippt, die
 *  bereits in die separate Webseiten-Inhalte-Box gewandert sind —
 *  sonst sähe der User dieselben Links zweimal (einmal als Bullet
 *  im Text, einmal in der Box). Inline-Links MITTEN im Satz bleiben
 *  unangetastet (die liest der User als Teil des Fließtexts; sie
 *  nochmal in der Box zu zeigen wäre Doppelung, aber sie zu strippen
 *  würde den Satz zerreißen — Bullets sind das eindeutige Signal
 *  für "redundante Aufzählung"). */
export function displayContent(
  msg: ChatMessage,
  inlineResultGrouping: boolean,
  ctx: GroupingContext,
): string {
  const raw = msg.content || '';
  if (!raw) return raw;
  if (!inlineResultGrouping) return raw;
  const promoted = groupedWebLinks(msg, ctx);
  if (!promoted.length) return raw;
  // Promoted-URLs OHNE bsid normalisieren — die Content-Bullets haben
  // die Original-URL (vor _withBsid), Strip-Vergleich muss damit auch
  // bsid-freie und bsid-gesetzte Varianten matchen.
  const stripBsid = (u: string): string => {
    try {
      const x = new URL(u);
      x.searchParams.delete('bsid');
      return x.toString().replace(/\?$/, '');
    } catch { return u; }
  };
  const promotedUrls = new Set(promoted.map(l => stripBsid(l.url)));
  const lines = raw.split('\n');
  // Match nur ganze Bullet-Zeilen — die sind die typische LLM-Output-
  // Form für Quellen-Aufzählung. Inline-Links wie "Schau dir [Faq](…) an"
  // bleiben.
  // Bullet (-, *, +, typografisch) ODER Numbering (1., 1)) am Zeilenanfang,
  // optional Bold/Italic/Quote um den Link, optional Trailing-Punctuation.
  // Parallel zum Backend-Pattern (chat.py:bullet_link_re) — Sicherheitsnetz
  // für alte gespeicherte Messages aus der Zeit vor dem Backend-Fix sowie
  // für LLM-Varianten, die das Backend ausnahmsweise durchlässt.
  const bulletWithLinkRe = /^\s*(?:[-*+•◦▪·‣⁃►▶]|\d+[.)])\s+(?:\*{0,2}|_{0,2}|["'])?\[[^\]\n]+\]\(\s*<?(https?:\/\/[^\s)>]+)>?\s*\)(?:\*{0,2}|_{0,2}|["'])?\s*[.,;:!?]?\s*$/;
  // HTML-Variante: ``- <a href="…">Label</a>`` (auch mit Bold-Wrappern).
  const bulletHtmlLinkRe = /^\s*(?:[-*+•◦▪·‣⁃►▶]|\d+[.)])\s+(?:\*{0,2}|_{0,2})?<a\s+[^>]*?href\s*=\s*["'](https?:\/\/[^"']+)["'][^>]*>[^<]+<\/a>(?:\*{0,2}|_{0,2})?\s*[.,;:!?]?\s*$/i;
  const out: string[] = [];
  for (const line of lines) {
    const m = line.match(bulletWithLinkRe);
    if (m && promotedUrls.has(stripBsid(m[1]))) continue;
    const h = line.match(bulletHtmlLinkRe);
    if (h && promotedUrls.has(stripBsid(h[1]))) continue;
    out.push(line);
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

/** Web-Links für die ``Webseiten-Inhalte``-Box. Bevorzugt das strukturierte
 *  Feld ``msg.webLinks`` (vom Backend per ``_extract_web_links_from_text``
 *  rausgezogen — der saubere Pfad). Fallback: Markdown-Link-Regex auf
 *  ``msg.content`` für alte gespeicherte Messages aus der Zeit vor dem
 *  strukturierten Feld. ``?bsid=`` wird auf Trusted-Hosts angehängt. */
export function groupedWebLinks(
  msg: ChatMessage,
  ctx: GroupingContext,
  n?: number,
): Array<{ title: string; url: string }> {
  // Type-Focus-Antworten (Material-Typ-Anfrage „nur Videos / hast du
  // Arbeitsblätter / …") rendern NIEMALS eine Webseiten-Inhalte-Box —
  // der Antwortmodus ist „Klick auf die Such-CTA", alles andere
  // verwirrt. Zwei Detection-Pfade:
  //   1. Backend-Marker ``debug._type_focus`` (auf neuen Antworten +
  //      via api.service.ts auch beim Restore mitgereicht)
  //   2. Content-Pattern-Match (defensiv für alte gespeicherte Messages
  //      die noch keinen Marker haben).
  if ((msg.debug as any)?._type_focus) return [];
  const _tfPattern = /^\s*Für\s+\S.*\bschau\s+in\s+die\s+Suche\s+unten\b/i;
  if (_tfPattern.test(msg.content || '')) return [];
  // Welle E (2026-05-23) — Limit aus display_rules.groups.webseiten_max
  const limit = n ?? _groupLimit(msg, 'webseiten_max');
  // ── Primärpfad: strukturiertes Backend-Feld ─────────────────
  if (Array.isArray(msg.webLinks) && msg.webLinks.length > 0) {
    return msg.webLinks
      .slice(0, limit)
      .map(l => ({ title: l.title, url: ctx.withBsid(l.url) }));
  }
  // ── Fallback: ChatMessage hat möglicherweise webLinks im debug-Feld
  // (kommt aus altem ``GET /messages``-Restore via ``_web_links``-Key) ──
  const debugLinks = (msg.debug as any)?._web_links;
  if (Array.isArray(debugLinks) && debugLinks.length > 0) {
    return debugLinks
      .filter((l: any) => l && l.title && l.url)
      .slice(0, limit)
      .map((l: any) => ({ title: String(l.title), url: ctx.withBsid(String(l.url)) }));
  }
  // ── Letzter Fallback: Regex auf Content ─────────────────────
  // Greift nur bei alten gespeicherten Messages oder bei custom Backends
  // die ``web_links`` noch nicht implementiert haben. Card-URLs werden
  // ausgeschlossen damit nichts doppelt erscheint.
  const content = msg.content || '';
  if (!content) return [];
  const cardUrls = new Set<string>();
  (msg.cards || []).forEach(c => {
    const u = (c.link || c.guide_url || c.wlo_url || c.url || '').trim();
    if (u) cardUrls.add(u);
    (c.topic_pages || []).forEach(tp => {
      if (tp?.url) cardUrls.add(tp.url);
    });
  });
  const re = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  const seen = new Set<string>();
  const out: Array<{ title: string; url: string }> = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    const label = m[1].trim();
    const url = m[2].trim();
    if (!label || !url) continue;
    if (seen.has(url) || cardUrls.has(url)) continue;
    seen.add(url);
    out.push({ title: label, url: ctx.withBsid(url) });
    if (out.length >= limit) break;
  }
  return out;
}

/** Title-Tooltip für ein Result-Group-Item bauen.
 *
 *  - Label (Card-Titel oder Link-Titel) als Basis,
 *  - bei externem/nicht-vertrauenswürdigem Host wird die Warnung
 *    ``"Achtung! Externe URL."`` mit `` — `` angehängt.
 *  - Wenn weder Label noch Warnung vorhanden ist, ``null``-Rückgabe
 *    sorgt dafür, dass Angular das ``title``-Attribut komplett weglässt
 *    (statt literal ``"null"`` ins DOM zu schreiben).
 *
 *  Verwendet vom Template für Themenseiten-/Sammlungen-/Webseiten-Boxen
 *  und für die Search-CTA. Ersetzt den vorherigen
 *  ``externalLinkWarning(url) || null``-Ausdruck, der bei trusted Hosts
 *  ``"null"`` als String anzeigte. */
export function itemTooltip(
  label: string | undefined | null,
  url: string | undefined | null,
  ctx: GroupingContext,
): string | null {
  const lbl = (label || '').trim();
  const warn = url ? (ctx.externalLinkWarning(url) || '') : '';
  if (lbl && warn) return `${lbl} — ${warn}`;
  if (lbl) return lbl;
  if (warn) return warn;
  return null;
}

/** Tooltip (title-Attribut) für Karten-Links: „Titel (Typ)". Der Typ ist
 *  der konkrete Inhaltstyp bei Einzelmaterialien (z.B. „Video",
 *  „Arbeitsblatt"), „Sammlung" bei Sammlungen, „Themenseite" bei
 *  Themenseiten — geliefert von getContentTypeLabel(). Plus ggf.
 *  Extern-Warnung (wie itemTooltip).
 *
 *  `typeLabel` überschreibt den Typ. Gebraucht im Sammlungen-Kasten: dort
 *  steht dieselbe Karte, die oben als Themenseite erscheint — mit dem
 *  Themenseiten-Label wäre sie im falschen Kasten beschriftet. */
export function cardTooltip(
  card: WloCard | null | undefined,
  url: string | null | undefined,
  ctx: GroupingContext,
  typeLabel?: string,
): string | null {
  if (!card) return null;
  const title = (card.title || '').trim();
  const type = typeLabel ?? getContentTypeLabel(card, ctx.t);
  const label = title && type ? `${title} (${type})` : (title || type);
  // ``ctx.withBsid(getCardPrimaryUrl(card))`` ≙ ``ChatComponent.cardUrl(card)``.
  return itemTooltip(label, url ?? ctx.withBsid(getCardPrimaryUrl(card)), ctx);
}

/** Tooltip-Builder für die Search-CTA-Box im Result-Grouping-Modus.
 *  Baut den String ``Alle Treffer in der Suche anzeigen zu „<term>"`` plus
 *  ggf. Extern-Warnung. Im Template aufrufen statt das umständliche
 *  Inline-Escaping mit ``\"`` zu hantieren.
 *
 *  C1-b3: zwei vollständige Sätze im Katalog statt eines Präfixes mit
 *  angeklebtem Zusatz — eine andere Sprache stellt den Suchbegriff womöglich
 *  voran, dort ginge Zusammenkleben schief. */
export function searchCtaTooltip(msg: ChatMessage, ctx: GroupingContext): string | null {
  const term = groupedSearchTerm(msg);
  const base = term
    ? ctx.t('groups.ctaTooltip.withTerm', { term })
    : ctx.t('groups.ctaTooltip.all');
  return itemTooltip(base, groupedSearchUrl(msg, ctx), ctx);
}

/** Tour-Antworten (``debug.pattern`` = „TOUR:…") sind bewusst rein
 *  textbasiert: kuratierte Inline-Links (Angebote/Sublinks/Kontakt) +
 *  ``__guide__``-Nav-Buttons. Sie tragen KEINE RAG-``web_links``. Die
 *  Result-Group-Boxen würden via Content-Scrape-Fallback nur die Tour-
 *  eigenen Links ein zweites Mal in die „Webseiten-Inhalte"-Box spiegeln
 *  → Dopplung. Daher während der Tour komplett unterdrücken. */
export function isTourMessage(msg: ChatMessage): boolean {
  const p = (msg?.debug as any)?.pattern;
  return typeof p === 'string' && p.startsWith('TOUR:');
}

/** True wenn die Gruppierungs-Anzeige für diese Message überhaupt etwas
 *  Sichtbares enthält (Themenseiten / Sammlungen / Web-Links / Search-CTA).
 *  Verhindert leere Wrapper bei Antworten ohne Suche und ohne RAG-Links.
 *
 *  Welle C.5+ (2026-05-22): Type-Focus-Antworten („Für Videos zu …")
 *  haben oft NUR die Such-CTA — keine Cards, keine Web-Links, weil die
 *  Box-Anzeige bewusst minimal sein soll. ``groupedSearchUrl`` ist dann
 *  unser einziger sichtbarer Anker und muss als Trigger zählen.
 */
export function hasGroupedResults(msg: ChatMessage, ctx: GroupingContext): boolean {
  if (isTourMessage(msg)) return false;
  const hasCards = !!(msg.cards && msg.cards.length);
  const hasWebLinks = groupedWebLinks(msg, ctx).length > 0;
  const hasSearchCta = !!groupedSearchUrl(msg, ctx);
  if (!hasCards && !hasWebLinks && !hasSearchCta) return false;
  return (
    (hasCards && (groupedTopicCards(msg).length > 0
                  || groupedCollectionCards(msg).length > 0
                  || groupedContentCards(msg).length > 0
                  || hasSearchCta))
    || hasWebLinks
    || hasSearchCta
  );
}
