/**
 * Die Teilkataloge des Studios, in der Reihenfolge, in der sie entstanden sind.
 *
 * EINE Liste und nicht je Sprache eine: ein neuer Teil kann so nicht
 * versehentlich nur auf Deutsch eingehängt werden, und `parts.spec.ts` deckt
 * jeden künftigen Teil ohne Nacharbeit ab. `de.ts` und `en.ts` setzen daraus
 * die beiden vollständigen Kataloge zusammen — die Schnittstelle nach draussen
 * bleibt unverändert.
 */
import { AGENT } from './agent';
import { AGENT_CENTER } from './agent-center';
import { AGENT_PROMPT } from './agent-prompt';
import { AGENT_PROBE } from './agent-probe';
import { AGENT_TRACE } from './agent-trace';
import { AREA_EDITOR } from './area-editor';
import { BACKUP } from './backup';
import type { CataloguePart } from './catalogue-part';
import { COSTS } from './costs';
import { CURATED } from './curated';
import { CURATED_BETRIEB } from './curated-betrieb';
import { FASSUNGEN } from './fassungen';
import { EFFECTS } from './effects';
import { EVAL_CLASSIFICATION } from './eval-classification';
import { EVAL_COMPARE } from './eval-compare';
import { EVAL_DETAIL } from './eval-detail';
import { EVAL_PATTERN } from './eval-pattern';
import { EVAL_PROFILE } from './eval-profile';
import { EVAL_START } from './eval-start';
import { EVAL_TRENDS } from './eval-trends';
import { EVALUATION } from './evaluation';
import { FIELDS_AGENT } from './fields-agent';
import { FIELDS_ANZEIGE_KOPF_GERAETE } from './fields-anzeige-kopf-geraete';
import { FIELDS_ANZEIGE_REGELN } from './fields-anzeige-regeln';
import { FIELDS_AUSWAHL } from './fields-auswahl';
import { FIELDS_BEGRUESSUNG } from './fields-begruessung';
import { FIELDS_DATENSCHUTZ } from './fields-datenschutz';
import { FIELDS_DROSSELUNG_PROTOKOLL } from './fields-drosselung-protokoll';
import { FIELDS_ENTITIES_SIGNALS } from './fields-entities-signals';
import { FIELDS_INTENTS_STATES } from './fields-intents-states';
import { FIELDS_KARTEN } from './fields-karten';
import { FIELDS_KLASSIFIKATION } from './fields-klassifikation';
import { FIELDS_KOSTEN_EVAL } from './fields-kosten-eval';
import { FIELDS_LAYER_DOC } from './fields-layer-doc';
import { FIELDS_LOTSE } from './fields-lotse';
import { FIELDS_MATERIAL } from './fields-material';
import { FIELDS_PATTERNS } from './fields-patterns';
import { FIELDS_PERSONAS } from './fields-personas';
import { FIELDS_REGELWERK } from './fields-regelwerk';
import { FIELDS_SICHERHEIT } from './fields-sicherheit';
import { FIELDS_TONE } from './fields-tone';
import { FIELDS_TOUR } from './fields-tour';
import { FIELDS_WISSENSBEREICHE } from './fields-wissensbereiche';
import { FRAME } from './frame';
import { GROUP_SECTION } from './group-section';
import { KNOWLEDGE } from './knowledge';
import { LOADTEST } from './loadtest';
import { MCP } from './mcp';
import { OVERVIEW } from './overview';
import { PREVIEW } from './preview';
import { PRIVACY_PURGE } from './privacy-purge';
import { QUALITY } from './quality';
import { QUALITY_FLOW } from './quality-flow';
import { QUALITY_LOGS } from './quality-logs';
import { QUALITY_MATRIX } from './quality-matrix';
import { REFERENCE } from './reference';
import { REFERENCE_CATALOGS } from './reference-catalogs';
import { REFERENCE_FLOW } from './reference-flow';
import { REFERENCE_KNOWLEDGE } from './reference-knowledge';
import { REFERENCE_MACHINES } from './reference-machines';
import { REFERENCE_ROWS } from './reference-rows';
import { REFERENCE_WIDGET } from './reference-widget';
import { RESTORE_MODE } from './restore-mode';
import { RETENTION } from './retention';
import { SAFETY } from './safety';
import { SESSIONS } from './sessions';
import { SHARED } from './shared';
import { VALIDATION } from './validation';
import { VIEWS } from './views';

export const STUDIO_PARTS: readonly CataloguePart[] = [
  FRAME, VIEWS, SHARED, AREA_EDITOR, GROUP_SECTION, BACKUP, FASSUNGEN, RESTORE_MODE, PREVIEW, KNOWLEDGE, MCP, CURATED, CURATED_BETRIEB, OVERVIEW,
  EVALUATION, EVAL_DETAIL, EVAL_PATTERN, EVAL_TRENDS, EVAL_START,
  QUALITY, QUALITY_MATRIX, QUALITY_FLOW, QUALITY_LOGS,
  LOADTEST, SESSIONS, SAFETY, COSTS, AGENT,
  REFERENCE, REFERENCE_ROWS, REFERENCE_KNOWLEDGE, REFERENCE_WIDGET, REFERENCE_FLOW,
  REFERENCE_CATALOGS, REFERENCE_MACHINES,
  // ST-1: Beschriftung und Hilfetext je Formularfeld, nach Modell geschlüsselt
  FIELDS_LAYER_DOC, FIELDS_BEGRUESSUNG, FIELDS_TOUR,
  FIELDS_INTENTS_STATES, FIELDS_ENTITIES_SIGNALS, FIELDS_TONE, FIELDS_MATERIAL,
  FIELDS_ANZEIGE_REGELN, FIELDS_ANZEIGE_KOPF_GERAETE, FIELDS_PATTERNS, FIELDS_PERSONAS,
  FIELDS_SICHERHEIT, FIELDS_DROSSELUNG_PROTOKOLL, FIELDS_REGELWERK, FIELDS_DATENSCHUTZ,
  FIELDS_WISSENSBEREICHE, FIELDS_AGENT,
  // ST-2d: Klartexte der Auswahlwerte · ST-2e: Prüffehler am Feld
  FIELDS_AUSWAHL, VALIDATION,
  // ST-6: Löschen über alle Sitzungen, Datenbank aufräumen
  PRIVACY_PURGE,
  // ST-9: die acht Bereiche, die bis dahin nur unter „Alle Bereiche“ standen
  FIELDS_KARTEN, FIELDS_LOTSE, FIELDS_KLASSIFIKATION, FIELDS_KOSTEN_EVAL,
  // ST-5: wo ein Bereich wirkt
  EFFECTS,
  // ST-7: Maschine je Lauf, Lauf-Profil, Vergleich
  EVAL_PROFILE, EVAL_COMPARE, EVAL_CLASSIFICATION,
  // ST-8: Agent-Steuerzentrale
  AGENT_TRACE, AGENT_CENTER, AGENT_PROMPT, AGENT_PROBE,
  // Paket 8 (A): Aufbewahrung der Protokolle
  RETENTION,
];
