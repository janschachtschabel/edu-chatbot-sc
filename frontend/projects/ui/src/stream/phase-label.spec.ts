import { describe, expect, it } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { ChatStreamEvent } from './stream-client';
import { formatPhaseLabel } from './phase-label';

/** Deutscher Übersetzer — pinnt den bisherigen Wortlaut über den Katalog. */
const t = createTranslator(DE, DE);

/**
 * Charakterisierung von `formatPhaseLabel` (8-4S-d-α) — Verbatim-Port aus ALT
 * `chat/chat-text-utils.ts` (ALT ohne eigene Spec). Gepinnt: die connected-
 * Sonderregel, die nicht-phase/end/unknown → null-Pfade und die vollständige
 * step→Label-Map (das Verhaltens-Contract des Lade-Indikators) — seit A6 in
 * zwei Gruppen: acht Schritte der Muster-Engine, zwei der Agent-Schleife.
 */

const evt = (event: string, data?: any): ChatStreamEvent => ({ event, data } as ChatStreamEvent);

describe('formatPhaseLabel', () => {
  it('connected → "Verbinde …"', () => {
    expect(formatPhaseLabel(evt('connected'), t)).toBe('Verbinde …');
  });

  it('nicht-phase-Events (result/text_delta/error) → null', () => {
    expect(formatPhaseLabel(evt('result', { content: 'x' }), t)).toBeNull();
    expect(formatPhaseLabel(evt('text_delta', { delta: 'x' }), t)).toBeNull();
    expect(formatPhaseLabel(evt('error', { message: 'boom' }), t)).toBeNull();
  });

  it('phase kind=end → null (unterdrückt Flicker beim Turn-Ende)', () => {
    expect(formatPhaseLabel(evt('phase', { kind: 'end', step: 'response' }), t)).toBeNull();
  });

  it('vollständige step→Label-Map der Muster-Engine', () => {
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
      expect(formatPhaseLabel(evt('phase', { step }), t)).toBe(label);
    }
  });

  it('Agent-Modus: beide Schleifen-Schritte tragen ein eigenes Label (A6)', () => {
    // Ohne diese zwei stünde im Agent-Modus den ganzen Lauf über „Formuliere
    // Antwort …" — das Etikett, das `respond_agent` beim Eintritt setzt und das
    // niemand mehr ablöst (`send-message.ts`: `if (!label) return`).
    expect(formatPhaseLabel(evt('phase', { step: 'agent_iteration', iteration: 3 }), t))
      .toBe('Überlege den nächsten Schritt …');
    expect(formatPhaseLabel(evt('phase', { step: 'agent_tool', tool: 'search_wlo_content' }), t))
      .toBe('Arbeite mit WLO-Inhalten …');
  });

  it('der Werkzeugname bleibt draussen — die Bubble spricht keine Maschinensprache', () => {
    // Das Ereignis TRÄGT ihn (`{tool}`), und ihn einzusetzen wäre eine Zeile.
    // Der Katalog kennt aber bis heute kein einziges Maschinenwort; ein
    // „wlo_delete_content" in der Ladeblase wäre das erste.
    const label = formatPhaseLabel(
      evt('phase', { step: 'agent_tool', tool: 'wlo_delete_content' }), t);
    expect(label).toBe('Arbeite mit WLO-Inhalten …');
    expect(label).not.toContain('wlo_delete_content');
  });

  it('unbekannter step → null', () => {
    expect(formatPhaseLabel(evt('phase', { step: 'nirgendwo' }), t)).toBeNull();
  });

  it('phase ohne data → null (leerer step)', () => {
    expect(formatPhaseLabel(evt('phase'), t)).toBeNull();
  });

  it('falsy evt → null', () => {
    expect(formatPhaseLabel(null as unknown as ChatStreamEvent, t)).toBeNull();
  });

  it('nimmt die Labels aus dem Übersetzer (C1-b3)', () => {
    const en = createTranslator({ 'phase.connected': 'Connecting …', 'phase.wlo_search': 'Searching WLO …' }, DE);
    expect(formatPhaseLabel(evt('connected'), en)).toBe('Connecting …');
    expect(formatPhaseLabel(evt('phase', { step: 'wlo_search' }), en)).toBe('Searching WLO …');
    expect(formatPhaseLabel(evt('phase', { step: 'response' }), en)).toBe('Formuliere Antwort …');
  });

  it('ein unbekannter step bleibt null — der Schlüssel darf nie in die Bubble', () => {
    // Ohne die Erlaubnisliste läge hier `t('phase.nirgendwo')` = der Schlüssel
    // selbst, und der Ladehinweis zeigte „phase.nirgendwo".
    const laut = createTranslator({}, {});
    expect(formatPhaseLabel(evt('phase', { step: 'nirgendwo' }), laut)).toBeNull();
  });
});
