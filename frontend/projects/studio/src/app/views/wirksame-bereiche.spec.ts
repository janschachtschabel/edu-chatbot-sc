/**
 * Welche Wissensbereiche ein Muster tatsächlich nutzt (Paket 6, S4 — externes
 * Audit F13). Dieselbe Regel wie im Backend — `domain/route_head._resolve_rag_areas`
 * und die Quellen-Sperre in `services/response_tool_selection.py` (`_rag_allowed_for_pattern`);
 * diese Tests halten den Zwilling an beiden fest.
 */
import { describe, expect, it } from 'vitest';

import { wirksameBereiche } from './wirksame-bereiche';

const KATALOG = {
  WLO: { mode: 'always' },
  FAQ: { mode: 'always' },
  Projekt: { mode: 'on-demand' },
  Notiz: 'kein Bereich ohne mode',
};

describe('wirksameBereiche', () => {
  it('nimmt eine gesetzte Liste wörtlich und nennt Namen, die der Katalog nicht kennt', () => {
    expect(wirksameBereiche({ sources: ['mcp', 'rag'], rag_areas: ['FAQ', 'Tippfehler'] }, KATALOG))
      .toEqual({ art: 'gesetzt', bereiche: ['FAQ'], unbekannt: ['Tippfehler'] });
  });

  it('sperrt auch eine gesetzte Liste, wenn `rag` nicht unter den Quellen steht', () => {
    // Die Laufzeit schaltet dann Vorab-Abruf und `query_knowledge` ab, egal
    // was `rag_areas` sagt (Review Paket 6) — ein neues Muster hat nur `mcp`.
    expect(wirksameBereiche({ sources: ['mcp'], rag_areas: ['FAQ'] }, KATALOG))
      .toEqual({ art: 'ohne-rag', bereiche: [], unbekannt: [] });
  });

  it('hält eine ausdrücklich leere Liste auseinander von „nicht gesetzt“', () => {
    expect(wirksameBereiche({ sources: ['rag'], rag_areas: [] }, KATALOG))
      .toEqual({ art: 'gesetzt', bereiche: [], unbekannt: [] });
  });

  it('nimmt ohne Liste die Bereiche „immer“ und danach „auf Abruf“, wenn `rag` unter den Quellen steht', () => {
    const katalog = { Projekt: { mode: 'on-demand' }, WLO: { mode: 'always' } };
    expect(wirksameBereiche({ sources: ['mcp', 'rag'] }, katalog))
      .toEqual({ art: 'vorgabe', bereiche: ['WLO', 'Projekt'], unbekannt: [] });
  });

  it('zählt einen Bereich ohne gültige Abrufart nicht zur Vorgabe', () => {
    const katalog = { WLO: { mode: 'always' }, Leer: { mode: '' }, Alt: { mode: 'nie' } };
    expect(wirksameBereiche({ sources: ['rag'] }, katalog).bereiche).toEqual(['WLO']);
    // Ausdrücklich genannt wirkt er trotzdem: die Laufzeit prüft dort nur, ob es ihn gibt.
    expect(wirksameBereiche({ sources: ['rag'], rag_areas: ['Leer'] }, katalog).bereiche)
      .toEqual(['Leer']);
  });

  it('nimmt keinen Bereich, wenn `rag` nicht unter den Quellen steht', () => {
    expect(wirksameBereiche({ sources: ['mcp'], rag_areas: null }, KATALOG))
      .toEqual({ art: 'ohne-rag', bereiche: [], unbekannt: [] });
  });

  it('rechnet ohne Quellen mit der Vorgabe der Engine (`["mcp"]`), also ohne Wissen', () => {
    expect(wirksameBereiche({}, KATALOG).art).toBe('ohne-rag');
    expect(wirksameBereiche({ rag_areas: ['FAQ'] }, KATALOG).art).toBe('ohne-rag');
  });
});
