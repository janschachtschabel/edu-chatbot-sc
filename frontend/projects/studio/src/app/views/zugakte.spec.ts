import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import type { Translate } from '../i18n/studio-language.service';
import { fehlernummer, readZugakte, statusLabel, umschreibungLabel } from './zugakte';

const übersetzer = (locale: 'de' | 'en'): Translate => {
  const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
  i18n.setLocale(locale);
  return (key, params) => i18n.t(key, params);
};

/** Eine Akte, wie `services/zugakte.Zugakte.als_dict` sie unter `debug._zugakte` ablegt. */
const AKTE = {
  werkzeuge: [
    {
      name: 'search_wlo_content',
      argumente_eingang: { query: 'Optik', maxItems: 5 },
      argumente_gesendet: { query: 'Optik', maxItems: 5 },
      status: 'ok', aus_cache: false, dauer_ms: 420, zeichen: 3800, fehler: null,
    },
    {
      name: 'get_collection_contents',
      argumente_eingang: { collection: 'Optik' },
      argumente_gesendet: { nodeId: 'abc-1' },
      status: 'tool', aus_cache: true, dauer_ms: 12, zeichen: null, fehler: 'Sammlung leer',
    },
  ],
  werkzeuge_ausgelassen: 3,
  umschreibungen: [
    { art: 'typ_fokus', original: 'Hier sind Webseiten …', ersatz: 'Für Videos schau in die Suche unten.', grund: 'Video' },
  ],
  schnellwege: [{ art: 'canvas', thema: 'Linsen' }],
};

describe('readZugakte', () => {
  it('liest Werkzeugaufrufe, Umschreibungen und Schnellwege', () => {
    const akte = readZugakte(AKTE)!;
    expect(akte.werkzeuge).toHaveLength(2);
    expect(akte.werkzeuge[0]).toMatchObject({
      name: 'search_wlo_content', status: 'ok', ausCache: false, dauerMs: 420, zeichen: 3800,
      fehler: '',
    });
    expect(akte.ausgelassen).toBe(3);
    expect(akte.umschreibungen).toEqual([
      { art: 'typ_fokus', original: 'Hier sind Webseiten …', ersatz: 'Für Videos schau in die Suche unten.', grund: 'Video' },
    ]);
    expect(akte.schnellwege).toEqual([{ art: 'canvas', thema: 'Linsen' }]);
  });

  it('zeigt die gesendeten Argumente nur, wenn sie von den eingegangenen abweichen', () => {
    // Die Auflösung (Sammlungsname → Kennung) ist genau das, was man sucht.
    const [gleich, aufgeloest] = readZugakte(AKTE)!.werkzeuge;
    expect(gleich.argumenteEingang).toContain('"query": "Optik"');
    expect(gleich.argumenteGesendet).toBe('');
    expect(aufgeloest.argumenteGesendet).toContain('"nodeId": "abc-1"');
    expect(aufgeloest.fehler).toBe('Sammlung leer');
    expect(aufgeloest.zeichen).toBeNull();
  });

  it('eine leere oder kaputte Akte ergibt null — kein leerer Abschnitt', () => {
    for (const roh of [undefined, null, {}, [], 'x', { werkzeuge: 'x', umschreibungen: 3 }]) {
      expect(readZugakte(roh)).toBeNull();
    }
  });

  it('prüft jedes Feld statt zu vertrauen: Einträge ohne Namen fallen weg, falsche Zahlen werden 0', () => {
    const akte = readZugakte({
      werkzeuge: [{ status: 'ok' }, { name: 'x', dauer_ms: 'lang', aus_cache: 'ja', zeichen: -1 }],
      umschreibungen: [{ art: 'waechter' }, 7],
    })!;
    expect(akte.werkzeuge).toEqual([expect.objectContaining({
      name: 'x', status: '', ausCache: false, dauerMs: 0, zeichen: null,
    })]);
    expect(akte.umschreibungen).toEqual([{ art: 'waechter', original: '', ersatz: '', grund: '' }]);
  });
});

describe('fehlernummer', () => {
  it('ist der Anfang der Trace-ID — wie in der Fehlerblase', () => {
    expect(fehlernummer('4711abcdef01-zug-zwei')).toBe('4711abcdef01');
    expect(fehlernummer('kurz')).toBe('kurz');
  });

  it('ohne Trace-ID keine Nummer', () => {
    expect(fehlernummer(undefined)).toBe('');
    expect(fehlernummer(42)).toBe('');
  });
});

describe('Bezeichnungen', () => {
  it('Status und Art der Umschreibung aus der Erlaubnisliste, Unbekanntes roh', () => {
    const t = übersetzer('de');
    expect(statusLabel('timeout', t)).toBe('Zeitüberschreitung');
    expect(statusLabel('toString', t)).toBe('toString');
    expect(umschreibungLabel('typ_fokus', t)).toBe('Typ-Fokus');
    expect(umschreibungLabel('neu', t)).toBe('neu');
    expect(statusLabel('ok', übersetzer('en'))).toBe('ok');
    // Review 2026-10-30: Aufrufe, die nicht zurückkamen (Paket 18G-4).
    expect(statusLabel('abgebrochen', t)).toBe('Abgebrochen (Frist)');
    expect(statusLabel('ausnahme', übersetzer('en'))).toBe('unexpected error');
  });
});
