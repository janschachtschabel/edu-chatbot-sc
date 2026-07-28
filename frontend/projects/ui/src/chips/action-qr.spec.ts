import { describe, it, expect } from 'vitest';
import {
  isActionQuickReply, parseActionQuickReply, actionQuickReplyLabel,
} from './action-qr';

const VALID = '__action__|Sammlung erkunden|browse_collection|{"collection_id":"C1","title":"Optik"}';

describe('action-qr: parseActionQuickReply', () => {
  it('parst ein gültiges Action-Pill', () => {
    expect(parseActionQuickReply(VALID)).toEqual({
      label: 'Sammlung erkunden',
      action: 'browse_collection',
      params: { collection_id: 'C1', title: 'Optik' },
    });
  });

  it('params-JSON darf ein Pipe enthalten (Split nur auf erste 2 Pipes)', () => {
    expect(parseActionQuickReply('__action__|L|a|{"title":"A|B"}')?.params).toEqual({ title: 'A|B' });
  });

  it('kaputtes JSON → null (Aufrufer fällt auf Text zurück)', () => {
    expect(parseActionQuickReply('__action__|L|a|{kaputt')).toBeNull();
  });

  it('fehlendes action-Segment → null', () => {
    expect(parseActionQuickReply('__action__|NurLabel')).toBeNull();
  });

  it('leeres Label oder action → null', () => {
    expect(parseActionQuickReply('__action__||browse_collection|{}')).toBeNull();
    expect(parseActionQuickReply('__action__|L||{}')).toBeNull();
  });

  it('JSON-Array statt Objekt → null', () => {
    expect(parseActionQuickReply('__action__|L|a|[1,2]')).toBeNull();
  });

  it('Nicht-Action-String → null', () => {
    expect(parseActionQuickReply('Normale Pille')).toBeNull();
  });
});

describe('action-qr: isActionQuickReply / actionQuickReplyLabel', () => {
  it('erkennt Action-Pills', () => {
    expect(isActionQuickReply(VALID)).toBe(true);
    expect(isActionQuickReply('Normale Pille')).toBe(false);
  });

  it('Label eines gültigen Pills', () => {
    expect(actionQuickReplyLabel(VALID)).toBe('Sammlung erkunden');
  });

  it('Label bleibt für Nicht-Action-Strings der Rohstring', () => {
    expect(actionQuickReplyLabel('Normale Pille')).toBe('Normale Pille');
  });

  it('strukturell Action-Pill mit kaputtem JSON → Label trotzdem extrahierbar', () => {
    expect(actionQuickReplyLabel('__action__|Kaputt|browse_collection|{bad')).toBe('Kaputt');
  });
});
