/**
 * Feldtexte (ST-1) der Seite „Datenschutz“: Bereiche `01-base/privacy-config` und
 * `01-base/quality-log-config`.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`. Hier besonders genau, weil es um
 * Speicherung geht — und nicht jeder Schalter wirkt: `logging.safety` setzt der
 * Lader fest auf an, und die drei `alerts`-Schwellen liest niemand. Die beiden
 * `retention_days` (Gesprächsverläufe, Qualitätsprotokoll) setzt seit Paket 8
 * `services/aufbewahrung.py` durch. Wirksam
 * sind außerdem `logging.messages` (in `services/db_sessions.save_message`,
 * durch das jede Chatnachricht geht),
 * `logging.memory` (nur am Endpunkt `POST /api/sessions/{id}/memory`),
 * `logging.quality` und `quality-log-config.logging.enabled` (beide in
 * `services/turn_quality.py`).
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_DATENSCHUTZ: CataloguePart = {
  de: {
    'feld.PrivacyConfigArea.logging.label': 'Speicherung',
    'feld.PrivacyConfigArea.logging.hint':
      'Was der Chatbot zu Sitzungen speichern darf. Abschalten lassen sich hier '
      + 'Chatnachrichten, Sitzungsgedächtnis und Qualitätsprotokoll.',
    'feld.PrivacyLoggingBlock.messages.label': 'Chatnachrichten',
    'feld.PrivacyLoggingBlock.messages.hint':
      'Aus: Nachrichten von Person und Bot werden nicht gespeichert, auch nicht Karten und '
      + 'Debug-Daten; ein Neuladen stellt das Gespräch dann nicht wieder her. Qualitäts- und '
      + 'Sicherheitsprotokoll halten weiter die ersten 500 Zeichen einer Nachricht fest — '
      + 'dafür gelten ihre eigenen Schalter.',
    'feld.PrivacyLoggingBlock.memory.label': 'Sitzungsgedächtnis',
    'feld.PrivacyLoggingBlock.memory.hint':
      'Aus: Gedächtnis-Einträge, die über die Sitzungs-Schnittstelle kommen, werden verworfen '
      + 'statt gespeichert. Der Chat selbst legt derzeit keine an.',
    'feld.PrivacyLoggingBlock.quality.label': 'Qualitätsprotokoll',
    'feld.PrivacyLoggingBlock.quality.hint':
      'Aus: kein Auswertungseintrag je Chat-Zug, gleich was unter „Qualitäts-Logging“ steht. '
      + 'An: dort entscheidet „Protokoll aktiv“.',
    'feld.PrivacyLoggingBlock.safety.label': 'Sicherheitsprotokoll',
    'feld.PrivacyLoggingBlock.safety.hint':
      'Immer an: der Code setzt den Wert fest, das Sicherheitsprotokoll lässt sich hier nicht '
      + 'abschalten. Seinen Umfang regelt „Sicherheit“ unter „Identität & Schutz“.',
    'feld.PrivacyLoggingBlock.retention_days.label': 'Aufbewahrung der Gesprächsverläufe (Tage)',
    'feld.PrivacyLoggingBlock.retention_days.hint':
      'Ältere Chatnachrichten und Gedächtnis-Einträge löscht das Backend alle sechs Stunden '
      + 'endgültig; 0 = unbegrenzt aufbewahren. Die Sitzungen und ihre Verbrauchszahlen '
      + 'bleiben. Was gerade fällig ist, zeigt „Aufbewahrung“ auf dieser Seite.',
    'feld.QualityLogConfigArea.logging.label': 'Protokollierung',
    'feld.QualityLogConfigArea.logging.hint':
      'Ob je Chat-Zug ein Auswertungseintrag gespeichert wird; daraus speist sich die '
      + 'Analyse.',
    'feld.QualityLoggingBlock.enabled.label': 'Protokoll aktiv',
    'feld.QualityLoggingBlock.enabled.hint':
      'Speichert je Chat-Zug Muster, Intent, Persona, Werkzeuge, Debug-Daten und die ersten '
      + '500 Zeichen der Nachricht. Wirkt nur, wenn unter „Datenschutz“ auch '
      + '„Qualitätsprotokoll“ an ist.',
    'feld.QualityLoggingBlock.retention_days.label': 'Aufbewahrung (Tage)',
    'feld.QualityLoggingBlock.retention_days.hint':
      'Ältere Einträge löscht das Backend alle sechs Stunden endgültig; 0 = unbegrenzt '
      + 'aufbewahren. Was gerade fällig ist, zeigt „Aufbewahrung“ auf dieser Seite.',
    'feld.QualityLogConfigArea.alerts.label': 'Warnschwellen',
    'feld.QualityLogConfigArea.alerts.hint':
      'Schwellen, ab denen die Auswertung warnen soll. Werden derzeit nicht ausgewertet: kein '
      + 'Code liest sie.',
    'feld.QualityAlertsBlock.tight_race_threshold.label': 'Knappe Musterwahl',
    'feld.QualityAlertsBlock.tight_race_threshold.hint':
      'Gedacht: Abstand der zwei besten Muster-Punktzahlen, unter dem eine Wahl als knapp '
      + 'gilt (etwa 0,02). Wird derzeit nicht ausgewertet.',
    'feld.QualityAlertsBlock.degradation_rate_warn.label': 'Rückfrage-Quote',
    'feld.QualityAlertsBlock.degradation_rate_warn.hint':
      'Gedacht: Anteil der Züge mit Rückfrage wegen fehlender Angaben, ab dem gewarnt wird (0 '
      + 'bis 1, etwa 0,15). Wird derzeit nicht ausgewertet.',
    'feld.QualityAlertsBlock.empty_entity_rate_warn.label': 'Quote ohne Entitäten',
    'feld.QualityAlertsBlock.empty_entity_rate_warn.hint':
      'Gedacht: Anteil der Züge, in denen der Klassifikator keine Angaben (Entitäten) '
      + 'erkennt, ab dem gewarnt wird (0 bis 1, etwa 0,30). Wird derzeit nicht ausgewertet.',
  },
  en: {
    'feld.PrivacyConfigArea.logging.label': 'Storage',
    'feld.PrivacyConfigArea.logging.hint':
      'What the chatbot may store about sessions. Chat messages, session memory and the '
      + 'quality log can be switched off here.',
    'feld.PrivacyLoggingBlock.messages.label': 'Chat messages',
    'feld.PrivacyLoggingBlock.messages.hint':
      'Off: messages from the person and the bot are not stored, nor are cards and debug '
      + 'data; a reload then cannot restore the conversation. The quality and safety logs '
      + 'still keep the first 500 characters of a message — their own switches govern that.',
    'feld.PrivacyLoggingBlock.memory.label': 'Session memory',
    'feld.PrivacyLoggingBlock.memory.hint':
      'Off: memory entries sent through the session interface are discarded instead of '
      + 'stored. The chat itself currently creates none.',
    'feld.PrivacyLoggingBlock.quality.label': 'Quality log',
    'feld.PrivacyLoggingBlock.quality.hint':
      'Off: no analysis entry per chat turn, whatever "Quality logging" says. On: "Log '
      + 'active" there decides.',
    'feld.PrivacyLoggingBlock.safety.label': 'Safety log',
    'feld.PrivacyLoggingBlock.safety.hint':
      'Always on: the code fixes the value, the safety log cannot be switched off here. Its '
      + 'scope is set under "Safety" in "Identity & safeguards".',
    'feld.PrivacyLoggingBlock.retention_days.label': 'Conversation retention (days)',
    'feld.PrivacyLoggingBlock.retention_days.hint':
      'The backend deletes older chat messages and memory entries for good every six hours; '
      + '0 = keep without limit. Sessions and their usage figures stay. What is due right now is '
      + 'shown under “Retention” on this page.',
    'feld.QualityLogConfigArea.logging.label': 'Logging',
    'feld.QualityLogConfigArea.logging.hint':
      'Whether an analysis entry is stored per chat turn; the analysis draws on it.',
    'feld.QualityLoggingBlock.enabled.label': 'Log active',
    'feld.QualityLoggingBlock.enabled.hint':
      'Stores per chat turn the pattern, intent, persona, tools, debug data and the first 500 '
      + 'characters of the message. Only takes effect if "Quality log" is also on under '
      + '"Privacy".',
    'feld.QualityLoggingBlock.retention_days.label': 'Retention (days)',
    'feld.QualityLoggingBlock.retention_days.hint':
      'The backend deletes older entries for good every six hours; 0 = keep without '
      + 'limit. What is due right now is shown under “Retention” on this page.',
    'feld.QualityLogConfigArea.alerts.label': 'Alert thresholds',
    'feld.QualityLogConfigArea.alerts.hint':
      'Thresholds from which the analysis is meant to warn. Currently not evaluated: no code '
      + 'reads them.',
    'feld.QualityAlertsBlock.tight_race_threshold.label': 'Close pattern race',
    'feld.QualityAlertsBlock.tight_race_threshold.hint':
      'Intended: gap between the two best pattern scores below which a choice counts as close '
      + '(such as 0.02). Currently not evaluated.',
    'feld.QualityAlertsBlock.degradation_rate_warn.label': 'Follow-up question rate',
    'feld.QualityAlertsBlock.degradation_rate_warn.hint':
      'Intended: share of turns with a follow-up question about missing details from which to '
      + 'warn (0 to 1, such as 0.15). Currently not evaluated.',
    'feld.QualityAlertsBlock.empty_entity_rate_warn.label': 'Empty entity rate',
    'feld.QualityAlertsBlock.empty_entity_rate_warn.hint':
      'Intended: share of turns in which the classifier extracts no details (entities) from '
      + 'which to warn (0 to 1, such as 0.30). Currently not evaluated.',
  },
};
