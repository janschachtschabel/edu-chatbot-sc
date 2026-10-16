/**
 * Feldtexte (ST-1) der Seite „Identität & Schutz“, Bereich `01-base/safety-config`
 * ohne die Teilbäume `rate_limits` und `logging` (die stehen in
 * `fields-drosselung-protokoll.ts`): Sicherheitsstufe, Stufen-Presets, Krisenweg
 * und Eskalation.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`: `feld.<Modell>.<feld>.{label,hint}`.
 * Geprüft gegen `services/safety/service.py`, `services/safety/regex_gate.py` und
 * `services/agent_gate.py`. Ein Feld wertet der Code nicht aus, und der Text sagt
 * das: `double_check` (gelesen, nie genutzt). `confidence_adjustments` und
 * `escalation.provider` sind gestrichen (Paket 7). `extra_crisis_terms`
 * und `extra_pii_terms` prüft das Regex-Gate seit Paket 4 (D8) nach seinen festen
 * Listen (`services/safety/zusatz_begriffe.py`). `escalation.mode` und
 * `escalation.legal_classifier` wirken nur als Rückfall, wenn `security_level`
 * kein Preset findet.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_SICHERHEIT: CataloguePart = {
  de: {
    'feld.SafetyConfigArea.security_level.label': 'Sicherheitsstufe',
    'feld.SafetyConfigArea.security_level.hint':
      'Welches Stufen-Preset gilt, etwa off, regex, standard, strict oder paranoid. Leer '
      + 'heißt standard. Passt kein Preset, gelten Moderation und Rechtsprüfung aus '
      + '„Eskalation“.',
    'feld.SafetyConfigArea.presets.label': 'Stufen-Presets',
    'feld.SafetyConfigArea.presets.hint':
      'Die wählbaren Sicherheitsstufen, je Name eine Zusammenstellung: wann Moderation und '
      + 'Rechtsprüfung laufen, Injection-Prüfung, Schwellenfaktor. Welche gilt, legt '
      + '„Sicherheitsstufe“ fest.',
    'feld.SafetyPreset.moderation.label': 'Moderation',
    'feld.SafetyPreset.moderation.hint':
      'Wann die Moderation die Nachricht prüft: never = nie, smart = nur bei schon erhöhtem '
      + 'Risiko, always = jede Nachricht. Nicht gesetzt (leer oder fehlend) wirkt wie smart. '
      + 'Ohne Zugang der Anlage entfällt sie.',
    'feld.SafetyPreset.legal_classifier.label': 'Rechtsprüfung',
    'feld.SafetyPreset.legal_classifier.hint':
      'Wann ein Sprachmodell die Nachricht auf Strafrecht, Jugendschutz, '
      + 'Persönlichkeitsrechte und Datenschutz prüft; Werte und Rückfall wie bei der '
      + 'Moderation. Kostet je Prüfung Tokens.',
    'feld.SafetyPreset.prompt_injection.label': 'Injection-Prüfung',
    'feld.SafetyPreset.prompt_injection.hint':
      'Prüft jede Nachricht zusätzlich auf Versuche, die Anweisungen des Bots auszuhebeln '
      + '(etwa „ignoriere alle Anweisungen“). Ein Treffer hebt das Risiko auf mittel.',
    'feld.SafetyPreset.legal_trigger_override.label': 'Rechtsprüfung bei Reizwort',
    'feld.SafetyPreset.legal_trigger_override.hint':
      'Steht die Rechtsprüfung auf smart, läuft sie auch bei geringem Risiko, sobald die '
      + 'Nachricht ein Reizwort enthält (etwa Beleidigung, Drohung, Hass).',
    'feld.SafetyPreset.threshold_multiplier.label': 'Schwellenfaktor',
    'feld.SafetyPreset.threshold_multiplier.hint':
      'Faktor auf alle Schwellen von Moderation und Rechtsprüfung. Unter 1 schlägt die '
      + 'Prüfung früher an (0,5 halbiert die Schwellen), über 1 später. Vorgabe 1.',
    'feld.SafetyPreset.double_check.label': 'Doppelte Prüfung',
    'feld.SafetyPreset.double_check.hint':
      'Gedacht für eine zweite Prüfrunde. Wird derzeit nicht ausgewertet: der Code liest den '
      + 'Wert, aber keine Prüfstufe nutzt ihn.',
    'feld.SafetyConfigArea.extra_crisis_terms.label': 'Zusätzliche Krisenbegriffe',
    'feld.SafetyConfigArea.extra_crisis_terms.hint':
      'Weitere Wörter, die als Krisensignal gelten — wie die eingebauten Muster: Es folgt die '
      + 'Schutzantwort, die Materialsuche ist gesperrt. Eingebaut und nicht abschaltbar sind '
      + 'neben Suizid- und Selbstverletzungsbegriffen typische Andeutungen wie „niemand würde '
      + 'mich vermissen“ oder „ich sehe keinen Ausweg mehr“. Ein Begriff trifft ab Wortanfang '
      + '(„klinge“ trifft „klingenscharf“), Groß-/Kleinschreibung egal; höchstens 200 Begriffe '
      + 'zu je 100 Zeichen.',
    'feld.SafetyConfigArea.extra_pii_terms.label': 'Zusätzliche PII-Begriffe',
    'feld.SafetyConfigArea.extra_pii_terms.hint':
      'Weitere Begriffe für persönliche Daten (PII). Ein Treffer sperrt die Volltextsuche, wie '
      + 'die eingebauten Muster. Ein Begriff trifft ab Wortanfang, Groß-/Kleinschreibung egal; '
      + 'höchstens 200 Begriffe zu je 100 Zeichen.',
    'feld.SafetyConfigArea.crisis_blocked_tools.label': 'Gesperrte Werkzeuge bei Krise',
    'feld.SafetyConfigArea.crisis_blocked_tools.hint':
      'Werkzeuge, die gesperrt werden, wenn die Moderation eine harte Kategorie meldet. Der '
      + 'Regex-Filter sperrt bei Krise oder Drohung unabhängig davon fest drei Such- und '
      + 'Sammlungswerkzeuge.',
    'feld.SafetyConfigArea.crisis_pattern.label': 'Krisenmuster',
    'feld.SafetyConfigArea.crisis_pattern.hint':
      'Muster, das antwortet, wenn die Moderation eine harte Kategorie meldet, die keine '
      + 'Drohung ist (etwa Selbstgefährdung). Leer oder fehlend: M01. Regex-Filter: bei Krise '
      + 'fest M01.',
    'feld.SafetyConfigArea.threat_pattern.label': 'Drohungsmuster',
    'feld.SafetyConfigArea.threat_pattern.hint':
      'Muster, das antwortet, wenn die Moderation eine Drohung als harte Kategorie meldet '
      + '(hate/threatening, harassment/threatening). Leer oder fehlend: M02. Regex-Filter: '
      + 'fest M02.',
    'feld.SafetyConfigArea.crisis_message.label': 'Krisenantwort',
    'feld.SafetyConfigArea.crisis_message.hint':
      'Antwort des Agent-Endpunkts (/api/agent) auf eine Krise; der Lauf beginnt dann nicht. '
      + 'Leer = Vorgabe (an Familie oder Ansprechperson der Einrichtung wenden). Der Chat '
      + 'antwortet über das Krisenmuster.',
    'feld.SafetyConfigArea.crisis_message_en.label': 'Krisenantwort (Englisch)',
    'feld.SafetyConfigArea.crisis_message_en.hint':
      'Englische Fassung der Krisenantwort des Agent-Endpunkts, gilt bei Sprache Englisch. '
      + 'Leer = die englische Vorgabe.',
    'feld.SafetyConfigArea.escalation.label': 'Eskalation',
    'feld.SafetyConfigArea.escalation.hint':
      'Schwellen, harte Kategorien und Herabstufung gelten, sobald Moderation oder '
      + 'Rechtsprüfung laufen. Moderation und Rechtsprüfung hier sind nur Rückfall, wenn kein '
      + 'Stufen-Preset passt.',
    'feld.EscalationBlock.mode.label': 'Moderation (Rückfall)',
    'feld.EscalationBlock.mode.hint':
      'Nur wenn die Sicherheitsstufe kein Preset findet: wann die Moderation läuft (off = '
      + 'nie, smart = bei erhöhtem Risiko, always = immer; nicht gesetzt = nie). Mit Preset '
      + 'ohne Wirkung.',
    'feld.EscalationBlock.legal_classifier.label': 'Rechtsprüfung (Rückfall)',
    'feld.EscalationBlock.legal_classifier.hint':
      'Nur wenn die Sicherheitsstufe kein Preset findet: an = Rechtsprüfung bei erhöhtem '
      + 'Risiko oder Reizwort, aus = nie. Ohne Eintrag an. Mit Preset ohne Wirkung.',
    'feld.EscalationBlock.thresholds.label': 'Schwellen je Kategorie',
    'feld.EscalationBlock.thresholds.hint':
      'Ab welchem Wert (0 bis 1) eine Moderationskategorie als getroffen gilt, etwa '
      + 'self_harm: 0,25 oder sexual/minors: 0,2 — Namen wie die Moderation sie meldet, '
      + 'Bindestrich als Unterstrich. Nicht genannte Kategorien: 0,95. Der Schwellenfaktor '
      + 'der Stufe wird darauf angewandt. Gemessen 2026-10-09: Unterricht über Suizid in '
      + 'Literatur und Prävention erreicht bei self_harm bis 0,16 — darunter drohen Fehlalarme; '
      + '0,25 erkennt dieselben Andeutungen wie 0,17.',
    'feld.EscalationBlock.hard_block_categories.label': 'Harte Kategorien',
    'feld.EscalationBlock.hard_block_categories.hint':
      'Moderationskategorien, die bei Treffer sofort als hohes Risiko gelten: das Krisen- '
      + 'oder Drohungsmuster antwortet, die Krisen-Werkzeuge werden gesperrt. Schreibweise '
      + 'wie bei den Schwellen.',
    'feld.EscalationBlock.downgrade_false_positives.label': 'Fehlalarme herabstufen',
    'feld.EscalationBlock.downgrade_false_positives.hint':
      'Senkt ein mittleres Risiko auf gering, wenn die gelaufenen Prüfungen (Moderation, '
      + 'Rechtsprüfung) nichts finden. Nicht bei Krisensignal oder Injection-Verdacht. Ohne '
      + 'Eintrag an.',
  },
  en: {
    'feld.SafetyConfigArea.security_level.label': 'Safety level',
    'feld.SafetyConfigArea.security_level.hint':
      'Which level preset applies, such as off, regex, standard, strict or paranoid. Empty '
      + 'means standard. If no preset matches, moderation and legal check from "Escalation" '
      + 'apply.',
    'feld.SafetyConfigArea.presets.label': 'Level presets',
    'feld.SafetyConfigArea.presets.hint':
      'The selectable safety levels, each a named bundle: when moderation and the legal check '
      + 'run, injection check, threshold factor. "Safety level" decides which one applies.',
    'feld.SafetyPreset.moderation.label': 'Moderation',
    'feld.SafetyPreset.moderation.hint':
      'When moderation checks the message: never, smart = only if the risk is already raised, '
      + 'always = every message. Not set (empty or missing) acts like smart. Skipped if the '
      + 'installation has no access.',
    'feld.SafetyPreset.legal_classifier.label': 'Legal check',
    'feld.SafetyPreset.legal_classifier.hint':
      'When a language model checks the message for criminal law, youth protection, '
      + 'personality rights and data protection; values and fallback as for moderation. Each '
      + 'check costs tokens.',
    'feld.SafetyPreset.prompt_injection.label': 'Injection check',
    'feld.SafetyPreset.prompt_injection.hint':
      'Also checks every message for attempts to override the instructions of the bot (such '
      + 'as "ignore all instructions"). A hit raises the risk to medium.',
    'feld.SafetyPreset.legal_trigger_override.label': 'Trigger-word legal check',
    'feld.SafetyPreset.legal_trigger_override.hint':
      'If the legal check is set to smart, it also runs at low risk as soon as the message '
      + 'contains a trigger word (such as an insult, a threat or hate).',
    'feld.SafetyPreset.threshold_multiplier.label': 'Threshold factor',
    'feld.SafetyPreset.threshold_multiplier.hint':
      'Factor applied to all moderation and legal-check thresholds. Below 1 the check fires '
      + 'earlier (0.5 halves the thresholds), above 1 later. Default 1.',
    'feld.SafetyPreset.double_check.label': 'Double check',
    'feld.SafetyPreset.double_check.hint':
      'Intended for a second round of checks. Currently not evaluated: the code reads the '
      + 'value, but no check stage uses it.',
    'feld.SafetyConfigArea.extra_crisis_terms.label': 'Extra crisis terms',
    'feld.SafetyConfigArea.extra_crisis_terms.hint':
      'Further words that count as a crisis signal — like the built-in patterns: the protective '
      + 'reply follows and material search is blocked. Built in and always on are, besides '
      + 'suicide and self-harm terms, typical hints such as “nobody would miss me” or “I don’t '
      + 'want to be here anymore”. A term matches from the start of a word '
      + '(“blade” matches “bladed”), case-insensitive; at most 200 terms of 100 characters each.',
    'feld.SafetyConfigArea.extra_pii_terms.label': 'Extra PII terms',
    'feld.SafetyConfigArea.extra_pii_terms.hint':
      'Further terms for personal data (PII). A match blocks full-text search, like the '
      + 'built-in patterns. A term matches from the start of a word, case-insensitive; at most '
      + '200 terms of 100 characters each.',
    'feld.SafetyConfigArea.crisis_blocked_tools.label': 'Crisis-blocked tools',
    'feld.SafetyConfigArea.crisis_blocked_tools.hint':
      'Tools that are blocked when moderation reports a hard-block category. On a crisis or '
      + 'threat, the regex filter blocks three fixed search and collection tools regardless.',
    'feld.SafetyConfigArea.crisis_pattern.label': 'Crisis pattern',
    'feld.SafetyConfigArea.crisis_pattern.hint':
      'Pattern that answers when moderation reports a hard-block category that is not a '
      + 'threat (such as self-harm). Empty or missing: M01. Regex filter: always M01 for a '
      + 'crisis.',
    'feld.SafetyConfigArea.threat_pattern.label': 'Threat pattern',
    'feld.SafetyConfigArea.threat_pattern.hint':
      'Pattern that answers when moderation reports a threat as a hard-block category '
      + '(hate/threatening, harassment/threatening). Empty or missing: M02. Regex filter: '
      + 'always M02.',
    'feld.SafetyConfigArea.crisis_message.label': 'Crisis reply',
    'feld.SafetyConfigArea.crisis_message.hint':
      'Reply of the agent endpoint (/api/agent) to a crisis; the run then does not start. '
      + 'Empty = default (turn to family or the contact person at the institution). The chat '
      + 'answers via the crisis pattern.',
    'feld.SafetyConfigArea.crisis_message_en.label': 'Crisis reply (English)',
    'feld.SafetyConfigArea.crisis_message_en.hint':
      'English version of the crisis reply of the agent endpoint, used when the language is '
      + 'English. Empty = the English default.',
    'feld.SafetyConfigArea.escalation.label': 'Escalation',
    'feld.SafetyConfigArea.escalation.hint':
      'Thresholds, hard-block categories and downgrading apply whenever moderation or the '
      + 'legal check runs. Moderation and legal check here are only a fallback when no level '
      + 'preset matches.',
    'feld.EscalationBlock.mode.label': 'Moderation (fallback)',
    'feld.EscalationBlock.mode.hint':
      'Only if the safety level finds no preset: when moderation runs (off = never, smart = '
      + 'at raised risk, always = every message; not set = never). No effect when a preset '
      + 'applies.',
    'feld.EscalationBlock.legal_classifier.label': 'Legal check (fallback)',
    'feld.EscalationBlock.legal_classifier.hint':
      'Only if the safety level finds no preset: on = legal check at raised risk or on a '
      + 'trigger word, off = never. Without an entry, on. No effect when a preset applies.',
    'feld.EscalationBlock.thresholds.label': 'Thresholds per category',
    'feld.EscalationBlock.thresholds.hint':
      'Score (0 to 1) from which a moderation category counts as hit, such as self_harm: 0.25 '
      + 'or sexual/minors: 0.2 — names as moderation reports them, with an underscore for '
      + 'a hyphen. Categories not listed: 0.95. The threshold factor of the level is applied '
      + 'on top. Measured 2026-10-09: lessons on suicide in literature and prevention reach '
      + 'up to 0.16 on self_harm — below that, false alarms loom; 0.25 catches the same hints '
      + 'as 0.17.',
    'feld.EscalationBlock.hard_block_categories.label': 'Hard-block categories',
    'feld.EscalationBlock.hard_block_categories.hint':
      'Moderation categories that count as high risk as soon as they are hit: the crisis or '
      + 'threat pattern answers and the crisis tools are blocked. Spelled as for the '
      + 'thresholds.',
    'feld.EscalationBlock.downgrade_false_positives.label': 'Downgrade false positives',
    'feld.EscalationBlock.downgrade_false_positives.hint':
      'Lowers a medium risk to low when the checks that ran (moderation, legal check) find '
      + 'nothing. Not for a crisis signal or suspected injection. Without an entry, on.',
  },
};
