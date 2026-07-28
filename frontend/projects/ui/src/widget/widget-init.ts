/**
 * Widget-Bootstrap-Logik — die beiden Entscheidungen, die vor dem ersten Render
 * fallen: „startet das Panel offen?" und „welcher Seitenkontext gilt?".
 *
 * Verbatim-Port von ALT `widget/widget-init.ts`. `window`/`document`/
 * `localStorage` bleiben bewusst HIER statt hinter einem Seam: die Funktionen
 * sind jsdom-kompatibel und werden in `widget-init.spec.ts` echt dagegen
 * gefahren — ein Seam wäre nur zusätzliche Indirektion ohne Testgewinn.
 */
import { detectPageContext } from '../page-context/page-context-detector';
import { isValidSessionId } from '../session/session-id';

/** Auto-Open-Policy (Welle E): Das Widget öffnet sich von selbst NUR bei
 *  ``?bsid=`` (Cross-TLD-/Tour-Handoff) ODER laufender Web-Tour
 *  (localStorage ``boerdi_tour_active``, von der Chat-Shell gesetzt —
 *  überlebt den WP-Full-Page-Reload; die Tour navigiert same-origin ohne
 *  ?bsid= und würde sonst auf jeder Tour-Seite zuklappen). Die frühere
 *  generische Same-Tab-Persistenz ist bewusst entfernt — ohne bsid und
 *  ohne aktive Tour bleibt das Widget bei Seiten-Navigation geschlossen.
 *  C9 (Audit 2026-07-09): der Auto-Open prüft die Validität der bsid
 *  (``isValidSessionId``) — ein von einer Drittseite angehängtes
 *  ``?bsid=irgendwas`` reißt das Widget nicht mehr auf. */
export function computeInitialExpanded(initialState: 'collapsed' | 'expanded'): boolean {
  let expanded = initialState === 'expanded';

  // Cross-TLD-Handoff: if the URL contains a VALID ?bsid=… the user was
  // navigated here from another page with an active chat session.
  // Auto-open the widget so the conversation continues seamlessly.
  try {
    const sp = new URL(window.location.href).searchParams;
    if (isValidSessionId(sp.get('bsid'))) {
      expanded = true;
    }
  } catch { /* ignore */ }

  try {
    if (localStorage.getItem('boerdi_tour_active') === '1') {
      expanded = true;
    }
  } catch { /* ignore */ }

  return expanded;
}

/** Merge automatic + manual page context.
 *
 *  - ``autoContext`` (strikte ``true``/``'true'``-Koerzierung wie bei den
 *    übrigen Embed-Attributen): URL-Basisdaten (path/query/title/referrer)
 *    plus Page-Context-Detector (WLO-Themenseiten/Sammlungen/Inhalte →
 *    ids + sichtbarer Text; leere Felder werden gedroppt, damit das
 *    Backend keine Leer-Strings als „gesetzt" speichert).
 *  - ``widget: true`` markiert die Session als Widget-getrieben (wichtig
 *    für Dev auf localhost:4200, wo env.page='/' sonst als Host-Seiten-
 *    Integration gälte).
 *  - Manueller ``pageContext`` (JSON-String oder Objekt) merged ZULETZT —
 *    der explizite Override gewinnt (unparsebarer String landet als
 *    ``raw``). */
export function resolveMergedPageContext(
  autoContext: boolean | string,
  pageContext: string | Record<string, unknown>,
): Record<string, unknown> {
  let resolved: Record<string, unknown> = {};

  const auto = autoContext === true || autoContext === 'true';
  if (auto) {
    try {
      const query: Record<string, string> = {};
      const sp = new URL(window.location.href).searchParams;
      sp.forEach((value, key) => { query[key] = value; });
      resolved = {
        path: window.location.pathname,
        query,
        title: document.title,
        referrer: document.referrer || '',
      };
    } catch { /* ignore */ }

    // Page-context-detector: recognise WLO topic / collection / content
    // pages and pull the relevant ids + visible text. Backend's
    // page_context_service resolves these via MCP into structured
    // metadata (title, disciplines, keywords, …). Manual `pageContext`
    // input below still wins — it's the explicit override path.
    try {
      const detected = detectPageContext();
      // Only attach non-empty, scalar fields. Drop undefined keys so
      // the backend doesn't store empty strings as "set" values.
      const cleaned: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(detected)) {
        if (v !== undefined && v !== null && v !== '') cleaned[k] = v;
      }
      resolved = { ...resolved, ...cleaned };
    } catch { /* ignore — never fail widget bootstrap on detection */ }
  }

  // Mark this session as widget-driven so the backend treats it as an
  // embedded widget regardless of env.page.
  resolved = { ...resolved, widget: true };

  if (typeof pageContext === 'string' && pageContext.trim()) {
    try {
      const manual = JSON.parse(pageContext);
      resolved = { ...resolved, ...manual };
    } catch {
      resolved = { ...resolved, raw: pageContext };
    }
  } else if (typeof pageContext === 'object' && pageContext) {
    resolved = { ...resolved, ...pageContext };
  }

  // C10 (Audit 2026-07-09): den Widget-Marker NACH dem manuellen Merge
  // erneut setzen — ein Host-geliefertes ``page-context`` (JSON oder Objekt)
  // darf ``widget`` nicht auf false kippen. Der Marker ist load-bearing für
  // die Backend-Session-Klassifizierung.
  resolved = { ...resolved, widget: true };

  return resolved;
}
