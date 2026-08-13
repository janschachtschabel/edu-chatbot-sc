import { describe, expect, it } from 'vitest';

import { MAX_NODE_IDS, buildAgentRequest, parseNodeIds } from './agent-request';

describe('parseNodeIds', () => {
  it('nimmt Zeilen, Kommas und Leerzeichen als Trenner', () => {
    // Wer IDs aus einer Tabelle oder aus edu-sharing kopiert, bekommt mal das
    // eine, mal das andere. Den Nutzer auf EIN Trennzeichen festzulegen hiesse,
    // ihn die Liste von Hand nachbearbeiten zu lassen.
    expect(parseNodeIds('a\nb, c  d\n\n')).toEqual(['a', 'b', 'c', 'd']);
  });

  it('wirft Doubletten raus, behält aber die Reihenfolge', () => {
    expect(parseNodeIds('a\nb\na')).toEqual(['a', 'b']);
  });

  it('ist bei leerer Eingabe leer, nicht [""]', () => {
    expect(parseNodeIds('   \n ')).toEqual([]);
  });
});

describe('buildAgentRequest', () => {
  const basis = { instruction: 'Prüfe die Sachrichtigkeit', collectionId: '', nodeIds: '',
                  resultSchema: '', writeMode: '', locale: '', allowCuration: true };

  it('schickt nur die Anweisung, wenn sonst nichts ausgefüllt ist', () => {
    // Leere Felder WEGLASSEN statt als "" zu schicken: `collection_id: ""`
    // liesse das Backend eine Sammlung mit leerer ID auflösen wollen, und
    // `write_mode: ""` fiele durch die Literal-Prüfung von AgentRequest.
    const gebaut = buildAgentRequest(basis);
    expect(gebaut.request).toEqual({ instruction: 'Prüfe die Sachrichtigkeit' });
    expect(gebaut.error).toBeNull();
  });

  it('verweigert eine leere Anweisung', () => {
    const gebaut = buildAgentRequest({ ...basis, instruction: '  ' });
    expect(gebaut.request).toBeNull();
    expect(gebaut.error).toBe('agent.error.instruction');
  });

  it('übernimmt die ausgefüllten Felder', () => {
    const gebaut = buildAgentRequest({
      ...basis, collectionId: ' abc ', nodeIds: 'n1, n2',
      writeMode: 'execute', locale: 'en',
    });
    expect(gebaut.request).toEqual({
      instruction: 'Prüfe die Sachrichtigkeit',
      collection_id: 'abc',
      node_ids: ['n1', 'n2'],
      write_mode: 'execute',
      locale: 'en',
    });
  });

  it('deckelt die Knotenliste dort, wo das Backend sie deckelt', () => {
    // MAX_NODE_IDS = 50 (`schemas_agent.py`). Ohne Deckel hier käme eine
    // 422 zurück, deren Text der Nutzer auf seine Anweisung bezöge.
    const zuviele = Array.from({ length: MAX_NODE_IDS + 5 }, (_, i) => `n${i}`).join('\n');
    const gebaut = buildAgentRequest({ ...basis, nodeIds: zuviele });
    expect(gebaut.request).toBeNull();
    expect(gebaut.error).toBe('agent.error.tooManyNodes');
  });

  it('reicht ein Ergebnis-Schema als Objekt weiter', () => {
    const gebaut = buildAgentRequest({
      ...basis, resultSchema: '{"type":"object","properties":{"note":{"type":"number"}}}',
    });
    expect(gebaut.request?.result_schema).toEqual({
      type: 'object', properties: { note: { type: 'number' } },
    });
  });

  it('verweigert ein unlesbares Schema, statt es wegzulassen', () => {
    // Stillschweigend weglassen wäre das Schlimmste: der Lauf liefe, kostete
    // Geld und lieferte kein strukturiertes Ergebnis — und niemand wüsste warum.
    const gebaut = buildAgentRequest({ ...basis, resultSchema: '{kein json' });
    expect(gebaut.request).toBeNull();
    expect(gebaut.error).toBe('agent.error.schema');
  });

  it('lässt `allow_curation` weg, solange es die Vorgabe ist', () => {
    // `AgentRequest.allow_curation` steht im Backend auf `true`. Es trotzdem
    // mitzuschicken wäre eine Zeile, die nichts sagt — und beim nächsten
    // Vorgabewechsel eine, die die neue Vorgabe still überstimmt. Dieselbe
    // Linie wie bei den leeren Textfeldern.
    expect(buildAgentRequest(basis).request).not.toHaveProperty('allow_curation');
  });

  it('schickt `allow_curation: false`, wenn der Haken weg ist', () => {
    // Der eingeschränkte Modus ist genau der, den man VOR einem Schreiblauf
    // sehen will. Ohne Schalter liesse er sich über diese Ansicht nie prüfen —
    // das Formular deckte fünf der sechs Felder ab und schwieg über das sechste.
    expect(buildAgentRequest({ ...basis, allowCuration: false }).request).toEqual({
      instruction: 'Prüfe die Sachrichtigkeit',
      allow_curation: false,
    });
  });

  it('verweigert ein Schema, das kein Objekt ist', () => {
    // `result_schema` ist im Backend ein dict. Eine Liste oder eine Zahl parst
    // sauber und wäre trotzdem falsch — 422, erst nach dem Absenden.
    expect(buildAgentRequest({ ...basis, resultSchema: '[1,2]' }).error).toBe('agent.error.schema');
    expect(buildAgentRequest({ ...basis, resultSchema: '42' }).error).toBe('agent.error.schema');
  });
});
