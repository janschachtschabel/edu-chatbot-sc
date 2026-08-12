import { describe, expect, it } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import {
  guideQuickReplyLabel,
  guideQuickReplyUrl,
  isGuideQuickReply,
  shouldHideGuideQuickReply,
} from './guide-qr';

const VALID = '__guide__|Zur Themenseite|https://redaktion.openeduhub.net/x';
const t = createTranslator(DE, DE);

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
    expect(guideQuickReplyLabel(VALID, true, t)).toBe('Zur Themenseite');
    expect(guideQuickReplyUrl(VALID, true)).toBe('https://redaktion.openeduhub.net/x');
  });

  it('Label fällt auf "Bring mich hin" zurück bei leerem Segment / ohne Separator', () => {
    expect(guideQuickReplyLabel('__guide__||https://x.de', true, t)).toBe('Bring mich hin');
    expect(guideQuickReplyLabel('__guide__|nurlabel', true, t)).toBe('nurlabel');
    expect(guideQuickReplyLabel('__guide__|', true, t)).toBe('Bring mich hin');
  });

  it('URL ist leer ohne Separator oder wenn kein Guide-QR', () => {
    expect(guideQuickReplyUrl('__guide__|nurlabel', true)).toBe('');
    expect(guideQuickReplyUrl(VALID, false)).toBe('');
  });

  it('Nicht-Guide-String bleibt für das Label der Rohstring', () => {
    expect(guideQuickReplyLabel('Normale Pille', true, t)).toBe('Normale Pille');
  });

  it('nur der Rückfall kommt aus dem Übersetzer — das Backend-Label bleibt stehen (C1-b4)', () => {
    const en = createTranslator({ 'chips.guideFallback': 'Take me there' }, DE);
    expect(guideQuickReplyLabel('__guide__|', true, en)).toBe('Take me there');
    // Das Label im Marker ist Backend-Inhalt und geht nie durch den Katalog.
    expect(guideQuickReplyLabel(VALID, true, en)).toBe('Zur Themenseite');
  });
});
