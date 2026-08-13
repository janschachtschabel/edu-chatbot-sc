/**
 * Die Ansicht „Agent & Maschine" (2026-08-13) — Formular auf `POST /api/agent`.
 *
 * Die Feldnamen (`instruction`, `collection_id`, …) bleiben englisch: sie sind
 * der Vertrag des Endpunkts und stehen so in `schemas_agent.py`. Was hier steht,
 * ist die Beschriftung darüber — und der Hinweis darunter, der sagt, wozu das
 * Feld gut ist. Wer den Endpunkt selbst ruft, findet den Feldnamen im Hinweis
 * wieder.
 */
import type { CataloguePart } from './catalogue-part';

export const AGENT: CataloguePart = {
  de: {
    'agent.field.instruction': 'Anweisung',
    'agent.field.instructionHint':
      '`instruction` — die Aufgabe, im Klartext. „Prüfe diese Inhalte auf '
      + 'Sachrichtigkeit und begründe kurz." Alles andere ist optional.',
    'agent.field.collection': 'Sammlung',
    'agent.field.collectionHint':
      '`collection_id` — aus dieser Sammlung holt der Agent seine Anleitungen '
      + '(Skills). Wird vorab aufgelöst.',
    'agent.field.nodes': 'Knoten',
    'agent.field.nodesHint':
      '`node_ids` — die Inhalte, um die es geht. Eine ID je Zeile oder durch '
      + 'Kommas getrennt, höchstens 50.',
    'agent.field.schema': 'Ergebnis-Schema (JSON)',
    'agent.field.schemaHint':
      '`result_schema` — verlangt eine maschinenlesbare Antwort in dieser Form. '
      + 'Leer lassen für reinen Text.',
    'agent.field.write': 'Schreibrecht',
    'agent.field.locale': 'Sprache',
    'agent.field.curation': 'Kurations-Werkzeuge erlauben',
    'agent.field.curationHint':
      '`allow_curation` — an ist die Vorgabe. Aus genommen läuft derselbe Auftrag '
      + 'ohne die schreibenden Werkzeuge; genau der Modus, den man vor einem '
      + 'Schreiblauf einmal gesehen haben will.',

    'agent.write.default': 'Vorgabe aus 01-base/engine',
    'agent.write.propose': 'nur vorschlagen (propose)',
    'agent.write.execute': 'ausführen (execute)',
    'agent.locale.default': 'Vorgabe des Hauses',
    'agent.locale.de': 'Deutsch',
    'agent.locale.en': 'Englisch',

    'agent.costNote':
      'Ein Lauf fährt die echte Schleife: bis zu einem Dutzend Modell-Runden plus '
      + 'MCP-Werkzeuge. Er kostet also Geld und Staging-Kapazität — wie ein Lasttest, '
      + 'nicht wie eine Suche. Die Deckel stehen im Abschnitt darüber.',
    'agent.run': 'Lauf starten',
    'agent.running': 'Läuft …',

    'agent.error.instruction': 'Ohne Anweisung gibt es nichts zu tun.',
    'agent.error.tooManyNodes': 'Höchstens 50 Knoten — das ist die Grenze des Abrufs.',
    'agent.error.schema':
      'Das Ergebnis-Schema ist kein lesbares JSON-Objekt. Es wurde nichts geschickt.',
    'agent.error.forbidden':
      'Der Endpunkt hat den Zugang abgelehnt. Ist die Studio-Anmeldung noch gültig?',
    'agent.error.rateLimit': 'Zu viele Läufe hintereinander. Kurz warten und erneut versuchen.',

    'agent.result.ready': 'Der Lauf ist fertig — das Ergebnis steht darunter.',
    'agent.result.title': 'Ergebnis',
    'agent.result.stopReason': 'Abbruchgrund',
    'agent.result.iterations': 'Runden',
    'agent.result.tools': 'Gerufene Werkzeuge',
    'agent.result.noTools': 'keine',
    'agent.result.text': 'Antworttext',
    'agent.result.noText': '(kein Text)',
    'agent.result.structured': 'Strukturiertes Ergebnis',
    'agent.result.noStructured':
      'Keines — das entsteht nur, wenn ein Ergebnis-Schema mitgegeben wurde.',
  },

  en: {
    'agent.field.instruction': 'Instruction',
    'agent.field.instructionHint':
      '`instruction` — the task, in plain words. “Check these items for factual '
      + 'accuracy and give a short reason.” Everything else is optional.',
    'agent.field.collection': 'Collection',
    'agent.field.collectionHint':
      '`collection_id` — the agent takes its instructions (skills) from this '
      + 'collection. Resolved up front.',
    'agent.field.nodes': 'Nodes',
    'agent.field.nodesHint':
      '`node_ids` — the items in question. One ID per line or comma-separated, '
      + 'at most 50.',
    'agent.field.schema': 'Result schema (JSON)',
    'agent.field.schemaHint':
      '`result_schema` — demands a machine-readable answer in this shape. Leave '
      + 'empty for plain text.',
    'agent.field.write': 'Write mode',
    'agent.field.locale': 'Language',
    'agent.field.curation': 'Allow curation tools',
    'agent.field.curationHint':
      '`allow_curation` — on is the default. Switched off, the same task runs '
      + 'without the writing tools; exactly the mode worth seeing once before a '
      + 'write run.',

    'agent.write.default': 'default from 01-base/engine',
    'agent.write.propose': 'propose only',
    'agent.write.execute': 'execute',
    'agent.locale.default': 'house default',
    'agent.locale.de': 'German',
    'agent.locale.en': 'English',

    'agent.costNote':
      'A run drives the real loop: up to a dozen model rounds plus MCP tools. So it '
      + 'costs money and staging capacity — like a load test, not like a search. The '
      + 'caps are in the section above.',
    'agent.run': 'Start run',
    'agent.running': 'Running …',

    'agent.error.instruction': 'Without an instruction there is nothing to do.',
    'agent.error.tooManyNodes': 'At most 50 nodes — that is the fetch limit.',
    'agent.error.schema':
      'The result schema is not a readable JSON object. Nothing was sent.',
    'agent.error.forbidden':
      'The endpoint refused access. Is the studio login still valid?',
    'agent.error.rateLimit': 'Too many runs in a row. Wait a moment and try again.',

    'agent.result.ready': 'The run has finished — the result is below.',
    'agent.result.title': 'Result',
    'agent.result.stopReason': 'Stop reason',
    'agent.result.iterations': 'Rounds',
    'agent.result.tools': 'Tools called',
    'agent.result.noTools': 'none',
    'agent.result.text': 'Answer text',
    'agent.result.noText': '(no text)',
    'agent.result.structured': 'Structured result',
    'agent.result.noStructured':
      'None — this only appears when a result schema was supplied.',
  },
};
