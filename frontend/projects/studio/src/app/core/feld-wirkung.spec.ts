import { describe, expect, it } from 'vitest';

import type { AreaEffects } from './effects-api.service';
import { abschnittsWirkung, feldPlakette } from './feld-wirkung';

/**
 * Rundgang 3: „Wirkt in …“ galt je Bereich — an Abschnitten mit Feld-Ausschnitt falsch
 * (Rolle & Schutz zeigte „Muster (teilweise)“ für Felder, die nur der Agent liest). Die
 * Feld-Ausnahmen kommen aus dem Backend (`FIELD_EFFECTS`).
 */
const EFFECTS: AreaEffects = {
  engine: 'agent',
  areas: {
    '01-base/engine': { pattern: 'teilweise', agent: 'teilweise' },
    '01-base/safety-config': { pattern: 'teilweise', agent: 'voll' },
  },
  fields: {
    '01-base/engine': {
      agent_rolle: { pattern: 'keine', agent: 'voll' },
      agent: { pattern: 'keine', agent: 'voll' },
      muster_skills: { pattern: 'voll', agent: 'keine' },
    },
    '01-base/safety-config': {
      crisis_message: { pattern: 'keine', agent: 'extern' },
      crisis_pattern: { pattern: 'voll', agent: 'krise' },
    },
  },
};

describe('abschnittsWirkung', () => {
  it('nimmt ohne Feld-Ausschnitt die Wirkung des Bereichs', () => {
    expect(abschnittsWirkung(EFFECTS, '01-base/engine', undefined))
      .toEqual({ pattern: 'teilweise', agent: 'teilweise' });
  });

  it('nimmt die gemeinsame Wirkung der gezeigten Felder', () => {
    expect(abschnittsWirkung(EFFECTS, '01-base/engine', ['agent_rolle', 'agent']))
      .toEqual({ pattern: 'keine', agent: 'voll' });
  });

  it('sagt „teilweise“, wo die gezeigten Felder verschieden wirken', () => {
    expect(abschnittsWirkung(EFFECTS, '01-base/engine', ['agent_rolle', 'muster_skills']))
      .toEqual({ pattern: 'teilweise', agent: 'teilweise' });
  });

  it('zählt ein Feld ohne Ausnahme mit der Wirkung des Bereichs', () => {
    expect(abschnittsWirkung(EFFECTS, '01-base/engine', ['agent', 'mode']))
      .toEqual({ pattern: 'teilweise', agent: 'teilweise' });
  });

  it('bleibt leer ohne Zuordnung', () => {
    expect(abschnittsWirkung(null, '01-base/engine', undefined)).toBeNull();
    expect(abschnittsWirkung(EFFECTS, 'gibt/es-nicht', undefined)).toBeNull();
  });
});

describe('feldPlakette', () => {
  it('kennzeichnet im Agent-Arbeitsbereich Felder ohne Agent-Wirkung', () => {
    expect(feldPlakette(EFFECTS, '01-base/engine', 'muster_skills', 'agent')).toBe('nurMuster');
    expect(feldPlakette(EFFECTS, '01-base/safety-config', 'crisis_pattern', 'agent'))
      .toBe('nurKrise');
    expect(feldPlakette(EFFECTS, '01-base/safety-config', 'crisis_message', 'agent'))
      .toBe('nurExtern');
  });

  it('kennzeichnet im Muster-Arbeitsbereich reine Agent-Felder', () => {
    expect(feldPlakette(EFFECTS, '01-base/engine', 'agent_rolle', 'pattern')).toBe('nurAgent');
    expect(feldPlakette(EFFECTS, '01-base/engine', 'muster_skills', 'pattern')).toBeNull();
  });

  it('schweigt bei Feldern, die wirken, und bei Feldern ohne Ausnahme', () => {
    expect(feldPlakette(EFFECTS, '01-base/engine', 'agent_rolle', 'agent')).toBeNull();
    expect(feldPlakette(EFFECTS, '01-base/engine', 'mode', 'agent')).toBeNull();
    // Nur der genannte Pfad, nicht jedes Kind — sonst stünde die Plakette überall.
    expect(feldPlakette(EFFECTS, '01-base/engine', 'agent_rolle.rolle', 'pattern')).toBeNull();
  });

  it('nennt Felder ohne jede Wirkung in beiden Arbeitsbereichen', () => {
    const ohne: AreaEffects = { ...EFFECTS, fields: { 'x/y': { start_label: {
      pattern: 'keine', agent: 'keine' } } } };
    expect(feldPlakette(ohne, 'x/y', 'start_label', 'agent')).toBe('ohneWirkung');
    expect(feldPlakette(ohne, 'x/y', 'start_label', 'pattern')).toBe('ohneWirkung');
  });

  it('sagt im Muster-Arbeitsbereich „nur externer Auftrag“ statt „nur Agent“ (Review A-2)', () => {
    const effects = {
      engine: 'pattern' as const, areas: { 'a/b': { pattern: 'voll' as const, agent: 'voll' as const } },
      fields: { 'a/b': {
        text: { pattern: 'keine' as const, agent: 'extern' as const },
        krise: { pattern: 'keine' as const, agent: 'krise' as const },
        kopf: { pattern: 'keine' as const, agent: 'voll' as const },
      } },
    };
    expect(feldPlakette(effects, 'a/b', 'text', 'pattern')).toBe('nurExtern');
    expect(feldPlakette(effects, 'a/b', 'krise', 'pattern')).toBe('nurKrise');
    expect(feldPlakette(effects, 'a/b', 'kopf', 'pattern')).toBe('nurAgent');
  });
});

