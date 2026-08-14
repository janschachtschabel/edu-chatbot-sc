/**
 * Tab-Adresse und Formular → das Objekt, das an `chat.replaceContext()` geht.
 *
 * **Warum hier nachgebaut und nicht importiert.** Das Widget hat dieselbe
 * Erkennung eingebaut (`ui/src/stream/chat-api.ts`). Sie hier zu importieren
 * hieße, das Beispiel an den Bauplan des Repositoriums zu ketten — dann wäre es
 * kein Beispiel mehr, sondern ein zweites Frontend. Der Preis ist Doppelung von
 * sechs Mustern; er ist bezahlt, weil dieser Ordner ohne `npm install` läuft.
 *
 * Geprüft mit `node scripts/check-context.mjs` — dort steht auch, warum die
 * eigene `chrome-extension://`-Adresse nichts beitragen darf.
 */

/** Die Arten, die die Steuerleiste anbietet. `auto` heißt „aus der Adresse". */
export const ARTEN = ['collection', 'topic', 'content', 'search', 'none'];

/**
 * Was die Adresse allein hergibt. `{}` wenn nichts — und das ist der Normalfall
 * auf jeder Seite, die keine WLO-Seite ist.
 *
 * Nur `http`/`https`: die Seitenleiste selbst läuft unter
 * `chrome-extension://<id>`, und daraus einen „Host" zu machen war genau der
 * Befund, der 2026-08-14 den Satz „das gehört nicht zu WLO" erzeugt hat.
 */
export function ausUrl(href) {
  let url;
  try {
    url = new URL(String(href || ''));
  } catch {
    return {};
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return {};

  const ctx = {};
  const p = url.searchParams;
  const pfad = url.pathname;

  // Anfrage-Parameter zuerst: sie sind die ausdrückliche Angabe der Seite und
  // schlagen deshalb, was im Pfad steht.
  if (p.get('collection')) { ctx.page_kind = 'collection'; ctx.collection_id = p.get('collection'); }
  if (p.get('node')) { ctx.page_kind = 'content'; ctx.node_id = p.get('node'); }
  if (p.get('q')) { ctx.page_kind = 'search'; ctx.search_query = p.get('q'); }

  const sammlung = pfad.match(/\/sammlung\/([^/?#]+)/);
  if (sammlung && !ctx.collection_id) {
    ctx.page_kind = 'collection';
    ctx.collection_id = sammlung[1];
  }

  const material = pfad.match(/\/material\/([^/?#]+)/);
  const render = pfad.match(/\/components\/render\/([a-f0-9-]{8,})/i);
  const knoten = material || render;
  if (knoten && !ctx.node_id) {
    ctx.page_kind = 'content';
    ctx.node_id = knoten[1];
  }

  // Die ART nur setzen, wenn kein Parameter sie schon bestimmt hat — sonst
  // schlüge der Pfad den Parameter, entgegen der Regel oben. Die BEZEICHNER
  // aus dem Pfad bleiben in jedem Fall: sie widersprechen dem Parameter nicht,
  // sie ergänzen ihn (`?q=…` auf einer Fachportal-Seite ist eine Suche IM
  // Fachportal, und beides gehört in den Kontext).
  const themenseite = pfad.match(/\/themenseite\/([^/?#]+)/);
  if (themenseite) {
    if (!ctx.page_kind) ctx.page_kind = 'topic';
    ctx.topic_page_slug = themenseite[1];
  }
  const fachportal = pfad.match(/\/fachportal\/([^/?#]+)(?:\/([^/?#]+))?/);
  if (fachportal) {
    if (!ctx.page_kind) ctx.page_kind = 'topic';
    ctx.subject_slug = fachportal[1];
    if (fachportal[2]) ctx.topic_page_slug = fachportal[2];
  }

  return ctx;
}

/** Gesetzte, nicht-leere Zeichenkette — oder nichts. */
function wenn(ziel, schluessel, wert) {
  const s = String(wert ?? '').trim();
  if (s) ziel[schluessel] = s;
}

/**
 * Der Kontext für den nächsten Zug. Drei Betriebsarten, die die Steuerleiste
 * anbietet:
 *
 * * `aus`     — gar kein Kontext. Der Bot weiß nichts über die Seite; das ist
 *               die ehrliche Vergleichsgröße, wenn man wissen will, was der
 *               Kontext eigentlich beiträgt.
 * * `auto`    — aus der Adresse des Tabs (plus Titel).
 * * `manuell` — nur die getippten Felder. Der Tab bleibt ausdrücklich außen
 *               vor, sonst wüsste niemand, welche der beiden Quellen gewonnen
 *               hat.
 *
 * Der Seitentext gilt in `auto` und `manuell`: er beschreibt, was zu sehen ist,
 * nicht woher der Kontext kommt.
 */
export function baueKontext(f = {}) {
  const modus = f.modus || 'auto';
  if (modus === 'aus') return {};

  let ctx;
  if (modus === 'manuell') {
    const art = f.art || 'none';
    ctx = art === 'none' ? {} : { page_kind: art };
    if (art === 'collection') wenn(ctx, 'collection_id', f.collectionId);
    if (art === 'content') wenn(ctx, 'node_id', f.nodeId);
    if (art === 'search') wenn(ctx, 'search_query', f.suche);
    if (art === 'topic') {
      wenn(ctx, 'topic_page_slug', f.topicSlug);
      wenn(ctx, 'collection_id', f.collectionId);
    }
  } else {
    ctx = ausUrl(f.tabUrl);
    wenn(ctx, 'document_title', f.tabTitel);
  }

  wenn(ctx, 'page_text', f.seitentext);
  return ctx;
}
