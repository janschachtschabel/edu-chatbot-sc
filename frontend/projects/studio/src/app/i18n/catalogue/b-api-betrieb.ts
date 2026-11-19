/**
 * Die b-api-Betriebsart in der Statusleiste der Übersicht (Plan 2026-11-19, N1,
 * `views/b-api-betrieb.component`). Die Warnungen tragen ihr Wort („Warnung:“,
 * „Hinweis:“) im Satz, damit nicht die Farbe allein sie kennzeichnet.
 */
import type { CataloguePart } from './catalogue-part';

export const B_API_BETRIEB: CataloguePart = {
  de: {
    'overview.bapi.title': 'b-api-Betrieb (diese Backend-Kopie)',
    'overview.bapi.erkannt': 'Betriebsart erkannt: {art}',
    'overview.bapi.art.delegation': 'hinter dem b-api-Proxy (Delegation)',
    'overview.bapi.art.schluessel': 'hinter dem b-api-Proxy (durchgereichter Schlüssel)',
    'overview.bapi.art.direkt': 'direkt (B_API_KEY)',
    'overview.bapi.keiner': 'Seit dem Start noch keine Nutzeranfrage',
    'overview.bapi.wann': 'zuletzt {ago} ({exact})',
    'overview.bapi.modus': 'Modus {modus}',
    'overview.bapi.abgewiesen': 'abgewiesen: {count}',
    'overview.bapi.warnung.forward_ohne_token':
      'Warnung: B_API_KEY_MODE=forward gesetzt, aber kein Token gesehen – Nutzeranfragen werden '
      + 'abgewiesen.',
    'overview.bapi.warnung.zugangsblock_fehlt':
      'Hinweis: Zugangsblock fehlt hinter dem Proxy – allowedRequestHeaders prüfen '
      + '(WLO-Access-Block). Nutzen alle den Chat anonym, ist das normal.',
    'overview.bapi.warnung.andere': 'Hinweis: {code}',
  },
  en: {
    'overview.bapi.title': 'b-api operation (this backend instance)',
    'overview.bapi.erkannt': 'Mode detected: {art}',
    'overview.bapi.art.delegation': 'behind the b-api proxy (delegation)',
    'overview.bapi.art.schluessel': 'behind the b-api proxy (forwarded key)',
    'overview.bapi.art.direkt': 'direct (B_API_KEY)',
    'overview.bapi.keiner': 'No user request since start',
    'overview.bapi.wann': 'last {ago} ({exact})',
    'overview.bapi.modus': 'Mode {modus}',
    'overview.bapi.abgewiesen': 'rejected: {count}',
    'overview.bapi.warnung.forward_ohne_token':
      'Warning: B_API_KEY_MODE=forward is set, but no token has been seen – user requests are '
      + 'being rejected.',
    'overview.bapi.warnung.zugangsblock_fehlt':
      'Note: access block missing behind the proxy – check allowedRequestHeaders '
      + '(WLO-Access-Block). If everyone uses the chat anonymously, this is normal.',
    'overview.bapi.warnung.andere': 'Note: {code}',
  },
};
