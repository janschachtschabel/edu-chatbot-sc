/**
 * Guide-Mode-Config — pure Parsing-/Mapping-Helfer für die Antwort von
 * ``GET /api/config/guide-mode``, plus die beiden Header-Nav-Helfer
 * (Icon-Lookup, bsid-Anreicherung).
 *
 * Verbatim-Port von ALT `widget/guide-mode-config.ts`. Fetch + Signal-Schreiben
 * liegen daneben in `guide-boot.ts`; hier lebt nur die deterministische
 * Abbildung Response-JSON → typisierte Werte. Felder, die in der Response
 * fehlen oder falsch typisiert sind, kommen als ``null`` zurück, damit der
 * Aufrufer die zugehörigen Signals unangetastet lässt (IST-Verhalten: nur
 * vorhandene Config überschreibt Defaults).
 */
import { ICONS } from '../icons/icons';
import { isValidSessionId } from '../session/session-id';
import { isTrustedHost, normalizeTrustedDomain } from '../session/trusted-host';

/** Optionaler Kopfzeilen-Nav-Button (aus 01-base/header-nav.yaml, vom Backend
 *  über /api/config/guide-mode → ``header_nav`` geliefert). */
export interface HeaderNavButton {
  id: string;
  label: string;
  /** C1-g1b: optionale englische Beschriftung. Leer heisst „nicht gepflegt" —
   *  dann zeigt `pickLocalized` die deutsche. */
  label_en: string;
  icon: string;
  url: string;
  new_tab: boolean;
}

/** Ergebnis von :func:`parseGuideModeConfig` — ``null`` je Feld heißt:
 *  in der Response nicht (valide) vorhanden → Signal nicht anfassen. */
export interface ParsedGuideModeConfig {
  /** ``trusted_domains`` normalisiert + leer-gefiltert. */
  trustedDomains: string[] | null;
  /** ``header_nav`` gefiltert (nur Einträge mit url) + typisiert. */
  headerNav: HeaderNavButton[] | null;
  /** ``welcome.greeting`` — nur non-blank Strings. */
  greeting: string | null;
  /** ``welcome.quick_replies`` — stringifiziert, getrimmt + leer-gefiltert
   *  (C13: getrimmt, damit der Tour-Chip-String-Match greift). */
  startReplies: string[] | null;
  /** ``welcome.tour_reply`` — jeder String zählt, auch ``''``. */
  tourReply: string | null;
  /** Die englischen Fassungen derselben drei Felder (C1-g1a liefert sie
   *  NEBEN den deutschen, weil der Server die Sprache nicht auflöst). */
  greetingEn: string | null;
  startRepliesEn: string[] | null;
  tourReplyEn: string | null;
  /** C5-c2: Herkunft des MCP-Servers (``scheme://host``) für die WLO-Anmeldung.
   *  Ein leerer Wert ist eine AUSSAGE („diese Anlage bietet sie nicht an") und
   *  wird deshalb übernommen; `null` heisst nur „stand nicht in der Antwort". */
  mcpAuthBase: string | null;
}


/** Wählt je Schlüssel zwischen deutscher und englischer Fassung.
 *
 * Ein leeres ``en`` heisst „nicht gepflegt", nicht „leerer Text" — dieselbe
 * Regel wie im Backend-Loader (C1-g1a). Wer sie hier anders auslegte, zeigte
 * einer englischen Oberfläche eine leere Begrüssung statt der deutschen.
 */
export function pickLocalized<T extends string | readonly string[]>(
  de: T, en: T, lang: string,
): T {
  if (lang !== 'en') return de;
  return (typeof en === 'string' ? en.length > 0 : en.length > 0) ? en : de;
}

/** Mappt die rohe ``/api/config/guide-mode``-Antwort auf typisierte Werte. */
export function parseGuideModeConfig(data: any): ParsedGuideModeConfig {
  const out: ParsedGuideModeConfig = {
    trustedDomains: null,
    headerNav: null,
    greeting: null,
    startReplies: null,
    tourReply: null,
    greetingEn: null,
    startRepliesEn: null,
    tourReplyEn: null,
    mcpAuthBase: null,
  };
  // C5-c2: jeder String zählt, auch der leere — er sagt „diese Anlage bietet
  // keine WLO-Anmeldung an". Nur ein fehlendes Feld bleibt `null`.
  if (typeof data?.mcp_auth_base === 'string') {
    out.mcpAuthBase = data.mcp_auth_base.trim();
  }
  if (Array.isArray(data?.trusted_domains)) {
    out.trustedDomains = data.trusted_domains
      .map((d: unknown) => normalizeTrustedDomain(String(d || '')))
      .filter((d: string) => d.length > 0);
  }
  // Optionale Kopfzeilen-Nav-Buttons (Studio: header-nav.yaml).
  if (Array.isArray(data?.header_nav)) {
    out.headerNav = data.header_nav
      .filter((b: any) => b && b.url)
      .map((b: any) => ({
        id: String(b.id || ''),
        label: String(b.label || ''),
        label_en: String(b.label_en || '').trim(),
        icon: String(b.icon || 'explore'),
        url: String(b.url),
        new_tab: !!b.new_tab,
      }));
  }
  // Begrüßung + Start-Quick-Replies (Studio: welcome-config.yaml).
  const w = data?.welcome;
  if (w && typeof w === 'object') {
    if (typeof w.greeting === 'string' && w.greeting.trim()) {
      out.greeting = w.greeting;
    }
    if (Array.isArray(w.quick_replies)) {
      // C13 (Audit 2026-07-09): trimmen UND leer-filtern — ungetrimmte
      // Einträge (" Tour ") ließen den Tour-Chip-String-Match in der
      // Chat-Shell fehlschlagen.
      out.startReplies = w.quick_replies
        .map((r: unknown) => String(r || '').trim())
        .filter(Boolean);
    }
    if (typeof w.tour_reply === 'string') {
      out.tourReply = w.tour_reply;
    }
    // Dieselben drei Regeln fuer die englische Fassung.
    if (typeof w.greeting_en === 'string' && w.greeting_en.trim()) {
      out.greetingEn = w.greeting_en;
    }
    if (Array.isArray(w.quick_replies_en)) {
      out.startRepliesEn = w.quick_replies_en
        .map((r: unknown) => String(r || '').trim())
        .filter(Boolean);
    }
    if (typeof w.tour_reply_en === 'string') {
      out.tourReplyEn = w.tour_reply_en;
    }
  }
  return out;
}

/** Icon-SVG für einen Kopfzeilen-Nav-Button (Name → icons/icons.ts).
 *  Unbekannter Name → Fallback ``explore``. */
export function headerNavIconSvg(icon: string | undefined): string {
  const set = ICONS as Record<string, string>;
  return set[icon ?? ''] || set['explore'] || '';
}

/** Ziel-URL eines Kopfzeilen-Nav-Buttons mit dynamisch angehängter bsid.
 *  Für Trusted-WLO-Hosts (auch same-origin) wird ``?bsid=<sid>`` ergänzt,
 *  damit die Chat-Session auf der Zielseite weiterläuft (sofern das Widget
 *  dort eingebettet ist). Die bsid wird dort beim Laden wieder aus der URL
 *  gestrippt. Untrusted/externe Hosts bleiben unverändert (kein Leak). */
export function headerNavHrefWithBsid(
  b: HeaderNavButton,
  sid: string,
  trustedDomains: readonly string[],
): string {
  const url = (b?.url || '').trim();
  if (!url) return '#';
  if (!isValidSessionId(sid)) return url;
  try {
    const u = new URL(url, window.location.href);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return url;
    if (!isTrustedHost(u.hostname.toLowerCase(), trustedDomains)) return url;
    if (!u.searchParams.has('bsid')) u.searchParams.set('bsid', sid);
    return u.toString();
  } catch {
    return url;
  }
}
