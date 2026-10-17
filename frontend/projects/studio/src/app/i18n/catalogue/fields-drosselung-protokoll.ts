/**
 * Feldtexte (ST-1) der Seite „Identität & Schutz“, Bereich `01-base/safety-config`,
 * Teilbäume `rate_limits` (Drosselung, gelesen von `services/rate_limits.py`) und
 * `logging` (Sicherheitsprotokoll, `_log_turn_safety` in `graph/build.py`).
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`. `RateLimitWindow` trägt beide
 * Fenster (je Sitzung, je IP-Adresse), darum gelten seine Texte für beide.
 * `logging.retention_days` setzt seit Paket 8 `services/aufbewahrung.py` durch:
 * alle sechs Stunden ein Lauf, der ältere Einträge löscht.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_DROSSELUNG_PROTOKOLL: CataloguePart = {
  de: {
    'feld.SafetyConfigArea.rate_limits.label': 'Drosselung',
    'feld.SafetyConfigArea.rate_limits.hint':
      'Bremse im Chat: wer je Sitzung oder IP-Adresse zu viele Anfragen stellt, bekommt statt '
      + 'einer Antwort den Hinweistext. Die technische HTTP-Grenze der Anlage zählt '
      + 'unabhängig davon.',
    'feld.RateLimitsBlock.enabled.label': 'Drosselung aktiv',
    'feld.RateLimitsBlock.enabled.hint':
      'Hauptschalter der Drosselung. Aus: keine Limits, gleich was darunter steht. Ohne '
      + 'Eintrag aus.',
    'feld.RateLimitsBlock.per_session.label': 'Je Sitzung',
    'feld.RateLimitsBlock.per_session.hint':
      'Limit je Browser-Sitzung; bremst einzelne Personen, die sehr viele Anfragen stellen.',
    'feld.RateLimitWindow.enabled.label': 'Aktiv',
    'feld.RateLimitWindow.enabled.hint':
      'Schaltet dieses Limit (Sitzung oder IP-Adresse) an oder aus. Ohne Eintrag an.',
    'feld.RateLimitWindow.requests_per_minute.label': 'Anfragen je Minute',
    'feld.RateLimitWindow.requests_per_minute.hint':
      'Höchstzahl der Chat-Anfragen in einem gleitenden Fenster von einer Minute. 0 oder leer '
      + '= unbegrenzt.',
    'feld.RateLimitWindow.requests_per_hour.label': 'Anfragen je Stunde',
    'feld.RateLimitWindow.requests_per_hour.hint':
      'Höchstzahl der Chat-Anfragen in einem gleitenden Fenster von einer Stunde. 0 oder leer '
      + '= unbegrenzt.',
    'feld.RateLimitsBlock.per_ip.label': 'Je IP-Adresse',
    'feld.RateLimitsBlock.per_ip.hint':
      'Limit je IP-Adresse der Verbindung. Großzügig wählen: in Schulen teilen sich oft ganze '
      + 'Räume eine Adresse.',
    'feld.RateLimitsBlock.ip_whitelist.label': 'Ausgenommene IP-Adressen',
    'feld.RateLimitsBlock.ip_whitelist.hint':
      'Adressen, für die das Limit je IP-Adresse nicht gilt, etwa bekannte Schulnetze. Nur '
      + 'einzelne Adressen, keine Bereiche; das Limit je Sitzung gilt weiter.',
    'feld.RateLimitsBlock.blocked_message.label': 'Text bei Drosselung',
    'feld.RateLimitsBlock.blocked_message.hint':
      'Erscheint im Chat statt einer Antwort, wenn ein Limit greift. Leer = „Zu viele '
      + 'Anfragen — bitte kurz warten.“',
    'feld.RateLimitsBlock.blocked_message_en.label': 'Text bei Drosselung (Englisch)',
    'feld.RateLimitsBlock.blocked_message_en.hint':
      'Englische Fassung, gilt bei Sprache Englisch. Leer = der deutsche Text.',
    'feld.SafetyConfigArea.logging.label': 'Sicherheitsprotokoll',
    'feld.SafetyConfigArea.logging.hint':
      'Welche Sicherheitsentscheidungen von Chat-Zügen gespeichert werden; einsehbar unter '
      + '„Safety-Logs“.',
    'feld.SafetyLoggingBlock.enabled.label': 'Protokoll aktiv',
    'feld.SafetyLoggingBlock.enabled.hint':
      'Speichert Sicherheitsentscheidungen von Chat-Zügen: Sitzung, IP-Adresse, Risiko, '
      + 'Gründe und die ersten 500 Zeichen der Nachricht. Drosselungen und gestoppte '
      + 'Direktaktionen landen immer darin.',
    'feld.SafetyLoggingBlock.log_all_turns.label': 'Jeden Zug protokollieren',
    'feld.SafetyLoggingBlock.log_all_turns.hint':
      'An: jeder Chat-Zug kommt ins Sicherheitsprotokoll. Aus: nur Züge mit mittlerem oder '
      + 'hohem Risiko.',
    'feld.SafetyLoggingBlock.retention_days.label': 'Aufbewahrung (Tage)',
    'feld.SafetyLoggingBlock.retention_days.hint':
      'Ältere Einträge löscht das Backend alle sechs Stunden endgültig; 0 = unbegrenzt '
      + 'aufbewahren. Was gerade fällig ist, zeigt „Aufbewahrung“ auf der Seite „Datenschutz“.',
  },
  en: {
    'feld.SafetyConfigArea.rate_limits.label': 'Rate limits',
    'feld.SafetyConfigArea.rate_limits.hint':
      'Brake in the chat: anyone sending too many requests per session or IP address gets the '
      + 'notice text instead of an answer. The technical HTTP limit of the installation '
      + 'counts separately.',
    'feld.RateLimitsBlock.enabled.label': 'Rate limits active',
    'feld.RateLimitsBlock.enabled.hint':
      'Master switch for rate limiting. Off: no limits, whatever is set below. Without an '
      + 'entry, off.',
    'feld.RateLimitsBlock.per_session.label': 'Per session',
    'feld.RateLimitsBlock.per_session.hint':
      'Limit per browser session; slows down individual people who send very many requests.',
    'feld.RateLimitWindow.enabled.label': 'Active',
    'feld.RateLimitWindow.enabled.hint':
      'Switches this limit (session or IP address) on or off. Without an entry, on.',
    'feld.RateLimitWindow.requests_per_minute.label': 'Requests per minute',
    'feld.RateLimitWindow.requests_per_minute.hint':
      'Maximum number of chat requests in a sliding one-minute window. 0 or empty = '
      + 'unlimited.',
    'feld.RateLimitWindow.requests_per_hour.label': 'Requests per hour',
    'feld.RateLimitWindow.requests_per_hour.hint':
      'Maximum number of chat requests in a sliding one-hour window. 0 or empty = unlimited.',
    'feld.RateLimitsBlock.per_ip.label': 'Per IP address',
    'feld.RateLimitsBlock.per_ip.hint':
      'Limit per IP address of the connection. Choose generously: in schools, whole rooms '
      + 'often share one address.',
    'feld.RateLimitsBlock.ip_whitelist.label': 'Exempt IP addresses',
    'feld.RateLimitsBlock.ip_whitelist.hint':
      'Addresses the per-IP limit does not apply to, such as known school networks. Single '
      + 'addresses only, no ranges; the per-session limit still applies.',
    'feld.RateLimitsBlock.blocked_message.label': 'Rate-limit message',
    'feld.RateLimitsBlock.blocked_message.hint':
      'Shown in the chat instead of an answer when a limit applies. Empty = "Zu viele '
      + 'Anfragen — bitte kurz warten." (German).',
    'feld.RateLimitsBlock.blocked_message_en.label': 'Rate-limit message (English)',
    'feld.RateLimitsBlock.blocked_message_en.hint':
      'English version, used when the language is English. Empty = the German text.',
    'feld.SafetyConfigArea.logging.label': 'Safety log',
    'feld.SafetyConfigArea.logging.hint':
      'Which safety decisions of chat turns are stored; viewable under "Safety logs".',
    'feld.SafetyLoggingBlock.enabled.label': 'Log active',
    'feld.SafetyLoggingBlock.enabled.hint':
      'Stores safety decisions of chat turns: session, IP address, risk, reasons and the '
      + 'first 500 characters of the message. Rate-limit hits and stopped direct actions are '
      + 'always logged.',
    'feld.SafetyLoggingBlock.log_all_turns.label': 'Log every turn',
    'feld.SafetyLoggingBlock.log_all_turns.hint':
      'On: every chat turn goes into the safety log. Off: only turns with medium or high '
      + 'risk.',
    'feld.SafetyLoggingBlock.retention_days.label': 'Retention (days)',
    'feld.SafetyLoggingBlock.retention_days.hint':
      'The backend deletes older entries for good every six hours; 0 = keep without '
      + 'limit. What is due right now is shown under “Retention” on the “Privacy” page.',
  },
};
