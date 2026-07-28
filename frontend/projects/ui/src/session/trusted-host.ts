/**
 * Trusted-host matching for the widget (§7 `ui/session`). Pure module functions
 * with an explicit hosts parameter — verbatim port of ALT
 * `services/trusted-host.service.ts`.
 *
 * V5 (plan): the NEU widget uses ONE canonical trusted list, built by
 * {@link buildTrustedDomains} (core WLO domains + backend + host attribute).
 * This unifies ALT's asymmetry, where the Chat side prepended
 * `CORE_TRUSTED_DOMAINS` while the Widget side matched the backend+attribute
 * list only. The verbatim matcher ({@link isTrustedHost}) and the parse/merge
 * helpers are unchanged and stay list-parameterised; only the list-building
 * caller is unified.
 *
 * The DOM click-interceptor + bot-`navigate` guard (ALT `widget/link-handoff.ts`,
 * `maybeRewriteOutgoingLink` / `resolveGuideNavUrl`) stay with the widget shell
 * (task 8-4) — they need element/event context. Behaviour pinned by
 * trusted-host.spec.ts. No logic change to ported bodies.
 */

/** Kern-WLO-Domains, die IMMER als vertrauenswürdig gelten — unabhängig davon,
 *  ob die dynamische Trusted-Liste (vom Backend via guide-mode-Config bzw. dem
 *  ``trusted-domains``-Attribut) zum Render-Zeitpunkt schon geladen ist.
 *  Verhindert, dass „Achtung! Externe URL." fälschlich bei WLO-Repo-/
 *  Themenseiten-Links erscheint (alle auf ``*.openeduhub.net``), wenn die
 *  Backend-Liste noch nicht angekommen ist. Die dynamische Liste ergänzt
 *  zusätzliche Hosts (Dev, localhost, *.nip.io …) on top. */
export const CORE_TRUSTED_DOMAINS: readonly string[] = [
  'openeduhub.net', 'wirlernenonline.de', 'openeduhub.de', 'wissenlebtonline.de',
];

/** Gültige BadBoerdi-Session-ID (``bb-`` + 32–40 Hex/Bindestrich-Zeichen).
 *  Nur solche Sessions dürfen als ``?bsid=`` in URLs wandern. */
const BSID_SESSION_RE = /^bb-[0-9a-f-]{32,40}$/i;

/** True wenn ``host`` zur Domain-Liste passt — exakter Match ODER Subdomain
 *  (Eintrag ``openeduhub.net`` matched alle ``*.openeduhub.net``).
 *  ``*.example.com`` und ``example.com`` sind gleichwertig: ``*.`` wird
 *  gestrippt, der ``endsWith('.X')``-Check deckt Subdomains automatisch ab.
 *  Leere Liste → false → alle Hosts gelten als extern. */
export function isTrustedHost(host: string, trustedDomains: readonly string[]): boolean {
  const h = (host || '').toLowerCase();
  if (!h) return false;
  for (const t of trustedDomains) {
    const tn = (t || '').toLowerCase().replace(/^\*\./, '');
    if (!tn) continue;
    if (h === tn || h.endsWith('.' + tn)) return true;
  }
  return false;
}

/** Widget-seitige Eintrags-Normalisierung (HTML-Attribut + Backend-Liste):
 *  trim, lowercase, ``https?://``-Präfix strippen, ``*.`` strippen
 *  (Matcher behandelt Subdomains via endsWith), Pfad abschneiden. */
export function normalizeTrustedDomain(input: string): string {
  return (input || '')
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/^\*\./, '')   // *.example.com → example.com (matcher behandelt Subdomains via endsWith)
      .split('/')[0];
}

/** Merge der beiden Trusted-Quellen (extrahiert aus ALT
 *  ``WidgetComponent._parsedTrustedDomains``).
 *
 *  Backend zuerst (vertrauenswürdige Quelle); das HTML-Attribut ergänzt
 *  additiv für Dev-Hosts (``localhost``, eigene Testdomains), kann
 *  Backend-Einträge aber nicht *entfernen* — das verhindert, dass ein
 *  Stored-XSS auf einer Host-Seite die Backend-Allow-Liste umgehen
 *  könnte (Defense-in-Depth). Duplikate werden übersprungen. */
export function mergeTrustedDomains(
  backendDomains: readonly string[],
  attrValue: string,
): string[] {
  const fromAttr = (attrValue || '')
    .split(/[,\s]+/)
    .map(s => normalizeTrustedDomain(s))
    .filter(s => s.length > 0);
  const seen = new Set<string>();
  const merged: string[] = [];
  for (const list of [backendDomains, fromAttr]) {
    for (const d of list) {
      if (d && !seen.has(d)) {
        seen.add(d);
        merged.push(d);
      }
    }
  }
  return merged;
}

/** V5 (plan): the single canonical trusted list for the whole widget. The core
 *  WLO domains are always trusted, then the backend (guide-mode) list, then the
 *  host ``trusted-domains`` attribute (additive — it can add Dev hosts but not
 *  remove backend entries). Entries are normalised and deduped. Replaces ALT's
 *  Chat-prepends-core vs Widget-merge-only split (see module docstring). */
export function buildTrustedDomains(
  backendDomains: readonly string[],
  attrValue: string,
): string[] {
  const base = [...CORE_TRUSTED_DOMAINS, ...backendDomains]
    .map(d => normalizeTrustedDomain(d))
    .filter(d => d.length > 0);
  return mergeTrustedDomains(base, attrValue);
}

/** Tooltip-Text für Card-Links und Themenseiten-Buttons, falls die
 *  Ziel-URL auf einen Host außerhalb der Trusted-Liste zeigt (öffnet
 *  dann in neuem Tab — siehe HTML target="_blank"). Empty-Return =
 *  kein Warntooltip nötig. Wird auch genutzt für Topic-Page-Links. */
export function externalLinkWarning(
  url: string | null | undefined,
  trustedDomains: readonly string[],
): string {
  const raw = (url || '').trim();
  if (!raw) return '';
  let host = '';
  try {
    host = new URL(raw, window.location.href).hostname.toLowerCase();
  } catch { return ''; }
  if (!host) return '';
  if (host === window.location.hostname.toLowerCase()) return '';
  if (isTrustedHost(host, trustedDomains)) return '';
  return 'Achtung! Externe URL.';
}

/** Hängt ``?bsid=<sessionId>`` an URLs zu Trusted-Hosts an, damit:
 *   - Right-Click → "Link-Adresse kopieren" die fertige URL liefert
 *   - Middle-Click / Ctrl-Click den Session-Param direkt mitnimmt
 *   - Screen-Reader und User-Skripte die korrekte URL sehen
 *  Non-trusted Hosts und Mailto/Tel/etc. bleiben unangetastet.
 *
 *  Konsequent (Welle E): bsid wird AUCH bei same-origin angehängt — das
 *  Widget-Auto-Open und die Tour-Fortsetzung keyen auf ``?bsid=``, so „folgt"
 *  der offene Chat dem Nutzer auch bei seiten-interner Navigation. Die bsid
 *  wird beim Laden in ``resolvePersistedSessionId`` sofort wieder aus der URL
 *  gestrippt (history.replaceState) → keine Bookmark-/Referer-Leaks. */
export function withBsid(
  url: string | null | undefined,
  sessionId: string,
  trustedDomains: readonly string[],
): string {
  const raw = (url || '').trim();
  if (!raw) return '';
  if (!sessionId) return raw;
  if (!BSID_SESSION_RE.test(sessionId)) return raw;
  let target: URL;
  try {
    target = new URL(raw, window.location.href);
  } catch { return raw; }
  if (target.protocol !== 'http:' && target.protocol !== 'https:') return raw;
  // Trusted? Sonst kein bsid (keine Daten-Leakage an unbekannte Hosts).
  if (!isTrustedHost(target.hostname.toLowerCase(), trustedDomains)) return raw;
  // Schon vorhanden? Nicht doppelt.
  if (target.searchParams.has('bsid')) return raw;
  target.searchParams.set('bsid', sessionId);
  return target.toString();
}
