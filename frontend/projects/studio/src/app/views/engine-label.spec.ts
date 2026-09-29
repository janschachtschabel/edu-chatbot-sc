import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { Translate } from '../i18n/studio-language.service';
import { engineLabel } from './engine-label';

// Über `I18n` wie in `gold-scorecard.spec.ts` — derselbe Weg wie im Betrieb.
const übersetzer = (locale: 'de' | 'en'): Translate => {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  return (key, params) => i18n.t(key, params);
};

describe('engineLabel (ST-7a)', () => {
  it('nennt die Maschinen wie der Umschalter und die Wirkungs-Hinweise', () => {
    const de = übersetzer('de');
    expect(engineLabel('pattern', de)).toBe('Muster-Maschine');
    expect(engineLabel('agent', de)).toBe('Agent-Schleife');
  });

  it('nennt den entfernten Hybrid älterer Läufe und sagt, wenn nichts bekannt ist', () => {
    const de = übersetzer('de');
    expect(engineLabel('hybrid', de)).toBe('Hybrid (entfernt)');
    expect(engineLabel('', de)).toBe('Maschine unbekannt');
  });

  it('zeigt einen fremden Wert roh statt eines Katalog-Schlüssels', () => {
    expect(engineLabel('warp', übersetzer('de'))).toBe('warp');
  });

  it('spricht Englisch', () => {
    const en = übersetzer('en');
    expect(engineLabel('pattern', en)).toBe('Pattern engine');
    expect(engineLabel('hybrid', en)).toBe('Hybrid (removed)');
    expect(engineLabel('', en)).toBe('Engine unknown');
  });
});
