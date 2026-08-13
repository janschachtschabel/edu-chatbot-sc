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
import { AREA_EDITOR } from './area-editor';
import { BACKUP } from './backup';
import type { CataloguePart } from './catalogue-part';
import { COSTS } from './costs';
import { CURATED } from './curated';
import { EVAL_DETAIL } from './eval-detail';
import { EVAL_PATTERN } from './eval-pattern';
import { EVAL_START } from './eval-start';
import { EVAL_TRENDS } from './eval-trends';
import { EVALUATION } from './evaluation';
import { FRAME } from './frame';
import { KNOWLEDGE } from './knowledge';
import { LOADTEST } from './loadtest';
import { MCP } from './mcp';
import { OVERVIEW } from './overview';
import { PREVIEW } from './preview';
import { QUALITY } from './quality';
import { QUALITY_FLOW } from './quality-flow';
import { QUALITY_LOGS } from './quality-logs';
import { QUALITY_MATRIX } from './quality-matrix';
import { REFERENCE } from './reference';
import { REFERENCE_CATALOGS } from './reference-catalogs';
import { REFERENCE_FLOW } from './reference-flow';
import { REFERENCE_KNOWLEDGE } from './reference-knowledge';
import { REFERENCE_ROWS } from './reference-rows';
import { REFERENCE_WIDGET } from './reference-widget';
import { SAFETY } from './safety';
import { SESSIONS } from './sessions';
import { SHARED } from './shared';
import { VIEWS } from './views';

export const STUDIO_PARTS: readonly CataloguePart[] = [
  FRAME, VIEWS, SHARED, AREA_EDITOR, BACKUP, PREVIEW, KNOWLEDGE, MCP, CURATED, OVERVIEW,
  EVALUATION, EVAL_DETAIL, EVAL_PATTERN, EVAL_TRENDS, EVAL_START,
  QUALITY, QUALITY_MATRIX, QUALITY_FLOW, QUALITY_LOGS,
  LOADTEST, SESSIONS, SAFETY, COSTS, AGENT,
  REFERENCE, REFERENCE_ROWS, REFERENCE_KNOWLEDGE, REFERENCE_WIDGET, REFERENCE_FLOW,
  REFERENCE_CATALOGS,
];
