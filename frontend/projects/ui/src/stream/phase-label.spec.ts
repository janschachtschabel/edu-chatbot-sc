import { describe, expect, it } from 'vitest';

import { ChatStreamEvent } from './stream-client';
import { formatPhaseLabel } from './phase-label';

/**
 * Charakterisierung von `formatPhaseLabel` (8-4S-d-α) — Verbatim-Port aus ALT
 * `chat/chat-text-utils.ts` (ALT ohne eigene Spec). Gepinnt: die connected-
 * Sonderregel, die nicht-phase/end/unknown → null-Pfade und die vollständige
 * 8-Einträge-step→Label-Map (das Verhaltens-Contract des Lade-Indikators).
 */

const evt = (event: string, data?: any): ChatStreamEvent => ({ event, data } as ChatStreamEvent);

describe('formatPhaseLabel', () => {
  it('connected → "Verbinde …"', () => {
    expect(formatPhaseLabel(evt('connected'))).toBe('Verbinde …');
  });

  it('nicht-phase-Events (result/text_delta/error) → null', () => {
    expect(formatPhaseLabel(evt('result', { content: 'x' }))).toBeNull();
    expect(formatPhaseLabel(evt('text_delta', { delta: 'x' }))).toBeNull();
    expect(formatPhaseLabel(evt('error', { message: 'boom' }))).toBeNull();
  });

  it('phase kind=end → null (unterdrückt Flicker beim Turn-Ende)', () => {
    expect(formatPhaseLabel(evt('phase', { kind: 'end', step: 'response' }))).toBeNull();
  });

  it('vollständige step→Label-Map', () => {
    const cases: Array<[string, string]> = [
      ['safety_classify', 'Verstehe deine Anfrage …'],
      ['context', 'Lade Sitzungs-Kontext …'],
      ['policy', 'Prüfe Datenschutz …'],
      ['pattern', 'Wähle die passende Antwort …'],
      ['wlo_search', 'Durchsuche WLO-Inhalte …'],
      ['topic_content', 'Lade Themenseiten-Inhalte …'],
      ['response', 'Formuliere Antwort …'],
      ['query_meta', 'Suchergebnisse zusammengestellt'],
    ];
    for (const [step, label] of cases) {
      expect(formatPhaseLabel(evt('phase', { step }))).toBe(label);
    }
  });

  it('unbekannter step → null', () => {
    expect(formatPhaseLabel(evt('phase', { step: 'nirgendwo' }))).toBeNull();
  });

  it('phase ohne data → null (leerer step)', () => {
    expect(formatPhaseLabel(evt('phase'))).toBeNull();
  });

  it('falsy evt → null', () => {
    expect(formatPhaseLabel(null as unknown as ChatStreamEvent)).toBeNull();
  });
});
