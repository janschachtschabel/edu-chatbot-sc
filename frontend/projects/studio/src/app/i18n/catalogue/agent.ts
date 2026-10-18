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

    // AG-2 (2026-09-26): der Master-Skill, nur lesend — er bleibt im Repositorium.
    'masterSkill.loading': 'Lade den Master-Skill …',
    'masterSkill.noNode':
      'Kein Master-Skill hinterlegt. Die Kennung setzt der Betrieb in der Umgebung '
      + 'des Backends (MASTER_SKILL_NODE_ID).',
    'masterSkill.state': 'Zustand',
    'masterSkill.state.on': 'Aktiv',
    'masterSkill.state.off': 'Abgeschaltet',
    'masterSkill.node': 'Knoten im Repositorium',
    'masterSkill.fetched': 'Zuletzt geholt',
    'masterSkill.notFetched': 'noch nicht',
    'masterSkill.length': 'Länge',
    'masterSkill.chars.one': '{n} Zeichen',
    'masterSkill.chars.other': '{n} Zeichen',
    'masterSkill.checksum': 'Prüfsumme (SHA-256)',
    'masterSkill.offNote':
      'Abgeschaltet (MASTER_SKILL_ENABLED): der Agent nutzt ihn nur dort, wo eine '
      + 'Einbettung ihn ausdrücklich einschaltet. Der Wortlaut zeigt, was gelten würde.',
    'masterSkill.lastError': 'Der letzte Abruf ist gescheitert: {error}',
    'masterSkill.reload': 'Neu laden',
    'masterSkill.reloading': 'Lädt neu …',
    'masterSkill.reloaded': 'Neu geladen.',
    'masterSkill.reloadFailed': 'Neu laden ist gescheitert: {error}',
    'masterSkill.edit': 'Im Editor bearbeiten',
    'masterSkill.view': 'Im Repositorium ansehen',
    'masterSkill.editHint': 'Speichern setzt eine edu-sharing-Anmeldung in diesem Browser voraus.',
    'masterSkill.linkOf': ': Master-Skill',
    'masterSkill.newTab': '(öffnet einen neuen Tab)',
    'masterSkill.cacheNote':
      'Das Backend holt den Text alle {minutes} min im Hintergrund; ein Chat-Zug wartet nicht '
      + 'darauf (nur direkt nach einem Neustart, solange noch kein Stand da ist). Scheitert ein Abruf, gilt der letzte gute Stand. „Neu laden“ holt ihn sofort '
      + 'in diesem Backend-Prozess; weitere Prozesse folgen mit ihrem nächsten Abruf.',
    'masterSkill.showText': 'Wortlaut anzeigen',
    'masterSkill.textLabel': 'Wortlaut des Master-Skills',
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

    'masterSkill.loading': 'Loading the master skill …',
    'masterSkill.noNode':
      'No master skill configured. Operations set its ID in the backend '
      + 'environment (MASTER_SKILL_NODE_ID).',
    'masterSkill.state': 'State',
    'masterSkill.state.on': 'Active',
    'masterSkill.state.off': 'Switched off',
    'masterSkill.node': 'Node in the repository',
    'masterSkill.fetched': 'Last fetched',
    'masterSkill.notFetched': 'not yet',
    'masterSkill.length': 'Length',
    'masterSkill.chars.one': '{n} character',
    'masterSkill.chars.other': '{n} characters',
    'masterSkill.checksum': 'Checksum (SHA-256)',
    'masterSkill.offNote':
      'Switched off (MASTER_SKILL_ENABLED): the agent only uses it where an embedding '
      + 'explicitly switches it on. The text shows what would apply.',
    'masterSkill.lastError': 'The last fetch failed: {error}',
    'masterSkill.reload': 'Reload',
    'masterSkill.reloading': 'Reloading …',
    'masterSkill.reloaded': 'Reloaded.',
    'masterSkill.reloadFailed': 'Reload failed: {error}',
    'masterSkill.edit': 'Edit in the editor',
    'masterSkill.view': 'View in the repository',
    'masterSkill.editHint': 'Saving requires an edu-sharing login in this browser.',
    'masterSkill.linkOf': ': master skill',
    'masterSkill.newTab': '(opens a new tab)',
    'masterSkill.cacheNote':
      'The backend fetches the text every {minutes} min in the background; a chat turn does not '
      + 'wait for it (only right after a restart, while there is no version yet). If a fetch fails, the last good version stays. “Reload” fetches it right '
      + 'away in this backend process; other processes follow with their next fetch.',
    'masterSkill.showText': 'Show the text',
    'masterSkill.textLabel': 'Text of the master skill',
  },
};
