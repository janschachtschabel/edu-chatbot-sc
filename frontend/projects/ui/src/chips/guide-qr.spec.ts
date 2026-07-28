import { describe, expect, it } from 'vitest';

import {
  guideQuickReplyLabel,
  guideQuickReplyUrl,
  isGuideQuickReply,
  shouldHideGuideQuickReply,
} from './guide-qr';

const VALID = '__guide__|Zur Themenseite|https://redaktion.openeduhub.net/x';

describe('guide-qr: isGuideQuickReply', () => {
  it('erkennt Guide-QR nur bei aktivem Lotsen-Modus', () => {
    expect(isGuideQuickReply(VALID, true)).toBe(true);
    expect(isGuideQuickReply(VALID, false)).toBe(false);
    expect(isGuideQuickReply('Normale Pille', true)).toBe(false);
  });
});

describe('guide-qr: shouldHideGuideQuickReply', () => {
  it('versteckt Guide-QR nur wenn Lotsen-Modus aus', () => {
    expect(shouldHideGuideQuickReply(VALID, false)).toBe(true);
    expect(shouldHideGuideQuickReply(VALID, true)).toBe(false);
    expect(shouldHideGuideQuickReply('Normale Pille', false)).toBe(false);
  });
});

describe('guide-qr: label + url', () => {
  it('extrahiert Label und URL eines gültigen Guide-QR', () => {
    expect(guideQuickReplyLabel(VALID, true)).toBe('Zur Themenseite');
    expect(guideQuickReplyUrl(VALID, true)).toBe('https://redaktion.openeduhub.net/x');
  });

  it('Label fällt auf "Bring mich hin" zurück bei leerem Segment / ohne Separator', () => {
    expect(guideQuickReplyLabel('__guide__||https://x.de', true)).toBe('Bring mich hin');
    expect(guideQuickReplyLabel('__guide__|nurlabel', true)).toBe('nurlabel');
    expect(guideQuickReplyLabel('__guide__|', true)).toBe('Bring mich hin');
  });

  it('URL ist leer ohne Separator oder wenn kein Guide-QR', () => {
    expect(guideQuickReplyUrl('__guide__|nurlabel', true)).toBe('');
    expect(guideQuickReplyUrl(VALID, false)).toBe('');
  });

  it('Nicht-Guide-String bleibt für das Label der Rohstring', () => {
    expect(guideQuickReplyLabel('Normale Pille', true)).toBe('Normale Pille');
  });
});
